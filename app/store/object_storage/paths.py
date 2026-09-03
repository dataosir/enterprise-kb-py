from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from app.store.object_storage.factory import get_object_storage


@contextmanager
def open_document_path(storage_ref: str):
  """解析文档存储引用；S3 下载的临时文件会在退出时删除。"""
  storage = get_object_storage()
  path = storage.resolve_local_path(storage_ref)
  is_temp = storage_ref.startswith("s3://")
  try:
    yield path
  finally:
    if is_temp and path.exists():
      path.unlink(missing_ok=True)
