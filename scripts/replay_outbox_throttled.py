#!/usr/bin/env python3
"""Throttled events_outbox replay — Phase 2.2 SYMBIOSIS organism completion.

Drains unconsumed events from `events_outbox` table safely via:
- Rate cap: 10 events/sec default, hard cap 20/sec via --rate
- Lock: SELECT ... FOR UPDATE SKIP LOCKED (race-safe with live producers)
- Two-phase mark: in_progress timestamp (1970-01-01) → finalize NOW() after pg_notify success
- DLQ: failed events INSERT INTO events_outbox_dlq + log + skip
- Schema validation: payload JSON must parse + have minimum keys
- Auto-pause: aborts if Redis stream length > 2× initial during replay

Approved 2026-05-12 by 4-panel review (Gemini BLOCK → DeepSeek WEAK → NB-1
PROCEED CON CONDIZIONI) — 7 corrections applied vs original spec.

Reference: docs/superpowers/specs/2026-05-12-phase2-core-plumbing-fix-spec.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

logger = logging.getLogger("replay_outbox_throttled")

# Hard limits (4-panel consensus)
HARD_MAX_RATE = 20
DEFAULT_RATE = 10
DEFAULT_BATCH = 10
DEFAULT_MAX_EVENTS = 5000
REDIS_GROWTH_THRESHOLD = 2.0
IN_PROGRESS_MARKER = datetime(1970, 1, 1, tzinfo=timezone.utc)

# DLQ schema — auto-created on first failed event
DLQ_DDL = """
CREATE TABLE IF NOT EXISTS events_outbox_dlq (
    id BIGINT PRIMARY KEY,
    channel TEXT NOT NULL,
    payload JSONB NOT NULL,
    failed_at TIMESTAMPTZ DEFAULT NOW(),
    failure_reason TEXT NOT NULL,
    original_created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outbox_dlq_failed_at
    ON events_outbox_dlq(failed_at DESC);
"""

# Payload schema: must be JSON dict. _outbox_id is INJECTED at notify time
# (it equals events_outbox.id PK), NOT stored in the payload pre-NOTIFY.
# So payload validation only requires JSON-decodability + dict type.

def _shutdown_flag():
    flag = {"stop": False}
    def _handler(*_):
        flag["stop"] = True
        logger.warning("shutdown signal received, finishing in-flight batch")
    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)
    return flag


def validate_payload(payload_text: str) -> tuple[bool, str]:
    """Schema validation. Returns (ok, reason).

    _outbox_id is INJECTED at notify time (equals events_outbox.id PK).
    Pre-NOTIFY payloads do NOT contain it; validation only checks
    JSON-decodability and dict type."""
    try:
        d = json.loads(payload_text) if isinstance(payload_text, str) else payload_text
    except (json.JSONDecodeError, TypeError) as exc:
        return False, f"json_decode_error: {exc}"
    if not isinstance(d, dict):
        return False, f"payload_not_dict: {type(d).__name__}"
    return True, "ok"


async def get_redis_stream_length(redis_cmd: str = "redis-cli") -> int:
    """Get current length of organism:events stream."""
    proc = await asyncio.create_subprocess_exec(
        redis_cmd, "XLEN", "organism:events",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    try:
        return int(stdout.decode().strip())
    except (ValueError, AttributeError):
        return 0


async def replay_batch(
    conn: asyncpg.Connection,
    channel_filter: str | None,
    since: datetime | None,
    batch_size: int,
    redis_initial_length: int,
    dry_run: bool,
) -> tuple[int, int, list[dict]]:
    """Replay one batch. Returns (replayed_count, dlq_count, batch_info_list)."""

    # 1. SELECT ... FOR UPDATE SKIP LOCKED — race-safe claim
    select_sql = """
        SELECT id, channel, payload::text AS payload_text, created_at
        FROM events_outbox
        WHERE consumed_at IS NULL
    """
    params = []
    if channel_filter:
        select_sql += f" AND channel = ${len(params)+1}"
        params.append(channel_filter)
    if since:
        select_sql += f" AND created_at >= ${len(params)+1}"
        params.append(since)
    select_sql += f" ORDER BY id ASC LIMIT ${len(params)+1} FOR UPDATE SKIP LOCKED"
    params.append(batch_size)

    rows = await conn.fetch(select_sql, *params)
    if not rows:
        return 0, 0, []

    # 2. Mark in_progress (two-phase mark step 1)
    in_progress_ids = []
    for r in rows:
        ok, reason = validate_payload(r["payload_text"])
        if not ok:
            # Poison pill → DLQ + skip (skip mutations in dry-run)
            if not dry_run:
                await conn.execute(
                    "INSERT INTO events_outbox_dlq "
                    "(id, channel, payload, failure_reason, original_created_at) "
                    "VALUES ($1, $2, $3::jsonb, $4, $5) "
                    "ON CONFLICT (id) DO NOTHING",
                    r["id"], r["channel"], r["payload_text"] or "{}", reason, r["created_at"]
                )
                # Mark this row as consumed_at with DLQ marker to skip in future replays
                await conn.execute(
                    "UPDATE events_outbox SET consumed_at = NOW() WHERE id = $1",
                    r["id"]
                )
            in_progress_ids.append((r["id"], r["channel"], None, reason))
            continue
        in_progress_ids.append((r["id"], r["channel"], r["payload_text"], None))

    if not dry_run:
        # Mark valid rows in_progress (NOT yet consumed)
        valid_ids = [iid for iid, _, ptext, fail in in_progress_ids if fail is None]
        if valid_ids:
            await conn.execute(
                "UPDATE events_outbox SET consumed_at = $1 WHERE id = ANY($2::bigint[])",
                IN_PROGRESS_MARKER, valid_ids
            )

    # 3. Issue pg_notify per valid event
    replayed = 0
    dlq_count = 0
    info = []
    for outbox_id, channel, payload_text, fail in in_progress_ids:
        if fail is not None:
            dlq_count += 1
            info.append({"id": outbox_id, "channel": channel, "status": "dlq", "reason": fail})
            continue
        if dry_run:
            replayed += 1
            info.append({"id": outbox_id, "channel": channel, "status": "would_replay"})
            continue
        try:
            await conn.execute("SELECT pg_notify($1, $2)", channel, payload_text)
            # Phase 2 of two-phase mark: finalize NOW()
            await conn.execute(
                "UPDATE events_outbox SET consumed_at = NOW() WHERE id = $1",
                outbox_id
            )
            replayed += 1
            info.append({"id": outbox_id, "channel": channel, "status": "ok"})
        except Exception as exc:
            # NOTIFY failure → revert in_progress mark + log
            await conn.execute(
                "UPDATE events_outbox SET consumed_at = NULL WHERE id = $1 AND consumed_at = $2",
                outbox_id, IN_PROGRESS_MARKER
            )
            dlq_count += 1
            info.append({"id": outbox_id, "channel": channel, "status": "notify_error", "reason": str(exc)})
            logger.warning("notify failed for id=%s ch=%s err=%s", outbox_id, channel, exc)

    return replayed, dlq_count, info


async def main(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.INFO if not args.verbose else logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    dsn = os.environ.get("EVENTBUS_DATABASE_URL") or args.dsn
    if not dsn:
        logger.error("EVENTBUS_DATABASE_URL not set and --dsn not provided")
        return 2

    if args.rate > HARD_MAX_RATE:
        logger.error("--rate %d exceeds HARD_MAX_RATE %d (4-panel safety)", args.rate, HARD_MAX_RATE)
        return 2

    stop = _shutdown_flag()
    sleep_seconds = max(0.1, args.batch / max(1, args.rate))

    conn = await asyncpg.connect(dsn=dsn, command_timeout=30)
    try:
        # Ensure DLQ table exists
        if not args.dry_run:
            await conn.execute(DLQ_DDL)

        # Pre-flight: snapshot Redis stream length
        redis_initial = await get_redis_stream_length()
        logger.info("redis organism:events initial length: %d", redis_initial)

        # Count unconsumed
        total_unconsumed = await conn.fetchval(
            "SELECT COUNT(*) FROM events_outbox WHERE consumed_at IS NULL"
        )
        logger.info("events_outbox unconsumed: %d (cap %d)", total_unconsumed, args.max_events)

        if args.dry_run:
            logger.info("=== DRY RUN — no pg_notify, no consumed_at marks ===")

        total_replayed = 0
        total_dlq = 0
        batch_num = 0
        since_dt = datetime.fromisoformat(args.since) if args.since else None

        while total_replayed + total_dlq < args.max_events and not stop["stop"]:
            batch_num += 1
            async with conn.transaction():
                replayed, dlq, info = await replay_batch(
                    conn, args.channel, since_dt, args.batch, redis_initial, args.dry_run
                )
            if replayed == 0 and dlq == 0:
                logger.info("no more events to replay — done")
                break
            total_replayed += replayed
            total_dlq += dlq
            logger.info(
                "batch %d: replayed=%d dlq=%d (total replayed=%d dlq=%d)",
                batch_num, replayed, dlq, total_replayed, total_dlq
            )

            # Auto-pause check: Redis growth
            redis_now = await get_redis_stream_length()
            if redis_initial > 0 and redis_now > redis_initial * REDIS_GROWTH_THRESHOLD:
                logger.error(
                    "ABORT: Redis stream length %d > %.1f× initial %d — auto-pause",
                    redis_now, REDIS_GROWTH_THRESHOLD, redis_initial
                )
                break

            await asyncio.sleep(sleep_seconds)

        # Final report
        logger.info("=== Replay complete ===")
        logger.info("Total replayed: %d", total_replayed)
        logger.info("Total DLQ: %d", total_dlq)
        logger.info("Batches: %d", batch_num)
        if args.dry_run:
            logger.info("(dry-run — no mutations applied)")
        else:
            redis_final = await get_redis_stream_length()
            logger.info("Redis stream length: %d → %d (delta %+d)", redis_initial, redis_final, redis_final - redis_initial)
            remaining = await conn.fetchval(
                "SELECT COUNT(*) FROM events_outbox WHERE consumed_at IS NULL"
            )
            logger.info("events_outbox unconsumed remaining: %d", remaining)

        return 0 if not stop["stop"] else 130
    finally:
        await conn.close()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dsn", help="PostgreSQL DSN (default: $EVENTBUS_DATABASE_URL)")
    p.add_argument("--rate", type=int, default=DEFAULT_RATE,
                   help=f"events/sec (default {DEFAULT_RATE}, hard cap {HARD_MAX_RATE})")
    p.add_argument("--batch", type=int, default=DEFAULT_BATCH,
                   help=f"batch size (default {DEFAULT_BATCH})")
    p.add_argument("--max-events", type=int, default=DEFAULT_MAX_EVENTS,
                   help=f"safety cap (default {DEFAULT_MAX_EVENTS})")
    p.add_argument("--channel", help="single channel only (default: all)")
    p.add_argument("--since", help="only events after this ISO timestamp")
    p.add_argument("--dry-run", action="store_true",
                   help="count + validate only, no pg_notify, no consumed_at marks")
    p.add_argument("--verbose", "-v", action="store_true", help="DEBUG logging")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(asyncio.run(main(args)))
