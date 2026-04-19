"""Cron entrypoint for SLAWorker — every 30 min on Pro.

Usage:
    PYTHONPATH=. python -m backend.services.review.sla_worker_cli

Env:
    DATABASE_URL             (required)
    TELEGRAM_BOT_TOKEN       (required for alerts)
    TELEGRAM_OWNER_CHAT_ID   (required — Zero's chat id)

Exit codes:
    0  sweep completed (any combination of soft/repeat/expire counts)
    1  configuration error or unrecoverable pool failure
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

import asyncpg

from backend.services.review.sla_worker import SLAWorker
from backend.services.review.telegram_adapter import TelegramReviewAdapter
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger("review.sla.cli")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


async def run() -> int:
    _configure_logging()
    dsn = os.environ.get("DATABASE_URL")
    owner_chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 1
    if not owner_chat_id:
        logger.error("TELEGRAM_OWNER_CHAT_ID not set")
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
        telegram = TelegramReviewAdapter()
        worker = SLAWorker(
            repo=repo, telegram=telegram, owner_chat_id=owner_chat_id,
        )
        result = await worker.sweep_once()
        sys.stdout.write(
            json.dumps(
                {
                    "swept_count": result.swept_count,
                    "soft_alerts_sent": result.soft_alerts_sent,
                    "repeat_alerts_sent": result.repeat_alerts_sent,
                    "expired_count": result.expired_count,
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
