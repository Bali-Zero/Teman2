"""Factory for the MCP server's BrowserManager instance."""
from __future__ import annotations

from browser_core import BrowserConfig, BrowserManager


def make_browser_manager() -> BrowserManager:
    """Build the BrowserManager used by the MCP server."""
    return BrowserManager(
        BrowserConfig(
            headless=True,
            max_contexts=5,
            page_load_timeout_ms=30000,
        )
    )


__all__ = ["make_browser_manager"]
