from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from db.migration_base import BaseMigration, MigrationError


class _DummyTransaction:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummyConn:
    def __init__(self):
        self.applied = False
        self.deps: dict[int, bool] = {}
        self.executed: list[tuple[str, tuple]] = []
        self.closed = False

    async def execute(self, sql, *args):
        self.executed.append((sql.strip(), args))

    async def fetchval(self, sql, *args):
        if "migration_name" in sql:
            return self.applied
        if "migration_number" in sql:
            return self.deps.get(args[0], False)
        return None

    def transaction(self):
        return _DummyTransaction()

    async def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def restore_migrations_dir():
    original = BaseMigration.MIGRATIONS_DIR
    yield
    BaseMigration.MIGRATIONS_DIR = original


def _make_migration(tmp_path: Path, sql_text: str, **kwargs) -> BaseMigration:
    sql_name = "001_test.sql"
    sql_path = tmp_path / sql_name
    sql_path.write_text(sql_text, encoding="utf-8")
    BaseMigration.MIGRATIONS_DIR = tmp_path
    return BaseMigration(
        migration_number=1,
        sql_file=sql_name,
        description="test migration",
        **kwargs,
    )


def test_sanitize_db_url(tmp_path):
    migration = _make_migration(tmp_path, "-- noop")
    url = "postgresql://user:secret@localhost:5432/db"
    assert migration._sanitize_db_url(url) == "postgresql://user:***@localhost:5432/db"
    assert migration._sanitize_db_url("postgresql://localhost/db") == "postgresql://localhost/db"


def test_validate_sql_truncate_rules(tmp_path):
    migration = _make_migration(tmp_path, "-- noop")
    migration._validate_sql("-- TRUNCATE TABLE users;")
    with pytest.raises(MigrationError, match="TRUNCATE"):
        migration._validate_sql("TRUNCATE TABLE users;")


def test_calculate_checksum_changes(tmp_path):
    migration = _make_migration(tmp_path, "-- noop")
    assert migration._calculate_checksum("a") == migration._calculate_checksum("a")
    assert migration._calculate_checksum("a") != migration._calculate_checksum("b")


@pytest.mark.asyncio
async def test_apply_success(monkeypatch, tmp_path):
    migration = _make_migration(tmp_path, "CREATE TABLE test(id int);")
    dummy_conn = _DummyConn()
    monkeypatch.setattr("db.migration_base.asyncpg.connect", AsyncMock(return_value=dummy_conn))
    monkeypatch.setattr("db.migration_base.settings", type("S", (), {"database_url": "db"})())
    migration.verify = AsyncMock(return_value=True)

    result = await migration.apply()

    assert result is True
    assert dummy_conn.closed is True
    assert any(
        "CREATE TABLE IF NOT EXISTS schema_migrations" in sql for sql, _ in dummy_conn.executed
    )
    assert any("INSERT INTO schema_migrations" in sql for sql, _ in dummy_conn.executed)


@pytest.mark.asyncio
async def test_apply_skips_when_already_applied(monkeypatch, tmp_path):
    migration = _make_migration(tmp_path, "CREATE TABLE test(id int);")
    dummy_conn = _DummyConn()
    dummy_conn.applied = True
    monkeypatch.setattr("db.migration_base.asyncpg.connect", AsyncMock(return_value=dummy_conn))
    monkeypatch.setattr("db.migration_base.settings", type("S", (), {"database_url": "db"})())
    migration.verify = AsyncMock(return_value=True)

    result = await migration.apply()

    assert result is True
    assert not any("CREATE TABLE test" in sql for sql, _ in dummy_conn.executed)


@pytest.mark.asyncio
async def test_apply_verify_failure(monkeypatch, tmp_path):
    migration = _make_migration(tmp_path, "CREATE TABLE test(id int);")
    dummy_conn = _DummyConn()
    monkeypatch.setattr("db.migration_base.asyncpg.connect", AsyncMock(return_value=dummy_conn))
    monkeypatch.setattr("db.migration_base.settings", type("S", (), {"database_url": "db"})())
    migration.verify = AsyncMock(return_value=False)

    with pytest.raises(MigrationError, match="Verification failed"):
        await migration.apply()

    assert dummy_conn.closed is True


@pytest.mark.asyncio
async def test_apply_requires_database_url(monkeypatch, tmp_path):
    migration = _make_migration(tmp_path, "CREATE TABLE test(id int);")
    monkeypatch.setattr("db.migration_base.settings", type("S", (), {"database_url": None})())

    with pytest.raises(MigrationError, match="DATABASE_URL not configured"):
        await migration.apply()


@pytest.mark.asyncio
async def test_check_dependencies_missing(tmp_path):
    migration = _make_migration(tmp_path, "CREATE TABLE test(id int);", dependencies=[2])
    dummy_conn = _DummyConn()

    with pytest.raises(MigrationError, match="depends on migration"):
        await migration._check_dependencies(dummy_conn)


@pytest.mark.asyncio
async def test_check_dependencies_present(tmp_path):
    migration = _make_migration(tmp_path, "CREATE TABLE test(id int);", dependencies=[2])
    dummy_conn = _DummyConn()
    dummy_conn.deps[2] = True

    await migration._check_dependencies(dummy_conn)


@pytest.mark.asyncio
async def test_rollback_calls_manager(tmp_path):
    migration = _make_migration(tmp_path, "CREATE TABLE test(id int);")
    manager = type("M", (), {"rollback_migration": AsyncMock(return_value=True)})()

    result = await migration.rollback(manager)

    assert result is True
    manager.rollback_migration.assert_called_once_with(migration.migration_name)


def test_repr(tmp_path):
    migration = _make_migration(tmp_path, "CREATE TABLE test(id int);")
    assert repr(migration) == "<Migration 1: test migration>"
