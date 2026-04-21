"""Shared client for the internal Brevo email adapter.

The Nuzantara backend exposes a notifications endpoint at
``/api/notifications/send-email`` (Pydantic model ``SendEmailRequest`` in
``backend/app/modules/notifications/router.py``) which routes outbound mail
through Brevo. Multiple modules need to send emails through this adapter
(HR notifications, CRM notifiers, attendance ultimatums, bonus alerts);
this module centralizes the wire format so the schema contract — in
particular ``cc`` as a comma-joined string, NOT a list — cannot drift.

History:
- Same scar fixed twice already: commits 08c4df17c (attendance_monitor.py)
  and 3dffb6e6e (hr_leave_notifier.py). Both regressed because the receiving
  Pydantic model declares ``cc: str | None`` and rejects list payloads with
  422. Centralizing here removes the duplication that enabled the recurrence.
- 2026-04-21: added ``email_type`` / ``pool`` kwargs for ``email_send_log``
  audit trail (migration 126). Critical email types (see
  ``email_audit.CRITICAL_EMAIL_TYPES``) additionally page the owner via
  Telegram on failure. Audit is opt-in per call — omitting ``pool`` keeps
  the legacy fire-and-forget behavior bit-for-bit identical.

Semantics:
- Fire-and-forget: ``send_internal_email`` catches every exception and logs a
  warning. It NEVER raises unless ``raise_on_failure=True``. When ``pool``
  and ``email_type`` are provided, failures are also persisted so the retry
  worker can re-attempt delivery.
- Schedule via FastAPI ``BackgroundTasks`` if invoked from a request handler,
  so the client does not pay the network latency.

Configuration:
- ``INTERNAL_EMAIL_API_URL`` env var (default points at the Fly production app)
- ``NUZANTARA_API_KEY`` env var for the ``X-API-Key`` header
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from backend.services.notifications.email_audit import (
    is_critical,
    log_email_attempt,
    notify_email_failure_critical,
    record_email_result,
)
from backend.services.notifications.email_http import get_email_client

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "")


async def send_internal_email(
    *,
    to: str,
    subject: str,
    body: str,
    cc: list[str] | None = None,
    log_context: str | None = None,
    raise_on_failure: bool = False,
    email_type: str | None = None,
    pool: asyncpg.Pool | None = None,
    practice_id: int | None = None,
    client_id: int | None = None,
) -> None:
    """Send an email through the internal Brevo adapter.

    Fire-and-forget by default: catches every exception, logs a warning,
    never raises. Pass ``raise_on_failure=True`` to propagate exceptions
    instead — useful when the caller has its own fallback transport
    (e.g. Zoho) and needs to detect Brevo failures.

    Args:
        to: primary recipient address
        subject: email subject (already prepared by the caller, no further
            escaping is performed)
        body: HTML body (already escaped by the caller)
        cc: list of CC addresses; joined with ", " before sending and omitted
            from the payload entirely when empty/None. The receiving
            ``SendEmailRequest`` Pydantic model declares ``cc: str | None``
            and would reject a list payload with 422.
        log_context: optional short string included in success/failure log
            lines so the caller can correlate the email with its source (e.g.
            ``"hr_leave req=42"`` or ``"crm bonus practice=99"``).
        raise_on_failure: when True, re-raise after logging instead of
            swallowing. Default False (fire-and-forget).
        email_type: audit classification (e.g. ``"hr_bonus"``,
            ``"cron_visa"``). Required if ``pool`` is provided. If present in
            :data:`CRITICAL_EMAIL_TYPES`, failures also page via Telegram.
        pool: if provided alongside ``email_type``, writes pre/post audit
            rows to ``email_send_log`` so the retry worker can recover.
        practice_id / client_id: correlation keys for audit & dashboard.
    """
    audit_enabled = pool is not None and email_type is not None
    row_id: int | None = None

    if audit_enabled:
        row_id = await log_email_attempt(
            pool,  # type: ignore[arg-type]
            email_type=email_type,  # type: ignore[arg-type]
            to_email=to,
            subject=subject,
            practice_id=practice_id,
            client_id=client_id,
        )

    try:
        payload: dict[str, str] = {
            "to": to,
            "subject": subject,
            "body": body,
        }
        if cc:
            payload["cc"] = ", ".join(cc)

        client = await get_email_client()
        response = await client.post(
            _EMAIL_API_URL,
            headers={"X-API-Key": _EMAIL_API_KEY},
            json=payload,
        )
        response.raise_for_status()

        logger.info(
            "Internal email sent: to=%s cc=%s context=%s",
            to,
            payload.get("cc", ""),
            log_context or "",
        )
        if audit_enabled:
            await record_email_result(
                pool,  # type: ignore[arg-type]
                row_id,
                status="sent",
                provider="brevo",
            )
    except Exception as e:
        logger.warning(
            "Internal email failed (context=%s): %s",
            log_context or "",
            e,
        )
        if audit_enabled:
            await record_email_result(
                pool,  # type: ignore[arg-type]
                row_id,
                status="failed",
                provider="brevo",
                error_message=str(e),
            )
            if is_critical(email_type):  # type: ignore[arg-type]
                notify_email_failure_critical(
                    email_type=email_type,  # type: ignore[arg-type]
                    to_email=to,
                    subject=subject,
                    practice_id=practice_id,
                    error=str(e),
                )
        if raise_on_failure:
            raise
