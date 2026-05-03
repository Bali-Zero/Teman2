"""HR leave request email notifiers — pending + review notifications.

Both functions delegate the actual HTTP transport to
``backend.app.services.internal_email.send_internal_email``, which
centralizes the contract with the receiving Brevo adapter (cc as
comma-joined string, fire-and-forget semantics, 30s timeout).

These functions are pure formatters: they build the recipient list,
escape user-controlled values, render the HTML body, and hand off to
the shared client. They are expected to be scheduled via FastAPI
``BackgroundTasks`` from the request handler so the client never pays
the email network latency.
"""
from __future__ import annotations

from datetime import date
from html import escape
from typing import Literal

from backend.app.services.hr.hr_leave_routing import (
    build_notification_recipients,
    build_review_recipients,
)
from backend.app.services.internal_email import send_internal_email


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
    """Send an email to the supervisor when a leave request is created."""
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

    await send_internal_email(
        to=recipients["to"],
        cc=recipients["cc"] or None,
        subject=(
            f"Leave Request — {safe_name} "
            f"({total_days} {day_label})"
        ),
        body=html_body,
        log_context=f"hr_leave pending req={request_id}",
    )


async def notify_leave_request_reviewed(
    *,
    request_id: int,
    requester_email: str,
    requester_name: str,
    reviewer_email: str,
    reviewer_name: str,
    leave_type_name: str,
    start_date: date,
    end_date: date,
    total_days: int,
    action: Literal["approved", "rejected"],
    rejection_reason: str | None,
) -> None:
    """Send an email to the requester after their leave request is reviewed.

    For ``action="approved"`` ``rejection_reason`` is ignored. For
    ``action="rejected"`` the reason is rendered in the body when present.
    """
    recipients = build_review_recipients(
        requester_email=requester_email,
        reviewer_email=reviewer_email,
    )
    date_range = (
        start_date.isoformat()
        if start_date == end_date
        else f"{start_date.isoformat()} → {end_date.isoformat()}"
    )
    day_label = "day" if total_days == 1 else "days"

    # Escape user-controlled values
    safe_requester = escape(requester_name)
    safe_reviewer = escape(reviewer_name)
    safe_type = escape(leave_type_name)
    safe_reason = escape(rejection_reason) if rejection_reason else None

    verb = "approved" if action == "approved" else "rejected"
    headline = (
        f"<p>Your leave request has been <strong>{verb}</strong>"
        f" by {safe_reviewer}.</p>"
    )
    reason_block = (
        f"<p><strong>Reason for rejection:</strong> {safe_reason}</p>"
        if action == "rejected" and safe_reason
        else ""
    )

    html_body = (
        f"{headline}"
        f"<p><strong>Employee:</strong> {safe_requester}<br>"
        f"<strong>Type:</strong> {safe_type}<br>"
        f"<strong>Dates:</strong> {date_range}<br>"
        f"<strong>Duration:</strong> {total_days} {day_label}</p>"
        f"{reason_block}"
        f'<p><a href="https://kita.balizero.com/hr/leave">'
        f"View in HR Dashboard</a></p>"
    )

    await send_internal_email(
        to=recipients["to"],
        cc=recipients["cc"] or None,
        subject=f"Leave {verb.capitalize()} — {total_days} {day_label}",
        body=html_body,
        log_context=f"hr_leave reviewed req={request_id} action={action}",
    )
