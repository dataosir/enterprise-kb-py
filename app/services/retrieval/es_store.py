from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

INDEX_BODY: dict[str, Any] = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "doc_id": {"type": "keyword"},
            "chunk_id": {"type": "keyword"},
            "filename": {"type": "keyword"},
            "content": {
                "type": "text",
                "analyzer": "ik_max_word",
                "search_analyzer": "ik_smart",
            },
            "created_at": {"type": "date"},
        }
    },
}


@dataclass
class Bm25Hit:
    chunk_id: str
    doc_id: str
    filename: str
    content: str
    score: float

    def to_document(self) -> Document:
        return Document(
            page_content=self.content,
            metadata={
                "chunk_id": self.chunk_id,
                "doc_id": self.doc_id,
                "filename": self.filename,
            },
        )


class ElasticsearchStore:
    """Elasticsearch BM25 全文索引，与 Chroma 向量库通过 chunk_id 关联。"""

    def __init__(self, url: str, index_prefix: str) -> None:
        self.url = url.strip()
        self.index_name = f"{index_prefix}_chunks"
        self._client: Any | None = None
        self._available: bool | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    @property
    def available(self) -> bool:
        if not self.enabled:
            return False
        if self._available is not None:
            return self._available
        self._available = self._ping()
        return self._available

    def status(self) -> str:
        if not self.enabled:
            return "disabled"
        return "connected" if self.available else "unavailable"

    def ensure_index(self) -> None:
        client = self._get_client()
        if client.indices.exists(index=self.index_name):
            return
        client.indices.create(index=self.index_name, body=INDEX_BODY)
        logger.info("Created Elasticsearch index: %s", self.index_name)

    def index_chunks(self, chunks: list[Document]) -> int:
        if not chunks or not self.available:
            return 0

        client = self._get_client()
        self.ensure_index()
        now = datetime.now(timezone.utc).isoformat()
        operations: list[dict[str, Any]] = []

        for chunk in chunks:
            chunk_id = str(chunk.metadata.get("chunk_id", ""))
            if not chunk_id:
                continue
            operations.append({"index": {"_index": self.index_name, "_id": chunk_id}})
            operations.append(
                {
                    "doc_id": str(chunk.metadata.get("doc_id", "")),
                    "chunk_id": chunk_id,
                    "filename": str(chunk.metadata.get("filename", "unknown")),
                    "content": chunk.page_content,
                    "created_at": now,
                }
            )

        if not operations:
            return 0

        client.bulk(operations=operations, refresh=True)
        return len(operations) // 2

    def delete_by_doc_id(self, doc_id: str) -> int:
        if not self.available:
            return 0

        client = self._get_client()
        if not client.indices.exists(index=self.index_name):
            return 0

        result = client.delete_by_query(
            index=self.index_name,
            body={"query": {"term": {"doc_id": doc_id}}},
            refresh=True,
        )
        return int(result.get("deleted", 0))

    def clear_index(self) -> None:
        if not self.available:
            return

        client = self._get_client()
        if client.indices.exists(index=self.index_name):
            client.indices.delete(index=self.index_name)
        self.ensure_index()

    def search(self, query: str, size: int) -> list[Bm25Hit]:
        if not self.available:
            return []

        client = self._get_client()
        if not client.indices.exists(index=self.index_name):
            return []

        response = client.search(
            index=self.index_name,
            body={
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["content"],
                    }
                },
                "size": size,
            },
        )

        hits: list[Bm25Hit] = []
        for hit in response.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            hits.append(
                Bm25Hit(
                    chunk_id=str(source.get("chunk_id", hit.get("_id", ""))),
                    doc_id=str(source.get("doc_id", "")),
                    filename=str(source.get("filename", "unknown")),
                    content=str(source.get("content", "")),
                    score=float(hit.get("_score", 0.0)),
                )
            )
        return hits

    def count(self) -> int:
        if not self.available:
            return 0

        client = self._get_client()
        if not client.indices.exists(index=self.index_name):
            return 0

        result = client.count(index=self.index_name)
        return int(result.get("count", 0))

    def _get_client(self) -> Any:
        if self._client is None:
            from elasticsearch import Elasticsearch

            self._client = Elasticsearch(self.url, request_timeout=10)
        return self._client

    def _ping(self) -> bool:
        try:
            client = self._get_client()
            return bool(client.ping())
        except Exception:
            logger.warning("Elasticsearch unavailable at %s", self.url, exc_info=True)
            self._available = False
            return False


_es_store: ElasticsearchStore | None = None


def get_es_store() -> ElasticsearchStore:
    global _es_store
    if _es_store is None:
        from app.config import ES_INDEX_PREFIX, ES_URL

        _es_store = ElasticsearchStore(ES_URL, ES_INDEX_PREFIX)
    return _es_store
