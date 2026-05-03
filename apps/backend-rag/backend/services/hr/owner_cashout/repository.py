"""Read-side repository for owner cashout API endpoints.

All functions return plain dicts suitable for JSON serialization.
"""
from __future__ import annotations

from typing import Any

import asyncpg


async def get_overview(pool: asyncpg.Pool) -> dict[str, Any]:
    async with pool.acquire() as c:
        meta = await c.fetchrow(
            """
            SELECT
                COUNT(*) AS total_weeks,
                MIN(week_start) AS first_week,
                MAX(week_start) AS last_week,
                COALESCE(SUM(total_margin_bz_idr), 0) AS mbz_total,
                COALESCE(SUM(total_margin_bs_idr), 0) AS mbs_total,
                COALESCE(SUM(total_practices), 0) AS practices_total
            FROM owner_weekly_cashout_weeks
            """
        )

        last_week_row = await c.fetchrow(
            """
            SELECT total_margin_bz_idr, total_practices
            FROM owner_weekly_cashout_weeks
            ORDER BY week_start DESC LIMIT 1
            """
        )

        trend_rows = await c.fetch(
            """
            SELECT week_start, total_margin_bz_idr AS margin_bz,
                   total_margin_bs_idr AS margin_bs, total_practices AS practices
            FROM owner_weekly_cashout_weeks
            ORDER BY week_start ASC
            """
        )

    return {
        "total_weeks": meta["total_weeks"],
        "first_week": meta["first_week"],
        "last_week": meta["last_week"],
        "kpi": {
            "margin_bz_total_idr": int(meta["mbz_total"]),
            "margin_bz_last_week_idr": int(last_week_row["total_margin_bz_idr"]) if last_week_row else 0,
            "margin_bs_total_idr": int(meta["mbs_total"]),
            "practices_total": int(meta["practices_total"]),
            "practices_last_week": int(last_week_row["total_practices"]) if last_week_row else 0,
        },
        "trend": [
            {
                "week_start": r["week_start"],
                "margin_bz": int(r["margin_bz"]),
                "margin_bs": int(r["margin_bs"]),
                "practices": int(r["practices"]),
            }
            for r in trend_rows
        ],
    }


async def list_weeks(pool: asyncpg.Pool) -> list[dict[str, Any]]:
    async with pool.acquire() as c:
        rows = await c.fetch(
            """
            SELECT id, week_start, tab_name_bz, tab_name_bs, total_practices,
                   total_income_idr, total_margin_bz_idr, total_margin_bs_idr,
                   last_synced_at
            FROM owner_weekly_cashout_weeks
            ORDER BY week_start DESC
            """
        )
    return [dict(r) for r in rows]


async def get_week_details(
    pool: asyncpg.Pool, week_id: int
) -> dict[str, Any] | None:
    async with pool.acquire() as c:
        week = await c.fetchrow(
            """
            SELECT id, week_start, tab_name_bz, tab_name_bs, total_practices,
                   total_income_idr, total_margin_bz_idr, total_margin_bs_idr,
                   last_synced_at
            FROM owner_weekly_cashout_weeks WHERE id = $1
            """,
            week_id,
        )
        if not week:
            return None

        rows = await c.fetch(
            """
            SELECT entity, row_index, client_name, process, pnbp_idr, urgent_idr,
                   rptka_imta_idr, total_income_idr, margin_bs_idr, margin_bz_idr,
                   final_price_idr, note
            FROM owner_weekly_cashout_rows
            WHERE week_id = $1
            ORDER BY entity, row_index
            """,
            week_id,
        )

        subtotals = await c.fetch(
            """
            SELECT process, COUNT(*) AS count,
                   COALESCE(SUM(margin_bz_idr), 0) AS margin_bz_idr
            FROM owner_weekly_cashout_rows
            WHERE week_id = $1 AND entity = 'BZ' AND process IS NOT NULL
            GROUP BY process
            ORDER BY margin_bz_idr DESC
            """,
            week_id,
        )

    rows_bz = [dict(r) for r in rows if r["entity"] == "BZ"]
    rows_bs = [dict(r) for r in rows if r["entity"] == "BS"]

    return {
        "week": dict(week),
        "rows_bz": rows_bz,
        "rows_bs": rows_bs,
        "subtotals_by_process": [
            {
                "process": s["process"],
                "count": int(s["count"]),
                "margin_bz_idr": int(s["margin_bz_idr"]),
            }
            for s in subtotals
        ],
    }


async def get_visa_types(pool: asyncpg.Pool, *, limit: int = 10) -> dict[str, Any]:
    async with pool.acquire() as c:
        rows = await c.fetch(
            """
            SELECT process,
                   COUNT(*) AS count,
                   COALESCE(SUM(margin_bz_idr), 0) AS margin_bz_total
            FROM owner_weekly_cashout_rows
            WHERE entity = 'BZ' AND process IS NOT NULL
            GROUP BY process
            ORDER BY margin_bz_total DESC
            LIMIT $1
            """,
            limit,
        )
    return {
        "top": [
            {
                "process": r["process"],
                "count": int(r["count"]),
                "margin_bz_total_idr": int(r["margin_bz_total"]),
            }
            for r in rows
        ]
    }
