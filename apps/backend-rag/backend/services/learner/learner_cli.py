"""Cron entrypoint for LearnerOrchestrator — nightly 03:00 WITA on Pro.

Sweeps published posts ≥ T+72h, composes score, records skill/scar in genome.

Usage:
    PYTHONPATH=. python -m backend.services.learner.learner_cli

Env:
    DATABASE_URL   (required)
    (GenomeAdapter persists via cell-core genome SQLite path defined in its
     own config.)

Exit codes:
    0  sweep completed
    1  configuration / pool error
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

import asyncpg

from backend.services.learner.genome_adapter import GenomeAdapter
from backend.services.learner.learner_orchestrator import LearnerOrchestrator
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger("learner.cli")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


async def run() -> int:
    _configure_logging()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 1

    try:
        pool = await asyncpg.create_pool(
            dsn, min_size=1, max_size=2, command_timeout=60,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("pool init failed: %s", exc, exc_info=True)
        return 1

    try:
        repo = WarRoomRepository(db_pool=pool)
        genome = GenomeAdapter()
        orchestrator = LearnerOrchestrator(repo=repo, genome=genome)
        result = await orchestrator.sweep_once()
        sys.stdout.write(
            json.dumps(
                {
                    "ran_at": result.ran_at.isoformat(),
                    "posts_considered": result.posts_considered,
                    "skills_recorded": result.skills_recorded,
                    "scars_recorded": result.scars_recorded,
                    "incomplete": result.incomplete,
                    "errors_count": len(result.errors),
                },
                default=str,
            )
            + "\n"
        )
        return 0
    finally:
        await pool.close()


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
