"""Regression tests for migration ledger tracking writes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from backend.db import migration_base
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


class FakeApplyConnection(FakeConnection):
    """Connection fake for the already-applied apply() branch."""

    def __init__(self) -> None:
        super().__init__()
        self.closed = False

    def transaction(self) -> FakeApplyConnection:
        return self

    async def __aenter__(self) -> FakeApplyConnection:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def fetchval(self, sql: str, *args: Any) -> bool:
        if "schema_migrations" in sql and "SELECT EXISTS" in sql:
            return True
        raise AssertionError(f"unexpected fetchval SQL: {sql!r}")

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_apply_reconciles_legacy_ledger_when_canonical_already_applied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _migration(tmp_path)
    conn = FakeApplyConnection()

    async def _fake_connect(database_url: str) -> FakeApplyConnection:
        assert database_url == "postgres://fake"
        return conn

    monkeypatch.setattr(migration_base.settings, "database_url", "postgres://fake")
    monkeypatch.setattr(migration_base.asyncpg, "connect", _fake_connect)

    result = await migration.apply()

    statements = [sql for sql, _args in conn.calls]
    assert result is True
    assert conn.closed is True
    assert any("INSERT INTO schema_migrations" in sql for sql in statements)
    assert any("INSERT INTO _schema_versions" in sql for sql in statements)
    assert not any(sql.strip() == "SELECT 1;" for sql in statements)
