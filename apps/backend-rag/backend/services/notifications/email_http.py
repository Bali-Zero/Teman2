"""Shared persistent httpx.AsyncClient for outbound email delivery.

CLAUDE.md Golden Rule #10 forbids ``httpx.AsyncClient()`` instantiation
in method bodies and loops — a persistent client avoids TCP handshake
and TLS resume cost on every call. The email send path runs in hot
loops (retry worker iterates up to 50 rows per cron tick) so the
overhead matters.

Pattern replicates ``backend/services/naga/deps.py``: lazy-singleton
global, re-created if closed. No explicit lifespan hook — FastAPI
shutdown drops the event loop which closes the underlying connections.

Usage:

    from backend.services.notifications.email_http import get_email_client
    client = await get_email_client()
    resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_EMAIL_HTTPX_TIMEOUT = 30.0

# Module-level singleton. Reset if the app process is reloaded (e.g.
# FastAPI dev autoreload) since the client is bound to a now-dead loop.
_client: httpx.AsyncClient | None = None


async def get_email_client() -> httpx.AsyncClient:
    """Return a module-level persistent AsyncClient for email POSTs.

    Safe to call from any coroutine on the same event loop. The client
    auto-recovers if closed externally.
    """
    global _client  # noqa: PLW0603 — singleton by design
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=_EMAIL_HTTPX_TIMEOUT)
        logger.debug("email_http: created persistent AsyncClient")
    return _client


async def close_email_client() -> None:
    """Release the shared client — test hook + graceful shutdown."""
    global _client  # noqa: PLW0603
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None
