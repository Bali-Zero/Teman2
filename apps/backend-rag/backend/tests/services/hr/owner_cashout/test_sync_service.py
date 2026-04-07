"""Tests for owner cashout sync service (upsert_week + run_sync)."""
from datetime import date

import asyncpg
import pytest

from backend.services.hr.owner_cashout.parser import CashoutRow
from backend.services.hr.owner_cashout.sync_service import upsert_week


@pytest.fixture
async def db_pool(monkeypatch):
    import os
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/nuzantara_dev"
    )
    pool = await asyncpg.create_pool(url)
    # Clean slate for this test run
    async with pool.acquire() as c:
        await c.execute("DELETE FROM owner_weekly_cashout_rows")
        await c.execute("DELETE FROM owner_weekly_cashout_weeks")
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
