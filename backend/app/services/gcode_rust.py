"""Rust-accelerated G-code scanner wrapper.

On the first import, attempts to load ``_nexus3d_rust.gcode_scan``.
If the native extension is not available (not built / wrong platform),
falls back to pure-Python helpers transparently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_rust_scan = None
try:
    from _nexus3d_rust import gcode_scan as _rust_scan
except ImportError:
    logger.debug("gcode_rust: _nexus3d_rust not found; using pure-Python fallback")


def gcode_scan(path: Path) -> dict[str, Any] | None:
    """Combined sha256 + metadata + thumbnail scan. Returns None if not available."""
    if _rust_scan is None:
        return None
    try:
        result = _rust_scan(str(path))
        return dict(result)  # PyDict → plain dict
    except Exception:
        logger.exception("gcode_rust: scan failed for %s", path.name)
        return None
