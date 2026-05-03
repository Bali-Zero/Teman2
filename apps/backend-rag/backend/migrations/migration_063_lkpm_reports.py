"""
Migration 063: LKPM Investment Activity Reports

Purpose:
- Create `lkpm_reports` table for storing quarterly LKPM drafts and submissions
- Create `lkpm_client_config` table for client investment plans and Jurnal API keys
- Support deterministic LKPM Ready Pack generation (zero AI on numbers)

Tables:
- lkpm_reports: quarterly report data, validation status, OSS submission tracking
- lkpm_client_config: per-client investment plan + Jurnal integration config

Author: Claude Opus 4.6
Date: 2026-03-16
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    """Apply migration 063 — create LKPM tables."""
    logger.info("Applying migration 063: LKPM Investment Activity Reports")

    # 1. Client configuration table (investment plan + Jurnal API)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS lkpm_client_config (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL,
            company_name TEXT NOT NULL,
            npwp TEXT,
            nib TEXT,
            kbli_codes TEXT[] NOT NULL DEFAULT '{}',

            -- Investment plan from BKPM approval (in IDR)
            planned_equipment_domestic BIGINT NOT NULL DEFAULT 0,
            planned_equipment_import BIGINT NOT NULL DEFAULT 0,
            planned_building_domestic BIGINT NOT NULL DEFAULT 0,
            planned_building_import BIGINT NOT NULL DEFAULT 0,
            planned_vehicle_domestic BIGINT NOT NULL DEFAULT 0,
            planned_vehicle_import BIGINT NOT NULL DEFAULT 0,
            planned_land BIGINT NOT NULL DEFAULT 0,
            planned_working_capital BIGINT NOT NULL DEFAULT 0,
            planned_other BIGINT NOT NULL DEFAULT 0,

            -- Employment plan
            planned_tki INTEGER NOT NULL DEFAULT 0,
            planned_tka INTEGER NOT NULL DEFAULT 0,

            -- Jurnal.id integration
            jurnal_api_key TEXT,
            jurnal_company_id TEXT,

            -- Metadata
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT uq_lkpm_client UNIQUE (client_id)
        );
    """)
    logger.info("✅ Created lkpm_client_config table")

    # 2. LKPM reports table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS lkpm_reports (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL,
            quarter TEXT NOT NULL,
            year INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',

            -- Investment realization (6 categories, domestic + import, in IDR)
            realized_equipment_domestic BIGINT NOT NULL DEFAULT 0,
            realized_equipment_import BIGINT NOT NULL DEFAULT 0,
            realized_building_domestic BIGINT NOT NULL DEFAULT 0,
            realized_building_import BIGINT NOT NULL DEFAULT 0,
            realized_vehicle_domestic BIGINT NOT NULL DEFAULT 0,
            realized_vehicle_import BIGINT NOT NULL DEFAULT 0,
            realized_land BIGINT NOT NULL DEFAULT 0,
            realized_working_capital BIGINT NOT NULL DEFAULT 0,
            realized_other BIGINT NOT NULL DEFAULT 0,

            -- Cumulative realization (sum of all quarters)
            cumulative_equipment_domestic BIGINT NOT NULL DEFAULT 0,
            cumulative_equipment_import BIGINT NOT NULL DEFAULT 0,
            cumulative_building_domestic BIGINT NOT NULL DEFAULT 0,
            cumulative_building_import BIGINT NOT NULL DEFAULT 0,
            cumulative_vehicle_domestic BIGINT NOT NULL DEFAULT 0,
            cumulative_vehicle_import BIGINT NOT NULL DEFAULT 0,
            cumulative_land BIGINT NOT NULL DEFAULT 0,
            cumulative_working_capital BIGINT NOT NULL DEFAULT 0,
            cumulative_other BIGINT NOT NULL DEFAULT 0,

            -- Employment
            current_tki INTEGER NOT NULL DEFAULT 0,
            current_tka INTEGER NOT NULL DEFAULT 0,

            -- Revenue (in IDR)
            quarterly_revenue BIGINT NOT NULL DEFAULT 0,
            annual_revenue BIGINT NOT NULL DEFAULT 0,

            -- Narrative / obstacles (template-based, not AI-generated)
            narrative_obstacles TEXT,
            narrative_plans TEXT,

            -- Validation
            validation_status TEXT NOT NULL DEFAULT 'pending',
            validation_alerts JSONB NOT NULL DEFAULT '[]',
            validated_at TIMESTAMPTZ,
            validated_by TEXT,

            -- Client approval
            client_approved BOOLEAN NOT NULL DEFAULT FALSE,
            client_approved_at TIMESTAMPTZ,

            -- OSS submission tracking
            oss_submitted BOOLEAN NOT NULL DEFAULT FALSE,
            oss_submitted_at TIMESTAMPTZ,
            oss_submitted_by TEXT,
            oss_receipt_number TEXT,
            oss_receipt_file_url TEXT,

            -- Data source tracking
            data_source TEXT NOT NULL DEFAULT 'manual',
            has_ai_categorized_items BOOLEAN NOT NULL DEFAULT FALSE,
            ai_categorized_count INTEGER NOT NULL DEFAULT 0,

            -- Metadata
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT uq_lkpm_report UNIQUE (client_id, quarter, year)
        );
    """)
    logger.info("✅ Created lkpm_reports table")

    # 3. Indexes
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_lkpm_reports_client
            ON lkpm_reports (client_id);
        CREATE INDEX IF NOT EXISTS idx_lkpm_reports_quarter
            ON lkpm_reports (year, quarter);
        CREATE INDEX IF NOT EXISTS idx_lkpm_reports_status
            ON lkpm_reports (status);
        CREATE INDEX IF NOT EXISTS idx_lkpm_reports_oss
            ON lkpm_reports (oss_submitted, status);
    """)
    logger.info("✅ Created indexes")

    print("✅ Applied migration 063: LKPM Investment Activity Reports")


async def rollback(conn: Any) -> None:
    """Rollback migration 063 — drop LKPM tables."""
    logger.info("Rolling back migration 063: LKPM Investment Activity Reports")

    await conn.execute("DROP TABLE IF EXISTS lkpm_reports CASCADE;")
    await conn.execute("DROP TABLE IF EXISTS lkpm_client_config CASCADE;")

    logger.info("Migration 063 rolled back successfully")
    print("⏪ Rolled back migration 063: LKPM Investment Activity Reports")
