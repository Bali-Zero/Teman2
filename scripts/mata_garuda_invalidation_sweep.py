#!/usr/bin/env python3
"""mata_garuda_invalidation_sweep.py — daily TTL + event invalidation sweep.

Sprint 3 W2 deliverable. Reference:
  docs/sprint3/mata-garuda-cell-design.md § "Mata-Garuda → WR2"
  apps/mata-garuda/cell.yaml (sub_organelles.invalidation_sweeper)

Runs daily at 04:13 WITA (off-minute, off-hour) via launchd plist
``com.matagaruda.invalidation-sweep``. Two sweep passes:

1. **TTL sweep**: rows with ``valid_until < NOW() AND invalidated_at IS NULL
   AND invalidation_mode='auto'`` are marked invalidated by the
   ``ttl_sweeper`` actor. The mig 155 trigger fires on the resulting
   UPDATE → ``asset_provenance`` channel emission with
   ``event_type='provenance_updated'`` and the row's new
   ``invalidated_at`` timestamp.

2. **Event sweep (deferred)**: when an upstream event-topic fires (e.g.
   ``reg_alert.visa``), the cell adapter responsible for that event will
   call ``UPDATE asset_provenance SET invalidated_at=NOW(),
   invalidated_by='event:<topic>' WHERE invalidation_event_topic=<topic>
   AND invalidated_at IS NULL``. This script does NOT itself listen on
   event channels — that's the responsibility of the cell adapter or a
   separate event-driven daemon (Sprint 4 wiring).

This script focuses on (1): the time-driven sweep that doesn't need a
listener. It is intentionally idempotent — running it twice in a row is
safe and a no-op the second time (the partial-index keeps the lookup
fast, and ``invalidated_at IS NOT NULL`` filters out already-processed
rows).

Symbiosis Law 2 enforcement: this script runs Pro-only (Pro-local
PostgreSQL is not reachable from Fly cells). The launchd plist is
deployed only to Pro.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# The cell_adapter lives in backend-rag (not in apps/mata-garuda — see
# B3 finding 2026-05-04 multi-LLM W2 review). This script is currently
# self-contained (does not import the adapter); the import path setup
# below is reserved for the future extension that will call
# `cell_adapter.list_expired_assets` to enrich the sweep log with
# per-asset_kind counts.
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "apps" / "backend-rag"))

logger = logging.getLogger("mata_garuda_invalidation_sweep")


async def _connect(database_url: str):
    """Create a small asyncpg pool sized for a single sweep batch.

    asyncpg is imported lazily so ``--help`` and unit tests of the argparse
    surface don't hard-fail on a system Python without the package
    installed (production runs from the backend venv where it IS
    installed).
    """
    import asyncpg  # noqa: PLC0415  (lazy by design)
    return await asyncpg.create_pool(
        dsn=database_url,
        min_size=1,
        max_size=2,
        command_timeout=30,
    )


async def run_ttl_sweep(
    pool: asyncpg.Pool,
    *,
    batch_size: int = 1000,
    dry_run: bool = False,
) -> int:
    """Mark TTL-expired provenance rows invalidated.

    Returns the number of rows updated. With ``dry_run=True`` no UPDATE is
    issued — the count returned is the would-update count.
    """
    select_sql = """
        SELECT id, asset_kind, asset_id, valid_until
        FROM asset_provenance
        WHERE valid_until IS NOT NULL
          AND valid_until < NOW()
          AND invalidated_at IS NULL
          AND invalidation_mode = 'auto'
        ORDER BY valid_until ASC
        LIMIT $1
    """
    update_sql = """
        UPDATE asset_provenance
        SET invalidated_at = NOW(),
            invalidated_by = 'ttl_sweeper',
            updated_at = NOW()
        WHERE id = ANY($1::bigint[])
    """
    async with pool.acquire() as conn:
        candidates = await conn.fetch(select_sql, batch_size)
        if not candidates:
            logger.info("ttl_sweep: 0 expired rows; nothing to do")
            return 0
        ids = [r["id"] for r in candidates]
        logger.info(
            "ttl_sweep: %d expired rows (oldest valid_until=%s, batch_size=%d, dry_run=%s)",
            len(ids), candidates[0]["valid_until"].isoformat(), batch_size, dry_run,
        )
        if dry_run:
            return len(ids)
        # The UPDATE fires the mig 155 trigger per row, which writes to
        # events_outbox + pg_notify (durability before volatile). Consumers
        # see asset_provenance events with event_type='provenance_updated'
        # and invalidated_at set.
        await conn.execute(update_sql, ids)
        logger.info("ttl_sweep: %d rows marked invalidated by ttl_sweeper", len(ids))
        return len(ids)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Postgres connection string (default: $DATABASE_URL).",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Maximum rows to process per sweep run (default 1000).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not UPDATE; only count would-be-invalidated rows.",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG logging.",
    )
    return p.parse_args(argv)


async def _main_async(args: argparse.Namespace) -> int:
    if not args.database_url:
        logger.error(
            "DATABASE_URL not set. Provide via --database-url or env."
        )
        return 2
    started = datetime.now()
    pool = await _connect(args.database_url)
    try:
        invalidated = await run_ttl_sweep(
            pool,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
    finally:
        await pool.close()
    elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
    logger.info(
        "sweep complete: invalidated=%d duration_ms=%d dry_run=%s",
        invalidated, elapsed_ms, args.dry_run,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _setup_logging(args.verbose)
    try:
        return asyncio.run(_main_async(args))
    except KeyboardInterrupt:
        logger.warning("sweep interrupted")
        return 130
    except Exception:
        logger.exception("sweep failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
