"""Omnichannel unified feed for team workspace (/kita/inbox).

Queries `conversation_messages` joined with `clients` for the operator's
timeline.

OWNER-ONLY (2026-05-28): the inbox is private to Zero. Every other user —
including the other CRM admins (asya@, antonellosiano@) and all team members —
receives HTTP 403. The gate is intentionally decoupled from the shared
`settings.admin_emails_set` so restricting inbox visibility never widens or
narrows admin RBAC elsewhere in the CRM.
"""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.dependencies import get_current_user, get_database_pool

router = APIRouter(prefix="/api/workspace/inbox", tags=["workspace"])

# Inbox-only allowlist — NOT settings.admin_emails_set (see module docstring).
# Deliberately narrower than deps.owner.OWNER_EMAILS (which also includes
# antonellosiano@): Zero asked for the inbox to be visible to zero@ ONLY
# (2026-05-28). Do NOT swap this for require_owner — it would widen access.
INBOX_OWNER_EMAILS: frozenset[str] = frozenset({"zero@balizero.com"})


def _is_inbox_owner(user: dict) -> bool:
    """True only for the inbox owner (Zero). Independent of CRM admin RBAC."""
    return (user.get("email") or "").lower() in INBOX_OWNER_EMAILS


def _require_inbox_owner(user: dict) -> None:
    if not _is_inbox_owner(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inbox is restricted to the workspace owner.",
        )


@router.get("")
async def feed(
    user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
    channel: str | None = Query(
        None, description="Filter by channel: whatsapp|telegram|instagram|web|email"
    ),
    client_id: int | None = Query(None, description="Filter by client_id"),
    direction: str | None = Query(None, description="inbound|outbound"),
    limit: int = Query(50, le=200, ge=1),
) -> dict:
    _require_inbox_owner(user)

    filters: list[str] = []
    params: list = []

    if channel:
        params.append(channel)
        filters.append(f"m.channel = ${len(params)}")
    if client_id is not None:
        params.append(client_id)
        filters.append(f"m.client_id = ${len(params)}")
    if direction in {"inbound", "outbound"}:
        params.append(direction)
        filters.append(f"m.direction = ${len(params)}")

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    sql = f"""
        SELECT m.id,
               m.channel,
               m.direction,
               m.content,
               m.created_at,
               m.client_id,
               cl.full_name AS client_name,
               cl.email AS client_email
        FROM conversation_messages m
        LEFT JOIN clients cl ON cl.id = m.client_id
        {where}
        ORDER BY m.created_at DESC
        LIMIT {limit}
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
    return {
        "items": [
            {
                "id": r["id"],
                "channel": r["channel"],
                "direction": r["direction"],
                "content": r["content"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "client_id": r["client_id"],
                "client_name": r["client_name"],
                "client_email": r["client_email"],
            }
            for r in rows
        ],
        "count": len(rows),
    }


@router.get("/stats")
async def stats(
    user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Aggregated counts by channel for the last 24h (owner-only)."""
    _require_inbox_owner(user)

    sql = """
        SELECT m.channel, COUNT(*) AS n
        FROM conversation_messages m
        LEFT JOIN clients cl ON cl.id = m.client_id
        WHERE m.created_at > NOW() - INTERVAL '24 hours'
        GROUP BY m.channel
        ORDER BY n DESC
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql)
    return {"by_channel": [{"channel": r["channel"], "count": r["n"]} for r in rows]}
