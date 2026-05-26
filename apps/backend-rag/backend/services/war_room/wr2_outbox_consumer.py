"""WR2 carousel events outbox consumer (Cluster C pattern).

Spec: research/wr2/2026-05-27-wr2-autonomous-workflow-spec.md §7
Migration: 199_wr2_carousel_events_outbox.sql

DeepSeek STRONG REJECT mitigation: events go to outbox (durable, idempotent
via consumed_by jsonb array), NOT direct PG NOTIFY. Each consumer (strategos,
learner, optional newsletter) polls outbox and marks itself consumed atomically.

Operator decision Q1: outbox polling pattern.
Operator decision Q4: learner refactor to outbox consumer (not direct read).
Operator decision Q7: newsletter independent — does NOT use this module.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg

logger = logging.getLogger("wr2.outbox_consumer")

EVENT_TABLE = "wr2_carousel_events_outbox"
DEFAULT_BATCH_SIZE = 20
DEFAULT_MAX_AGE_HOURS = 72

EventHandler = Callable[[dict[str, Any]], Awaitable[bool]]


async def claim_and_process_batch(
    conn: asyncpg.Connection,
    consumer_name: str,
    event_types: tuple[str, ...],
    handler: EventHandler,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_age_hours: int = DEFAULT_MAX_AGE_HOURS,
) -> dict[str, int]:
    """Claim unconsumed events + dispatch + atomically mark consumed.

    Idempotency: consumed_by jsonb array filter. Same consumer claiming
    twice is a no-op (FOR UPDATE SKIP LOCKED + array membership check).

    Returns dict {claimed, processed, failed, skipped_stale}.
    """
    stats = {"claimed": 0, "processed": 0, "failed": 0, "skipped_stale": 0}
    if not event_types:
        return stats

    # Transaction per batch: SELECT FOR UPDATE SKIP LOCKED + UPDATE on success
    async with conn.transaction():
        rows = await conn.fetch(
            f"""
            SELECT id, carousel_id, event_type, payload, created_at, consumed_by
              FROM {EVENT_TABLE}
             WHERE event_type = ANY($1::text[])
               AND NOT (consumed_by ? $2)
               AND created_at > NOW() - INTERVAL '{int(max_age_hours)} hours'
             ORDER BY created_at ASC
             LIMIT $3
             FOR UPDATE SKIP LOCKED
            """,
            list(event_types), consumer_name, batch_size,
        )
        stats["claimed"] = len(rows)

        for row in rows:
            event = {
                "id": row["id"],
                "carousel_id": row["carousel_id"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"],
                "created_at": row["created_at"],
            }
            try:
                ok = await handler(event)
            except Exception as exc:
                logger.exception(f"consumer={consumer_name} handler raised on event id={row['id']}: {exc}")
                stats["failed"] += 1
                continue

            if ok:
                await conn.execute(
                    f"""
                    UPDATE {EVENT_TABLE}
                       SET consumed_by = consumed_by || jsonb_build_array($2),
                           updated_at = NOW()
                     WHERE id = $1
                    """,
                    row["id"], consumer_name,
                )
                stats["processed"] += 1
            else:
                stats["failed"] += 1

    return stats


async def emit_event(
    conn: asyncpg.Connection,
    carousel_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> int | None:
    """Insert event into outbox. Returns row id."""
    try:
        row_id = await conn.fetchval(
            f"""
            INSERT INTO {EVENT_TABLE} (carousel_id, event_type, payload, consumed_by, created_at)
            VALUES ($1, $2, $3::jsonb, '[]'::jsonb, NOW())
            RETURNING id
            """,
            carousel_id, event_type, json.dumps(payload),
        )
    except (asyncpg.PostgresError, asyncpg.InterfaceError) as exc:
        logger.error(f"emit_event failed for carousel_id={carousel_id} type={event_type}: {exc}")
        return None
    return row_id
