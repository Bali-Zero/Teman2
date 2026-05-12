#!/usr/bin/env python3
"""One-shot backfill: apply Tier 1 router rules to all existing unrouted items.

Run this AFTER deploying the router (so newly-arrived items are routed live
by the listener, but pre-deploy items still in routing_status='unrouted' need
this manual sweep).

Usage:
    cd ~/Desktop/nuzantara
    source apps/backend-rag/.venv/bin/activate
    PYTHONPATH=apps/backend-rag python3 scripts/intel-lake-router-backfill.py

Requires DATABASE_URL env var (Fly proxy on localhost:15432).
"""
import asyncio
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("intel-lake-router-backfill")


async def main() -> int:
    import asyncpg  # noqa: PLC0415

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag",
    )
    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=3)
    if pool is None:
        logger.error("failed to create asyncpg pool")
        return 1

    try:
        from backend.services.intel.intel_lake_router import backfill_unrouted  # noqa: PLC0415

        total = await backfill_unrouted(pool, batch_size=100)
        logger.info("✅ backfill complete: %s items routed", total)
        return 0
    except Exception as exc:
        logger.exception("backfill failed: %s", exc)
        return 1
    finally:
        await pool.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
