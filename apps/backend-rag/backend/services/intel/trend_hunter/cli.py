"""Cron entrypoint for Trend-Hunter.

Invoked every 2h on Pro (OpenClaw/launchd). Usage:

    cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python -m backend.services.intel.trend_hunter.cli

Exit codes:
    0 — cycle completed (any number of signals, including zero)
    1 — configuration error (DATABASE_URL missing, pool init failed)
    2 — cycle hard failure (all adapters raised)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

import asyncpg

from backend.services.intel.dossier_repository import IntelRepository
from backend.services.intel.trend_hunter.orchestrator import TrendHunterOrchestrator

logger = logging.getLogger("trend_hunter.cli")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


async def run() -> int:
    _configure_logging()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set — cannot run cycle")
        return 1

    try:
        pool = await asyncpg.create_pool(
            dsn,
            min_size=1,
            max_size=2,
            command_timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("pool init failed: %s", exc, exc_info=True)
        return 1

    try:
        repo = IntelRepository(db_pool=pool)
        orchestrator = TrendHunterOrchestrator(repo=repo)
        summary = await orchestrator.run_cycle()
        sys.stdout.write(
            json.dumps(
                {
                    "persisted": summary.persisted,
                    "after_dedup": summary.after_dedup,
                    "raw": summary.raw_signals,
                    "degraded": summary.degraded,
                    "host": summary.host,
                    "adapters": [
                        {
                            "name": a.adapter_name,
                            "signals": len(a.signals),
                            "duration_ms": round(a.duration_ms, 1),
                            "error": a.error,
                        }
                        for a in summary.adapters_run
                    ],
                },
                default=str,
            )
            + "\n"
        )
        if not summary.adapters_run or all(
            (not a.ok) for a in summary.adapters_run
        ):
            return 2
        return 0
    finally:
        await pool.close()


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
