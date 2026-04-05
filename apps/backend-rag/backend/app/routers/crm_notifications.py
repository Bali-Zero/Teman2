"""
CRM Notifications Endpoints

GET /api/crm/notifications — returns notification_alerts for the current team member.
Used by the NotificationBell component in the CRM header.

Surfaces: portal document uploads, portal profile updates, and future alert types from notification_alerts.
"""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Query

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/crm", tags=["crm-notifications"])


@router.get("/notifications")
async def get_crm_notifications(
    unread_only: bool = Query(False, description="Return only unread (pending) notifications"),
    limit: int = Query(50, le=200),
    pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """
    Return notification_alerts for the current team member.

    Filters by clients assigned_to the current user (or all clients for admins).
    Notifications are sorted newest first.
    """
    from backend.app.routers.crm_clients import is_crm_admin

    user_email = (current_user.get("email") or "").strip().lower()
    user_is_admin = is_crm_admin(current_user)

    async with pool.acquire() as conn:
        if user_is_admin:
            # Admins see all portal-upload notifications
            rows = await conn.fetch(
                """
                SELECT
                    na.id,
                    na.client_id,
                    na.alert_type,
                    na.status,
                    na.message,
                    na.created_at,
                    na.sent_at,
                    c.full_name AS client_name,
                    c.assigned_to
                FROM notification_alerts na
                JOIN clients c ON c.id = na.client_id AND c.deleted_at IS NULL
                WHERE na.alert_type IN ('portal_document_upload', 'portal_profile_update')
                  AND ($1 = false OR na.status = 'pending')
                ORDER BY na.created_at DESC
                LIMIT $2
                """,
                unread_only,
                limit,
            )
        else:
            # Team members see only their clients
            rows = await conn.fetch(
                """
                SELECT
                    na.id,
                    na.client_id,
                    na.alert_type,
                    na.status,
                    na.message,
                    na.created_at,
                    na.sent_at,
                    c.full_name AS client_name,
                    c.assigned_to
                FROM notification_alerts na
                JOIN clients c ON c.id = na.client_id AND c.deleted_at IS NULL
                WHERE na.alert_type IN ('portal_document_upload', 'portal_profile_update')
                  AND LOWER(c.assigned_to) = $1
                  AND ($2 = false OR na.status = 'pending')
                ORDER BY na.created_at DESC
                LIMIT $3
                """,
                user_email,
                unread_only,
                limit,
            )

    return [
        {
            "id": r["id"],
            "client_id": r["client_id"],
            "client_name": r["client_name"],
            "alert_type": r["alert_type"],
            "status": r["status"],
            "message": r["message"],
            "created_at": r["created_at"].isoformat(),
            "sent_at": r["sent_at"].isoformat() if r["sent_at"] else None,
        }
        for r in rows
    ]


@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Mark a notification as read (status = 'sent')."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE notification_alerts
            SET status = 'sent', sent_at = NOW()
            WHERE id = $1 AND status = 'pending'
            RETURNING id, status
            """,
            notification_id,
        )
    if not row:
        return {"id": notification_id, "status": "already_read"}
    return {"id": row["id"], "status": row["status"]}


@router.get("/notifications/count")
async def get_unread_notifications_count(
    pool: asyncpg.Pool = Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, int]:
    """Return count of unread (pending) portal notifications for current user."""
    from backend.app.routers.crm_clients import is_crm_admin

    user_email = (current_user.get("email") or "").strip().lower()
    user_is_admin = is_crm_admin(current_user)

    async with pool.acquire() as conn:
        if user_is_admin:
            count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM notification_alerts na
                JOIN clients c ON c.id = na.client_id AND c.deleted_at IS NULL
                WHERE na.alert_type IN ('portal_document_upload', 'portal_profile_update')
                  AND na.status = 'pending'
                """,
            )
        else:
            count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM notification_alerts na
                JOIN clients c ON c.id = na.client_id AND c.deleted_at IS NULL
                WHERE na.alert_type IN ('portal_document_upload', 'portal_profile_update')
                  AND na.status = 'pending'
                  AND LOWER(c.assigned_to) = $1
                """,
                user_email,
            )

    return {"unread": int(count or 0)}
