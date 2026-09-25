"""Durable, bounded-retry email notices for manually sent portal messages."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from pydantic import EmailStr, TypeAdapter

from backend.app.services.internal_email import EmailProviderRejected, send_internal_email

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)
_ADDRESS = TypeAdapter(EmailStr)
_BODY = '<p>You have a new message from the Bali Zero team.</p><p><a href="https://my.balizero.com/portal/messages">Read your message</a></p>'

_CLAIM = """
WITH candidate AS (
    SELECT message_id, attempts >= 3 AS exhausted FROM portal_message_email_outbox
    WHERE (state = 'pending' AND next_attempt_at <= NOW())
       OR (state = 'sending' AND lease_until <= NOW())
    ORDER BY next_attempt_at, message_id
    FOR UPDATE SKIP LOCKED LIMIT 1
), claimed AS (
    UPDATE portal_message_email_outbox q
    SET state = 'sending', attempts = LEAST(attempts + 1, 3),
        first_attempt_at = COALESCE(first_attempt_at, NOW()),
        lease_until = NOW() + INTERVAL '2 minutes'
    FROM candidate WHERE q.message_id = candidate.message_id
    RETURNING q.*, candidate.exhausted
)
SELECT q.*, m.client_id, m.direction, m.is_system_generated,
       c.email, c.assigned_to, c.deleted_at,
       q.first_attempt_at < NOW() - INTERVAL '14 minutes' AS expired
FROM claimed q
JOIN portal_messages m ON m.id = q.message_id
JOIN clients c ON c.id = m.client_id
"""


async def _finish(
    pool: asyncpg.Pool, row: asyncpg.Record, state: str, error: str | None = None
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE portal_message_email_outbox
            SET state = $3, last_error = $4, lease_until = NULL,
                next_attempt_at = NOW() + $5,
                sent_at = CASE WHEN $3 = 'sent' THEN NOW() ELSE sent_at END
            WHERE message_id = $1 AND attempts = $2 AND state = 'sending' AND lease_until = $6
            """,
            row["message_id"],
            row["attempts"],
            state,
            error,
            timedelta(seconds=60 * 2 ** min(row["attempts"] - 1, 3)),
            row["lease_until"],
        )


async def deliver_one(pool: asyncpg.Pool) -> bool:
    """Claim durably before I/O; only the current lease may finish the row."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_CLAIM)
    if row is None:
        return False
    if row["expired"] or row["exhausted"]:
        # Brevo idempotency keys expire after 15 minutes. After a long crash,
        # do not guess whether an earlier provider request was accepted.
        await _finish(
            pool,
            row,
            "uncertain",
            "attempts_exhausted" if row["exhausted"] else "idempotency_window_expired",
        )
        logger.error("Portal email requires review: message_id=%s", row["message_id"])
        return True
    if (
        row["deleted_at"] is not None
        or row["direction"] != "team_to_client"
        or row["is_system_generated"]
    ):
        await _finish(pool, row, "failed", "message_ineligible")
        return True
    try:
        recipient = str(_ADDRESS.validate_python(row["email"]))
    except ValueError:
        await _finish(pool, row, "failed", "recipient_unavailable")
        return True
    lead = row["assigned_to"] or ""
    cc = [lead] if lead.lower().endswith("@balizero.com") else None
    try:
        await send_internal_email(
            to=recipient,
            subject="You have a new message in your Bali Zero portal",
            body=_BODY,
            cc=cc,
            email_type="portal_message",
            log_context=f"portal_message_id={row['message_id']}",
            raise_on_failure=True,
            idempotency_key=str(row["idempotency_key"]),
        )
    except Exception as exc:
        state = (
            "pending"
            if row["attempts"] < 3
            else ("failed" if isinstance(exc, EmailProviderRejected) else "uncertain")
        )
        await _finish(pool, row, state, type(exc).__name__)
        logger.warning(
            "Portal email attempt failed: message_id=%s state=%s", row["message_id"], state
        )
    else:
        await _finish(pool, row, "sent")
    return True


async def run_worker(pool: asyncpg.Pool) -> None:
    """A small dedicated consumer; database claims coordinate multiple hosts."""
    while True:
        try:
            for _ in range(10):
                if not await deliver_one(pool):
                    break
        except Exception as exc:
            logger.error("Portal email worker error: %s", type(exc).__name__)
        await asyncio.sleep(30)
