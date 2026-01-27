#!/usr/bin/env python3
import asyncio
import argparse
import json
from pathlib import Path
from playwright.async_api import async_playwright

# Configuration
PROJECT_ROOT = Path(__file__).parent.parent
STAGING_DIR = PROJECT_ROOT / "data" / "scout_staging"
SCREENSHOT_DIR = STAGING_DIR / "screenshots"

STAGING_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


async def scout_url(url: str, output_name: str = None, headless: bool = True):
    """
    Scouts a URL using a real browser to bypass basic blocks.
    Extracts main content and takes a screenshot.
    """
    print(f"🕵️  Scout engaging target: {url}")

    async with async_playwright() as p:
        # Launch browser with stealth-like args using WebKit (more stable on macOS)
        try:
            browser = await p.chromium.launch(headless=headless)
        except Exception:
            print("   ⚠️ Chromium failed, switching to WebKit...")
            browser = await p.webkit.launch(headless=headless)

        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        page = await context.new_page()

        try:
            # Go to page and wait for network to settle (useful for SPAs)
            await page.goto(url, wait_until="networkidle", timeout=60000)
            print("   Target acquired. Rendering...")

            # Extract basic info
            title = await page.title()
            content = await page.evaluate("() => document.body.innerText")

            # Generate filename
            if not output_name:
                import time

                timestamp = int(time.time())
                safe_title = "".join([c if c.isalnum() else "_" for c in title])[:30]
                output_name = f"scout_{timestamp}_{safe_title}"

            # Screenshot
            screenshot_path = SCREENSHOT_DIR / f"{output_name}.png"
            await page.screenshot(path=str(screenshot_path))
            print(f"   📸 Proof captured: {screenshot_path.relative_to(PROJECT_ROOT)}")

            # Save Data
            data = {
                "url": url,
                "title": title,
                "content_preview": content[:200],
                "full_content": content,
                "scouted_at": str(screenshot_path),
            }

            json_path = STAGING_DIR / f"{output_name}.json"
            with open(json_path, "w") as f:
                json.dump(data, f, indent=2)

            print(f"   💾 Intelligence stored: {json_path.relative_to(PROJECT_ROOT)}")
            return data

        except Exception as e:
            print(f"   ❌ Mission failed: {e}")
            return None
        finally:
            await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scout Agent: Visual Extraction")
    parser.add_argument("url", help="Target URL to scout")
    parser.add_argument("--name", help="Custom output name", default=None)
    parser.add_argument(
        "--visible", help="Run with visible browser", action="store_true"
    )

    args = parser.parse_args()

    asyncio.run(scout_url(args.url, args.name, headless=not args.visible))
