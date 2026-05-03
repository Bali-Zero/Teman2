"""
Smoke test for migration 114 (pii_violations): verify apply() + rollback()
issue the expected DDL. No real Postgres required — we mock the asyncpg
connection and assert on the captured SQL.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.migrations.migration_114a_pii_violations import apply, rollback


class TestMigration114:
    @pytest.mark.asyncio
    async def test_apply_creates_table_and_three_indexes(self):
        conn = AsyncMock()
        await apply(conn)

        # apply() must issue exactly 4 execute() calls: 1 CREATE TABLE + 3 CREATE INDEX
        assert conn.execute.await_count == 4
        statements = [c.args[0] for c in conn.execute.await_args_list]

        # Table exists with the expected columns
        create_table = statements[0]
        assert "CREATE TABLE" in create_table
        assert "pii_violations" in create_table
        for col in (
            "request_id", "route", "pattern_matched", "severity",
            "user_hash", "occurrence_count", "created_at",
        ):
            assert col in create_table

        # The three composite indexes we designed for the admin queries
        joined = "\n".join(statements[1:])
        assert "idx_pii_violations_recent" in joined
        assert "idx_pii_violations_pattern_trend" in joined
        assert "idx_pii_violations_request" in joined
        # Recent-query index must order on created_at DESC
        assert "(created_at DESC, route)" in joined

    @pytest.mark.asyncio
    async def test_rollback_drops_table(self):
        conn = AsyncMock()
        await rollback(conn)
        conn.execute.assert_awaited_once()
        sql = conn.execute.await_args.args[0]
        assert "DROP TABLE" in sql
        assert "pii_violations" in sql

    @pytest.mark.asyncio
    async def test_rollback_is_idempotent_via_if_exists(self):
        conn = AsyncMock()
        await rollback(conn)
        sql = conn.execute.await_args.args[0]
        # IF EXISTS prevents "does not exist" errors on partial-state rollback
        assert "IF EXISTS" in sql
