"""
Notifications Router
====================
FastAPI router for notification endpoints.

Endpoints:
- POST /api/notifications/check: Run manual expiry check
- GET /api/notifications/status: Get notification system status
- GET /api/notifications/pending: Get pending alerts (admin)
- POST /api/notifications/send: Send pending alerts (admin)
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.modules.notifications.checker import ExpiryChecker
from backend.app.modules.notifications.models import ClientInfo
from backend.app.modules.notifications.service import NotificationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class CheckRequest(BaseModel):
    """Request body for manual check trigger."""

    client_id: int | None = None  # If None, check all clients


class CheckResponse(BaseModel):
    """Response from check operation."""

    success: bool
    alerts_generated: int
    message: str
    timestamp: datetime


class StatusResponse(BaseModel):
    """System status response."""

    status: str
    pending_alerts: int
    last_check: datetime | None
    email_provider: str


async def get_clients_from_db(pool, client_id: int | None = None) -> list[ClientInfo]:
    """Fetch clients from database."""
    async with pool.acquire() as conn:
        if client_id:
            rows = await conn.fetch(
                """
                SELECT
                    c.id,
                    c.email,
                    c.full_name,
                    COALESCE(c.preferred_language, 'en') as preferred_language,
                    c.assigned_to as team_leader_email,
                    c.date_of_birth,
                    c.passport_expiry,
                    c.passport_number,
                    v.expiry_date as visa_expiry,
                    v.visa_type
                FROM clients c
                LEFT JOIN (
                    SELECT DISTINCT ON (client_id)
                        client_id, expiry_date, document_type as visa_type
                    FROM client_documents
                    WHERE document_category = 'immigration'
                    AND expiry_date IS NOT NULL
                    ORDER BY client_id, expiry_date DESC
                ) v ON v.client_id = c.id
                WHERE c.id = $1 AND c.is_active = true
                """,
                client_id,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT
                    c.id,
                    c.email,
                    c.full_name,
                    COALESCE(c.preferred_language, 'en') as preferred_language,
                    c.assigned_to as team_leader_email,
                    c.date_of_birth,
                    c.passport_expiry,
                    c.passport_number,
                    v.expiry_date as visa_expiry,
                    v.visa_type
                FROM clients c
                LEFT JOIN (
                    SELECT DISTINCT ON (client_id)
                        client_id, expiry_date, document_type as visa_type
                    FROM client_documents
                    WHERE document_category = 'immigration'
                    AND expiry_date IS NOT NULL
                    ORDER BY client_id, expiry_date DESC
                ) v ON v.client_id = c.id
                WHERE c.is_active = true
                """
            )

        clients = []
        for row in rows:
            client_data = dict(row)
            # Convert string dates to datetime
            for field in ["date_of_birth", "passport_expiry", "visa_expiry"]:
                if client_data.get(field) and isinstance(client_data[field], str):
                    client_data[field] = datetime.fromisoformat(client_data[field])
            clients.append(ClientInfo(**client_data))

        return clients


@router.post("/check", response_model=CheckResponse)
async def run_expiry_check(
    request: CheckRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """
    Run manual expiry check for all clients or specific client.
    Requires authentication.
    """
    try:
        pool = await get_database_pool()

        # Fetch clients
        clients = await get_clients_from_db(pool, request.client_id)

        if not clients:
            return CheckResponse(
                success=True,
                alerts_generated=0,
                message="No active clients found",
                timestamp=datetime.now(tz=timezone.utc).replace(tzinfo=None),
            )

        # Run check
        checker = ExpiryChecker()
        alerts = checker.check_all_clients(clients)

        # Store alerts in database
        async with pool.acquire() as conn:
            for alert in alerts:
                await conn.execute(
                    """
                    INSERT INTO notification_alerts
                    (client_id, alert_type, status, message, email_subject, email_body, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (client_id, alert_type, DATE(created_at))
                    DO NOTHING
                    """,
                    alert.client_id,
                    alert.alert_type.value,
                    alert.status.value,
                    alert.message,
                    alert.email_subject,
                    alert.email_body,
                    alert.created_at,
                )

        logger.info(
            "Manual expiry check completed",
            extra={
                "user": current_user.get("email"),
                "clients_checked": len(clients),
                "alerts_generated": len(alerts),
            },
        )

        return CheckResponse(
            success=True,
            alerts_generated=len(alerts),
            message=f"Check completed. {len(alerts)} alerts generated.",
            timestamp=datetime.now(tz=timezone.utc).replace(tzinfo=None),
        )

    except Exception as e:
        logger.error("Expiry check failed", exc_info=e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=StatusResponse)
async def get_notification_status(
    current_user: dict = Depends(get_current_user),
):
    """Get notification system status."""
    try:
        pool = await get_database_pool()

        async with pool.acquire() as conn:
            pending_count = await conn.fetchval(
                "SELECT COUNT(*) FROM notification_alerts WHERE status = 'pending'"
            )
            last_check = await conn.fetchval("SELECT MAX(created_at) FROM notification_alerts")

        return StatusResponse(
            status="operational",
            pending_alerts=pending_count,
            last_check=last_check,
            email_provider="sendgrid",
        )

    except Exception as e:
        logger.error("Failed to get status", exc_info=e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-pending")
async def send_pending_alerts(
    current_user: dict = Depends(get_current_user),
):
    """
    Send all pending alerts.
    Admin only endpoint.
    """
    # Check admin role
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        pool = await get_database_pool()
        service = NotificationService(pool)

        # Get pending alerts
        pending = await service.get_pending_alerts()

        if not pending:
            return {"success": True, "message": "No pending alerts", "sent": 0}

        # Send alerts
        async def get_client_email(client_id: int) -> str | None:
            async with pool.acquire() as conn:
                return await conn.fetchval(
                    "SELECT email FROM clients WHERE id = $1",
                    client_id,
                )

        results = await service.process_alerts_batch(pending, get_client_email)

        successful = sum(1 for r in results if r.success)

        return {
            "success": True,
            "message": f"Processed {len(results)} alerts",
            "sent": successful,
            "failed": len(results) - successful,
        }

    except Exception as e:
        logger.error("Failed to send pending alerts", exc_info=e)
        raise HTTPException(status_code=500, detail=str(e))


# Include test endpoints only in non-production environments
import os

if os.getenv("ENVIRONMENT", "development").lower() != "production":
    from backend.app.modules.notifications.test_endpoint import router as test_router

    router.include_router(test_router)

# Include admin router
from backend.app.modules.notifications.admin_router import router as admin_router

router.include_router(admin_router)
