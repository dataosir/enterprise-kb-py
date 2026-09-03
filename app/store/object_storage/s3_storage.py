from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from urllib.parse import unquote

logger = logging.getLogger(__name__)


class S3ObjectStorage:
  """MinIO / S3 兼容对象存储。"""

  def __init__(
    self,
    endpoint: str,
    access_key: str,
    secret_key: str,
    bucket: str,
  ) -> None:
    import boto3
    from botocore.config import Config

    self.bucket = bucket
    self._client = boto3.client(
      "s3",
      endpoint_url=endpoint,
      aws_access_key_id=access_key,
      aws_secret_access_key=secret_key,
      region_name="us-east-1",
      config=Config(signature_version="s3v4"),
    )
    self._ensure_bucket()

  @property
  def backend(self) -> str:
    return "s3"

  def status(self) -> str:
    return "connected"

  def put_upload(self, doc_id: str, filename: str, content: bytes) -> str:
    key = f"uploads/{doc_id}/{filename}"
    self._client.put_object(Bucket=self.bucket, Key=key, Body=content)
    return f"s3://{self.bucket}/{key}"

  def resolve_local_path(self, storage_ref: str) -> Path:
    if not storage_ref.startswith("s3://"):
      # 兼容 local → s3 切换后 metadata 中仍保留本地路径的历史文档
      local = Path(storage_ref)
      if local.is_file():
        logger.debug("Legacy local storage ref, using existing file: %s", storage_ref)
        return local
      raise ValueError(f"Invalid S3 reference: {storage_ref}")
    bucket, key = self._parse_ref(storage_ref)
    suffix = Path(key).suffix or ".bin"
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp.close()
    self._client.download_file(bucket, key, temp.name)
    return Path(temp.name)

  def delete(self, storage_ref: str) -> None:
    bucket, key = self._parse_ref(storage_ref)
    self._client.delete_object(Bucket=self.bucket, Key=key)

  def is_managed_upload(self, storage_ref: str) -> bool:
    return storage_ref.startswith("s3://")

  def _ensure_bucket(self) -> None:
    try:
      self._client.head_bucket(Bucket=self.bucket)
    except Exception:
      try:
        self._client.create_bucket(Bucket=self.bucket)
        logger.info("Created S3 bucket: %s", self.bucket)
      except Exception as exc:
        raise RuntimeError(f"Cannot access or create bucket {self.bucket}: {exc}") from exc

  @staticmethod
  def _parse_ref(storage_ref: str) -> tuple[str, str]:
    if not storage_ref.startswith("s3://"):
      raise ValueError(f"Invalid S3 reference: {storage_ref}")
    without_scheme = storage_ref[5:]
    bucket, key = without_scheme.split("/", 1)
    return bucket, unquote(key)
