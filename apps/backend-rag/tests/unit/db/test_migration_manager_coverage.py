from __future__ import annotations
from tests.conftest import create_mock_settings

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from backend.db.migration_manager import MigrationError, MigrationManager


class _DummyConn:
    def __init__(self, rollback_sql=None):
        self.rollback_sql = rollback_sql
        self.executed = []

    async def execute(self, query, *args):
        self.executed.append((query.strip(), args))

    async def fetch(self, _query):
        return [
            {
                "migration_name": "001_init",
                "migration_number": 1,
                "executed_at": "now",
                "description": "init",
            }
        ]

    async def fetchval(self, _query, _number):
        return True

    async def fetchrow(self, _query, _name):
        if self.rollback_sql is None:
            return None
        return {"rollback_sql": self.rollback_sql}

    def transaction(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _AcquireCtx:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummyPool:
    def __init__(self, conn):
        self.conn = conn
        self.closed = False

    def acquire(self):
        return _AcquireCtx(self.conn)

    async def close(self):
        self.closed = True


def test_init_requires_database_url(monkeypatch):
    monkeypatch.setattr("backend.db.migration_manager.settings", create_mock_settings(database_url=None))
    with pytest.raises(MigrationError):
        MigrationManager()


@pytest.mark.asyncio
async def test_connect_and_close(monkeypatch):
    monkeypatch.setattr("backend.db.migration_manager.settings", create_mock_settings(database_url="postgres://test"))
    pool = _DummyPool(_DummyConn())
    monkeypatch.setattr("backend.db.migration_manager.asyncpg.create_pool", AsyncMock(return_value=pool))

    manager = MigrationManager()
    await manager.connect()
    assert manager.pool is pool
    await manager.close()
    assert pool.closed is True
    assert manager.pool is None


def test_sanitize_db_url(monkeypatch):
    monkeypatch.setattr("backend.db.migration_manager.settings", create_mock_settings(database_url="postgres://test"))
    manager = MigrationManager()
    assert (
        manager._sanitize_db_url("postgresql://user:secret@localhost:5432/db")
        == "postgresql://user:***@localhost:5432/db"
    )


@pytest.mark.asyncio
async def test_get_applied_migrations(monkeypatch):
    monkeypatch.setattr("backend.db.migration_manager.settings", create_mock_settings(database_url="postgres://test"))
    manager = MigrationManager()
    manager.pool = _DummyPool(_DummyConn())
    result = await manager.get_applied_migrations()
    assert result[0]["migration_number"] == 1


@pytest.mark.asyncio
async def test_is_applied(monkeypatch):
    monkeypatch.setattr("backend.db.migration_manager.settings", create_mock_settings(database_url="postgres://test"))
    manager = MigrationManager()
    manager.pool = _DummyPool(_DummyConn())
    assert await manager.is_applied(1) is True


@pytest.mark.asyncio
async def test_rollback_migration_no_sql(monkeypatch):
    monkeypatch.setattr("backend.db.migration_manager.settings", create_mock_settings(database_url="postgres://test"))
    manager = MigrationManager()
    manager.pool = _DummyPool(_DummyConn(rollback_sql=None))
    assert await manager.rollback_migration("001_init") is False


@pytest.mark.asyncio
async def test_rollback_migration_success(monkeypatch):
    monkeypatch.setattr("backend.db.migration_manager.settings", create_mock_settings(database_url="postgres://test"))
    manager = MigrationManager()
    conn = _DummyConn(rollback_sql="DELETE FROM test")
    manager.pool = _DummyPool(conn)
    assert await manager.rollback_migration("001_init") is True
    assert any("DELETE FROM test" in query for query, _ in conn.executed)


@pytest.mark.asyncio
async def test_discover_migrations(monkeypatch):
    monkeypatch.setattr("backend.db.migration_manager.settings", create_mock_settings(database_url="postgres://test"))
    manager = MigrationManager()
    migrations = await manager.discover_migrations()
    assert migrations


@pytest.mark.asyncio
async def test_apply_all_pending(monkeypatch):
    monkeypatch.setattr("backend.db.migration_manager.settings", create_mock_settings(database_url="postgres://test"))
    manager = MigrationManager()

    async def discover():
        return [
            {"number": 1, "file": "001_init.sql", "path": Path("001_init.sql")},
            {"number": 2, "file": "002_next.sql", "path": Path("002_next.sql")},
        ]

    async def applied():
        return [{"migration_number": 1}]

    monkeypatch.setattr(manager, "discover_migrations", discover)
    monkeypatch.setattr(manager, "get_applied_migrations", applied)

    class _DummyMigration:
        def __init__(self, migration_number, sql_file, description):
            self.migration_number = migration_number

        async def apply(self):
            return True

    monkeypatch.setattr("backend.db.migration_manager.BaseMigration", _DummyMigration)

    result = await manager.apply_all_pending()
    assert result["applied"] == [2]


@pytest.mark.asyncio
async def test_apply_all_pending_dry_run(monkeypatch):
    monkeypatch.setattr("backend.db.migration_manager.settings", create_mock_settings(database_url="postgres://test"))
    manager = MigrationManager()

    async def discover():
        return [{"number": 1, "file": "001_init.sql", "path": Path("001_init.sql")}]

    async def applied():
        return []

    monkeypatch.setattr(manager, "discover_migrations", discover)
    monkeypatch.setattr(manager, "get_applied_migrations", applied)

    result = await manager.apply_all_pending(dry_run=True)
    assert result["applied"] == []
