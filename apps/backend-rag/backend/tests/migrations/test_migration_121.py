"""Tests for migration 121 and its DDL lock guard."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

import asyncpg
import pytest


def _sql_calls(conn: AsyncMock) -> list[str]:
    """Return SQL passed to the connection execute mock."""
    return [call.args[0] for call in conn.execute.call_args_list]


@pytest.mark.asyncio
async def test_migration_121_noops_without_ddl_when_column_and_index_exist() -> None:
    """Existing schema must never issue a lock-taking DDL statement."""
    from backend.migrations.migration_121_practices_family_member import apply

    conn = AsyncMock()
    conn.fetchval.side_effect = [True, True]

    await apply(conn)

    assert conn.execute.call_count == 0


@pytest.mark.asyncio
async def test_migration_121_creates_missing_column_and_index_in_order() -> None:
    """A new schema receives the column before its dependent index."""
    from backend.migrations.migration_121_practices_family_member import apply

    conn = AsyncMock()
    conn.fetchval.side_effect = [False, False]

    await apply(conn)

    sql = _sql_calls(conn)
    assert len(sql) == 2
    assert "ALTER TABLE practices" in sql[0]
    assert "CREATE INDEX IF NOT EXISTS idx_practices_family_member_id" in sql[1]


@pytest.mark.asyncio
async def test_migration_121_creates_only_missing_index() -> None:
    """An existing column skips ALTER TABLE when only the index is absent."""
    from backend.migrations.migration_121_practices_family_member import apply

    conn = AsyncMock()
    conn.fetchval.side_effect = [True, False]

    await apply(conn)

    sql = _sql_calls(conn)
    assert sql == [
        "CREATE INDEX IF NOT EXISTS idx_practices_family_member_id "
        "ON practices (family_member_id) "
        "WHERE family_member_id IS NOT NULL;"
    ]


@pytest.mark.asyncio
async def test_lock_guard_sets_timeout_before_calling_ddl() -> None:
    """The session lock timeout is set before invoking the DDL function."""
    from backend.migrations._lock_guard import run_ddl_with_lock_timeout

    conn = AsyncMock()
    call_order: list[str] = []

    async def fn(connection: asyncpg.Connection) -> None:
        assert connection is conn
        call_order.append("fn")

    conn.execute.side_effect = lambda sql: call_order.append(sql)

    await run_ddl_with_lock_timeout(conn, fn)

    assert call_order == ["SET lock_timeout = '5s'", "fn"]


@pytest.mark.asyncio
async def test_lock_guard_retries_until_ddl_succeeds() -> None:
    """Two unavailable locks retry twice before a successful third attempt."""
    from backend.migrations._lock_guard import run_ddl_with_lock_timeout

    conn = AsyncMock()
    fn: Callable[[asyncpg.Connection], Awaitable[None]] = AsyncMock(
        side_effect=[
            asyncpg.exceptions.LockNotAvailableError("x"),
            asyncpg.exceptions.LockNotAvailableError("x"),
            None,
        ]
    )
    sleeper = AsyncMock()

    await run_ddl_with_lock_timeout(conn, fn, sleeper=sleeper)

    assert fn.call_count == 3
    assert sleeper.call_count == 2


@pytest.mark.asyncio
async def test_lock_guard_reraises_after_all_attempts() -> None:
    """An unavailable lock after the final attempt remains visible to callers."""
    from backend.migrations._lock_guard import run_ddl_with_lock_timeout

    conn = AsyncMock()
    fn: Callable[[asyncpg.Connection], Awaitable[None]] = AsyncMock(
        side_effect=asyncpg.exceptions.LockNotAvailableError("x")
    )
    sleeper = AsyncMock()

    with pytest.raises(asyncpg.exceptions.LockNotAvailableError):
        await run_ddl_with_lock_timeout(conn, fn, attempts=3, sleeper=sleeper)

    assert fn.call_count == 3
    assert sleeper.call_count == 2


@pytest.mark.asyncio
async def test_lock_guard_rejects_invalid_timeout_before_execute() -> None:
    """Timeout validation must prevent unsafe SQL interpolation."""
    from backend.migrations._lock_guard import run_ddl_with_lock_timeout

    conn = AsyncMock()
    fn: Callable[[asyncpg.Connection], Awaitable[None]] = AsyncMock()

    with pytest.raises(ValueError, match="Invalid lock_timeout"):
        await run_ddl_with_lock_timeout(conn, fn, lock_timeout="5s; SELECT 1")

    assert conn.execute.call_count == 0
