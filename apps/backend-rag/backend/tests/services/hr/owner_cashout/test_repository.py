"""Tests for owner cashout read-side repository."""
import os
from datetime import date

import asyncpg
import pytest

pytestmark = [
    pytest.mark.integration,
]

from backend.services.hr.owner_cashout.parser import CashoutRow
from backend.services.hr.owner_cashout.repository import (
    get_overview,
    get_visa_types,
    get_week_details,
    list_weeks,
)
from backend.services.hr.owner_cashout.sync_service import upsert_week

_row_idx = 100  # start at 100 to avoid collision with other tests


def _next_idx():
    global _row_idx
    _row_idx += 1
    return _row_idx


@pytest.fixture
async def populated_pool():
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    try:
        pool = await asyncpg.create_pool(url)
    except Exception:
        pytest.skip("PostgreSQL not reachable — skipping integration test")
    try:
        async with pool.acquire() as c:
            await c.execute("DELETE FROM owner_weekly_cashout_rows")
            await c.execute("DELETE FROM owner_weekly_cashout_weeks")
    except asyncpg.exceptions.UndefinedTableError:
        await pool.close()
        pytest.skip("owner_cashout tables not migrated — skipping integration test")

    def bz(name, process, mbz, ti):
        return CashoutRow(
            entity="BZ", row_index=_next_idx(), client_name=name, process=process,
            pnbp_idr=1_000_000, urgent_idr=0, rptka_imta_idr=0,
            total_income_idr=ti, margin_bs_idr=600_000, margin_bz_idr=mbz,
            final_price_idr=0, note=None,
        )

    def bs(name, mbs, fp):
        return CashoutRow(
            entity="BS", row_index=_next_idx(), client_name=name, process="C1",
            pnbp_idr=1_000_000, urgent_idr=0, rptka_imta_idr=0,
            total_income_idr=0, margin_bs_idr=mbs, margin_bz_idr=0,
            final_price_idr=fp, note=None,
        )

    await upsert_week(
        pool, week_start=date(2025, 8, 22),
        tab_bz="BZ 22 AUG", tab_bs="BS 22 AUG",
        rows=[
            bz("A", "C1", 1_100_000, 2_700_000),
            bz("B", "C1", 1_100_000, 2_700_000),
            bz("C", "D12 1 YEAR", 1_700_000, 7_500_000),
            bs("A", 600_000, 1_600_000),
        ],
    )
    await upsert_week(
        pool, week_start=date(2025, 8, 29),
        tab_bz="BZ 29 AUG", tab_bs="BS 29 AUG",
        rows=[
            bz("D", "C1", 1_100_000, 2_700_000),
            bz("E", "D12 1 YEAR", 1_700_000, 7_500_000),
        ],
    )

    yield pool
    await pool.close()


@pytest.mark.asyncio
async def test_get_overview_kpis(populated_pool):
    result = await get_overview(populated_pool)
    assert result["total_weeks"] == 2
    assert result["first_week"] == date(2025, 8, 22)
    assert result["last_week"] == date(2025, 8, 29)
    assert result["kpi"]["margin_bz_total_idr"] == 6_700_000
    assert result["kpi"]["margin_bz_last_week_idr"] == 2_800_000
    assert result["kpi"]["practices_total"] == 5
    assert result["kpi"]["practices_last_week"] == 2


@pytest.mark.asyncio
async def test_get_overview_trend_ordered(populated_pool):
    result = await get_overview(populated_pool)
    trend = result["trend"]
    assert len(trend) == 2
    assert trend[0]["week_start"] == date(2025, 8, 22)
    assert trend[1]["week_start"] == date(2025, 8, 29)


@pytest.mark.asyncio
async def test_list_weeks_returns_newest_first(populated_pool):
    weeks = await list_weeks(populated_pool)
    assert len(weeks) == 2
    assert weeks[0]["week_start"] == date(2025, 8, 29)
    assert weeks[1]["week_start"] == date(2025, 8, 22)


@pytest.mark.asyncio
async def test_get_week_details_drill_down(populated_pool):
    weeks = await list_weeks(populated_pool)
    first_week_id = weeks[1]["id"]  # 22 AUG
    detail = await get_week_details(populated_pool, first_week_id)
    assert detail["week"]["week_start"] == date(2025, 8, 22)
    assert len(detail["rows_bz"]) == 3
    assert len(detail["rows_bs"]) == 1
    subs = {s["process"]: s for s in detail["subtotals_by_process"]}
    assert "C1" in subs
    assert subs["C1"]["count"] == 2
    assert subs["C1"]["margin_bz_idr"] == 2_200_000
    assert subs["D12 1 YEAR"]["count"] == 1


@pytest.mark.asyncio
async def test_get_week_details_not_found(populated_pool):
    assert await get_week_details(populated_pool, 999_999) is None


@pytest.mark.asyncio
async def test_get_visa_types_top_ranked_by_margin(populated_pool):
    result = await get_visa_types(populated_pool)
    top = result["top"]
    assert top[0]["process"] == "D12 1 YEAR"
    assert top[0]["margin_bz_total_idr"] == 3_400_000
    assert top[1]["process"] == "C1"
    assert top[1]["margin_bz_total_idr"] == 3_300_000
