from __future__ import annotations

import logging

from app.config import (
  S3_ACCESS_KEY,
  S3_BUCKET,
  S3_ENDPOINT,
  S3_SECRET_KEY,
  STORAGE_BACKEND,
)
from app.store.object_storage.base import ObjectStorage
from app.store.object_storage.local_storage import LocalObjectStorage
from app.store.object_storage.s3_storage import S3ObjectStorage

logger = logging.getLogger(__name__)


class FallbackObjectStorage:
  def __init__(self, inner: LocalObjectStorage, reason: str) -> None:
    self._inner = inner
    self._reason = reason

  @property
  def backend(self) -> str:
    return "local"

  def status(self) -> str:
    return "fallback"

  @property
  def fallback_reason(self) -> str:
    return self._reason

  def put_upload(self, doc_id: str, filename: str, content: bytes) -> str:
    return self._inner.put_upload(doc_id, filename, content)

  def resolve_local_path(self, storage_ref: str):
    return self._inner.resolve_local_path(storage_ref)

  def delete(self, storage_ref: str) -> None:
    self._inner.delete(storage_ref)

  def is_managed_upload(self, storage_ref: str) -> bool:
    return self._inner.is_managed_upload(storage_ref)


_storage: ObjectStorage | None = None


def get_object_storage() -> ObjectStorage:
  global _storage
  if _storage is None:
    _storage = create_object_storage()
  return _storage


def create_object_storage() -> ObjectStorage:
  local = LocalObjectStorage()

  if STORAGE_BACKEND != "s3":
    return local

  if not (S3_ENDPOINT and S3_ACCESS_KEY and S3_SECRET_KEY):
    logger.warning("STORAGE_BACKEND=s3 但 S3 凭据不完整，已回退本地存储")
    return FallbackObjectStorage(local, "S3 credentials incomplete")

  try:
    store = S3ObjectStorage(
      endpoint=S3_ENDPOINT,
      access_key=S3_ACCESS_KEY,
      secret_key=S3_SECRET_KEY,
      bucket=S3_BUCKET,
    )
    logger.info("Using S3 object storage (bucket=%s)", S3_BUCKET)
    return store
  except Exception as exc:
    logger.warning("S3 初始化失败，已回退本地存储: %s", exc)
    return FallbackObjectStorage(local, str(exc))


def s3_status() -> str:
  """not_configured | connected | unavailable | fallback"""
  if STORAGE_BACKEND != "s3":
    return "not_configured"
  storage = get_object_storage()
  if storage.backend == "s3":
    return storage.status()
  if storage.status == "fallback":
    return "fallback"
  return "unavailable"
