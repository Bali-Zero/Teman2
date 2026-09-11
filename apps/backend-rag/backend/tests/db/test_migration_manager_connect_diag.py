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


def _manager(database_url: str, *, dedicated: bool | None = None) -> MigrationManager:
    """Build a MigrationManager on an EXPLICIT url, not via `resolve_migration_dsn()`.

    Built through the real constructor on purpose: since 2026-09-11 the manager
    freezes URL and mode together, and the diagnostic names the source it
    actually dialled. A hand-assembled instance would not carry that mode and
    would test a shape that cannot occur.
    """
    return MigrationManager(database_url=database_url, dedicated=dedicated)


@pytest.mark.asyncio
async def test_connect_error_names_migration_database_url_and_hints_sslmode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MIGRATION_DATABASE_URL set, no sslmode, create_pool raises ConnectionResetError."""
    dsn = "postgresql://migrator:s3cr3t@10.0.0.5:5432/nuzantara"
    # The runner is ON the migrator DSN -- the production shape, where
    # `resolve_migration_dsn()` selects exactly this url.
    monkeypatch.setattr(migration_base.settings, "migration_database_url", dsn)

    async def _raise(*_a, **_kw):
        raise ConnectionResetError()

    monkeypatch.setattr("backend.db.migration_manager.asyncpg.create_pool", _raise)

    mgr = _manager(dsn)

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
async def test_connect_error_names_database_url_for_an_explicit_legacy_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The runner invariant, seen through the diagnostic (2026-09-11).

    `MIGRATION_DATABASE_URL` is configured, but THIS manager was handed the
    runtime DSN explicitly. It dialled DATABASE_URL, so the message must say
    DATABASE_URL -- naming the migrator here would send the next operator to
    debug a secret that was never in play.
    """
    monkeypatch.setattr(migration_base.settings, "migration_database_url", "postgresql://mig@h/db")

    async def _raise(*_a, **_kw):
        raise ConnectionResetError()

    monkeypatch.setattr("backend.db.migration_manager.asyncpg.create_pool", _raise)

    mgr = _manager("postgresql://runtime:pass@10.0.0.5:5432/nuzantara")
    assert mgr._dedicated is False

    with pytest.raises(migration_base.MigrationError) as exc_info:
        await mgr.connect()

    text = str(exc_info.value)
    assert "MIGRATION_DATABASE_URL" not in text
    assert "DATABASE_URL" in text
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
