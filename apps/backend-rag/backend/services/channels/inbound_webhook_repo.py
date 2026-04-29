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

    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO inbound_webhooks (channel, payload, dedup_key)
                VALUES ($1, $2::jsonb, $3)
                ON CONFLICT (channel, dedup_key) DO NOTHING
                RETURNING id
                """,
                channel,
                payload_json,
                dedup_key,
            )

            if row is None:
                # Duplicate was deduped at ON CONFLICT — nothing to wake up.
                logger.debug(
                    "inbound_webhooks: duplicate dedup_key=%s on channel=%s "
                    "(silently dropped)",
                    dedup_key,
                    channel,
                )
                return (None, False)

            new_id = int(row["id"])

            # Wake up the WebhookProcessor via the existing Outbox helper.
            # The PG NOTIFY is volatile, but the row is durable — the
            # processor's poll-fallback (5s) catches the row anyway if
            # the listener is disconnected.
            try:
                await events_outbox.publish(
                    conn,
                    channel=NOTIFY_CHANNEL,
                    payload={
                        "channel": channel,
                        "dedup_key": dedup_key,
                        "inbound_webhook_id": new_id,
                    },
                )
            except Exception as exc:  # noqa: BLE001 — never block the ack
                # Outbox failure must not break the ack — the row is in
                # inbound_webhooks and the processor will pick it up via
                # the 5s poll.
                logger.warning(
                    "inbound_webhooks: outbox notify failed for id=%d "
                    "channel=%s: %s",
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
            return (new_id, True)


__all__ = ["NOTIFY_CHANNEL", "persist"]
