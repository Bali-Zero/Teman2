"""Tests for migration 127 (PT PMA base_price 20M -> 25M)."""

from __future__ import annotations

import pytest

from backend.migrations import migration_127_practice_types_pt_pma_25m as m


class FakeConn:
    """In-memory practice_types: {code: base_price}; mimics the guarded UPDATE."""

    def __init__(self, rows: dict[str, int]) -> None:
        self.rows = rows

    async def execute(self, sql: str, new: int, code: str, old: int) -> str:
        assert "WHERE code = $2 AND base_price = $3" in sql
        if self.rows.get(code) == old:
            self.rows[code] = new
            return "UPDATE 1"
        return "UPDATE 0"


@pytest.mark.asyncio
async def test_moves_20m_to_25m() -> None:
    conn = FakeConn({"company_pt_pma": 20_000_000, "other": 20_000_000})
    await m.apply(conn)
    assert conn.rows == {"company_pt_pma": 25_000_000, "other": 20_000_000}


@pytest.mark.asyncio
async def test_leaves_other_value_untouched() -> None:
    conn = FakeConn({"company_pt_pma": 22_000_000})
    await m.apply(conn)
    assert conn.rows == {"company_pt_pma": 22_000_000}


@pytest.mark.asyncio
async def test_noop_when_already_moved_or_absent() -> None:
    moved = FakeConn({"company_pt_pma": 25_000_000})
    await m.apply(moved)
    assert moved.rows == {"company_pt_pma": 25_000_000}
    absent = FakeConn({})
    await m.apply(absent)
    assert absent.rows == {}


@pytest.mark.asyncio
async def test_rollback_restores_only_the_moved_value() -> None:
    conn = FakeConn({"company_pt_pma": 25_000_000})
    await m.rollback(conn)
    assert conn.rows == {"company_pt_pma": 20_000_000}
    other = FakeConn({"company_pt_pma": 22_000_000})
    await m.rollback(other)
    assert other.rows == {"company_pt_pma": 22_000_000}
