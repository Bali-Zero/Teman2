"""Regression tests for migration ledger tracking writes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from backend.db.migration_base import BaseMigration


class FakeConnection:
    """Tiny asyncpg-like recorder for migration tracking SQL."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, sql: str, *args: Any) -> None:
        self.calls.append((sql, args))


def _migration(tmp_path: Path) -> BaseMigration:
    sql_file = tmp_path / "200_tracking_probe.sql"
    sql_file.write_text("SELECT 1;\n", encoding="utf-8")
    return BaseMigration(
        migration_number=200,
        sql_file=sql_file.name,
        description="tracking probe",
        rollback_sql="SELECT 0;",
        _sql_dir=tmp_path,
    )


@pytest.mark.asyncio
async def test_ensure_migration_log_creates_both_tracking_tables(tmp_path: Path) -> None:
    migration = _migration(tmp_path)
    conn = FakeConnection()

    await migration._ensure_migration_log(conn)  # noqa: SLF001

    statements = "\n".join(sql for sql, _args in conn.calls)
    assert "CREATE TABLE IF NOT EXISTS schema_migrations" in statements
    assert "CREATE TABLE IF NOT EXISTS _schema_versions" in statements
    assert "idx_schema_versions_number" in statements


@pytest.mark.asyncio
async def test_log_migration_writes_schema_versions_ledger(tmp_path: Path) -> None:
    migration = _migration(tmp_path)
    conn = FakeConnection()

    await migration._log_migration(conn, "SELECT 1;", 17, "SELECT 0;")  # noqa: SLF001

    statements = [sql for sql, _args in conn.calls]
    assert any("INSERT INTO schema_migrations" in sql for sql in statements)
    schema_versions_call = next(
        (call for call in conn.calls if "INSERT INTO _schema_versions" in call[0]),
        None,
    )
    assert schema_versions_call is not None
    assert schema_versions_call[1][0] == "200_tracking_probe"
    assert schema_versions_call[1][1] == 200
    assert schema_versions_call[1][3] == "tracking probe"
    assert schema_versions_call[1][4] == 17
    assert schema_versions_call[1][5] == "SELECT 0;"
    assert schema_versions_call[1][6] == "migration-base"
