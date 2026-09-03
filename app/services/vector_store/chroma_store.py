from __future__ import annotations

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.config import CHROMA_DIR


class ChromaVectorStore:
  def __init__(self, embeddings: Embeddings) -> None:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    self._store = Chroma(
      collection_name="enterprise_kb",
      embedding_function=embeddings,
      persist_directory=str(CHROMA_DIR),
    )

  @property
  def backend(self) -> str:
    return "chroma"

  def status(self) -> str:
    return "connected"

  def add_documents(self, chunks: list[Document]) -> None:
    self._store.add_documents(chunks)

  def similarity_search_with_score(self, query: str, k: int) -> list[tuple[Document, float]]:
    return self._store.similarity_search_with_score(query, k=k)

  def max_marginal_relevance_search(
    self,
    query: str,
    k: int,
    fetch_k: int,
    lambda_mult: float,
  ) -> list[Document]:
    return self._store.max_marginal_relevance_search(
      query,
      k=k,
      fetch_k=fetch_k,
      lambda_mult=lambda_mult,
    )

  def delete_by_doc_id(self, doc_id: str) -> None:
    self._store.delete(where={"doc_id": doc_id})

  def count(self) -> int:
    return self._store._collection.count()
