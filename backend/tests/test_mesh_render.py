from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from app.services import mesh_render


def _tilt_matrix() -> np.ndarray:
    # Flat meshes are viewed face-on but tipped 25° around screen-X
    # (see mesh_render._front_rotation_for_thin_axis).
    tilt = np.radians(25.0)
    ct, st = np.cos(tilt), np.sin(tilt)
    return np.array([[1, 0, 0], [0, ct, -st], [0, st, ct]], dtype=np.float64)


def test_flat_z_mesh_uses_front_view_like_stl_viewer() -> None:
    verts = np.array(
        [
            [-5.0, -5.0, -0.2],
            [5.0, -5.0, -0.2],
            [5.0, 5.0, 0.2],
            [-5.0, 5.0, 0.2],
        ],
        dtype=np.float64,
    )

    rotation = mesh_render._select_view_rotation(verts, np)
    view = verts @ rotation.T

    expected = _tilt_matrix() @ np.diag([1.0, 1.0, -1.0])
    np.testing.assert_allclose(rotation, expected, atol=1e-12)
    # Screen-X is untouched by the tilt: the broad face still spans the view.
    np.testing.assert_allclose(view[:, 0], verts[:, 0])


def test_solid_mesh_uses_z_up_hero_view() -> None:
    # A chunky/solid mesh gets the 3/4 "hero" view, not the flat front view.
    # Print models are Z-up, so object +Z must map to (mostly) screen-up — the
    # old view looked down the Z axis and showed the top of upright models (e.g.
    # the gathered top of a dumpling) instead of their front.
    verts = np.array(
        [
            [-1.0, -1.0, -1.0],
            [1.0, -1.0, -1.0],
            [1.0, 1.0, -1.0],
            [-1.0, 1.0, -1.0],
            [-1.0, -1.0, 1.0],
            [1.0, -1.0, 1.0],
            [1.0, 1.0, 1.0],
            [-1.0, 1.0, 1.0],
        ],
        dtype=np.float64,
    )

    rotation = mesh_render._select_view_rotation(verts, np)

    # A proper rotation, and not the flat front-view fallback.
    np.testing.assert_allclose(rotation @ rotation.T, np.eye(3), atol=1e-9)
    assert np.linalg.det(rotation) > 0.99
    assert not np.allclose(rotation, np.diag([1.0, 1.0, -1.0]))

    # Object +Z lands (mostly) on screen-up, not pointing into the screen.
    z_on_screen = rotation @ np.array([0.0, 0.0, 1.0])
    assert z_on_screen[1] > 0.8  # up
    assert abs(z_on_screen[0]) < 0.2  # not tipped sideways


def test_flat_x_mesh_uses_broad_face_view() -> None:
    verts = np.array(
        [
            [-0.1, -2.0, -3.0],
            [0.1, -2.0, -3.0],
            [0.1, 2.0, 3.0],
            [-0.1, 2.0, 3.0],
        ],
        dtype=np.float64,
    )

    rotation = mesh_render._select_view_rotation(verts, np)

    expected = _tilt_matrix() @ np.array(
        [
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [-1.0, 0.0, 0.0],
        ],
        dtype=np.float64,
    )
    np.testing.assert_allclose(rotation, expected, atol=1e-12)


def test_front_facing_flat_mesh_does_not_fall_back_to_silhouette(monkeypatch) -> None:
    mesh = SimpleNamespace(
        vertices=np.array(
            [
                [-1.0, -1.0, 0.0],
                [1.0, -1.0, 0.0],
                [1.0, 1.0, 0.0],
                [-1.0, 1.0, 0.0],
            ],
            dtype=np.float64,
        ),
        faces=np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64),
    )
    warnings: list[str] = []

    def capture_warning(message: str, *args, **kwargs) -> None:
        warnings.append(message % args if args else message)

    monkeypatch.setattr(mesh_render.logger, "warning", capture_warning)

    png = mesh_render.render_thumbnail(
        lambda _path: mesh, Path("front-facing.stl"), width=80, height=80
    )

    assert png is not None
    assert png.startswith(b"\x89PNG")
    assert not any("no visible triangles" in message for message in warnings)


def _unique_opaque_colours(png: bytes) -> int:
    """Number of distinct RGB shades among the opaque pixels of a thumbnail."""
    import io

    from PIL import Image

    arr = np.asarray(Image.open(io.BytesIO(png)).convert("RGBA"))
    opaque = arr[arr[:, :, 3] > 200][:, :3]
    return len(np.unique(opaque.reshape(-1, 3), axis=0))


def test_smooth_surface_renders_a_gradient_not_facets() -> None:
    # Crease-aware Gouraud shading: a sphere must shade as a smooth gradient
    # (thousands of shades), not a handful of flat facets. Guards the original
    # faceted-thumbnail regression.
    import trimesh

    png = mesh_render.render_mesh_thumbnail(
        trimesh.creation.uv_sphere(radius=5.0, count=[48, 48]), "sphere"
    )
    assert png is not None
    assert _unique_opaque_colours(png) > 2000


def test_hard_edges_stay_flat_not_melted() -> None:
    # The flip side: a cube must keep flat, distinct faces (a crease at each
    # edge), so it has far fewer shades than a smooth body of similar size.
    # Guards against smoothing rounding mechanical parts into a blob.
    import trimesh

    box = mesh_render.render_mesh_thumbnail(
        trimesh.creation.box(extents=[10.0, 12.0, 10.0]), "box"
    )
    sphere = mesh_render.render_mesh_thumbnail(
        trimesh.creation.uv_sphere(radius=6.0, count=[48, 48]), "sphere"
    )
    assert box is not None and sphere is not None
    assert _unique_opaque_colours(box) * 3 < _unique_opaque_colours(sphere)
