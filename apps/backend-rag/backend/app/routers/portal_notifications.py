"""
Portal Notifications Router.

Client notification center. Reads from portal_notifications table.
Gracefully returns empty if table doesn't exist.
"""

from typing import Any, NoReturn
from uuid import uuid4

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.dependencies import get_database_pool
from backend.app.routers.portal import get_current_client
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/portal/notifications", tags=["portal-notifications"])


def _raise_notifications_unavailable(
    operation: str,
    error: Exception,
) -> NoReturn:
    """Raise a client-safe 503 linked to a redacted diagnostic event."""
    error_ref = uuid4().hex
    logger.error(
        "Portal notifications unavailable operation=%s error_ref=%s error_type=%s",
        operation,
        error_ref,
        type(error).__name__,
    )
    raise HTTPException(
        status_code=503,
        detail=f"Notifications temporarily unavailable. Reference: {error_ref}",
    ) from error


async def _get_notifications(
    pool: asyncpg.Pool,
    client_id: int,
    limit: int = 50,
) -> dict[str, Any]:
    """Get notifications for a client. Returns empty if table doesn't exist."""
    try:
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
            except asyncpg.UndefinedTableError:
                logger.warning(
                    "Portal notifications schema unavailable; returning explicit degraded state",
                )
                return {"notifications": [], "unread_count": 0, "degraded": True}
    except Exception as error:
        _raise_notifications_unavailable("get_notifications", error)

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
    try:
        async with pool.acquire() as conn:
            affected = await conn.fetchval(
                "UPDATE portal_notifications SET read_at = NOW() WHERE id = $1 AND client_id = $2 AND read_at IS NULL RETURNING id",
                notification_id,
                client_id,
            )
    except Exception as error:
        _raise_notifications_unavailable("mark_read", error)
    return affected is not None


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
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE portal_notifications SET read_at = NOW() WHERE client_id = $1 AND read_at IS NULL",
                client["client_id"],
            )
    except Exception as error:
        _raise_notifications_unavailable("mark_all_read", error)
    return {"success": True}
