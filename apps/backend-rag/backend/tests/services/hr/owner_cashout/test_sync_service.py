"""Tests for owner cashout sync service (upsert_week + run_sync)."""
import os
from datetime import date

import asyncpg
import pytest

pytestmark = [
    pytest.mark.integration,
]

from backend.services.hr.owner_cashout.parser import CashoutRow
from backend.services.hr.owner_cashout.sync_service import upsert_week


@pytest.fixture
async def db_pool(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    try:
        pool = await asyncpg.create_pool(url)
    except Exception:
        pytest.skip("PostgreSQL not reachable — skipping integration test")
    # Clean slate for this test run
    try:
        async with pool.acquire() as c:
            await c.execute("DELETE FROM owner_weekly_cashout_rows")
            await c.execute("DELETE FROM owner_weekly_cashout_weeks")
            await c.execute("DELETE FROM owner_cashout_sync_log")
    except asyncpg.exceptions.UndefinedTableError:
        await pool.close()
        pytest.skip("owner_cashout tables not migrated — skipping integration test")
    yield pool
    await pool.close()


_row_counter = 0


def _next_row_index() -> int:
    global _row_counter
    _row_counter += 1
    return _row_counter


def make_bz_row(name: str, margin_bz: int, total_income: int) -> CashoutRow:
    return CashoutRow(
        entity="BZ",
        row_index=_next_row_index(),
        client_name=name,
        process="C1",
        pnbp_idr=1_000_000,
        urgent_idr=0,
        rptka_imta_idr=0,
        total_income_idr=total_income,
        margin_bs_idr=600_000,
        margin_bz_idr=margin_bz,
        final_price_idr=0,
        note=None,
    )


def make_bs_row(name: str, margin_bs: int, final_price: int) -> CashoutRow:
    return CashoutRow(
        entity="BS",
        row_index=_next_row_index(),
        client_name=name,
        process="C1",
        pnbp_idr=1_000_000,
        urgent_idr=0,
        rptka_imta_idr=0,
        total_income_idr=0,
        margin_bs_idr=margin_bs,
        margin_bz_idr=0,
        final_price_idr=final_price,
        note=None,
    )


@pytest.mark.asyncio
async def test_upsert_week_inserts_week_and_rows(db_pool):
    rows_bz = [
        make_bz_row("CLIENT A", 1_000_000, 2_700_000),
        make_bz_row("CLIENT B", 1_100_000, 2_700_000),
    ]
    rows_bs = [make_bs_row("CLIENT A", 600_000, 1_600_000)]

    week_id = await upsert_week(
        db_pool,
        week_start=date(2025, 8, 22),
        tab_bz="BZ 22 AUG",
        tab_bs="BS 22 AUG",
        rows=rows_bz + rows_bs,
    )

    async with db_pool.acquire() as c:
        week = await c.fetchrow(
            "SELECT * FROM owner_weekly_cashout_weeks WHERE id = $1", week_id
        )
        assert week["week_start"] == date(2025, 8, 22)
        assert week["tab_name_bz"] == "BZ 22 AUG"
        assert week["tab_name_bs"] == "BS 22 AUG"
        assert week["total_practices"] == 2  # 2 BZ clients
        assert week["total_income_idr"] == 5_400_000
        assert week["total_margin_bz_idr"] == 2_100_000
        assert week["total_margin_bs_idr"] == 600_000

        rows = await c.fetch(
            "SELECT entity, client_name FROM owner_weekly_cashout_rows WHERE week_id = $1 ORDER BY entity, client_name",
            week_id,
        )
        assert len(rows) == 3  # 2 BZ + 1 BS


@pytest.mark.asyncio
async def test_upsert_week_is_idempotent(db_pool):
    rows_bz = [make_bz_row("CLIENT A", 1_000_000, 2_700_000)]

    id1 = await upsert_week(
        db_pool, week_start=date(2025, 8, 22),
        tab_bz="BZ 22 AUG", tab_bs="BS 22 AUG", rows=rows_bz,
    )
    id2 = await upsert_week(
        db_pool, week_start=date(2025, 8, 22),
        tab_bz="BZ 22 AUG", tab_bs="BS 22 AUG", rows=rows_bz,
    )

    assert id1 == id2
    async with db_pool.acquire() as c:
        count = await c.fetchval(
            "SELECT COUNT(*) FROM owner_weekly_cashout_rows WHERE week_id = $1", id1
        )
        assert count == 1  # not duplicated


@pytest.mark.asyncio
async def test_upsert_week_replaces_rows_on_rerun(db_pool):
    # First run: 2 clients
    rows_first = [
        make_bz_row("CLIENT A", 1_000_000, 2_700_000),
        make_bz_row("CLIENT B", 1_100_000, 2_700_000),
    ]
    await upsert_week(
        db_pool, week_start=date(2025, 8, 22),
        tab_bz="BZ 22 AUG", tab_bs=None, rows=rows_first,
    )

    # Second run: only 1 client (client B removed from sheet)
    rows_second = [make_bz_row("CLIENT A", 1_000_000, 2_700_000)]
    week_id = await upsert_week(
        db_pool, week_start=date(2025, 8, 22),
        tab_bz="BZ 22 AUG", tab_bs=None, rows=rows_second,
    )

    async with db_pool.acquire() as c:
        names = [
            r["client_name"]
            for r in await c.fetch(
                "SELECT client_name FROM owner_weekly_cashout_rows WHERE week_id = $1",
                week_id,
            )
        ]
        assert names == ["CLIENT A"]

        week = await c.fetchrow(
            "SELECT total_practices, total_margin_bz_idr FROM owner_weekly_cashout_weeks WHERE id = $1",
            week_id,
        )
        assert week["total_practices"] == 1
        assert week["total_margin_bz_idr"] == 1_000_000


from unittest.mock import patch


class FakeReader:
    def __init__(self, tabs: dict[str, list[list[str]]]):
        self.tabs = tabs

    def list_tabs(self, sheet_id: str) -> list[str]:
        return list(self.tabs.keys())

    def read_range(self, sheet_id: str, range_: str) -> list[list[str]]:
        # range_ is like "BZ 22 AUG!A1:I200"
        tab = range_.split("!")[0]
        return self.tabs.get(tab, [])


@pytest.mark.asyncio
async def test_run_sync_happy_path(db_pool):
    from backend.services.hr.owner_cashout.sync_service import run_sync

    fake_tabs = {
        "BZ 22 AUG": [
            ["NEW CASHOUT"],
            ["NAME", "PROCESS", "PNBP", "URGENT", "RPTKA/IMTA", "TOTAL INCOME", "MARGIN BS", "MARGIN BZ", "NOTE"],
            ["A BC", "C1", "Rp1,000,000", "", "", "Rp2,700,000", "Rp600,000", "Rp1,100,000"],
        ],
        "BS 22 AUG": [
            ["NEW CASHOUT"],
            ["NAME", "PROCESS", "PNBP", "URGENT", "RPTKA/IMTA", "MARGIN BS", "FINAL PRICE"],
            ["A BC", "C1", "Rp1,000,000", "", "", "Rp600,000", "Rp1,600,000"],
        ],
        "Sheet18": [["junk"]],
    }

    with patch(
        "backend.services.hr.owner_cashout.sync_service.SheetReader",
        return_value=FakeReader(fake_tabs),
    ):
        result = await run_sync(db_pool, triggered_by="test")

    assert result.status == "success"
    assert result.weeks_processed == 1
    assert result.rows_upserted == 2
    assert result.unknown_tabs == []


@pytest.mark.asyncio
async def test_run_sync_unknown_tab_triggers_partial(db_pool):
    from backend.services.hr.owner_cashout.sync_service import run_sync

    fake_tabs = {
        "BZ 22 AUG": [
            ["NEW CASHOUT"],
            ["NAME", "PROCESS", "PNBP", "URGENT", "RPTKA/IMTA", "TOTAL INCOME", "MARGIN BS", "MARGIN BZ", "NOTE"],
            ["A BC", "C1", "Rp1,000,000", "", "", "Rp2,700,000", "Rp600,000", "Rp1,100,000"],
        ],
        "BS 22 AUG": [
            ["NEW CASHOUT"],
            ["NAME", "PROCESS", "PNBP", "URGENT", "RPTKA/IMTA", "MARGIN BS", "FINAL PRICE"],
            ["A BC", "C1", "Rp1,000,000", "", "", "Rp600,000", "Rp1,600,000"],
        ],
        "BZ 13 FEB 26": [  # unknown, not in TAB_TO_WEEK
            ["NEW CASHOUT"],
            ["NAME", "PROCESS", "PNBP", "URGENT", "RPTKA/IMTA", "TOTAL INCOME", "MARGIN BS", "MARGIN BZ", "NOTE"],
            ["X Y", "C1", "Rp1,000,000", "", "", "Rp2,700,000", "Rp600,000", "Rp1,100,000"],
        ],
    }

    with patch(
        "backend.services.hr.owner_cashout.sync_service.SheetReader",
        return_value=FakeReader(fake_tabs),
    ), patch(
        "backend.services.hr.owner_cashout.sync_service.send_alert",
    ) as mock_alert:
        result = await run_sync(db_pool, triggered_by="test")

    assert result.status == "partial"
    assert "BZ 13 FEB 26" in result.unknown_tabs
    assert result.weeks_skipped >= 1
    assert result.weeks_processed == 1
    mock_alert.assert_called_once()


@pytest.mark.asyncio
async def test_run_sync_writes_log_row(db_pool):
    from backend.services.hr.owner_cashout.sync_service import run_sync

    fake_tabs = {
        "BZ 22 AUG": [
            ["NEW CASHOUT"],
            ["NAME", "PROCESS", "PNBP", "URGENT", "RPTKA/IMTA", "TOTAL INCOME", "MARGIN BS", "MARGIN BZ", "NOTE"],
            ["A BC", "C1", "Rp1,000,000", "", "", "Rp2,700,000", "Rp600,000", "Rp1,100,000"],
        ],
    }

    with patch(
        "backend.services.hr.owner_cashout.sync_service.SheetReader",
        return_value=FakeReader(fake_tabs),
    ):
        await run_sync(db_pool, triggered_by="manual:zero@balizero.com")

    async with db_pool.acquire() as c:
        row = await c.fetchrow(
            "SELECT * FROM owner_cashout_sync_log ORDER BY started_at DESC LIMIT 1"
        )
        assert row["status"] in ("success", "partial")
        assert row["triggered_by"] == "manual:zero@balizero.com"
        assert row["finished_at"] is not None
