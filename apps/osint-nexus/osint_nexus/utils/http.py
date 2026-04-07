"""Shared async HTTP client with anti-detection defaults."""

from __future__ import annotations

import asyncio
import random
import ssl
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fake_useragent import UserAgent

from osint_nexus.config import (
    SCRAPE_MAX_DELAY,
    SCRAPE_MIN_DELAY,
    SCRAPE_PROXY,
    SCRAPE_TIMEOUT,
)
from osint_nexus.utils.logging import get_logger

logger = get_logger("http")
_ua = UserAgent(browsers=["chrome", "firefox", "edge"])


def _ssl_context() -> ssl.SSLContext:
    """Permissive SSL — many .go.id sites have expired certs."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


@asynccontextmanager
async def get_client(**kwargs) -> AsyncIterator[httpx.AsyncClient]:
    """Yields a configured async client. Closes on exit."""
    defaults = {
        "timeout": httpx.Timeout(SCRAPE_TIMEOUT, connect=10.0),
        "verify": _ssl_context(),
        "follow_redirects": True,
        "http2": True,
        "headers": {
            "User-Agent": _ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
        },
    }
    if SCRAPE_PROXY:
        defaults["proxy"] = SCRAPE_PROXY
    defaults.update(kwargs)
    async with httpx.AsyncClient(**defaults) as client:
        yield client


async def random_delay(min_s: float | None = None, max_s: float | None = None) -> None:
    """Human-like random delay between requests."""
    lo = min_s or SCRAPE_MIN_DELAY
    hi = max_s or SCRAPE_MAX_DELAY
    delay = random.uniform(lo, hi)
    logger.debug("Sleeping %.1fs", delay)
    await asyncio.sleep(delay)
