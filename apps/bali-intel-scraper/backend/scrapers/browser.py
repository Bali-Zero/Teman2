"""
Browser automation with Playwright and stealth mode.

Provides:
- Stealth plugins to avoid bot detection
- Browser context pooling
- Automatic retry and error recovery
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, List, Optional, Any
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config.settings import settings
from backend.core.logger import get_logger, LogAction
from backend.core.rate_limiter import limit_scrape_request

logger = get_logger(__name__, component="browser")


@dataclass
class BrowserConfig:
    """Browser configuration."""

    headless: bool = True
    browser_type: str = "chromium"
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: Optional[str] = None
    locale: str = "en-US"
    timezone: str = "America/New_York"

    # Stealth options
    stealth_enabled: bool = True
    webdriver_patch: bool = True
    chrome_runtime_patch: bool = True
    navigator_patch: bool = True


class StealthPlugin:
    """Apply stealth patches to avoid bot detection."""

    @staticmethod
    def get_webdriver_patch() -> str:
        """Patch to hide webdriver property."""
        return """
        () => {
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        }
        """

    @staticmethod
    def get_chrome_runtime_patch() -> str:
        """Patch to fix chrome runtime."""
        return """
        () => {
            window.chrome = {
                runtime: {}
            };
        }
        """

    @staticmethod
    def get_navigator_patch() -> str:
        """Patch navigator properties."""
        return """
        () => {
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        }
        """

    @staticmethod
    def get_permissions_patch() -> str:
        """Patch permissions API."""
        return """
        () => {
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        }
        """

    @staticmethod
    def get_canvas_noise_patch() -> str:
        """Add subtle noise to canvas fingerprint."""
        return """
        () => {
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            
            HTMLCanvasElement.prototype.toDataURL = function(type) {
                const context = this.getContext('2d');
                if (context) {
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    // Add subtle noise
                    for (let i = 0; i < imageData.data.length; i += 4) {
                        imageData.data[i] = imageData.data[i] + (Math.random() < 0.5 ? -1 : 1);
                    }
                    context.putImageData(imageData, 0, 0);
                }
                return originalToDataURL.apply(this, arguments);
            };
        }
        """

    @classmethod
    def get_all_scripts(cls) -> List[str]:
        """Get all stealth scripts."""
        return [
            cls.get_webdriver_patch(),
            cls.get_chrome_runtime_patch(),
            cls.get_navigator_patch(),
            cls.get_permissions_patch(),
            cls.get_canvas_noise_patch(),
        ]


class BrowserManager:
    """Manages browser instances and contexts."""

    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig(headless=settings.scraping.headless)
        self._browser: Optional[Browser] = None
        self._playwright = None
        self._context_pool: List[BrowserContext] = []
        self._max_contexts = settings.scraping.max_concurrent_browsers
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize browser instance."""
        if self._browser is not None:
            return

        logger.info(
            "Initializing browser",
            action=LogAction.START,
            metadata={
                "browser_type": self.config.browser_type,
                "headless": self.config.headless,
            },
        )

        try:
            self._playwright = await async_playwright().start()

            browser_class = getattr(self._playwright, self.config.browser_type)

            self._browser = await browser_class.launch(
                headless=self.config.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-site-isolation-trials",
                ],
            )

            logger.info("Browser initialized", action=LogAction.END)

        except Exception as e:
            logger.error(
                "Browser initialization failed",
                action=LogAction.ERROR,
                metadata={"error": str(e)},
            )
            raise

    async def close(self) -> None:
        """Close browser and cleanup."""
        logger.info("Closing browser", action=LogAction.START)

        # Close all contexts
        for context in self._context_pool:
            try:
                await context.close()
            except Exception:
                pass
        self._context_pool.clear()

        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        logger.info("Browser closed", action=LogAction.END)

    async def create_context(
        self,
        proxy: Optional[Dict[str, str]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> BrowserContext:
        """Create a new browser context with stealth settings."""
        if self._browser is None:
            await self.initialize()

        context_options = {
            "viewport": {
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
            "locale": self.config.locale,
            "timezone_id": self.config.timezone,
        }

        if proxy:
            context_options["proxy"] = proxy

        if extra_headers:
            context_options["extra_http_headers"] = extra_headers

        context = await self._browser.new_context(**context_options)

        # Apply stealth patches
        if self.config.stealth_enabled:
            for script in StealthPlugin.get_all_scripts():
                await context.add_init_script(script)

        return context

    @asynccontextmanager
    async def get_context(
        self,
        proxy: Optional[Dict[str, str]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[BrowserContext, None]:
        """Get a context from pool or create new one."""
        context = None

        try:
            # Try to reuse from pool
            async with self._lock:
                if self._context_pool:
                    context = self._context_pool.pop()

            if context is None:
                context = await self.create_context(proxy, extra_headers)

            yield context

        finally:
            if context:
                # Return to pool if not full, otherwise close
                async with self._lock:
                    if len(self._context_pool) < self._max_contexts:
                        # Clear cookies and storage for reuse
                        await context.clear_cookies()
                        self._context_pool.append(context)
                    else:
                        await context.close()

    @asynccontextmanager
    async def get_page(
        self,
        url: Optional[str] = None,
        proxy: Optional[Dict[str, str]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[Page, None]:
        """Get a page with automatic cleanup."""
        async with self.get_context(proxy, extra_headers) as context:
            page = await context.new_page()

            try:
                if url:
                    # Apply rate limiting
                    parsed = urlparse(url)
                    await limit_scrape_request(parsed.netloc)

                    response = await page.goto(
                        url,
                        wait_until="networkidle",
                        timeout=settings.scraping.page_load_timeout * 1000,
                    )

                    if response.status >= 400:
                        raise BrowserError(f"HTTP {response.status} for {url}")

                yield page

            finally:
                await page.close()

    async def get_page_content(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
        proxy: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Get page content with metadata."""
        async with self.get_page(url, proxy) as page:
            if wait_for_selector:
                await page.wait_for_selector(wait_for_selector, timeout=10000)

            content = await page.content()
            title = await page.title()

            return {"url": url, "title": title, "content": content, "status": 200}


class BrowserError(Exception):
    """Browser operation error."""

    pass


# Global browser manager instance
browser_manager = BrowserManager()


async def init_browser() -> None:
    """Initialize global browser manager."""
    await browser_manager.initialize()


async def close_browser() -> None:
    """Close global browser manager."""
    await browser_manager.close()


__all__ = [
    "BrowserManager",
    "BrowserConfig",
    "StealthPlugin",
    "BrowserError",
    "browser_manager",
    "init_browser",
    "close_browser",
]
