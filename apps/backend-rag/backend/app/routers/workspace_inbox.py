"""Omnichannel unified feed for team workspace (/kita/inbox).

Queries `conversation_messages` joined with `clients` for the operator's
timeline. RBAC: admins see all, team users see only messages linked to
clients they are assigned to.
"""
from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, Query

from backend.app.core.config import settings
from backend.app.dependencies import get_current_user, get_database_pool

router = APIRouter(prefix="/api/workspace/inbox", tags=["workspace"])


def _is_admin(user: dict) -> bool:
    if user.get("role") == "admin":
        return True
    email = (user.get("email") or "").lower()
    return email in settings.admin_emails_set


@router.get("")
async def feed(
    user: dict = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
    channel: str | None = Query(None, description="Filter by channel: whatsapp|telegram|instagram|web|email"),
    client_id: int | None = Query(None, description="Filter by client_id"),
    direction: str | None = Query(None, description="inbound|outbound"),
    limit: int = Query(50, le=200, ge=1),
) -> dict:
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

    # RBAC: non-admin users see only messages for clients they own
    if not _is_admin(user):
        params.append(user.get("email"))
        filters.append(f"cl.assigned_to = ${len(params)}")

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    sql = f"""
        SELECT m.id,
               m.channel,
               m.direction,
               m.content,
               m.created_at,
               m.client_id,
               cl.name AS client_name,
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
    """Aggregated counts by channel for the last 24h (RBAC-filtered)."""
    params: list = []
    filter_sql = ""
    if not _is_admin(user):
        params.append(user.get("email"))
        filter_sql = f"AND cl.assigned_to = ${len(params)}"

    sql = f"""
        SELECT m.channel, COUNT(*) AS n
        FROM conversation_messages m
        LEFT JOIN clients cl ON cl.id = m.client_id
        WHERE m.created_at > NOW() - INTERVAL '24 hours'
          {filter_sql}
        GROUP BY m.channel
        ORDER BY n DESC
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)
    return {"by_channel": [{"channel": r["channel"], "count": r["n"]} for r in rows]}
