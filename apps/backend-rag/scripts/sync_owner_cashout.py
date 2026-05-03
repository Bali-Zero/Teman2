"""CLI entrypoint for owner cashout sync (cron on Air).

Usage:
    PYTHONPATH=. python scripts/sync_owner_cashout.py [--triggered-by cron]

Env:
    DATABASE_URL                  — Postgres URL
    OWNER_CASHOUT_SA_FILE / _JSON — Service Account credentials
    TELEGRAM_BOT_TOKEN            — for failure alerts
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

import asyncpg

from backend.services.hr.owner_cashout.sync_service import run_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("sync_owner_cashout")


async def main(triggered_by: str) -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        logger.error("DATABASE_URL not set")
        return 2

    pool = await asyncpg.create_pool(url, min_size=1, max_size=2)
    try:
        result = await run_sync(pool, triggered_by=triggered_by)
        logger.info(
            "sync done status=%s weeks=%d rows=%d unknown=%s",
            result.status,
            result.weeks_processed,
            result.rows_upserted,
            result.unknown_tabs,
        )
        return 0 if result.status == "success" else 1
    finally:
        await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--triggered-by", default="cron")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.triggered_by)))
