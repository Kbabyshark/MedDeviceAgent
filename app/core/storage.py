"""MinIO 对象存储 — 文档/附件/音频。"""
from minio import Minio
from minio.error import S3Error
from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)
_client = None


def get_minio() -> Minio:
    global _client
    if _client is not None:
        return _client
    s = get_settings().minio
    _client = Minio(s.endpoint, access_key=s.access_key, secret_key=s.secret_key, secure=s.secure)
    # 确保 bucket 存在
    if not _client.bucket_exists(s.bucket):
        _client.make_bucket(s.bucket)
        logger.info("minio_bucket_created", bucket=s.bucket)
    return _client


def upload_file(object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    import io
    s = get_settings().minio
    client = get_minio()
    client.put_object(s.bucket, object_name, io.BytesIO(data), len(data), content_type=content_type)
    return object_name


def get_file_url(object_name: str) -> str:
    s = get_settings().minio
    client = get_minio()
    return client.presigned_get_object(s.bucket, object_name, expires=3600)