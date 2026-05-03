"""
Browser automation with Playwright and stealth mode.

Provides:
- Stealth plugins to avoid bot detection
- Browser context pooling
- Automatic retry and error recovery
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from browser_core.stealth import StealthPlugin

logger = logging.getLogger(__name__)

# Type alias for injectable rate limiter
RateLimiter = Callable[[str], Awaitable[None]]


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

    # Pool / timeout options (previously read from settings)
    max_contexts: int = 5
    page_load_timeout_ms: int = 30000


class BrowserError(Exception):
    """Browser operation error."""

    pass


class BrowserManager:
    """Manages browser instances and contexts."""

    def __init__(
        self,
        config: Optional[BrowserConfig] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ):
        self.config = config or BrowserConfig()
        self._browser: Optional[Browser] = None
        self._playwright = None
        self._context_pool: List[BrowserContext] = []
        self._max_contexts = self.config.max_contexts
        self._lock = asyncio.Lock()
        self._rate_limiter = rate_limiter

    async def initialize(self) -> None:
        """Initialize browser instance."""
        if self._browser is not None:
            return

        logger.info(
            "Initializing browser: browser_type=%s, headless=%s",
            self.config.browser_type,
            self.config.headless,
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

            logger.info("Browser initialized")

        except Exception as e:
            logger.error("Browser initialization failed: %s", e)
            raise

    async def close(self) -> None:
        """Close browser and cleanup."""
        logger.info("Closing browser")

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

        logger.info("Browser closed")

    async def create_context(
        self,
        proxy: Optional[Dict[str, str]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> BrowserContext:
        """Create a new browser context with stealth settings."""
        if self._browser is None:
            await self.initialize()

        context_options: Dict[str, Any] = {
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
                    if self._rate_limiter is not None:
                        await self._rate_limiter(parsed.netloc)

                    response = await page.goto(
                        url,
                        wait_until="networkidle",
                        timeout=self.config.page_load_timeout_ms,
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
