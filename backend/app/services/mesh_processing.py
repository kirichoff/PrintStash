"""Mesh loading, geometry extraction, thumbnail rendering, and STL export.

Trimesh is heavy, so it is lazy-imported inside each function that needs it.
Callers pass a `Path` and receive plain dicts / bytes — they never touch a
trimesh object directly.

The software thumbnail rasteriser lives in `mesh_render` and is re-exposed
here as `render_thumbnail` for backwards compatibility. Ingestion uses
`analyze_mesh`, which loads the mesh once for both geometry and thumbnail.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import gc
import io
import struct
import threading
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.logging import get_logger
from app.services import mesh_render

logger = get_logger(__name__)

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# Resolved once: the glibc handle used by _reclaim_memory, or False on a libc
# without malloc_trim (musl/Alpine, non-Linux). None means "not looked up yet".
_LIBC: "ctypes.CDLL | bool | None" = None


def _reclaim_memory() -> None:
    """Force Python + the allocator to give a just-freed mesh back to the OS.

    Loading and rasterising a mesh churns hundreds of MB of NumPy/trimesh arrays.
    Dropping the references frees them on the Python heap, but glibc keeps the
    emptied arenas mapped, so across a long library scan RSS only ever climbs and
    never recedes — which presents exactly as a memory leak (#29). A
    ``gc.collect()`` breaks any reference cycles the mesh held, and
    ``malloc_trim(0)`` returns the freed arenas to the kernel so the high-water
    mark resets between files. Best-effort: a no-op where malloc_trim is absent.
    """
    gc.collect()
    global _LIBC
    try:
        if _LIBC is None:
            libc_name = ctypes.util.find_library("c")
            _LIBC = ctypes.CDLL(libc_name) if libc_name else False
        if _LIBC and hasattr(_LIBC, "malloc_trim"):
            _LIBC.malloc_trim(0)
    except (OSError, AttributeError):  # pragma: no cover - platform dependent
        _LIBC = False


# Process-wide gate limiting how many mesh load+render jobs run at once. Cached
# as (limit, semaphore) so a runtime override / test change to max_render_jobs
# rebuilds it; protected by a lock because ingestion calls in from the
# background-task threadpool.
_RENDER_SEMAPHORE: "tuple[int, threading.BoundedSemaphore] | None" = None
_RENDER_SEMAPHORE_LOCK = threading.Lock()


def _render_jobs_limit() -> int:
    """Effective max concurrent render jobs (always >= 1)."""
    try:
        return max(int(settings.max_render_jobs), 1)
    except (TypeError, ValueError):
        return 1


def _render_semaphore() -> "threading.BoundedSemaphore":
    """Concurrency gate for mesh load+render.

    Ingestion runs in FastAPI's background-task threadpool, so a bulk/folder
    upload (#26) can otherwise fire dozens of concurrent renders that each peak
    hundreds of MB and collectively OOM the box (#29). This caps how many run at
    once to ``VAULT_MAX_RENDER_JOBS``; the RAM-aware triangle cap separately
    divides its per-job budget by the same count so each concurrent job stays
    within its share.
    """
    global _RENDER_SEMAPHORE
    limit = _render_jobs_limit()
    with _RENDER_SEMAPHORE_LOCK:
        if _RENDER_SEMAPHORE is None or _RENDER_SEMAPHORE[0] != limit:
            _RENDER_SEMAPHORE = (limit, threading.BoundedSemaphore(limit))
        return _RENDER_SEMAPHORE[1]


def _estimate_triangle_count(path: Path) -> Optional[int]:
    """Best-effort triangle count *without* loading the mesh into memory.

    Loading is itself the memory blow-up (trimesh.load of a 5M-triangle mesh
    peaks at ~3.5 GB), so the only way to keep a dense lattice/gyroid model from
    OOM-killing the process is to estimate before we load and bail out (#24).

    Exact for binary STL (the triangle count is a uint32 in the header) and for
    PLY (the face count is declared in the ASCII header); a face-directive count
    for OBJ; a size-based estimate for ASCII STL and 3MF (uncompressed mesh XML).
    For an STL that fails the exact binary size check we distinguish ASCII from a
    binary file with trailing bytes and pick the *conservative* density, so we
    never underestimate a binary mesh into an unsafe load. Returns None for
    formats we can't cheaply size up (incl. STEP, which trimesh can't mesh
    without optional CAD deps anyway) — the caller then relies on the post-load
    cap, which still skips the render.
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
        if suffix == ".obj":
            # OBJ is plain text; each "f " line is one face. trimesh triangulates
            # an n-gon face into (n - 2) triangles, so summing that keeps the
            # estimate a conservative upper bound (tris/quads dominate real files,
            # where it's already exact). A full text scan is cheap — no float
            # parsing, no mesh build — versus the trimesh.load it guards against.
            faces = 0
            with path.open("rb") as fh:
                for line in fh:
                    if not line.startswith(b"f ") and not line.startswith(b"f\t"):
                        continue
                    # vertex refs on the line, minus 2 = triangles after fan
                    # triangulation; clamp at 1 so a malformed face never
                    # subtracts from the count.
                    verts = len(line.split()) - 1
                    faces += max(verts - 2, 1)
            return faces or None
        if suffix == ".3mf":
            with zipfile.ZipFile(path) as zf:
                infos = zf.infolist()
                xml_bytes = sum(
                    info.file_size
                    for info in infos
                    if info.filename.lower().endswith(".model")
                )
                if not xml_bytes:
                    # Some 3MF variants keep the mesh outside a ".model" part (or
                    # name it unusually). Rather than return None and let the
                    # caller load a possibly-huge archive blind (#29), fall back to
                    # the total uncompressed payload as a conservative upper bound.
                    xml_bytes = sum(info.file_size for info in infos)
            # 3MF mesh XML runs ~70 bytes per <triangle> (verts are shared).
            return xml_bytes // 70 if xml_bytes else None
    except (OSError, zipfile.BadZipFile, struct.error):
        return None
    return None

# Measured peak RSS per triangle for a full load + thumbnail render, rounded up
# for safety margin. 3MF's XML loader plus the crease-aware rasteriser cost far
# more than a raw STL of the same geometry (~4.5x), so it gets its own factor.
_PEAK_BYTES_PER_TRIANGLE: dict[str, int] = {".3mf": 3600}
_DEFAULT_PEAK_BYTES_PER_TRIANGLE = 2200  # stl / ply / obj

# Cached once: the memory ceiling this process can reach before the OOM killer
# fires. False means "looked up, nothing usable"; None means "not looked up yet".
_MEMORY_LIMIT_BYTES: "int | bool | None" = None


def _detect_memory_limit_bytes() -> int | None:
    """Best-effort bytes of RAM the process may use before being OOM-killed.

    Container-aware: a Docker/NAS deployment is usually capped well below host
    RAM by its cgroup, and that limit — not the host's total — is what the kernel
    enforces. Takes the smallest of the cgroup limit (v2 then v1) and host
    ``MemTotal`` so the RAM-aware cap reflects the real ceiling. Returns None when
    nothing can be read (non-Linux, locked-down /proc), disabling the RAM cap.
    """
    limits: list[int] = []
    try:  # cgroup v2
        raw = Path("/sys/fs/cgroup/memory.max").read_text().strip()
        if raw != "max":
            limits.append(int(raw))
    except (OSError, ValueError):
        pass
    try:  # cgroup v1
        v1 = int(Path("/sys/fs/cgroup/memory/memory.limit_in_bytes").read_text().strip())
        if 0 < v1 < (1 << 62):  # v1 uses a huge sentinel for "unlimited"
            limits.append(v1)
    except (OSError, ValueError):
        pass
    try:  # host total
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                limits.append(int(line.split()[1]) * 1024)
                break
    except (OSError, ValueError, IndexError):
        pass
    return min(limits) if limits else None


def _ram_triangle_cap(suffix: str) -> Optional[int]:
    """RAM-derived triangle ceiling for *suffix*, or None when RAM capping is off.

    Turns the ``mesh_memory_budget_fraction`` of detected memory into a triangle
    count using the format's measured per-triangle peak cost, so the same config
    auto-skips a mesh on a 4 GB box that a 32 GB box renders fine. The budget is
    divided by ``max_render_jobs`` so concurrent renders share the RAM ceiling
    rather than each claiming the whole of it (#29)."""
    fraction = settings.mesh_memory_budget_fraction
    if fraction <= 0:
        return None
    global _MEMORY_LIMIT_BYTES
    if _MEMORY_LIMIT_BYTES is None:
        _MEMORY_LIMIT_BYTES = _detect_memory_limit_bytes() or False
    if not _MEMORY_LIMIT_BYTES:
        return None
    budget = _MEMORY_LIMIT_BYTES * fraction / _render_jobs_limit()
    per_tri = _PEAK_BYTES_PER_TRIANGLE.get(suffix, _DEFAULT_PEAK_BYTES_PER_TRIANGLE)
    return max(int(budget / per_tri), 1)


def _exceeds_cap(path: Path) -> bool:
    """True when *path* is too expensive to hand to trimesh (#24, #29).

    Centralises the "bail out before loading" guard so every entry point
    (analyze/geometry/thumbnail/export) skips the same monster meshes and logs
    consistently. Two independent ceilings, because each covers the other's blind
    spot:

    * A raw on-disk **size** cap (``mesh_max_load_mb``). Format-blind, so it
      catches the files the triangle estimate can't size up — a 3MF whose mesh
      the estimator doesn't sum returns ``None`` below, and the old code then
      loaded the whole archive and OOM-killed the scan inside trimesh (#29).
    * The **triangle** estimate vs. ``mesh_max_render_triangles`` (#24), which
      catches a dense lattice/gyroid that is small on disk but explodes on load.

    Returns True if either ceiling is exceeded; the file is still indexed and a
    3MF still falls back to its embedded preview.
    """
    size_cap_mb = settings.mesh_max_load_mb
    if size_cap_mb > 0:
        try:
            size_mb = path.stat().st_size / (1024 * 1024)
        except OSError:
            size_mb = 0.0
        if size_mb > size_cap_mb:
            logger.warning(
                "mesh_processing: %s is %.0f MB (> cap %d MB); skipping mesh load "
                "to avoid OOM",
                path.name,
                size_mb,
                size_cap_mb,
            )
            return True

    estimate = _estimate_triangle_count(path)
    if estimate is None:
        return False
    # Effective cap = the smaller of the static ceiling and the RAM-derived cap,
    # so a small host auto-skips meshes a large host would render (#29).
    cap = settings.mesh_max_render_triangles
    ram_cap = _ram_triangle_cap(path.suffix.lower())
    if ram_cap is not None and ram_cap < cap:
        cap = ram_cap
        limiter = "RAM budget"
    else:
        limiter = "static cap"
    if estimate > cap:
        logger.warning(
            "mesh_processing: %s is ~%d triangles (> %s %d); skipping mesh load "
            "to avoid OOM",
            path.name,
            estimate,
            limiter,
            cap,
        )
        return True
    return False


# Slicer-generated 3MF archives usually embed a pre-rendered preview
# (Metadata/thumbnail.png per spec; plate_*.png from Orca/Bambu).
_3MF_THUMBNAIL_DIRS = ("metadata/", "3d/thumbnails/", "thumbnails/", "auxiliaries/.thumbnails/")


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
    # The file is still indexed; a large 3MF still gets its embedded preview below.
    over_cap = _exceeds_cap(path)

    # One concurrency gate around the whole load+render so a bulk upload's
    # background tasks don't collectively OOM the box (#29). The body is cheap
    # when the mesh is skipped (over cap), so holding the gate then is harmless.
    with _render_semaphore():
        mesh = None if over_cap else _load_mesh(path)

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
        if thumb is None and (
            not over_cap or settings.use_embedded_3mf_preview_for_large_files
        ):
            # Embedded slicer preview as a fallback. When the mesh was skipped
            # before loading because it's too large, this preview is the only
            # source — and for a large 3MF it lets us avoid trimesh's costly XML
            # parse entirely — so that path is gated on the large-3MF flag.
            thumb = extract_embedded_3mf_thumbnail(path)
        if mesh is not None:
            # Free the mesh (and its NumPy arrays) before returning so a library
            # scan reclaims the memory between files instead of letting RSS climb.
            del mesh
            _reclaim_memory()
    return geometry, thumb


def extract_geometry(path: Path) -> Dict[str, Optional[float]]:
    """Extract bounding box, volume, and triangle count from a mesh file.

    The returned dict is shaped for direct use as **kwargs to the
    `Metadata` SQLModel constructor. Missing values are returned as None.
    """
    if _exceeds_cap(path):
        return _geometry_from_mesh(None)
    with _render_semaphore():
        mesh = _load_mesh(path)
        try:
            return _geometry_from_mesh(mesh)
        finally:
            if mesh is not None:
                del mesh
                _reclaim_memory()


def render_thumbnail(
    path: Path, width: int = 640, height: int = 480
) -> Optional[bytes]:
    """Render a PNG thumbnail of *path*. Returns PNG bytes or None on failure."""
    cap = settings.mesh_max_render_triangles
    over_cap = _exceeds_cap(path)
    with _render_semaphore():
        mesh = None if over_cap else _load_mesh(path)
        try:
            # Prefer the in-house render for a consistent look across all cards;
            # fall back to the slicer-embedded preview only when rendering fails
            # or is skipped. The over-cap embedded fallback is gated on the
            # large-3MF flag (consistent with analyze_mesh).
            if mesh is not None and len(mesh.faces) <= cap:
                thumb = mesh_render.render_mesh_thumbnail(
                    mesh, path.name, width=width, height=height
                )
                if thumb is not None:
                    return thumb
            if not over_cap or settings.use_embedded_3mf_preview_for_large_files:
                return extract_embedded_3mf_thumbnail(path)
            return None
        finally:
            if mesh is not None:
                del mesh
                _reclaim_memory()


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

    with _render_semaphore():
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
        finally:
            del mesh
            _reclaim_memory()


# --------------------------------------------------------------------------- #
# Per-plate 3MF parsing (multi-plate viewer)
# --------------------------------------------------------------------------- #

# Bambu/Orca cap: refuse pathological archives with hundreds of objects.
_MAX_PLATE_OBJECTS = 64


@dataclass
class PlateObject:
    """One printable object placed on a plate."""

    stl_bytes: bytes
    bbox_mm: Tuple[float, float, float]
    # Object translation on the bed (mm) from the build-item transform.
    origin_mm: Tuple[float, float, float]
    name: Optional[str] = None


@dataclass
class PlateGeometry:
    """One build plate and the objects assigned to it."""

    index: int  # 1-based plate number
    objects: List[PlateObject] = field(default_factory=list)


def _read_zip_member(zf: "zipfile.ZipFile", *candidates: str) -> Optional[bytes]:
    """Return the first archive member matching one of *candidates*
    (case-insensitive, tolerant of a leading slash), or None."""
    names = {n.lower().lstrip("/"): n for n in zf.namelist()}
    for cand in candidates:
        key = cand.lower().lstrip("/")
        if key in names:
            return zf.read(names[key])
    # Suffix match (e.g. "3d/3dmodel.model" regardless of casing/prefix).
    for cand in candidates:
        suffix = cand.lower().lstrip("/")
        for low, real in names.items():
            if low.endswith(suffix):
                return zf.read(real)
    return None


def _parse_plate_object_map(config_xml: bytes) -> Dict[int, List[int]]:
    """Map ``{plater_id: [root_object_id, ...]}`` from ``model_settings.config``.

    Returns an empty dict when the config is absent or unparseable, signalling a
    single-plate fallback to the caller.
    """
    import xml.etree.ElementTree as ET

    out: Dict[int, List[int]] = {}
    try:
        root = ET.fromstring(config_xml)
    except Exception:
        return out
    for plate in root.findall(".//plate"):
        plater_id: Optional[int] = None
        for m in plate.findall("./metadata"):
            if m.get("key") == "plater_id":
                try:
                    plater_id = int(m.get("value", ""))
                except (TypeError, ValueError):
                    plater_id = None
        if plater_id is None:
            continue
        obj_ids: List[int] = []
        for inst in plate.findall("./model_instance"):
            for m in inst.findall("./metadata"):
                if m.get("key") == "object_id":
                    try:
                        obj_ids.append(int(m.get("value", "")))
                    except (TypeError, ValueError):
                        pass
        out[plater_id] = obj_ids
    return out


def _parse_root_object_components(model_xml: bytes) -> Dict[int, str]:
    """Map root ``<object id>`` → its component inner ``objectid`` (as a string
    scene-geometry key) from ``3D/3dmodel.model``."""
    import xml.etree.ElementTree as ET

    out: Dict[int, str] = {}
    try:
        root = ET.fromstring(model_xml)
    except Exception:
        return out
    # 3MF core namespace on <object>; components/component may carry it too.
    for obj in root.iter():
        if not obj.tag.endswith("}object") and obj.tag != "object":
            continue
        oid = obj.get("id")
        if oid is None:
            continue
        for comp in obj.iter():
            if comp.tag.endswith("}component") or comp.tag == "component":
                inner = comp.get("objectid")
                if inner is not None:
                    try:
                        out[int(oid)] = str(inner)
                    except ValueError:
                        pass
                    break
    return out


def parse_3mf_plates(path: Path) -> List[PlateGeometry]:
    """Parse a 3MF into per-plate object geometry, preserving plate grouping
    and per-object bed placement. Never flattens across plates.

    Degrades to a single plate holding every object when the archive carries no
    Bambu/Orca plate config, and returns ``[]`` when the file is too large to
    load safely or cannot be parsed.
    """
    import trimesh

    if path.suffix.lower() != ".3mf":
        return []
    if _exceeds_cap(path):
        logger.warning("mesh_processing: 3mf %s over cap, skipping plate parse", path.name)
        return []

    # Read the plate map + component map from the archive (best-effort).
    plate_object_map: Dict[int, List[int]] = {}
    root_components: Dict[int, str] = {}
    try:
        with zipfile.ZipFile(path) as zf:
            cfg = _read_zip_member(zf, "Metadata/model_settings.config")
            if cfg:
                plate_object_map = _parse_plate_object_map(cfg)
            model = _read_zip_member(zf, "3D/3dmodel.model", "3dmodel.model")
            if model:
                root_components = _parse_root_object_components(model)
    except (zipfile.BadZipFile, OSError):
        logger.warning("mesh_processing: 3mf %s not a readable zip", path.name, exc_info=True)
        return []

    with _render_semaphore():
        try:
            scene = trimesh.load(str(path), force="scene", process=False)
        except Exception:
            logger.warning("mesh_processing: trimesh scene load failed for %s", path.name, exc_info=True)
            return []

        try:
            # Build {geometry_key: (Trimesh, translation_xyz)} from the scene graph.
            geom_nodes: Dict[str, Tuple["trimesh.Trimesh", Tuple[float, float, float]]] = {}
            if isinstance(scene, trimesh.Scene):
                for node in scene.graph.nodes_geometry:
                    transform, geom_key = scene.graph[node]
                    mesh = scene.geometry.get(geom_key)
                    if mesh is None or not isinstance(mesh, trimesh.Trimesh):
                        continue
                    t = transform[:3, 3]
                    geom_nodes[str(geom_key)] = (
                        mesh,
                        (float(t[0]), float(t[1]), float(t[2])),
                    )
            elif isinstance(scene, trimesh.Trimesh):
                geom_nodes["0"] = (scene, (0.0, 0.0, 0.0))

            if not geom_nodes:
                return []

            def _make_object(
                mesh: "trimesh.Trimesh", origin: Tuple[float, float, float]
            ) -> Optional[PlateObject]:
                try:
                    out = io.BytesIO()
                    mesh.export(out, file_type="stl")
                    stl = out.getvalue()
                except Exception:
                    return None
                if not stl or len(stl) <= 84:
                    return None
                if mesh.vertices.shape[0] > 0:
                    extents = mesh.bounds[1] - mesh.bounds[0]
                    bbox = (
                        round(float(extents[0]), 2),
                        round(float(extents[1]), 2),
                        round(float(extents[2]), 2),
                    )
                else:
                    bbox = (0.0, 0.0, 0.0)
                return PlateObject(stl_bytes=stl, bbox_mm=bbox, origin_mm=origin)

            plates: List[PlateGeometry] = []
            used_keys: set[str] = set()
            object_budget = _MAX_PLATE_OBJECTS

            if plate_object_map and root_components:
                for plater_id in sorted(plate_object_map):
                    plate = PlateGeometry(index=plater_id)
                    for root_obj_id in plate_object_map[plater_id]:
                        geom_key = root_components.get(root_obj_id)
                        if geom_key is None or geom_key not in geom_nodes:
                            continue
                        if object_budget <= 0:
                            break
                        mesh, origin = geom_nodes[geom_key]
                        po = _make_object(mesh, origin)
                        if po is not None:
                            plate.objects.append(po)
                            used_keys.add(geom_key)
                            object_budget -= 1
                    if plate.objects:
                        plates.append(plate)

            # Any geometry not claimed by a plate (or no plate map at all) goes
            # onto a single fallback plate so nothing is silently dropped.
            leftover = [
                (k, v) for k, v in geom_nodes.items() if k not in used_keys
            ]
            if leftover and object_budget > 0:
                fallback_index = (max((p.index for p in plates), default=0) + 1) if plates else 1
                fallback = PlateGeometry(index=fallback_index)
                for _key, (mesh, origin) in leftover:
                    if object_budget <= 0:
                        break
                    po = _make_object(mesh, origin)
                    if po is not None:
                        fallback.objects.append(po)
                        object_budget -= 1
                if fallback.objects:
                    plates.append(fallback)

            # Re-number plates 1..N in order so the frontend gets a clean sequence.
            plates.sort(key=lambda p: p.index)
            for i, plate in enumerate(plates, start=1):
                plate.index = i
            return plates
        finally:
            del scene
            _reclaim_memory()
