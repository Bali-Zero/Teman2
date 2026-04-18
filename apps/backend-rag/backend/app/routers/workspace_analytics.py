"""Workspace analytics — funnel attribution dashboard (admin-only).

Aggregates `funnel_sessions` + `funnel_attributions` into a single payload
consumed by /kita/analytics/funnel.
"""
from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from backend.app.core.config import settings
from backend.app.dependencies import get_current_user, get_database_pool

router = APIRouter(prefix="/api/workspace/analytics", tags=["workspace"])


def _require_admin(user: dict) -> None:
    if user.get("role") == "admin":
        return
    email = (user.get("email") or "").lower()
    if email in settings.admin_emails_set:
        return
    raise HTTPException(status_code=403, detail="admin only")


@router.get("/funnel")
async def funnel_view(
    user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Return session counts by funnel + conversion counts by first-touch funnel.

    Resilient: if optional tables are missing (e.g. in staging) we return empty
    buckets rather than 500.
    """
    _require_admin(user)

    sessions: list[dict] = []
    conversions: list[dict] = []
    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch(
                "SELECT funnel, COUNT(*) AS n FROM funnel_sessions GROUP BY funnel ORDER BY n DESC"
            )
            sessions = [{"funnel": r["funnel"], "count": r["n"]} for r in rows]
        except asyncpg.UndefinedTableError:
            sessions = []

        try:
            rows = await conn.fetch(
                """
                SELECT first_funnel AS funnel, COUNT(*) AS n
                FROM funnel_attributions
                GROUP BY first_funnel
                ORDER BY n DESC
                """
            )
            conversions = [{"funnel": r["funnel"], "count": r["n"]} for r in rows]
        except asyncpg.UndefinedTableError:
            conversions = []

    return {"sessions": sessions, "conversions": conversions}
