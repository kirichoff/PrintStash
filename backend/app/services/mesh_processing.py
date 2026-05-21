"""Mesh loading, geometry extraction, thumbnail rendering, and STL export.

Trimesh is lazy-imported as it is heavy. All functions accept a Path
and return Python dicts / bytes so callers never touch trimesh directly.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


def _load_mesh(path: Path):
    """Return a trimesh.Trimesh for *path*, or None on failure."""
    import trimesh

    try:
        loaded = trimesh.load(str(path), force="mesh")
    except Exception:
        logger.warning("mesh_processing: trimesh.load failed for %s", path.name, exc_info=True)
        return None

    if isinstance(loaded, trimesh.Trimesh):
        return loaded

    if isinstance(loaded, trimesh.Scene):
        # Merge all geometry into a single mesh.
        meshes = [
            g
            for g in loaded.geometry.values()
            if isinstance(g, trimesh.Trimesh)
        ]
        if not meshes:
            return None
        if len(meshes) == 1:
            return meshes[0]
        return trimesh.util.concatenate(meshes)

    return None


def extract_geometry(path: Path) -> Dict[str, Optional[float]]:
    """Extract bounding-box, volume, and triangle count from a mesh file.

    Returns a dictionary suitable for passing as **kwargs to the
    Metadata SQLModel constructor (bbox_x_mm, bbox_y_mm, bbox_z_mm,
    volume_mm3, triangle_count).  Values are None when extraction fails.
    """
    out: Dict[str, Optional[float]] = {
        "bbox_x_mm": None,
        "bbox_y_mm": None,
        "bbox_z_mm": None,
        "volume_mm3": None,
        "triangle_count": None,
    }

    mesh = _load_mesh(path)
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
        pass

    return out


def render_thumbnail(path: Path, width: int = 640, height: int = 480) -> Optional[bytes]:
    """Render a PNG thumbnail of *path* via a pure-numpy software rasterizer.

    No GL / no display required. Produces an isometric-ish, lit, z-buffered
    view of the mesh. Returns raw PNG bytes or None on failure.
    """
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        logger.error("mesh_processing: numpy/Pillow unavailable; cannot render thumbnail")
        return None

    mesh = _load_mesh(path)
    if mesh is None or len(mesh.vertices) == 0 or mesh.faces is None or len(mesh.faces) == 0:
        logger.warning("mesh_processing: empty mesh for %s", path.name)
        return None

    try:
        verts = np.asarray(mesh.vertices, dtype=np.float64)
        faces = np.asarray(mesh.faces, dtype=np.int64)

        # 1. Centre the mesh at origin.
        center = (verts.max(axis=0) + verts.min(axis=0)) * 0.5
        verts = verts - center

        # 2. Build an isometric-ish view matrix (rotate around X then Z).
        elev = np.radians(30.0)
        azim = np.radians(-45.0)
        cz, sz = np.cos(azim), np.sin(azim)
        cx, sx = np.cos(elev), np.sin(elev)
        # Rotate around Z (yaw) then around X (pitch) — Z-up convention.
        rot_z = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], dtype=np.float64)
        rot_x = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float64)
        rotation = rot_x @ rot_z
        view = verts @ rotation.T  # (N, 3)

        # 3. Orthographic projection with margin; preserve aspect ratio.
        xs, ys = view[:, 0], view[:, 1]
        x_min, x_max = float(xs.min()), float(xs.max())
        y_min, y_max = float(ys.min()), float(ys.max())
        extent_x = max(x_max - x_min, 1e-6)
        extent_y = max(y_max - y_min, 1e-6)
        margin = 0.08
        scale = min(
            (width * (1 - 2 * margin)) / extent_x,
            (height * (1 - 2 * margin)) / extent_y,
        )
        # Map to pixel coordinates (image y is flipped).
        px = (xs - (x_min + x_max) * 0.5) * scale + width * 0.5
        py = height * 0.5 - (ys - (y_min + y_max) * 0.5) * scale
        pz = view[:, 2]
        screen = np.stack([px, py, pz], axis=1)

        # 4. Per-face: lighting + back-face culling using triangle normals.
        tri = screen[faces]                       # (F, 3, 3) screen-space
        world_tri = view[faces]                   # (F, 3, 3) view-space (post-rotation)
        edge1 = world_tri[:, 1] - world_tri[:, 0]
        edge2 = world_tri[:, 2] - world_tri[:, 0]
        normals = np.cross(edge1, edge2)
        norm_len = np.linalg.norm(normals, axis=1, keepdims=True)
        norm_len[norm_len == 0] = 1.0
        normals = normals / norm_len

        # Light from camera + a touch from upper-left for shape readability.
        light_dir = np.array([0.3, 0.4, 1.0])
        light_dir = light_dir / np.linalg.norm(light_dir)
        intensity = np.clip(normals @ light_dir, 0.0, 1.0)
        # Ambient floor so back-facing edges aren't pure black, plus diffuse.
        shade = 0.25 + 0.75 * intensity            # (F,)

        # Cull triangles facing away from camera (camera looks down +Z in our setup,
        # so visible faces have negative z-component of view-space normal).
        front = normals[:, 2] < 0.0
        # Also skip degenerate triangles.
        valid = front & (norm_len.squeeze() > 1e-8)
        tri = tri[valid]
        shade = shade[valid]
        if tri.shape[0] == 0:
            logger.warning("mesh_processing: no visible triangles for %s", path.name)
            # Fall through: draw silhouette anyway by using all triangles.
            tri = screen[faces]
            shade = np.full((faces.shape[0],), 0.6)

        # 5. Sort by average z (painter's algorithm — far first).
        avg_z = tri[:, :, 2].mean(axis=1)
        order = np.argsort(-avg_z)  # camera looks toward -Z (after rotation), far = smaller z
        tri = tri[order]
        shade = shade[order]

        # 6. Rasterise into RGB buffer with a per-pixel z-buffer for correctness.
        base_color = np.array([158, 179, 194], dtype=np.float32)   # slate blue-grey
        bg_color = np.array([248, 249, 250], dtype=np.uint8)       # match UI muted bg

        img = np.broadcast_to(bg_color, (height, width, 3)).copy()
        zbuf = np.full((height, width), np.inf, dtype=np.float32)

        # Pre-compute pixel grid once.
        _rasterise_triangles(img, zbuf, tri, shade, base_color, width, height)

        pil = Image.fromarray(img, mode="RGB")
        buf = io.BytesIO()
        pil.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception:
        logger.warning("mesh_processing: render_thumbnail failed for %s", path.name, exc_info=True)
        return None


def _rasterise_triangles(img, zbuf, tri, shade, base_color, width: int, height: int) -> None:
    """Z-buffered rasterisation of 2D triangles with per-face flat shading."""
    import numpy as np

    for i in range(tri.shape[0]):
        v0, v1, v2 = tri[i]
        x_min = max(int(np.floor(min(v0[0], v1[0], v2[0]))), 0)
        x_max = min(int(np.ceil(max(v0[0], v1[0], v2[0]))), width - 1)
        y_min = max(int(np.floor(min(v0[1], v1[1], v2[1]))), 0)
        y_max = min(int(np.ceil(max(v0[1], v1[1], v2[1]))), height - 1)
        if x_max < x_min or y_max < y_min:
            continue

        # Edge function denominator.
        denom = (v1[1] - v2[1]) * (v0[0] - v2[0]) + (v2[0] - v1[0]) * (v0[1] - v2[1])
        if abs(denom) < 1e-9:
            continue

        xs = np.arange(x_min, x_max + 1) + 0.5
        ys = np.arange(y_min, y_max + 1) + 0.5
        gx, gy = np.meshgrid(xs, ys)

        w0 = ((v1[1] - v2[1]) * (gx - v2[0]) + (v2[0] - v1[0]) * (gy - v2[1])) / denom
        w1 = ((v2[1] - v0[1]) * (gx - v2[0]) + (v0[0] - v2[0]) * (gy - v2[1])) / denom
        w2 = 1.0 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue

        z = w0 * v0[2] + w1 * v1[2] + w2 * v2[2]
        sub_z = zbuf[y_min : y_max + 1, x_min : x_max + 1]
        sub_img = img[y_min : y_max + 1, x_min : x_max + 1]
        write = inside & (z < sub_z)
        if not write.any():
            continue

        colour = np.clip(base_color * shade[i], 0, 255).astype(np.uint8)
        sub_img[write] = colour
        sub_z[write] = z[write]


def to_stl_bytes(path: Path) -> Optional[bytes]:
    """Convert any supported mesh file to binary STL bytes.

    If the file is already a binary STL, return its raw bytes.
    Returns None on conversion failure.
    """
    from pathlib import Path

    suffix = Path(path).suffix.lower()

    # If already STL, serve directly
    if suffix == ".stl":
        try:
            return path.read_bytes()
        except OSError:
            return None

    mesh = _load_mesh(path)
    if mesh is None:
        return None

    try:
        out = io.BytesIO()
        mesh.export(out, file_type="stl")
        return out.getvalue()
    except Exception:
        logger.warning("mesh_processing: STL export failed for %s", path.name, exc_info=True)
        return None
