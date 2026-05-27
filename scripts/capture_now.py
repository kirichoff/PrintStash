"""Capture screenshots only (data already seeded)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from playwright.async_api import async_playwright

FRONTEND = "http://nexus3d-frontend:3000"
OUT_DIR = Path("/tmp/screenshots")
OUT_DIR.mkdir(exist_ok=True)

import asyncio


async def capture():
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

        # ── 02 — Category filter ────────────────────────────────────
        cat_links = page.locator('a[href*="category="], button')
        found = False
        for text in ["Cable", "Functional", "Brackets", "Mounts"]:
            btn = page.locator(f'button:has-text("{text}")')
            if await btn.count() > 0:
                await btn.first.click()
                await page.wait_for_timeout(800)
                await page.screenshot(path=str(OUT_DIR / "02-category-filter.png"))
                print("  ✓ 02-category-filter.png")
                found = True
                break
        if not found:
            print("  ⚠ No category filter found, taking fallback screenshot")
            await page.screenshot(path=str(OUT_DIR / "02-category-filter.png"))

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

        # ── 04 — Model Detail (GPU Anti-Sag Bracket) ────────────────
        await page.goto(FRONTEND + "/", wait_until="networkidle")
        await page.wait_for_timeout(600)
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

        # ── 05 — 3D Viewer (Planter Pot) ────────────────────────────
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
                await page.wait_for_timeout(1500)
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

        # ── 06 — Setup Wizard (first-run UX) ────────────────────────
        await page.goto(FRONTEND + "/setup", wait_until="networkidle")
        await page.wait_for_timeout(800)
        await page.screenshot(path=str(OUT_DIR / "06-setup-wizard.png"))
        print("  ✓ 06-setup-wizard.png")

        # ── 07 — Login Page ─────────────────────────────────────────
        await page.goto(FRONTEND + "/login", wait_until="networkidle")
        await page.wait_for_timeout(600)
        await page.screenshot(path=str(OUT_DIR / "07-login-page.png"))
        print("  ✓ 07-login-page.png")

        await ctx.close()

        # ── 08 — Demo GIF ───────────────────────────────────────────
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
            await vpage.keyboard.press("Escape")
            await vpage.wait_for_timeout(800)

        await vctx.close()
        await browser.close()

    # Convert webm to GIF
    webm_files = sorted(OUT_DIR.glob("*.webm"), key=lambda p: p.stat().st_mtime, reverse=True)
    if webm_files:
        webm = webm_files[0]
        gif_path = OUT_DIR / "00-demo.gif"
        result = subprocess.run([
            "/usr/bin/ffmpeg", "-y", "-i", str(webm),
            "-vf", "fps=12,scale=640:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            "-loop", "0", str(gif_path),
        ], capture_output=True)
        if result.returncode == 0:
            print(f"  ✓ 00-demo.gif ({gif_path.stat().st_size} bytes)")
        else:
            print(f"  ⚠ ffmpeg failed: {result.stderr.decode()[:200]}")
        webm.unlink()
    else:
        print("  ⚠ No webm video produced")

    print("\nAll captures done!")


if __name__ == "__main__":
    asyncio.run(capture())
