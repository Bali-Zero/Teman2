"""Tests for backend.app.routers.dashboard_summary"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Helper functions ────────────────────────────────────────────────────────


class TestGetUserId:
    def test_from_sub(self):
        from backend.app.routers.dashboard_summary import _get_user_id
        assert _get_user_id({"sub": "user123"}) == "user123"

    def test_from_user_id(self):
        from backend.app.routers.dashboard_summary import _get_user_id
        assert _get_user_id({"user_id": "user456"}) == "user456"

    def test_empty(self):
        from backend.app.routers.dashboard_summary import _get_user_id
        assert _get_user_id({}) == ""

    def test_sub_takes_precedence(self):
        from backend.app.routers.dashboard_summary import _get_user_id
        assert _get_user_id({"sub": "a", "user_id": "b"}) == "a"


class TestIsAdmin:
    def test_admin(self):
        from backend.app.routers.dashboard_summary import _is_admin
        assert _is_admin({"role": "admin"}) is True

    def test_founder(self):
        from backend.app.routers.dashboard_summary import _is_admin
        assert _is_admin({"role": "Founder"}) is True

    def test_owner(self):
        from backend.app.routers.dashboard_summary import _is_admin
        assert _is_admin({"role": "Owner"}) is True

    def test_team(self):
        from backend.app.routers.dashboard_summary import _is_admin
        assert _is_admin({"role": "team"}) is False

    def test_empty_role(self):
        from backend.app.routers.dashboard_summary import _is_admin
        assert _is_admin({}) is False


# ── _get_email_stats ────────────────────────────────────────────────────────


class TestGetEmailStats:
    @pytest.mark.asyncio
    async def test_not_connected(self):
        from backend.app.routers.dashboard_summary import _get_email_stats

        mock_pool = AsyncMock()
        with (
            patch("backend.app.routers.dashboard_summary.ZohoOAuthService") as MockOAuth,
            patch("backend.app.routers.dashboard_summary.ZohoEmailService"),
        ):
            mock_oauth = AsyncMock()
            mock_oauth.get_connection_status = AsyncMock(return_value={"connected": False})
            MockOAuth.return_value = mock_oauth

            result = await _get_email_stats(mock_pool, "user1")
            assert result["connected"] is False
            assert result["unread_count"] == 0

    @pytest.mark.asyncio
    async def test_connected(self):
        from backend.app.routers.dashboard_summary import _get_email_stats

        mock_pool = AsyncMock()
        with (
            patch("backend.app.routers.dashboard_summary.ZohoOAuthService") as MockOAuth,
            patch("backend.app.routers.dashboard_summary.ZohoEmailService") as MockEmail,
        ):
            mock_oauth = AsyncMock()
            mock_oauth.get_connection_status = AsyncMock(return_value={"connected": True})
            MockOAuth.return_value = mock_oauth

            mock_email = AsyncMock()
            mock_email.get_unread_count = AsyncMock(return_value=5)
            MockEmail.return_value = mock_email

            result = await _get_email_stats(mock_pool, "user1")
            assert result["connected"] is True
            assert result["unread_count"] == 5

    @pytest.mark.asyncio
    async def test_exception_returns_default(self):
        from backend.app.routers.dashboard_summary import _get_email_stats

        mock_pool = AsyncMock()
        with patch(
            "backend.app.routers.dashboard_summary.ZohoOAuthService",
            side_effect=Exception("fail"),
        ):
            result = await _get_email_stats(mock_pool, "user1")
            assert result["connected"] is False


# ── _get_critical_deadlines ─────────────────────────────────────────────────


def _make_pool(mock_conn):
    """Create a mock pool that works with `async with pool.acquire() as conn:`."""
    mock_pool = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = ctx
    return mock_pool


class TestGetCriticalDeadlines:
    @pytest.mark.asyncio
    async def test_admin_query(self):
        from backend.app.routers.dashboard_summary import _get_critical_deadlines

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"count": 3})
        mock_pool = _make_pool(mock_conn)

        result = await _get_critical_deadlines(mock_pool, "admin1", is_admin=True)
        assert result == 3

    @pytest.mark.asyncio
    async def test_team_query(self):
        from backend.app.routers.dashboard_summary import _get_critical_deadlines

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"count": 1})
        mock_pool = _make_pool(mock_conn)

        result = await _get_critical_deadlines(mock_pool, "team1", is_admin=False)
        assert result == 1

    @pytest.mark.asyncio
    async def test_exception_returns_zero(self):
        from backend.app.routers.dashboard_summary import _get_critical_deadlines

        mock_pool = AsyncMock()
        mock_pool.acquire.side_effect = Exception("fail")

        result = await _get_critical_deadlines(mock_pool, "user1", is_admin=False)
        assert result == 0


# ── _get_revenue_stats ──────────────────────────────────────────────────────


class TestGetRevenueStats:
    @pytest.mark.asyncio
    async def test_returns_revenue(self):
        from backend.app.routers.dashboard_summary import _get_revenue_stats

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "total_revenue": 10000,
            "paid_revenue": 7000,
            "outstanding_revenue": 3000,
        })
        mock_pool = _make_pool(mock_conn)

        result = await _get_revenue_stats(mock_pool)
        assert result["total_revenue"] == 10000.0
        assert result["paid_revenue"] == 7000.0

    @pytest.mark.asyncio
    async def test_no_revenue_row(self):
        from backend.app.routers.dashboard_summary import _get_revenue_stats

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool = _make_pool(mock_conn)

        result = await _get_revenue_stats(mock_pool)
        assert result["total_revenue"] == 0

    @pytest.mark.asyncio
    async def test_exception_returns_zeros(self):
        from backend.app.routers.dashboard_summary import _get_revenue_stats

        mock_pool = AsyncMock()
        mock_pool.acquire.side_effect = Exception("fail")

        result = await _get_revenue_stats(mock_pool)
        assert result["total_revenue"] == 0


# ── _calculate_revenue_growth ───────────────────────────────────────────────


class TestCalculateRevenueGrowth:
    @pytest.mark.asyncio
    async def test_positive_growth(self):
        from backend.app.routers.dashboard_summary import _calculate_revenue_growth

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            side_effect=[{"revenue": 15000}, {"revenue": 10000}],
        )
        mock_pool = _make_pool(mock_conn)

        result = await _calculate_revenue_growth(mock_pool)
        assert result == 50.0

    @pytest.mark.asyncio
    async def test_zero_previous(self):
        from backend.app.routers.dashboard_summary import _calculate_revenue_growth

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            side_effect=[{"revenue": 5000}, {"revenue": 0}],
        )
        mock_pool = _make_pool(mock_conn)

        result = await _calculate_revenue_growth(mock_pool)
        assert result == 100.0

    @pytest.mark.asyncio
    async def test_both_zero(self):
        from backend.app.routers.dashboard_summary import _calculate_revenue_growth

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(side_effect=[{"revenue": 0}, {"revenue": 0}])
        mock_pool = _make_pool(mock_conn)

        result = await _calculate_revenue_growth(mock_pool)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_exception_returns_zero(self):
        from backend.app.routers.dashboard_summary import _calculate_revenue_growth

        mock_pool = AsyncMock()
        mock_pool.acquire.side_effect = Exception("fail")

        result = await _calculate_revenue_growth(mock_pool)
        assert result == 0.0
