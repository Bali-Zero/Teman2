"""`_purge_expired_sessions` (migration 317's enforcement arm) — guilt/innocence
pair for the one invariant that matters most: a session that was handed off
to a consultant must NEVER be deleted, even once it is past its own
`expires_at`. Uses the same fake-pool pattern as
`test_visa_oracle_handoff.py` (`_AcquireCM` + `AsyncMock` on `conn.execute`,
asserting the SQL text/params) — no real database needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class _AcquireCM:
    """Minimal async context manager mimicking `pool.acquire()` (mirrors
    test_visa_oracle_handoff.py's own helper — duplicated here rather than
    imported, since that file has no shared conftest export for it)."""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_a):
        return False


def _fake_pool(execute_return="DELETE 0"):
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=execute_return)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireCM(conn))
    return pool, conn


@pytest.mark.asyncio
async def test_purge_sql_excludes_handoff_triggered_rows_and_expired_only() -> None:
    """Guilt/innocence, SQL-shape half: the WHERE clause must both scope to
    expired rows AND exclude any row with handoff_triggered = TRUE. If a
    future edit dropped the handoff exclusion, this assertion goes red
    before any row is ever deleted for real."""
    from backend.app.routers import visa_oracle as mod

    pool, conn = _fake_pool("DELETE 0")

    await mod._purge_expired_sessions(pool, limit=500)

    assert conn.execute.await_count == 1
    sql_arg = conn.execute.await_args.args[0]
    assert "DELETE FROM visa_oracle_sessions" in sql_arg
    assert "expires_at < NOW()" in sql_arg
    assert "NOT COALESCE(handoff_triggered, false)" in sql_arg
    # Bounded, not a bare table-wide DELETE.
    assert "LIMIT $1" in sql_arg
    assert conn.execute.await_args.args[1] == 500


@pytest.mark.asyncio
async def test_purge_returns_deleted_count_from_asyncpg_status() -> None:
    from backend.app.routers import visa_oracle as mod

    pool, _conn = _fake_pool("DELETE 3")

    deleted = await mod._purge_expired_sessions(pool, limit=500)

    assert deleted == 3


@pytest.mark.asyncio
async def test_purge_returns_zero_on_unparseable_status() -> None:
    from backend.app.routers import visa_oracle as mod

    pool, _conn = _fake_pool("")

    deleted = await mod._purge_expired_sessions(pool, limit=500)

    assert deleted == 0


@pytest.mark.asyncio
async def test_purge_is_non_fatal_on_db_error_and_returns_zero(caplog) -> None:
    """Non-fatal on error, per the router's other session helpers'
    convention — never raises, logs a warning, returns 0."""
    from backend.app.routers import visa_oracle as mod

    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=RuntimeError("connection reset"))
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireCM(conn))

    with caplog.at_level("WARNING"):
        deleted = await mod._purge_expired_sessions(pool, limit=500)

    assert deleted == 0
    assert any("visa-oracle session purge failed" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_purge_failure_log_never_carries_the_exception_message(caplog) -> None:
    """Council round 1, finding F8 (Codex, PROVEN): this catch used to log
    `str(exc)` — an asyncpg error's message can echo back bound values, and
    this function's own docstring already promises "failures are logged,
    not raised" under the same PII discipline as the other session helpers.
    A sentinel string planted in the exception's message must never reach
    any log record; only the exception's CLASS name may."""
    from backend.app.routers import visa_oracle as mod

    sentinel = "session_id=abc123-should-never-be-logged"
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=RuntimeError(sentinel))
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AcquireCM(conn))

    with caplog.at_level("WARNING"):
        deleted = await mod._purge_expired_sessions(pool, limit=500)

    assert deleted == 0
    messages = [r.message for r in caplog.records]
    assert any("visa-oracle session purge failed" in m for m in messages)
    assert any("RuntimeError" in m for m in messages)
    for m in messages:
        assert sentinel not in m


@pytest.mark.asyncio
async def test_purge_does_not_log_session_ids_or_answers_on_success(caplog) -> None:
    """PII discipline: a successful purge logs only the count, never a
    session_id, quiz_answers, message or ip_hash (none of which this
    function ever reads in the first place — the DELETE returns a bare
    asyncpg status string, not rows)."""
    from backend.app.routers import visa_oracle as mod

    pool, _conn = _fake_pool("DELETE 5")

    with caplog.at_level("INFO"):
        deleted = await mod._purge_expired_sessions(pool, limit=500)

    assert deleted == 5
    messages = [r.message for r in caplog.records]
    assert any("deleted=5" in m for m in messages)
    for m in messages:
        assert "session_id" not in m
        assert "quiz_answers" not in m
        assert "ip_hash" not in m
