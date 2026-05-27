"""Re-ingest to regenerate thumbnails now that networkx is present, then capture."""
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
MODELS_DIR = Path("/tmp/models")

DATASET = [
    {"file": "Cam Holder v4.stl", "name": "Camera Mount Bracket v4", "cat": "Functional/Mounts", "tags": "PLA,camera,mount", "desc": "Articulated camera mount. Snap-fit joints, 1/4\" tripod thread."},
    {"file": "Cam Holder v4(1).stl", "name": "Camera Mount Bracket v4 Gooseneck", "cat": "Functional/Mounts", "tags": "PLA,camera,gooseneck", "desc": "Gooseneck camera mount variant. Longer reach, flexible arm."},
    {"file": "Inverted Oloid.3mf", "name": "Inverted Oloid Sculpture", "cat": "Decorative/Sculptures", "tags": "PLA,math,oloid,desk_toy", "desc": "An inverted oloid — a fascinating mathematical form. Smooth rolling wobble. Great desk fidget."},
    {"file": "doniczka-kotek.3mf", "name": "Cat Planter Pot", "cat": "Decorative/Planters", "tags": "PLA,planter,cat,cute", "desc": "Cat-shaped planter pot with drainage. Fits succulents. Low-poly aesthetic."},
    {"file": "helm-wandhalter3mf.3mf", "name": "Helmet Wall Mount", "cat": "Functional/Organizers", "tags": "PETG,helmet,wall_mount,garage", "desc": "Wall-mounted helmet hanger. Hides screws. PETG for load."},
]


def api(method, path, **kw):
    headers = kw.pop("headers", {})
    headers.setdefault("X-API-Key", API_KEY)
    r = getattr(httpx, method)(f"{API_BASE}{path}", headers=headers, **kw)
    return r


async def clear_and_reingest():
    print("Clearing old data...")
    models = api("get", "/models", params={"limit": 50}).json()
    for m in models:
        api("delete", f"/models/{m['id']}")
        await asyncio.sleep(0.3)

    for t in api("get", "/tags").json():
        api("delete", f"/tags/{t['id']}")

    cats = api("get", "/categories").json()
    for c in sorted(cats, key=lambda x: x.get("path", "").count("/"), reverse=True):
        api("delete", f"/categories/{c['id']}")

    for f in os.listdir("/data/thumbs"):
        os.remove(f"/data/thumbs/{f}")

    for item in DATASET:
        fp = MODELS_DIR / item["file"]
        if not fp.exists():
            print(f"  ✗ Missing: {fp}")
            continue
        print(f"▶ {item['name']}")
        with open(fp, "rb") as fh:
            r = api("post", "/ingest/model", files={
                "file": (item["file"], fh, "application/octet-stream"),
            }, data={
                "model_name": item["name"],
                "category": item["cat"],
                "tags": item["tags"],
            })
        print(f"  → {r.status_code}")
        await asyncio.sleep(6)

    print("\n▶ Descriptions...")
    models = api("get", "/models", params={"limit": 50}).json()
    for m in models:
        for item in DATASET:
            if m["name"] == item["name"]:
                api("patch", f"/models/{m['id']}", json={"description": item["desc"]})
                print(f"  ✓ {m['name']}")
    print("✅ Done")


async def capture():
    # Remove old captures
    for f in OUT_DIR.glob("*"):
        f.unlink()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])

        # ── 01 Grid ──────────────────────────────────────────────
        print("\nCapturing...")
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page = await ctx.new_page()
        await page.goto(FRONTEND + "/", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        await page.screenshot(path=str(OUT_DIR / "01-asset-grid.png"))
        print("  ✓ 01-asset-grid.png")

        # ── 02 Category filter ──────────────────────────────────
        cat_btn = page.locator('a[href*="category="], button:has-text("Functional"), [role="button"]:has-text("Functional")').first
        if await cat_btn.count() > 0:
            await cat_btn.click()
            await page.wait_for_timeout(800)
            await page.screenshot(path=str(OUT_DIR / "02-category-filter.png"))
            print("  ✓ 02-category-filter.png")

        # ── 03 Search ───────────────────────────────────────────
        await page.goto(FRONTEND + "/", wait_until="networkidle")
        await page.wait_for_timeout(500)
        search = page.locator("input").first
        if await search.count() > 0:
            await search.click()
            await search.press_sequentially("helmet", delay=80)
            await page.wait_for_timeout(1200)
            await page.screenshot(path=str(OUT_DIR / "03-search.png"))
            print("  ✓ 03-search.png")

        # ── 04 Model Detail ─────────────────────────────────────
        await search.fill("")
        await page.wait_for_timeout(300)
        await page.goto(FRONTEND + "/", wait_until="networkidle")
        await page.wait_for_timeout(600)
        links = page.locator('a[href^="/models/"]')
        count = await links.count()
        for i in range(count):
            text = await links.nth(i).text_content()
            if "Oloid" in text:
                href = await links.nth(i).get_attribute("href")
                await page.goto(FRONTEND + href, wait_until="networkidle")
                await page.wait_for_timeout(2000)

                # Wait for the viewer canvas to actually load
                canvas = page.locator("canvas").first
                if await canvas.count() > 0:
                    # Wait a bit more for the STL to load
                    await page.wait_for_timeout(3000)
                    box = await canvas.bounding_box()
                    if box:
                        await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                        await page.mouse.down()
                        await page.mouse.move(box["x"] + box["width"] / 2 + 180, box["y"] + box["height"] / 2 + 60, steps=20)
                        await page.mouse.up()
                        await page.wait_for_timeout(600)
                        await page.mouse.down()
                        await page.mouse.move(box["x"] + box["width"] / 2 - 100, box["y"] + box["height"] / 2 - 50, steps=15)
                        await page.mouse.up()
                        await page.wait_for_timeout(600)

                await page.screenshot(path=str(OUT_DIR / "04-3d-viewer.png"))
                print("  ✓ 04-3d-viewer.png")
                break

        # ── 05 Model detail page (metadata) ─────────────────────
        await page.goto(FRONTEND + "/", wait_until="networkidle")
        await page.wait_for_timeout(500)
        links = page.locator('a[href^="/models/"]')
        count = await links.count()
        for i in range(count):
            text = await links.nth(i).text_content()
            if "Camera Mount" in text and "Gooseneck" not in text:
                href = await links.nth(i).get_attribute("href")
                await page.goto(FRONTEND + href, wait_until="networkidle")
                await page.wait_for_timeout(1500)
                await page.screenshot(path=str(OUT_DIR / "05-model-detail.png"))
                print("  ✓ 05-model-detail.png")
                break

        await ctx.close()

        # ── GIF ─────────────────────────────────────────────────
        print("\nRecording GIF...")
        vctx = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=str(OUT_DIR),
            record_video_size={"width": 1280, "height": 720},
        )
        vp = await vctx.new_page()

        # Grid browse
        await vp.goto(FRONTEND + "/", wait_until="networkidle")
        await vp.wait_for_timeout(1200)
        await vp.evaluate("window.scrollBy(0, 200)")
        await vp.wait_for_timeout(600)
        await vp.evaluate("window.scrollTo(0, 0)")
        await vp.wait_for_timeout(500)

        # Click first model → show detail + viewer
        links = vp.locator('a[href^="/models/"]')
        if await links.count() > 0:
            href = await links.first.get_attribute("href")
            await vp.goto(FRONTEND + href, wait_until="networkidle")
            await vp.wait_for_timeout(2000)
            await vp.evaluate("window.scrollBy(0, 300)")
            await vp.wait_for_timeout(600)
            await vp.evaluate("window.scrollTo(0, 0)")
            await vp.wait_for_timeout(500)

            canvas = vp.locator("canvas").first
            if await canvas.count() > 0:
                await vp.wait_for_timeout(2000)
                box = await canvas.bounding_box()
                if box:
                    await vp.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    await vp.mouse.down()
                    await vp.mouse.move(box["x"] + box["width"] / 2 + 150, box["y"] + box["height"] / 2 + 60, steps=20)
                    await vp.mouse.up()
                    await vp.wait_for_timeout(500)
                    await vp.mouse.down()
                    await vp.mouse.move(box["x"] + box["width"] / 2 - 80, box["y"] + box["height"] / 2 - 40, steps=12)
                    await vp.mouse.up()
                    await vp.wait_for_timeout(900)

        # Search
        await vp.goto(FRONTEND + "/", wait_until="networkidle")
        await vp.wait_for_timeout(600)
        sinp = vp.locator("input").first
        if await sinp.count() > 0:
            await sinp.click()
            await vp.wait_for_timeout(300)
            await sinp.press_sequentially("planter", delay=80)
            await vp.wait_for_timeout(1500)
            await sinp.fill("")
            await vp.wait_for_timeout(400)
            await vp.press("body", "Escape")
            await vp.wait_for_timeout(800)

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

    print("\nAll done!")


async def main():
    await clear_and_reingest()
    await capture()


if __name__ == "__main__":
    asyncio.run(main())
