"""Sync service for owner weekly cashout.

Reads the WEEKLY CASHOUT sheet, parses BZ/BS tabs, upserts to Postgres atomically
per week. Logs each run to owner_cashout_sync_log.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import asyncpg

from backend.services.hr.owner_cashout.constants import (
    JUNK_TABS,
    SHEET_ID,
    TAB_TO_WEEK,
)
from backend.services.hr.owner_cashout.parser import (
    CashoutRow,
    parse_bs_tab,
    parse_bz_tab,
)
from backend.services.hr.owner_cashout.sheet_reader import SheetReader
from backend.services.hr.owner_cashout.telegram_alert import send_alert

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    status: str                  # 'success' | 'partial' | 'failed'
    weeks_processed: int
    weeks_skipped: int
    rows_upserted: int
    unknown_tabs: list[str]
    error: str | None = None


async def upsert_week(
    pool: asyncpg.Pool,
    *,
    week_start: date,
    tab_bz: str | None,
    tab_bs: str | None,
    rows: list[CashoutRow],
) -> int:
    """Atomically replace a week's data. Returns week_id."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            week_id: int = await conn.fetchval(
                """
                INSERT INTO owner_weekly_cashout_weeks
                    (week_start, tab_name_bz, tab_name_bs, last_synced_at)
                VALUES ($1, $2, $3, now())
                ON CONFLICT (week_start) DO UPDATE SET
                    tab_name_bz = EXCLUDED.tab_name_bz,
                    tab_name_bs = EXCLUDED.tab_name_bs,
                    last_synced_at = now()
                RETURNING id
                """,
                week_start, tab_bz, tab_bs,
            )

            await conn.execute(
                "DELETE FROM owner_weekly_cashout_rows WHERE week_id = $1",
                week_id,
            )

            if rows:
                records = [
                    (
                        week_id, r.entity, r.row_index, r.client_name, r.process,
                        r.pnbp_idr, r.urgent_idr, r.rptka_imta_idr, r.total_income_idr,
                        r.margin_bs_idr, r.margin_bz_idr, r.final_price_idr, r.note,
                    )
                    for r in rows
                ]
                await conn.executemany(
                    """
                    INSERT INTO owner_weekly_cashout_rows
                        (week_id, entity, row_index, client_name, process,
                         pnbp_idr, urgent_idr, rptka_imta_idr, total_income_idr,
                         margin_bs_idr, margin_bz_idr, final_price_idr, note)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                    """,
                    records,
                )

            await conn.execute(
                """
                UPDATE owner_weekly_cashout_weeks SET
                    total_practices = (
                        SELECT COUNT(*) FROM owner_weekly_cashout_rows
                        WHERE week_id = $1 AND entity = 'BZ'
                    ),
                    total_income_idr = COALESCE((
                        SELECT SUM(total_income_idr) FROM owner_weekly_cashout_rows
                        WHERE week_id = $1 AND entity = 'BZ'
                    ), 0),
                    total_margin_bz_idr = COALESCE((
                        SELECT SUM(margin_bz_idr) FROM owner_weekly_cashout_rows
                        WHERE week_id = $1 AND entity = 'BZ'
                    ), 0),
                    total_margin_bs_idr = COALESCE((
                        SELECT SUM(margin_bs_idr) FROM owner_weekly_cashout_rows
                        WHERE week_id = $1 AND entity = 'BS'
                    ), 0)
                WHERE id = $1
                """,
                week_id,
            )
            return week_id


async def run_sync(pool: asyncpg.Pool, *, triggered_by: str) -> SyncResult:
    raise NotImplementedError  # implemented in Task 11
