"""Capture 3D viewer screenshot for Planter Pot model."""
import asyncio
import subprocess
from pathlib import Path

from playwright.async_api import async_playwright

FRONTEND = "http://nexus3d-frontend:3000"
OUT_DIR = Path("/tmp/screenshots")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu"],
        )
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
        )
        page = await ctx.new_page()

        # Find Planter Pot model ID
        import httpx
        models = httpx.get("http://localhost:8000/api/v1/models", params={"q": "Planter"}).json()
        if models:
            model = models[0]
            mid = model["id"]
            print(f"Navigating to Planter Pot (id={mid})...")
            await page.goto(FRONTEND + f"/models/{mid}", wait_until="networkidle")
            await page.wait_for_timeout(1500)

            # Try to find and rotate the 3D canvas
            canvas = page.locator("canvas").first
            if await canvas.count() > 0:
                box = await canvas.bounding_box()
                if box:
                    print(f"  Canvas found at {box}")
                    await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    await page.mouse.down()
                    await page.mouse.move(
                        box["x"] + box["width"] / 2 + 200,
                        box["y"] + box["height"] / 2 + 60,
                        steps=20,
                    )
                    await page.mouse.up()
                    await page.wait_for_timeout(600)
                    await page.mouse.down()
                    await page.mouse.move(
                        box["x"] + box["width"] / 2 - 100,
                        box["y"] + box["height"] / 2 - 40,
                        steps=15,
                    )
                    await page.mouse.up()
                    await page.wait_for_timeout(600)
                await page.screenshot(path=str(OUT_DIR / "05-3d-viewer.png"))
                print("  ✓ 05-3d-viewer.png")
            else:
                print("  ✗ No canvas found")
                await page.screenshot(path=str(OUT_DIR / "05-model-page.png"))

        await ctx.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
