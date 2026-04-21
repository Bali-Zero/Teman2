#!/usr/bin/env python3
"""
Apply migration 119: Partners module — 4 tables + team_members.partner_id + 5 system_settings rows.

Usage:
    python -m backend.migrations.apply_migration_119

On Fly.io:
    fly ssh console -a nuzantara-rag \\
        -C "/bin/sh -c 'cd /app && python -m backend.migrations.apply_migration_119'"

The migration is idempotent (DO $$ IF NOT EXISTS guards, CREATE INDEX IF NOT EXISTS,
ON CONFLICT DO NOTHING on system_settings). Safe to re-run.

Reference: docs/superpowers/specs/2026-04-20-crm-partners-module.md §3
"""

import asyncio
import logging
import os
import sys

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations.migration_119_partners import apply  # noqa: E402

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
        # Pre-flight: check if partners table already exists
        exists = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables "
            "WHERE table_name = 'partners' AND table_schema = 'public')",
        )
        if exists:
            logger.info(
                "Table 'partners' already exists — migration is idempotent, "
                "re-running to verify indexes/columns are present.",
            )

        logger.info(
            "Applying migration 119: partners + partner_referrals + "
            "partner_commissions + partner_audit_log + team_members.partner_id column",
        )
        await apply(conn)

        # Verify core tables exist
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'public' "
            "AND tablename IN ('partners','partner_referrals','partner_commissions','partner_audit_log') "
            "ORDER BY tablename",
        )
        found = {r["tablename"] for r in tables}
        expected = {"partners", "partner_referrals", "partner_commissions", "partner_audit_log"}
        missing = expected - found
        if missing:
            logger.error("❌ Migration 119 post-verify: missing tables %s", missing)
            sys.exit(2)

        # Verify system_settings rows
        rows = await conn.fetch(
            "SELECT key FROM system_settings WHERE key LIKE 'partner_%' ORDER BY key"
        )
        keys = {r["key"] for r in rows}
        expected_keys = {
            "partner_accrual_cooling_off_days",
            "partner_clawback_auto_writeoff_idr",
            "partner_withholding_no_npwp_surcharge",
            "partner_withholding_rate_pph21",
            "partner_withholding_rate_pph23",
        }
        missing_keys = expected_keys - keys
        if missing_keys:
            logger.error("❌ Migration 119 post-verify: missing system_settings keys %s", missing_keys)
            sys.exit(2)

        logger.info(
            "✅ Migration 119 applied. Tables present: %s. system_settings keys: %s",
            ", ".join(sorted(found)),
            ", ".join(sorted(keys)),
        )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
