"""MigrationManager.connect() retries transport-level failures with backoff.

Born 2026-09-10: four consecutive Fly release_commands died in
``asyncpg.create_pool`` with ``ConnectionResetError`` inside the TLS
handshake while Postgres itself was healthy. The bare call had no retry, so
each reset was a hard deploy failure (superscar #8).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import asyncpg
import pytest

from backend.db.migration_manager import MigrationManager


def _manager() -> MigrationManager:
    return MigrationManager(database_url="postgresql://u:p@db.example.internal:5432/x")


@pytest.mark.asyncio
async def test_connect_retries_connection_reset_then_succeeds() -> None:
    manager = _manager()
    pool = object()
    create_pool = AsyncMock(side_effect=[ConnectionResetError("reset by peer"), pool])
    sleep = AsyncMock()

    with (
        patch("backend.db.migration_manager.asyncpg.create_pool", create_pool),
        patch("backend.db.migration_manager.asyncio.sleep", sleep),
    ):
        await manager.connect()

    assert manager.pool is pool
    assert create_pool.await_count == 2
    sleep.assert_awaited_once_with(MigrationManager.CONNECT_BACKOFF_BASE_SECONDS)


@pytest.mark.asyncio
async def test_connect_retries_target_server_attribute_not_matched() -> None:
    """asyncpg's multi-host fallback error is the OTHER shape the incident took."""
    manager = _manager()
    pool = object()
    create_pool = AsyncMock(
        side_effect=[asyncpg.exceptions.TargetServerAttributeNotMatched("no host matched"), pool]
    )

    with (
        patch("backend.db.migration_manager.asyncpg.create_pool", create_pool),
        patch("backend.db.migration_manager.asyncio.sleep", AsyncMock()),
    ):
        await manager.connect()

    assert manager.pool is pool
    assert create_pool.await_count == 2


@pytest.mark.asyncio
async def test_connect_gives_up_after_bounded_attempts_with_exponential_backoff() -> None:
    manager = _manager()
    create_pool = AsyncMock(side_effect=ConnectionResetError("reset by peer"))
    sleep = AsyncMock()

    with (
        patch("backend.db.migration_manager.asyncpg.create_pool", create_pool),
        patch("backend.db.migration_manager.asyncio.sleep", sleep),
    ):
        with pytest.raises(ConnectionResetError):
            await manager.connect()

    assert manager.pool is None
    assert create_pool.await_count == MigrationManager.CONNECT_ATTEMPTS
    base = MigrationManager.CONNECT_BACKOFF_BASE_SECONDS
    delays = [c.args[0] for c in sleep.await_args_list]
    assert delays == [base * (2**i) for i in range(MigrationManager.CONNECT_ATTEMPTS - 1)]


@pytest.mark.asyncio
async def test_connect_does_not_retry_postgres_level_refusals() -> None:
    """A bad password / missing database is a real error, not a flap."""
    manager = _manager()
    create_pool = AsyncMock(
        side_effect=asyncpg.exceptions.InvalidPasswordError("password authentication failed")
    )
    sleep = AsyncMock()

    with (
        patch("backend.db.migration_manager.asyncpg.create_pool", create_pool),
        patch("backend.db.migration_manager.asyncio.sleep", sleep),
    ):
        with pytest.raises(asyncpg.exceptions.InvalidPasswordError):
            await manager.connect()

    assert create_pool.await_count == 1
    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_connect_is_idempotent_once_connected() -> None:
    manager = _manager()
    pool = object()
    create_pool = AsyncMock(return_value=pool)

    with patch("backend.db.migration_manager.asyncpg.create_pool", create_pool):
        await manager.connect()
        await manager.connect()

    assert create_pool.await_count == 1
