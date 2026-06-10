"""Tests for migration 124: Autonomous Lab runtime tables."""

from __future__ import annotations

import re
from unittest.mock import AsyncMock

import pytest


def _collect_sql(calls) -> str:
    return "\n".join(call.args[0] for call in calls if call.args)


@pytest.mark.asyncio
async def test_migration_124_creates_lab_runs_and_outbox_tables() -> None:
    from backend.migrations.migration_124_autonomous_lab_runtime import apply

    conn = AsyncMock()
    await apply(conn)
    sql = _collect_sql(conn.execute.call_args_list)

    assert "CREATE TABLE IF NOT EXISTS autonomous_lab_runs" in sql
    assert "CREATE TABLE IF NOT EXISTS autonomous_lab_events_outbox" in sql
    assert "idempotency_key TEXT NOT NULL UNIQUE" in sql
    assert "receipt JSONB NOT NULL" in sql
    assert "payload JSONB NOT NULL" in sql
    assert "REFERENCES autonomous_lab_runs(run_id)" in sql
    assert "'air_m5_cockpit'" in sql
    assert "'pro_runtime'" in sql
    assert "'mini_scheduler'" in sql


@pytest.mark.asyncio
async def test_migration_124_status_and_event_constraints() -> None:
    from backend.migrations.migration_124_autonomous_lab_runtime import apply

    conn = AsyncMock()
    await apply(conn)
    sql = _collect_sql(conn.execute.call_args_list)

    assert "'pending'" in sql
    assert "'running'" in sql
    assert "'succeeded'" in sql
    assert "'failed_dlq'" in sql
    assert "'run_enqueued'" in sql
    assert "'candidate_ready'" in sql


@pytest.mark.asyncio
async def test_migration_124_idempotent_and_indexed_for_claiming() -> None:
    from backend.migrations.migration_124_autonomous_lab_runtime import apply

    conn = AsyncMock()
    await apply(conn)
    sql = _collect_sql(conn.execute.call_args_list)

    assert "idx_autonomous_lab_runs_claimable" in sql
    assert "idx_autonomous_lab_outbox_claimable" in sql
    all_create_idx = re.findall(r"CREATE INDEX", sql)
    all_if_not_exists = re.findall(r"CREATE INDEX IF NOT EXISTS", sql)
    assert len(all_create_idx) > 0
    assert len(all_create_idx) == len(all_if_not_exists)


@pytest.mark.asyncio
async def test_migration_124_rollback_drops_child_outbox_before_runs() -> None:
    from backend.migrations.migration_124_autonomous_lab_runtime import rollback

    conn = AsyncMock()
    await rollback(conn)
    sql = _collect_sql(conn.execute.call_args_list)

    outbox_pos = sql.find("DROP TABLE IF EXISTS autonomous_lab_events_outbox")
    runs_pos = sql.find("DROP TABLE IF EXISTS autonomous_lab_runs")
    assert outbox_pos != -1
    assert runs_pos != -1
    assert outbox_pos < runs_pos
    assert "DROP INDEX IF EXISTS idx_autonomous_lab_outbox_claimable" in sql
    assert "DROP INDEX IF EXISTS idx_autonomous_lab_runs_claimable" in sql
