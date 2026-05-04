#!/usr/bin/env python3
"""events_outbox_prune.py — daily prune of consumed events.

Sprint 6 / audit P0-2 phase 3 partial: pruning cron for events_outbox.

Background:
    Migration 144 (2026-04-29) added events_outbox for EventBus durability.
    Phase 1+2 (Sprint 3 W2) made writes go through outbox + pg_notify atomic
    in DB triggers. Phase 3 introduced replay-on-reconnect with auto-ack.
    What was missing: pruning. The table grew unbounded; cell_pulse_observed
    alone produces ~3k events/week (~150k/year) — without pruning, the
    table would saturate disk in months.

What this script does:
    Calls outbox.prune_consumed(conn, older_than_days=30). Pending
    (unconsumed) rows are NEVER deleted. Returns the row count for the
    structured log.

Operational doctrine:
    - Connect via DATABASE_URL_LOCAL (fly proxy 127.0.0.1:15432) — same
      pattern used by mata_garuda_invalidation_sweep.py.
    - Run idempotently. Re-running mid-day with no candidates → no-op.
    - Log to ~/logs/events-outbox-prune.{stdout,stderr}.log via plist
      StandardOutPath/StandardErrorPath (cf. cicatrix P0-3: never log to
      /tmp).
    - Best-effort: a DB connection failure logs WARNING and exits 1.
      LaunchAgent will retry next day.
    - Lock-free: prune_consumed uses a single DELETE statement, atomic.
      No risk of contention with EventBus listeners (they only INSERT
      and UPDATE consumed_at).

Schedule:
    Daily at 04:30 WITA via com.matagaruda.events-outbox-prune.plist.
    Slot chosen to come AFTER:
        - Daily indexing-sweep at 00:30 WITA
        - Auto-sentinel at 03:00 WITA
        - Mata-Garuda invalidation-sweep at 04:13 WITA
    And BEFORE:
        - Drive watchdog at 06:00 WITA
        - Auto-test at 02:15 WITA (already passed)

Restore (rollback):
    Disable LaunchAgent: launchctl bootout gui/$(id -u)/com.matagaruda.events-outbox-prune
    Re-enable: launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.matagaruda.events-outbox-prune.plist
    The script + helper function are pure read-then-DELETE; rollback is
    just "stop running it". No schema changes.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time

import asyncpg

# Add backend-rag src to path so we can reuse the helper.
# This script lives in scripts/ at repo root; the helper is in
# apps/backend-rag/backend/services/events/outbox.py.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "apps", "backend-rag"))

from backend.services.events.outbox import prune_consumed  # noqa: E402


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("events_outbox_prune")


async def main(database_url: str, older_than_days: int, dry_run: bool) -> int:
    t_start = time.monotonic()
    try:
        conn = await asyncpg.connect(database_url, timeout=10)
    except Exception as exc:
        logger.error("db_connect_failed: %s", exc)
        return 1

    try:
        # Diagnostic: count what's eligible BEFORE deleting.
        eligible = await conn.fetchval(
            "SELECT COUNT(*) FROM events_outbox "
            "WHERE consumed_at IS NOT NULL "
            f"AND consumed_at < NOW() - INTERVAL '{int(older_than_days)} days'"
        )

        if dry_run:
            logger.info(
                "dry_run: %d rows would be pruned (consumed older than %dd)",
                eligible,
                older_than_days,
            )
            return 0

        deleted = await prune_consumed(conn, older_than_days=older_than_days)
        elapsed = time.monotonic() - t_start
        logger.info(
            "prune complete: deleted=%d eligible_before=%d duration_ms=%.0f older_than_days=%d",
            deleted,
            eligible,
            elapsed * 1000,
            older_than_days,
        )

        # Log surviving table size for monitoring trend.
        remaining = await conn.fetchval("SELECT COUNT(*) FROM events_outbox")
        logger.info("events_outbox remaining rows: %d", remaining)

        return 0
    except Exception as exc:
        logger.error("prune_failed: %s", exc)
        return 1
    finally:
        await conn.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Postgres DSN (default: $DATABASE_URL).",
    )
    parser.add_argument(
        "--older-than-days",
        type=int,
        default=int(os.environ.get("OUTBOX_PRUNE_DAYS", "30")),
        help="Retention days for consumed rows (default: 30).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count eligible rows but do NOT delete.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if not args.database_url:
        logger.error("DATABASE_URL not set. Provide via --database-url or env.")
        sys.exit(2)
    sys.exit(
        asyncio.run(
            main(
                database_url=args.database_url,
                older_than_days=args.older_than_days,
                dry_run=args.dry_run,
            )
        )
    )
