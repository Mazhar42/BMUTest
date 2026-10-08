# 0003 — Object store: RustFS (S3-compatible) instead of the MinIO image

**Status:** accepted (M1)

## Context
The roadmap specifies MinIO for private buckets with presigned URLs. MinIO no longer publishes free
container images for new releases.

## Decision
Run **RustFS** (`rustfs/rustfs`), which speaks the S3 API, in the `minio` service slot. The code talks
plain S3 through boto3 (`app/core/storage.py`), so MinIO, RustFS or a managed S3 service are
interchangeable by changing `S3_ENDPOINT` and keys. Tests use the local-directory backend.

## Consequences
Pin `RUSTFS_TAG` in production once BMU confirms hosting. Buckets are created on first use and are never
public; the API streams objects after a permission check (or presigns for 5 minutes).
