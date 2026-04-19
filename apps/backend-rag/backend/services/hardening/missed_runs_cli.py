"""Cron entrypoint for MissedRunsAlerter — every 6h on Pro.

Scans war_room_missed_runs, alerts Zero on unnotified entries, then marks
them notified.

Usage:
    PYTHONPATH=. python -m backend.services.hardening.missed_runs_cli

Env:
    DATABASE_URL             (required)
    TELEGRAM_BOT_TOKEN       (required)
    TELEGRAM_OWNER_CHAT_ID   (required)

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

from backend.services.hardening.missed_runs_alerter import MissedRunsAlerter
from backend.services.review.telegram_adapter import TelegramReviewAdapter
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger("hardening.missed_runs.cli")


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
        alerter = MissedRunsAlerter(
            repo=repo, telegram=telegram, owner_chat_id=owner_chat_id,
        )
        result = await alerter.sweep_once()
        sys.stdout.write(
            json.dumps(
                {
                    "ran_at": result.ran_at.isoformat(),
                    "pending_count": result.pending_count,
                    "notified_count": result.notified_count,
                    "message_sent": result.message_sent,
                    "error": result.error,
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
