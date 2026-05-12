#!/usr/bin/env python3
"""10-min watchdog: reset stale war_room_drafts.status='rendering' leases."""
import asyncio
import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apps" / "backend-rag"))

import asyncpg  # noqa: E402

from backend.services.canva_renderer_v2._pg import reset_stale_leases  # noqa: E402
from backend.services.canva_renderer_v2._telegram import send_telegram  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lease-watchdog")


async def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.critical("DATABASE_URL not set")
        return 2
    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        recovered = await reset_stale_leases(conn, stale_after_minutes=15)
        if recovered:
            ids_short = [str(x)[:8] for x in recovered[:5]]
            send_telegram(
                f"🪂 WR2 stale-lease watchdog recovered {len(recovered)}: {ids_short}"
            )
            logger.info("Recovered %d stale leases", len(recovered))
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
