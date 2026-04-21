"""Tests for migration 120: partner_email_outbox — transactional outbox for partner emails.

Verifies SQL structure, required columns, indexes, idempotency, and rollback
without requiring a live database connection (AsyncMock pattern).

Spec: docs/superpowers/reviews/2026-04-21-partners-v1/99-synthesis.md CRIT-2
"""
from __future__ import annotations

import re
from unittest.mock import AsyncMock

import pytest


def _collect_sql(calls) -> str:
    """Concatenate all SQL strings passed to conn.execute."""
    return "\n".join(call.args[0] for call in calls if call.args)


def _normalize(sql: str) -> str:
    return re.sub(r"\s+", " ", sql)


@pytest.mark.asyncio
async def test_migration_120_creates_outbox_table():
    """apply() must create partner_email_outbox with all required columns."""
    from backend.migrations.migration_120_partner_email_outbox import apply
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_sql(conn.execute.call_args_list)
    assert "CREATE TABLE partner_email_outbox" in sql
    assert "email_type" in sql
    assert "status TEXT NOT NULL DEFAULT 'pending'" in sql
    assert "idempotency_key TEXT UNIQUE" in sql


@pytest.mark.asyncio
async def test_migration_120_check_constraints():
    """apply() must include CHECK constraints for email_type and status."""
    from backend.migrations.migration_120_partner_email_outbox import apply
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_sql(conn.execute.call_args_list)
    assert "'welcome', 'commission_earned'" in sql or ("'welcome'" in sql and "'commission_earned'" in sql)
    assert "'pending', 'sent', 'failed_dlq'" in sql or ("'pending'" in sql and "'failed_dlq'" in sql)


@pytest.mark.asyncio
async def test_migration_120_idempotent():
    """apply() uses IF NOT EXISTS / DO $$ guards — all indexes use IF NOT EXISTS."""
    from backend.migrations.migration_120_partner_email_outbox import apply
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_sql(conn.execute.call_args_list)

    # Table creation is inside DO $$ IF NOT EXISTS block
    assert "IF NOT EXISTS" in sql

    # All CREATE INDEX must use IF NOT EXISTS
    all_create_idx = re.findall(r"CREATE INDEX", sql)
    all_if_not_exists = re.findall(r"CREATE INDEX IF NOT EXISTS", sql)
    assert len(all_create_idx) > 0
    assert len(all_create_idx) == len(all_if_not_exists), (
        f"Every CREATE INDEX must use IF NOT EXISTS "
        f"({len(all_create_idx)} total vs {len(all_if_not_exists)} with IF NOT EXISTS)"
    )


@pytest.mark.asyncio
async def test_migration_120_creates_indexes():
    """apply() must create both named indexes."""
    from backend.migrations.migration_120_partner_email_outbox import apply
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_sql(conn.execute.call_args_list)
    assert "idx_partner_email_outbox_pending" in sql
    assert "idx_partner_email_outbox_partner_id" in sql


@pytest.mark.asyncio
async def test_migration_120_rollback():
    """rollback() must drop the table and both indexes."""
    from backend.migrations.migration_120_partner_email_outbox import rollback
    conn = AsyncMock()
    await rollback(conn)
    sql = _collect_sql(conn.execute.call_args_list)
    assert "DROP TABLE IF EXISTS partner_email_outbox" in sql
    assert "DROP INDEX IF EXISTS idx_partner_email_outbox_pending" in sql
    assert "DROP INDEX IF EXISTS idx_partner_email_outbox_partner_id" in sql


@pytest.mark.asyncio
async def test_migration_120_rollback_index_before_table():
    """rollback() must drop indexes before the table (FK-safe order)."""
    from backend.migrations.migration_120_partner_email_outbox import rollback
    conn = AsyncMock()
    await rollback(conn)
    sql = _collect_sql(conn.execute.call_args_list)

    pos_idx_partner = sql.find("idx_partner_email_outbox_partner_id")
    pos_idx_pending = sql.find("idx_partner_email_outbox_pending")
    pos_table = sql.find("DROP TABLE IF EXISTS partner_email_outbox")

    assert pos_table != -1, "rollback must drop partner_email_outbox"
    assert pos_idx_pending < pos_table, "pending index must be dropped before table"
    assert pos_idx_partner < pos_table, "partner_id index must be dropped before table"
