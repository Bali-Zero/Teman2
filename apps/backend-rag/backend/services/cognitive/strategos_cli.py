"""Cron entrypoint for Strategos — weekly Sunday 22:00 WITA on Pro.

Two modes:
    --generate   (default)  run the orchestrator to (re)build the week's brief.
    --deliver               read latest brief and send to Telegram.

Usage:
    PYTHONPATH=. python -m backend.services.cognitive.strategos_cli
    PYTHONPATH=. python -m backend.services.cognitive.strategos_cli --deliver
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys

import asyncpg

from backend.services.cognitive.repository import CognitiveRepository
from backend.services.cognitive.strategos import StrategosOrchestrator
from backend.services.cognitive.strategos_delivery import StrategosDelivery
from backend.services.council.cli_runners import ClaudeCLIRunner
from backend.services.intel.dossier_repository import IntelRepository
from backend.services.review.telegram_adapter import TelegramReviewAdapter
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger("cognitive.strategos.cli")


DEFAULT_OWNER = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


async def _generate(pool: asyncpg.Pool) -> int:
    intel_repo = IntelRepository(db_pool=pool)
    cognitive_repo = CognitiveRepository(db_pool=pool)
    war_room_repo = WarRoomRepository(db_pool=pool)
    runner = ClaudeCLIRunner()
    orchestrator = StrategosOrchestrator(
        intel_repo=intel_repo,
        cognitive_repo=cognitive_repo,
        war_room_repo=war_room_repo,
        runner=runner,
    )
    result = await orchestrator.run_once()
    sys.stdout.write(json.dumps({
        "week_of": result.week_of.isoformat(),
        "inserted": result.inserted,
        "brief_id": str(result.brief.id) if result.brief else None,
        "context_chars": result.context_chars,
        "prompt_chars": result.prompt_chars,
        "errors_count": len(result.errors),
    }, default=str) + "\n")
    return 0 if result.inserted else 2


async def _deliver(pool: asyncpg.Pool) -> int:
    cognitive_repo = CognitiveRepository(db_pool=pool)
    telegram = TelegramReviewAdapter()
    delivery = StrategosDelivery(
        repo=cognitive_repo,
        telegram=telegram,
        owner_chat_id=DEFAULT_OWNER,
    )
    result = await delivery.send_latest_brief()
    sys.stdout.write(json.dumps({
        "ok": result.ok,
        "brief_id": str(result.brief_id) if result.brief_id else None,
        "message_id": result.message_id,
        "skipped": result.skipped,
        "skip_reason": result.skip_reason,
        "error": result.error,
    }, default=str) + "\n")
    return 0 if result.ok else 2


async def run(mode: str) -> int:
    _configure_logging()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 1
    try:
        pool = await asyncpg.create_pool(
            dsn, min_size=1, max_size=2, command_timeout=180,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("pool init failed: %s", exc, exc_info=True)
        return 1
    try:
        if mode == "deliver":
            return await _deliver(pool)
        return await _generate(pool)
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--deliver",
        action="store_true",
        help="Send latest brief to Telegram (instead of generating)",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(run(mode="deliver" if args.deliver else "generate")))


if __name__ == "__main__":
    main()
