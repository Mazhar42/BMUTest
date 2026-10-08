"""Object storage (ROADMAP §6.1, §9): private buckets on an S3-compatible store (MinIO/RustFS) in dev/prod,
or a local directory in tests. Objects are never public; the API streams them after a permission check
(or hands out a 5-minute presigned URL)."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from app.config import get_settings
from app.core.errors import NotFound

Bucket = Literal["prescriptions", "reports", "attachments"]
_SAFE_KEY = re.compile(r"^[A-Za-z0-9/_\-.]+$")


def _check_key(key: str) -> None:
    if not _SAFE_KEY.match(key) or ".." in key or key.startswith("/"):
        raise ValueError(f"unsafe object key {key!r}")


@lru_cache
def _s3() -> Any:
    import boto3
    from botocore.config import Config

    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name=s.s3_region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


_ensured: set[str] = set()


def _ensure_bucket(bucket: str) -> None:
    if bucket in _ensured:
        return
    client = _s3()
    try:
        client.head_bucket(Bucket=bucket)
    except Exception:  # any "missing" flavour from S3-compatible stores
        client.create_bucket(Bucket=bucket)
    _ensured.add(bucket)


def put(bucket: Bucket, key: str, data: bytes, content_type: str) -> None:
    _check_key(key)
    s = get_settings()
    if s.storage_backend == "local":
        path = Path(s.storage_local_dir) / bucket / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return
    _ensure_bucket(bucket)
    _s3().put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)


def get(bucket: Bucket, key: str) -> bytes:
    _check_key(key)
    s = get_settings()
    if s.storage_backend == "local":
        path = Path(s.storage_local_dir) / bucket / key
        if not path.exists():
            raise NotFound("object")
        return path.read_bytes()
    try:
        obj = _s3().get_object(Bucket=bucket, Key=key)
    except Exception as exc:
        raise NotFound("object") from exc
    data: bytes = obj["Body"].read()
    return data


def presign(bucket: Bucket, key: str) -> str | None:
    """A short-lived download URL (S3 only); None for local storage (stream through the API instead)."""
    _check_key(key)
    s = get_settings()
    if s.storage_backend == "local":
        return None
    url: str = _s3().generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=s.presign_seconds
    )
    if s.s3_public_endpoint and s.s3_public_endpoint != s.s3_endpoint:
        url = url.replace(s.s3_endpoint, s.s3_public_endpoint, 1)
    return url
