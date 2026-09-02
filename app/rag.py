from __future__ import annotations

from dataclasses import dataclass
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
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    LOCAL_EMBEDDING_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    TOP_K,
    UPLOAD_DIR,
)


@dataclass
class RetrievedChunk:
    filename: str
    snippet: str
    score: float


class RagEngine:
    """LangChain RAG 引擎 — 面试重点：Retriever + Prompt + 引用来源。"""

    def __init__(self) -> None:
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
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )
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

    def ingest_file(self, file_path: Path, filename: str, doc_id: str | None = None) -> int:
        docs = self._load_documents(file_path, filename)
        doc_id = doc_id or str(uuid4())
        for doc in docs:
            doc.metadata["doc_id"] = doc_id
            doc.metadata["filename"] = filename

        chunks = self.splitter.split_documents(docs)
        if not chunks:
            return 0

        self.vectorstore.add_documents(chunks)
        return len(chunks)

    def retrieve_sources(self, question: str) -> list[RetrievedChunk]:
        results = self.vectorstore.similarity_search_with_score(question, k=TOP_K)
        chunks: list[RetrievedChunk] = []
        for doc, score in results:
            chunks.append(
                RetrievedChunk(
                    filename=str(doc.metadata.get("filename", "unknown")),
                    snippet=self._truncate(doc.page_content, 200),
                    score=float(score),
                )
            )
        return chunks

    def chat(self, question: str, conversation_id: str) -> tuple[str, list[RetrievedChunk]]:
        sources = self.retrieve_sources(question)
        context = "\n\n".join(
            f"[{s.filename}] {self._truncate(s.snippet, 300)}" for s in sources
        )
        history = self._format_history(conversation_id)

        chain = self._prompt | self.llm
        answer = chain.invoke(
            {"context": context or "（无相关上下文）", "history": history, "question": question}
        ).content

        self._append_memory(conversation_id, question, str(answer))
        return str(answer), sources

    def stream_chat(self, question: str, conversation_id: str) -> Iterator[str]:
        sources = self.retrieve_sources(question)
        context = "\n\n".join(
            f"[{s.filename}] {self._truncate(s.snippet, 300)}" for s in sources
        )
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

