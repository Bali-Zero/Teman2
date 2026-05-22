#!/usr/bin/env python3
"""Render 9 HTML slides to 1080x1350 PNG via Playwright."""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path("/Users/nuzantara/Desktop/nuzantara/apps/war-room/output/carousel/2026-05-22-permenkumham-22-2024-kitap/slides")

async def render_all():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 1080, "height": 1350},
            device_scale_factor=1,
        )

        for i in range(1, 10):
            html = ROOT / f"{i}.html"
            if not html.exists():
                print(f"  SKIP {html.name} (not found)")
                continue
            png = ROOT / f"{i}.png"
            page = await ctx.new_page()
            await page.goto(f"file://{html}")
            await page.evaluate("() => document.fonts.ready")
            await page.wait_for_timeout(800)
            await page.screenshot(path=str(png), full_page=False, omit_background=False)
            await page.close()
            print(f"  rendered {png.name}")

        await browser.close()
    print("Done")

asyncio.run(render_all())
