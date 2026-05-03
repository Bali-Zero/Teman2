"""nuzantara-browser-core — shared stealth Playwright manager for Nuzantara."""
from browser_core.manager import (
    BrowserConfig,
    BrowserError,
    BrowserManager,
    RateLimiter,
)
from browser_core.stealth import StealthPlugin

__all__ = [
    "BrowserConfig",
    "BrowserError",
    "BrowserManager",
    "RateLimiter",
    "StealthPlugin",
]

__version__ = "0.1.0"
