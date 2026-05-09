"""Cron entrypoint for Connector L1 — nightly 04:00 WITA on Pro.

Usage:
    cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python -m backend.services.cognitive.connector_cli

Exit codes:
    0  cycle completed
    1  configuration / pool init error
    2  CLI runner failed and zero theses produced
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

import asyncpg

from backend.services.cognitive.connector import ConnectorOrchestrator
from backend.services.cognitive.repository import CognitiveRepository
from backend.services.council.cli_runners import ClaudeCLIRunner
from backend.services.intel.dossier_repository import IntelRepository

logger = logging.getLogger("cognitive.connector.cli")


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
            dsn,
            min_size=1,
            max_size=2,
            command_timeout=60,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("pool init failed: %s", exc, exc_info=True)
        return 1

    try:
        intel_repo = IntelRepository(db_pool=pool)
        cognitive_repo = CognitiveRepository(db_pool=pool)
        runner = ClaudeCLIRunner()
        orchestrator = ConnectorOrchestrator(
            intel_repo=intel_repo,
            cognitive_repo=cognitive_repo,
            runner=runner,
        )
        result = await orchestrator.run_once()

        sys.stdout.write(
            json.dumps(
                {
                    "dossiers_considered": result.dossiers_considered,
                    "theses_proposed": result.theses_proposed,
                    "theses_inserted": result.theses_inserted,
                    "theses_rejected": result.theses_rejected,
                    "idempotent_skipped": result.idempotent_skipped,
                    "errors_count": len(result.errors),
                    "errors": result.errors[:3],
                    "inserted_ids": [str(x) for x in result.inserted_ids],
                },
                default=str,
            )
            + "\n"
        )

        if result.errors and result.theses_inserted == 0:
            if all(error.startswith("runner:") for error in result.errors):
                logger.warning("connector runner degraded: %s", result.errors)
                return 0
            return 2
        return 0
    finally:
        await pool.close()


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
