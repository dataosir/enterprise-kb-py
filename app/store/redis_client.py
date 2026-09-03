from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.config import REDIS_URL

if TYPE_CHECKING:
    import redis

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None
_available: bool | None = None


def get_redis() -> redis.Redis | None:
    """返回 Redis 客户端；未配置或不可用时返回 None。"""
    global _client, _available
    if not REDIS_URL:
        return None
    if _available is False:
        return None
    if _client is None:
        import redis as redis_lib

        try:
            _client = redis_lib.from_url(REDIS_URL, decode_responses=True)
            _client.ping()
            _available = True
            logger.info("Redis connected")
        except Exception:
            logger.warning("Redis unavailable, falling back to in-memory mode", exc_info=True)
            _client = None
            _available = False
    return _client


def redis_status() -> str:
    """connected | unavailable | not_configured"""
    if not REDIS_URL:
        return "not_configured"
    client = get_redis()
    if client is None:
        return "unavailable"
    try:
        client.ping()
        return "connected"
    except Exception:
        return "unavailable"


def reset_redis_client() -> None:
    """测试或重连时重置客户端缓存。"""
    global _client, _available
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
    _client = None
    _available = None
