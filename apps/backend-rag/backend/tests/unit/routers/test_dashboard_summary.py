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

        mock_pool = MagicMock()
        mock_pool.acquire.side_effect = Exception("fail")

        result = await _get_critical_deadlines(mock_pool, "user1", is_admin=False)
        assert result == 0


# ── _get_revenue_stats ──────────────────────────────────────────────────────


class TestGetRevenueStats:
    @pytest.mark.asyncio
    async def test_returns_revenue(self):
        from backend.app.routers.dashboard_summary import _get_revenue_stats

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(
            return_value={
                "total_revenue": 10000,
                "paid_revenue": 7000,
                "outstanding_revenue": 3000,
            }
        )
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

        mock_pool = MagicMock()
        mock_pool.acquire.side_effect = Exception("fail")

        result = await _get_revenue_stats(mock_pool)
        assert result["total_revenue"] == 0


# ── _get_total_clients ──────────────────────────────────────────────────────


class TestGetTotalClients:
    @pytest.mark.asyncio
    async def test_returns_count(self):
        from backend.app.routers.dashboard_summary import _get_total_clients

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1481)
        mock_pool = _make_pool(mock_conn)

        assert await _get_total_clients(mock_pool) == 1481
        # Same source as /clients: non-soft-deleted, NOT status='active'
        sql = mock_conn.fetchval.call_args.args[0]
        assert "deleted_at IS NULL" in sql
        assert "status" not in sql

    @pytest.mark.asyncio
    async def test_none_returns_zero(self):
        from backend.app.routers.dashboard_summary import _get_total_clients

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=None)
        mock_pool = _make_pool(mock_conn)

        assert await _get_total_clients(mock_pool) == 0

    @pytest.mark.asyncio
    async def test_exception_returns_zero(self):
        from backend.app.routers.dashboard_summary import _get_total_clients

        mock_pool = MagicMock()
        mock_pool.acquire.side_effect = Exception("fail")

        assert await _get_total_clients(mock_pool) == 0


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

        mock_pool = MagicMock()
        mock_pool.acquire.side_effect = Exception("fail")

        result = await _calculate_revenue_growth(mock_pool)
        assert result == 0.0


# ── _get_active_team_members_count (replaces role=zero's fake agenti_count) ─


class TestGetActiveTeamMembersCount:
    @pytest.mark.asyncio
    async def test_returns_count(self):
        from backend.app.routers.dashboard_summary import _get_active_team_members_count

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=7)
        mock_pool = _make_pool(mock_conn)

        assert await _get_active_team_members_count(mock_pool) == 7
        sql = mock_conn.fetchval.call_args.args[0]
        assert "team_members" in sql
        assert "active = TRUE" in sql

    @pytest.mark.asyncio
    async def test_exception_returns_zero(self):
        from backend.app.routers.dashboard_summary import _get_active_team_members_count

        mock_pool = MagicMock()
        mock_pool.acquire.side_effect = Exception("fail")

        assert await _get_active_team_members_count(mock_pool) == 0


# ── _get_compliant_clients_count (replaces role=tax's fake clienti_compliant) ─


class TestGetCompliantClientsCount:
    @pytest.mark.asyncio
    async def test_returns_count(self):
        from backend.app.routers.dashboard_summary import _get_compliant_clients_count

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=12)
        mock_pool = _make_pool(mock_conn)

        assert await _get_compliant_clients_count(mock_pool) == 12
        sql = mock_conn.fetchval.call_args.args[0]
        assert "compliance_alerts" in sql
        assert "deleted_at IS NULL" in sql

    @pytest.mark.asyncio
    async def test_exception_returns_zero(self):
        from backend.app.routers.dashboard_summary import _get_compliant_clients_count

        mock_pool = MagicMock()
        mock_pool.acquire.side_effect = Exception("fail")

        assert await _get_compliant_clients_count(mock_pool) == 0


# ── _get_pending_tax_alerts_count (replaces role=tax's fake alert_pajak) ────


class TestGetPendingTaxAlertsCount:
    @pytest.mark.asyncio
    async def test_returns_count(self):
        from backend.app.routers.dashboard_summary import _get_pending_tax_alerts_count

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=3)
        mock_pool = _make_pool(mock_conn)

        assert await _get_pending_tax_alerts_count(mock_pool) == 3
        sql = mock_conn.fetchval.call_args.args[0]
        assert "category = 'tax'" in sql

    @pytest.mark.asyncio
    async def test_exception_returns_zero(self):
        from backend.app.routers.dashboard_summary import _get_pending_tax_alerts_count

        mock_pool = MagicMock()
        mock_pool.acquire.side_effect = Exception("fail")

        assert await _get_pending_tax_alerts_count(mock_pool) == 0


# ── _get_new_leads_count (replaces role=marketing's fake lead_nuovi) ────────


class TestGetNewLeadsCount:
    @pytest.mark.asyncio
    async def test_returns_count(self):
        from backend.app.routers.dashboard_summary import _get_new_leads_count

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=9)
        mock_pool = _make_pool(mock_conn)

        assert await _get_new_leads_count(mock_pool) == 9
        sql = mock_conn.fetchval.call_args.args[0]
        assert "lead_intents" in sql

    @pytest.mark.asyncio
    async def test_exception_returns_zero(self):
        from backend.app.routers.dashboard_summary import _get_new_leads_count

        mock_pool = MagicMock()
        mock_pool.acquire.side_effect = Exception("fail")

        assert await _get_new_leads_count(mock_pool) == 0


# ── get_role_metrics: fake constants removed / replaced ─────────────────────


class TestGetRoleMetricsFakeConstantsGone:
    @pytest.mark.asyncio
    async def test_zero_role_agenti_count_from_query_no_fly_uptime(self):
        from backend.app.routers.dashboard_summary import get_role_metrics

        mock_conn = AsyncMock()
        # order: active_practices, overdue_invoices, revenue_mtd, expiring_soon,
        # then _get_active_team_members_count's own query
        mock_conn.fetchval = AsyncMock(side_effect=[5, 2, 10000, 1, 8])
        mock_pool = _make_pool(mock_conn)

        result = await get_role_metrics(
            role="zero", user_id="", _current_user={}, db_pool=mock_pool
        )

        assert result["metrics"]["agenti_count"] == 8
        assert "fly_uptime" not in result["metrics"]

    @pytest.mark.asyncio
    async def test_team_role_has_no_doc_mancanti(self):
        from backend.app.routers.dashboard_summary import get_role_metrics

        mock_conn = AsyncMock()
        # order: active_practices, overdue_invoices, revenue_mtd, expiring_soon,
        # then team's own user_practices, stalled, next_deadline
        mock_conn.fetchval = AsyncMock(
            side_effect=[5, 2, 10000, 1, 3, 0, "20/03/2026"],
        )
        mock_pool = _make_pool(mock_conn)

        result = await get_role_metrics(
            role="team", user_id="u1", _current_user={}, db_pool=mock_pool
        )

        assert "doc_mancanti" not in result["metrics"]
        assert result["metrics"]["assigned_cases"] == 3

    @pytest.mark.asyncio
    async def test_tax_role_clienti_compliant_and_alert_pajak_from_query(self):
        from backend.app.routers.dashboard_summary import get_role_metrics

        mock_conn = AsyncMock()
        # order: active_practices, overdue_invoices, revenue_mtd, expiring_soon,
        # then _get_compliant_clients_count, then _get_pending_tax_alerts_count
        mock_conn.fetchval = AsyncMock(side_effect=[5, 2, 10000, 1, 14, 4])
        mock_pool = _make_pool(mock_conn)

        result = await get_role_metrics(
            role="tax", user_id="", _current_user={}, db_pool=mock_pool
        )

        assert result["metrics"]["clienti_compliant"] == 14
        assert result["metrics"]["alert_pajak"] == 4

    @pytest.mark.asyncio
    async def test_marketing_role_lead_nuovi_from_query_no_subscriber_delta(self):
        from backend.app.routers.dashboard_summary import get_role_metrics

        mock_conn = AsyncMock()
        # order: active_practices, overdue_invoices, revenue_mtd, expiring_soon,
        # then articles_published, articles_review, then _get_new_leads_count
        mock_conn.fetchval = AsyncMock(side_effect=[5, 2, 10000, 1, 6, 2, 11])
        mock_pool = _make_pool(mock_conn)

        result = await get_role_metrics(
            role="marketing", user_id="", _current_user={}, db_pool=mock_pool
        )

        assert result["metrics"]["lead_nuovi"] == 11
        assert "subscriber_delta" not in result["metrics"]


# ── get_neural_pulse: fake fallback constants removed ───────────────────────


class TestGetNeuralPulseFakeFieldsGone:
    @pytest.mark.asyncio
    async def test_model_version_removed_and_real_zero_not_masked(self):
        from backend.app.routers.dashboard_summary import get_neural_pulse

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=None)  # last_conv / last_int
        mock_pool = _make_pool(mock_conn)

        mock_memory_service = AsyncMock()
        mock_memory_service.get_stats = AsyncMock(return_value={"total_facts": 0})

        mock_qdrant = AsyncMock()
        mock_qdrant.get_stats = AsyncMock(return_value={"total_documents": 0})
        mock_qdrant.close = AsyncMock()

        with (
            patch("backend.app.routers.dashboard_summary._cache") as mock_cache,
            patch(
                "backend.app.routers.dashboard_summary.CollectiveMemoryService",
                return_value=mock_memory_service,
            ),
            patch(
                "backend.app.routers.dashboard_summary.QdrantClient",
                return_value=mock_qdrant,
            ),
        ):
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()

            result = await get_neural_pulse(db_pool=mock_pool)

        # memory_facts/knowledge_docs were previously masked with `or 42` /
        # `or 53757` fallbacks whenever the real query returned a genuine 0.
        assert result["memory_facts"] == 0
        assert result["knowledge_docs"] == 0
        assert "model_version" not in result


# ── GET /api/dashboard/portal-challenge ─────────────────────────────────────


class TestPortalChallengeEndpoint:
    """Endpoint-level tests: real `require_team_member` gate, mocked pool."""

    @pytest.fixture(autouse=True)
    def _bypass_cache(self):
        """Every test computes fresh — no cross-test pollution via the
        module-singleton `_cache`."""
        with patch("backend.app.routers.dashboard_summary._cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            yield mock_cache

    def _make_client(self, current_user: dict, mock_pool):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from backend.app.dependencies import get_current_user, get_database_pool
        from backend.app.routers.dashboard_summary import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: current_user
        app.dependency_overrides[get_database_pool] = lambda: mock_pool
        return TestClient(app)

    def test_client_token_rejected(self, mock_client_user, mock_db_pool):
        """A portal CLIENT token must never reach the staff leaderboard."""
        client = self._make_client(mock_client_user, mock_db_pool)
        resp = client.get("/api/dashboard/portal-challenge")
        assert resp.status_code == 403

    def test_staff_token_returns_leaderboard(self, mock_current_user, mock_db_pool):
        from datetime import datetime, timezone

        roster_rows = [
            {
                "email": "winner@balizero.com",
                "display_name": "Winner",
                "department": "setup",
                "role": "member",
                "active": True,
            },
            {
                "email": "zero_activity@balizero.com",
                "display_name": "Zero Activity",
                "department": "setup",
                "role": "member",
                "active": True,
            },
        ]
        activity_rows = [
            {
                "creator_email": "winner@balizero.com",
                "activations": 20,
                "invited": 20,
                "last_activation_at": datetime(2026, 9, 20, tzinfo=timezone.utc),
            }
        ]
        recent_rows = [
            {
                "creator_email": "winner@balizero.com",
                "used_at": datetime(2026, 9, 20, tzinfo=timezone.utc),
            }
        ]
        mock_db_pool._mock_conn.fetch = AsyncMock(
            side_effect=[roster_rows, activity_rows, recent_rows]
        )

        client = self._make_client(mock_current_user, mock_db_pool)
        resp = client.get("/api/dashboard/portal-challenge")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] in {"upcoming", "live", "closed"}
        assert body["timezone"] == "Asia/Makassar"
        assert {t["tier"] for t in body["tiers"]} == {1, 2, 3}
        assert body["team_total_activations"] == 20

        by_member = {e["member"]: e for e in body["entries"]}
        assert by_member["winner"]["activations"] == 20
        assert by_member["winner"]["award_tier"] == 1
        assert by_member["winner"]["prize_idr"] == 3_000_000
        assert by_member["winner"]["is_me"] is (mock_current_user["email"] == "winner@balizero.com")
        assert by_member["zero_activity"]["activations"] == 0
        assert by_member["zero_activity"]["award_tier"] is None

        assert len(body["recent_activations"]) == 1
        assert body["recent_activations"][0]["display_name"] == "Winner"

    def test_staff_token_is_me_flags_the_caller(self, mock_db_pool):

        # A "clean" staff email — the shared `mock_current_user` fixture uses
        # test@balizero.com, which the roster merge deliberately filters as a
        # QA fixture account (see TestMergeRosterAndActivity), so it can't be
        # used to exercise the is_me=True branch here.
        caller = {"id": "u1", "email": "caller@balizero.com", "role": "member", "full_name": "Caller"}
        roster_rows = [
            {
                "email": "caller@balizero.com",
                "display_name": "Caller",
                "department": "setup",
                "role": "member",
                "active": True,
            }
        ]
        mock_db_pool._mock_conn.fetch = AsyncMock(side_effect=[roster_rows, [], []])

        client = self._make_client(caller, mock_db_pool)
        resp = client.get("/api/dashboard/portal-challenge")

        assert resp.status_code == 200
        entries = resp.json()["entries"]
        assert len(entries) == 1
        assert entries[0]["is_me"] is True
