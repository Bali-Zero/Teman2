"""Funnel email router — one-click unsubscribe + internal cron trigger.

Two endpoints:
    GET /api/funnel_email/unsubscribe/{token}   public, no auth
    POST /api/funnel_email/fire-due              internal, requires API key
"""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Path
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from backend.app.dependencies import get_database_pool
from backend.app.utils.logging_utils import get_logger
from backend.services.notifications.funnel_email.repository import (
    EmailSubscriptionRepository,
)
from backend.services.notifications.funnel_email.scheduler import fire_due

logger = get_logger(__name__)

router = APIRouter(prefix="/api/funnel_email", tags=["funnel-email"])


_UNSUB_HTML = """<!doctype html>
<html><head><meta charset=utf-8><title>Unsubscribed</title>
<style>body{{font-family:-apple-system,sans-serif;padding:48px;max-width:520px;margin:0 auto;text-align:center}}</style>
</head>
<body>
<h1>Unsubscribed</h1>
<p>We won't send you more Bali Zero {app} reminders. If you change your mind, message us on WhatsApp any time.</p>
<p><a href="https://balizero.com">← Back to balizero.com</a></p>
</body></html>
"""


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
async def unsubscribe(
    token: str = Path(..., min_length=16, max_length=64),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> HTMLResponse:
    """One-click unsubscribe. Always returns 200 HTML so the email link
    works even if the token is bogus (avoid leaking which tokens exist)."""
    repo = EmailSubscriptionRepository(db_pool)
    try:
        count = await repo.unsubscribe_by_token(token)
    except asyncpg.PostgresError:
        logger.exception("funnel_email.unsub: DB error token=%s", token[:8])
        count = 0
    app = "visa" if count > 0 else ""  # best-effort hint
    return HTMLResponse(_UNSUB_HTML.format(app=app).replace("{app}", app))


class FireDueResponse(BaseModel):
    due: int
    sent: int
    skipped_render: int


@router.post("/fire-due", response_model=FireDueResponse)
async def cron_fire_due(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    x_internal_key: str | None = Header(default=None),
) -> FireDueResponse:
    """Internal cron endpoint. Runs the due-row sender.

    Auth: X-Internal-Key header must match INTERNAL_CRON_KEY env var.
    Called by Air OpenClaw cron every 10 minutes.
    """
    import os

    expected = os.getenv("INTERNAL_CRON_KEY", "")
    if not expected or x_internal_key != expected:
        raise HTTPException(status_code=403, detail="Forbidden")

    stats = await fire_due(pool=db_pool)
    return FireDueResponse(**stats)
