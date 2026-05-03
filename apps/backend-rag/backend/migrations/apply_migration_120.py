#!/usr/bin/env python3
"""
Apply migration 120: partner_email_outbox — transactional outbox for partner emails.

Usage:
    python -m backend.migrations.apply_migration_120

On Fly.io:
    fly ssh console -a nuzantara-rag \\
        -C "/bin/sh -c 'cd /app && python -m backend.migrations.apply_migration_120'"

Depends on migration 119 (FK to partners, partner_commissions). Idempotent.

Reference: docs/superpowers/reviews/2026-04-21-partners-v1/99-synthesis.md CRIT-2
"""

import asyncio
import logging
import os
import sys

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations.migration_120_partner_email_outbox import apply  # noqa: E402

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

    # Pre-flight: migration 119 must be applied (we depend on partners + partner_commissions)
    logger.info("Connecting to database...")
    conn = await asyncpg.connect(database_url)
    try:
        deps_ok = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_name = 'partners' AND table_schema = 'public')",
        )
        if not deps_ok:
            logger.error(
                "❌ Migration 120 prerequisites not met — 'partners' table missing. "
                "Run apply_migration_119.py first."
            )
            sys.exit(2)

        logger.info("Applying migration 120: partner_email_outbox")
        await apply(conn)

        # Verify
        exists = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_name = 'partner_email_outbox' AND table_schema = 'public')",
        )
        if not exists:
            logger.error("❌ Migration 120 post-verify: partner_email_outbox not found")
            sys.exit(2)

        logger.info("✅ Migration 120 applied. partner_email_outbox ready.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
