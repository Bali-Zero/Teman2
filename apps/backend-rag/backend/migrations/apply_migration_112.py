#!/usr/bin/env python3
"""
Apply migration 112: job_runs table.

Usage:
    python -m backend.migrations.apply_migration_112

Or on Fly.io:
    fly ssh console -a nuzantara-rag -C "cd /app && python -m backend.migrations.apply_migration_112"

Reference: docs/superpowers/specs/2026-04-18-backend-jobs-agents-orchestration-design.md
"""

import asyncio
import logging
import os
import sys

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations.migration_112_job_runs import apply  # noqa: E402

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
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='job_runs')",
        )
        if exists:
            logger.info(
                "Table job_runs already exists; IF NOT EXISTS guards will no-op the CREATE statements"
            )

        logger.info("Applying migration 112: job_runs")
        await apply(conn)

        row_count = await conn.fetchval("SELECT COUNT(*) FROM job_runs")
        logger.info("✅ Migration 112 applied. job_runs rows=%d", row_count)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
