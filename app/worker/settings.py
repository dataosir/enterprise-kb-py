from __future__ import annotations

import logging

from arq.connections import RedisSettings

from app.config import REDIS_URL

logger = logging.getLogger(__name__)


async def ingest_document_task(_ctx: dict, doc_id: str, job_id: str) -> dict:
    """异步入库任务：加载文档 → 切分 → 向量化 → 写入 Chroma + ES。"""
    from app.services.rag_engine import get_rag_engine
    from app.store.job_store import get_job_store

    job_store = get_job_store()
    job_store.update(job_id, status="PROCESSING", message="正在解析与向量化文档")

    try:
        engine = get_rag_engine()
        chunk_count = engine.process_document_ingest(doc_id)
        job_store.update(
            job_id,
            status="COMPLETED",
            chunk_count=chunk_count,
            message=f"文档已成功入库，共切分 {chunk_count} 个片段",
            error=None,
        )
        logger.info("Ingest job %s completed: %d chunks", job_id, chunk_count)
        return {"doc_id": doc_id, "chunk_count": chunk_count}
    except Exception as exc:
        logger.exception("Ingest job %s failed", job_id)
        job_store.update(
            job_id,
            status="FAILED",
            message="文档入库失败",
            error=str(exc),
        )
        raise


class WorkerSettings:
    """ARQ Worker 配置。低内存设备建议 max_jobs=1。"""

    functions = [ingest_document_task]
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    max_jobs = 1
    job_timeout = 600
    keep_result = 3600
