"""Synthetic training — bootstrap PatternIndex with diverse situation coverage.

Two modes:
  1. --synthetic (default): generates a grid of situations covering all
     combinations of health/rt/budget/db/qdrant/error_rate, calls Qwen 9B
     once per distinct situation, saves patterns. Fast, cheap, comprehensive.

  2. --from-history: reads real pulse_log, extracts unique situation buckets,
     trains only on situations NOT already covered by existing patterns.

Usage:
    cd apps/cell
    source .venv/bin/activate

    # Recommended: synthetic grid (comprehensive, ~2-3min with Ollama)
    CELL_DATABASE_URL=postgresql://nuzantara@localhost/nuzantara_dev \\
        python scripts/train_from_history.py --synthetic

    # From real history (useful when there's diverse real data)
    CELL_DATABASE_URL=postgresql://nuzantara@localhost/nuzantara_dev \\
        python scripts/train_from_history.py --from-history --days 30

    # Dry run (no DB writes)
    ... --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncpg

from cell.core.config import settings
from cell.slow.reasoner import SlowReasoner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [TRAIN] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("cell.train")


# Synthetic situation grid — covers the space CELL needs to know
_SYNTHETIC_SITUATIONS = [
    # (health_status, response_time_ms, budget_pct, db_ok, qdrant_ok, error_rate_norm, label)
    # --- RED situations ---
    ("red",    0,     0.1, 1.0, 1.0, 0.0, "backend_down_fresh"),
    ("red",    0,     0.1, 1.0, 1.0, 0.5, "backend_down_errors"),
    ("red",    0,     0.5, 1.0, 1.0, 0.0, "backend_down_mid_budget"),
    ("red",    0,     0.9, 1.0, 1.0, 0.0, "backend_down_high_budget"),
    ("red",    0,     0.1, 0.0, 1.0, 0.0, "backend_down_db_fail"),
    ("red",    0,     0.1, 1.0, 0.0, 0.0, "backend_down_qdrant_fail"),
    ("red",    0,     0.1, 0.0, 0.0, 1.0, "backend_down_all_fail"),
    ("red", 3000,     0.1, 1.0, 1.0, 0.0, "backend_slow_red"),
    ("red", 8000,     0.1, 1.0, 1.0, 0.2, "backend_very_slow"),
    ("red", 30000,    0.1, 1.0, 1.0, 0.0, "backend_timeout"),
    # --- YELLOW situations ---
    ("yellow", 2000,  0.1, 1.0, 1.0, 0.0, "slow_response"),
    ("yellow", 4000,  0.1, 1.0, 1.0, 0.0, "very_slow_response"),
    ("yellow", 1000,  0.1, 0.5, 1.0, 0.0, "db_degraded"),
    ("yellow", 1000,  0.1, 1.0, 0.5, 0.0, "qdrant_degraded"),
    ("yellow",  500,  0.1, 1.0, 1.0, 0.3, "elevated_error_rate"),
    ("yellow",  500,  0.1, 1.0, 1.0, 0.8, "high_error_rate"),
    ("yellow", 1500,  0.5, 1.0, 1.0, 0.0, "slow_mid_budget"),
    ("yellow", 1500,  0.85,1.0, 1.0, 0.0, "slow_budget_alert"),
    ("yellow",  500,  0.9, 1.0, 1.0, 0.0, "budget_almost_full"),
    ("yellow",  300,  0.1, 0.5, 0.5, 0.2, "multiple_degraded"),
    # --- Escalating RED after sustained YELLOW ---
    ("red",  1000,    0.3, 0.0, 1.0, 0.5, "db_down_errors"),
    ("red",  1000,    0.3, 1.0, 0.0, 0.5, "qdrant_down_errors"),
    ("red",     0,    0.95,1.0, 1.0, 0.0, "backend_down_budget_critical"),
]


async def train_synthetic(dry_run: bool) -> None:
    logger.info(f"Synthetic training: {len(_SYNTHETIC_SITUATIONS)} situations, dry_run={dry_run}")

    db_url = os.environ.get("CELL_DATABASE_URL", settings.database_url)
    reasoner = SlowReasoner()
    existing = await reasoner.bootstrap_memory()
    logger.info(f"Loaded {existing} existing patterns from DB")

    saved = 0
    skipped = 0

    for (health, rt_ms, budget_pct, db_ok, qdrant_ok, error_rate, label) in _SYNTHETIC_SITUATIONS:
        history = [
            {"health_status": health, "pulse_number": i, "response_time_ms": rt_ms}
            for i in range(5)
        ]

        # Check if already covered by PatternIndex
        match = reasoner._patterns.find_similar(
            health, rt_ms, budget_pct, db_ok=db_ok, qdrant_ok=qdrant_ok, error_rate_norm=error_rate,
        )
        if match is not None:
            logger.info(f"  SKIP [{label}] — already covered (→ {match.action})")
            skipped += 1
            continue

        try:
            proposal = await reasoner.think(
                health_status=health,
                response_time_ms=rt_ms,
                error_message="Connection refused" if health == "red" and rt_ms == 0 else "",
                recent_history=history,
                budget_spent=budget_pct * 10.0,
                budget_limit=10.0,
                db_ok=db_ok,
                qdrant_ok=qdrant_ok,
                error_rate_norm=error_rate,
                max_tier=0,  # Qwen 9B only for speed
            )

            if proposal.action == "none" or proposal.tier_used == -1:
                logger.info(f"  SKIP [{label}] — action={proposal.action} tier={proposal.tier_used}")
                skipped += 1
                continue

            logger.info(
                f"  SAVE [{label}] health={health} rt={rt_ms}ms budget={budget_pct:.0%} "
                f"→ {proposal.action} conf={proposal.confidence:.2f}"
                + (" [DRY]" if dry_run else "")
            )

            if not dry_run:
                from cell.core.db import save_pattern, get_pool  # noqa: PLC0415
                await get_pool()  # ensure pool is open
                await save_pattern(
                    health_status=health,
                    response_time_ms=rt_ms,
                    budget_pct=budget_pct,
                    action=proposal.action,
                    reason=proposal.reason,
                    confidence=proposal.confidence,
                    tier_used=proposal.tier_used,
                )
                # Also add to in-memory index so subsequent situations benefit
                reasoner._patterns.add(
                    health_status=health,
                    response_time_ms=rt_ms,
                    budget_pct=budget_pct,
                    action=proposal.action,
                    reason=proposal.reason,
                    confidence=proposal.confidence,
                    tier_used=proposal.tier_used,
                    db_ok=db_ok,
                    qdrant_ok=qdrant_ok,
                    error_rate_norm=error_rate,
                )
            saved += 1

        except Exception as e:
            logger.warning(f"  ERROR [{label}]: {e}")

    if not dry_run:
        # Small delay to let fire-and-forget tasks complete before closing pool
        await asyncio.sleep(0.5)
        from cell.core.db import close_pool  # noqa: PLC0415
        await close_pool()

    total_patterns = existing + saved
    logger.info(
        f"\nTraining complete:"
        f"\n  Situations:  {len(_SYNTHETIC_SITUATIONS)}"
        f"\n  Saved:       {saved}"
        f"\n  Skipped:     {skipped} (already covered)"
        f"\n  Total in DB: {total_patterns}"
        + ("\n  [DRY RUN — nothing written]" if dry_run else "")
    )


async def train_from_history(days: int, limit: int, dry_run: bool) -> None:
    """Train from real pulse history — useful for discovering actual behavior patterns."""
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415
    logger.info(f"History training: days={days}, limit={limit}, dry_run={dry_run}")

    db_url = os.environ.get("CELL_DATABASE_URL", settings.database_url)
    conn = await asyncpg.connect(db_url)

    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = await conn.fetch(
        """SELECT DISTINCT
               health_status,
               (response_time_ms / 1000) * 1000 AS rt_bucket,
               ROUND(budget_spent / NULLIF(budget_limit, 0), 1) AS budget_bucket,
               action_taken
           FROM cell_pulse_log
           WHERE health_status != 'green'
             AND created_at >= $1
             AND action_taken IS NOT NULL
           ORDER BY health_status, rt_bucket, budget_bucket
           LIMIT $2""",
        since, limit if limit > 0 else 500,
    )
    await conn.close()

    if not rows:
        logger.warning("No non-green pulses with actions in history.")
        return

    logger.info(f"Found {len(rows)} distinct situation buckets in history")

    reasoner = SlowReasoner()
    existing = await reasoner.bootstrap_memory()
    logger.info(f"Loaded {existing} existing patterns")

    saved = 0
    skipped = 0

    for row in rows:
        health = row["health_status"]
        rt_ms = int(row["rt_bucket"] or 0)
        budget_pct = float(row["budget_bucket"] or 0.0)
        known_action = row["action_taken"]

        # Skip if already covered
        match = reasoner._patterns.find_similar(health, rt_ms, budget_pct)
        if match is not None:
            skipped += 1
            continue

        if not dry_run:
            from cell.core.db import save_pattern, get_pool  # noqa: PLC0415
            await get_pool()
            await save_pattern(
                health_status=health,
                response_time_ms=rt_ms,
                budget_pct=budget_pct,
                action=known_action,
                reason=f"Learned from history: {health} rt={rt_ms}ms budget={budget_pct:.0%}",
                confidence=0.8,
                tier_used=0,
            )
        saved += 1
        logger.info(f"  SAVE {health} rt={rt_ms}ms budget={budget_pct:.0%} → {known_action}")

    if not dry_run:
        from cell.core.db import close_pool  # noqa: PLC0415
        await close_pool()

    logger.info(f"\nHistory training complete: saved={saved}, skipped={skipped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CELL synthetic/history training")
    parser.add_argument("--synthetic", action="store_true", default=True, help="Synthetic grid (default)")
    parser.add_argument("--from-history", action="store_true", help="Train from real pulse_log")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.from_history:
        asyncio.run(train_from_history(args.days, args.limit, args.dry_run))
    else:
        asyncio.run(train_synthetic(args.dry_run))
