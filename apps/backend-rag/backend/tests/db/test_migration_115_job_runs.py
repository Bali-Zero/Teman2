"""Tests for migration 115: job_runs table."""
from __future__ import annotations

import os

import asyncpg
import pytest

from backend.migrations.migration_115_job_runs import apply, rollback

TEST_DB_URL = (
    os.environ.get("TEST_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
)

if not TEST_DB_URL:
    pytest.skip(
        "TEST_DATABASE_URL or DATABASE_URL must be set for migration tests",
        allow_module_level=True,
    )


@pytest.fixture
async def conn():
    c = await asyncpg.connect(TEST_DB_URL)
    try:
        await c.execute("DROP TABLE IF EXISTS job_runs CASCADE")
        yield c
    finally:
        await c.execute("DROP TABLE IF EXISTS job_runs CASCADE")
        await c.close()


async def test_apply_creates_table(conn):
    await apply(conn)
    exists = await conn.fetchval(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='job_runs')"
    )
    assert exists is True


async def test_apply_creates_expected_columns(conn):
    await apply(conn)
    rows = await conn.fetch(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='job_runs' ORDER BY ordinal_position"
    )
    names = [r["column_name"] for r in rows]
    for required in (
        "id", "job_name", "scheduled_tick", "idempotency_key",
        "status", "attempt", "started_at", "finished_at",
        "error", "cost_cents", "meta", "created_at",
    ):
        assert required in names, f"missing column {required}"


async def test_status_check_constraint(conn):
    await apply(conn)
    with pytest.raises(asyncpg.CheckViolationError):
        await conn.execute(
            "INSERT INTO job_runs (job_name, scheduled_tick, idempotency_key, status) "
            "VALUES ('x', now(), 'k', 'bogus')"
        )


async def test_indexes_present(conn):
    await apply(conn)
    rows = await conn.fetch(
        "SELECT indexname FROM pg_indexes WHERE tablename='job_runs'"
    )
    names = {r["indexname"] for r in rows}
    assert "idx_job_runs_name_tick" in names
    assert "idx_job_runs_idempotency" in names
    assert "idx_job_runs_status_name" in names


async def test_rollback_drops_table(conn):
    await apply(conn)
    await rollback(conn)
    exists = await conn.fetchval(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='job_runs')"
    )
    assert exists is False
