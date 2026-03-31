"""
Portal Notifications Router.

Client notification center. Reads from portal_notifications table.
Gracefully returns empty if table doesn't exist.
"""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.dependencies import get_database_pool
from backend.app.routers.portal import get_current_client
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/portal/notifications", tags=["portal-notifications"])


async def _get_notifications(
    pool: asyncpg.Pool,
    client_id: int,
    limit: int = 50,
) -> dict[str, Any]:
    """Get notifications for a client. Returns empty if table doesn't exist."""
    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch(
                """
                SELECT id, type, title, body, data, read_at, created_at
                FROM portal_notifications
                WHERE client_id = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                client_id,
                limit,
            )
            unread = await conn.fetchval(
                "SELECT COUNT(*) FROM portal_notifications WHERE client_id = $1 AND read_at IS NULL",
                client_id,
            )
        except Exception:
            return {"notifications": [], "unread_count": 0}

    return {
        "notifications": [
            {
                "id": r["id"],
                "type": r["type"],
                "title": r["title"],
                "body": r["body"],
                "data": r["data"],
                "read": r["read_at"] is not None,
                "created_at": str(r["created_at"]) if r["created_at"] else None,
            }
            for r in rows
        ],
        "unread_count": unread or 0,
    }


async def _mark_read(
    pool: asyncpg.Pool,
    client_id: int,
    notification_id: int,
) -> bool:
    """Mark a notification as read. Returns False if not found."""
    async with pool.acquire() as conn:
        try:
            affected = await conn.fetchval(
                "UPDATE portal_notifications SET read_at = NOW() WHERE id = $1 AND client_id = $2 AND read_at IS NULL RETURNING id",
                notification_id,
                client_id,
            )
            return affected is not None
        except Exception:
            return False


@router.get("")
async def get_notifications(
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    limit: int = Query(default=50, le=100),
) -> dict[str, Any]:
    """Get notifications for the authenticated client."""
    result = await _get_notifications(db_pool, client["client_id"], limit)
    return {"success": True, "data": result}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Mark a notification as read."""
    success = await _mark_read(db_pool, client["client_id"], notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True}


@router.post("/read-all")
async def mark_all_read(
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Mark all notifications as read."""
    async with db_pool.acquire() as conn:
        try:
            await conn.execute(
                "UPDATE portal_notifications SET read_at = NOW() WHERE client_id = $1 AND read_at IS NULL",
                client["client_id"],
            )
        except Exception:
            pass
    return {"success": True}
