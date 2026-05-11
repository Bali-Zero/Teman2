"""Universal Outbox helper for the EventBus.

Foundation for the P0-2 replay-on-reconnect mechanism. EventBus uses
PostgreSQL LISTEN/NOTIFY (cicatrix: "EventBus is PG LISTEN/NOTIFY but
Symbiosis docs say Redis Streams (2026-04-29)"); pg_notify is volatile,
so any event published while the listener is reconnecting (5s window in
``event_bus.py:_RECONNECT_DELAY_S``) is silently lost.

This module records every publication in the ``events_outbox`` table
(migration 144) so the EventBus can replay missed events when its
listener comes back online.

Status (post phase-3, 2026-05-09):

* Phase 1 (PR #342, migration 144): ``publish()`` + ``replay_unconsumed()``
  callable, EventBus reconnect hook wired.
* Phase 2 (migration 146 + ``EventBus.emit_pg`` delegation): six DB-trigger
  functions refactored to write events_outbox FIRST, then pg_notify with
  ``_outbox_id`` injected.
* Phase 3 (this file as-shipped): ``replay_unconsumed()`` only acks rows
  AFTER ``dispatch_fn`` returns successfully — handler crash leaves the
  row unconsumed for next replay (at-least-once semantics). Consumers
  must dedupe via ``_outbox_id``. A daily ``prune_consumed(30)`` cron
  (LaunchAgent ``com.nuzantara.outbox-prune.daily``) keeps the table
  bounded.

Reference impl: ``apps/backend-rag/backend/services/bridge/outbox.py``
(generalised here — bridge_outbox is a different table for Pro/Air
sync; events_outbox is the universal EventBus durability layer).
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Allowed channel-name pattern: alphanumeric + underscore, 1-63 chars.
# Matches the existing PG_CHANNEL_MAP names in event_bus.py and Postgres'
# native identifier limit. Defense-in-depth: even though pg_notify($1, $2)
# parameterises the channel, we reject suspect names early so a typo
# never reaches the DB. See cicatrix scar (2026-04-29).
_CHANNEL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")

# Cap on a single replay batch — protects against memory blow-up after a
# long disconnect (e.g. days). The EventBus calls replay per-channel
# already, so 500 per channel is plenty.
_DEFAULT_REPLAY_BATCH_SIZE = 500


class InvalidChannelError(ValueError):
    """Raised when a channel name fails ``validate_channel`` checks."""


def validate_channel(channel: str) -> None:
    """Raise :class:`InvalidChannelError` if ``channel`` is not a safe identifier.

    Defense in depth: ``pg_notify($1, $2)`` already parameterises the
    channel so there is no SQL injection vector, but we still reject
    suspicious names early to avoid wasting a round-trip and to keep
    the contract narrow.
    """
    if not isinstance(channel, str) or not _CHANNEL_RE.match(channel):
        raise InvalidChannelError(
            f"channel name must match {_CHANNEL_RE.pattern}, got {channel!r}"
        )


async def publish(
    conn: asyncpg.Connection,
    channel: str,
    payload: dict[str, Any],
) -> int:
    """Insert ``payload`` into ``events_outbox`` and fire ``pg_notify``.

    Atomic with the caller's transaction: if ``conn`` is already inside
    a transaction and the caller rolls back, the INSERT and the
    NOTIFY both vanish (Postgres queues NOTIFY until COMMIT).

    The NOTIFY payload is the original ``payload`` dict augmented with
    ``_outbox_id`` so the consumer can call :func:`acknowledge` after
    successful processing.

    Args:
        conn: an asyncpg connection (may or may not be in a tx).
        channel: PG channel name; must satisfy :func:`validate_channel`.
        payload: JSON-serialisable dict.

    Returns:
        The new ``events_outbox.id`` (BIGSERIAL).

    Raises:
        InvalidChannelError: if ``channel`` is not a safe identifier.
    """
    validate_channel(channel)

    insert_payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    row = await conn.fetchrow(
        """
        INSERT INTO events_outbox (channel, payload)
        VALUES ($1, $2::jsonb)
        RETURNING id
        """,
        channel,
        insert_payload_json,
    )
    outbox_id = int(row["id"])

    # NOTIFY payload includes _outbox_id so consumers can ack idempotently.
    notify_payload = dict(payload)
    notify_payload["_outbox_id"] = outbox_id
    notify_payload_json = json.dumps(notify_payload, ensure_ascii=False, default=str)

    # Parameterised pg_notify — channel is a value, NOT a raw identifier.
    # Postgres treats $1 as a string literal here, no DDL interpolation.
    await conn.execute("SELECT pg_notify($1, $2)", channel, notify_payload_json)

    logger.debug(
        "events_outbox: published id=%d channel=%s bytes=%d",
        outbox_id,
        channel,
        len(notify_payload_json),
    )
    return outbox_id


async def acknowledge(
    conn: asyncpg.Connection,
    outbox_id: int,
    consumer_id: str | None = None,
) -> bool:
    """Mark an outbox row as consumed. Idempotent.

    Safe to call multiple times with the same ``outbox_id``: the
    ``WHERE consumed_at IS NULL`` clause guards against double-acks.

    Args:
        conn: asyncpg connection.
        outbox_id: id returned by :func:`publish`.
        consumer_id: optional diagnostic — which handler acked the row.

    Returns:
        True if the row transitioned from unconsumed to consumed,
        False if the row was already consumed or does not exist.
    """
    result = await conn.execute(
        """
        UPDATE events_outbox
           SET consumed_at = NOW(),
               consumer_id = COALESCE($2, consumer_id)
         WHERE id = $1
           AND consumed_at IS NULL
        """,
        outbox_id,
        consumer_id,
    )
    # asyncpg returns "UPDATE N" — check N == 1.
    if isinstance(result, str) and result.startswith("UPDATE "):
        try:
            return int(result.split()[1]) >= 1
        except (IndexError, ValueError):
            return False
    return False


async def replay_unconsumed(
    conn: asyncpg.Connection,
    dispatch_fn: Callable[[dict[str, Any]], Awaitable[None]],
    *,
    channel: str | None = None,
    max_age_minutes: int = 60,
    batch_size: int = _DEFAULT_REPLAY_BATCH_SIZE,
    consumer_id: str = "outbox_replay",
) -> int:
    """Re-dispatch unconsumed events to ``dispatch_fn`` and ack each on success.

    Called from the EventBus reconnect handler so events lost during a
    listener-disconnect window are not silently dropped.

    Phase-3 contract: each row is dispatched once, and acked only AFTER
    ``dispatch_fn`` returns successfully. If ``dispatch_fn`` raises, the
    exception is logged and the row stays unconsumed (retried on the
    next replay). At-least-once semantics — handlers must dedupe via
    ``_outbox_id`` for idempotency.

    Args:
        conn: asyncpg connection.
        dispatch_fn: async callable receiving the payload dict (with
            ``_outbox_id`` injected).
        channel: optional channel filter; if ``None``, replay all channels.
        max_age_minutes: skip rows older than this. Default 60 — long
            enough to cover a deploy window, short enough to avoid
            replaying days of stale events after a long outage.
        batch_size: cap on rows fetched in a single call.
        consumer_id: tag written into ``events_outbox.consumer_id`` on ack.

    Returns:
        Number of rows successfully acked.
    """
    if channel is not None:
        validate_channel(channel)

    where_clauses = [
        "consumed_at IS NULL",
        f"created_at > NOW() - INTERVAL '{int(max_age_minutes)} minutes'",
    ]
    params: list[Any] = []

    if channel is not None:
        where_clauses.append(f"channel = ${len(params) + 1}")
        params.append(channel)

    params.append(int(batch_size))
    limit_param_idx = len(params)

    sql = (
        "SELECT id, channel, payload "
        "FROM events_outbox "
        f"WHERE {' AND '.join(where_clauses)} "
        "ORDER BY id ASC "
        f"LIMIT ${limit_param_idx}"
    )

    rows = await conn.fetch(sql, *params)

    acked = 0
    for row in rows:
        outbox_id = int(row["id"])
        raw_payload = row["payload"]
        # asyncpg may return JSONB as already-decoded dict OR as str
        # depending on codec config. Normalise.
        if isinstance(raw_payload, str):
            try:
                payload_dict = json.loads(raw_payload)
            except json.JSONDecodeError as exc:
                logger.error(
                    "events_outbox: invalid JSON in row id=%d: %s", outbox_id, exc
                )
                continue
        elif isinstance(raw_payload, dict):
            payload_dict = dict(raw_payload)
        else:
            logger.error(
                "events_outbox: unexpected payload type %s for id=%d",
                type(raw_payload).__name__,
                outbox_id,
            )
            continue

        payload_dict["_outbox_id"] = outbox_id
        payload_dict["_replay"] = True

        try:
            await dispatch_fn(payload_dict)
        except Exception as exc:  # noqa: BLE001 — bubbling up would block replay
            logger.error(
                "events_outbox: dispatch failed for id=%d channel=%s: %s",
                outbox_id,
                row["channel"],
                exc,
                exc_info=True,
            )
            # Row stays unconsumed — retried next replay.
            continue

        if await acknowledge(conn, outbox_id, consumer_id=consumer_id):
            acked += 1

    if rows:
        logger.info(
            "events_outbox: replayed %d/%d rows (channel=%s, max_age=%dm)",
            acked,
            len(rows),
            channel or "<all>",
            max_age_minutes,
        )
    return acked


async def prune_consumed(
    conn: asyncpg.Connection,
    *,
    older_than_days: int = 30,
) -> int:
    """Delete consumed rows older than ``older_than_days``.

    Pending (unconsumed) rows are NEVER deleted by this function — they
    represent events that have not yet been processed. Use a separate
    dead-letter strategy if you need to garbage-collect old pendings.

    Returns:
        Number of rows deleted (parsed from asyncpg's "DELETE N" status).
    """
    days = int(older_than_days)
    sql = (
        "DELETE FROM events_outbox "
        "WHERE consumed_at IS NOT NULL "
        f"AND consumed_at < NOW() - INTERVAL '{days} days'"
    )
    result = await conn.execute(sql)
    if isinstance(result, str) and result.startswith("DELETE "):
        try:
            return int(result.split()[1])
        except (IndexError, ValueError):
            return 0
    return 0


async def get_unconsumed_count(
    conn: asyncpg.Connection,
    channel: str | None = None,
) -> int:
    """Diagnostic: count of unconsumed rows, optionally filtered by channel."""
    if channel is None:
        return int(
            await conn.fetchval(
                "SELECT COUNT(*) FROM events_outbox WHERE consumed_at IS NULL"
            )
        )
    validate_channel(channel)
    return int(
        await conn.fetchval(
            "SELECT COUNT(*) FROM events_outbox WHERE consumed_at IS NULL AND channel = $1",
            channel,
        )
    )


__all__ = [
    "InvalidChannelError",
    "acknowledge",
    "get_unconsumed_count",
    "prune_consumed",
    "publish",
    "replay_unconsumed",
    "validate_channel",
]
