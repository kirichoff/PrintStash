"""Streaming sha256 helpers."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO

_CHUNK = 1024 * 1024  # 1 MiB


def sha256_file(path: Path) -> str:
    """Compute the sha256 hex digest of a file by streaming it."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_stream(fh: BinaryIO) -> str:
    """Compute sha256 from a binary stream (consumes it)."""
    h = hashlib.sha256()
    for chunk in iter(lambda: fh.read(_CHUNK), b""):
        h.update(chunk)
    return h.hexdigest()
