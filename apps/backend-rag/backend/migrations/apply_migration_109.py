#!/usr/bin/env python3
"""
Apply migration 109: funnel_sessions + funnel_attributions tables.

Usage:
    python -m backend.migrations.apply_migration_109

Or on Fly.io:
    fly ssh console -a nuzantara-rag -C "cd /app && python -m backend.migrations.apply_migration_109"

Reference: docs/superpowers/specs/2026-04-17-v2-subdomain-rollout-design.md §3.1
"""

import asyncio
import logging
import os
import sys

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations.migration_109_funnel_sessions import apply  # noqa: E402

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
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'funnel_sessions')",
        )
        if exists:
            logger.info(
                "Table funnel_sessions already exists — migration is idempotent (CREATE IF NOT EXISTS + DO block)",
            )

        logger.info("Applying migration 109: funnel_sessions + funnel_attributions")
        await apply(conn)

        # Verify
        row_count = await conn.fetchval("SELECT COUNT(*) FROM funnel_sessions")
        attr_count = await conn.fetchval("SELECT COUNT(*) FROM funnel_attributions")
        logger.info(
            "✅ Migration 109 applied. funnel_sessions rows=%d, funnel_attributions rows=%d",
            row_count,
            attr_count,
        )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
