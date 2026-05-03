#!/usr/bin/env python3
"""genome_decay_cron.py — Nightly confidence decay for genome skills.

# Organo: cell-core L0 → consumes genome SQLite → produces decayed confidence
# Schedule: 02:30 WITA (19:30 UTC) via LaunchAgent
# If fails: skills retain current confidence, next run catches up

Applies exponential decay (Ebbinghaus-aligned) to unused skills across
all known genome databases. Scars are immune. Skills used in last 7 days
are skipped.

Formula: new_conf = confidence * (0.95 ^ days_unused)
Threshold: below 0.3 → silenced (non-destructive)
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# ─── Config ──────────────────────────────────────────────────────────────────

LOG_FILE = Path.home() / "logs" / "genome-decay.log"
DECAY_RATE = 0.95
SILENCE_THRESHOLD = 0.3
MIN_IDLE_DAYS = 7

# Known genome databases — paths relative to project root
# Each genome DB may serve multiple cells
GENOME_DB_PATHS = [
    Path.home() / "Projects" / "nuzantara" / "apps" / "mata-garuda" / "data" / "knowledge.db",
    Path.home() / "Projects" / "nuzantara" / "apps" / "mata-garuda" / "data" / "sentinel_cell.db",
]

# ─── Setup ───────────────────────────────────────────────────────────────────

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("genome_decay")

# ─── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    logger.info("Genome decay cron started")
    total_counts = {"decayed": 0, "silenced": 0, "skipped": 0}

    # Add cell-core to path
    cell_core_path = Path.home() / "Projects" / "nuzantara" / "packages" / "cell-core"
    if str(cell_core_path) not in sys.path:
        sys.path.insert(0, str(cell_core_path))

    try:
        from cell_core.genome import Genome
    except ImportError:
        logger.error("cell_core not importable — aborting")
        return

    for db_path in GENOME_DB_PATHS:
        if not db_path.exists():
            logger.info(f"DB not found, skip: {db_path}")
            continue

        try:
            g = Genome(db_path=str(db_path))
            stats_before = g.stats()
            counts = g.decay_unused_skills(
                decay_rate=DECAY_RATE,
                silence_threshold=SILENCE_THRESHOLD,
                min_idle_days=MIN_IDLE_DAYS,
            )
            stats_after = g.stats()

            for k in total_counts:
                total_counts[k] += counts.get(k, 0)

            logger.info(
                f"DB {db_path.name}: {counts} "
                f"(active: {stats_before['active']}→{stats_after['active']})"
            )
        except Exception as e:
            logger.error(f"Failed on {db_path}: {e}")

    logger.info(f"Genome decay cron complete: {total_counts}")


if __name__ == "__main__":
    main()
