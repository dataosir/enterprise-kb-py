from __future__ import annotations

from typing import Protocol

from langchain_core.documents import Document


class VectorStore(Protocol):
  """向量库抽象 — Demo 用 Chroma，生产用 pgvector。"""

  @property
  def backend(self) -> str:
    """chroma | pgvector"""
    ...

  def status(self) -> str:
    """connected | unavailable | fallback"""
    ...

  def add_documents(self, chunks: list[Document]) -> None: ...

  def similarity_search_with_score(self, query: str, k: int) -> list[tuple[Document, float]]: ...

  def max_marginal_relevance_search(
    self,
    query: str,
    k: int,
    fetch_k: int,
    lambda_mult: float,
  ) -> list[Document]: ...

  def delete_by_doc_id(self, doc_id: str) -> None: ...

  def count(self) -> int: ...
