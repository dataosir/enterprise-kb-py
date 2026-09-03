from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config import JOB_TTL_SECONDS
from app.store.redis_client import get_redis

logger = logging.getLogger(__name__)


class JobStore:
    """基于 Redis 的异步入库任务状态存储。"""

    def __init__(self, ttl_seconds: int = JOB_TTL_SECONDS) -> None:
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _key(job_id: str) -> str:
        return f"job:{job_id}"

    def create(self, doc_id: str, filename: str) -> str:
        client = get_redis()
        if client is None:
            raise RuntimeError("Redis unavailable")
        job_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "job_id": job_id,
            "doc_id": doc_id,
            "filename": filename,
            "status": "PENDING",
            "chunk_count": 0,
            "message": "任务已创建，等待处理",
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
        client.setex(self._key(job_id), self.ttl_seconds, json.dumps(payload, ensure_ascii=False))
        return job_id

    def get(self, job_id: str) -> dict[str, Any] | None:
        client = get_redis()
        if client is None:
            return None
        raw = client.get(self._key(job_id))
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Invalid job payload: %s", job_id)
            return None

    def update(self, job_id: str, **fields: Any) -> dict[str, Any] | None:
        client = get_redis()
        if client is None:
            return None
        current = self.get(job_id)
        if current is None:
            return None
        current.update(fields)
        current["updated_at"] = datetime.now(timezone.utc).isoformat()
        client.setex(self._key(job_id), self.ttl_seconds, json.dumps(current, ensure_ascii=False))
        return current

    def to_api_dict(self, job: dict[str, Any]) -> dict[str, Any]:
        return {
            "jobId": job["job_id"],
            "docId": job.get("doc_id"),
            "filename": job.get("filename"),
            "status": job.get("status"),
            "chunkCount": job.get("chunk_count", 0),
            "message": job.get("message"),
            "error": job.get("error"),
            "createdAt": job.get("created_at"),
            "updatedAt": job.get("updated_at"),
        }


_store: JobStore | None = None


def get_job_store() -> JobStore:
    global _store
    if _store is None:
        _store = JobStore()
    return _store
