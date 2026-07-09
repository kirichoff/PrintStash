"""S3StorageBackend exercised against a real object store (MinIO).

Skipped unless PRINTSTASH_TEST_S3_ENDPOINT is set, so ``uv run pytest tests``
stays dependency-free for contributors. Start a throwaway MinIO with:

    docker compose -f docker-compose.test.yml up -d
    PRINTSTASH_TEST_S3_ENDPOINT=http://localhost:9100 \
        uv run pytest tests/test_storage_s3.py -v
    docker compose -f docker-compose.test.yml down -v

``tests/test_storage_seam.py`` covers ``exists()``'s auth-error handling with
a hand-built client stub; this file covers the read/write round trip that
only a real (or real-compatible) S3 endpoint can validate.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Iterator

import pytest

from app.core.config import _overlay
from app.services.storage_backend import S3StorageBackend

_ENDPOINT = os.environ.get("PRINTSTASH_TEST_S3_ENDPOINT")

pytestmark = pytest.mark.skipif(
    not _ENDPOINT, reason="set PRINTSTASH_TEST_S3_ENDPOINT to run S3 integration tests"
)


@pytest.fixture
def s3_backend() -> Iterator[S3StorageBackend]:
    bucket = f"printstash-test-{uuid.uuid4().hex[:12]}"
    _overlay.update(
        {
            "s3_bucket": bucket,
            "s3_endpoint_url": _ENDPOINT,
            "s3_region": "us-east-1",
            "s3_access_key": os.environ.get("PRINTSTASH_TEST_S3_ACCESS_KEY", "minioadmin"),
            "s3_secret_key": os.environ.get("PRINTSTASH_TEST_S3_SECRET_KEY", "minioadmin"),
        }
    )
    backend = S3StorageBackend()  # creates the bucket (_ensure_bucket)
    try:
        yield backend
    finally:
        for key in backend.list_keys():
            backend.delete(key)
        for field in (
            "s3_bucket",
            "s3_endpoint_url",
            "s3_region",
            "s3_access_key",
            "s3_secret_key",
        ):
            _overlay.pop(field, None)


def test_round_trips_bytes(s3_backend: S3StorageBackend):
    key = "models/round-trip.txt"
    assert not s3_backend.exists(key)

    s3_backend.write_bytes(b"hello minio", key)

    assert s3_backend.exists(key)
    assert s3_backend.stat_size(key) == len(b"hello minio")
    assert s3_backend.read_bytes(key) == b"hello minio"


def test_upload_file_then_download_to_path(s3_backend: S3StorageBackend, tmp_path: Path):
    src = tmp_path / "source.bin"
    src.write_bytes(b"payload bytes")
    key = "models/uploaded.bin"

    s3_backend.upload_file(src, key)
    assert s3_backend.exists(key)

    dest = tmp_path / "downloaded.bin"
    s3_backend.download_to_path(key, dest)
    assert dest.read_bytes() == b"payload bytes"


def test_move_in_uploads_and_removes_staged_file(
    s3_backend: S3StorageBackend, tmp_path: Path
):
    staged = tmp_path / "staged.bin"
    staged.write_bytes(b"staged content")
    key = "models/moved.bin"

    s3_backend.move_in(staged, key)

    assert s3_backend.exists(key)
    assert s3_backend.read_bytes(key) == b"staged content"
    assert not staged.exists()


def test_delete_removes_object(s3_backend: S3StorageBackend):
    key = "models/to-delete.txt"
    s3_backend.write_bytes(b"gone soon", key)
    assert s3_backend.exists(key)

    s3_backend.delete(key)

    assert not s3_backend.exists(key)


def test_exists_false_on_missing_key(s3_backend: S3StorageBackend):
    assert not s3_backend.exists("models/never-written.txt")
