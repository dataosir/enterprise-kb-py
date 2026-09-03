from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from app.config import CONVERSATION_TTL_SECONDS, CONVERSATION_STORE
from app.store.redis_client import get_redis, redis_status

logger = logging.getLogger(__name__)

DEFAULT_TENANT = "default"


class ConversationStore(ABC):
    @abstractmethod
    def get_turns(self, conversation_id: str, tenant: str = DEFAULT_TENANT) -> list[tuple[str, str]]:
        ...

    @abstractmethod
    def append_turn(
        self,
        conversation_id: str,
        question: str,
        answer: str,
        tenant: str = DEFAULT_TENANT,
    ) -> None:
        ...

    @abstractmethod
    def clear(self, conversation_id: str, tenant: str = DEFAULT_TENANT) -> bool:
        ...

    def get_messages(self, conversation_id: str, tenant: str = DEFAULT_TENANT) -> list[dict]:
        messages: list[dict] = []
        for question, answer in self.get_turns(conversation_id, tenant):
            messages.append({"role": "user", "content": question})
            messages.append({"role": "assistant", "content": answer})
        return messages


class MemoryConversationStore(ConversationStore):
    def __init__(self) -> None:
        self._memory: dict[str, list[tuple[str, str]]] = {}

    def get_turns(self, conversation_id: str, tenant: str = DEFAULT_TENANT) -> list[tuple[str, str]]:
        key = f"{tenant}:{conversation_id}"
        return list(self._memory.get(key, []))

    def append_turn(
        self,
        conversation_id: str,
        question: str,
        answer: str,
        tenant: str = DEFAULT_TENANT,
    ) -> None:
        key = f"{tenant}:{conversation_id}"
        self._memory.setdefault(key, []).append((question, answer))

    def clear(self, conversation_id: str, tenant: str = DEFAULT_TENANT) -> bool:
        key = f"{tenant}:{conversation_id}"
        if key in self._memory:
            del self._memory[key]
            return True
        return False


class RedisConversationStore(ConversationStore):
    def __init__(self, ttl_seconds: int = CONVERSATION_TTL_SECONDS) -> None:
        self.ttl_seconds = ttl_seconds

    def _turns_key(self, tenant: str, conversation_id: str) -> str:
        return f"conv:{tenant}:{conversation_id}"

    def _meta_key(self, conversation_id: str) -> str:
        return f"conv:meta:{conversation_id}"

    def get_turns(self, conversation_id: str, tenant: str = DEFAULT_TENANT) -> list[tuple[str, str]]:
        client = get_redis()
        if client is None:
            return []
        raw_items = client.lrange(self._turns_key(tenant, conversation_id), 0, -1)
        turns: list[tuple[str, str]] = []
        for item in raw_items:
            try:
                data = json.loads(item)
                turns.append((data["question"], data["answer"]))
            except (json.JSONDecodeError, KeyError):
                logger.warning("Skip invalid conversation turn: %s", item)
        return turns

    def append_turn(
        self,
        conversation_id: str,
        question: str,
        answer: str,
        tenant: str = DEFAULT_TENANT,
    ) -> None:
        client = get_redis()
        if client is None:
            raise RuntimeError("Redis unavailable")
        payload = json.dumps({"question": question, "answer": answer}, ensure_ascii=False)
        turns_key = self._turns_key(tenant, conversation_id)
        meta_key = self._meta_key(conversation_id)
        now = datetime.now(timezone.utc).isoformat()
        pipe = client.pipeline()
        pipe.rpush(turns_key, payload)
        pipe.expire(turns_key, self.ttl_seconds)
        pipe.hset(
            meta_key,
            mapping={
                "tenant": tenant,
                "updated_at": now,
                "created_at": client.hget(meta_key, "created_at") or now,
            },
        )
        pipe.expire(meta_key, self.ttl_seconds)
        pipe.execute()

    def clear(self, conversation_id: str, tenant: str = DEFAULT_TENANT) -> bool:
        client = get_redis()
        if client is None:
            return False
        deleted = client.delete(
            self._turns_key(tenant, conversation_id),
            self._meta_key(conversation_id),
        )
        return deleted > 0


_store: ConversationStore | None = None


def get_conversation_store() -> ConversationStore:
    global _store
    if _store is None:
        mode = CONVERSATION_STORE
        use_redis = mode == "redis" or (mode == "auto" and redis_status() == "connected")
        if use_redis and redis_status() == "connected":
            _store = RedisConversationStore()
            logger.info("Using Redis conversation store")
        else:
            if mode == "redis" and redis_status() != "connected":
                logger.warning("CONVERSATION_STORE=redis but Redis unavailable, using memory")
            _store = MemoryConversationStore()
            logger.info("Using in-memory conversation store")
    return _store


def conversation_store_type() -> str:
    store = get_conversation_store()
    return "redis" if isinstance(store, RedisConversationStore) else "memory"
