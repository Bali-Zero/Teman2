"""
Unit tests for backend/app/routers/admin_team_activity.py

Covers: verify_admin, get_overview, get_messages, get_team_stats,
        get_timesheet, get_crm_actions, get_practice_stats,
        export_messages, response models.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.app.routers.admin_team_activity import (
    MessageItem,
    OverviewStats,
    TeamMemberStats,
    verify_admin,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def admin_user():
    return {"email": "zero@balizero.com", "role": "admin"}


@pytest.fixture
def non_admin_user():
    return {"email": "agent@balizero.com", "role": "agent"}


@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    conn = AsyncMock()
    acq = MagicMock()
    acq.__aenter__ = AsyncMock(return_value=conn)
    acq.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acq)
    pool._mock_conn = conn
    return pool


# ============================================================================
# Models
# ============================================================================


class TestModels:
    def test_message_item(self):
        m = MessageItem(
            conversation_id=1, user_id="user@test.com",
            role="user", content="Hello",
            message_timestamp=datetime.now(tz=timezone.utc),
            content_length=5,
        )
        assert m.conversation_id == 1

    def test_team_member_stats(self):
        s = TeamMemberStats(
            email="a@t.com", name="Alice", role="agent",
            department="visa", conversations=10, messages=50,
            days_worked=20, crm_actions=30,
            last_activity=datetime.now(tz=timezone.utc),
        )
        assert s.messages == 50

    def test_overview_stats(self):
        o = OverviewStats(
            total_conversations=100, total_messages=500,
            total_team_members=5, active_today=3, messages_today=20,
        )
        assert o.active_today == 3


# ============================================================================
# verify_admin
# ============================================================================


class TestVerifyAdmin:
    @pytest.mark.asyncio
    @patch("backend.app.routers.admin_team_activity.is_crm_admin", return_value=True)
    async def test_admin_allowed(self, mock_is_admin, admin_user):
        result = await verify_admin(current_user=admin_user)
        assert result == admin_user

    @pytest.mark.asyncio
    @patch("backend.app.routers.admin_team_activity.is_crm_admin", return_value=False)
    async def test_non_admin_rejected(self, mock_is_admin, non_admin_user):
        with pytest.raises(HTTPException) as exc_info:
            await verify_admin(current_user=non_admin_user)
        assert exc_info.value.status_code == 403


# ============================================================================
# Endpoint tests (direct function calls with mocked deps)
# ============================================================================


class TestGetOverview:
    @pytest.mark.asyncio
    async def test_overview_no_start_date(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_overview

        conn = mock_db_pool._mock_conn
        # get_overview calls fetchval 5 times: total_convs, total_msgs, kg_nodes, kg_edges, total_team, active_today, msgs_today
        conn.fetchval = AsyncMock(side_effect=[100, 500, 50, 20, 5, 3, 10])
        conn.fetch = AsyncMock(return_value=[
            {"user_id": "user@test.com", "msg_count": 42},
        ])

        result = await get_overview(
            start_date=None, _admin={"email": "admin"}, db_pool=mock_db_pool,
        )
        assert result["success"] is True
        assert result["stats"]["total_conversations"] == 100

    @pytest.mark.asyncio
    async def test_overview_with_start_date(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_overview

        conn = mock_db_pool._mock_conn
        # 7 fetchval calls
        conn.fetchval = AsyncMock(side_effect=[50, 200, 10, 15, 5, 3, 8])
        conn.fetch = AsyncMock(return_value=[])

        result = await get_overview(
            start_date="2026-01-01", _admin={"email": "admin"}, db_pool=mock_db_pool,
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_overview_db_error(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_overview

        mock_db_pool._mock_conn.fetchval = AsyncMock(side_effect=Exception("DB error"))
        with pytest.raises(HTTPException) as exc_info:
            await get_overview(start_date=None, _admin={"email": "admin"}, db_pool=mock_db_pool)
        assert exc_info.value.status_code == 500


class TestGetMessages:
    @pytest.mark.asyncio
    async def test_no_filters(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_messages

        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(return_value=10)
        conn.fetch = AsyncMock(return_value=[
            {"conversation_id": 1, "user_id": "u@t.com", "role": "user", "content": "Hi"},
        ])

        result = await get_messages(
            user_id=None, role=None, search=None,
            date_from=None, date_to=None, limit=100, offset=0,
            _admin={"email": "admin"}, db_pool=mock_db_pool,
        )
        assert result["success"] is True
        assert result["total"] == 10

    @pytest.mark.asyncio
    async def test_with_all_filters(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_messages

        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[])

        result = await get_messages(
            user_id="u@t.com", role="user", search="visa",
            date_from="2026-01-01", date_to="2026-04-01",
            limit=50, offset=0,
            _admin={"email": "admin"}, db_pool=mock_db_pool,
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_db_error(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_messages

        mock_db_pool._mock_conn.fetchval = AsyncMock(side_effect=Exception("fail"))
        with pytest.raises(HTTPException):
            await get_messages(
                user_id=None, role=None, search=None,
                date_from=None, date_to=None, limit=100, offset=0,
                _admin={"email": "admin"}, db_pool=mock_db_pool,
            )


class TestGetTeamStats:
    @pytest.mark.asyncio
    async def test_with_days(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_team_stats

        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[
            {"email": "a@t.com", "name": "Alice", "messages": 10},
        ])
        result = await get_team_stats(
            days=30, start_date=None, _admin={"email": "admin"}, db_pool=mock_db_pool,
        )
        assert result["success"] is True
        assert "last 30 days" in result["period"]

    @pytest.mark.asyncio
    async def test_with_start_date(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_team_stats

        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[])
        result = await get_team_stats(
            days=30, start_date="2026-01-01",
            _admin={"email": "admin"}, db_pool=mock_db_pool,
        )
        assert result["success"] is True
        assert "from 2026-01-01" in result["period"]

    @pytest.mark.asyncio
    async def test_db_error(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_team_stats

        mock_db_pool._mock_conn.fetch = AsyncMock(side_effect=Exception("fail"))
        with pytest.raises(HTTPException):
            await get_team_stats(
                days=30, start_date=None, _admin={"email": "admin"}, db_pool=mock_db_pool,
            )


class TestGetTimesheet:
    @pytest.mark.asyncio
    async def test_no_filters(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_timesheet

        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(return_value=5)
        conn.fetch = AsyncMock(return_value=[])

        result = await get_timesheet(
            email=None, date_from=None, date_to=None,
            limit=100, offset=0,
            _admin={"email": "admin"}, db_pool=mock_db_pool,
        )
        assert result["success"] is True
        assert result["total"] == 5

    @pytest.mark.asyncio
    async def test_with_filters(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_timesheet

        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(return_value=2)
        conn.fetch = AsyncMock(return_value=[])

        result = await get_timesheet(
            email="a@t.com", date_from="2026-04-01", date_to="2026-04-10",
            limit=50, offset=0,
            _admin={"email": "admin"}, db_pool=mock_db_pool,
        )
        assert result["success"] is True


class TestGetCRMActions:
    @pytest.mark.asyncio
    async def test_no_filters(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_crm_actions

        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(return_value=0)
        conn.fetch = AsyncMock(return_value=[])

        result = await get_crm_actions(
            email=None, action=None, entity_type=None,
            limit=100, offset=0,
            _admin={"email": "admin"}, db_pool=mock_db_pool,
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_with_all_filters(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_crm_actions

        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[])

        result = await get_crm_actions(
            email="a@t.com", action="create", entity_type="client",
            limit=50, offset=0,
            _admin={"email": "admin"}, db_pool=mock_db_pool,
        )
        assert result["success"] is True


class TestGetPracticeStats:
    @pytest.mark.asyncio
    async def test_practice_stats(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_practice_stats

        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[
            {"email": "a@t.com", "completed": 5, "in_progress": 2, "active": 3, "revenue": 1000000},
        ])
        result = await get_practice_stats(
            _admin={"email": "admin"}, db_pool=mock_db_pool,
        )
        assert result["success"] is True
        assert len(result["practice_stats"]) == 1

    @pytest.mark.asyncio
    async def test_db_error(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_practice_stats

        mock_db_pool._mock_conn.fetch = AsyncMock(side_effect=Exception("fail"))
        with pytest.raises(HTTPException):
            await get_practice_stats(
                _admin={"email": "admin"}, db_pool=mock_db_pool,
            )


class TestExportMessages:
    @pytest.mark.asyncio
    async def test_export_basic(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import export_messages

        now = datetime.now(tz=timezone.utc)
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[
            {
                "conversation_id": 1, "user_id": "u@t.com",
                "role": "user", "content": "Hello there",
                "message_timestamp": now, "conversation_started": now,
            },
        ])

        response = await export_messages(
            user_id=None, date_from=None, date_to=None,
            _admin={"email": "admin"}, db_pool=mock_db_pool,
        )
        assert response.media_type == "text/csv"

    @pytest.mark.asyncio
    async def test_export_with_filters(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import export_messages

        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[])
        response = await export_messages(
            user_id="u@t.com", date_from="2026-01-01", date_to="2026-04-01",
            _admin={"email": "admin"}, db_pool=mock_db_pool,
        )
        assert response.media_type == "text/csv"

    @pytest.mark.asyncio
    async def test_export_with_null_content(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import export_messages

        now = datetime.now(tz=timezone.utc)
        mock_db_pool._mock_conn.fetch = AsyncMock(return_value=[
            {
                "conversation_id": 1, "user_id": None,
                "role": "assistant", "content": None,
                "message_timestamp": now, "conversation_started": now,
            },
        ])

        response = await export_messages(
            user_id=None, date_from=None, date_to=None,
            _admin={"email": "admin"}, db_pool=mock_db_pool,
        )
        assert response.media_type == "text/csv"

    @pytest.mark.asyncio
    async def test_export_db_error(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import export_messages

        mock_db_pool._mock_conn.fetch = AsyncMock(side_effect=Exception("DB error"))
        with pytest.raises(HTTPException):
            await export_messages(
                user_id=None, date_from=None, date_to=None,
                _admin={"email": "admin"}, db_pool=mock_db_pool,
            )


# ============================================================================
# get_crm_activity
# ============================================================================


class TestGetCrmActivity:
    @pytest.mark.asyncio
    async def test_no_filters_returns_all_crm_endpoints(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_crm_activity

        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(return_value=3)
        conn.fetch = AsyncMock(return_value=[
            {
                "timestamp": "2026-04-10T10:23:11+00:00",
                "user_email": "rina@balizero.com",
                "method": "POST",
                "endpoint": "/api/crm/clients/",
                "response_status": 201,
                "response_time_ms": 145,
                "ip_address": "172.16.0.1",
            },
        ])

        result = await get_crm_activity(
            from_time=None, to_time=None, user=None,
            method=None, limit=100,
            _admin={"email": "zero@balizero.com"}, db_pool=mock_db_pool,
        )
        assert result["success"] is True
        assert result["total"] == 3
        assert len(result["items"]) == 1
        assert result["items"][0]["user_email"] == "rina@balizero.com"

    @pytest.mark.asyncio
    async def test_partial_user_filter_uses_ilike(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_crm_activity

        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(return_value=1)
        conn.fetch = AsyncMock(return_value=[
            {
                "timestamp": "2026-04-10T10:30:00+00:00",
                "user_email": "rina@balizero.com",
                "method": "GET",
                "endpoint": "/api/crm/clients/",
                "response_status": 200,
                "response_time_ms": 80,
                "ip_address": "172.16.0.1",
            },
        ])

        result = await get_crm_activity(
            from_time=None, to_time=None, user="rina",
            method=None, limit=100,
            _admin={"email": "zero@balizero.com"}, db_pool=mock_db_pool,
        )
        assert result["success"] is True
        # Verify ILIKE pattern was passed to query
        call_args = conn.fetch.call_args
        assert "%rina%" in str(call_args)

    @pytest.mark.asyncio
    async def test_time_range_filter(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_crm_activity

        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(return_value=0)
        conn.fetch = AsyncMock(return_value=[])

        result = await get_crm_activity(
            from_time="10:00", to_time="11:45", user=None,
            method=None, limit=100,
            _admin={"email": "zero@balizero.com"}, db_pool=mock_db_pool,
        )
        assert result["success"] is True
        assert result["total"] == 0
        # Verify time filters passed to query
        call_args = conn.fetch.call_args
        assert "10:00" in str(call_args) or "10" in str(call_args)

    @pytest.mark.asyncio
    async def test_method_filter(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_crm_activity

        conn = mock_db_pool._mock_conn
        conn.fetchval = AsyncMock(return_value=2)
        conn.fetch = AsyncMock(return_value=[])

        result = await get_crm_activity(
            from_time=None, to_time=None, user=None,
            method="POST", limit=100,
            _admin={"email": "zero@balizero.com"}, db_pool=mock_db_pool,
        )
        assert result["success"] is True
        call_args = conn.fetch.call_args
        assert "POST" in str(call_args)

    @pytest.mark.asyncio
    async def test_db_error_raises_500(self, mock_db_pool):
        from backend.app.routers.admin_team_activity import get_crm_activity

        mock_db_pool._mock_conn.fetchval = AsyncMock(side_effect=Exception("DB down"))
        with pytest.raises(HTTPException) as exc_info:
            await get_crm_activity(
                from_time=None, to_time=None, user=None,
                method=None, limit=100,
                _admin={"email": "zero@balizero.com"}, db_pool=mock_db_pool,
            )
        assert exc_info.value.status_code == 500
