#!/usr/bin/env python3
"""
Apply migration 127: practice_types.base_price of company_pt_pma 20M -> 25M.

Usage:
    python -m backend.migrations.apply_migration_127

On Fly.io:
    fly ssh console -a nuzantara-rag \\
        -C "/bin/sh -c 'cd /app && python -m backend.migrations.apply_migration_127'"

Data-only and guarded (WHERE base_price = 20000000), so a re-run is a no-op.
Post-verify fails loud when the row exists and still reads 20M.

Reference: owner ruling 2026-10-12 — PT PMA setup price 25.000.000 IDR.
"""

import asyncio
import logging
import os
import sys

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations.migration_127_practice_types_pt_pma_25m import CODE, OLD_PRICE, apply

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    logger.info("Connecting to database...")
    conn = await asyncpg.connect(database_url)
    try:
        exists = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_name = 'practice_types' AND table_schema = 'public')",
        )
        if not exists:
            logger.error("❌ Migration 127 prerequisites not met — 'practice_types' table missing.")
            sys.exit(2)

        logger.info("Applying migration 127: %s base_price -> 25M", CODE)
        await apply(conn)

        price = await conn.fetchval(
            "SELECT base_price FROM practice_types WHERE code = $1",
            CODE,
        )
        if price is not None and int(price) == OLD_PRICE:
            logger.error("❌ Migration 127 post-verify: %s still at %s", CODE, OLD_PRICE)
            sys.exit(2)

        logger.info("✅ Migration 127 applied. %s base_price = %s", CODE, price)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
