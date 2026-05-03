"""Cron entrypoint for MeasurementScheduler — every 6h on Pro.

Sweeps published posts at T+24h / T+72h / T+7d windows using whichever
samplers are reachable (graceful degradation per SYMBIOSIS Legge 4).

Usage:
    PYTHONPATH=. python -m backend.services.measurer.scheduler_cli

Env:
    DATABASE_URL                (required)
    IG_LONG_LIVED_TOKEN
    or INSTAGRAM_ACCESS_TOKEN   (optional — enables MetaGraphSampler)

UTM attribution sampling is skipped by the default CLI because it requires
a lead_lookup_fn from the CRM side; wire that in when the CRM→WR2 bridge
lands (design §9, future sprint).

Exit codes:
    0  sweep completed
    1  configuration / pool error
    2  no samplers available (IG token missing and no UTM hook)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

import asyncpg

from backend.services.measurer.orchestrator import MeasurerOrchestrator
from backend.services.measurer.scheduler import MeasurementScheduler
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger("measurer.scheduler.cli")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


def _build_samplers() -> list:
    """Build the sampler list from what's reachable in this environment.

    Today this is just MetaGraphSampler if IG creds are present. As the
    CRM → WR2 lead attribution bridge lands, UTMAttributionSampler can be
    added here behind a feature flag.
    """
    samplers: list = []
    if os.environ.get("IG_LONG_LIVED_TOKEN") or os.environ.get(
        "INSTAGRAM_ACCESS_TOKEN"
    ):
        from backend.services.measurer.meta_graph_sampler import (
            MetaGraphSampler,
        )

        try:
            samplers.append(MetaGraphSampler())
        except Exception as exc:  # noqa: BLE001
            logger.warning("MetaGraphSampler init failed: %s", exc)
    return samplers


async def run() -> int:
    _configure_logging()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 1

    samplers = _build_samplers()
    if not samplers:
        logger.warning(
            "no samplers available; skipping sweep (set IG_LONG_LIVED_TOKEN "
            "or INSTAGRAM_ACCESS_TOKEN to enable Meta Graph)"
        )
        return 2

    try:
        pool = await asyncpg.create_pool(
            dsn, min_size=1, max_size=2, command_timeout=60,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("pool init failed: %s", exc, exc_info=True)
        return 1

    try:
        repo = WarRoomRepository(db_pool=pool)
        orchestrator = MeasurerOrchestrator(samplers=samplers, repo=repo)
        scheduler = MeasurementScheduler(repo=repo, orchestrator=orchestrator)
        result = await scheduler.sweep_once()
        sys.stdout.write(
            json.dumps(
                {
                    "ran_at": result.ran_at.isoformat(),
                    "posts_measured": result.posts_measured,
                    "windows_hit": result.windows_hit,
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
