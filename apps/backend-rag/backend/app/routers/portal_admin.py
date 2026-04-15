"""
Portal Admin Router.

Only superusers (SUPERUSER_EMAILS in routers/portal.py) can hit these routes.
Provides a search endpoint so the portal header can resolve a client to
impersonate via the ?as_client=<id> query param used by every portal API.

This module does NOT need /api/portal/admin prefix to be added to the
workspace menu — clients never see the endpoint because it 403s for them.
"""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.deps.database import get_database_pool

router = APIRouter(prefix="/api/portal/admin", tags=["portal-admin"])


@router.get("/clients/search")
async def search_clients(
    request: Request,
    q: str = "",
    limit: int = 20,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Fuzzy-search clients by name/email for the superuser impersonation bar.

    The caller must be authenticated as a SUPERUSER_EMAILS account; the
    dependency is enforced here rather than via Depends so we can return a
    consistent JSON shape (the frontend treats 403 as "hide the search bar").
    """
    from backend.app.routers.portal import SUPERUSER_EMAILS

    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    email = (user.get("email") or "").lower()
    if email not in SUPERUSER_EMAILS:
        raise HTTPException(status_code=403, detail="Not a superuser")

    limit = max(1, min(int(limit or 20), 50))
    query_text = (q or "").strip()

    async with db_pool.acquire() as conn:
        if query_text:
            rows = await conn.fetch(
                """
                SELECT id, email, full_name
                FROM clients
                WHERE LOWER(full_name) LIKE '%' || LOWER($1) || '%'
                   OR LOWER(email) LIKE '%' || LOWER($1) || '%'
                ORDER BY
                    CASE WHEN LOWER(full_name) LIKE LOWER($1) || '%' THEN 0 ELSE 1 END,
                    full_name
                LIMIT $2
                """,
                query_text,
                limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT id, email, full_name
                FROM clients
                WHERE full_name IS NOT NULL
                ORDER BY updated_at DESC NULLS LAST
                LIMIT $1
                """,
                limit,
            )

    return {
        "success": True,
        "count": len(rows),
        "items": [
            {"id": r["id"], "email": r["email"], "full_name": r["full_name"]}
            for r in rows
        ],
    }


@router.get("/me")
async def whoami(request: Request) -> dict:
    """Returns whether the caller is a recognised superuser.

    Frontend calls this once on portal mount so it knows whether to render
    the impersonation search bar. Never throws on non-superuser — just
    returns is_superuser=false so the UI stays silent.
    """
    from backend.app.routers.portal import SUPERUSER_EMAILS

    user = getattr(request.state, "user", None)
    email = (user.get("email") if user else "") or ""
    is_superuser = email.lower() in SUPERUSER_EMAILS
    return {
        "success": True,
        "is_superuser": is_superuser,
        "email": email if is_superuser else None,
    }
