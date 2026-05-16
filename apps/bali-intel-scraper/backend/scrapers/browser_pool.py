"""
Browser connection pool for efficient resource reuse.

Manages a pool of browser contexts/pages to minimize
browser startup overhead.
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import AsyncGenerator, Dict, Optional, Set
from urllib.parse import urlparse

from playwright.async_api import BrowserContext, Page

from backend.core.logger import get_logger, LogAction
from backend.scrapers.browser import browser_manager

logger = get_logger(__name__, component="browser_pool")


class PoolItemStatus(Enum):
    """Status of pool items."""

    AVAILABLE = "available"
    IN_USE = "in_use"
    CLEANING = "cleaning"
    BROKEN = "broken"


@dataclass
class PooledContext:
    """Pooled browser context."""

    context: BrowserContext
    created_at: float
    use_count: int = 0
    status: PoolItemStatus = PoolItemStatus.AVAILABLE
    last_host: Optional[str] = None


@dataclass
class PooledPage:
    """Pooled page."""

    page: Page
    context_id: str
    created_at: float
    use_count: int = 0
    status: PoolItemStatus = PoolItemStatus.AVAILABLE


class BrowserPool:
    """Pool for browser contexts and pages."""

    def __init__(
        self,
        max_contexts: int = 5,
        max_pages_per_context: int = 3,
        max_age_seconds: float = 300,
        max_uses: int = 50,
    ):
        self.max_contexts = max_contexts
        self.max_pages_per_context = max_pages_per_context
        self.max_age_seconds = max_age_seconds
        self.max_uses = max_uses

        self._contexts: Dict[str, PooledContext] = {}
        self._pages: Dict[str, PooledPage] = {}
        self._context_pages: Dict[str, Set[str]] = {}

        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._counter = 0

    async def initialize(self) -> None:
        """Initialize the pool."""
        await browser_manager.initialize()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info(
            "Browser pool initialized",
            action=LogAction.START,
            metadata={
                "max_contexts": self.max_contexts,
                "max_pages_per_context": self.max_pages_per_context,
            },
        )

    async def close(self) -> None:
        """Close the pool and all resources."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        async with self._lock:
            # Close all pages
            for _, pooled_page in list(self._pages.items()):
                try:
                    await pooled_page.page.close()
                except Exception:
                    pass
            self._pages.clear()

            # Close all contexts
            for _, pooled_context in list(self._contexts.items()):
                try:
                    await pooled_context.context.close()
                except Exception:
                    pass
            self._contexts.clear()
            self._context_pages.clear()

        logger.info("Browser pool closed", action=LogAction.END)

    async def _create_context(self) -> str:
        """Create a new browser context."""
        context = await browser_manager.create_context()

        self._counter += 1
        context_id = f"ctx_{self._counter}"

        self._contexts[context_id] = PooledContext(
            context=context, created_at=asyncio.get_event_loop().time()
        )
        self._context_pages[context_id] = set()

        return context_id

    async def _get_or_create_context(self, host: Optional[str] = None) -> str:
        """Get existing context or create new one."""
        async with self._lock:
            # Try to find available context
            for context_id, pooled in self._contexts.items():
                if (
                    pooled.status == PoolItemStatus.AVAILABLE
                    and len(self._context_pages[context_id])
                    < self.max_pages_per_context
                ):
                    # Check if context is still valid
                    age = asyncio.get_event_loop().time() - pooled.created_at
                    if age < self.max_age_seconds and pooled.use_count < self.max_uses:
                        pooled.status = PoolItemStatus.IN_USE
                        pooled.use_count += 1
                        pooled.last_host = host
                        return context_id

            # Create new context if under limit
            if len(self._contexts) < self.max_contexts:
                context_id = await self._create_context()
                self._contexts[context_id].status = PoolItemStatus.IN_USE
                self._contexts[context_id].use_count += 1
                self._contexts[context_id].last_host = host
                return context_id

            # Wait for available context
            return None

    async def _create_page(self, context_id: str) -> str:
        """Create a new page in context."""
        pooled_context = self._contexts[context_id]
        page = await pooled_context.context.new_page()

        self._counter += 1
        page_id = f"page_{self._counter}"

        self._pages[page_id] = PooledPage(
            page=page, context_id=context_id, created_at=asyncio.get_event_loop().time()
        )
        self._context_pages[context_id].add(page_id)

        return page_id

    @asynccontextmanager
    async def acquire_page(
        self, url: Optional[str] = None, timeout: float = 30.0
    ) -> AsyncGenerator[Page, None]:
        """
        Acquire a page from the pool.

        Args:
            url: URL to navigate to (optional)
            timeout: Maximum time to wait for available page
        """
        host = None
        if url:
            parsed = urlparse(url)
            host = parsed.netloc

        page_id = None
        context_id = None
        start_time = asyncio.get_event_loop().time()

        try:
            # Wait for available context/page
            while True:
                context_id = await self._get_or_create_context(host)

                if context_id:
                    async with self._lock:
                        page_id = await self._create_page(context_id)
                        self._pages[page_id].status = PoolItemStatus.IN_USE
                    break

                # Check timeout
                if asyncio.get_event_loop().time() - start_time > timeout:
                    raise TimeoutError("Could not acquire page from pool")

                await asyncio.sleep(0.1)

            page = self._pages[page_id].page

            # Navigate if URL provided
            if url:
                await page.goto(url, wait_until="domcontentloaded")

            yield page

        finally:
            if page_id:
                async with self._lock:
                    pooled_page = self._pages.get(page_id)
                    if pooled_page:
                        # Clear cookies and storage
                        try:
                            await pooled_page.page.evaluate("localStorage.clear()")
                            await pooled_page.page.context.clear_cookies()
                        except Exception:
                            pass

                        pooled_page.status = PoolItemStatus.AVAILABLE
                        pooled_page.use_count += 1

    async def _cleanup_loop(self) -> None:
        """Periodic cleanup of old resources."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._cleanup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "Cleanup error", action=LogAction.ERROR, metadata={"error": str(e)}
                )

    async def _cleanup(self) -> None:
        """Clean up old contexts and pages."""
        async with self._lock:
            now = asyncio.get_event_loop().time()

            # Clean up old pages
            pages_to_remove = []
            for page_id, pooled_page in list(self._pages.items()):
                if pooled_page.status != PoolItemStatus.IN_USE:
                    age = now - pooled_page.created_at
                    if (
                        age > self.max_age_seconds
                        or pooled_page.use_count > self.max_uses
                    ):
                        try:
                            await pooled_page.page.close()
                        except Exception:
                            pass

                        pages_to_remove.append(page_id)

            for page_id in pages_to_remove:
                del self._pages[page_id]
                for _, page_ids in self._context_pages.items():
                    page_ids.discard(page_id)

            # Clean up old contexts
            contexts_to_remove = []
            for context_id, pooled_context in list(self._contexts.items()):
                if (
                    pooled_context.status != PoolItemStatus.IN_USE
                    and not self._context_pages.get(context_id)
                ):
                    age = now - pooled_context.created_at
                    if (
                        age > self.max_age_seconds
                        or pooled_context.use_count > self.max_uses
                    ):
                        try:
                            await pooled_context.context.close()
                        except Exception:
                            pass

                        contexts_to_remove.append(context_id)

            for context_id in contexts_to_remove:
                del self._contexts[context_id]
                self._context_pages.pop(context_id, None)

            if pages_to_remove or contexts_to_remove:
                logger.info(
                    f"Cleaned up {len(pages_to_remove)} pages and {len(contexts_to_remove)} contexts",
                    action=LogAction.DELETE,
                )

    def get_stats(self) -> Dict:
        """Get pool statistics."""
        return {
            "contexts": {
                "total": len(self._contexts),
                "available": sum(
                    1
                    for c in self._contexts.values()
                    if c.status == PoolItemStatus.AVAILABLE
                ),
                "in_use": sum(
                    1
                    for c in self._contexts.values()
                    if c.status == PoolItemStatus.IN_USE
                ),
            },
            "pages": {
                "total": len(self._pages),
                "available": sum(
                    1
                    for p in self._pages.values()
                    if p.status == PoolItemStatus.AVAILABLE
                ),
                "in_use": sum(
                    1 for p in self._pages.values() if p.status == PoolItemStatus.IN_USE
                ),
            },
            "max_contexts": self.max_contexts,
            "max_pages_per_context": self.max_pages_per_context,
        }


# Global pool instance
browser_pool = BrowserPool()


async def init_pool() -> None:
    """Initialize global browser pool."""
    await browser_pool.initialize()


async def close_pool() -> None:
    """Close global browser pool."""
    await browser_pool.close()


__all__ = [
    "BrowserPool",
    "browser_pool",
    "init_pool",
    "close_pool",
]
