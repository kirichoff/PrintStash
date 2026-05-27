"""Ingest user's real 3D models, add metadata, capture screenshots."""
from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

API_BASE = "http://localhost:8000/api/v1"
API_KEY = "changeme"
FRONTEND = "http://nexus3d-frontend:3000"
OUT_DIR = Path("/tmp/screenshots")
OUT_DIR.mkdir(exist_ok=True)
MODELS_DIR = Path("/tmp/models")

DATASET = [
    {
        "file": "Cam Holder v4.stl",
        "name": "Camera Mount Bracket v4",
        "cat": "Functional/Mounts",
        "tags": "PLA,camera,mount,adjustable",
        "desc": "Articulated camera mounting bracket. Snap-fit joints, 1/4\" tripod thread. Print-in-place design.",
    },
    {
        "file": "Cam Holder v4(1).stl",
        "name": "Camera Mount Bracket v4 — gooseneck variant",
        "cat": "Functional/Mounts",
        "tags": "PLA,camera,gooseneck,flexible",
        "desc": "Gooseneck variant of the camera mount. Longer reach, segmented arm for flexible positioning.",
    },
    {
        "file": "Inverted Oloid.3mf",
        "name": "Inverted Oloid Sculpture",
        "cat": "Decorative/Sculptures",
        "tags": "PLA,math,oloid,desk_toy",
        "desc": "An inverted oloid — a fascinating mathematical shape that rolls in a perfectly smooth wobble. Great desk fidget.",
    },
    {
        "file": "doniczka-kotek.3mf",
        "name": "Cat Planter Pot",
        "cat": "Decorative/Planters",
        "tags": "PLA,planter,cat,cute",
        "desc": "Adorable cat-shaped planter pot with drainage. Fits small succulents. Low-poly aesthetic.",
    },
    {
        "file": "helm-wandhalter3mf.3mf",
        "name": "Helmet Wall Mount",
        "cat": "Functional/Organizers",
        "tags": "PETG,helmet,wall_mount,garage",
        "desc": "Wall-mounted helmet hanger. Holds bike / skate helmets securely. Hidden screw mounts. PETG recommended for load.",
    },
]


def api(method, path, **kw):
    headers = kw.pop("headers", {})
    headers.setdefault("X-API-Key", API_KEY)
    r = getattr(httpx, method)(f"{API_BASE}{path}", headers=headers, **kw)
    return r


async def seed():
    print("Clearing old data...")

    # Delete models
    models = api("get", "/models", params={"limit": 50}).json()
    for m in models:
        api("delete", f"/models/{m['id']}")
        await asyncio.sleep(0.3)

    # Delete tags
    for t in api("get", "/tags").json():
        api("delete", f"/tags/{t['id']}")

    # Delete categories (deepest first)
    cats = api("get", "/categories").json()
    for c in sorted(cats, key=lambda x: x.get("path", "").count("/"), reverse=True):
        api("delete", f"/categories/{c['id']}")

    # Clear thumbnails so they regenerate
    for f in os.listdir("/data/thumbs"):
        os.remove(f"/data/thumbs/{f}")

    # Ingest each model
    for item in DATASET:
        filepath = MODELS_DIR / item["file"]
        if not filepath.exists():
            print(f"  ✗ Missing: {filepath}")
            continue
        print(f"\n▶ {item['name']}")
        with open(filepath, "rb") as fh:
            files = {"file": (item["file"], fh, "application/octet-stream")}
            data = {
                "model_name": item["name"],
                "category": item["cat"],
                "tags": item["tags"],
            }
            r = api("post", "/ingest/model", files=files, data=data)
            print(f"  → {r.status_code}")
        await asyncio.sleep(5)  # wait for background thumbnail rendering

    # Update descriptions
    print("\n▶ Updating descriptions...")
    models = api("get", "/models", params={"limit": 50}).json()
    for m in models:
        for item in DATASET:
            if m["name"] == item["name"]:
                api("patch", f"/models/{m['id']}", json={"description": item["desc"]})
                print(f"  ✓ {m['name']}")

    print("\n✅ Seeding complete!")


async def capture():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
        )

        # ── 01 — Full Asset Grid ───────────────────────────────────
        print("\nCapturing screenshots...")
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page = await ctx.new_page()
        await page.goto(FRONTEND + "/", wait_until="networkidle")
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(OUT_DIR / "01-asset-grid.png"))
        print("  ✓ 01-asset-grid.png")

        # ── 02 — Category filter sidebar ──────────────────────────
        # Click first category link/filter
        cat_el = page.locator('a[href*="category="], button:has-text("Functional")').first
        if await cat_el.count() > 0:
            await cat_el.click()
            await page.wait_for_timeout(800)
            await page.screenshot(path=str(OUT_DIR / "02-category-filter.png"))
            print("  ✓ 02-category-filter.png")

        # ── 03 — Search ───────────────────────────────────────────
        await page.goto(FRONTEND + "/", wait_until="networkidle")
        await page.wait_for_timeout(500)
        search = page.locator("input").first
        if await search.count() > 0:
            await search.click()
            await search.press_sequentially("camera", delay=80)
            await page.wait_for_timeout(1000)
            await page.screenshot(path=str(OUT_DIR / "03-search.png"))
            print("  ✓ 03-search.png")

        # ── 04 — Model Detail (Camera Mount) ──────────────────────
        await search.fill("")
        await page.wait_for_timeout(300)
        await page.goto(FRONTEND + "/", wait_until="networkidle")
        await page.wait_for_timeout(600)
        links = page.locator('a[href^="/models/"]')
        count = await links.count()
        for i in range(count):
            link = links.nth(i)
            text = await link.text_content()
            if "Camera Mount" in text and "gooseneck" not in text.lower():
                href = await link.get_attribute("href")
                await page.goto(FRONTEND + href, wait_until="networkidle")
                await page.wait_for_timeout(800)
                await page.screenshot(path=str(OUT_DIR / "04-model-detail.png"))
                print("  ✓ 04-model-detail.png")
                break

        # ── 05 — 3D Viewer (Oloid) ────────────────────────────────
        await page.goto(FRONTEND + "/", wait_until="networkidle")
        await page.wait_for_timeout(500)
        links = page.locator('a[href^="/models/"]')
        count = await links.count()
        for i in range(count):
            link = links.nth(i)
            text = await link.text_content()
            if "Oloid" in text:
                href = await link.get_attribute("href")
                await page.goto(FRONTEND + href, wait_until="networkidle")
                await page.wait_for_timeout(1500)
                canvas = page.locator("canvas").first
                if await canvas.count() > 0:
                    box = await canvas.bounding_box()
                    if box:
                        await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                        await page.mouse.down()
                        await page.mouse.move(box["x"] + box["width"] / 2 + 180, box["y"] + box["height"] / 2 + 60, steps=20)
                        await page.mouse.up()
                        await page.wait_for_timeout(500)
                        await page.mouse.down()
                        await page.mouse.move(box["x"] + box["width"] / 2 - 100, box["y"] + box["height"] / 2 - 40, steps=15)
                        await page.mouse.up()
                        await page.wait_for_timeout(500)
                await page.screenshot(path=str(OUT_DIR / "05-3d-viewer.png"))
                print("  ✓ 05-3d-viewer.png")
                break

        await ctx.close()

        # ── 06 — Demo GIF ─────────────────────────────────────────
        print("\nRecording demo GIF...")
        vctx = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            device_scale_factor=1,
            record_video_dir=str(OUT_DIR),
            record_video_size={"width": 1280, "height": 720},
        )
        vpage = await vctx.new_page()

        await vpage.goto(FRONTEND + "/", wait_until="networkidle")
        await vpage.wait_for_timeout(1200)
        await vpage.evaluate("window.scrollBy(0, 200)")
        await vpage.wait_for_timeout(600)
        await vpage.evaluate("window.scrollTo(0, 0)")
        await vpage.wait_for_timeout(500)

        # Click first model link
        links = vpage.locator('a[href^="/models/"]')
        count = await links.count()
        if count > 0:
            first_href = await links.first.get_attribute("href")
            await vpage.goto(FRONTEND + first_href, wait_until="networkidle")
            await vpage.wait_for_timeout(1000)
            await vpage.evaluate("window.scrollBy(0, 300)")
            await vpage.wait_for_timeout(600)
            await vpage.evaluate("window.scrollTo(0, 0)")
            await vpage.wait_for_timeout(500)

            canvas = vpage.locator("canvas").first
            if await canvas.count() > 0:
                box = await canvas.bounding_box()
                if box:
                    await vpage.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    await vpage.mouse.down()
                    await vpage.mouse.move(box["x"] + box["width"] / 2 + 150, box["y"] + box["height"] / 2 + 50, steps=20)
                    await vpage.mouse.up()
                    await vpage.wait_for_timeout(500)
                    await vpage.mouse.down()
                    await vpage.mouse.move(box["x"] + box["width"] / 2 - 80, box["y"] + box["height"] / 2 - 30, steps=12)
                    await vpage.mouse.up()
                    await vpage.wait_for_timeout(900)

        # Search
        await vpage.goto(FRONTEND + "/", wait_until="networkidle")
        await vpage.wait_for_timeout(600)
        sinp = vpage.locator("input").first
        if await sinp.count() > 0:
            await sinp.click()
            await vpage.wait_for_timeout(300)
            await sinp.press_sequentially("helmet", delay=80)
            await vpage.wait_for_timeout(1500)
            await sinp.fill("")
            await vpage.wait_for_timeout(400)
            await vpage.press("body", "Escape")
            await vpage.wait_for_timeout(800)

        await vctx.close()
        await browser.close()

    # Convert to GIF
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
