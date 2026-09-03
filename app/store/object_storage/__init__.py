"""对象存储 — 本地目录（Demo）/ MinIO S3（生产）。"""

from app.store.object_storage.factory import get_object_storage, s3_status

__all__ = ["get_object_storage", "s3_status"]
