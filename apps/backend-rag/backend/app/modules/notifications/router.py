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
from backend.app.utils.internal_api_auth import verify_internal_api_key

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


class SendEmailRequest(BaseModel):
    """Request body for sending a direct email."""

    to: str
    subject: str
    body: str
    cc: str | None = None


class SendEmailResponse(BaseModel):
    """Response from direct email send."""

    success: bool
    message: str


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
                """,
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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/status", response_model=StatusResponse)
async def get_notification_status(
    current_user: dict = Depends(get_current_user),
):
    """Get notification system status."""
    try:
        pool = await get_database_pool()

        async with pool.acquire() as conn:
            pending_count = await conn.fetchval(
                "SELECT COUNT(*) FROM notification_alerts WHERE status = 'pending'",
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
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/send-email", response_model=SendEmailResponse)
async def send_direct_email(
    request: SendEmailRequest,
    _auth: dict = Depends(verify_internal_api_key),
) -> SendEmailResponse:
    """
    Send email via best available channel.

    Routing:
    - @balizero.com recipients → Zoho SMTP (avoids intra-domain spoofing rejection)
    - External recipients → Brevo HTTP API (better deliverability + tracking)

    Auth: X-API-Key header.
    Sender is always zantara@balizero.com (alias of damar@balizero.com).
    """
    import os

    cc_list = [c.strip() for c in request.cc.split(",")] if request.cc else None

    # Route: intra-domain (@balizero.com) → Zoho SMTP, external → Brevo
    if request.to.endswith("@balizero.com"):
        result = await _send_via_zoho_smtp(request.to, request.subject, request.body, cc_list)
    else:
        result = await _send_via_brevo(request.to, request.subject, request.body, cc_list)

    if result:
        logger.info(f"Direct email sent to {request.to} — {request.subject!r}")
        return SendEmailResponse(success=True, message=f"Email sent to {request.to}")

    # Fallback: if primary fails, try the other channel
    logger.warning(f"Primary channel failed for {request.to}, trying fallback")
    if request.to.endswith("@balizero.com"):
        fallback = await _send_via_brevo(request.to, request.subject, request.body, cc_list)
    else:
        fallback = await _send_via_zoho_smtp(request.to, request.subject, request.body, cc_list)

    if fallback:
        logger.info(f"Email sent to {request.to} via fallback — {request.subject!r}")
        return SendEmailResponse(success=True, message=f"Email sent to {request.to} (fallback)")

    return SendEmailResponse(success=False, message="Both Zoho SMTP and Brevo failed")


async def _send_via_zoho_smtp(
    to_email: str, subject: str, body: str, cc_list: list[str] | None,
) -> bool:
    """Send via Zoho SMTP (for intra-domain @balizero.com delivery)."""
    try:
        from backend.app.modules.notifications.service import SMTPProvider

        provider = SMTPProvider()
        return await provider.send_email(
            to_email=to_email,
            subject=subject,
            html_body=body,
            from_email="zantara@balizero.com",
            from_name="Zantara",
            bcc=cc_list,
        )
    except Exception as e:
        logger.error(f"Zoho SMTP failed for {to_email}: {e}")
        return False


async def _send_via_brevo(
    to_email: str, subject: str, body: str, cc_list: list[str] | None,
) -> bool:
    """Send via Brevo HTTP API (for external delivery)."""
    import os

    import httpx

    api_key = os.getenv("SENDGRID_API_KEY", "")
    if not api_key:
        return False

    payload: dict = {
        "sender": {"email": "zantara@balizero.com", "name": "Zantara"},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": body,
    }
    if cc_list:
        payload["cc"] = [{"email": e} for e in cc_list]

    is_brevo = api_key.startswith("xkeysib-")
    url = "https://api.brevo.com/v3/smtp/email" if is_brevo else "https://api.sendgrid.com/v3/mail/send"
    headers = (
        {"api-key": api_key, "Content-Type": "application/json"}
        if is_brevo
        else {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    )

    if not is_brevo:
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": "zantara@balizero.com", "name": "Zantara"},
            "subject": subject,
            "content": [{"type": "text/html", "value": body}],
        }
        if cc_list:
            payload["personalizations"][0]["cc"] = [{"email": e} for e in cc_list]

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code in (200, 201, 202):
            return True
        logger.error(f"Brevo API error {resp.status_code}: {resp.text[:300]}")
        return False
    except Exception as e:
        logger.error(f"Brevo failed for {to_email}: {e}")
        return False


# Include test endpoints only in non-production environments
import os

if os.getenv("ENVIRONMENT", "development").lower() != "production":
    from backend.app.modules.notifications.test_endpoint import router as test_router

    router.include_router(test_router)

# Include admin router
from backend.app.modules.notifications.admin_router import router as admin_router

router.include_router(admin_router)
