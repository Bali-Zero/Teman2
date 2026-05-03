"""
Unit tests for auto clock-in on team login (PANOPTICON Phase 0).

Tests the `_auto_clockin_if_needed` helper in backend/app/routers/auth.py.

Scenarios:
1. First team login of the day → inserts clock_in entry
2. Second login when already clocked in → skips (no duplicate)
3. Client role user → skips (not a team member)
4. DB error → handled gracefully, login not blocked
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_pool(fetchval_result: int = 0, execute_raises: Exception | None = None) -> MagicMock:
    """
    Build a minimal asyncpg Pool mock.

    - pool.acquire() is an async context manager that yields a connection mock
    - conn.fetchval() returns `fetchval_result`
    - conn.execute() either succeeds or raises `execute_raises`
    """
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=fetchval_result)

    if execute_raises is not None:
        conn.execute = AsyncMock(side_effect=execute_raises)
    else:
        conn.execute = AsyncMock(return_value=None)

    # pool.acquire() must be an async context manager
    acquire_cm = AsyncMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)

    return pool, conn


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAutoClockInIfNeeded:
    """Tests for the _auto_clockin_if_needed helper."""

    @pytest.mark.asyncio
    async def test_auto_clockin_inserts_on_first_login(self) -> None:
        """First team login of the day creates a clock_in entry."""
        from backend.app.routers.auth import _auto_clockin_if_needed

        pool, conn = _make_pool(fetchval_result=0)  # No existing record

        result = await _auto_clockin_if_needed(
            pool=pool,
            user_id="user-123",
            email="alice@balizero.com",
            role="team",
        )

        assert result is True
        conn.fetchval.assert_awaited_once()
        conn.execute.assert_awaited_once()

        # Verify the execute call inserts clock_in with auto_login source
        call_args = conn.execute.call_args
        sql: str = call_args[0][0]
        assert "clock_in" in sql
        assert "auto_login" in sql

    @pytest.mark.asyncio
    async def test_auto_clockin_skips_if_already_clocked_in(self) -> None:
        """Second login on same day does not create a duplicate entry."""
        from backend.app.routers.auth import _auto_clockin_if_needed

        pool, conn = _make_pool(fetchval_result=1)  # Already clocked in

        result = await _auto_clockin_if_needed(
            pool=pool,
            user_id="user-123",
            email="alice@balizero.com",
            role="team",
        )

        assert result is False
        conn.fetchval.assert_awaited_once()
        conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_auto_clockin_skips_client_users(self) -> None:
        """Client-role users are not team members — no clock-in inserted."""
        from backend.app.routers.auth import _auto_clockin_if_needed

        pool, conn = _make_pool(fetchval_result=0)

        result = await _auto_clockin_if_needed(
            pool=pool,
            user_id="client-456",
            email="john@example.com",
            role="client",
        )

        assert result is False
        # Pool should never be touched for client users
        conn.fetchval.assert_not_awaited()
        conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_auto_clockin_skips_non_balizero_email(self) -> None:
        """Non-@balizero.com emails (external accounts) are skipped."""
        from backend.app.routers.auth import _auto_clockin_if_needed

        pool, conn = _make_pool(fetchval_result=0)

        result = await _auto_clockin_if_needed(
            pool=pool,
            user_id="ext-789",
            email="partner@other-company.com",
            role="team",
        )

        assert result is False
        conn.fetchval.assert_not_awaited()
        conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_auto_clockin_handles_db_error_gracefully(self) -> None:
        """A DB error must not propagate — returns False, login continues."""
        from backend.app.routers.auth import _auto_clockin_if_needed

        pool, conn = _make_pool(
            fetchval_result=0,
            execute_raises=Exception("DB connection lost"),
        )

        # Should NOT raise
        result = await _auto_clockin_if_needed(
            pool=pool,
            user_id="user-123",
            email="bob@balizero.com",
            role="admin",
        )

        assert result is False
        conn.fetchval.assert_awaited_once()
        conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_auto_clockin_handles_fetchval_error_gracefully(self) -> None:
        """A DB error on SELECT also returns False without raising."""
        from backend.app.routers.auth import _auto_clockin_if_needed

        conn = AsyncMock()
        conn.fetchval = AsyncMock(side_effect=Exception("timeout"))
        conn.execute = AsyncMock()

        acquire_cm = AsyncMock()
        acquire_cm.__aenter__ = AsyncMock(return_value=conn)
        acquire_cm.__aexit__ = AsyncMock(return_value=False)

        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_cm)

        result = await _auto_clockin_if_needed(
            pool=pool,
            user_id="user-123",
            email="carol@balizero.com",
            role="team",
        )

        assert result is False
        conn.execute.assert_not_awaited()
