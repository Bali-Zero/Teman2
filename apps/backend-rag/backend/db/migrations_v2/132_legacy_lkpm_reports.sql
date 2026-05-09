-- 132_legacy_lkpm_reports.sql
--
-- Promote `lkpm_reports` to migrations_v2. Two things at once:
--
-- 1. CREATE TABLE IF NOT EXISTS — mirrors the schema that lived in
--    backend/migrations/migration_063_lkpm_reports.py (old-style Python
--    migration the v2 runner does not discover) plus the additions made
--    by migration_100a_lkpm_company_id.py.
--
-- 2. The realized_*/cumulative_* columns were declared NOT NULL DEFAULT
--    0 in migration_063, but prod relaxed them to nullable via a
--    hand-run ALTER that never became a tracked migration. The
--    test_lkpm_ready_pack_automation suite intentionally INSERTs NULLs
--    to exercise the validator; without the relaxation, a fresh
--    DB rejects those inserts.
--
-- Idempotent: every statement uses IF NOT EXISTS / DROP NOT NULL. No-op
-- on prod (already in this shape), converges partially bootstrapped DBs
-- where lkpm_reports exists without every promoted column, and remains
-- safe on previously-bootstrapped CI.
--
-- Reserved gap: number 131 is intentionally skipped — it's reserved for
-- 131_unify_migration_tracking.sql in Strategy 01 Step 3.

CREATE TABLE IF NOT EXISTS lkpm_reports (
    id                              SERIAL PRIMARY KEY,
    client_id                       INTEGER NOT NULL,
    quarter                         TEXT NOT NULL,
    year                            INTEGER NOT NULL,
    status                          TEXT NOT NULL DEFAULT 'draft',
    lkpm_assigned_to                TEXT,

    realized_equipment_domestic     BIGINT NOT NULL DEFAULT 0,
    realized_equipment_import       BIGINT NOT NULL DEFAULT 0,
    realized_building_domestic      BIGINT NOT NULL DEFAULT 0,
    realized_building_import        BIGINT NOT NULL DEFAULT 0,
    realized_vehicle_domestic       BIGINT NOT NULL DEFAULT 0,
    realized_vehicle_import         BIGINT NOT NULL DEFAULT 0,
    realized_land                   BIGINT NOT NULL DEFAULT 0,
    realized_working_capital        BIGINT NOT NULL DEFAULT 0,
    realized_other                  BIGINT NOT NULL DEFAULT 0,

    cumulative_equipment_domestic   BIGINT NOT NULL DEFAULT 0,
    cumulative_equipment_import     BIGINT NOT NULL DEFAULT 0,
    cumulative_building_domestic    BIGINT NOT NULL DEFAULT 0,
    cumulative_building_import      BIGINT NOT NULL DEFAULT 0,
    cumulative_vehicle_domestic     BIGINT NOT NULL DEFAULT 0,
    cumulative_vehicle_import       BIGINT NOT NULL DEFAULT 0,
    cumulative_land                 BIGINT NOT NULL DEFAULT 0,
    cumulative_working_capital      BIGINT NOT NULL DEFAULT 0,
    cumulative_other                BIGINT NOT NULL DEFAULT 0,

    current_tki                     INTEGER NOT NULL DEFAULT 0,
    current_tka                     INTEGER NOT NULL DEFAULT 0,

    quarterly_revenue               BIGINT NOT NULL DEFAULT 0,
    annual_revenue                  BIGINT NOT NULL DEFAULT 0,

    narrative_obstacles             TEXT,
    narrative_plans                 TEXT,

    validation_status               TEXT NOT NULL DEFAULT 'pending',
    validation_alerts               JSONB NOT NULL DEFAULT '[]',
    validated_at                    TIMESTAMPTZ,
    validated_by                    TEXT,

    client_approved                 BOOLEAN NOT NULL DEFAULT FALSE,
    client_approved_at              TIMESTAMPTZ,

    oss_submitted                   BOOLEAN NOT NULL DEFAULT FALSE,
    oss_submitted_at                TIMESTAMPTZ,
    oss_submitted_by                TEXT,
    oss_receipt_number              TEXT,
    oss_receipt_file_url            TEXT,

    data_source                     TEXT NOT NULL DEFAULT 'manual',
    has_ai_categorized_items        BOOLEAN NOT NULL DEFAULT FALSE,
    ai_categorized_count            INTEGER NOT NULL DEFAULT 0,

    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- CREATE TABLE IF NOT EXISTS does not add missing columns on a partial table.
-- Re-state the promoted shape as ADD COLUMN IF NOT EXISTS before relaxing
-- realization nullability, so this migration can repair a half-bootstrapped
-- lkpm_reports relation instead of crashing on the first missing column.
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS client_id INTEGER;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS quarter TEXT;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS year INTEGER;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'draft';
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS lkpm_assigned_to TEXT;

ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS realized_equipment_domestic BIGINT DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS realized_equipment_import BIGINT DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS realized_building_domestic BIGINT DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS realized_building_import BIGINT DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS realized_vehicle_domestic BIGINT DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS realized_vehicle_import BIGINT DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS realized_land BIGINT DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS realized_working_capital BIGINT DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS realized_other BIGINT DEFAULT 0;

ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS cumulative_equipment_domestic BIGINT DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS cumulative_equipment_import BIGINT DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS cumulative_building_domestic BIGINT DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS cumulative_building_import BIGINT DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS cumulative_vehicle_domestic BIGINT DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS cumulative_vehicle_import BIGINT DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS cumulative_land BIGINT DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS cumulative_working_capital BIGINT DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS cumulative_other BIGINT DEFAULT 0;

ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS current_tki INTEGER DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS current_tka INTEGER DEFAULT 0;

ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS quarterly_revenue BIGINT DEFAULT 0;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS annual_revenue BIGINT DEFAULT 0;

ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS narrative_obstacles TEXT;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS narrative_plans TEXT;

ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS validation_status TEXT DEFAULT 'pending';
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS validation_alerts JSONB DEFAULT '[]'::jsonb;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS validated_at TIMESTAMPTZ;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS validated_by TEXT;

ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS client_approved BOOLEAN DEFAULT FALSE;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS client_approved_at TIMESTAMPTZ;

ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS oss_submitted BOOLEAN DEFAULT FALSE;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS oss_submitted_at TIMESTAMPTZ;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS oss_submitted_by TEXT;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS oss_receipt_number TEXT;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS oss_receipt_file_url TEXT;

ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS data_source TEXT DEFAULT 'manual';
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS has_ai_categorized_items BOOLEAN DEFAULT FALSE;
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS ai_categorized_count INTEGER DEFAULT 0;

ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- company_id was added by migration_100a_lkpm_company_id.py (old-style
-- Python migration). lkpm_ready_pack joins lkpm_reports r ↔
-- lkpm_client_config cfg on COALESCE(r.company_id, 0) = COALESCE(cfg.company_id, 0).
ALTER TABLE lkpm_reports ADD COLUMN IF NOT EXISTS company_id INTEGER;

-- Relax NOT NULL on every realized_*/cumulative_* column to match prod.
-- Tests insert NULLs to exercise the validator; prod accepted the same
-- via an out-of-band ALTER. DROP NOT NULL is idempotent — re-running
-- against a column that's already nullable is a no-op.
ALTER TABLE lkpm_reports ALTER COLUMN realized_equipment_domestic   DROP NOT NULL;
ALTER TABLE lkpm_reports ALTER COLUMN realized_equipment_import     DROP NOT NULL;
ALTER TABLE lkpm_reports ALTER COLUMN realized_building_domestic    DROP NOT NULL;
ALTER TABLE lkpm_reports ALTER COLUMN realized_building_import      DROP NOT NULL;
ALTER TABLE lkpm_reports ALTER COLUMN realized_vehicle_domestic     DROP NOT NULL;
ALTER TABLE lkpm_reports ALTER COLUMN realized_vehicle_import       DROP NOT NULL;
ALTER TABLE lkpm_reports ALTER COLUMN realized_land                 DROP NOT NULL;
ALTER TABLE lkpm_reports ALTER COLUMN realized_working_capital      DROP NOT NULL;
ALTER TABLE lkpm_reports ALTER COLUMN realized_other                DROP NOT NULL;
ALTER TABLE lkpm_reports ALTER COLUMN cumulative_equipment_domestic DROP NOT NULL;
ALTER TABLE lkpm_reports ALTER COLUMN cumulative_equipment_import   DROP NOT NULL;
ALTER TABLE lkpm_reports ALTER COLUMN cumulative_building_domestic  DROP NOT NULL;
ALTER TABLE lkpm_reports ALTER COLUMN cumulative_building_import    DROP NOT NULL;
ALTER TABLE lkpm_reports ALTER COLUMN cumulative_vehicle_domestic   DROP NOT NULL;
ALTER TABLE lkpm_reports ALTER COLUMN cumulative_vehicle_import     DROP NOT NULL;
ALTER TABLE lkpm_reports ALTER COLUMN cumulative_land               DROP NOT NULL;
ALTER TABLE lkpm_reports ALTER COLUMN cumulative_working_capital    DROP NOT NULL;
ALTER TABLE lkpm_reports ALTER COLUMN cumulative_other              DROP NOT NULL;

-- === ROLLBACK ===
-- The rollback only undoes the column add; restoring NOT NULL on every
-- realized_*/cumulative_* would fail on rows that legitimately store
-- NULL today (the validator path). DROP TABLE is intentionally NOT
-- offered — lkpm_reports holds compliance data we cannot lose.
ALTER TABLE lkpm_reports DROP COLUMN IF EXISTS company_id;
