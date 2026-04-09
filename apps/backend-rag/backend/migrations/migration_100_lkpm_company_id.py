"""
Migration 100: Add company_id to LKPM tables

Purpose:
- Add company_id to lkpm_reports and lkpm_client_config
- Change UNIQUE constraints to include company_id
- A single client (director) can have multiple PT PMAs, each with its own LKPM report
- Backfill company_id from lkpm_client_config JOIN companies

Author: Claude Opus 4.6
Date: 2026-04-09
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    """Apply migration 100 — add company_id to LKPM tables."""
    logger.info("Applying migration 100: LKPM company_id support")

    # 1. Add company_id to lkpm_client_config
    await conn.execute("""
        ALTER TABLE lkpm_client_config
            ADD COLUMN IF NOT EXISTS company_id INTEGER;
    """)
    logger.info("✅ Added company_id to lkpm_client_config")

    # 2. Backfill lkpm_client_config.company_id from companies table
    updated_config = await conn.execute("""
        UPDATE lkpm_client_config lc
        SET company_id = sub.company_id
        FROM (
            SELECT lc2.id AS config_id, c.id AS company_id
            FROM lkpm_client_config lc2
            JOIN companies c ON LOWER(TRIM(c.company_name)) = LOWER(TRIM(lc2.company_name))
            WHERE lc2.company_id IS NULL
        ) sub
        WHERE lc.id = sub.config_id
    """)
    logger.info(f"✅ Backfilled lkpm_client_config rows with company_id: {updated_config}")

    # 3. Add company_id to lkpm_reports
    await conn.execute("""
        ALTER TABLE lkpm_reports
            ADD COLUMN IF NOT EXISTS company_id INTEGER;
    """)
    logger.info("✅ Added company_id to lkpm_reports")

    # 4. Backfill lkpm_reports.company_id from lkpm_client_config
    updated_reports = await conn.execute("""
        UPDATE lkpm_reports r
        SET company_id = lc.company_id
        FROM lkpm_client_config lc
        WHERE r.client_id = lc.client_id
          AND r.company_id IS NULL
          AND lc.company_id IS NOT NULL
    """)
    logger.info(f"✅ Backfilled lkpm_reports rows with company_id: {updated_reports}")

    # 5. Drop old UNIQUE constraints and create new ones
    # lkpm_client_config: was UNIQUE(client_id), now UNIQUE(client_id, company_id)
    await conn.execute("""
        ALTER TABLE lkpm_client_config
            DROP CONSTRAINT IF EXISTS uq_lkpm_client;
    """)
    await conn.execute("""
        ALTER TABLE lkpm_client_config
            ADD CONSTRAINT uq_lkpm_client UNIQUE (client_id, company_id);
    """)
    logger.info("✅ Updated lkpm_client_config UNIQUE to (client_id, company_id)")

    # lkpm_reports: was UNIQUE(client_id, quarter, year), now UNIQUE(client_id, company_id, quarter, year)
    await conn.execute("""
        ALTER TABLE lkpm_reports
            DROP CONSTRAINT IF EXISTS uq_lkpm_report;
    """)
    await conn.execute("""
        ALTER TABLE lkpm_reports
            ADD CONSTRAINT uq_lkpm_report UNIQUE (client_id, company_id, quarter, year);
    """)
    logger.info("✅ Updated lkpm_reports UNIQUE to (client_id, company_id, quarter, year)")

    # 6. Index on company_id for both tables
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_lkpm_config_company
            ON lkpm_client_config (company_id);
        CREATE INDEX IF NOT EXISTS idx_lkpm_reports_company
            ON lkpm_reports (company_id);
    """)
    logger.info("✅ Created company_id indexes")

    print("✅ Applied migration 100: LKPM company_id support")


async def rollback(conn: Any) -> None:
    """Rollback migration 100."""
    logger.info("Rolling back migration 100: LKPM company_id support")

    # Restore old constraints
    await conn.execute("ALTER TABLE lkpm_reports DROP CONSTRAINT IF EXISTS uq_lkpm_report;")
    await conn.execute("""
        ALTER TABLE lkpm_reports
            ADD CONSTRAINT uq_lkpm_report UNIQUE (client_id, quarter, year);
    """)

    await conn.execute("ALTER TABLE lkpm_client_config DROP CONSTRAINT IF EXISTS uq_lkpm_client;")
    await conn.execute("""
        ALTER TABLE lkpm_client_config
            ADD CONSTRAINT uq_lkpm_client UNIQUE (client_id);
    """)

    # Drop columns
    await conn.execute("DROP INDEX IF EXISTS idx_lkpm_reports_company;")
    await conn.execute("DROP INDEX IF EXISTS idx_lkpm_config_company;")
    await conn.execute("ALTER TABLE lkpm_reports DROP COLUMN IF EXISTS company_id;")
    await conn.execute("ALTER TABLE lkpm_client_config DROP COLUMN IF EXISTS company_id;")

    print("✅ Rolled back migration 100: LKPM company_id support")
