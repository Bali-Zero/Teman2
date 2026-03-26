"""
Notification Test Endpoint
==========================
Temporary endpoint for testing the notification system in staging.

WARNING: This endpoint should be removed before production deployment.
It allows manual testing with real client data.

Usage:
  POST /api/notifications/test
  {
    "client_id": 123,  // optional
    "alert_type": "passport_critical",  // optional
    "force_send": false  // if true, sends email immediately
  }
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.modules.notifications.checker import ExpiryChecker
from backend.app.modules.notifications.models import AlertType, ClientInfo
from backend.app.modules.notifications.service import NotificationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications/test", tags=["notifications-test"])


class TestNotificationRequest(BaseModel):
    """Request body for testing notifications."""

    client_id: int | None = Field(
        None, description="Test with specific client, or random if omitted"
    )
    alert_type: AlertType | None = Field(
        None, description="Force specific alert type, or auto-detect"
    )
    force_send: bool = Field(False, description="If true, actually sends email (use with caution!)")
    test_email: str | None = Field(None, description="Override recipient email for testing")


class TestNotificationResponse(BaseModel):
    """Response from test endpoint."""

    success: bool
    message: str
    alert_generated: bool
    alert_sent: bool
    alert_details: dict | None = None
    client_info: dict | None = None


@router.post("/", response_model=TestNotificationResponse)
async def test_notification(
    request: TestNotificationRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Test notification system with real client data.

    This endpoint is for STAGING ONLY. It allows testing the notification
    system without waiting for scheduled runs.

    If force_send is True, an actual email will be sent. Use with caution!
    """
    # Only allow in staging/non-production
    from backend.app.core.config import settings

    if settings.environment == "production":
        raise HTTPException(
            status_code=403,
            detail="Test endpoint disabled in production",
        )

    pool = await get_database_pool()

    try:
        # Get client(s) from database
        async with pool.acquire() as conn:
            if request.client_id:
                row = await conn.fetchrow(
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
                    request.client_id,
                )
                if not row:
                    raise HTTPException(
                        status_code=404, detail=f"Client {request.client_id} not found"
                    )
                rows = [row]
            else:
                # Get clients with expiring documents for testing
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
                    AND (c.passport_expiry IS NOT NULL OR v.expiry_date IS NOT NULL)
                    LIMIT 10
                    """
                )

        if not rows:
            return TestNotificationResponse(
                success=False,
                message="No clients found with passport/visa data",
                alert_generated=False,
                alert_sent=False,
            )

        # Pick first client or random
        import random

        row = random.choice(rows) if len(rows) > 1 else rows[0]

        client_data = dict(row)
        # Convert string dates to datetime
        for field in ["date_of_birth", "passport_expiry", "visa_expiry"]:
            if client_data.get(field) and isinstance(client_data[field], str):
                client_data[field] = datetime.fromisoformat(client_data[field])

        client = ClientInfo(**client_data)

        # If force_send, we may want to modify dates to trigger specific alerts
        if request.alert_type:
            # Override dates to force specific alert type
            today = datetime.now(tz=timezone.utc).replace(tzinfo=None)

            if request.alert_type == AlertType.PASSPORT_WARNING:
                client.passport_expiry = today + timedelta(days=365)
            elif request.alert_type == AlertType.PASSPORT_CRITICAL:
                client.passport_expiry = today + timedelta(days=240)
            elif request.alert_type == AlertType.PASSPORT_EXPIRED:
                client.passport_expiry = today - timedelta(days=30)
            elif request.alert_type == AlertType.VISA_WARNING:
                client.visa_expiry = today + timedelta(days=100)
            elif request.alert_type == AlertType.VISA_CRITICAL:
                client.visa_expiry = today + timedelta(days=50)
            elif request.alert_type == AlertType.VISA_EXPIRED:
                client.visa_expiry = today - timedelta(days=10)
            elif request.alert_type == AlertType.BIRTHDAY:
                client.date_of_birth = today.replace(year=today.year - 30)

        # Run check
        checker = ExpiryChecker()
        alerts = checker.check_client(client)

        if not alerts:
            return TestNotificationResponse(
                success=True,
                message=f"No alerts generated for client {client.full_name}. Try force_send with specific alert_type.",
                alert_generated=False,
                alert_sent=False,
                client_info={
                    "id": client.id,
                    "name": client.full_name,
                    "email": client.email,
                    "passport_expiry": client.passport_expiry.isoformat()
                    if client.passport_expiry
                    else None,
                    "visa_expiry": client.visa_expiry.isoformat() if client.visa_expiry else None,
                    "date_of_birth": client.date_of_birth.isoformat()
                    if client.date_of_birth
                    else None,
                },
            )

        # Get first alert
        alert = alerts[0]

        alert_sent = False
        error_msg = None

        if request.force_send:
            # Actually send the email
            service = NotificationService(pool)
            email_to = request.test_email or client.email

            try:
                result = await service.process_alert(alert, email_to)
                alert_sent = result.success
                if not result.success:
                    error_msg = result.error_message
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Test email send failed: {e}", exc_info=True)

        return TestNotificationResponse(
            success=True,
            message=f"Test completed. {'Email sent to ' + (request.test_email or client.email) if alert_sent else 'Alert generated but not sent (force_send=false)'}"
            + (f" Error: {error_msg}" if error_msg else ""),
            alert_generated=True,
            alert_sent=alert_sent,
            alert_details={
                "type": alert.alert_type.value,
                "subject": alert.email_subject,
                "body_preview": alert.email_body[:200] + "..."
                if len(alert.email_body) > 200
                else alert.email_body,
            },
            client_info={
                "id": client.id,
                "name": client.full_name,
                "email": client.email,
                "language": client.preferred_language,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Test notification failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clients")
async def list_testable_clients(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50),
):
    """
    List clients that have passport/visa data for testing.
    Staging only.
    """
    from backend.app.core.config import settings

    if settings.environment == "production":
        raise HTTPException(status_code=403, detail="Test endpoint disabled in production")

    pool = await get_database_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                c.id,
                c.full_name,
                c.email,
                c.passport_expiry,
                c.date_of_birth,
                v.expiry_date as visa_expiry
            FROM clients c
            LEFT JOIN (
                SELECT DISTINCT ON (client_id)
                    client_id, expiry_date
                FROM client_documents
                WHERE document_category = 'immigration'
                AND expiry_date IS NOT NULL
                ORDER BY client_id, expiry_date DESC
            ) v ON v.client_id = c.id
            WHERE c.is_active = true
            AND (c.passport_expiry IS NOT NULL OR v.expiry_date IS NOT NULL)
            ORDER BY c.id
            LIMIT $1
            """,
            limit,
        )

    return {
        "clients": [
            {
                "id": row["id"],
                "name": row["full_name"],
                "email": row["email"],
                "has_passport": row["passport_expiry"] is not None,
                "has_visa": row["visa_expiry"] is not None,
                "has_dob": row["date_of_birth"] is not None,
            }
            for row in rows
        ],
        "count": len(rows),
    }
