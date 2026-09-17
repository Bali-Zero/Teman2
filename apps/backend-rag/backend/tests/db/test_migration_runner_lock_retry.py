"""Tests for `run_with_lock_retry` (backend/db/migration_base.py) — the
generic lock-timeout retry primitive wrapping `BaseMigration.apply()`'s and
`MigrationManager.rollback_migration`'s transaction bodies.

Born 2026-09-17 alongside the primitive itself: before this, ANY DDL
migration/rollback that lost a `lock_timeout` race against a long reader
(nightly pg_dump, an ordinary long transaction) failed the whole `apply()`
on the first occurrence, indistinguishable from any other SQL error.

Two layers, matching the two reference styles named in the task:

* UNIT — mocked `asyncpg.Connection`/pool, no database, following
  `test_migration_advisory_lock.py`'s `_FakeAcquireCtx` /
  `MigrationManager.__new__` pattern. Fast, exercises the retry/backoff/
  budget/blocker-naming logic in isolation.
* LIVE — real PostgreSQL, following `test_migration_317_visa_oracle_
  sessions_retention.py`'s live-concurrency pattern: a throwaway table, a
  holder transaction with `SET application_name = 'fake_pg_dump'` locking
  it in ACCESS SHARE MODE, released by an `asyncio` task after N seconds.
  Skipped when `TEST_DATABASE_URL` is unset; refuses to run against a
  database matching `_FORBIDDEN_DB_SUBSTRINGS`.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from backend.db.migration_base import (
    LOCK_RETRY_MAX_ATTEMPTS,
    BaseMigration,
    MigrationError,
    _lock_retry_backoff_seconds,
    run_with_lock_retry,
    split_migration_sql,
)
from backend.db.migration_manager import MigrationManager

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# UNIT — mocked connection, no database
# ---------------------------------------------------------------------------


def _lock_error(pid: int = 4242) -> asyncpg.exceptions.LockNotAvailableError:
    """Build a `LockNotAvailableError` the way asyncpg would raise it."""
    return asyncpg.exceptions.LockNotAvailableError("canceling statement due to lock timeout")


class _FakeTxCtx:
    """Stand-in for `conn.transaction()`'s async context manager.

    Mirrors real asyncpg semantics closely enough for this test: entering
    is a no-op, and on exit with an exception the transaction is considered
    rolled back (the exception is NOT suppressed — `__aexit__` returns
    False/None), which is exactly what lets `run_with_lock_retry` retry on
    the SAME `conn` object.
    """

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


def _new_fake_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=_FakeTxCtx())
    conn.execute = AsyncMock(return_value=None)
    return conn


def _lock_timeout_calls(conn: AsyncMock) -> list[str]:
    """The `SET LOCAL lock_timeout` statements issued on `conn.execute`."""
    return [call.args[0] for call in conn.execute.call_args_list if "lock_timeout" in call.args[0]]


# (a) retries twice then succeeds
async def test_retries_lock_not_available_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.db.migration_base.asyncio.sleep", AsyncMock(return_value=None))
    conn = _new_fake_conn()
    attempts: list[int] = []

    async def body() -> bool:
        attempts.append(1)
        if len(attempts) < 3:
            raise _lock_error()
        return True

    result = await run_with_lock_retry(conn, "test_migration", body)

    assert result is True
    assert len(attempts) == 3
    lock_calls = _lock_timeout_calls(conn)
    assert len(lock_calls) == 3
    for stmt in lock_calls:
        assert stmt.startswith("SET LOCAL lock_timeout")


# (b) QueryCanceledError propagates on the FIRST attempt, unretried
async def test_query_canceled_propagates_unretried(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_mock = AsyncMock(return_value=None)
    monkeypatch.setattr("backend.db.migration_base.asyncio.sleep", sleep_mock)
    conn = _new_fake_conn()
    attempts: list[int] = []

    async def body() -> bool:
        attempts.append(1)
        raise asyncpg.exceptions.QueryCanceledError("canceling statement due to statement timeout")

    with pytest.raises(asyncpg.exceptions.QueryCanceledError):
        await run_with_lock_retry(conn, "test_migration", body)

    assert len(attempts) == 1
    sleep_mock.assert_not_awaited()


# (c) a generic PostgresError propagates unretried
async def test_generic_postgres_error_propagates_unretried(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_mock = AsyncMock(return_value=None)
    monkeypatch.setattr("backend.db.migration_base.asyncio.sleep", sleep_mock)
    conn = _new_fake_conn()
    attempts: list[int] = []

    async def body() -> bool:
        attempts.append(1)
        raise asyncpg.exceptions.UndefinedTableError("relation does not exist")

    with pytest.raises(asyncpg.exceptions.UndefinedTableError):
        await run_with_lock_retry(conn, "test_migration", body)

    assert len(attempts) == 1
    sleep_mock.assert_not_awaited()


# (d) exhausted retries -> MigrationError names the blocker, never `query`
async def test_exhausted_retries_raises_migration_error_naming_blocker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("backend.db.migration_base.asyncio.sleep", AsyncMock(return_value=None))
    conn = _new_fake_conn()

    blocker_row = {
        "pid": 9911,
        "usename": "fake_pg_dump_role",
        "application_name": "fake_pg_dump",
        "relname": "visa_oracle_sessions",
    }
    conn.fetch = AsyncMock(return_value=[blocker_row])

    async def body() -> bool:
        raise _lock_error()

    with pytest.raises(MigrationError) as exc_info:
        await run_with_lock_retry(conn, "test_migration", body)

    message = str(exc_info.value)
    assert "still lock-blocked" in message
    assert "fake_pg_dump" in message
    assert "fake_pg_dump_role" in message
    assert "visa_oracle_sessions" in message
    assert "9911" in message
    assert "query" not in message.lower().replace("still lock-blocked", "")


# (e) budget: a small budget stops the loop before LOCK_RETRY_MAX_ATTEMPTS
async def test_budget_stops_loop_before_max_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.db.migration_base.asyncio.sleep", AsyncMock(return_value=None))
    monkeypatch.setattr("backend.db.migration_base.LOCK_RETRY_BUDGET_SECONDS", 0.05)
    conn = _new_fake_conn()
    conn.fetch = AsyncMock(return_value=[])
    attempts: list[int] = []

    async def body() -> bool:
        attempts.append(1)
        raise _lock_error()

    with pytest.raises(MigrationError):
        await run_with_lock_retry(conn, "test_migration", body)

    assert 0 < len(attempts) < LOCK_RETRY_MAX_ATTEMPTS


# (f) backoff doubles from 0.5, capped at 3.0, +<=20% jitter
def test_backoff_doubles_and_caps_with_jitter() -> None:
    expected_base = [0.5, 1.0, 2.0, 3.0, 3.0, 3.0, 3.0, 3.0]
    for attempt, base in enumerate(expected_base, start=1):
        # Sample repeatedly: jitter is random, bounds must hold every time.
        for _ in range(25):
            value = _lock_retry_backoff_seconds(attempt)
            assert base <= value <= base * 1.2 + 1e-9, (
                f"attempt {attempt}: expected [{base}, {base * 1.2}], got {value}"
            )


# (g) rollback_migration path: SET LOCAL, and a failed retry must not leave
# the DELETEs committed outside the retried transaction.
class _FakeAcquireCtx:
    """Async context manager wrapping a single connection mock — same shape
    as `test_migration_advisory_lock.py`'s helper of the same name."""

    def __init__(self, conn: AsyncMock) -> None:
        self.conn = conn

    async def __aenter__(self) -> AsyncMock:
        return self.conn

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


def _manager_with_conn(conn: AsyncMock) -> MigrationManager:
    mgr = MigrationManager.__new__(MigrationManager)
    mgr.database_url = "postgres://fake"
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_FakeAcquireCtx(conn))
    mgr.pool = pool
    return mgr


async def test_rollback_migration_uses_set_local_on_pooled_conn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("backend.db.migration_base.asyncio.sleep", AsyncMock(return_value=None))
    conn = _new_fake_conn()
    conn.fetchrow = AsyncMock(return_value={"rollback_sql": "DROP TABLE foo;"})

    mgr = _manager_with_conn(conn)

    result = await mgr.rollback_migration("some_migration")

    assert result is True
    lock_calls = _lock_timeout_calls(conn)
    assert len(lock_calls) == 1
    assert lock_calls[0].startswith("SET LOCAL lock_timeout")

    # Order: rollback SQL, then both ledger DELETEs, all inside the ONE
    # attempt that succeeded — none of them a bare statement outside the
    # retried transaction.
    executed = [call.args[0] for call in conn.execute.call_args_list]
    rollback_idx = executed.index("DROP TABLE foo;")
    delete_calls = [
        i for i, stmt in enumerate(executed) if stmt.strip().upper().startswith("DELETE")
    ]
    assert len(delete_calls) == 2
    assert all(i > rollback_idx for i in delete_calls)


async def test_rollback_migration_lock_failure_does_not_commit_deletes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the rollback body raises LockNotAvailableError on every attempt,
    the DELETEs from the ledger must never have been issued as part of an
    attempt that then succeeded — i.e. no DELETE appears after the LAST
    lock_timeout SET that was followed by a raised error."""
    monkeypatch.setattr("backend.db.migration_base.asyncio.sleep", AsyncMock(return_value=None))
    conn = _new_fake_conn()
    conn.fetchrow = AsyncMock(return_value={"rollback_sql": "DROP TABLE foo;"})
    conn.fetch = AsyncMock(return_value=[])

    call_count = {"n": 0}
    real_execute = conn.execute

    async def flaky_execute(stmt: str, *args: Any, **kwargs: Any) -> Any:
        if stmt == "DROP TABLE foo;":
            call_count["n"] += 1
            raise _lock_error()
        return await real_execute(stmt, *args, **kwargs)

    conn.execute = AsyncMock(side_effect=flaky_execute)

    mgr = _manager_with_conn(conn)

    with pytest.raises(MigrationError):
        await mgr.rollback_migration("some_migration")

    executed = [call.args[0] for call in conn.execute.call_args_list]
    assert not any(stmt.strip().upper().startswith("DELETE") for stmt in executed), (
        "no DELETE should ever have been issued: every attempt's rollback "
        "SQL raised LockNotAvailableError before reaching the ledger writes"
    )
    assert call_count["n"] == LOCK_RETRY_MAX_ATTEMPTS


# ---------------------------------------------------------------------------
# LIVE — real PostgreSQL, skipped without TEST_DATABASE_URL
# ---------------------------------------------------------------------------

TEST_DSN = os.environ.get("TEST_DATABASE_URL")

#: Same refusal convention as test_migration_317_visa_oracle_sessions_retention.py
#: and test_migration_advisory_lock.py's live siblings: never hold a table
#: lock / run DDL against anything that looks like a real database.
_FORBIDDEN_DB_SUBSTRINGS = ("nuzantara_rag", "prod", "production")


def _forbidden(dbname: str) -> str | None:
    lowered = dbname.lower()
    return next((bad for bad in _FORBIDDEN_DB_SUBSTRINGS if bad in lowered), None)


async def _refuse_if_real_database(conn: asyncpg.Connection) -> None:
    actual = await conn.fetchval("SELECT current_database()")
    if bad := _forbidden(actual or ""):
        pytest.fail(
            f"refusing to hold a table lock / run migration DDL against "
            f"database {actual!r} — it matched {bad!r}."
        )


_PROBE_TABLE = f"public._lock_retry_probe_{os.getpid()}"
_PROBE_MIGRATION_NAME = f"999999_lock_retry_probe_{os.getpid()}"


async def _hold_lock_for(tx: asyncpg.transaction.Transaction, *, seconds: float) -> None:
    await asyncio.sleep(seconds)
    await tx.commit()


async def _reset_ledger_and_probe(conn: asyncpg.Connection) -> None:
    await conn.execute(f"DROP TABLE IF EXISTS {_PROBE_TABLE}")
    for stmt, args in (
        ("DELETE FROM schema_migrations WHERE migration_name = $1", (_PROBE_MIGRATION_NAME,)),
        ("DELETE FROM _schema_versions WHERE migration_name = $1", (_PROBE_MIGRATION_NAME,)),
    ):
        try:
            await conn.execute(stmt, *args)
        except asyncpg.exceptions.UndefinedTableError:
            pass


def _write_probe_migration(tmp_path: Path) -> Path:
    sql = (
        f"CREATE TABLE IF NOT EXISTS {_PROBE_TABLE} (id SERIAL PRIMARY KEY);\n"
        f"ALTER TABLE {_PROBE_TABLE} ADD COLUMN IF NOT EXISTS c2 INT;\n"
        "-- === ROLLBACK ===\n"
        f"ALTER TABLE {_PROBE_TABLE} DROP COLUMN IF EXISTS c2;\n"
    )
    # NOTE: deliberately NOT prefixed with "999999_" — BaseMigration.__init__
    # builds `migration_name` as f"{migration_number:03d}_{sql_base_name}"
    # and only STRIPS a pre-existing prefix when it is exactly 3 digits
    # (`re.sub(r"^\d{3}_", ...)`). A 6-digit migration_number's own prefix
    # does not match that regex, so a filename that already started with
    # "999999_" would double up into "999999_999999_...", silently
    # desyncing `_PROBE_MIGRATION_NAME` (computed by hand below) from the
    # real ledger row and making `_reset_ledger_and_probe`'s DELETE match
    # zero rows — found live: it let a stale ledger row leak across test
    # runs and made a GUILT case pass on a re-run instead of raising.
    sql_file = tmp_path / f"lock_retry_probe_{os.getpid()}.sql"
    sql_file.write_text(sql, encoding="utf-8")
    return sql_file


@pytest.mark.skipif(not TEST_DSN, reason="TEST_DATABASE_URL is unset — no live Postgres to drive")
async def test_live_innocence_blocker_released_within_budget(tmp_path: Path) -> None:
    """INNOCENCE: a blocker released ~4s in lets `apply()` through — the
    column exists and the ledger has the row."""
    conn_a = await asyncpg.connect(TEST_DSN)
    try:
        await _refuse_if_real_database(conn_a)
        await _reset_ledger_and_probe(conn_a)
        await conn_a.execute(f"CREATE TABLE {_PROBE_TABLE} (id SERIAL PRIMARY KEY)")

        tx = conn_a.transaction()
        await tx.start()
        await conn_a.execute("SET application_name = 'fake_pg_dump'")
        await conn_a.execute(f"LOCK TABLE {_PROBE_TABLE} IN ACCESS SHARE MODE")

        sql_file = _write_probe_migration(tmp_path)
        _forward, rollback = split_migration_sql(sql_file.read_text(encoding="utf-8"))
        migration = BaseMigration(
            migration_number=999999,
            sql_file=sql_file.name,
            description="test: lock-retry innocence",
            rollback_sql=rollback,
            _sql_dir=sql_file.parent,
        )

        holder_task = asyncio.create_task(_hold_lock_for(tx, seconds=4))
        try:
            ok = await migration.apply(database_url=TEST_DSN, dedicated=False)
        finally:
            await holder_task

        assert ok is True

        conn_b = await asyncpg.connect(TEST_DSN)
        try:
            has_col = await conn_b.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=$1 AND column_name='c2')",
                _PROBE_TABLE.split(".")[-1],
            )
            assert has_col is True
            ledger_row = await conn_b.fetchval(
                "SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE migration_name = $1)",
                migration.migration_name,
            )
            assert ledger_row is True
        finally:
            await conn_b.close()
    finally:
        try:
            await _reset_ledger_and_probe(conn_a)
        finally:
            await conn_a.close()


@pytest.mark.skipif(not TEST_DSN, reason="TEST_DATABASE_URL is unset — no live Postgres to drive")
async def test_live_guilt_blocker_held_beyond_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GUILT: shrink the retry envelope (2 attempts, 10s budget) so the test
    stays fast, then hold the blocker ~15s. `apply()` must raise naming
    `fake_pg_dump`, and neither the column nor the ledger row may exist."""
    monkeypatch.setattr("backend.db.migration_base.LOCK_RETRY_MAX_ATTEMPTS", 2)
    monkeypatch.setattr("backend.db.migration_base.LOCK_RETRY_BUDGET_SECONDS", 10.0)

    conn_a = await asyncpg.connect(TEST_DSN)
    try:
        await _refuse_if_real_database(conn_a)
        await _reset_ledger_and_probe(conn_a)
        await conn_a.execute(f"CREATE TABLE {_PROBE_TABLE} (id SERIAL PRIMARY KEY)")

        tx = conn_a.transaction()
        await tx.start()
        await conn_a.execute("SET application_name = 'fake_pg_dump'")
        await conn_a.execute(f"LOCK TABLE {_PROBE_TABLE} IN ACCESS SHARE MODE")

        sql_file = _write_probe_migration(tmp_path)
        _forward, rollback = split_migration_sql(sql_file.read_text(encoding="utf-8"))
        migration = BaseMigration(
            migration_number=999999,
            sql_file=sql_file.name,
            description="test: lock-retry guilt",
            rollback_sql=rollback,
            _sql_dir=sql_file.parent,
        )

        holder_task = asyncio.create_task(_hold_lock_for(tx, seconds=15))
        try:
            with pytest.raises(MigrationError, match="still lock-blocked") as exc_info:
                await migration.apply(database_url=TEST_DSN, dedicated=False)
            assert "fake_pg_dump" in str(exc_info.value)
        finally:
            await holder_task

        conn_b = await asyncpg.connect(TEST_DSN)
        try:
            has_col = await conn_b.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=$1 AND column_name='c2')",
                _PROBE_TABLE.split(".")[-1],
            )
            assert has_col is False
            ledger_row = await conn_b.fetchval(
                "SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE migration_name = $1)",
                migration.migration_name,
            )
            assert ledger_row is False
        finally:
            await conn_b.close()
    finally:
        try:
            await _reset_ledger_and_probe(conn_a)
        finally:
            await conn_a.close()
