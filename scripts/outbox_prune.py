#!/usr/bin/env python3
"""Weekly prune of events_outbox.consumed rows older than 30 days.

GUARDS (per 4-panel Phase 2 review 2026-05-12):
- NEVER prune rows where consumed_at IS NULL (regardless of age)
- NEVER prune rows where consumed_at == in_progress_marker (replay active)
- ONLY prune where consumed_at IS NOT NULL AND consumed_at > epoch
  AND consumed_at < NOW() - INTERVAL '30 days'

Reports: count before, count pruned, count after, table size before/after.

Reference: docs/superpowers/specs/2026-05-12-phase2-core-plumbing-fix-spec.md
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone

import asyncpg

logger = logging.getLogger("outbox_prune")

# Two-phase mark sentinel from replay_outbox_throttled.py
IN_PROGRESS_MARKER = datetime(1970, 1, 1, tzinfo=timezone.utc)


async def main(args: argparse.Namespace) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    dsn = os.environ.get("EVENTBUS_DATABASE_URL") or args.dsn
    if not dsn:
        logger.error("EVENTBUS_DATABASE_URL not set and --dsn not provided")
        return 2

    conn = await asyncpg.connect(dsn=dsn, command_timeout=60)
    try:
        # Snapshot before
        total_before = await conn.fetchval("SELECT COUNT(*) FROM events_outbox")
        unconsumed_before = await conn.fetchval(
            "SELECT COUNT(*) FROM events_outbox WHERE consumed_at IS NULL"
        )
        consumed_before = total_before - unconsumed_before
        logger.info(
            "BEFORE: total=%d, unconsumed=%d, consumed=%d",
            total_before, unconsumed_before, consumed_before
        )

        if args.dry_run:
            count_to_prune = await conn.fetchval(
                "SELECT COUNT(*) FROM events_outbox "
                "WHERE consumed_at IS NOT NULL "
                "AND consumed_at > $1 "
                f"AND consumed_at < NOW() - INTERVAL '{args.older_than_days} days'",
                IN_PROGRESS_MARKER
            )
            logger.info("DRY RUN: would prune %d rows", count_to_prune)
            return 0

        # Prune with strict guards
        result = await conn.execute(
            "DELETE FROM events_outbox "
            "WHERE consumed_at IS NOT NULL "
            "AND consumed_at > $1 "
            f"AND consumed_at < NOW() - INTERVAL '{args.older_than_days} days'",
            IN_PROGRESS_MARKER
        )
        # asyncpg execute returns 'DELETE N' status string
        pruned = int(result.split()[1]) if result.startswith("DELETE ") else 0
        logger.info("PRUNED: %d rows (older than %d days)", pruned, args.older_than_days)

        # Snapshot after
        total_after = await conn.fetchval("SELECT COUNT(*) FROM events_outbox")
        logger.info("AFTER: total=%d (delta %+d)", total_after, total_after - total_before)

        # Optional: VACUUM ANALYZE to reclaim space
        if args.vacuum:
            logger.info("VACUUM ANALYZE events_outbox...")
            await conn.execute("VACUUM ANALYZE events_outbox")
            logger.info("vacuum complete")

        return 0
    finally:
        await conn.close()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dsn", help="PostgreSQL DSN (default: $EVENTBUS_DATABASE_URL)")
    p.add_argument("--older-than-days", type=int, default=30, help="retention days (default 30)")
    p.add_argument("--dry-run", action="store_true", help="count only, no DELETE")
    p.add_argument("--vacuum", action="store_true", help="VACUUM ANALYZE after prune")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    sys.exit(asyncio.run(main(args)))
