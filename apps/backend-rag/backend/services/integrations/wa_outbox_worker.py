"""WA Meta Inbox outbox worker.

Drains the ``wa_outbox`` send-intent queue for the Meta WhatsApp Business
number +62 821-3465-159 (``phone_number_id`` = ``META_INBOX_PHONE_NUMBER_ID``).

Design (panel-approved spec 2026-06-03, sezione 3 "Worker"):

1. Reclaim stale claims (``claim_expires_at < now()`` → ``pending``) so a
   crashed worker does not park sends forever.
2. Claim one due ``pending`` row with ``FOR UPDATE SKIP LOCKED`` (single-flight,
   crash-safe lease).
3. If the row needs bot generation, re-check ``human_handling`` (the operator
   may have taken over since the webhook enqueued it) → if true, ABORT and drop
   the outbox row (bot must stay silent on a human-handled thread).
4. Enforce the Meta 24h customer-care window — if the last inbound customer
   message is older than 24h, fail the ledger row (free-text send not allowed).
5. Send via the existing ``whatsapp_service`` (hardcodes the target
   ``phone_number_id`` from settings — already the correct number), record the
   Meta ``wamid`` on the ledger row, apply any orphan ``wa_status_pending``
   receipt for that wamid, and mark the outbox row done. On HTTP failure,
   backoff with ``next_retry_at``; after ``MAX_ATTEMPTS`` mark ``failed``.

This module exposes a single callable, :func:`process_outbox_once`, which
processes at most one outbox row per call. A scheduler/loop that calls it every
~3s is intentionally left as a TODO hook (see module bottom) — wiring a new
LaunchAgent/background loop is out of scope for the backend feature and would
be decided with the operator.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Verified ground truth: the Meta WhatsApp Business number this inbox manages.
# settings.whatsapp_phone_number_id == this value == the send number, so the
# existing whatsapp_service sends from the correct number without parametrising.
META_INBOX_PHONE_NUMBER_ID = "1104946272705747"

# Lease window for a claimed outbox row. Must be safely larger than the
# Graph + LLM send timeout (spec: < 30s) to avoid a second worker double-sending.
CLAIM_LEASE_SECONDS = 120

# Send retry policy.
MAX_ATTEMPTS = 5
RETRY_BACKOFF_BASE_SECONDS = 30

# Meta free-text customer-care window.
CUSTOMER_WINDOW_HOURS = 24

# Type alias for the injected bot text generator. Given a thread row mapping it
# returns the reply text to send (or raises). Kept injectable so the worker has
# no hard dependency on the RAG orchestrator (and is trivially testable).
BotGenerateFn = Callable[[asyncpg.Record], Awaitable[str]]


def _extract_wamid(send_result: dict[str, Any] | None) -> str | None:
    """Pull the Meta message id (wamid) from a Graph send response."""
    if not isinstance(send_result, dict):
        return None
    messages = send_result.get("messages")
    if isinstance(messages, list) and messages:
        first = messages[0]
        if isinstance(first, dict):
            wamid = first.get("id")
            if isinstance(wamid, str) and wamid:
                return wamid
    return None


async def _apply_pending_status(conn: asyncpg.Connection, wamid: str) -> None:
    """Apply (and consume) an orphan status receipt that arrived before send.

    A delivered/read callback can land before the outbound row has its wamid
    committed (sezione 3). We stage those in ``wa_status_pending``; once the
    send commits the wamid, fold the staged status into the ledger row.
    """
    pending = await conn.fetchrow(
        "SELECT status, error FROM wa_status_pending WHERE meta_message_id = $1",
        wamid,
    )
    if pending is None:
        return

    await conn.execute(
        """
        UPDATE meta_inbox_messages
        SET status = $2,
            error = COALESCE($3, error)
        WHERE meta_message_id = $1
        """,
        wamid,
        pending["status"],
        pending["error"],
    )
    await conn.execute(
        "DELETE FROM wa_status_pending WHERE meta_message_id = $1",
        wamid,
    )
    logger.info("wa_outbox: applied staged status %s for wamid=%s", pending["status"], wamid)


async def process_outbox_once(
    pool: asyncpg.Pool,
    whatsapp_service: Any,
    bot_generate_fn: BotGenerateFn,
) -> str:
    """Process at most one ``wa_outbox`` row.

    Args:
        pool: asyncpg pool.
        whatsapp_service: object exposing ``async send_message(phone, text,
            reply_to_message_id=None)`` returning the Graph API response dict.
        bot_generate_fn: async callable producing the bot reply text for a
            thread (only invoked when ``needs_generation`` is true).

    Returns:
        A short status string describing what happened (for logging/metrics):
        ``"idle"`` (no due row), ``"sent"``, ``"aborted_human"``,
        ``"window_closed"``, ``"retry"``, ``"failed"``.
    """
    # 1. Reclaim stale claims (best-effort, outside the claim TX).
    await pool.execute(
        """
        UPDATE wa_outbox
        SET status = 'pending', claim_token = NULL, claimed_at = NULL,
            claim_expires_at = NULL
        WHERE status = 'claimed' AND claim_expires_at < NOW()
        """,
    )

    claim_token = uuid.uuid4()

    async with pool.acquire() as conn:
        # 2. Claim one due pending row. The SELECT ... FOR UPDATE SKIP LOCKED
        #    + same-TX UPDATE is the single-flight guarantee across workers.
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT id, thread_id, message_id, needs_generation, attempts
                FROM wa_outbox
                WHERE status = 'pending' AND next_retry_at <= NOW()
                ORDER BY next_retry_at, id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """,
            )
            if row is None:
                return "idle"

            await conn.execute(
                """
                UPDATE wa_outbox
                SET status = 'claimed', claim_token = $2, claimed_at = NOW(),
                    claim_expires_at = NOW() + ($3 * INTERVAL '1 second')
                WHERE id = $1
                """,
                row["id"],
                claim_token,
                CLAIM_LEASE_SECONDS,
            )

        outbox_id = row["id"]
        thread_id = row["thread_id"]
        message_id = row["message_id"]
        needs_generation = row["needs_generation"]
        attempts = row["attempts"]

        # Load the thread (human_handling gate + 24h window source).
        thread = await conn.fetchrow(
            """
            SELECT thread_id, counterpart_phone, human_handling,
                   last_customer_at
            FROM meta_inbox_threads
            WHERE thread_id = $1
            """,
            thread_id,
        )
        if thread is None:
            # Should not happen (FK), but never park the row.
            await conn.execute(
                "UPDATE wa_outbox SET status = 'failed' WHERE id = $1", outbox_id
            )
            await conn.execute(
                """
                UPDATE meta_inbox_messages
                SET status = 'failed', error = 'thread_missing'
                WHERE id = $1
                """,
                message_id,
            )
            logger.error("wa_outbox: thread %s missing for outbox %s", thread_id, outbox_id)
            return "failed"

        # 3. Bot replies: re-check human_handling (takeover may have flipped it).
        body_text: str
        if needs_generation:
            if thread["human_handling"]:
                # Operator took over — bot must stay silent. Drop the intent.
                await conn.execute(
                    "UPDATE wa_outbox SET status = 'failed' WHERE id = $1", outbox_id
                )
                await conn.execute(
                    """
                    UPDATE meta_inbox_messages
                    SET status = 'failed', error = 'aborted_human_takeover'
                    WHERE id = $1
                    """,
                    message_id,
                )
                logger.info(
                    "wa_outbox: aborted bot send for thread %s (human_handling=true)",
                    thread_id,
                )
                return "aborted_human"

            await conn.execute(
                "UPDATE meta_inbox_messages SET status = 'generating' WHERE id = $1",
                message_id,
            )
            await conn.execute(
                "UPDATE wa_outbox SET status = 'generating' WHERE id = $1", outbox_id
            )
            # bot_generate_fn may raise (transient RAG error, or — in the
            # human-send-only v1 — a NotImplementedError sentinel). Without this
            # guard the exception bubbles to the scheduler and the row is left
            # ORPHANED in 'generating' (reclaim only resets 'claimed' rows), so
            # it is never retried nor surfaced. Mirror the send retry/backoff
            # policy: retry with backoff up to MAX_ATTEMPTS, then mark failed.
            try:
                body_text = await bot_generate_fn(thread)
            except Exception as gen_exc:
                attempts += 1
                if attempts >= MAX_ATTEMPTS:
                    await conn.execute(
                        "UPDATE wa_outbox SET status = 'failed', attempts = $2 WHERE id = $1",
                        outbox_id,
                        attempts,
                    )
                    await conn.execute(
                        """
                        UPDATE meta_inbox_messages
                        SET status = 'failed', error = $2
                        WHERE id = $1
                        """,
                        message_id,
                        f"bot_generate_failed_after_{attempts}_attempts: {gen_exc}",
                    )
                    logger.error(
                        "wa_outbox: bot generation failed permanently "
                        "(outbox=%s thread=%s): %s",
                        outbox_id,
                        thread_id,
                        gen_exc,
                    )
                    return "failed"

                backoff = RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempts - 1))
                await conn.execute(
                    """
                    UPDATE wa_outbox
                    SET status = 'pending', attempts = $2,
                        next_retry_at = NOW() + ($3 * INTERVAL '1 second'),
                        claim_token = NULL, claimed_at = NULL, claim_expires_at = NULL
                    WHERE id = $1
                    """,
                    outbox_id,
                    attempts,
                    backoff,
                )
                await conn.execute(
                    "UPDATE meta_inbox_messages SET status = 'queued' WHERE id = $1",
                    message_id,
                )
                logger.warning(
                    "wa_outbox: bot generation failed (attempt %d/%d), retry in %ds "
                    "(outbox=%s): %s",
                    attempts,
                    MAX_ATTEMPTS,
                    backoff,
                    outbox_id,
                    gen_exc,
                )
                return "retry"

            await conn.execute(
                "UPDATE meta_inbox_messages SET body = $2 WHERE id = $1",
                message_id,
                body_text,
            )
        else:
            # Human send: the body is already on the ledger row.
            ledger = await conn.fetchrow(
                "SELECT body FROM meta_inbox_messages WHERE id = $1",
                message_id,
            )
            body_text = (ledger["body"] if ledger else None) or ""

        # 4. Enforce the Meta 24h customer-care window.
        window_open = await conn.fetchval(
            """
            SELECT last_customer_at IS NOT NULL
               AND NOW() - last_customer_at < ($2 * INTERVAL '1 hour')
            FROM meta_inbox_threads
            WHERE thread_id = $1
            """,
            thread_id,
            CUSTOMER_WINDOW_HOURS,
        )
        if not window_open:
            await conn.execute(
                "UPDATE wa_outbox SET status = 'failed' WHERE id = $1", outbox_id
            )
            await conn.execute(
                """
                UPDATE meta_inbox_messages
                SET status = 'failed', error = '24h_window_closed'
                WHERE id = $1
                """,
                message_id,
            )
            logger.info("wa_outbox: 24h window closed for thread %s", thread_id)
            return "window_closed"

        # 5. Send via Graph (whatsapp_service hardcodes the target number).
        await conn.execute(
            "UPDATE meta_inbox_messages SET status = 'sending' WHERE id = $1",
            message_id,
        )
        try:
            send_result = await whatsapp_service.send_message(
                phone=thread["counterpart_phone"],
                text=body_text,
                reply_to_message_id=None,
            )
        except Exception as exc:
            attempts += 1
            if attempts >= MAX_ATTEMPTS:
                await conn.execute(
                    "UPDATE wa_outbox SET status = 'failed', attempts = $2 WHERE id = $1",
                    outbox_id,
                    attempts,
                )
                await conn.execute(
                    """
                    UPDATE meta_inbox_messages
                    SET status = 'failed', error = $2
                    WHERE id = $1
                    """,
                    message_id,
                    f"send_failed_after_{attempts}_attempts: {exc}",
                )
                logger.error(
                    "wa_outbox: send failed permanently (outbox=%s thread=%s): %s",
                    outbox_id,
                    thread_id,
                    exc,
                )
                return "failed"

            backoff = RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempts - 1))
            await conn.execute(
                """
                UPDATE wa_outbox
                SET status = 'pending', attempts = $2,
                    next_retry_at = NOW() + ($3 * INTERVAL '1 second'),
                    claim_token = NULL, claimed_at = NULL, claim_expires_at = NULL
                WHERE id = $1
                """,
                outbox_id,
                attempts,
                backoff,
            )
            logger.warning(
                "wa_outbox: send failed (attempt %d/%d), retry in %ds (outbox=%s): %s",
                attempts,
                MAX_ATTEMPTS,
                backoff,
                outbox_id,
                exc,
            )
            return "retry"

        wamid = _extract_wamid(send_result)
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE meta_inbox_messages
                SET status = 'sent', meta_message_id = $2, sent_at = NOW()
                WHERE id = $1
                """,
                message_id,
                wamid,
            )
            await conn.execute(
                "UPDATE wa_outbox SET status = 'done' WHERE id = $1", outbox_id
            )
            # Fold any status receipt that raced ahead of the send commit.
            if wamid:
                await _apply_pending_status(conn, wamid)

        logger.info(
            "wa_outbox: sent (outbox=%s thread=%s wamid=%s)",
            outbox_id,
            thread_id,
            wamid,
        )
        return "sent"


# TODO(scheduler): a background loop calling process_outbox_once(pool,
# whatsapp_service, bot_generate_fn) every ~3s is required to drain the queue
# in production. It is intentionally NOT wired here — the choice of host
# (FastAPI lifespan asyncio task vs LaunchAgent vs WebhookProcessor sibling)
# is an operator/deploy decision. process_outbox_once is the unit of work; the
# loop just needs to call it, catch exceptions, and sleep ~3s between ticks.
