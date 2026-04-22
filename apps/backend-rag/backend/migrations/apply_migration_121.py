#!/usr/bin/env python3
"""
Apply migration 121: practices.family_member_id — tag a practice with a dependent.

Usage:
    python -m backend.migrations.apply_migration_121

On Fly.io:
    fly ssh console -a nuzantara-rag \\
        -C "/bin/sh -c 'cd /app && python -m backend.migrations.apply_migration_121'"

Depends on tables `practices` + `client_family_members` (both pre-existing). Idempotent.

Reference: PR #195 — feat(crm) tag practices by family member for dependent processes.
"""

import asyncio
import logging
import os
import sys

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations.migration_121_practices_family_member import apply  # noqa: E402

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
        # Pre-flight: both parent tables must exist
        for table in ("practices", "client_family_members"):
            exists = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.tables "
                "WHERE table_name = $1 AND table_schema = 'public')",
                table,
            )
            if not exists:
                logger.error(
                    f"❌ Migration 121 prerequisites not met — '{table}' table missing.",
                )
                sys.exit(2)

        logger.info("Applying migration 121: practices.family_member_id")
        await apply(conn)

        # Verify column + FK
        col_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.columns "
            "WHERE table_name = 'practices' AND column_name = 'family_member_id' "
            "AND table_schema = 'public')",
        )
        if not col_exists:
            logger.error("❌ Migration 121 post-verify: practices.family_member_id not found")
            sys.exit(2)

        logger.info("✅ Migration 121 applied. practices.family_member_id ready.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
