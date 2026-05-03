"""
Notification Admin Router
=========================
Admin-only endpoints for monitoring and managing notifications.

Endpoints:
- GET /api/admin/notifications/dashboard: Stats and recent activity
- GET /api/admin/notifications/alerts: List all alerts with filters
- GET /api/admin/notifications/stats: Aggregate statistics
- POST /api/admin/notifications/retry: Retry failed alerts
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.dependencies import get_current_user, get_database_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/notifications", tags=["notifications-admin"])


class AlertListItem(BaseModel):
    """Alert item for list endpoint."""

    id: int
    client_id: int
    client_name: str
    client_email: str
    alert_type: str
    status: str
    email_subject: str
    created_at: datetime
    sent_at: datetime | None
    error_message: str | None


class NotificationStats(BaseModel):
    """Notification statistics."""

    total_alerts_24h: int
    total_alerts_7d: int
    total_alerts_30d: int
    pending_count: int
    sent_count_24h: int
    failed_count_24h: int
    alerts_by_type: dict
    alerts_by_status: dict
    top_clients: list[dict]


class DashboardData(BaseModel):
    """Dashboard data response."""

    stats: NotificationStats
    recent_alerts: list[AlertListItem]
    system_status: str
    last_check: datetime | None


class RetryRequest(BaseModel):
    """Request to retry failed alerts."""

    alert_ids: list[int] | None = None  # If None, retry all failed


class RetryResponse(BaseModel):
    """Retry operation response."""

    success: bool
    retried: int
    message: str


def require_admin(current_user: dict) -> None:
    """Verify user is admin."""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/dashboard", response_model=DashboardData)
async def get_dashboard(
    current_user: dict = Depends(get_current_user),
) -> DashboardData:
    """
    Get notification dashboard data.
    Admin only.
    """
    require_admin(current_user)

    pool = await get_database_pool()

    async with pool.acquire() as conn:
        # Get statistics
        stats_row = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as total_24h,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as total_7d,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') as total_30d,
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'sent' AND sent_at > NOW() - INTERVAL '24 hours') as sent_24h,
                COUNT(*) FILTER (WHERE status = 'failed' AND created_at > NOW() - INTERVAL '24 hours') as failed_24h
            FROM notification_alerts
            """,
        )

        # Get alerts by type
        type_rows = await conn.fetch(
            """
            SELECT alert_type, COUNT(*) as count
            FROM notification_alerts
            WHERE created_at > NOW() - INTERVAL '30 days'
            GROUP BY alert_type
            ORDER BY count DESC
            """,
        )

        # Get alerts by status
        status_rows = await conn.fetch(
            """
            SELECT status, COUNT(*) as count
            FROM notification_alerts
            GROUP BY status
            """,
        )

        # Get top clients with most alerts
        top_clients = await conn.fetch(
            """
            SELECT
                c.id,
                c.full_name,
                c.email,
                COUNT(*) as alert_count
            FROM notification_alerts na
            JOIN clients c ON c.id = na.client_id
            WHERE na.created_at > NOW() - INTERVAL '30 days'
            GROUP BY c.id, c.full_name, c.email
            ORDER BY alert_count DESC
            LIMIT 10
            """,
        )

        # Get recent alerts
        recent = await conn.fetch(
            """
            SELECT
                na.id,
                na.client_id,
                c.full_name as client_name,
                c.email as client_email,
                na.alert_type,
                na.status,
                na.email_subject,
                na.created_at,
                na.sent_at,
                na.error_message
            FROM notification_alerts na
            JOIN clients c ON c.id = na.client_id
            ORDER BY na.created_at DESC
            LIMIT 50
            """,
        )

        # Get last check time
        last_check = await conn.fetchval("SELECT MAX(created_at) FROM notification_alerts")

    stats = NotificationStats(
        total_alerts_24h=stats_row["total_24h"],
        total_alerts_7d=stats_row["total_7d"],
        total_alerts_30d=stats_row["total_30d"],
        pending_count=stats_row["pending"],
        sent_count_24h=stats_row["sent_24h"],
        failed_count_24h=stats_row["failed_24h"],
        alerts_by_type={row["alert_type"]: row["count"] for row in type_rows},
        alerts_by_status={row["status"]: row["count"] for row in status_rows},
        top_clients=[
            {
                "id": row["id"],
                "name": row["full_name"],
                "email": row["email"],
                "alert_count": row["alert_count"],
            }
            for row in top_clients
        ],
    )

    recent_alerts = [
        AlertListItem(
            id=row["id"],
            client_id=row["client_id"],
            client_name=row["client_name"],
            client_email=row["client_email"],
            alert_type=row["alert_type"],
            status=row["status"],
            email_subject=row["email_subject"],
            created_at=row["created_at"],
            sent_at=row["sent_at"],
            error_message=row["error_message"],
        )
        for row in recent
    ]

    # Determine system status
    if stats.failed_count_24h > 10:
        system_status = "degraded"
    elif stats.pending_count > 100:
        system_status = "backlogged"
    else:
        system_status = "healthy"

    return DashboardData(
        stats=stats,
        recent_alerts=recent_alerts,
        system_status=system_status,
        last_check=last_check,
    )


@router.get("/alerts")
async def list_alerts(
    status: str | None = Query(None, description="Filter by status"),
    alert_type: str | None = Query(None, description="Filter by type"),
    client_id: int | None = Query(None, description="Filter by client"),
    days: int = Query(30, ge=1, le=365, description="Days to look back"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """
    List alerts with filtering and pagination.
    Admin only.
    """
    require_admin(current_user)

    pool = await get_database_pool()

    # Build query — use parameterized interval for safety
    interval = timedelta(days=days)
    where_clauses = [f"na.created_at > NOW() - ${1}::interval"]
    params = [interval]
    param_idx = 2

    if status:
        where_clauses.append(f"na.status = ${param_idx}")
        params.append(status)
        param_idx += 1

    if alert_type:
        where_clauses.append(f"na.alert_type = ${param_idx}")
        params.append(alert_type)
        param_idx += 1

    if client_id:
        where_clauses.append(f"na.client_id = ${param_idx}")
        params.append(client_id)
        param_idx += 1

    where_sql = " AND ".join(where_clauses)

    async with pool.acquire() as conn:
        # Get total count
        count_sql = f"""
            SELECT COUNT(*)
            FROM notification_alerts na
            WHERE {where_sql}
        """
        total = await conn.fetchval(count_sql, *params)

        # Get alerts
        query_sql = f"""
            SELECT
                na.id,
                na.client_id,
                c.full_name as client_name,
                c.email as client_email,
                na.alert_type,
                na.status,
                na.email_subject,
                na.email_body,
                na.created_at,
                na.sent_at,
                na.error_message
            FROM notification_alerts na
            JOIN clients c ON c.id = na.client_id
            WHERE {where_sql}
            ORDER BY na.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([limit, offset])

        rows = await conn.fetch(query_sql, *params)

    return {
        "alerts": [dict(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(rows) < total,
    }


@router.get("/stats")
async def get_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(get_current_user),
):
    """
    Get detailed statistics.
    Admin only.
    """
    require_admin(current_user)

    pool = await get_database_pool()

    async with pool.acquire() as conn:
        # Daily breakdown
        interval = timedelta(days=days)
        daily = await conn.fetch(
            """
            SELECT
                DATE(created_at) as date,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'sent') as sent,
                COUNT(*) FILTER (WHERE status = 'failed') as failed,
                COUNT(*) FILTER (WHERE status = 'pending') as pending
            FROM notification_alerts
            WHERE created_at > NOW() - $1::interval
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            """,
            interval,
        )

        # By type and status
        by_type_status = await conn.fetch(
            """
            SELECT
                alert_type,
                status,
                COUNT(*) as count
            FROM notification_alerts
            WHERE created_at > NOW() - $1::interval
            GROUP BY alert_type, status
            ORDER BY alert_type, status
            """,
            interval,
        )

        # Success rate
        success_rate = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'sent') as sent,
                COUNT(*) FILTER (WHERE status = 'failed') as failed,
                COUNT(*) as total,
                CASE
                    WHEN COUNT(*) > 0
                    THEN ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'sent') / COUNT(*), 2)
                    ELSE 0
                END as success_rate
            FROM notification_alerts
            WHERE created_at > NOW() - $1::interval
            """,
            interval,
        )

    return {
        "daily_breakdown": [dict(row) for row in daily],
        "by_type_status": [dict(row) for row in by_type_status],
        "success_rate": {
            "sent": success_rate["sent"],
            "failed": success_rate["failed"],
            "total": success_rate["total"],
            "rate_percent": success_rate["success_rate"],
        },
    }


@router.post("/retry", response_model=RetryResponse)
async def retry_failed_alerts(
    request: RetryRequest,
    current_user: dict = Depends(get_current_user),
) -> RetryResponse:
    """
    Retry failed alerts.
    Admin only.
    """
    require_admin(current_user)

    from backend.app.modules.notifications.service import NotificationService

    pool = await get_database_pool()
    service = NotificationService(pool)

    async with pool.acquire() as conn:
        if request.alert_ids:
            # Retry specific alerts
            rows = await conn.fetch(
                """
                SELECT * FROM notification_alerts
                WHERE id = ANY($1) AND status = 'failed'
                """,
                request.alert_ids,
            )
        else:
            # Retry all failed alerts from last 7 days
            rows = await conn.fetch(
                """
                SELECT * FROM notification_alerts
                WHERE status = 'failed'
                AND created_at > NOW() - INTERVAL '7 days'
                """,
            )

        if not rows:
            return RetryResponse(
                success=True,
                retried=0,
                message="No failed alerts to retry",
            )

        # Import here to avoid circular imports
        from backend.app.modules.notifications.models import ClientAlert

        alerts = [ClientAlert(**dict(row)) for row in rows]

    # Use a separate connection for email lookup to avoid deadlock
    async def get_email(client_id: int) -> str | None:
        async with pool.acquire() as email_conn:
            return await email_conn.fetchval(
                "SELECT email FROM clients WHERE id = $1",
                client_id,
            )

    results = await service.process_alerts_batch(alerts, get_email)

    successful = sum(1 for r in results if r.success)

    logger.info(
        "Retry operation completed",
        extra={
            "user": current_user.get("email"),
            "retried": len(alerts),
            "successful": successful,
        },
    )

    return RetryResponse(
        success=True,
        retried=len(alerts),
        message=f"Retried {len(alerts)} alerts, {successful} successful",
    )


@router.post("/pause-client")
async def pause_client_notifications(
    client_id: int,
    hours: int = Query(24, ge=1, le=168),
    current_user: dict = Depends(get_current_user),
):
    """
    Pause notifications for a client temporarily.
    Admin only.
    """
    require_admin(current_user)

    pool = await get_database_pool()

    async with pool.acquire() as conn:
        # Suppress pending alerts for this client
        interval = timedelta(hours=hours)
        await conn.execute(
            """
            UPDATE notification_alerts
            SET status = 'suppressed'
            WHERE client_id = $1
            AND status = 'pending'
            AND created_at > NOW() - $2::interval
            """,
            client_id,
            interval,
        )

    logger.info(
        "Client notifications paused",
        extra={
            "user": current_user.get("email"),
            "client_id": client_id,
            "hours": hours,
        },
    )

    return {
        "success": True,
        "message": f"Notifications paused for client {client_id} for {hours} hours",
    }
