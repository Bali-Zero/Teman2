#!/usr/bin/env python3
"""
Apply migration 107: bridge_outbox table for Pro<->Fly bidirectional bridge.

Usage:
    python -m backend.migrations.apply_migration_107

Or on Fly.io:
    fly ssh console -a nuzantara-rag -C "cd /app && python -m backend.migrations.apply_migration_107"

Reference: docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md §4
"""

import asyncio
import logging
import os
import sys

import asyncpg

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations.migration_107_bridge_outbox import apply

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
        # Check current state
        exists = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'bridge_outbox')"
        )
        if exists:
            logger.info("Table bridge_outbox already exists — migration is idempotent (CREATE IF NOT EXISTS)")

        logger.info("Applying migration 107: bridge_outbox table")
        await apply(conn)

        # Verify
        exists = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'bridge_outbox')"
        )
        if exists:
            logger.info("✅ Migration 107 applied successfully — bridge_outbox table verified")
        else:
            logger.error("❌ Migration apply() returned but table does not exist")
            sys.exit(1)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
