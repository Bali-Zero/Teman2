"""Thin wrapper — delegates to browser-core with app-specific settings.

The mature stealth BrowserManager lives in packages/browser-core/. This
file preserves backward compatibility for bali-intel-scraper code that
imports `browser_manager` from here.
"""
from __future__ import annotations

from browser_core import BrowserConfig, BrowserError, BrowserManager, StealthPlugin
from config.settings import settings
from backend.core.rate_limiter import limit_scrape_request


def _build_config() -> BrowserConfig:
    return BrowserConfig(
        headless=settings.scraping.headless,
        max_contexts=settings.scraping.max_concurrent_browsers,
        page_load_timeout_ms=settings.scraping.page_load_timeout * 1000,
    )


browser_manager = BrowserManager(_build_config(), rate_limiter=limit_scrape_request)


async def init_browser() -> None:
    await browser_manager.initialize()


async def close_browser() -> None:
    await browser_manager.close()


__all__ = [
    "BrowserConfig",
    "BrowserError",
    "BrowserManager",
    "StealthPlugin",
    "browser_manager",
    "init_browser",
    "close_browser",
]
