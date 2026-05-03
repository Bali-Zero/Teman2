"""Unit tests for `MigrationManager.apply_all_pending` advisory-lock semantics.

Postgres `pg_advisory_lock` / `pg_advisory_unlock` are session-scoped: a
lock acquired on connection A must be released on the same connection A.
Releasing on a different connection silently no-ops and the original
session keeps the lock until it terminates. The tests below pin that
contract so the bug we just fixed cannot regress.

These tests do not need real Postgres — they assert which connection
object received which SQL.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.db.migration_manager import MigrationManager


class _FakeAcquireCtx:
    """Async context manager wrapping a single connection mock.

    Behaves like the object returned by `asyncpg.Pool.acquire()`. We use
    one of these per simulated checkout so the test can prove that lock
    and unlock land on the *same* underlying connection.
    """

    def __init__(self, conn: AsyncMock) -> None:
        self.conn = conn

    async def __aenter__(self) -> AsyncMock:
        return self.conn

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


def _new_conn(*, lock_result: bool | None = True) -> AsyncMock:
    """Build a connection mock that records every SQL call.

    `fetchval` returns ``lock_result`` for `pg_try_advisory_lock`. `execute`
    is a recorder. Test asserts on `mock.call_args_list`.
    """
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=lock_result)
    conn.execute = AsyncMock(return_value=None)
    # marker so test failures pinpoint which connection ran which SQL
    conn._fake_id = id(conn)
    return conn


def _manager_with_pool(connections: list[AsyncMock]) -> MigrationManager:
    """Build a MigrationManager whose pool yields `connections` in order.

    Each `pool.acquire()` call returns the next connection from the list,
    each wrapped in its own context manager. Bypasses the asyncpg-creation
    code path entirely.
    """
    mgr = MigrationManager.__new__(MigrationManager)
    mgr.database_url = "postgres://fake"
    pool = MagicMock()
    iterator = iter(connections)

    def _acquire() -> _FakeAcquireCtx:
        try:
            conn = next(iterator)
        except StopIteration as exc:  # pragma: no cover - defensive
            raise AssertionError(
                "test ran out of fake connections — production code is "
                "calling pool.acquire() more times than expected",
            ) from exc
        return _FakeAcquireCtx(conn)

    pool.acquire = _acquire
    mgr.pool = pool
    return mgr


@pytest.mark.asyncio
async def test_lock_and_unlock_use_same_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: lock + unlock must hit the *same* asyncpg connection.

    Before the fix, `apply_all_pending` did
    ``async with pool.acquire() as conn: pg_try_advisory_lock(...)``
    and a second ``async with pool.acquire() as conn:
    pg_advisory_unlock(...)`` in `finally`. Because asyncpg pools recycle
    connections, the unlock often landed on a different session and was a
    no-op. This test ensures the new code threads the same connection
    through the whole run.
    """
    lock_conn = _new_conn(lock_result=True)
    mgr = _manager_with_pool([lock_conn])

    async def _no_pending(*_a: Any, **_kw: Any) -> dict:
        return {"applied": [], "skipped": [], "failed": []}

    monkeypatch.setattr(mgr, "_apply_all_pending_locked", _no_pending)

    await mgr.apply_all_pending()

    fetchval_calls = lock_conn.fetchval.call_args_list
    execute_calls = lock_conn.execute.call_args_list

    assert len(fetchval_calls) == 1
    assert "pg_try_advisory_lock" in fetchval_calls[0].args[0]

    assert len(execute_calls) == 1
    assert "pg_advisory_unlock" in execute_calls[0].args[0]


@pytest.mark.asyncio
async def test_lock_id_is_consistent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lock and unlock must reference the same advisory-lock id.

    The id is sent as a parameterised arg (the second positional in
    `fetchval`/`execute`); both calls must carry the same number.
    """
    lock_conn = _new_conn(lock_result=True)
    mgr = _manager_with_pool([lock_conn])

    async def _no_pending(*_a: Any, **_kw: Any) -> dict:
        return {"applied": [], "skipped": [], "failed": []}

    monkeypatch.setattr(mgr, "_apply_all_pending_locked", _no_pending)

    await mgr.apply_all_pending()

    lock_id_acquired = lock_conn.fetchval.call_args_list[0].args[1]
    lock_id_released = lock_conn.execute.call_args_list[0].args[1]
    assert lock_id_acquired == lock_id_released
    assert lock_id_acquired == MigrationManager._APPLY_ALL_LOCK_ID


@pytest.mark.asyncio
async def test_unlock_runs_even_if_locked_run_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the locked apply path raises, the lock must still be released.

    Without the explicit `try/finally` over the same connection, an
    exception inside `_apply_all_pending_locked` would leak the lock to
    the next session's worth of work.
    """
    lock_conn = _new_conn(lock_result=True)
    mgr = _manager_with_pool([lock_conn])

    async def _boom(*_a: Any, **_kw: Any) -> dict:
        raise RuntimeError("simulated migration failure")

    monkeypatch.setattr(mgr, "_apply_all_pending_locked", _boom)

    with pytest.raises(RuntimeError, match="simulated migration failure"):
        await mgr.apply_all_pending()

    # Even though the body raised, unlock must have been issued.
    assert lock_conn.execute.await_count == 1
    assert "pg_advisory_unlock" in lock_conn.execute.call_args_list[0].args[0]


@pytest.mark.asyncio
async def test_concurrent_runner_skipped_when_lock_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If `pg_try_advisory_lock` returns false, do nothing and return empty."""
    lock_conn = _new_conn(lock_result=False)
    mgr = _manager_with_pool([lock_conn])

    sentinel: dict[str, bool] = {"called": False}

    async def _should_not_run(*_a: Any, **_kw: Any) -> dict:
        sentinel["called"] = True
        return {"applied": [99], "skipped": [], "failed": []}

    monkeypatch.setattr(mgr, "_apply_all_pending_locked", _should_not_run)

    result = await mgr.apply_all_pending()

    assert result == {"applied": [], "skipped": [], "failed": []}
    assert sentinel["called"] is False
    # We must NOT have tried to release a lock we never acquired
    assert lock_conn.execute.await_count == 0


@pytest.mark.asyncio
async def test_unlock_failure_is_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A spurious error during unlock must not mask a successful run.

    The session is about to be returned to the pool; advisory locks die
    with the session, so a failed explicit release is best-effort.
    """
    lock_conn = _new_conn(lock_result=True)
    lock_conn.execute.side_effect = RuntimeError("network blip during unlock")
    mgr = _manager_with_pool([lock_conn])

    async def _ok(*_a: Any, **_kw: Any) -> dict:
        return {"applied": [42], "skipped": [], "failed": []}

    monkeypatch.setattr(mgr, "_apply_all_pending_locked", _ok)

    result = await mgr.apply_all_pending()
    assert result == {"applied": [42], "skipped": [], "failed": []}
