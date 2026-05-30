"""Disabled Rust triangle rasteriser wrapper.

``mesh_render`` falls back to the pure-numpy rasteriser while the native
implementation has a known triangle-coverage bug.
"""

from __future__ import annotations

from typing import Optional

_rasterise = None


def rasterise(
    tri: "numpy.ndarray",  # noqa: F821 — forward-reference for numpy
    shade: "numpy.ndarray",  # noqa: F821
    width: int,
    height: int,
) -> Optional[bytes]:
    """Return None until the native rasteriser is corrected."""
    return None
