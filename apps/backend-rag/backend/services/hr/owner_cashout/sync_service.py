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


async def _create_sync_log(
    pool: asyncpg.Pool, triggered_by: str
) -> int:
    async with pool.acquire() as c:
        return await c.fetchval(
            """
            INSERT INTO owner_cashout_sync_log (status, triggered_by)
            VALUES ('running', $1)
            RETURNING id
            """,
            triggered_by,
        )


async def _finalize_sync_log(
    pool: asyncpg.Pool,
    log_id: int,
    *,
    status: str,
    weeks_processed: int,
    weeks_skipped: int,
    rows_upserted: int,
    unknown_tabs: list[str],
    error: str | None,
) -> None:
    async with pool.acquire() as c:
        await c.execute(
            """
            UPDATE owner_cashout_sync_log SET
                finished_at = now(),
                status = $2,
                weeks_processed = $3,
                weeks_skipped = $4,
                rows_upserted = $5,
                unknown_tabs = $6,
                error = $7
            WHERE id = $1
            """,
            log_id,
            status,
            weeks_processed,
            weeks_skipped,
            rows_upserted,
            ",".join(unknown_tabs) if unknown_tabs else None,
            error,
        )


async def run_sync(pool: asyncpg.Pool, *, triggered_by: str) -> SyncResult:
    """Read sheet, parse all known tabs, upsert to DB, log result."""
    log_id = await _create_sync_log(pool, triggered_by)
    weeks_processed = 0
    weeks_skipped = 0
    rows_upserted = 0
    unknown_tabs: list[str] = []

    try:
        reader = SheetReader()
        all_tabs = reader.list_tabs(SHEET_ID)

        # Group tabs by week_start
        weeks: dict[date, dict[str, str]] = {}
        for tab in all_tabs:
            if tab in JUNK_TABS:
                continue
            if tab not in TAB_TO_WEEK:
                unknown_tabs.append(tab)
                weeks_skipped += 1
                continue
            week_start = TAB_TO_WEEK[tab]
            entry = weeks.setdefault(week_start, {})
            if tab.startswith("BZ"):
                entry["bz"] = tab
            elif tab.startswith("BS"):
                entry["bs"] = tab

        for week_start in sorted(weeks.keys()):
            entry = weeks[week_start]
            tab_bz = entry.get("bz")
            tab_bs = entry.get("bs")
            all_rows: list[CashoutRow] = []

            if tab_bz:
                raw = reader.read_range(SHEET_ID, f"{tab_bz}!A1:I200")
                all_rows.extend(parse_bz_tab(raw))
            if tab_bs:
                raw = reader.read_range(SHEET_ID, f"{tab_bs}!A1:G200")
                all_rows.extend(parse_bs_tab(raw))

            await upsert_week(
                pool,
                week_start=week_start,
                tab_bz=tab_bz,
                tab_bs=tab_bs,
                rows=all_rows,
            )
            weeks_processed += 1
            rows_upserted += len(all_rows)

        if unknown_tabs:
            status = "partial"
            msg = (
                "\u26a0\ufe0f *Owner Cashout sync*: tab sconosciute rilevate.\n"
                f"Tabs: `{', '.join(unknown_tabs)}`\n"
                "Aggiungi entry a `TAB_TO_WEEK` in "
                "`backend/services/hr/owner_cashout/constants.py` e rifai sync."
            )
            await send_alert(msg)
        else:
            status = "success"

        await _finalize_sync_log(
            pool, log_id,
            status=status,
            weeks_processed=weeks_processed,
            weeks_skipped=weeks_skipped,
            rows_upserted=rows_upserted,
            unknown_tabs=unknown_tabs,
            error=None,
        )
        return SyncResult(
            status=status,
            weeks_processed=weeks_processed,
            weeks_skipped=weeks_skipped,
            rows_upserted=rows_upserted,
            unknown_tabs=unknown_tabs,
        )

    except Exception as e:
        logger.exception("[CASHOUT] sync failed")
        await _finalize_sync_log(
            pool, log_id,
            status="failed",
            weeks_processed=weeks_processed,
            weeks_skipped=weeks_skipped,
            rows_upserted=rows_upserted,
            unknown_tabs=unknown_tabs,
            error=str(e)[:500],
        )
        await send_alert(
            f"\u274c *Owner Cashout sync failed*\n```\n{str(e)[:400]}\n```"
        )
        return SyncResult(
            status="failed",
            weeks_processed=weeks_processed,
            weeks_skipped=weeks_skipped,
            rows_upserted=rows_upserted,
            unknown_tabs=unknown_tabs,
            error=str(e)[:500],
        )
