from __future__ import annotations

from pathlib import Path

from app.config import UPLOAD_DIR


class LocalObjectStorage:
  def __init__(self) -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

  @property
  def backend(self) -> str:
    return "local"

  def status(self) -> str:
    return "connected"

  def put_upload(self, doc_id: str, filename: str, content: bytes) -> str:
    saved_path = UPLOAD_DIR / f"{doc_id}_{filename}"
    saved_path.write_bytes(content)
    return str(saved_path)

  def resolve_local_path(self, storage_ref: str) -> Path:
    return Path(storage_ref)

  def delete(self, storage_ref: str) -> None:
    path = Path(storage_ref)
    if path.exists() and path.parent == UPLOAD_DIR:
      path.unlink(missing_ok=True)

  def is_managed_upload(self, storage_ref: str) -> bool:
    path = Path(storage_ref)
    return path.parent == UPLOAD_DIR
