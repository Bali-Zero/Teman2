"""Email audit trail + critical-failure Telegram alerts.

Every email the backend sends (Brevo direct, Brevo via internal_email, Zoho
fallback) writes a row to ``email_send_log`` (migration 126) before the
network call and updates it after. When a CRITICAL email type fails and
cannot be retried locally, the caller may call
:func:`notify_email_failure_critical` to page the owner via Telegram.

The single-writer principle — only this module touches ``email_send_log`` —
means the retry worker in ``email_health_monitor.py`` can reason about
state transitions deterministically.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

# Owner chat_id lives in CLAUDE.md §14 (TELEGRAM_OWNER_CHAT_ID=1125336968).
# We prefer the env var so tests can override with a stub chat_id.
_OWNER_CHAT_ID: str = os.getenv("TELEGRAM_OWNER_CHAT_ID", "1125336968")

# Email types treated as operationally critical. Failure on these triggers a
# Telegram alert immediately (bypassing the retry queue's 3-attempt wait).
CRITICAL_EMAIL_TYPES: frozenset[str] = frozenset({
    "waiting_docs_client",
    "waiting_docs_team",
    "completion_client",
    "completion_team",
    "hr_bonus",
    "invoice_client",
    "welcome",
})

# Email types whose body cannot be reconstructed at retry time
# (personalized HTML, document URLs, brochure attachments). The retry
# worker would produce a "[RETRY] original subject was X" stub — a
# confusing meta-email from the client's point of view. For these types,
# a first failure is escalated directly to the owner via Telegram and
# the row is marked `retry_after=NULL` so `check_and_retry_failed_emails`
# never touches it. `escalate_unrecoverable` picks it up on the next
# monitor pass. Team-facing and stateless notifications (hr_bonus,
# waiting_docs_team, completion_team, invoice_client, cron_*) are
# acceptable to retry because a resent plain notification still conveys
# the actionable content.
NON_RESURRECTABLE_EMAIL_TYPES: frozenset[str] = frozenset({
    "waiting_docs_client",
    "completion_client",
    "welcome",
})

# Retry schedule: 1h after first failure, 4h after second, escalate after third.
_RETRY_BACKOFF = (
    timedelta(hours=1),
    timedelta(hours=4),
)


async def log_email_attempt(
    pool: asyncpg.Pool,
    *,
    email_type: str,
    to_email: str,
    subject: str | None = None,
    practice_id: int | None = None,
    client_id: int | None = None,
    attempt_number: int = 1,
    payload_cache: dict[str, Any] | None = None,
) -> int | None:
    """Insert a 'sending' row immediately before the network call.

    Returns the row id; caller passes it back to :func:`record_email_result`.
    If DB insert fails, returns None and the caller proceeds without audit —
    the email attempt itself is not gated on audit success.
    """
    try:
        async with pool.acquire() as conn:
            row_id = await conn.fetchval(
                """
                INSERT INTO email_send_log
                    (email_type, practice_id, client_id, to_email,
                     subject, status, attempt_number, payload_cache)
                VALUES ($1, $2, $3, $4, $5, 'sending', $6, $7::jsonb)
                RETURNING id
                """,
                email_type,
                practice_id,
                client_id,
                to_email,
                (subject or "")[:500],
                attempt_number,
                json.dumps(payload_cache) if payload_cache is not None else None,
            )
            return int(row_id) if row_id is not None else None
    except Exception as exc:
        logger.warning("email_audit: log_email_attempt failed: %s", exc)
        return None


async def record_email_result(
    pool: asyncpg.Pool,
    row_id: int | None,
    *,
    status: str,
    provider: str | None = None,
    error_message: str | None = None,
) -> None:
    """Update the 'sending' row with terminal status.

    status ∈ {'sent','failed','skipped_idempotent'}. On 'failed', computes
    ``retry_after`` via :data:`_RETRY_BACKOFF`. If ``row_id`` is None
    (audit insert failed earlier), this is a no-op.
    """
    if row_id is None:
        return
    if status not in {"sent", "failed", "skipped_idempotent"}:
        logger.warning("email_audit: invalid status %r, coercing to failed", status)
        status = "failed"

    retry_after: datetime | None = None
    if status == "failed":
        # Read current attempt_number + email_type to decide next retry window.
        # Non-resurrectable types skip retry entirely — retry_after stays
        # None and escalate_unrecoverable() picks them up directly.
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT attempt_number, email_type FROM email_send_log WHERE id = $1",
                    row_id,
                )
                if row:
                    attempt_n = row["attempt_number"]
                    et = row["email_type"]
                    if et in NON_RESURRECTABLE_EMAIL_TYPES:
                        # leave retry_after=None → escalated on next monitor pass
                        pass
                    elif attempt_n and attempt_n <= len(_RETRY_BACKOFF):
                        retry_after = datetime.now(tz=timezone.utc) + _RETRY_BACKOFF[attempt_n - 1]
                        # attempt 3 = no more retries; retry_after stays None →
                        # escalate_unrecoverable() will pick it up.
        except Exception as exc:
            logger.warning("email_audit: could not resolve attempt_n for %d: %s", row_id, exc)

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE email_send_log
                   SET status = $2,
                       provider = COALESCE($3, provider),
                       error_message = $4,
                       sent_at = CASE WHEN $2 = 'sent' THEN NOW() ELSE sent_at END,
                       retry_after = $5
                 WHERE id = $1
                """,
                row_id,
                status,
                provider,
                (error_message or "")[:4000] if error_message else None,
                retry_after,
            )
    except Exception as exc:
        logger.warning("email_audit: record_email_result failed for %d: %s", row_id, exc)


def notify_email_failure_critical(
    *,
    email_type: str,
    to_email: str,
    subject: str | None,
    practice_id: int | None,
    error: str,
) -> None:
    """Synchronous Telegram page for a critical-email failure.

    Uses urllib (not httpx) because callers are already deep in the send path
    and shouldn't spawn an async client. Errors are swallowed — a failed
    Telegram ping must not cascade into the caller's retry logic.
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        logger.warning(
            "email_audit: TELEGRAM_BOT_TOKEN not set; skipping alert for %s → %s",
            email_type,
            to_email,
        )
        return

    practice_fragment = f" (practice #{practice_id})" if practice_id else ""
    short_subj = (subject or "").strip()[:120]
    short_err = error.strip().replace("\n", " ")[:400]

    # Tell the operator whether to wait for retry or act immediately.
    # Non-resurrectable types (personalized HTML / attachments) bypass the
    # retry queue — a stub "[RETRY] original subject was X" email would
    # confuse the client, so record_email_result leaves retry_after=None
    # and escalate_unrecoverable pages again on the next monitor pass.
    if email_type in NON_RESURRECTABLE_EMAIL_TYPES:
        footer = "Not queued for retry (personalized body) — manual recovery required."
    else:
        footer = "Queued for retry. Check `email_send_log` if it escalates."

    text = (
        "🚨 *Email delivery failure* — critical path\n\n"
        f"*Type:* `{email_type}`{practice_fragment}\n"
        f"*To:* `{to_email}`\n"
        f"*Subject:* {short_subj}\n"
        f"*Error:* `{short_err}`\n\n"
        f"{footer}"
    )

    try:
        data = urllib.parse.urlencode(
            {"chat_id": _OWNER_CHAT_ID, "text": text, "parse_mode": "Markdown"},
        ).encode()
        urllib.request.urlopen(  # noqa: S310 — api.telegram.org is a known URL
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data,
            timeout=10,
        )
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.warning("email_audit: Telegram alert failed: %s", exc)


def is_critical(email_type: str) -> bool:
    """Return True iff a failure of ``email_type`` should page immediately."""
    return email_type in CRITICAL_EMAIL_TYPES
