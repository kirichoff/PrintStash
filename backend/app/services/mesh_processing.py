"""Mesh loading, geometry extraction, thumbnail rendering, and STL export.

Trimesh is heavy, so it is lazy-imported inside each function that needs it.
Callers pass a `Path` and receive plain dicts / bytes — they never touch a
trimesh object directly.

The software thumbnail rasteriser lives in `mesh_render` and is re-exposed
here as `render_thumbnail` for backwards compatibility. Ingestion uses
`analyze_mesh`, which loads the mesh once for both geometry and thumbnail.
"""

from __future__ import annotations

import io
import struct
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple
import zipfile

from app.core.config import settings
from app.core.logging import get_logger
from app.services import mesh_render

logger = get_logger(__name__)

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _estimate_triangle_count(path: Path) -> Optional[int]:
    """Best-effort triangle count *without* loading the mesh into memory.

    Loading is itself the memory blow-up (trimesh.load of a 5M-triangle mesh
    peaks at ~3.5 GB), so the only way to keep a dense lattice/gyroid model from
    OOM-killing the process is to estimate before we load and bail out (#24).

    Exact for binary STL (the triangle count is a uint32 in the header) and for
    PLY (the face count is declared in the ASCII header); a size-based estimate
    for ASCII STL and 3MF (uncompressed mesh XML). For an STL that fails the
    exact binary size check we distinguish ASCII from a binary file with trailing
    bytes and pick the *conservative* density, so we never underestimate a binary
    mesh into an unsafe load. Returns None for formats we can't cheaply size up —
    the caller then relies on the post-load cap, which still skips the render.
    """
    suffix = path.suffix.lower()
    try:
        if suffix == ".stl":
            size = path.stat().st_size
            with path.open("rb") as fh:
                sample = fh.read(1024)
            if len(sample) >= 84:
                count = struct.unpack("<I", sample[80:84])[0]
                # Binary STL is exactly 84 + 50 bytes per triangle; if the math
                # checks out we trust the header count exactly.
                if size == 84 + count * 50:
                    return count
            # The exact binary check failed. Now disambiguate a true ASCII STL
            # from a binary STL with trailing bytes (which also fails the check).
            # Guessing wrong toward ASCII is dangerous: ASCII is ~250 B/triangle
            # but binary is only ~50 B/triangle, so an ASCII estimate of a binary
            # file underestimates 5x and can let an over-cap mesh slip through to
            # the exact OOM load #24 set out to prevent. An ASCII STL starts with
            # the text "solid" and contains no NUL bytes; binary headers do.
            looks_ascii = (
                sample[:6].lower().startswith(b"solid") and b"\x00" not in sample
            )
            if looks_ascii:
                # ASCII STL: ~7 lines / ~250 bytes per triangle.
                return size // 250
            # Binary STL body is exactly 50 bytes per facet after the 84-byte
            # header; this stays a safe upper bound even with trailing bytes.
            return max(size - 84, 0) // 50
        if suffix == ".ply":
            # The PLY header is ASCII even when the body is binary, and it
            # declares the face count up front ("element face N"), so we can size
            # the mesh without parsing the (possibly huge) body.
            with path.open("rb") as fh:
                for _ in range(256):  # headers are short; bound the scan
                    line = fh.readline()
                    if not line:
                        break
                    parts = line.split()
                    if (
                        len(parts) >= 3
                        and parts[0].lower() == b"element"
                        and parts[1].lower() == b"face"
                    ):
                        try:
                            return int(parts[2])
                        except ValueError:
                            return None
                    if parts and parts[0].lower() == b"end_header":
                        break
            return None
        if suffix == ".3mf":
            with zipfile.ZipFile(path) as zf:
                xml_bytes = sum(
                    info.file_size
                    for info in zf.infolist()
                    if info.filename.lower().endswith(".model")
                )
            # 3MF mesh XML runs ~70 bytes per <triangle> (verts are shared).
            return xml_bytes // 70 if xml_bytes else None
    except (OSError, zipfile.BadZipFile, struct.error):
        return None
    return None

def _exceeds_cap(path: Path) -> bool:
    """True when the pre-load triangle estimate is over the render cap (#24).

    Centralises the "estimate before loading and bail out" guard so every entry
    point (analyze/geometry/thumbnail/export) skips the same monster meshes and
    logs consistently. Returns False when the count can't be estimated cheaply —
    callers that load anyway then rely on the post-load backstop.
    """
    estimate = _estimate_triangle_count(path)
    cap = settings.mesh_max_render_triangles
    if estimate is not None and estimate > cap:
        logger.warning(
            "mesh_processing: %s is ~%d triangles (> cap %d); skipping mesh load "
            "to avoid OOM",
            path.name,
            estimate,
            cap,
        )
        return True
    return False


# Slicer-generated 3MF archives usually embed a pre-rendered preview
# (Metadata/thumbnail.png per spec; plate_*.png from Orca/Bambu).
_3MF_THUMBNAIL_DIRS = ("metadata/", "3d/thumbnails/", "thumbnails/")


def _load_mesh(path: Path):
    """Return a single `trimesh.Trimesh` for *path*, or None on failure."""
    import trimesh

    try:
        # process=False skips trimesh's vertex-merge + adjacency build, which we
        # don't need for bbox/volume/render and which adds ~15% peak memory.
        loaded = trimesh.load(str(path), force="mesh", process=False)
    except Exception:
        logger.warning(
            "mesh_processing: trimesh.load failed for %s", path.name, exc_info=True
        )
        return None

    if isinstance(loaded, trimesh.Trimesh):
        return loaded

    if isinstance(loaded, trimesh.Scene):
        # Flatten all geometry in the scene into a single mesh.
        meshes = [g for g in loaded.geometry.values() if isinstance(g, trimesh.Trimesh)]
        if not meshes:
            return None
        if len(meshes) == 1:
            return meshes[0]
        return trimesh.util.concatenate(meshes)

    return None


def _geometry_from_mesh(mesh) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {
        "bbox_x_mm": None,
        "bbox_y_mm": None,
        "bbox_z_mm": None,
        "volume_mm3": None,
        "triangle_count": None,
    }

    if mesh is None:
        return out

    if mesh.vertices.shape[0] > 0:
        extents = mesh.bounds[1] - mesh.bounds[0]
        out["bbox_x_mm"] = round(float(extents[0]), 2)
        out["bbox_y_mm"] = round(float(extents[1]), 2)
        out["bbox_z_mm"] = round(float(extents[2]), 2)

    if mesh.faces is not None and len(mesh.faces) > 0:
        out["triangle_count"] = len(mesh.faces)

    try:
        vol = mesh.volume
        if vol is not None and vol > 0:
            out["volume_mm3"] = round(float(vol), 2)
    except Exception:
        # Non-watertight meshes raise here; volume is best-effort only.
        pass

    return out


def extract_embedded_3mf_thumbnail(path: Path) -> Optional[bytes]:
    """Return the largest PNG preview embedded in a 3MF archive, or None.

    3MF files are ZIP archives; slicers store a rendered plate preview next to
    the mesh. Using it skips the software rasteriser entirely and matches what
    the user saw in the slicer.
    """
    if path.suffix.lower() != ".3mf":
        return None
    try:
        with zipfile.ZipFile(path) as zf:
            candidates = [
                info
                for info in zf.infolist()
                if info.filename.lower().lstrip("/").startswith(_3MF_THUMBNAIL_DIRS)
                and info.filename.lower().endswith(".png")
                and info.file_size > 0
            ]
            if not candidates:
                return None
            best = max(candidates, key=lambda info: info.file_size)
            data = zf.read(best)
            if data.startswith(_PNG_MAGIC):
                logger.info(
                    "mesh_processing: using embedded 3MF thumbnail %s (%d bytes)",
                    best.filename,
                    len(data),
                )
                return data
    except (zipfile.BadZipFile, OSError, KeyError):
        logger.warning(
            "mesh_processing: embedded 3MF thumbnail read failed for %s",
            path.name,
            exc_info=True,
        )
    return None


def analyze_mesh(
    path: Path,
    *,
    width: int = 640,
    height: int = 480,
    report: Callable[[str], None] | None = None,
) -> Tuple[Dict[str, Optional[float]], Optional[bytes]]:
    """Extract geometry and render a thumbnail with a single mesh load.

    Returns ``(geometry_dict, png_bytes_or_None)``. *report* receives progress
    labels as the stages run (see ingestion progress hints).
    """

    def _report(label: str) -> None:
        if report is not None:
            report(label)

    _report("loading_mesh")
    cap = settings.mesh_max_render_triangles
    # Too dense to load safely — skip it rather than risk an OOM kill (#24).
    # The file is still indexed; a 3MF still gets its embedded preview below.
    mesh = None if _exceeds_cap(path) else _load_mesh(path)

    _report("extracting_geometry")
    geometry = _geometry_from_mesh(mesh)

    _report("rendering_thumbnail")
    # Render in-house first so every model card shares one look — same
    # blue-grey shading, same centred framing, same transparent background.
    # Slicer-embedded previews (orange G-code plate renders, off-centre 3MF
    # plate shots) are visually inconsistent, so they're only a fallback for
    # when the software rasteriser can't render the geometry.
    thumb: Optional[bytes] = None
    if mesh is not None and len(mesh.faces) > cap:
        # Backstop: the estimate missed (unknown format / bad header) but the
        # loaded mesh is over budget — keep the cheap geometry, skip the render.
        logger.warning(
            "mesh_processing: %s loaded with %d triangles (> cap %d); skipping render",
            path.name,
            len(mesh.faces),
            cap,
        )
    elif mesh is not None:
        thumb = mesh_render.render_mesh_thumbnail(
            mesh, path.name, width=width, height=height
        )
    if thumb is None:
        thumb = extract_embedded_3mf_thumbnail(path)
    return geometry, thumb


def extract_geometry(path: Path) -> Dict[str, Optional[float]]:
    """Extract bounding box, volume, and triangle count from a mesh file.

    The returned dict is shaped for direct use as **kwargs to the
    `Metadata` SQLModel constructor. Missing values are returned as None.
    """
    if _exceeds_cap(path):
        return _geometry_from_mesh(None)
    return _geometry_from_mesh(_load_mesh(path))


def render_thumbnail(
    path: Path, width: int = 640, height: int = 480
) -> Optional[bytes]:
    """Render a PNG thumbnail of *path*. Returns PNG bytes or None on failure."""
    cap = settings.mesh_max_render_triangles
    mesh = None if _exceeds_cap(path) else _load_mesh(path)
    # Prefer the in-house render for a consistent look across all cards; fall
    # back to the slicer-embedded preview only when rendering fails or is skipped.
    if mesh is not None and len(mesh.faces) <= cap:
        thumb = mesh_render.render_mesh_thumbnail(mesh, path.name, width=width, height=height)
        if thumb is not None:
            return thumb
    return extract_embedded_3mf_thumbnail(path)


def to_stl_bytes(path: Path) -> Optional[bytes]:
    """Convert any supported mesh file to binary STL bytes.

    If *path* is already an STL, its raw bytes are returned untouched.
    Returns None on conversion failure.
    """
    if path.suffix.lower() == ".stl":
        try:
            return path.read_bytes()
        except OSError:
            return None

    # Converting means a full trimesh.load + export; an over-cap mesh would OOM
    # the process and take every request down with it (#24). Refuse it cleanly —
    # the caller surfaces a 500 instead, which is far better than a crash-loop.
    if _exceeds_cap(path):
        return None

    mesh = _load_mesh(path)
    if mesh is None:
        return None

    try:
        out = io.BytesIO()
        mesh.export(out, file_type="stl")
        return out.getvalue()
    except Exception:
        logger.warning(
            "mesh_processing: STL export failed for %s", path.name, exc_info=True
        )
        return None
