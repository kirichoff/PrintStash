"""Bounds on mesh processing that keep one pathological NAS file from taking
down the whole process during a library scan (issue #24).

A multi-hundred-MB / tens-of-millions-of-triangles mesh, loaded and rasterised
synchronously inside the scan thread, can peg a core and balloon RSS long enough
to trip a container liveness watchdog. ``analyze_mesh`` must skip the heavy work
above the configured caps while still indexing the file.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from app.core.config import _overlay
from app.services import mesh_processing


def _fake_mesh(num_faces: int):
    """A trimesh-like stand-in with just the attributes the geometry/cap code reads."""
    return SimpleNamespace(
        vertices=np.zeros((3, 3), dtype=np.float64),
        bounds=np.array([[0.0, 0.0, 0.0], [10.0, 20.0, 30.0]]),
        faces=np.zeros((num_faces, 3), dtype=np.int64),
        volume=42.0,
    )


def test_oversized_file_skips_mesh_load_and_render(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setitem(_overlay, "mesh_max_mb", 0)  # any non-empty file is "too large"
    path = tmp_path / "huge.stl"
    path.write_bytes(b"solid\n" * 100)

    def _boom(_path):  # pragma: no cover - must never run
        raise AssertionError("oversized file must not be loaded into trimesh")

    monkeypatch.setattr(mesh_processing, "_load_mesh", _boom)
    monkeypatch.setattr(
        mesh_processing.mesh_render,
        "render_mesh_thumbnail",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not render")),
    )

    geometry, thumb = mesh_processing.analyze_mesh(path)

    # File is still "indexed" — we just have no geometry/thumbnail for it.
    assert geometry["triangle_count"] is None
    assert geometry["bbox_x_mm"] is None
    assert thumb is None  # no embedded 3MF preview in a raw .stl


def test_too_many_triangles_keeps_geometry_but_skips_render(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setitem(_overlay, "mesh_max_render_triangles", 2)
    path = tmp_path / "dense.stl"
    path.write_bytes(b"solid\n")

    monkeypatch.setattr(mesh_processing, "_load_mesh", lambda _p: _fake_mesh(num_faces=5))
    monkeypatch.setattr(
        mesh_processing.mesh_render,
        "render_mesh_thumbnail",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not render")),
    )

    geometry, thumb = mesh_processing.analyze_mesh(path)

    # Geometry is cheap and still extracted; only the rasteriser is skipped.
    assert geometry["triangle_count"] == 5
    assert geometry["bbox_x_mm"] == 10.0
    assert thumb is None


def test_within_caps_renders_normally(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "ok.stl"
    path.write_bytes(b"solid\n")

    monkeypatch.setattr(mesh_processing, "_load_mesh", lambda _p: _fake_mesh(num_faces=12))
    monkeypatch.setattr(
        mesh_processing.mesh_render,
        "render_mesh_thumbnail",
        lambda *a, **k: b"PNGDATA",
    )

    geometry, thumb = mesh_processing.analyze_mesh(path)

    assert geometry["triangle_count"] == 12
    assert thumb == b"PNGDATA"
