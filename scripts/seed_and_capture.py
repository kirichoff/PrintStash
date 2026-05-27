"""Seed realistic demo data into PrintStash and capture screenshots.

Runs inside the api container: docker exec -u root nexus3d-api .venv/bin/python /tmp/seed_and_capture.py
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

API_BASE = "http://localhost:8000/api/v1"
API_KEY = "changeme"  # from .env.example default
FRONTEND = "http://nexus3d-frontend:3000"
OUT_DIR = Path("/tmp/screenshots")
OUT_DIR.mkdir(exist_ok=True)

# ─── tiny STL generators ────────────────────────────────────────────────

def stl_cube(size: float = 20.0) -> bytes:
    """Axis-aligned cube, origin at centre."""
    s = size / 2
    verts = [
        (-s, -s, -s), (+s, -s, -s), (+s, +s, -s), (-s, +s, -s),  # back
        (-s, -s, +s), (+s, -s, +s), (+s, +s, +s), (-s, +s, +s),  # front
    ]
    faces = [
        (0, 1, 2), (0, 2, 3),   # back
        (1, 5, 6), (1, 6, 2),   # right
        (5, 4, 7), (5, 7, 6),   # front
        (4, 0, 3), (4, 3, 7),   # left
        (3, 2, 6), (3, 6, 7),   # top
        (4, 5, 1), (4, 1, 0),   # bottom
    ]
    return _write_binary_stl(verts, faces)


def stl_flattened_cube(w: float, h: float, d: float) -> bytes:
    """Rectangular prism (plate / bracket body)."""
    w2, h2, d2 = w / 2, h / 2, d / 2
    verts = [
        (-w2, -h2, -d2), (+w2, -h2, -d2), (+w2, +h2, -d2), (-w2, +h2, -d2),
        (-w2, -h2, +d2), (+w2, -h2, +d2), (+w2, +h2, +d2), (-w2, +h2, +d2),
    ]
    faces = [
        (0, 1, 2), (0, 2, 3), (1, 5, 6), (1, 6, 2),
        (5, 4, 7), (5, 7, 6), (4, 0, 3), (4, 3, 7),
        (3, 2, 6), (3, 6, 7), (4, 5, 1), (4, 1, 0),
    ]
    return _write_binary_stl(verts, faces)


def stl_l_bracket(body_w: float, body_h: float, body_d: float,
                  arm_w: float, arm_h: float, arm_d: float) -> bytes:
    """Simple L-shaped bracket (two boxes merged via boolean union of triangles)."""
    # We'll compose two flattened cubes as a union approximation
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []

    # Body (vertical)
    w2, h2, d2 = body_w / 2, body_h / 2, body_d / 2
    base = len(verts)
    v = [
        (-w2, -h2, -d2), (+w2, -h2, -d2), (+w2, +h2, -d2), (-w2, +h2, -d2),
        (-w2, -h2, +d2), (+w2, -h2, +d2), (+w2, +h2, +d2), (-w2, +h2, +d2),
    ]
    verts.extend(v)
    faces.extend([
        (base, base + 1, base + 2), (base, base + 2, base + 3),
        (base + 1, base + 5, base + 6), (base + 1, base + 6, base + 2),
        (base + 5, base + 4, base + 7), (base + 5, base + 7, base + 6),
        (base + 4, base + 0, base + 3), (base + 4, base + 3, base + 7),
        (base + 3, base + 2, base + 6), (base + 3, base + 6, base + 7),
        (base + 4, base + 5, base + 1), (base + 4, base + 1, base + 0),
    ])

    # Arm (horizontal, attached to bottom of body)
    w2a, h2a, d2a = arm_w / 2, arm_h / 2, arm_d / 2
    offset_x, offset_y, offset_z = 0.0, -h2 - h2a, d2 + d2a
    base2 = len(verts)
    v2 = [
        (-w2a + offset_x, -h2a + offset_y, -d2a + offset_z),
        (+w2a + offset_x, -h2a + offset_y, -d2a + offset_z),
        (+w2a + offset_x, +h2a + offset_y, -d2a + offset_z),
        (-w2a + offset_x, +h2a + offset_y, -d2a + offset_z),
        (-w2a + offset_x, -h2a + offset_y, +d2a + offset_z),
        (+w2a + offset_x, -h2a + offset_y, +d2a + offset_z),
        (+w2a + offset_x, +h2a + offset_y, +d2a + offset_z),
        (-w2a + offset_x, +h2a + offset_y, +d2a + offset_z),
    ]
    verts.extend(v2)
    faces.extend([
        (base2, base2 + 1, base2 + 2), (base2, base2 + 2, base2 + 3),
        (base2 + 1, base2 + 5, base2 + 6), (base2 + 1, base2 + 6, base2 + 2),
        (base2 + 5, base2 + 4, base2 + 7), (base2 + 5, base2 + 7, base2 + 6),
        (base2 + 4, base2 + 0, base2 + 3), (base2 + 4, base2 + 3, base2 + 7),
        (base2 + 3, base2 + 2, base2 + 6), (base2 + 3, base2 + 6, base2 + 7),
        (base2 + 4, base2 + 5, base2 + 1), (base2 + 4, base2 + 1, base2 + 0),
    ])

    return _write_binary_stl(verts, faces)


def stl_cylinder_vase(radius: float, height: float, segments: int = 24) -> bytes:
    """Open-top cylinder (vase/planter shape)."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    import math

    # Bottom cap (closed) and top rim (open)
    bottom_center = len(verts)
    verts.append((0.0, -height / 2, 0.0))
    bottom_ring = len(verts)
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        verts.append((radius * math.cos(angle), -height / 2, radius * math.sin(angle)))
    # Bottom cap triangles
    for i in range(segments):
        faces.append((bottom_center, bottom_ring + i, bottom_ring + (i + 1) % segments))

    top_ring = len(verts)
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        verts.append((radius * math.cos(angle), height / 2, radius * math.sin(angle)))
    # Side wall
    for i in range(segments):
        bi = bottom_ring + i
        bj = bottom_ring + (i + 1) % segments
        ti = top_ring + i
        tj = top_ring + (i + 1) % segments
        faces.append((bi, bj, tj))
        faces.append((bi, tj, ti))

    return _write_binary_stl(verts, faces)


def stl_rounded_plate(diameter: float, thickness: float, segments: int = 32) -> bytes:
    """Flat rounded disc (for phone stand base / clip base)."""
    import math

    r = diameter / 2
    h = thickness / 2
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []

    bottom_center = len(verts)
    verts.append((0.0, -h, 0.0))
    top_center = len(verts)
    verts.append((0.0, h, 0.0))

    bottom_ring = len(verts)
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        verts.append((r * math.cos(angle), -h, r * math.sin(angle)))
    top_ring = len(verts)
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        verts.append((r * math.cos(angle), h, r * math.sin(angle)))

    for i in range(segments):
        bi = bottom_ring + i
        bj = bottom_ring + (i + 1) % segments
        ti = top_ring + i
        tj = top_ring + (i + 1) % segments
        faces.append((bottom_center, bj, bi))  # bottom cap
        faces.append((top_center, ti, tj))     # top cap
        faces.append((bi, bj, tj))             # side wall
        faces.append((bi, tj, ti))

    return _write_binary_stl(verts, faces)


def _normal(v0, v1, v2):
    u = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
    w = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
    nx = u[1] * w[2] - u[2] * w[1]
    ny = u[2] * w[0] - u[0] * w[2]
    nz = u[0] * w[1] - u[1] * w[0]
    length = (nx * nx + ny * ny + nz * nz) ** 0.5
    if length < 1e-10:
        return (0.0, 0.0, 1.0)
    return (nx / length, ny / length, nz / length)


def _write_binary_stl(verts: list, faces: list) -> bytes:
    buf = io.BytesIO()
    buf.write(b"\x00" * 80)  # header
    buf.write(struct.pack("<I", len(faces)))  # triangle count
    for tri in faces:
        v0, v1, v2 = verts[tri[0]], verts[tri[1]], verts[tri[2]]
        nx, ny, nz = _normal(v0, v1, v2)
        buf.write(struct.pack("<3f", nx, ny, nz))
        for v in (v0, v1, v2):
            buf.write(struct.pack("<3f", *v))
        buf.write(struct.pack("<H", 0))  # attribute
    return buf.getvalue()


# ─── API helpers ────────────────────────────────────────────────────────

def api(method: str, path: str, **kw) -> httpx.Response:
    headers = kw.pop("headers", {})
    headers.setdefault("X-API-Key", API_KEY)
    r = getattr(httpx, method)(f"{API_BASE}{path}", headers=headers, **kw)
    if r.status_code >= 400:
        print(f"  API {method} {path} → {r.status_code}: {r.text[:200]}")
    return r


# ─── dataset ───────────────────────────────────────────────────────────

DATASET = [
    {
        "name": "Cable Management Clip v2",
        "description": "Underside desk clip for routing USB and power cables. Low-profile, snap-fit design. Printed in PETG for flexibility.",
        "category": "Functional/Cable Management",
        "tags": ["PETG", "desk", "clip", "snap-fit"],
        "stl": stl_l_bracket(8, 12, 3, 10, 3, 8),
    },
    {
        "name": "GoPro Handlebar Mount",
        "description": "Clamp-style mount for 22-35mm handlebars. M5 bolt tension, integrated GoPro-style 3-prong interface. ASA for UV resistance.",
        "category": "Functional/Mounts",
        "tags": ["bike", "camera", "ASA", "outdoor"],
        "stl": stl_l_bracket(12, 15, 10, 15, 5, 10),
    },
    {
        "name": "Planter Pot — Hex Pattern",
        "description": "80mm hexagonal planter with drainage holes and integrated saucer. Vase-mode compatible, 0.6mm nozzle recommended.",
        "category": "Decorative/Planters",
        "tags": ["PLA", "vase-mode", "planter", "home"],
        "stl": stl_cylinder_vase(25, 35, 24),
    },
    {
        "name": "Filament Guide Arm",
        "description": "Roller-bearing filament guide for top-mounted spool holders. Reduces feed angle, prevents tangles. Fits 608 bearings.",
        "category": "Functional/Printer Upgrades",
        "tags": ["PLA", "printer_upgrade", "bearing", "Ender-3"],
        "stl": stl_l_bracket(6, 20, 4, 8, 2, 12),
    },
    {
        "name": "Headphone Hook (IKEA Skadis)",
        "description": "Pegboard headphone hanger for IKEA SKÅDIS system. Fits all pegboard hole spacing. Holds up to 500g when printed with 4 perimeters.",
        "category": "Functional/Organizers",
        "tags": ["PLA", "Skadis", "pegboard", "headphones"],
        "stl": stl_l_bracket(6, 15, 3, 6, 3, 18),
    },
    {
        "name": "GPU Anti-Sag Bracket",
        "description": "Adjustable support bracket for heavy GPUs. Threaded rod design with rubber pads top and bottom. Fits most ATX cases.",
        "category": "Functional/Brackets",
        "tags": ["PETG", "PC_build", "GPU", "support"],
        "stl": stl_flattened_cube(10, 40, 10),
    },
    {
        "name": "Desk Edge Phone Stand",
        "description": "Clamps to desk edge, adjustable viewing angle. Fits phones up to 16mm thick with case. Cable passthrough for charging.",
        "category": "Functional/Desk Accessories",
        "tags": ["PLA", "desk", "phone", "ergonomics"],
        "stl": stl_l_bracket(10, 14, 5, 12, 4, 10),
    },
    {
        "name": "VESA 100x100 Adapter Plate",
        "description": "Converts non-VESA monitors to standard 100×100mm VESA mount. Countersunk M4 holes. Tested to 8kg with 6mm PLA walls.",
        "category": "Functional/Mounts",
        "tags": ["PLA", "VESA", "monitor", "mount"],
        "stl": stl_flattened_cube(55, 55, 5),
    },
    {
        "name": "Screw Gauge / Thread Checker",
        "description": "M2–M8 metric bolt gauge with marked sizes. Also checks nut sizes. Flat print, no supports needed.",
        "category": "Tools",
        "tags": ["PLA", "tools", "metric", "workshop"],
        "stl": stl_flattened_cube(40, 15, 3),
    },
    {
        "name": "Cable Spool Organizer",
        "description": "Stackable filament-shaped spool for storing loose cables, paracord, or ribbon. 5 perimeters for rigidity.",
        "category": "Functional/Organizers",
        "tags": ["PLA", "spool", "storage", "workshop"],
        "stl": stl_rounded_plate(30, 8, 32),
    },
]


# ─── main ───────────────────────────────────────────────────────────────

async def seed():
    """Create categories, tags, and ingest all models."""
    # Remove old test data first
    print("Clearing old test models...")
    # Delete models 1-5 (the test cubes / cam holder)
    for mid in range(1, 6):
        api("delete", f"/models/{mid}")

    # Remove old tags and categories
    print("Cleaning old tags & categories...")
    for tag_resp in api("get", "/tags").json():
        api("delete", f"/tags/{tag_resp['id']}")
    for cat_resp in api("get", "/categories").json():
        api("delete", f"/categories/{cat_resp['id']}")

    seen_categories: set[str] = set()
    seen_tags: set[str] = set()

    for item in DATASET:
        print(f"\nSeeding: {item['name']}")
        # Create category hierarchy
        cat_path = item["category"]
        parts = cat_path.split("/")
        parent_id = None
        for i, part in enumerate(parts):
            key = "/".join(parts[:i + 1])
            if key not in seen_categories:
                r = api("post", "/categories", json={
                    "name": part,
                    "parent_id": parent_id,
                })
                if r.status_code in (200, 201):
                    cat_data = r.json()
                    parent_id = cat_data["id"]
                    seen_categories.add(key)
                else:
                    # Might already exist, try to find it
                    cats = api("get", "/categories").json()
                    for c in cats:
                        if c.get("path") == key:
                            parent_id = c["id"]
                            seen_categories.add(key)
                            break
            else:
                cats = api("get", "/categories").json()
                for c in cats:
                    if c.get("path") == key:
                        parent_id = c["id"]
                        break

        # Create tags
        for tag_name in item["tags"]:
            if tag_name not in seen_tags:
                r = api("post", "/tags", json={"name": tag_name})
                if r.status_code in (200, 201):
                    seen_tags.add(tag_name)

        # Ingest STL
        stl_bytes = item["stl"]
        files = {"file": (f"{item['name'].lower().replace(' ', '_')}.stl", io.BytesIO(stl_bytes), "application/octet-stream")}
        data = {
            "model_name": item["name"],
            "category": item["category"],
            "tags": ",".join(item["tags"]),
        }
        r = api("post", "/ingest/model", files=files, data=data)
        if r.status_code in (200, 201, 202):
            result = r.json()
            print(f"  → job: {result.get('job_id', '?')} ({r.status_code})")
            # Wait a moment for background task
            await asyncio.sleep(2)
        else:
            print(f"  ✗ Failed: {r.status_code} {r.text[:200]}")

    # Update descriptions via PATCH
    print("\nUpdating model descriptions...")
    models = api("get", "/models", params={"limit": 50}).json()
    for model_item in models:
        for ds_item in DATASET:
            if model_item["name"] == ds_item["name"]:
                r = api("patch", f"/models/{model_item['id']}", json={
                    "description": ds_item["description"],
                })
                if r.status_code == 200:
                    print(f"  ✓ {model_item['name']}")
                else:
                    print(f"  ✗ {model_item['name']}: {r.status_code}")

    print("\nDone seeding!")


async def capture():
    """Capture fresh screenshots."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
        )

        # ── 01 — Asset Grid ──────────────────────────────────────────
        print("\nCapturing screenshots...")
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page = await ctx.new_page()
        await page.goto(FRONTEND + "/", wait_until="networkidle")
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(OUT_DIR / "01-asset-grid.png"))
        print("  ✓ 01-asset-grid.png")

        # ── 02 — Category filter sidebar ────────────────────────────
        # Try clicking a category chip/filter
        cat_links = page.locator('a[href*="category="], button:has-text("Cable"), button:has-text("Functional"), [data-testid="category"]')
        if await cat_links.count() > 0:
            await cat_links.first.click()
            await page.wait_for_timeout(800)
            await page.screenshot(path=str(OUT_DIR / "02-category-filter.png"))
            print("  ✓ 02-category-filter.png")
        else:
            print("  ⚠ No category filter found, trying tag filter")
            # Try tag instead
            tag_el = page.locator('text=PLA, text=PETG, text=desk').first
            if await tag_el.count() > 0:
                await tag_el.click()
                await page.wait_for_timeout(800)
                await page.screenshot(path=str(OUT_DIR / "02-category-filter.png"))
                print("  ✓ 02-category-filter.png")

        # ── 03 — Search ─────────────────────────────────────────────
        await page.goto(FRONTEND + "/", wait_until="networkidle")
        await page.wait_for_timeout(500)
        search = page.locator("input").first
        if await search.count() > 0:
            await search.click()
            await search.press_sequentially("bracket", delay=60)
            await page.wait_for_timeout(1000)
            await page.screenshot(path=str(OUT_DIR / "03-search.png"))
            print("  ✓ 03-search.png")

        # ── 04 — Model Detail (G-code mock: GPU Anti-Sag Bracket) ──
        await search.fill("")
        await page.wait_for_timeout(300)
        await page.goto(FRONTEND + "/", wait_until="networkidle")
        await page.wait_for_timeout(600)
        gpu_card = page.locator('text=GPU').first
        if await gpu_card.count() > 0:
            # Find parent link
            links = page.locator('a[href^="/models/"]')
            count = await links.count()
            for i in range(count):
                link = links.nth(i)
                text = await link.text_content()
                if "GPU" in text:
                    href = await link.get_attribute("href")
                    await page.goto(FRONTEND + href, wait_until="networkidle")
                    await page.wait_for_timeout(800)
                    await page.screenshot(path=str(OUT_DIR / "04-model-detail.png"))
                    print("  ✓ 04-model-detail.png")
                    break

        # ── 05 — 3D Viewer ──────────────────────────────────────────
        planter_card = page.locator('text=Planter').first
        if await planter_card.count() > 0:
            await page.goto(FRONTEND + "/", wait_until="networkidle")
            await page.wait_for_timeout(500)
            links = page.locator('a[href^="/models/"]')
            count = await links.count()
            for i in range(count):
                link = links.nth(i)
                text = await link.text_content()
                if "Planter" in text:
                    href = await link.get_attribute("href")
                    await page.goto(FRONTEND + href, wait_until="networkidle")
                    await page.wait_for_timeout(1000)
                    canvas = page.locator("canvas").first
                    if await canvas.count() > 0:
                        box = await canvas.bounding_box()
                        if box:
                            await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                            await page.mouse.down()
                            await page.mouse.move(box["x"] + box["width"] / 2 + 150, box["y"] + box["height"] / 2 + 50, steps=15)
                            await page.mouse.up()
                            await page.wait_for_timeout(500)
                            await page.mouse.down()
                            await page.mouse.move(box["x"] + box["width"] / 2 - 80, box["y"] + box["height"] / 2 - 30, steps=10)
                            await page.mouse.up()
                            await page.wait_for_timeout(400)
                    await page.screenshot(path=str(OUT_DIR / "05-3d-viewer.png"))
                    print("  ✓ 05-3d-viewer.png")
                    break

        await ctx.close()

        # ── 06 — Demo GIF ───────────────────────────────────────────
        print("\nRecording demo GIF...")
        vctx = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            device_scale_factor=1,
            record_video_dir=str(OUT_DIR),
            record_video_size={"width": 1280, "height": 720},
        )
        vpage = await vctx.new_page()

        await vpage.goto(FRONTEND + "/", wait_until="networkidle")
        await vpage.wait_for_timeout(1000)
        await vpage.evaluate("window.scrollBy(0, 200)")
        await vpage.wait_for_timeout(600)
        await vpage.evaluate("window.scrollTo(0, 0)")
        await vpage.wait_for_timeout(500)

        # Click on "Planter Pot" model
        links = vpage.locator('a[href^="/models/"]')
        count = await links.count()
        for i in range(count):
            link = links.nth(i)
            text = await link.text_content()
            if "Planter" in text:
                href = await link.get_attribute("href")
                await vpage.goto(FRONTEND + href, wait_until="networkidle")
                await vpage.wait_for_timeout(800)
                await vpage.evaluate("window.scrollBy(0, 300)")
                await vpage.wait_for_timeout(600)
                await vpage.evaluate("window.scrollTo(0, 0)")
                await vpage.wait_for_timeout(400)
                canvas = vpage.locator("canvas").first
                if await canvas.count() > 0:
                    box = await canvas.bounding_box()
                    if box:
                        await vpage.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                        await vpage.mouse.down()
                        await vpage.mouse.move(box["x"] + box["width"] / 2 + 150, box["y"] + box["height"] / 2 + 50, steps=20)
                        await vpage.mouse.up()
                        await vpage.wait_for_timeout(400)
                        await vpage.mouse.down()
                        await vpage.mouse.move(box["x"] + box["width"] / 2 - 80, box["y"] + box["height"] / 2 - 30, steps=15)
                        await vpage.mouse.up()
                        await vpage.wait_for_timeout(800)
                break

        # Search
        await vpage.goto(FRONTEND + "/", wait_until="networkidle")
        await vpage.wait_for_timeout(600)
        sinp = vpage.locator("input").first
        if await sinp.count() > 0:
            await sinp.click()
            await vpage.wait_for_timeout(300)
            await sinp.press_sequentially("mount", delay=80)
            await vpage.wait_for_timeout(1500)
            await sinp.fill("")
            await vpage.wait_for_timeout(400)
            await vpage.press("body", "Escape")
            await vpage.wait_for_timeout(800)

        await vctx.close()
        await browser.close()

    # Convert webm to GIF
    webm_files = sorted(OUT_DIR.glob("*.webm"), key=lambda p: p.stat().st_mtime, reverse=True)
    if webm_files:
        webm = webm_files[0]
        gif_path = OUT_DIR / "00-demo.gif"
        subprocess.run([
            "/usr/bin/ffmpeg", "-y", "-i", str(webm),
            "-vf", "fps=12,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            "-loop", "0", str(gif_path),
        ], check=True, capture_output=True)
        print(f"  ✓ 00-demo.gif ({gif_path.stat().st_size} bytes)")
        webm.unlink()

    print("\nAll captures done!")


async def main():
    await seed()
    await capture()


if __name__ == "__main__":
    asyncio.run(main())
