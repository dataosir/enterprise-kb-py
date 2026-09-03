from __future__ import annotations

import json
import logging
from typing import Any

from langchain_community.vectorstores.utils import maximal_marginal_relevance
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.store.pg_client import get_pg_connection

logger = logging.getLogger(__name__)


class PgVectorStore:
  """PostgreSQL + pgvector 向量库（生产环境）。"""

  def __init__(self, embeddings: Embeddings, connection_url: str) -> None:
    self.embeddings = embeddings
    self.connection_url = connection_url
    self._dimension = len(embeddings.embed_query("dimension_probe"))
    self._init_schema()

  @property
  def backend(self) -> str:
    return "pgvector"

  def status(self) -> str:
    return "connected"

  def _init_schema(self) -> None:
    with get_pg_connection() as conn:
      with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute(
          f"""
          CREATE TABLE IF NOT EXISTS kb_chunks (
              id          TEXT PRIMARY KEY,
              doc_id      TEXT NOT NULL,
              filename    TEXT NOT NULL,
              content     TEXT NOT NULL,
              embedding   vector({self._dimension}),
              metadata    JSONB DEFAULT '{{}}'::jsonb,
              created_at  TIMESTAMPTZ DEFAULT now()
          )
          """
        )
        cur.execute(
          "CREATE INDEX IF NOT EXISTS kb_chunks_doc_id_idx ON kb_chunks (doc_id)"
        )
      conn.commit()
    logger.info("PgVector schema ready (dimension=%d)", self._dimension)

  def add_documents(self, chunks: list[Document]) -> None:
    if not chunks:
      return
    texts = [chunk.page_content for chunk in chunks]
    vectors = self.embeddings.embed_documents(texts)
    with get_pg_connection() as conn:
      with conn.cursor() as cur:
        for chunk, vector in zip(chunks, vectors):
          chunk_id = str(chunk.metadata.get("chunk_id", ""))
          if not chunk_id:
            raise ValueError("chunk_id is required for pgvector ingest")
          cur.execute(
            """
            INSERT INTO kb_chunks (id, doc_id, filename, content, embedding, metadata)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (id) DO UPDATE SET
              doc_id = EXCLUDED.doc_id,
              filename = EXCLUDED.filename,
              content = EXCLUDED.content,
              embedding = EXCLUDED.embedding,
              metadata = EXCLUDED.metadata
            """,
            (
              chunk_id,
              str(chunk.metadata.get("doc_id", "")),
              str(chunk.metadata.get("filename", "unknown")),
              chunk.page_content,
              vector,
              json.dumps(chunk.metadata, ensure_ascii=False),
            ),
          )
      conn.commit()

  def similarity_search_with_score(self, query: str, k: int) -> list[tuple[Document, float]]:
    query_vector = self.embeddings.embed_query(query)
    rows = self._search_rows(query_vector, k, include_embedding=False)
    return [(self._row_to_document(row), float(row["distance"])) for row in rows]

  def max_marginal_relevance_search(
    self,
    query: str,
    k: int,
    fetch_k: int,
    lambda_mult: float,
  ) -> list[Document]:
    query_vector = self.embeddings.embed_query(query)
    rows = self._search_rows(query_vector, fetch_k, include_embedding=True)
    if not rows:
      return []
    embeddings = [row["embedding"] for row in rows]
    indices = maximal_marginal_relevance(
      query_vector,
      embeddings,
      lambda_mult=lambda_mult,
      k=min(k, len(rows)),
    )
    return [self._row_to_document(rows[i]) for i in indices]

  def delete_by_doc_id(self, doc_id: str) -> None:
    with get_pg_connection() as conn:
      with conn.cursor() as cur:
        cur.execute("DELETE FROM kb_chunks WHERE doc_id = %s", (doc_id,))
      conn.commit()

  def count(self) -> int:
    with get_pg_connection() as conn:
      with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM kb_chunks")
        row = cur.fetchone()
    return int(row[0]) if row else 0

  def _search_rows(
    self,
    query_vector: list[float],
    limit: int,
    *,
    include_embedding: bool,
  ) -> list[dict[str, Any]]:
    embedding_col = ", embedding" if include_embedding else ""
    sql = f"""
      SELECT id, doc_id, filename, content, metadata,
             (embedding <=> %s::vector) AS distance
             {embedding_col}
      FROM kb_chunks
      ORDER BY embedding <=> %s::vector
      LIMIT %s
    """
    with get_pg_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, (query_vector, query_vector, limit))
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]

  @staticmethod
  def _row_to_document(row: dict[str, Any]) -> Document:
    metadata = row.get("metadata") or {}
    if isinstance(metadata, str):
      metadata = json.loads(metadata)
    metadata = dict(metadata)
    metadata.setdefault("chunk_id", row["id"])
    metadata.setdefault("doc_id", row["doc_id"])
    metadata.setdefault("filename", row["filename"])
    return Document(page_content=row["content"], metadata=metadata)
