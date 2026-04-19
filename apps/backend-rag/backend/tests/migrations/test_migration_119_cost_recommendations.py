"""Tests for Migration 119: llm_cost_recommendations table.

Verifies SQL structure without a live PG connection (AsyncMock pattern,
matches test_migration_107_bridge_outbox.py convention).
"""
from __future__ import annotations

import re
from unittest.mock import AsyncMock

import pytest

from backend.migrations.migration_119_cost_recommendations import apply, rollback


def _collect_sql(calls) -> str:
    return "\n".join(call.args[0] for call in calls if call.args)


def _normalize(sql: str) -> str:
    return re.sub(r"\s+", " ", sql)


@pytest.mark.asyncio
async def test_apply_creates_cost_recommendations_table():
    conn = AsyncMock()
    await apply(conn)
    sql = _normalize(_collect_sql(conn.execute.call_args_list))

    assert "CREATE TABLE IF NOT EXISTS llm_cost_recommendations" in sql
    assert "id BIGSERIAL PRIMARY KEY" in sql
    assert "ts_utc TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()" in sql
    assert "endpoint VARCHAR(128) NOT NULL" in sql
    assert "current_model VARCHAR(128) NOT NULL" in sql
    assert "proposed_model VARCHAR(128) NOT NULL" in sql
    assert "estimated_monthly_saving_usd NUMERIC(12, 6) NOT NULL" in sql
    assert "quality_tradeoff TEXT NOT NULL" in sql
    assert "confidence VARCHAR(16) NOT NULL" in sql
    assert "spike_flag BOOLEAN NOT NULL DEFAULT FALSE" in sql
    assert "status VARCHAR(16) NOT NULL DEFAULT 'pending'" in sql


@pytest.mark.asyncio
async def test_apply_enforces_confidence_and_status_check_constraints():
    conn = AsyncMock()
    await apply(conn)
    sql = _normalize(_collect_sql(conn.execute.call_args_list))

    assert "CHECK (confidence IN ('low','medium','high'))" in sql
    assert "CHECK (status IN ('pending','reviewed','applied','rejected'))" in sql


@pytest.mark.asyncio
async def test_apply_creates_two_indexes():
    conn = AsyncMock()
    await apply(conn)
    sql = _normalize(_collect_sql(conn.execute.call_args_list))

    assert "CREATE INDEX IF NOT EXISTS idx_llm_cost_reco_status_ts" in sql
    assert "CREATE INDEX IF NOT EXISTS idx_llm_cost_reco_endpoint" in sql


@pytest.mark.asyncio
async def test_apply_idempotent():
    conn = AsyncMock()
    await apply(conn)
    await apply(conn)
    # 1 table + 2 indexes = 3 statements per call
    assert conn.execute.call_count == 6


@pytest.mark.asyncio
async def test_rollback_drops_table_if_exists():
    conn = AsyncMock()
    await rollback(conn)
    sql = _normalize(_collect_sql(conn.execute.call_args_list))

    assert "DROP TABLE IF EXISTS llm_cost_recommendations" in sql
