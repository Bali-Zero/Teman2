"""Cron entrypoint for DossierCompiler — nightly 04:00 WITA on Pro.

Usage:
    cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python -m backend.services.intel.dossier_compiler_cli

Exit codes:
    0  cycle completed (any count, including zero dossiers)
    1  configuration / pool init error
    2  every cluster failed to compile
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

import asyncpg

from backend.services.council.cli_runners import ClaudeCLIRunner
from backend.services.intel.dossier_compiler import DossierCompiler
from backend.services.intel.dossier_repository import IntelRepository

logger = logging.getLogger("intel.dossier_compiler.cli")


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
        repo = IntelRepository(db_pool=pool)
        runner = ClaudeCLIRunner()
        compiler = DossierCompiler(repo=repo, runner=runner)
        summary = await compiler.run_once()

        output = {
            "batch_size": summary.batch_size,
            "clusters_built": summary.clusters_built,
            "dossiers_compiled": summary.dossiers_compiled,
            "dossiers_failed": summary.dossiers_failed,
            "signals_consumed": summary.signals_consumed,
            "errors_count": len(summary.errors),
        }
        sys.stdout.write(json.dumps(output, default=str) + "\n")

        if summary.clusters_built > 0 and summary.dossiers_compiled == 0:
            return 2
        return 0
    finally:
        await pool.close()


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
