#!/usr/bin/env python3
"""
Apply migration 032: Drop legacy KG tables

Usage:
    python -m backend.migrations.apply_migration_032

Or on Fly.io:
    fly ssh console -a nuzantara-rag -C "cd /app && python -m backend.migrations.apply_migration_032"
"""

import asyncio
import logging
import os
import sys

import asyncpg

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations.migration_032_drop_legacy_kg_tables import MIGRATION_ID, MIGRATION_NAME, run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    logger.info("Connecting to database...")
    conn = await asyncpg.connect(database_url)

    try:
        # Check current state before migration
        legacy_tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('kg_entities', 'kg_relationships', 'kg_entity_mentions')
        """)

        if legacy_tables:
            table_names = [t['table_name'] for t in legacy_tables]
            logger.info(f"Found legacy tables to drop: {table_names}")

            # Show row counts before dropping
            for table in table_names:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                logger.info(f"  - {table}: {count} rows")
        else:
            logger.info("No legacy KG tables found (already dropped or never created)")

        # Run migration
        async with conn.transaction():
            success = await run(conn)

        if success:
            logger.info(f"✅ Migration {MIGRATION_ID} ({MIGRATION_NAME}) applied successfully")
        else:
            logger.error(f"❌ Migration {MIGRATION_ID} failed")
            sys.exit(1)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
