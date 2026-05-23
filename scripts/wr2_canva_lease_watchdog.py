#!/usr/bin/env python3
"""10-min watchdog: reset stale war_room_drafts.status='rendering' leases.

W49 (2026-05-23): connect-with-retry for pg-proxy WG tunnel idle-conn drop.
Pre-W49 empirical: 98 lifetime asyncpg.TimeoutError on connect (cf.
~/logs/wr2_canva_lease_watchdog.error.log lifetime grep). Each timeout was
a lost tick (cron retries 10min later, accumulating stale-lease window).
W47-family pattern: pg-proxy tunnel drops idle conns at ~10s, so a single
asyncpg.connect(timeout=10) competes with the drop. Retry with backoff
absorbs the race; exit 0 on retry-exhaust because losing one tick is
harmless for a recovery watchdog (next tick still resets stale leases).
"""
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

CONNECT_TIMEOUT_SEC = 10
MAX_RETRIES = 3
BACKOFF_SEC = (1, 3, 7)  # progressive backoff per retry


async def _connect_with_retry(dsn: str) -> asyncpg.Connection | None:
    """Best-effort connect; returns None on exhaust (caller exits cleanly)."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await asyncpg.connect(dsn, timeout=CONNECT_TIMEOUT_SEC)
        except (asyncio.TimeoutError, OSError, asyncpg.PostgresError) as e:
            if attempt == MAX_RETRIES:
                logger.warning(
                    "connect exhausted %d retries (last error: %s: %s); skipping tick",
                    MAX_RETRIES, type(e).__name__, e,
                )
                return None
            sleep_for = BACKOFF_SEC[attempt - 1]
            logger.info(
                "connect attempt %d/%d failed (%s: %s); retry in %ds",
                attempt, MAX_RETRIES, type(e).__name__, e, sleep_for,
            )
            await asyncio.sleep(sleep_for)
    return None  # unreachable; mypy comfort


async def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.critical("DATABASE_URL not set")
        return 2
    conn = await _connect_with_retry(dsn)
    if conn is None:
        # All retries exhausted. Exit 0: next cron tick (~10min) will catch
        # any leases this tick would have recovered. Stale-lease threshold
        # is 15min so a single missed tick stays within tolerance.
        return 0
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
