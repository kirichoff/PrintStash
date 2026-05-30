"""Filesystem layout helpers for the vault.

Pure helpers only — no delegation to the StorageBackend. Callers that need
read/write/move/delete use ``get_backend()`` directly from
``app.services.storage_backend``.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import BinaryIO

from app.services.storage_backend import LocalStorageBackend, get_backend

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Produce a filesystem-safe, kebab-case slug."""
    normalized = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    )
    slug = _SLUG_RE.sub("-", normalized.lower()).strip("-")
    return slug or "model"


def ensure_unique_slug(base: str, exists: callable) -> str:
    """Append -2, -3, ... until exists(slug) returns False."""
    candidate = base
    n = 2
    while exists(candidate):
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def stream_to_path(src: BinaryIO, dest: Path) -> int:
    """Stream a binary source to a local path, returning bytes written."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    bytes_written = 0
    with dest.open("wb") as out:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            bytes_written += len(chunk)
    return bytes_written


def canonical_blob_path(slug: str, version: int, filename: str) -> str:
    """Return the storage key for a blob at its canonical location."""
    return get_backend().blob_key(slug, version, filename)


def thumbnail_path_for(file_id: int) -> str:
    """Return the storage key for a thumbnail."""
    return get_backend().thumbnail_key(file_id)


def move_file(src: Path, dest_key: str) -> None:
    """Move a local staged file into the storage backend at *dest_key*."""
    backend = get_backend()
    if isinstance(backend, LocalStorageBackend):
        backend.move(str(src), dest_key)
    else:
        backend.upload_file(src, dest_key)
        try:
            src.unlink(missing_ok=True)
        except OSError:
            pass
