from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ObjectStorage(Protocol):
  @property
  def backend(self) -> str:
    """local | s3"""
    ...

  def status(self) -> str:
    """connected | unavailable | fallback"""
    ...

  def put_upload(self, doc_id: str, filename: str, content: bytes) -> str:
    """保存上传文件，返回存储引用（本地路径或 s3:// URI）。"""
    ...

  def resolve_local_path(self, storage_ref: str) -> Path:
    """获取可供 Loader 读取的本地路径（S3 会下载到临时文件）。"""
    ...

  def delete(self, storage_ref: str) -> None:
    """删除托管的上传文件。"""
    ...

  def is_managed_upload(self, storage_ref: str) -> bool:
    """是否为应用托管的上传文件（可安全删除）。"""
    ...
