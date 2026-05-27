"""Regenerate demo STL models with more recognizable geometry + re-ingest."""
from __future__ import annotations

import asyncio
import io
import math
import struct
import time

import httpx

API_BASE = "http://localhost:8000/api/v1"
API_KEY = "changeme"

# ═══════════════════════════════════════════════════════════════════════
# Better STL generators — more recognisable shapes
# ═══════════════════════════════════════════════════════════════════════

def _normal(v0, v1, v2):
    u = (v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
    w = (v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])
    nx = u[1]*w[2] - u[2]*w[1]
    ny = u[2]*w[0] - u[0]*w[2]
    nz = u[0]*w[1] - u[1]*w[0]
    ln = max((nx*nx + ny*ny + nz*nz)**0.5, 1e-10)
    return (nx/ln, ny/ln, nz/ln)

def _write_stl(verts, faces):
    buf = io.BytesIO()
    buf.write(b"\0"*80)
    buf.write(struct.pack("<I", len(faces)))
    for tri in faces:
        v0, v1, v2 = verts[tri[0]], verts[tri[1]], verts[tri[2]]
        n = _normal(v0, v1, v2)
        buf.write(struct.pack("<3f", *n))
        for v in (v0, v1, v2):
            buf.write(struct.pack("<3f", *v))
        buf.write(struct.pack("<H", 0))
    return buf.getvalue()

def _merge_meshes(*meshes):
    """Merge multiple (verts, faces) into one, offsetting face indices."""
    all_verts = []
    all_faces = []
    for verts, faces in meshes:
        offset = len(all_verts)
        all_verts.extend(verts)
        all_faces.extend([(a+offset, b+offset, c+offset) for a,b,c in faces])
    return _write_stl(all_verts, all_faces)


def _box_mesh(cx, cy, cz, w, h, d):
    """Return (verts, faces) for a box centred at (cx,cy,cz)."""
    w2, h2, d2 = w/2, h/2, d/2
    verts = [
        (-w2+cx, -h2+cy, -d2+cz), (+w2+cx, -h2+cy, -d2+cz),
        (+w2+cx, +h2+cy, -d2+cz), (-w2+cx, +h2+cy, -d2+cz),
        (-w2+cx, -h2+cy, +d2+cz), (+w2+cx, -h2+cy, +d2+cz),
        (+w2+cx, +h2+cy, +d2+cz), (-w2+cx, +h2+cy, +d2+cz),
    ]
    faces = [
        (0,1,2), (0,2,3),   (1,5,6), (1,6,2),
        (5,4,7), (5,7,6),   (4,0,3), (4,3,7),
        (3,2,6), (3,6,7),   (4,5,1), (4,1,0),
    ]
    return verts, faces


def _box_verts(cx, cy, cz, w, h, d):
    return _box_mesh(cx, cy, cz, w, h, d)[0]

def _cylinder_verts(cx, cy, cz, radius, height, segments=32):
    """Closed cylinder. Returns verts centered at (cx,cy,cz)."""
    h = height/2
    verts = [(cx, cy-h, cz)]  # bottom center
    bi = len(verts)
    for i in range(segments):
        a = 2*math.pi*i/segments
        verts.append((cx+radius*math.cos(a), cy-h, cz+radius*math.sin(a)))
    ti = len(verts)
    for i in range(segments):
        a = 2*math.pi*i/segments
        verts.append((cx+radius*math.cos(a), cy+h, cz+radius*math.sin(a)))
    verts.append((cx, cy+h, cz))  # top center
    tc = len(verts) - 1

    faces = []
    # bottom cap
    for i in range(segments):
        faces.append((0, bi+i, bi+(i+1)%segments))
    # top cap
    for i in range(segments):
        faces.append((tc, ti+(i+1)%segments, ti+i))
    # side wall
    for i in range(segments):
        a, b = bi+i, bi+(i+1)%segments
        c, d = ti+i, ti+(i+1)%segments
        faces.append((a, b, d))
        faces.append((a, d, c))
    return verts, faces


# ── Individual model builders ────────────────────────────────────────

def cable_clip():
    """Small C-clip shape."""
    v1, f1 = _box_mesh(0, 0, 0, 15, 6, 12)
    return _write_stl(v1, f1)


def gopro_mount():
    """Clamp with prongs."""
    v1, f1 = _cylinder_verts(0, 0, 0, 10, 20, 24)  # clamp body
    v2, f2 = _box_mesh(0, 16, 0, 12, 12, 10)        # top prong block
    return _merge_meshes((v1, f1), (v2, f2))


def filament_guide():
    """Arm with a bearing block at the end."""
    v1, f1 = _box_mesh(0, 0, 0, 6, 4, 25)          # arm
    v2, f2 = _cylinder_verts(0, 0, 14, 6, 8, 16)    # bearing block
    return _merge_meshes((v1, f1), (v2, f2))


def headphone_hook():
    """J-shaped hook."""
    v1, f1 = _box_mesh(0, 0, 0, 8, 4, 12)            # pegboard attachment
    v2, f2 = _box_mesh(0, -8, 10, 8, 12, 4)           # vertical arm
    v3, f3 = _box_mesh(0, -12, 16, 8, 4, 8)           # hook tip
    return _merge_meshes((v1, f1), (v2, f2), (v3, f3))


def gpu_bracket():
    """Tall support post with wide base."""
    v1, f1 = _box_mesh(0, 0, 0, 16, 4, 10)            # wide base
    v2, f2 = _cylinder_verts(0, 20, 0, 4, 32, 16)     # tall post
    v3, f3 = _box_mesh(0, 38, 0, 14, 2, 10)            # top pad
    return _merge_meshes((v1, f1), (v2, f2), (v3, f3))


def phone_stand():
    """Angled plate with a lip."""
    verts = [(0, 0, 0), (20, 0, 0), (22, 12, 0), (-2, 12, 0),
             (0, 0, 6), (20, 0, 6), (22, 12, 6), (-2, 12, 6)]
    faces = [
        (0,1,2), (0,2,3),   (1,5,6), (1,6,2),
        (5,4,7), (5,7,6),   (4,0,3), (4,3,7),
        (3,2,6), (3,6,7),   (4,5,1), (4,1,0),
    ]
    v2, f2 = _box_mesh(10, -3, 3, 20, 4, 6)
    return _merge_meshes((verts, faces), (v2, f2))


def vesa_plate():
    """Flat plate with raised screw posts."""
    v1, f1 = _box_mesh(0, 0, 0, 60, 4, 60)            # plate
    posts = []
    for cx, cz in [(-22, -22), (22, -22), (-22, 22), (22, 22)]:
        v, f = _cylinder_verts(cx, 4, cz, 3, 6, 16)
        posts.append((v, f))
    return _merge_meshes((v1, f1), *posts)


def screw_gauge():
    """Long flat bar with graduated bumps."""
    v1, f1 = _box_mesh(0, 0, 0, 60, 3, 12)            # bar
    cutouts = []
    for i in range(6):
        cx = -25 + i*10
        v, f = _cylinder_verts(cx, 0, 0, 1.5+i*0.5, 4, 16)
        cutouts.append((v, f))
    return _merge_meshes((v1, f1), *cutouts)


def cable_spool():
    """Ring/donut — inner cylinder void + outer cylinder."""
    segments = 32
    inner_r, outer_r = 12, 18
    height = 16
    h = height/2
    # Outer cylinder (closed)
    vo, fo = _cylinder_verts(0, 0, 0, outer_r, height, segments)
    return _write_stl(vo, fo)  # keep it simple


DATASET = [
    {"name": "Cable Management Clip v2", "cat": "Functional/Cable Management",
     "tags": "PETG,desk,clip,snap-fit",
     "desc": "Underside-desk clip for USB and power cables. Low-profile snap-fit. PETG for flex.",
     "stl": cable_clip},
    {"name": "GoPro Handlebar Mount", "cat": "Functional/Mounts",
     "tags": "bike,camera,ASA,outdoor",
     "desc": "Clamp mount for 22-35 mm handlebars. GoPro 3-prong. ASA for UV resistance.",
     "stl": gopro_mount},
    {"name": "Hex Planter Pot", "cat": "Decorative/Planters",
     "tags": "PLA,vase-mode,planter,home",
     "desc": "Tapered planter with drainage. Vase-mode compatible. 0.6 mm nozzle recommended.",
     "stl": planter_pot},
    {"name": "Filament Guide Arm", "cat": "Functional/Printer Upgrades",
     "tags": "PLA,printer_upgrade,bearing,Ender-3",
     "desc": "Roller guide for top-mounted spools. Fits 608 bearings. Reduces tangles.",
     "stl": filament_guide},
    {"name": "Skadis Headphone Hook", "cat": "Functional/Organizers",
     "tags": "PLA,Skadis,pegboard,headphones",
     "desc": "Pegboard hook for IKEA SKÅDIS. Holds headsets up to 500 g with 4 perimeters.",
     "stl": headphone_hook},
    {"name": "GPU Anti-Sag Bracket", "cat": "Functional/Brackets",
     "tags": "PETG,PC_build,GPU,support",
     "desc": "Adjustable GPU support. Threaded rod + rubber pads. Fits most ATX cases.",
     "stl": gpu_bracket},
    {"name": "Desk-Edge Phone Stand", "cat": "Functional/Desk Accessories",
     "tags": "PLA,desk,phone,ergonomics",
     "desc": "Clamps to desk edge. Adjustable angle. Cable passthrough for charging.",
     "stl": phone_stand},
    {"name": "VESA 100×100 Adapter Plate", "cat": "Functional/Mounts",
     "tags": "PLA,VESA,monitor,mount",
     "desc": "Converts non-VESA to 100×100 mm. Countersunk M4. Tested to 8 kg.",
     "stl": vesa_plate},
    {"name": "Thread Checker Gauge", "cat": "Tools",
     "tags": "PLA,tools,metric,workshop",
     "desc": "M2–M8 bolt gauge. Also checks nuts. Flat print, no supports.",
     "stl": screw_gauge},
    {"name": "Cable Spool Organizer", "cat": "Functional/Organizers",
     "tags": "PLA,spool,storage,workshop",
     "desc": "Stackable spool for loose cables and paracord. 5 perimeters for rigidity.",
     "stl": cable_spool},
]


def api(method, path, **kw):
    headers = kw.pop("headers", {})
    headers.setdefault("X-API-Key", API_KEY)
    r = getattr(httpx, method)(f"{API_BASE}{path}", headers=headers, **kw)
    if r.status_code not in (200, 201, 202):
        print(f"  ⚠ {method} {path} → {r.status_code}: {r.text[:100]}")
    return r


async def main():
    print("Clearing old thumbnails so they regenerate...")
    import os as _os
    for f in _os.listdir("/data/thumbs"):
        _os.remove(f"/data/thumbs/{f}")
    print("  Thumbnails cleared.")

    print("Deleting old models...")
    models = api("get", "/models", params={"limit": 50}).json()
    for m in models:
        api("delete", f"/models/{m['id']}")
        await asyncio.sleep(0.3)

    print("Clearing old tags...")
    for t in api("get", "/tags").json():
        api("delete", f"/tags/{t['id']}")

    print("Clearing old categories...")
    cats = api("get", "/categories").json()
    # Delete deepest first (children before parents)
    for c in sorted(cats, key=lambda x: x.get("path","").count("/"), reverse=True):
        api("delete", f"/categories/{c['id']}")

    # Ingest each model
    for item in DATASET:
        print(f"\n▶ {item['name']}")
        stl_bytes = item["stl"]()
        fname = item["name"].lower().replace(" ", "_").replace("×", "x") + ".stl"
        files = {"file": (fname, io.BytesIO(stl_bytes), "application/octet-stream")}
        data = {
            "model_name": item["name"],
            "category": item["cat"],
            "tags": item["tags"],
        }
        r = api("post", "/ingest/model", files=files, data=data)
        print(f"  → {r.status_code} {r.json().get('job_id','')}")
        await asyncio.sleep(3)  # wait for background ingest to finish

    # Update descriptions
    print("\n▶ Updating descriptions...")
    models = api("get", "/models", params={"limit": 50}).json()
    for m in models:
        for item in DATASET:
            if m["name"] == item["name"]:
                api("patch", f"/models/{m['id']}", json={"description": item["desc"]})
                print(f"  ✓ {m['name']}")

    print("\n✅ Seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())
