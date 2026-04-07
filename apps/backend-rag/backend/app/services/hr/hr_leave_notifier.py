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
        reason_block = (
            f"<p><strong>Reason:</strong> {reason}</p>" if reason else ""
        )

        html_body = (
            f"<p>A leave request needs your review.</p>"
            f"<p><strong>Employee:</strong> {requester_name} ({requester_email})<br>"
            f"<strong>Type:</strong> {leave_type_name}<br>"
            f"<strong>Dates:</strong> {date_range}<br>"
            f"<strong>Duration:</strong> {total_days} {day_label}</p>"
            f"{reason_block}"
            f'<p><a href="https://kita.balizero.com/hr/leave">'
            f"Review in HR Dashboard</a></p>"
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _EMAIL_API_URL,
                headers={"X-API-Key": _EMAIL_API_KEY},
                json={
                    "to": recipients["to"],
                    "cc": recipients["cc"],
                    "subject": (
                        f"Leave Request — {requester_name} "
                        f"({total_days} {day_label})"
                    ),
                    "body": html_body,
                },
            )
            response.raise_for_status()

        logger.info(
            "Leave notification sent: req=%s to=%s cc=%s",
            request_id,
            recipients["to"],
            ",".join(recipients["cc"]),
        )
    except Exception as e:
        logger.warning(
            "Leave notification failed for request %s: %s", request_id, e,
        )
