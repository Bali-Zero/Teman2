"""HR leave request email notifier — Brevo via internal HTTP endpoint.

Consistent with backend/services/crm/notifiers.py pattern: posts to the
internal notifications/send-email endpoint which routes to Brevo. The URL
can be overridden with the INTERNAL_EMAIL_API_URL env var for local/staging.

Fire-and-forget semantics: all exceptions are caught and logged as warnings.
The caller (router) schedules this via fastapi.BackgroundTasks so the
HTTP request handler returns immediately without waiting for the email.
"""
from __future__ import annotations

import logging
import os
from datetime import date
from html import escape

import httpx

from backend.app.services.hr.hr_leave_routing import (
    build_notification_recipients,
)

logger = logging.getLogger(__name__)

_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "")


async def notify_leave_request_pending(
    *,
    request_id: int,
    requester_email: str,
    requester_name: str,
    leave_type_name: str,
    start_date: date,
    end_date: date,
    total_days: int,
    reason: str | None,
) -> None:
    """Send an email to the supervisor when a leave request is created.

    Fire-and-forget: logs warning on failure, never raises. Expected to be
    scheduled via fastapi.BackgroundTasks so the client does not pay the
    email network latency.
    """
    try:
        recipients = build_notification_recipients(requester_email)
        date_range = (
            start_date.isoformat()
            if start_date == end_date
            else f"{start_date.isoformat()} → {end_date.isoformat()}"
        )
        day_label = "day" if total_days == 1 else "days"

        # Escape user-controlled values to prevent HTML injection in mail clients
        safe_name = escape(requester_name)
        safe_email = escape(requester_email)
        safe_type = escape(leave_type_name)
        safe_reason = escape(reason) if reason else None
        reason_block = (
            f"<p><strong>Reason:</strong> {safe_reason}</p>" if safe_reason else ""
        )

        html_body = (
            f"<p>A leave request needs your review.</p>"
            f"<p><strong>Employee:</strong> {safe_name} ({safe_email})<br>"
            f"<strong>Type:</strong> {safe_type}<br>"
            f"<strong>Dates:</strong> {date_range}<br>"
            f"<strong>Duration:</strong> {total_days} {day_label}</p>"
            f"{reason_block}"
            f'<p><a href="https://kita.balizero.com/hr/leave">'
            f"Review in HR Dashboard</a></p>"
        )

        # cc must be a comma-joined string (Pydantic SendEmailRequest expects
        # str | None, NOT list[str]). Same scar as commit 08c4df17c.
        payload: dict[str, str] = {
            "to": recipients["to"],
            "subject": (
                f"Leave Request — {safe_name} "
                f"({total_days} {day_label})"
            ),
            "body": html_body,
        }
        if recipients["cc"]:
            payload["cc"] = ", ".join(recipients["cc"])

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _EMAIL_API_URL,
                headers={"X-API-Key": _EMAIL_API_KEY},
                json=payload,
            )
            response.raise_for_status()

        logger.info(
            "Leave notification sent: req=%s to=%s cc=%s",
            request_id,
            recipients["to"],
            payload.get("cc", ""),
        )
    except Exception as e:
        logger.warning(
            "Leave notification failed for request %s: %s", request_id, e,
        )
