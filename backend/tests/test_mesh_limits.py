"""Mesh-density cap that stops one dense lattice/gyroid file from OOM-killing the
process during a library scan (issue #24).

Loading + rasterising a mesh costs ~700 MB of peak RSS per million triangles,
and the cost is paid inside ``trimesh.load`` — so the only safe defence is to
estimate the triangle count *before* loading and skip the monster. The file is
still indexed; a 3MF still yields its embedded slicer preview.
"""

from __future__ import annotations

import struct
import zipfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from app.core.config import _overlay
from app.services import mesh_processing


def _write_binary_stl(path: Path, n_triangles: int) -> None:
    """A minimal but structurally valid binary STL with *n_triangles* facets."""
    with path.open("wb") as fh:
        fh.write(b"\x00" * 80)  # header
        fh.write(struct.pack("<I", n_triangles))
        fh.write(b"\x00" * (50 * n_triangles))  # 50 bytes per facet


def _fake_mesh(num_faces: int):
    return SimpleNamespace(
        vertices=np.zeros((3, 3), dtype=np.float64),
        bounds=np.array([[0.0, 0.0, 0.0], [10.0, 20.0, 30.0]]),
        faces=np.zeros((num_faces, 3), dtype=np.int64),
        volume=42.0,
    )


def test_binary_stl_triangle_count_is_exact(tmp_path: Path) -> None:
    p = tmp_path / "cube.stl"
    _write_binary_stl(p, 1234)
    assert mesh_processing._estimate_triangle_count(p) == 1234


def test_3mf_triangle_count_from_uncompressed_xml(tmp_path: Path) -> None:
    p = tmp_path / "dense.3mf"
    model_xml = b"<triangle/>" * 10_000  # 110_000 bytes of "mesh"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("3D/3dmodel.model", model_xml)
    # ~70 bytes per triangle proxy.
    assert mesh_processing._estimate_triangle_count(p) == len(model_xml) // 70


def test_over_cap_mesh_is_never_loaded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setitem(_overlay, "mesh_max_render_triangles", 1000)
    p = tmp_path / "huge.stl"
    _write_binary_stl(p, 50_000)  # well over the cap

    def _boom(_path):  # pragma: no cover - must never run
        raise AssertionError("over-cap mesh must not be loaded into trimesh")

    monkeypatch.setattr(mesh_processing, "_load_mesh", _boom)

    geometry, thumb = mesh_processing.analyze_mesh(p)

    # Indexed, but with no geometry/thumbnail — and crucially, no load attempt.
    assert geometry["triangle_count"] is None
    assert thumb is None


def test_over_cap_3mf_still_gets_embedded_preview(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setitem(_overlay, "mesh_max_render_triangles", 1000)
    png = mesh_processing._PNG_MAGIC + b"preview-bytes"
    p = tmp_path / "dense.3mf"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("3D/3dmodel.model", b"<triangle/>" * 100_000)  # ~157k tris, over cap
        zf.writestr("Metadata/thumbnail.png", png)

    monkeypatch.setattr(
        mesh_processing,
        "_load_mesh",
        lambda _p: (_ for _ in ()).throw(AssertionError("must not load")),
    )

    geometry, thumb = mesh_processing.analyze_mesh(p)

    assert geometry["triangle_count"] is None  # mesh skipped
    assert thumb == png  # but the cheap embedded preview is still used


def test_post_load_backstop_skips_render_when_estimate_missed(
    tmp_path: Path, monkeypatch
) -> None:
    # A format the estimator can't size up (returns None) but whose loaded mesh
    # is over budget: keep the cheap geometry, skip the expensive render.
    monkeypatch.setitem(_overlay, "mesh_max_render_triangles", 10)
    p = tmp_path / "model.obj"
    p.write_text("# obj")

    monkeypatch.setattr(mesh_processing, "_estimate_triangle_count", lambda _p: None)
    monkeypatch.setattr(mesh_processing, "_load_mesh", lambda _p: _fake_mesh(num_faces=99))
    monkeypatch.setattr(
        mesh_processing.mesh_render,
        "render_mesh_thumbnail",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not render")),
    )

    geometry, thumb = mesh_processing.analyze_mesh(p)

    assert geometry["triangle_count"] == 99  # cheap geometry kept
    assert thumb is None  # render skipped


def test_under_cap_mesh_renders_normally(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setitem(_overlay, "mesh_max_render_triangles", 1_000_000)
    p = tmp_path / "ok.stl"
    _write_binary_stl(p, 500)

    monkeypatch.setattr(mesh_processing, "_load_mesh", lambda _p: _fake_mesh(num_faces=500))
    monkeypatch.setattr(
        mesh_processing.mesh_render, "render_mesh_thumbnail", lambda *a, **k: b"PNGDATA"
    )

    geometry, thumb = mesh_processing.analyze_mesh(p)

    assert geometry["triangle_count"] == 500
    assert thumb == b"PNGDATA"


# ---------------------------------------------------------------------------
# Estimator: binary-vs-ASCII STL disambiguation (the dangerous direction).
# ---------------------------------------------------------------------------


def test_binary_stl_with_trailing_bytes_is_not_underestimated(tmp_path: Path) -> None:
    # Some exporters append metadata after the facet block, so the exact
    # 84 + 50*N size check fails. The old code fell back to the ASCII estimate
    # (size // 250), underestimating a binary file ~5x and letting an over-cap
    # mesh slip through to an OOM load. The body-size estimate must stay a safe
    # upper bound on the real triangle count.
    p = tmp_path / "trailing.stl"
    n = 100_000
    _write_binary_stl(p, n)
    with p.open("ab") as fh:
        fh.write(b"exported by SomeSlicer\x00\x01\x02" * 50)  # trailing junk

    est = mesh_processing._estimate_triangle_count(p)
    assert est is not None
    assert est >= n  # never below the true count (the OOM-unsafe direction)
    # And nowhere near the 5x-low ASCII misread.
    assert est < n * 2


def test_ascii_stl_is_detected_and_estimated_by_text_density(tmp_path: Path) -> None:
    facet = (
        b"  facet normal 0 0 1\n"
        b"    outer loop\n"
        b"      vertex 0 0 0\n"
        b"      vertex 1 0 0\n"
        b"      vertex 0 1 0\n"
        b"    endloop\n"
        b"  endfacet\n"
    )
    p = tmp_path / "ascii.stl"
    p.write_bytes(b"solid mymesh\n" + facet * 300 + b"endsolid mymesh\n")

    est = mesh_processing._estimate_triangle_count(p)
    # ASCII estimate is size // 250; the file holds 300 real facets, and the
    # estimate should land in the same order of magnitude (not the 5x-too-low
    # binary misread of size // 50-equivalents).
    assert est == p.stat().st_size // 250
    assert est > 0


def test_binary_stl_header_starting_with_solid_is_not_misread_as_ascii(
    tmp_path: Path,
) -> None:
    # The classic STL trap: a binary STL whose 80-byte header text starts with
    # "solid". The NUL bytes in the binary body must keep it on the binary path.
    p = tmp_path / "trap.stl"
    n = 60_000
    with p.open("wb") as fh:
        fh.write(b"solid exported-by-tool".ljust(80, b"\x00"))
        fh.write(struct.pack("<I", n))
        fh.write(b"\x00" * (50 * n))
    with p.open("ab") as fh:
        fh.write(b"trailer")  # break the exact size match

    est = mesh_processing._estimate_triangle_count(p)
    assert est is not None
    assert est >= n  # treated as binary, not the 5x-low ASCII estimate


# ---------------------------------------------------------------------------
# Estimator: PLY face count from the header (no body parse).
# ---------------------------------------------------------------------------


def test_ply_face_count_from_header(tmp_path: Path) -> None:
    p = tmp_path / "scan.ply"
    header = (
        b"ply\n"
        b"format binary_little_endian 1.0\n"
        b"element vertex 8\n"
        b"property float x\n"
        b"property float y\n"
        b"property float z\n"
        b"element face 1234567\n"
        b"property list uchar int vertex_indices\n"
        b"end_header\n"
    )
    # Body is intentionally tiny/garbage — the estimate must come from the header
    # alone, never from loading the (declared-huge) body.
    p.write_bytes(header + b"\x00" * 32)

    assert mesh_processing._estimate_triangle_count(p) == 1234567


def test_ply_without_face_element_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "points.ply"
    p.write_bytes(
        b"ply\nformat ascii 1.0\nelement vertex 3\n"
        b"property float x\nend_header\n0 0 0\n"
    )
    assert mesh_processing._estimate_triangle_count(p) is None


def test_over_cap_ply_skips_load(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setitem(_overlay, "mesh_max_render_triangles", 1000)
    p = tmp_path / "dense.ply"
    p.write_bytes(
        b"ply\nformat binary_little_endian 1.0\n"
        b"element face 999999\nend_header\n"
    )
    monkeypatch.setattr(
        mesh_processing,
        "_load_mesh",
        lambda _p: (_ for _ in ()).throw(AssertionError("over-cap PLY must not load")),
    )

    geometry = mesh_processing.extract_geometry(p)
    assert geometry["triangle_count"] is None


# ---------------------------------------------------------------------------
# The cap is enforced on every entry point, not just analyze_mesh.
# ---------------------------------------------------------------------------


def test_extract_geometry_respects_cap(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setitem(_overlay, "mesh_max_render_triangles", 1000)
    p = tmp_path / "huge.stl"
    _write_binary_stl(p, 50_000)
    monkeypatch.setattr(
        mesh_processing,
        "_load_mesh",
        lambda _p: (_ for _ in ()).throw(AssertionError("must not load")),
    )
    assert mesh_processing.extract_geometry(p)["triangle_count"] is None


def test_render_thumbnail_respects_cap_and_falls_back_to_embedded(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setitem(_overlay, "mesh_max_render_triangles", 1000)
    png = mesh_processing._PNG_MAGIC + b"plate"
    p = tmp_path / "dense.3mf"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("3D/3dmodel.model", b"<triangle/>" * 100_000)  # over cap
        zf.writestr("Metadata/thumbnail.png", png)
    monkeypatch.setattr(
        mesh_processing,
        "_load_mesh",
        lambda _p: (_ for _ in ()).throw(AssertionError("must not load")),
    )

    assert mesh_processing.render_thumbnail(p) == png


def test_to_stl_bytes_refuses_over_cap_mesh(tmp_path: Path, monkeypatch) -> None:
    # A download-as-STL click on a monster 3MF/OBJ must not run an unbounded
    # trimesh.load (which would OOM the process for every user). Refuse cleanly.
    monkeypatch.setitem(_overlay, "mesh_max_render_triangles", 1000)
    p = tmp_path / "dense.3mf"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("3D/3dmodel.model", b"<triangle/>" * 100_000)  # over cap
    monkeypatch.setattr(
        mesh_processing,
        "_load_mesh",
        lambda _p: (_ for _ in ()).throw(AssertionError("must not load")),
    )

    assert mesh_processing.to_stl_bytes(p) is None


def test_to_stl_bytes_passes_through_raw_stl(tmp_path: Path) -> None:
    # An STL is returned byte-for-byte without any load, so the cap never applies
    # (no conversion, no memory blow-up) even for a large file.
    p = tmp_path / "raw.stl"
    _write_binary_stl(p, 10)
    assert mesh_processing.to_stl_bytes(p) == p.read_bytes()


# ---------------------------------------------------------------------------
# Estimator: OBJ face-directive count (a first-class type that was unguarded).
# ---------------------------------------------------------------------------


def _write_obj(path: Path, tri_faces: int, *, quads: int = 0) -> None:
    lines = [b"# comment\n", b"o mesh\n", b"v 0 0 0\n", b"vn 0 0 1\n"]
    lines += [b"f 1//1 2//1 3//1\n"] * tri_faces
    lines += [b"f 1 2 3 4\n"] * quads  # quad = 2 triangles after fan
    path.write_bytes(b"".join(lines))


def test_obj_triangle_count_from_face_directives(tmp_path: Path) -> None:
    p = tmp_path / "mesh.obj"
    _write_obj(p, tri_faces=300)
    # 300 triangular faces -> 300 triangles (exact for tris).
    assert mesh_processing._estimate_triangle_count(p) == 300


def test_obj_ngon_faces_count_conservatively(tmp_path: Path) -> None:
    p = tmp_path / "quads.obj"
    _write_obj(p, tri_faces=10, quads=5)  # 10 + 5*(4-2) = 20 triangles
    assert mesh_processing._estimate_triangle_count(p) == 20


def test_obj_without_faces_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "points.obj"
    p.write_bytes(b"v 0 0 0\nv 1 0 0\nvn 0 0 1\n")
    assert mesh_processing._estimate_triangle_count(p) is None


def test_over_cap_obj_skips_load(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setitem(_overlay, "mesh_max_render_triangles", 1000)
    p = tmp_path / "dense.obj"
    _write_obj(p, tri_faces=5000)  # well over the cap
    monkeypatch.setattr(
        mesh_processing,
        "_load_mesh",
        lambda _p: (_ for _ in ()).throw(AssertionError("over-cap OBJ must not load")),
    )

    assert mesh_processing.extract_geometry(p)["triangle_count"] is None
    assert mesh_processing.render_thumbnail(p) is None
    assert mesh_processing.to_stl_bytes(p) is None
