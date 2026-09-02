from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from langchain_chroma import Chroma
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import (
    CHAT_MODEL,
    CHROMA_DIR,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    LOCAL_EMBEDDING_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    UPLOAD_DIR,
)
from app.models.domain import DocumentRecord, RetrievedChunk
from app.store.document_store import DocumentStore, get_document_store
from app.store.rag_settings import RagSettingsStore, get_rag_settings_store

logger = logging.getLogger(__name__)


class RagEngine:
    """RAG 核心引擎：文档入库 → 向量检索 → LLM 生成。"""

    def __init__(
        self,
        doc_store: DocumentStore | None = None,
        settings_store: RagSettingsStore | None = None,
    ) -> None:
        self.doc_store = doc_store or get_document_store()
        self.settings_store = settings_store or get_rag_settings_store()
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)

        llm_kwargs: dict[str, Any] = {
            "model": CHAT_MODEL,
            "api_key": OPENAI_API_KEY,
            "temperature": 0.2,
        }
        if OPENAI_BASE_URL:
            llm_kwargs["base_url"] = OPENAI_BASE_URL

        if EMBEDDING_PROVIDER == "openai":
            embed_kwargs: dict[str, Any] = {
                "model": EMBEDDING_MODEL,
                "api_key": OPENAI_API_KEY,
            }
            if OPENAI_BASE_URL:
                embed_kwargs["base_url"] = OPENAI_BASE_URL
            self.embeddings = OpenAIEmbeddings(**embed_kwargs)
        else:
            self.embeddings = HuggingFaceEmbeddings(
                model_name=LOCAL_EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )

        self.llm = ChatOpenAI(**llm_kwargs)
        self.vectorstore = Chroma(
            collection_name="enterprise_kb",
            embedding_function=self.embeddings,
            persist_directory=str(CHROMA_DIR),
        )
        self._refresh_splitter()
        self._memory: dict[str, list[tuple[str, str]]] = {}
        self._prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是企业内部知识库助手。仅根据提供的上下文回答，"
                    "不知道就说不知道。回答简洁，并在末尾列出引用文档名。",
                ),
                ("human", "上下文:\n{context}\n\n历史:\n{history}\n\n问题: {question}"),
            ]
        )

    def get_settings(self) -> dict:
        return self.settings_store.get().to_api_dict()

    def update_settings(
        self,
        *,
        top_k: int | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> dict:
        settings = self.settings_store.get()
        next_chunk_size = chunk_size if chunk_size is not None else settings.chunk_size
        next_chunk_overlap = (
            chunk_overlap if chunk_overlap is not None else settings.chunk_overlap
        )
        if next_chunk_overlap >= next_chunk_size:
            raise ValueError("chunk_overlap 必须小于 chunk_size")

        updated = self.settings_store.update(
            top_k=top_k,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        self._refresh_splitter()
        return updated.to_api_dict()

    def reindex_all(self) -> dict:
        records = [r for r in self.doc_store.list_all() if r.status == "READY"]
        total_chunks = 0
        reindexed = 0

        for record in records:
            path = Path(record.file_path)
            if not path.exists():
                logger.warning("Skip reindex, file missing: %s", record.file_path)
                continue

            self.vectorstore.delete(where={"doc_id": record.id})
            chunk_count = self._ingest_chunks(path, record.filename, record.id)
            self.doc_store.update_chunk_count(record.id, chunk_count)
            total_chunks += chunk_count
            reindexed += 1

        self.settings_store.mark_indexed()
        message = f"已重建 {reindexed} 篇文档索引，共 {total_chunks} 个片段"
        logger.info(message)
        return {
            "reindexed": reindexed,
            "total_chunks": total_chunks,
            "message": message,
        }

    def ingest_file(
        self,
        file_path: Path,
        filename: str,
        doc_id: str | None = None,
        *,
        file_size: int | None = None,
        persist_metadata: bool = True,
    ) -> int:
        doc_id = doc_id or str(uuid4())
        size = file_size if file_size is not None else file_path.stat().st_size

        try:
            docs = self._load_documents(file_path, filename)
            for doc in docs:
                doc.metadata["doc_id"] = doc_id
                doc.metadata["filename"] = filename

            chunks = self.splitter.split_documents(docs)
            if not chunks:
                if persist_metadata:
                    self.doc_store.add(
                        DocumentRecord(
                            id=doc_id,
                            filename=filename,
                            file_path=str(file_path),
                            file_size=size,
                            chunk_count=0,
                            status="FAILED",
                            created_at=datetime.now(timezone.utc),
                        )
                    )
                return 0

            self.vectorstore.add_documents(chunks)

            if persist_metadata:
                self.doc_store.add(
                    DocumentRecord(
                        id=doc_id,
                        filename=filename,
                        file_path=str(file_path),
                        file_size=size,
                        chunk_count=len(chunks),
                        status="READY",
                        created_at=datetime.now(timezone.utc),
                    )
                )
                self.settings_store.mark_indexed()

            logger.info("Ingested %s: %d chunks", filename, len(chunks))
            return len(chunks)
        except Exception:
            logger.exception("Failed to ingest %s", filename)
            if persist_metadata:
                self.doc_store.add(
                    DocumentRecord(
                        id=doc_id,
                        filename=filename,
                        file_path=str(file_path),
                        file_size=size,
                        chunk_count=0,
                        status="FAILED",
                        created_at=datetime.now(timezone.utc),
                    )
                )
            raise

    def delete_document(self, doc_id: str) -> bool:
        record = self.doc_store.get(doc_id)
        if not record:
            return False

        self.vectorstore.delete(where={"doc_id": doc_id})
        self.doc_store.delete(doc_id)

        file_path = Path(record.file_path)
        if file_path.exists() and file_path.parent == UPLOAD_DIR:
            file_path.unlink(missing_ok=True)

        logger.info("Deleted document %s (%s)", doc_id, record.filename)
        return True

    def retrieve_sources(self, question: str) -> list[RetrievedChunk]:
        top_k = self.settings_store.get().top_k
        results = self.vectorstore.similarity_search_with_score(question, k=top_k)
        chunks: list[RetrievedChunk] = []
        for doc, score in results:
            content = doc.page_content
            chunks.append(
                RetrievedChunk(
                    filename=str(doc.metadata.get("filename", "unknown")),
                    content=content,
                    snippet=self._truncate(content, 200),
                    score=float(score),
                )
            )
        return chunks

    def chat(self, question: str, conversation_id: str) -> tuple[str, list[RetrievedChunk]]:
        sources = self.retrieve_sources(question)
        context = "\n\n".join(f"[{s.filename}] {s.content}" for s in sources)
        history = self._format_history(conversation_id)

        chain = self._prompt | self.llm
        answer = chain.invoke(
            {"context": context or "（无相关上下文）", "history": history, "question": question}
        ).content

        self._append_memory(conversation_id, question, str(answer))
        return str(answer), sources

    def stream_chat(self, question: str, conversation_id: str) -> Iterator[str]:
        sources = self.retrieve_sources(question)
        context = "\n\n".join(f"[{s.filename}] {s.content}" for s in sources)
        history = self._format_history(conversation_id)

        chain = self._prompt | self.llm
        full_answer = ""
        for chunk in chain.stream(
            {"context": context or "（无相关上下文）", "history": history, "question": question}
        ):
            text = chunk.content
            if text:
                full_answer += text
                yield text

        self._append_memory(conversation_id, question, full_answer)

    def vector_count(self) -> int:
        return self.vectorstore._collection.count()

    def _ingest_chunks(self, file_path: Path, filename: str, doc_id: str) -> int:
        docs = self._load_documents(file_path, filename)
        for doc in docs:
            doc.metadata["doc_id"] = doc_id
            doc.metadata["filename"] = filename

        chunks = self.splitter.split_documents(docs)
        if not chunks:
            return 0

        self.vectorstore.add_documents(chunks)
        return len(chunks)

    def _refresh_splitter(self) -> None:
        settings = self.settings_store.get()
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    def _load_documents(self, file_path: Path, filename: str) -> list[Document]:
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            loader = PyPDFLoader(str(file_path))
        elif suffix in {".md", ".markdown"}:
            loader = TextLoader(str(file_path), encoding="utf-8")
        elif suffix in {".doc", ".docx"}:
            loader = Docx2txtLoader(str(file_path))
        else:
            loader = TextLoader(str(file_path), encoding="utf-8")

        docs = loader.load()
        for doc in docs:
            doc.metadata["source"] = filename
        return docs

    def _format_history(self, conversation_id: str) -> str:
        turns = self._memory.get(conversation_id, [])
        if not turns:
            return "（无）"
        return "\n".join(f"用户: {q}\n助手: {a}" for q, a in turns[-3:])

    def _append_memory(self, conversation_id: str, question: str, answer: str) -> None:
        self._memory.setdefault(conversation_id, []).append((question, answer))

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."


_rag_engine: RagEngine | None = None


def get_rag_engine() -> RagEngine:
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RagEngine()
    return _rag_engine
