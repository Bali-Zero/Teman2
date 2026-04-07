"""
Migration 099: Historical bonus import tables

For pre-system bonus data imported from PDF files.
No FK to practices (historical data has no practice_id).
"""

MIGRATION_ID = "099_hr_bonus_historical"

UP_SQL = """
CREATE TABLE IF NOT EXISTS hr_bonus_historical (
    id SERIAL PRIMARY KEY,
    employee_name TEXT NOT NULL,
    employee_id INTEGER,
    bonus_month SMALLINT NOT NULL CHECK (bonus_month BETWEEN 1 AND 12),
    bonus_year SMALLINT NOT NULL CHECK (bonus_year BETWEEN 2020 AND 2100),
    total_amount_idr BIGINT NOT NULL CHECK (total_amount_idr >= 0),
    task_count INTEGER NOT NULL DEFAULT 0,
    source_pdf TEXT NOT NULL,
    accounting_total_data INTEGER,
    accounting_not_paid INTEGER,
    accounting_paid INTEGER,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT,
    UNIQUE (employee_name, bonus_month, bonus_year)
);

CREATE TABLE IF NOT EXISTS hr_bonus_historical_items (
    id SERIAL PRIMARY KEY,
    history_id INTEGER NOT NULL REFERENCES hr_bonus_historical(id) ON DELETE CASCADE,
    row_index INTEGER NOT NULL,
    client_name TEXT NOT NULL,
    service_type TEXT,
    amount_idr BIGINT NOT NULL DEFAULT 0,
    UNIQUE (history_id, row_index)
);

CREATE INDEX IF NOT EXISTS idx_hr_bonus_hist_period
    ON hr_bonus_historical(bonus_year, bonus_month);
CREATE INDEX IF NOT EXISTS idx_hr_bonus_hist_items_parent
    ON hr_bonus_historical_items(history_id);
"""

DOWN_SQL = """
DROP TABLE IF EXISTS hr_bonus_historical_items;
DROP TABLE IF EXISTS hr_bonus_historical;
"""


async def up(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(UP_SQL)


async def down(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(DOWN_SQL)
