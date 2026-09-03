from __future__ import annotations

import logging

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import REDIS_URL

logger = logging.getLogger(__name__)

_pool: ArqRedis | None = None


async def get_arq_pool() -> ArqRedis | None:
    """获取 ARQ 连接池；Redis 未配置时返回 None。"""
    global _pool
    if not REDIS_URL:
        return None
    if _pool is None:
        try:
            _pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
            logger.info("ARQ pool created")
        except Exception:
            logger.warning("Failed to create ARQ pool", exc_info=True)
            return None
    return _pool


async def close_arq_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def enqueue_ingest_job(doc_id: str, job_id: str) -> bool:
    pool = await get_arq_pool()
    if pool is None:
        return False
    await pool.enqueue_job("ingest_document_task", doc_id, job_id)
    return True
