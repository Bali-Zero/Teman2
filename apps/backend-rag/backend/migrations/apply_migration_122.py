#!/usr/bin/env python3
"""
Apply migration 122: insert D1 Tourism tiers (1y/2y/5y) into practice_types.

Usage:
    python -m backend.migrations.apply_migration_122

On Fly.io:
    fly ssh console -a nuzantara-rag \\
        -C "/bin/sh -c 'cd /app && python -m backend.migrations.apply_migration_122'"

Idempotent (UPSERT on `code`).
"""

import asyncio
import logging
import os
import sys

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations.migration_122_practice_types_visa_d1_5yr import apply  # noqa: E402

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
            logger.error("❌ Migration 122 prerequisites not met — practice_types table missing")
            sys.exit(2)

        logger.info("Applying migration 122: D1 Tourism tiers (1y/2y/5y)")
        await apply(conn)

        rows = await conn.fetch(
            "SELECT code, name, base_price, typical_duration_days, is_active "
            "FROM practice_types "
            "WHERE code = ANY($1::text[]) ORDER BY typical_duration_days",
            [
                "visa_d1_tourism_1yr",
                "visa_d1_tourism_2yr",
                "visa_d1_tourism_5yr",
            ],
        )
        if len(rows) != 3 or not all(r["is_active"] for r in rows):
            logger.error(
                "❌ Migration 122 post-verify: expected 3 active D1 tiers, got %d",
                len(rows),
            )
            sys.exit(2)

        for r in rows:
            logger.info(
                "✅ %s — %s IDR, %s days",
                r["name"],
                r["base_price"],
                r["typical_duration_days"],
            )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
