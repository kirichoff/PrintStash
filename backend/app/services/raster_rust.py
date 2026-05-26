"""Rust-accelerated triangle rasteriser wrapper.

Attempts to load ``_nexus3d_rust.rasterise`` on import.
If unavailable, callers should fall back to the pure-numpy
rasteriser in ``mesh_render``.
"""

from __future__ import annotations

from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

_rasterise = None
try:
    from _nexus3d_rust import rasterise as _rasterise
except ImportError:
    logger.debug("raster_rust: _nexus3d_rust not found; using pure-Python fallback")


def rasterise(
    tri: "numpy.ndarray",
    shade: "numpy.ndarray",
    width: int,
    height: int,
) -> Optional[bytes]:
    """Render triangles to RGB bytes. Returns None if Rust rasteriser unavailable."""
    if _rasterise is None:
        return None
    try:
        import numpy as np

        # PyO3 accepts lists of f64 — convert numpy arrays.
        tri_list: list[float] = np.asarray(tri, dtype=np.float64).ravel().tolist()
        shade_list: list[float] = np.asarray(shade, dtype=np.float64).ravel().tolist()
        buf: bytes = _rasterise(tri_list, shade_list, width, height)
        return buf
    except Exception:
        logger.exception("raster_rust: rasterise failed")
        return None
