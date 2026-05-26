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
# NOTE: The _nexus3d_rust rasterise function has a known triangle-coverage
# bug that causes severe rasterisation corruption (only a tiny fraction of
# each triangle's area is filled). Until the Rust crate is fixed and
# re-released, we unconditionally return None here so mesh_render falls
# back to the correct pure-numpy rasteriser.
#
# Original import kept below (commented) so CI/linters don't lose track of
# the symbol; remove the comment once the Rust bug is resolved.
#
# try:
#     from _nexus3d_rust import rasterise as _rasterise
# except ImportError:
#     logger.debug("raster_rust: _nexus3d_rust not found; using pure-Python fallback")


def rasterise(
    tri: "numpy.ndarray",
    shade: "numpy.ndarray",
    width: int,
    height: int,
) -> Optional[bytes]:
    """Render triangles to RGB bytes.

    Returns None — the Rust rasteriser is disabled due to a triangle-coverage
    bug. ``mesh_render`` will use the pure-numpy fallback instead.
    """
    return None
