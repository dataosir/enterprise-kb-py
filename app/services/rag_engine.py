from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import (
    CHAT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    LOCAL_EMBEDDING_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
)
from app.services.vector_store.factory import create_vector_store
from app.store.object_storage.factory import get_object_storage
from app.store.object_storage.paths import open_document_path
from app.models.domain import DocumentRecord, RetrievedChunk
from app.services.retrieval.context_builder import build_context
from app.services.retrieval.es_store import ElasticsearchStore, get_es_store
from app.services.retrieval.hybrid import fuse_hybrid_results
from app.services.retrieval.reranker import Reranker
from app.store.conversation_store import ConversationStore, get_conversation_store
from app.store.document_store import DocumentStore, get_document_store
from app.store.rag_settings import RagSettingsStore, get_rag_settings_store

logger = logging.getLogger(__name__)


class RagEngine:
    """RAG 核心引擎：文档入库 → 向量检索 → LLM 生成。"""

    def __init__(
        self,
        doc_store: DocumentStore | None = None,
        settings_store: RagSettingsStore | None = None,
        es_store: ElasticsearchStore | None = None,
        conversation_store: ConversationStore | None = None,
    ) -> None:
        self.doc_store = doc_store or get_document_store()
        self.settings_store = settings_store or get_rag_settings_store()
        self.es_store = es_store if es_store is not None else get_es_store()
        self.conversation_store = conversation_store or get_conversation_store()
        self.object_storage = get_object_storage()
        self._reranker = Reranker()

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

        self.vectorstore = create_vector_store(self.embeddings)
        self._refresh_splitter()
        self._refresh_llm()
        self._refresh_prompt()

    def get_settings(self) -> dict:
        data = self.settings_store.get().to_api_dict()
        data["esEnabled"] = self.es_store.enabled
        data["esStatus"] = self.es_store.status()
        data["esChunkCount"] = self.es_store.count() if self.es_store.available else 0
        data["vectorStore"] = self.vectorstore.backend
        data["vectorStatus"] = self.vectorstore.status()
        data["vectorChunkCount"] = self.vector_count()
        data["storageBackend"] = self.object_storage.backend
        data["storageStatus"] = self.object_storage.status()
        return data

    def update_settings(
        self,
        *,
        top_k: int | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        score_threshold: float | None = ...,  # type: ignore[assignment]
        fetch_k: int | None = None,
        use_mmr: bool | None = None,
        mmr_lambda: float | None = None,
        use_rerank: bool | None = None,
        temperature: float | None = None,
        history_turns: int | None = None,
        max_context_chars: int | None = None,
        system_prompt: str | None = None,
        snippet_length: int | None = None,
        retrieval_mode: str | None = None,
        hybrid_alpha: float | None = None,
        rrf_k: int | None = None,
    ) -> dict:
        updated = self.settings_store.update(
            top_k=top_k,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            score_threshold=score_threshold,
            fetch_k=fetch_k,
            use_mmr=use_mmr,
            mmr_lambda=mmr_lambda,
            use_rerank=use_rerank,
            temperature=temperature,
            history_turns=history_turns,
            max_context_chars=max_context_chars,
            system_prompt=system_prompt,
            snippet_length=snippet_length,
            retrieval_mode=retrieval_mode,
            hybrid_alpha=hybrid_alpha,
            rrf_k=rrf_k,
        )
        self._refresh_splitter()
        if temperature is not None:
            self._refresh_llm()
        if system_prompt is not None:
            self._refresh_prompt()
        return updated.to_api_dict() | {
            "esEnabled": self.es_store.enabled,
            "esStatus": self.es_store.status(),
            "esChunkCount": self.es_store.count() if self.es_store.available else 0,
            "vectorStore": self.vectorstore.backend,
            "vectorStatus": self.vectorstore.status(),
            "vectorChunkCount": self.vector_count(),
            "storageBackend": self.object_storage.backend,
            "storageStatus": self.object_storage.status(),
        }

    def reindex_all(self) -> dict:
        records = [r for r in self.doc_store.list_all() if r.status == "READY"]
        total_chunks = 0
        reindexed = 0

        for record in records:
            if not self._document_file_available(record.file_path):
                logger.warning("Skip reindex, file missing: %s", record.file_path)
                continue

            self.vectorstore.delete_by_doc_id(record.id)
            chunk_count = self._ingest_chunks(record.file_path, record.filename, record.id)
            self.doc_store.update_chunk_count(record.id, chunk_count)
            total_chunks += chunk_count
            reindexed += 1

        self.settings_store.mark_indexed()
        message = f"已重建 {reindexed} 篇文档索引，共 {total_chunks} 个片段"
        if self.es_store.available:
            message += f"；ES 全文索引 {self.es_store.count()} 个片段"
        logger.info(message)
        return {
            "reindexed": reindexed,
            "total_chunks": total_chunks,
            "message": message,
        }

    def sync_es_index(self) -> dict:
        """全量重建向量库与 Elasticsearch 索引，确保 chunk_id 一致。"""
        if not self.es_store.available:
            raise ValueError("Elasticsearch 未配置或不可用，无法同步")

        self.es_store.clear_index()
        result = self.reindex_all()
        return {
            "synced_documents": result["reindexed"],
            "total_chunks": result["total_chunks"],
            "message": result["message"],
        }

    def ingest_file(
        self,
        storage_ref: str | Path,
        filename: str,
        doc_id: str | None = None,
        *,
        file_size: int | None = None,
        persist_metadata: bool = True,
    ) -> int:
        doc_id = doc_id or str(uuid4())
        storage_ref_str = str(storage_ref)
        if file_size is not None:
            size = file_size
        elif storage_ref_str.startswith("s3://"):
            raise ValueError("file_size is required for S3 storage references")
        else:
            size = Path(storage_ref_str).stat().st_size

        try:
            with open_document_path(storage_ref_str) as local_path:
                docs = self._load_documents(local_path, filename)
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
                            file_path=storage_ref_str,
                            file_size=size,
                            chunk_count=0,
                            status="FAILED",
                            created_at=datetime.now(timezone.utc),
                        )
                    )
                return 0

            self._assign_chunk_ids(chunks)
            self.vectorstore.add_documents(chunks)
            self.es_store.delete_by_doc_id(doc_id)
            self.es_store.index_chunks(chunks)

            if persist_metadata:
                self.doc_store.add(
                    DocumentRecord(
                        id=doc_id,
                        filename=filename,
                        file_path=storage_ref_str,
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
                        file_path=storage_ref_str,
                        file_size=size,
                        chunk_count=0,
                        status="FAILED",
                        created_at=datetime.now(timezone.utc),
                    )
                )
            raise

    def process_document_ingest(self, doc_id: str) -> int:
        """处理已上传文档的入库（供异步入库 Worker 调用）。"""
        record = self.doc_store.get(doc_id)
        if not record:
            raise ValueError(f"Document not found: {doc_id}")

        if not self._document_file_available(record.file_path):
            self.doc_store.update_status(doc_id, "FAILED", chunk_count=0)
            raise FileNotFoundError(f"File missing: {record.file_path}")

        self.doc_store.update_status(doc_id, "PROCESSING")
        try:
            self.vectorstore.delete_by_doc_id(doc_id)
            chunk_count = self._ingest_chunks(record.file_path, record.filename, doc_id)
            if chunk_count == 0:
                self.doc_store.update_status(doc_id, "FAILED", chunk_count=0)
                return 0

            self.doc_store.update_chunk_count(doc_id, chunk_count, status="READY")
            self.settings_store.mark_indexed()
            logger.info("Processed ingest for %s: %d chunks", record.filename, chunk_count)
            return chunk_count
        except Exception:
            self.doc_store.update_status(doc_id, "FAILED", chunk_count=0)
            raise

    def delete_document(self, doc_id: str) -> bool:
        record = self.doc_store.get(doc_id)
        if not record:
            return False

        self.vectorstore.delete_by_doc_id(doc_id)
        self.es_store.delete_by_doc_id(doc_id)
        self.doc_store.delete(doc_id)

        if self.object_storage.is_managed_upload(record.file_path):
            self.object_storage.delete(record.file_path)

        logger.info("Deleted document %s (%s)", doc_id, record.filename)
        return True

    def retrieve_sources(self, question: str) -> list[RetrievedChunk]:
        settings = self.settings_store.get()
        fetch_k = max(settings.fetch_k, settings.top_k)
        results: list[tuple[Document, float]]

        use_hybrid = (
            settings.retrieval_mode == "hybrid"
            and self.es_store.available
            and self.es_store.count() > 0
        )
        if settings.retrieval_mode == "hybrid" and not use_hybrid:
            logger.warning("混合检索已开启但 ES 不可用或索引为空，已回退为纯向量检索")

        if use_hybrid:
            vector_results = self.vectorstore.similarity_search_with_score(question, k=fetch_k)
            bm25_results = self.es_store.search(question, size=fetch_k)
            results = fuse_hybrid_results(
                vector_results,
                bm25_results,
                alpha=settings.hybrid_alpha,
                rrf_k=settings.rrf_k,
            )
        elif settings.use_mmr:
            docs = self.vectorstore.max_marginal_relevance_search(
                question,
                k=settings.top_k,
                fetch_k=fetch_k,
                lambda_mult=settings.mmr_lambda,
            )
            results = [(doc, 0.0) for doc in docs]
        else:
            results = self.vectorstore.similarity_search_with_score(question, k=fetch_k)

        if settings.score_threshold is not None and not use_hybrid:
            results = [
                (doc, score)
                for doc, score in results
                if float(score) <= settings.score_threshold
            ]

        if settings.use_rerank and results:
            results = self._reranker.rerank(question, results, settings.top_k)
        else:
            results = results[: settings.top_k]

        chunks: list[RetrievedChunk] = []
        for doc, score in results:
            content = doc.page_content
            chunks.append(
                RetrievedChunk(
                    filename=str(doc.metadata.get("filename", "unknown")),
                    content=content,
                    snippet=self._truncate(content, settings.snippet_length),
                    score=float(score),
                )
            )
        return chunks

    def chat(self, question: str, conversation_id: str) -> tuple[str, list[RetrievedChunk]]:
        sources = self.retrieve_sources(question)
        settings = self.settings_store.get()
        context = build_context(sources, settings.max_context_chars)
        history = self._format_history(conversation_id)

        chain = self._prompt | self.llm
        answer = chain.invoke(
            {"context": context or "（无相关上下文）", "history": history, "question": question}
        ).content

        self._append_memory(conversation_id, question, str(answer))
        return str(answer), sources

    def stream_chat(self, question: str, conversation_id: str) -> Iterator[str]:
        sources = self.retrieve_sources(question)
        settings = self.settings_store.get()
        context = build_context(sources, settings.max_context_chars)
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
        return self.vectorstore.count()

    def _document_file_available(self, storage_ref: str) -> bool:
        if storage_ref.startswith("s3://"):
            return True
        return Path(storage_ref).exists()

    def _ingest_chunks(self, storage_ref: str, filename: str, doc_id: str) -> int:
        self.es_store.delete_by_doc_id(doc_id)
        with open_document_path(storage_ref) as file_path:
            docs = self._load_documents(file_path, filename)
            for doc in docs:
                doc.metadata["doc_id"] = doc_id
                doc.metadata["filename"] = filename

            chunks = self.splitter.split_documents(docs)
            if not chunks:
                return 0

            self._assign_chunk_ids(chunks)
            self.vectorstore.add_documents(chunks)
            self.es_store.index_chunks(chunks)
            return len(chunks)

    @staticmethod
    def _assign_chunk_ids(chunks: list[Document]) -> None:
        for chunk in chunks:
            chunk.metadata["chunk_id"] = str(uuid4())

    def _refresh_splitter(self) -> None:
        settings = self.settings_store.get()
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    def _refresh_llm(self) -> None:
        settings = self.settings_store.get()
        llm_kwargs: dict[str, Any] = {
            "model": CHAT_MODEL,
            "api_key": OPENAI_API_KEY,
            "temperature": settings.temperature,
        }
        if OPENAI_BASE_URL:
            llm_kwargs["base_url"] = OPENAI_BASE_URL
        self.llm = ChatOpenAI(**llm_kwargs)

    def _refresh_prompt(self) -> None:
        settings = self.settings_store.get()
        prompt_text = settings.system_prompt.strip() or DEFAULT_SYSTEM_PROMPT
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", prompt_text),
                ("human", "上下文:\n{context}\n\n历史:\n{history}\n\n问题: {question}"),
            ]
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
        settings = self.settings_store.get()
        turns = self.conversation_store.get_turns(conversation_id)
        if not turns or settings.history_turns <= 0:
            return "（无）"
        return "\n".join(
            f"用户: {q}\n助手: {a}" for q, a in turns[-settings.history_turns :]
        )

    def _append_memory(self, conversation_id: str, question: str, answer: str) -> None:
        self.conversation_store.append_turn(conversation_id, question, answer)

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
