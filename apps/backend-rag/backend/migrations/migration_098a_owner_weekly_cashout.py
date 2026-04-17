"""
Migration 098: Owner Weekly Cashout — Private weekly practice tracking for owner

Tables:
  - owner_weekly_cashout_weeks: one row per ISO-like week, totals
  - owner_weekly_cashout_rows: one row per client practice, per entity (BZ|BS)
  - owner_cashout_sync_log: history of sync runs

Visibility: OWNER ONLY. Isolated from hr_employees / payroll tables.
"""

MIGRATION_ID = "098_owner_weekly_cashout"

UP_SQL = """
CREATE TABLE IF NOT EXISTS owner_weekly_cashout_weeks (
    id SERIAL PRIMARY KEY,
    week_start DATE NOT NULL UNIQUE,
    tab_name_bz TEXT,
    tab_name_bs TEXT,
    total_practices INT NOT NULL DEFAULT 0,
    total_income_idr BIGINT NOT NULL DEFAULT 0,
    total_margin_bz_idr BIGINT NOT NULL DEFAULT 0,
    total_margin_bs_idr BIGINT NOT NULL DEFAULT 0,
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_owner_cashout_weeks_start
    ON owner_weekly_cashout_weeks(week_start DESC);

CREATE TABLE IF NOT EXISTS owner_weekly_cashout_rows (
    id SERIAL PRIMARY KEY,
    week_id INT NOT NULL REFERENCES owner_weekly_cashout_weeks(id) ON DELETE CASCADE,
    entity TEXT NOT NULL CHECK (entity IN ('BZ', 'BS')),
    row_index INT NOT NULL,
    client_name TEXT NOT NULL,
    process TEXT,
    pnbp_idr BIGINT NOT NULL DEFAULT 0,
    urgent_idr BIGINT NOT NULL DEFAULT 0,
    rptka_imta_idr BIGINT NOT NULL DEFAULT 0,
    total_income_idr BIGINT NOT NULL DEFAULT 0,
    margin_bs_idr BIGINT NOT NULL DEFAULT 0,
    margin_bz_idr BIGINT NOT NULL DEFAULT 0,
    final_price_idr BIGINT NOT NULL DEFAULT 0,
    note TEXT,
    UNIQUE (week_id, entity, row_index)
);

CREATE INDEX IF NOT EXISTS idx_owner_cashout_rows_week
    ON owner_weekly_cashout_rows(week_id);

CREATE TABLE IF NOT EXISTS owner_cashout_sync_log (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'partial', 'failed')),
    weeks_processed INT NOT NULL DEFAULT 0,
    weeks_skipped INT NOT NULL DEFAULT 0,
    rows_upserted INT NOT NULL DEFAULT 0,
    unknown_tabs TEXT,
    error TEXT,
    triggered_by TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_owner_cashout_sync_log_started
    ON owner_cashout_sync_log(started_at DESC);
"""

DOWN_SQL = """
DROP TABLE IF EXISTS owner_cashout_sync_log;
DROP TABLE IF EXISTS owner_weekly_cashout_rows;
DROP TABLE IF EXISTS owner_weekly_cashout_weeks;
"""


async def up(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(UP_SQL)


async def down(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(DOWN_SQL)
