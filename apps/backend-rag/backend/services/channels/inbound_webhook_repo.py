"""Inbound webhook persistence helper.

Single ack-first persistence point shared by all four channel routers
(whatsapp, telegram, instagram, twitter). Reuses the existing Outbox
helper from ``services/events/outbox.py`` (P0-2 phase 1, PR #342) to
also publish a notification on the ``inbound_webhook_queued`` channel
so the ``WebhookProcessor`` can wake immediately via PG LISTEN.

P0-6 from zero-crash audit 2026-04-29.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import asyncpg

from backend.services.events import outbox as events_outbox

logger = logging.getLogger(__name__)

# Channel name used by WebhookProcessor LISTEN. Must satisfy the
# ``validate_channel`` regex in services/events/outbox.py.
NOTIFY_CHANNEL = "inbound_webhook_queued"


async def persist(
    pool: asyncpg.Pool,
    *,
    channel: str,
    dedup_key: str,
    payload: dict[str, Any],
    recovery_after_seconds: int = 0,
) -> tuple[int | None, bool]:
    """Persist a verified inbound webhook payload.

    Atomic flow inside a single transaction:

    1. INSERT INTO inbound_webhooks (channel, payload, dedup_key)
       ON CONFLICT (channel, dedup_key) DO NOTHING — idempotent on
       Meta/Twitter retries that arrive before the original ack.
    2. If the row was inserted, publish to the Outbox channel
       ``inbound_webhook_queued`` so the WebhookProcessor wakes up
       immediately via PG LISTEN. The payload includes the new row id
       and the channel name; the WebhookProcessor uses these as a hint
       and still drains the table by SELECT (NOTIFY is a wake-up,
       not the source of truth).

    Args:
        pool: asyncpg.Pool from get_database().
        channel: "whatsapp" | "telegram" | "instagram" | "twitter".
        dedup_key: per-channel idempotency key (Meta message_id, Telegram
            f"telegram-{update_id}", Twitter direct_message_events[0].id).
        payload: full webhook body (already signature-verified).
        recovery_after_seconds: optional grace window before the durable
            recovery worker may claim this row. Use this when the router also
            schedules a fast-path background task, to avoid duplicate replies.

    Returns:
        (row_id, inserted):
            row_id   — id of the inbound_webhooks row, or None if a duplicate
                       was dropped at ON CONFLICT.
            inserted — True if INSERT actually wrote a new row, False if
                       a duplicate was dropped.

    The router can ignore the return value — the contract is "persist or
    deduplicate, then ack 200 OK". The returned tuple is for logging /
    metrics only.
    """
    if not channel:
        raise ValueError("channel must be a non-empty string")
    if not dedup_key:
        raise ValueError("dedup_key must be a non-empty string")

    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    recovery_delay = max(0, int(recovery_after_seconds))

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO inbound_webhooks (
                    channel,
                    payload,
                    dedup_key,
                    next_retry_at
                )
                VALUES (
                    $1,
                    $2::jsonb,
                    $3,
                    CASE
                        WHEN $4::integer > 0
                        THEN NOW() + ($4::integer * INTERVAL '1 second')
                        ELSE NULL
                    END
                )
                ON CONFLICT (channel, dedup_key) DO NOTHING
                RETURNING id
                """,
                channel,
                payload_json,
                dedup_key,
                recovery_delay,
            )

            if row is None:
                # Duplicate was deduped at ON CONFLICT — nothing to wake up.
                logger.debug(
                    "inbound_webhooks: duplicate dedup_key=%s on channel=%s (silently dropped)",
                    dedup_key,
                    channel,
                )
                return (None, False)

            new_id = int(row["id"])

            # Wake up the WebhookProcessor via the existing Outbox helper.
            # The PG NOTIFY is volatile, but the inbound_webhooks row is durable
            # — the processor's poll-fallback (5s) catches the row anyway if the
            # listener is disconnected. publish() stays INSIDE the transaction so
            # the wake-up row + NOTIFY are atomic with the INSERT (roll back
            # together if the INSERT is undone).
            outbox_id: int | None = None
            try:
                outbox_id = await events_outbox.publish(
                    conn,
                    channel=NOTIFY_CHANNEL,
                    payload={
                        "channel": channel,
                        "dedup_key": dedup_key,
                        "inbound_webhook_id": new_id,
                    },
                )
            except Exception as exc:
                # Outbox publish failure must not break the ack-first contract —
                # the row is in inbound_webhooks and the processor's 5s poll
                # picks it up. Swallow so the INSERT still commits.
                logger.warning(
                    "inbound_webhooks: outbox notify failed for id=%d channel=%s: %s",
                    new_id,
                    channel,
                    exc,
                )

            logger.debug(
                "inbound_webhooks: persisted id=%d channel=%s dedup_key=%s",
                new_id,
                channel,
                dedup_key,
            )

        # ── transaction committed ──
        # Best-effort ack of the wake-up row, OUTSIDE the transaction so a failed
        # ack can NEVER roll back the just-committed inbound_webhooks row. Nothing
        # else acks the `inbound_webhook_queued` channel, so without this
        # events_outbox grows unbounded (188+ orphans as of 2026-06-05;
        # replay_unconsumed's 60-min window never reclaims them, prune_consumed
        # only touches consumed rows). The durable truth is the inbound_webhooks
        # row (drained by the WebhookProcessor 5s poll regardless), so
        # pre-consuming the outbox row only forfeits replay — which is redundant
        # with the poll for this channel. consumer_id is per-channel for a
        # readable events_outbox audit trail.
        if outbox_id is not None:
            try:
                await events_outbox.acknowledge(
                    conn, outbox_id, consumer_id=f"inbound_webhook_persist:{channel}"
                )
            except Exception as exc:
                logger.warning(
                    "inbound_webhooks: outbox ack failed (non-fatal) for id=%d channel=%s: %s",
                    new_id,
                    channel,
                    exc,
                )

        return (new_id, True)


async def mark_processed(
    pool: asyncpg.Pool,
    *,
    channel: str,
    dedup_key: str,
    error_message: str | None = None,
) -> bool:
    """Mark a persisted inbound webhook as processed after fast-path handling."""
    if not channel:
        raise ValueError("channel must be a non-empty string")
    if not dedup_key:
        raise ValueError("dedup_key must be a non-empty string")

    async with pool.acquire() as conn:
        status = await conn.execute(
            """
            UPDATE inbound_webhooks
            SET processed_at = NOW(),
                error_message = COALESCE($3, error_message)
            WHERE channel = $1
              AND dedup_key = $2
              AND processed_at IS NULL
            """,
            channel,
            dedup_key,
            error_message,
        )

    return status.upper().endswith(" 1")


__all__ = ["NOTIFY_CHANNEL", "mark_processed", "persist"]
