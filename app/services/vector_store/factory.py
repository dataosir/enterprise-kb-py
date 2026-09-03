from __future__ import annotations

import logging

from langchain_core.embeddings import Embeddings

from app.config import DATABASE_URL, VECTOR_STORE
from app.services.vector_store.base import VectorStore
from app.services.vector_store.chroma_store import ChromaVectorStore
from app.services.vector_store.pgvector_store import PgVectorStore
from app.store.pg_client import check_pg_connection

logger = logging.getLogger(__name__)


class FallbackVectorStore:
  """pgvector 不可用时的 Chroma 回退包装。"""

  def __init__(self, inner: ChromaVectorStore, reason: str) -> None:
    self._inner = inner
    self._reason = reason

  @property
  def backend(self) -> str:
    return "chroma"

  def status(self) -> str:
    return "fallback"

  @property
  def fallback_reason(self) -> str:
    return self._reason

  def add_documents(self, chunks) -> None:
    self._inner.add_documents(chunks)

  def similarity_search_with_score(self, query: str, k: int):
    return self._inner.similarity_search_with_score(query, k=k)

  def max_marginal_relevance_search(self, query: str, k: int, fetch_k: int, lambda_mult: float):
    return self._inner.max_marginal_relevance_search(query, k, fetch_k, lambda_mult)

  def delete_by_doc_id(self, doc_id: str) -> None:
    self._inner.delete_by_doc_id(doc_id)

  def count(self) -> int:
    return self._inner.count()


def create_vector_store(embeddings: Embeddings) -> VectorStore:
  chroma = ChromaVectorStore(embeddings)

  if VECTOR_STORE != "pgvector":
    return chroma

  if not DATABASE_URL:
    logger.warning("VECTOR_STORE=pgvector 但未配置 DATABASE_URL，已回退 Chroma")
    return FallbackVectorStore(chroma, "DATABASE_URL not configured")

  if not check_pg_connection():
    logger.warning("PostgreSQL/pgvector 不可用，已回退 Chroma")
    return FallbackVectorStore(chroma, "PostgreSQL unavailable")

  try:
    store = PgVectorStore(embeddings, DATABASE_URL)
    logger.info("Using pgvector vector store")
    return store
  except Exception as exc:
    logger.warning("PgVector 初始化失败，已回退 Chroma: %s", exc)
    return FallbackVectorStore(chroma, str(exc))
