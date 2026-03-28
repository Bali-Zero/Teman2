#!/usr/bin/env python3
"""Check team_members table schema."""

import asyncio
import logging
import os

import asyncpg

logger = logging.getLogger(__name__)


async def check_schema():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not set")
        return

    conn = await asyncpg.connect(database_url)

    try:
        rows = await conn.fetch(
            """
            SELECT column_name, is_nullable, data_type
            FROM information_schema.columns
            WHERE table_name = 'team_members'
            ORDER BY ordinal_position
            """,
        )
        logger.info("=== team_members table schema ===")
        for row in rows:
            logger.info(f"{row['column_name']:20} {row['is_nullable']:5} {row['data_type']}")

        # Check existing team members
        members = await conn.fetch("SELECT full_name, name, email FROM team_members")
        logger.info("\n=== existing team members ===")
        for m in members:
            logger.info(f"full_name={m['full_name']}, name={m['name']}, email={m['email']}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(check_schema())
