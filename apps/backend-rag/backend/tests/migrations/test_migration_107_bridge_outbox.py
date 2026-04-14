"""
Tests for Migration 107: bridge_outbox table.

Verifies SQL structure without requiring a live PG connection (AsyncMock pattern,
matches test_migration_079_naga.py convention).

Note: The plan originally referenced migration_101, but 101-106 already exist
in main. We use 107 to avoid collision.
"""
from __future__ import annotations

import re
from unittest.mock import AsyncMock

import pytest

from backend.migrations.migration_107_bridge_outbox import apply, rollback


def _collect_sql(calls) -> str:
    """Concatenate all SQL strings passed to conn.execute."""
    return "\n".join(call.args[0] for call in calls if call.args)


def _normalize(sql: str) -> str:
    return re.sub(r"\s+", " ", sql)


@pytest.mark.asyncio
async def test_apply_creates_bridge_outbox_table():
    """apply() emits CREATE TABLE IF NOT EXISTS bridge_outbox with required columns."""
    conn = AsyncMock()
    await apply(conn)
    sql = _normalize(_collect_sql(conn.execute.call_args_list))

    assert "CREATE TABLE IF NOT EXISTS bridge_outbox" in sql
    # Required columns (case-insensitive substrings)
    assert "id BIGSERIAL PRIMARY KEY" in sql
    assert "type VARCHAR(64) NOT NULL" in sql
    assert "payload JSONB NOT NULL" in sql
    assert "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()" in sql


@pytest.mark.asyncio
async def test_apply_creates_three_indexes():
    """apply() emits CREATE INDEX IF NOT EXISTS for id, type, created_at."""
    conn = AsyncMock()
    await apply(conn)
    sql = _normalize(_collect_sql(conn.execute.call_args_list))

    assert "CREATE INDEX IF NOT EXISTS idx_outbox_id ON bridge_outbox" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_outbox_type ON bridge_outbox" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_outbox_created_at ON bridge_outbox" in sql


@pytest.mark.asyncio
async def test_apply_idempotent():
    """apply() can be called twice without raising (uses IF NOT EXISTS)."""
    conn = AsyncMock()
    await apply(conn)
    await apply(conn)  # Must not raise
    # Each call emits 4 statements (1 table + 3 indexes) = 8 total
    assert conn.execute.call_count == 8


@pytest.mark.asyncio
async def test_rollback_drops_table_and_indexes():
    """rollback() emits DROP statements for table and all 3 indexes."""
    conn = AsyncMock()
    await rollback(conn)
    sql = _normalize(_collect_sql(conn.execute.call_args_list))

    assert "DROP INDEX IF EXISTS idx_outbox_id" in sql
    assert "DROP INDEX IF EXISTS idx_outbox_type" in sql
    assert "DROP INDEX IF EXISTS idx_outbox_created_at" in sql
    assert "DROP TABLE IF EXISTS bridge_outbox" in sql


@pytest.mark.asyncio
async def test_rollback_uses_if_exists_throughout():
    """rollback() is safe to run even if table doesn't exist."""
    conn = AsyncMock()
    await rollback(conn)
    sql = _collect_sql(conn.execute.call_args_list)
    # Every DROP must be IF EXISTS
    drop_statements = re.findall(r"DROP\s+(?:TABLE|INDEX)[^;]*", sql, re.IGNORECASE)
    assert len(drop_statements) >= 4
    for stmt in drop_statements:
        assert "IF EXISTS" in stmt.upper(), f"Missing IF EXISTS in: {stmt}"
