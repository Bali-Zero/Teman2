"""
Unit tests for TeamTimesheetService
Target: >95% coverage
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.analytics.team_timesheet_service import TeamTimesheetService

BALI_TZ = ZoneInfo("Asia/Makassar")


@pytest.fixture
def mock_db_pool():
    """Mock database pool"""
    pool = AsyncMock()
    return pool


@pytest.fixture
def timesheet_service(mock_db_pool):
    """Create TeamTimesheetService instance"""
    return TeamTimesheetService(db_pool=mock_db_pool)


class TestTeamTimesheetService:
    """Tests for TeamTimesheetService"""

    def test_init(self, mock_db_pool):
        """Test initialization"""
        service = TeamTimesheetService(db_pool=mock_db_pool)
        assert service.pool == mock_db_pool
        assert service.running is False

    @pytest.mark.asyncio
    async def test_clock_in_success(self, timesheet_service, mock_db_pool):
        """Test clocking in successfully"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)  # Not already clocked in
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        # acquire() returns a context manager, not a coroutine
        mock_db_pool.acquire = MagicMock(return_value=mock_conn)
        result = await timesheet_service.clock_in("user1", "test@example.com")
        assert result["success"] is True
        assert result["action"] == "clock_in"

    @pytest.mark.asyncio
    async def test_clock_in_already_clocked_in(self, timesheet_service, mock_db_pool):
        """Test clocking in when already clocked in"""
        mock_conn = AsyncMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "is_online": True,
            "last_action_bali": datetime.now(BALI_TZ),
        }.get(key)
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        # acquire() returns a context manager, not a coroutine
        mock_db_pool.acquire = MagicMock(return_value=mock_conn)
        result = await timesheet_service.clock_in("user1", "test@example.com")
        assert result["success"] is False
        assert result["error"] == "already_clocked_in"

    @pytest.mark.asyncio
    async def test_clock_out_success(self, timesheet_service, mock_db_pool):
        """Test clocking out successfully"""
        mock_conn = AsyncMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "is_online": True,
            "last_action_bali": datetime.now(BALI_TZ),
        }.get(key)
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_conn.execute = AsyncMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        # acquire() returns a context manager, not a coroutine
        mock_db_pool.acquire = MagicMock(return_value=mock_conn)
        result = await timesheet_service.clock_out("user1", "test@example.com")
        assert result["success"] is True
        assert result["action"] == "clock_out"

    @pytest.mark.asyncio
    async def test_clock_out_not_clocked_in(self, timesheet_service, mock_db_pool):
        """Test clocking out when not clocked in"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        # acquire() returns a context manager, not a coroutine
        mock_db_pool.acquire = MagicMock(return_value=mock_conn)
        result = await timesheet_service.clock_out("user1", "test@example.com")
        assert result["success"] is False
        assert result["error"] == "not_clocked_in"

    @pytest.mark.asyncio
    async def test_start_auto_logout_monitor(self, timesheet_service):
        """Test starting auto-logout monitor"""
        await timesheet_service.start_auto_logout_monitor()
        assert timesheet_service.running is True
        assert timesheet_service.auto_logout_task is not None

    @pytest.mark.asyncio
    async def test_stop_auto_logout_monitor(self, timesheet_service):
        """Test stopping auto-logout monitor"""
        await timesheet_service.start_auto_logout_monitor()
        await timesheet_service.stop_auto_logout_monitor()
        assert timesheet_service.running is False
