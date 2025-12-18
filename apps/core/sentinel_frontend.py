"""
SENTINEL FRONTEND - Synthetic User Monitoring
Part of the Zantara Full-Stack Observability Suite.

This script acts as a "Synthetic User" that periodically checks the health
of the Frontend application by performing real browser interactions.

It complements the Backend Sentinel by verifying that the UI is:
1. Reachable
2. Functional (Login works)
3. Connected (Chat works)

Usage:
    python apps/core/sentinel_frontend.py --url https://nuzantara-webapp.fly.dev
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime

from playwright.async_api import async_playwright

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("sentinel.frontend")


class FrontendSentinel:
    def __init__(self, base_url: str, headless: bool = True):
        self.base_url = base_url.rstrip("/")
        self.headless = headless
        self.test_user = {"email": "zero@balizero.com", "pin": "010719"}

    async def run_health_check(self) -> bool:
        """Run the full health check suite"""
        logger.info(f"🚀 Starting Frontend Sentinel check for {self.base_url}")

        async with async_playwright() as p:
            browser = await p.webkit.launch(headless=self.headless)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                # 1. Check Reachability
                await self._check_reachability(page)

                # 2. Check Login Flow
                await self._check_login(page)

                # 3. Check Chat Interface
                await self._check_chat_load(page)

                logger.info("✅ ALL FRONTEND SYSTEMS NOMINAL")
                return True

            except Exception as e:
                logger.error(f"❌ Frontend Sentinel Failed: {e}")
                # Take screenshot on failure
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                await page.screenshot(path=f"sentinel_failure_{timestamp}.png")
                logger.info(
                    f"📸 Failure screenshot saved to sentinel_failure_{timestamp}.png"
                )
                return False
            finally:
                await browser.close()

    async def _check_reachability(self, page):
        """Verify the site loads"""
        logger.info("📡 Checking reachability...")
        response = await page.goto(self.base_url, timeout=10000)
        if not response or response.status >= 400:
            raise Exception(
                f"Site unreachable. Status: {response.status if response else 'None'}"
            )
        logger.info("✅ Site is reachable")

    async def _check_login(self, page):
        """Verify login functionality"""
        logger.info("🔑 Checking login flow...")

        # Check if we are already on chat (if session persisted, unlikely in incognito)
        if "/chat" in page.url:
            logger.info("ℹ️ Already logged in")
            return

        # Wait for login form
        await page.wait_for_selector("input[type='email']", timeout=5000)

        # Fill credentials
        await page.fill("input[type='email']", self.test_user["email"])
        await page.fill("input[type='password']", self.test_user["pin"])

        # Click login
        # Look for button with text "Sign in" or similar
        login_button = page.get_by_role("button", name="Sign in")
        if not await login_button.count():
            login_button = page.get_by_role("button", name="Login")

        await login_button.click()

        # Wait for navigation to chat
        try:
            await page.wait_for_url("**/chat", timeout=10000)
            logger.info("✅ Login successful")
        except Exception:
            raise Exception("Login failed - did not redirect to /chat")

    async def _check_chat_load(self, page):
        """Verify chat interface loads"""
        logger.info("💬 Checking chat interface...")

        # Check for input area
        await page.wait_for_selector("textarea", timeout=5000)

        # Check for Zantara logo or header
        if await page.get_by_text("Zantara").count() > 0:
            logger.info("✅ Chat interface loaded")
        else:
            logger.warning("⚠️ Chat interface loaded but 'Zantara' text not found")


def main():
    parser = argparse.ArgumentParser(description="Sentinel Frontend Health Check")
    parser.add_argument(
        "--url", default="https://nuzantara-webapp.fly.dev", help="Frontend URL to test"
    )
    parser.add_argument(
        "--visible", action="store_true", help="Run browser in visible mode"
    )
    args = parser.parse_args()

    sentinel = FrontendSentinel(base_url=args.url, headless=not args.visible)
    success = asyncio.run(sentinel.run_health_check())

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
