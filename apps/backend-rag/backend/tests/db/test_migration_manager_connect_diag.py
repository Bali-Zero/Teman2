"""Unit tests for `MigrationManager.connect()` failure diagnostics.

Live incident, 2026-09-10 19:13Z-20:04Z: four consecutive 'Deploy Backend to
Fly.io' failures. The Fly release_command died inside
`asyncpg.create_pool()` with a bare `ConnectionResetError` raised from
asyncpg's TLS handshake, and the traceback never said which DSN source was
in play (`MIGRATION_DATABASE_URL`, created that day without
`?sslmode=disable`, vs. `DATABASE_URL`, which carries it). These tests pin
that `connect()` now names the source, the sanitized DSN, the exception,
and a sslmode hint when applicable -- and that the password never leaks.

No real Postgres needed: `asyncpg.create_pool` is monkeypatched to raise.
"""

from __future__ import annotations

import pytest

from backend.db import migration_base
from backend.db.migration_manager import MigrationManager


def _manager(database_url: str) -> MigrationManager:
    """Build a MigrationManager without going through `resolve_migration_dsn()`."""
    mgr = MigrationManager.__new__(MigrationManager)
    mgr.database_url = database_url
    mgr.pool = None
    return mgr


@pytest.mark.asyncio
async def test_connect_error_names_migration_database_url_and_hints_sslmode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MIGRATION_DATABASE_URL set, no sslmode, create_pool raises ConnectionResetError."""
    monkeypatch.setattr(migration_base.settings, "migration_database_url", "postgresql://mig@h/db")

    async def _raise(*_a, **_kw):
        raise ConnectionResetError()

    monkeypatch.setattr("backend.db.migration_manager.asyncpg.create_pool", _raise)

    mgr = _manager("postgresql://migrator:s3cr3t@10.0.0.5:5432/nuzantara")

    with pytest.raises(migration_base.MigrationError) as exc_info:
        await mgr.connect()

    text = str(exc_info.value)
    assert "MIGRATION_DATABASE_URL" in text
    assert "ConnectionResetError" in text
    assert "hint" in text
    assert "sslmode=disable" in text
    assert "s3cr3t" not in text


@pytest.mark.asyncio
async def test_connect_error_names_database_url_when_not_dedicated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only DATABASE_URL configured: message names it, not the MIGRATION word."""
    monkeypatch.setattr(migration_base.settings, "migration_database_url", None)

    async def _raise(*_a, **_kw):
        raise ConnectionResetError()

    monkeypatch.setattr("backend.db.migration_manager.asyncpg.create_pool", _raise)

    mgr = _manager("postgresql://runtime:pass@10.0.0.5:5432/nuzantara")

    with pytest.raises(migration_base.MigrationError) as exc_info:
        await mgr.connect()

    text = str(exc_info.value)
    assert "DATABASE_URL" in text
    assert "MIGRATION_DATABASE_URL" not in text
    assert "pass" not in text


@pytest.mark.asyncio
async def test_connect_error_no_hint_when_sslmode_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DSN already carries ?sslmode=... -- no hint line, would be redundant."""
    monkeypatch.setattr(migration_base.settings, "migration_database_url", None)

    async def _raise(*_a, **_kw):
        raise ConnectionResetError()

    monkeypatch.setattr("backend.db.migration_manager.asyncpg.create_pool", _raise)

    mgr = _manager("postgresql://runtime:pass@10.0.0.5:5432/nuzantara?sslmode=disable")

    with pytest.raises(migration_base.MigrationError) as exc_info:
        await mgr.connect()

    text = str(exc_info.value)
    assert "DATABASE_URL" in text
    assert "hint" not in text
