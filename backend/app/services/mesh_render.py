"""Software triangle rasteriser used by `mesh_processing.render_thumbnail`.

Pure numpy + Pillow — no GL, no display. Kept in its own module so the
mesh-processing surface stays focused on load / geometry / export and this
~120-line block of graphics code can be read (or replaced) in isolation.

When the ``_nexus3d_rust`` native module is available the inner rasterisation
loop runs in Rust (rayon-parallel) instead of Python/numpy.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from app.core.logging import get_logger
from app.services import raster_rust

logger = get_logger(__name__)


def render_thumbnail(
    load_mesh, path: Path, width: int = 640, height: int = 480
) -> Optional[bytes]:
    """Render a PNG thumbnail of *path* via an isometric software rasteriser.

    `load_mesh` is injected to avoid a circular import on `mesh_processing`.
    Returns raw PNG bytes, or None on failure.
    """
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        logger.error("mesh_render: numpy/Pillow unavailable; cannot render thumbnail")
        return None

    mesh = load_mesh(path)
    if (
        mesh is None
        or len(mesh.vertices) == 0
        or mesh.faces is None
        or len(mesh.faces) == 0
    ):
        logger.warning("mesh_render: empty mesh for %s", path.name)
        return None

    try:
        verts = np.asarray(mesh.vertices, dtype=np.float64)
        faces = np.asarray(mesh.faces, dtype=np.int64)

        # 1. Centre the mesh at origin.
        center = (verts.max(axis=0) + verts.min(axis=0)) * 0.5
        verts = verts - center

        # 2. Build an isometric-ish view matrix (yaw around Z then pitch around X).
        elev = np.radians(30.0)
        azim = np.radians(-45.0)
        cz, sz = np.cos(azim), np.sin(azim)
        cx, sx = np.cos(elev), np.sin(elev)
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
        px = (xs - (x_min + x_max) * 0.5) * scale + width * 0.5
        py = height * 0.5 - (ys - (y_min + y_max) * 0.5) * scale  # image y is flipped
        pz = view[:, 2]
        screen = np.stack([px, py, pz], axis=1)

        # 4. Per-face: flat shading + back-face culling using triangle normals.
        tri = screen[faces]          # (F, 3, 3) screen-space
        world_tri = view[faces]      # (F, 3, 3) view-space (post-rotation)
        edge1 = world_tri[:, 1] - world_tri[:, 0]
        edge2 = world_tri[:, 2] - world_tri[:, 0]
        normals = np.cross(edge1, edge2)
        norm_len = np.linalg.norm(normals, axis=1, keepdims=True)
        norm_len[norm_len == 0] = 1.0
        normals = normals / norm_len

        # Light from camera, biased upper-left for shape readability.
        light_dir = np.array([0.3, 0.4, 1.0])
        light_dir = light_dir / np.linalg.norm(light_dir)
        intensity = np.clip(normals @ light_dir, 0.0, 1.0)
        shade = 0.25 + 0.75 * intensity  # ambient + diffuse, per face

        # Camera looks down +Z (after rotation); visible faces have normal.z < 0.
        front = normals[:, 2] < 0.0
        valid = front & (norm_len.squeeze() > 1e-8)  # drop degenerate triangles
        tri = tri[valid]
        shade = shade[valid]
        if tri.shape[0] == 0:
            logger.warning("mesh_render: no visible triangles for %s", path.name)
            # Fall back to a flat silhouette using every triangle.
            tri = screen[faces]
            shade = np.full((faces.shape[0],), 0.6)

        # 5. Painter's algorithm — draw far triangles first.
        avg_z = tri[:, :, 2].mean(axis=1)
        order = np.argsort(-avg_z)
        tri = tri[order]
        shade = shade[order]

        # 6. Rasterise into an RGB buffer with a per-pixel z-buffer for correctness.
        base_color = np.array([158, 179, 194], dtype=np.float32)  # slate blue-grey
        bg_color = np.array([248, 249, 250], dtype=np.uint8)      # matches UI bg

        # Try the Rust rasteriser first; fall back to numpy loop.
        rgb = raster_rust.rasterise(tri, shade, width, height)
        if rgb is None:
            img = np.broadcast_to(bg_color, (height, width, 3)).copy()
            zbuf = np.full((height, width), np.inf, dtype=np.float32)
            _rasterise_triangles(img, zbuf, tri, shade, base_color, width, height)
            rgb = img.tobytes()

        pil = Image.frombytes("RGB", (width, height), rgb)
        buf = io.BytesIO()
        pil.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
    except Exception:
        logger.warning(
            "mesh_render: render_thumbnail failed for %s", path.name, exc_info=True
        )
        return None


def _rasterise_triangles(
    img, zbuf, tri, shade, base_color, width: int, height: int
) -> None:
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

        # Edge-function denominator (twice the signed triangle area).
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
