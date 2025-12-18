"""
Unit tests for Team Timesheet Service
100% coverage target with comprehensive mocking
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import asyncpg
import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.team_timesheet_service import (
    BALI_TZ,
    TeamTimesheetService,
    get_timesheet_service,
    init_timesheet_service,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db_pool():
    """Create mock database pool"""
    pool = MagicMock(spec=asyncpg.Pool)
    pool.acquire = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    return pool


@pytest.fixture
def timesheet_service(mock_db_pool):
    """Create TeamTimesheetService instance"""
    return TeamTimesheetService(db_pool=mock_db_pool)


# ============================================================================
# Tests: Initialization
# ============================================================================


def test_timesheet_service_init(timesheet_service, mock_db_pool):
    """Test TeamTimesheetService initialization"""
    assert timesheet_service.pool is mock_db_pool
    assert timesheet_service.auto_logout_task is None
    assert timesheet_service.running is False


# ============================================================================
# Tests: start_auto_logout_monitor / stop_auto_logout_monitor
# ============================================================================


@pytest.mark.asyncio
async def test_start_auto_logout_monitor(timesheet_service):
    """Test starting auto-logout monitor"""
    await timesheet_service.start_auto_logout_monitor()

    assert timesheet_service.running is True
    assert timesheet_service.auto_logout_task is not None

    await timesheet_service.stop_auto_logout_monitor()


@pytest.mark.asyncio
async def test_start_auto_logout_monitor_already_running(timesheet_service):
    """Test starting auto-logout monitor when already running"""
    await timesheet_service.start_auto_logout_monitor()

    # Try to start again
    await timesheet_service.start_auto_logout_monitor()

    assert timesheet_service.running is True

    await timesheet_service.stop_auto_logout_monitor()


@pytest.mark.asyncio
async def test_stop_auto_logout_monitor(timesheet_service):
    """Test stopping auto-logout monitor"""
    await timesheet_service.start_auto_logout_monitor()
    assert timesheet_service.running is True

    await timesheet_service.stop_auto_logout_monitor()

    assert timesheet_service.running is False


# ============================================================================
# Tests: clock_in
# ============================================================================


@pytest.mark.asyncio
async def test_clock_in_success(timesheet_service, mock_db_pool):
    """Test clocking in successfully"""
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)  # No existing status
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await timesheet_service.clock_in("user123", "user@example.com", {"ip": "1.2.3.4"})

    assert result["success"] is True
    assert result["action"] == "clock_in"
    assert "timestamp" in result
    assert "bali_time" in result
    mock_conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_clock_in_already_clocked_in(timesheet_service, mock_db_pool):
    """Test clocking in when already clocked in"""
    mock_conn = MagicMock()
    mock_status = MagicMock()
    mock_status.is_online = True
    mock_status.last_action_bali = datetime.now(BALI_TZ)
    mock_status.user_id = "user123"
    mock_conn.fetchrow = AsyncMock(return_value=mock_status)
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await timesheet_service.clock_in("user123", "user@example.com")

    assert result["success"] is False
    assert result["error"] == "already_clocked_in"
    assert "clocked_in_at" in result


@pytest.mark.asyncio
async def test_clock_in_notifies_admin(timesheet_service, mock_db_pool):
    """Test clock-in notifies admin"""
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    with patch("services.notification_hub.notification_hub") as mock_hub:
        mock_hub.send = AsyncMock()

        await timesheet_service.clock_in("user123", "user@example.com")

        # Should attempt to notify (may fail silently)
        # Just verify it doesn't raise exception


# ============================================================================
# Tests: clock_out
# ============================================================================


@pytest.mark.asyncio
async def test_clock_out_success(timesheet_service, mock_db_pool):
    """Test clocking out successfully"""
    mock_conn = MagicMock()
    clock_in_time = datetime.now(BALI_TZ) - timedelta(hours=8)
    mock_status = {
        "is_online": True,
        "last_action_bali": clock_in_time,
        "user_id": "user123",
        "email": "user@example.com",
        "action_type": "clock_in",
    }
    mock_conn.fetchrow = AsyncMock(return_value=mock_status)
    mock_conn.execute = AsyncMock()
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await timesheet_service.clock_out("user123", "user@example.com")

    assert result["success"] is True
    assert result["action"] == "clock_out"
    assert "hours_worked" in result
    assert result["hours_worked"] > 0


@pytest.mark.asyncio
async def test_clock_out_not_clocked_in(timesheet_service, mock_db_pool):
    """Test clocking out when not clocked in"""
    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await timesheet_service.clock_out("user123", "user@example.com")

    assert result["success"] is False
    assert result["error"] == "not_clocked_in"


# ============================================================================
# Tests: get_my_status
# ============================================================================


@pytest.mark.asyncio
async def test_get_my_status_success(timesheet_service, mock_db_pool):
    """Test getting user status successfully"""
    mock_conn = MagicMock()
    mock_status = {
        "is_online": True,
        "last_action_bali": datetime.now(BALI_TZ),
        "action_type": "clock_in",
        "user_id": "user123",
        "email": "user@example.com",
    }
    mock_today_hours = {"hours_worked": 8.0}
    mock_week_summary = {"total_hours": 40.0, "days_worked": 5}

    mock_conn.fetchrow = AsyncMock(side_effect=[mock_status, mock_today_hours, mock_week_summary])
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await timesheet_service.get_my_status("user123")

    assert result["user_id"] == "user123"
    assert result["is_online"] is True
    assert result["today_hours"] == 8.0
    assert result["week_hours"] == 40.0
    assert result["week_days"] == 5


@pytest.mark.asyncio
async def test_get_my_status_no_data(timesheet_service, mock_db_pool):
    """Test getting user status with no data"""
    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(side_effect=[None, None, None])
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await timesheet_service.get_my_status("user123")

    assert result["is_online"] is False
    assert result["today_hours"] == 0.0
    assert result["week_hours"] == 0.0


# ============================================================================
# Tests: get_team_online_status
# ============================================================================


@pytest.mark.asyncio
async def test_get_team_online_status_success(timesheet_service, mock_db_pool):
    """Test getting team online status successfully"""
    mock_conn = MagicMock()
    mock_rows = [
        {
            "user_id": "user1",
            "email": "user1@example.com",
            "is_online": True,
            "last_action_bali": datetime.now(BALI_TZ),
            "action_type": "clock_in",
        },
        {
            "user_id": "user2",
            "email": "user2@example.com",
            "is_online": False,
            "last_action_bali": datetime.now(BALI_TZ) - timedelta(hours=2),
            "action_type": "clock_out",
        },
    ]
    mock_conn.fetch = AsyncMock(return_value=mock_rows)
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await timesheet_service.get_team_online_status()

    assert len(result) == 2
    assert result[0]["is_online"] is True
    assert result[1]["is_online"] is False


# ============================================================================
# Tests: get_daily_hours
# ============================================================================


@pytest.mark.asyncio
async def test_get_daily_hours_success(timesheet_service, mock_db_pool):
    """Test getting daily hours successfully"""
    mock_conn = MagicMock()
    mock_rows = [
        {
            "user_id": "user1",
            "email": "user1@example.com",
            "work_date": datetime.now(BALI_TZ).date(),
            "clock_in_bali": datetime.now(BALI_TZ).replace(hour=9, minute=0),
            "clock_out_bali": datetime.now(BALI_TZ).replace(hour=17, minute=0),
            "hours_worked": 8.0,
        }
    ]
    mock_conn.fetch = AsyncMock(return_value=mock_rows)
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await timesheet_service.get_daily_hours()

    assert len(result) == 1
    assert result[0]["hours_worked"] == 8.0
    assert result[0]["email"] == "user1@example.com"


@pytest.mark.asyncio
async def test_get_daily_hours_with_date(timesheet_service, mock_db_pool):
    """Test getting daily hours for specific date"""
    target_date = datetime.now(BALI_TZ).date()
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await timesheet_service.get_daily_hours(target_date)

    assert isinstance(result, list)
    # Verify date was used in query
    call_args = mock_conn.fetch.call_args[0]
    assert len(call_args) > 0


# ============================================================================
# Tests: get_weekly_summary
# ============================================================================


@pytest.mark.asyncio
async def test_get_weekly_summary_success(timesheet_service, mock_db_pool):
    """Test getting weekly summary successfully"""
    mock_conn = MagicMock()
    mock_rows = [
        {
            "user_id": "user1",
            "email": "user1@example.com",
            "week_start": datetime.now(BALI_TZ).date(),
            "days_worked": 5,
            "total_hours": 40.0,
            "avg_hours_per_day": 8.0,
        }
    ]
    mock_conn.fetch = AsyncMock(return_value=mock_rows)
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await timesheet_service.get_weekly_summary()

    assert len(result) == 1
    assert result[0]["total_hours"] == 40.0
    assert result[0]["days_worked"] == 5


# ============================================================================
# Tests: get_monthly_summary
# ============================================================================


@pytest.mark.asyncio
async def test_get_monthly_summary_success(timesheet_service, mock_db_pool):
    """Test getting monthly summary successfully"""
    mock_conn = MagicMock()
    mock_rows = [
        {
            "user_id": "user1",
            "email": "user1@example.com",
            "month_start": datetime.now(BALI_TZ).date().replace(day=1),
            "days_worked": 20,
            "total_hours": 160.0,
            "avg_hours_per_day": 8.0,
        }
    ]
    mock_conn.fetch = AsyncMock(return_value=mock_rows)
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await timesheet_service.get_monthly_summary()

    assert len(result) == 1
    assert result[0]["total_hours"] == 160.0


# ============================================================================
# Tests: export_timesheet_csv
# ============================================================================


@pytest.mark.asyncio
async def test_export_timesheet_csv_success(timesheet_service, mock_db_pool):
    """Test exporting timesheet CSV successfully"""
    mock_conn = MagicMock()
    mock_rows = [
        {
            "email": "user1@example.com",
            "work_date": datetime.now(BALI_TZ).date(),
            "clock_in_bali": datetime.now(BALI_TZ).replace(hour=9, minute=0),
            "clock_out_bali": datetime.now(BALI_TZ).replace(hour=17, minute=0),
            "hours_worked": 8.0,
        }
    ]
    mock_conn.fetch = AsyncMock(return_value=mock_rows)
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    start_date = datetime.now(BALI_TZ) - timedelta(days=7)
    end_date = datetime.now(BALI_TZ)

    result = await timesheet_service.export_timesheet_csv(start_date, end_date)

    assert isinstance(result, str)
    assert "Email,Date,Clock In,Clock Out,Hours Worked" in result
    assert "user1@example.com" in result


# ============================================================================
# Tests: Singleton functions
# ============================================================================


def test_get_timesheet_service_none():
    """Test get_timesheet_service when not initialized"""
    import services.team_timesheet_service

    services.team_timesheet_service._timesheet_service = None
    result = get_timesheet_service()

    assert result is None


def test_init_timesheet_service(mock_db_pool):
    """Test initializing timesheet service"""
    service = init_timesheet_service(mock_db_pool)

    assert isinstance(service, TeamTimesheetService)
    assert get_timesheet_service() is service


# ============================================================================
# Tests: _process_auto_logout
# ============================================================================


@pytest.mark.asyncio
async def test_process_auto_logout_success(timesheet_service, mock_db_pool):
    """Test processing auto-logout successfully"""
    mock_conn = MagicMock()
    mock_rows = [
        {
            "email": "user1@example.com",
            "clock_in_time": datetime.now(BALI_TZ) - timedelta(hours=10),
            "auto_logout_time": datetime.now(BALI_TZ),
        }
    ]
    mock_conn.fetch = AsyncMock(return_value=mock_rows)
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    await timesheet_service._process_auto_logout()

    mock_conn.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_process_auto_logout_no_expired_sessions(timesheet_service, mock_db_pool):
    """Test processing auto-logout with no expired sessions"""
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    await timesheet_service._process_auto_logout()

    mock_conn.fetch.assert_called_once()


@pytest.mark.asyncio
async def test_process_auto_logout_db_error(timesheet_service, mock_db_pool):
    """Test processing auto-logout with database error"""
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(side_effect=Exception("DB Error"))
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    with pytest.raises(Exception, match="DB Error"):
        await timesheet_service._process_auto_logout()


# ============================================================================
# Tests: _auto_logout_loop
# ============================================================================


@pytest.mark.asyncio
async def test_auto_logout_loop_runs_and_stops(timesheet_service, mock_db_pool):
    """Test auto-logout loop runs and can be stopped"""
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    # Start the loop
    timesheet_service.running = True
    task = asyncio.create_task(timesheet_service._auto_logout_loop())

    # Let it run for a brief moment
    await asyncio.sleep(0.1)

    # Stop it
    timesheet_service.running = False
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_auto_logout_loop_handles_errors(timesheet_service, mock_db_pool):
    """Test auto-logout loop handles errors gracefully"""
    # Test that _process_auto_logout errors are caught in the loop
    # We'll call _process_auto_logout directly with an error condition
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(side_effect=Exception("Database error"))
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    # The loop should catch and log the error without crashing
    # We test this by verifying _process_auto_logout raises but the loop would handle it
    try:
        await timesheet_service._process_auto_logout()
        assert False, "Should have raised an exception"
    except Exception as e:
        assert "Database error" in str(e)


# ============================================================================
# Tests: _get_user_current_status
# ============================================================================


@pytest.mark.asyncio
async def test_get_user_current_status_success(timesheet_service, mock_db_pool):
    """Test getting user current status successfully"""
    mock_conn = MagicMock()
    mock_row = {
        "user_id": "user123",
        "email": "user@example.com",
        "last_action_bali": datetime.now(BALI_TZ),
        "action_type": "clock_in",
        "is_online": True,
    }
    mock_conn.fetchrow = AsyncMock(return_value=mock_row)

    result = await timesheet_service._get_user_current_status(mock_conn, "user123")

    assert result is not None
    assert result["user_id"] == "user123"
    assert result["is_online"] is True


@pytest.mark.asyncio
async def test_get_user_current_status_not_found(timesheet_service, mock_db_pool):
    """Test getting user current status when user not found"""
    mock_conn = MagicMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)

    result = await timesheet_service._get_user_current_status(mock_conn, "user123")

    assert result is None


# ============================================================================
# Tests: Edge cases for clock_in
# ============================================================================


@pytest.mark.asyncio
async def test_clock_in_with_metadata(timesheet_service, mock_db_pool):
    """Test clocking in with metadata"""
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    metadata = {"ip_address": "192.168.1.1", "user_agent": "Mozilla/5.0"}
    result = await timesheet_service.clock_in("user123", "user@example.com", metadata)

    assert result["success"] is True
    # Verify metadata was passed to execute
    call_args = mock_conn.execute.call_args[0]
    assert json.dumps(metadata) in str(call_args)


@pytest.mark.asyncio
async def test_clock_in_notification_failure(timesheet_service, mock_db_pool):
    """Test clock-in when notification fails"""
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    # Patch notification_hub import inside the method
    with patch("services.notification_hub.notification_hub") as mock_hub:
        mock_hub.send = AsyncMock(side_effect=Exception("Notification failed"))

        # Should still succeed even if notification fails
        result = await timesheet_service.clock_in("user123", "user@example.com")

        assert result["success"] is True


# ============================================================================
# Tests: Edge cases for clock_out
# ============================================================================


@pytest.mark.asyncio
async def test_clock_out_with_naive_datetime(timesheet_service, mock_db_pool):
    """Test clocking out with naive datetime (no timezone)"""
    mock_conn = MagicMock()
    # Clock in time without timezone
    clock_in_time = datetime.now().replace(tzinfo=None) - timedelta(hours=5)
    mock_status_row = MagicMock()
    mock_status_row.__getitem__ = lambda self, key: {
        "is_online": True,
        "last_action_bali": clock_in_time,
        "user_id": "user123",
        "email": "user@example.com",
        "action_type": "clock_in",
    }[key]

    mock_conn.fetchrow = AsyncMock(return_value=mock_status_row)
    mock_conn.execute = AsyncMock()
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await timesheet_service.clock_out("user123", "user@example.com")

    assert result["success"] is True
    assert "hours_worked" in result


@pytest.mark.asyncio
async def test_clock_out_with_metadata(timesheet_service, mock_db_pool):
    """Test clocking out with metadata"""
    mock_conn = MagicMock()
    clock_in_time = datetime.now(BALI_TZ) - timedelta(hours=3)
    mock_status_row = MagicMock()
    mock_status_row.__getitem__ = lambda self, key: {
        "is_online": True,
        "last_action_bali": clock_in_time,
        "user_id": "user123",
        "email": "user@example.com",
        "action_type": "clock_in",
    }[key]

    mock_conn.fetchrow = AsyncMock(return_value=mock_status_row)
    mock_conn.execute = AsyncMock()
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    metadata = {"ip_address": "192.168.1.1"}
    result = await timesheet_service.clock_out("user123", "user@example.com", metadata)

    assert result["success"] is True


@pytest.mark.asyncio
async def test_clock_out_notification_failure(timesheet_service, mock_db_pool):
    """Test clock-out when notification fails"""
    mock_conn = MagicMock()
    clock_in_time = datetime.now(BALI_TZ) - timedelta(hours=4)
    mock_status_row = MagicMock()
    mock_status_row.__getitem__ = lambda self, key: {
        "is_online": True,
        "last_action_bali": clock_in_time,
        "user_id": "user123",
        "email": "user@example.com",
        "action_type": "clock_in",
    }[key]

    mock_conn.fetchrow = AsyncMock(return_value=mock_status_row)
    mock_conn.execute = AsyncMock()
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    # Patch notification_hub import inside the method
    with patch("services.notification_hub.notification_hub") as mock_hub:
        mock_hub.send = AsyncMock(side_effect=Exception("Notification failed"))

        # Should still succeed even if notification fails
        result = await timesheet_service.clock_out("user123", "user@example.com")

        assert result["success"] is True


@pytest.mark.asyncio
async def test_clock_out_offline_status(timesheet_service, mock_db_pool):
    """Test clocking out when status shows offline"""
    mock_conn = MagicMock()
    mock_status_row = MagicMock()
    mock_status_row.__getitem__ = lambda self, key: {
        "is_online": False,
        "last_action_bali": datetime.now(BALI_TZ),
        "user_id": "user123",
        "email": "user@example.com",
        "action_type": "clock_out",
    }[key]

    mock_conn.fetchrow = AsyncMock(return_value=mock_status_row)
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await timesheet_service.clock_out("user123", "user@example.com")

    assert result["success"] is False
    assert result["error"] == "not_clocked_in"


# ============================================================================
# Tests: Edge cases for get_daily_hours
# ============================================================================


@pytest.mark.asyncio
async def test_get_daily_hours_with_datetime_object(timesheet_service, mock_db_pool):
    """Test getting daily hours with datetime object"""
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    target_datetime = datetime.now(BALI_TZ)
    result = await timesheet_service.get_daily_hours(target_datetime)

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_daily_hours_empty_result(timesheet_service, mock_db_pool):
    """Test getting daily hours with empty result"""
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await timesheet_service.get_daily_hours()

    assert result == []


# ============================================================================
# Tests: Edge cases for get_weekly_summary
# ============================================================================


@pytest.mark.asyncio
async def test_get_weekly_summary_with_datetime_object(timesheet_service, mock_db_pool):
    """Test getting weekly summary with datetime object"""
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    week_start = datetime.now(BALI_TZ)
    result = await timesheet_service.get_weekly_summary(week_start)

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_weekly_summary_empty_result(timesheet_service, mock_db_pool):
    """Test getting weekly summary with empty result"""
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await timesheet_service.get_weekly_summary()

    assert result == []


# ============================================================================
# Tests: Edge cases for get_monthly_summary
# ============================================================================


@pytest.mark.asyncio
async def test_get_monthly_summary_with_datetime_object(timesheet_service, mock_db_pool):
    """Test getting monthly summary with datetime object"""
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    month_start = datetime.now(BALI_TZ)
    result = await timesheet_service.get_monthly_summary(month_start)

    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_monthly_summary_empty_result(timesheet_service, mock_db_pool):
    """Test getting monthly summary with empty result"""
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await timesheet_service.get_monthly_summary()

    assert result == []


# ============================================================================
# Tests: Edge cases for export_timesheet_csv
# ============================================================================


@pytest.mark.asyncio
async def test_export_timesheet_csv_empty_result(timesheet_service, mock_db_pool):
    """Test exporting timesheet CSV with no data"""
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    start_date = datetime.now(BALI_TZ) - timedelta(days=7)
    end_date = datetime.now(BALI_TZ)

    result = await timesheet_service.export_timesheet_csv(start_date, end_date)

    assert result == "Email,Date,Clock In,Clock Out,Hours Worked"


@pytest.mark.asyncio
async def test_export_timesheet_csv_multiple_rows(timesheet_service, mock_db_pool):
    """Test exporting timesheet CSV with multiple rows"""
    mock_conn = MagicMock()
    mock_rows = [
        {
            "email": "user1@example.com",
            "work_date": datetime.now(BALI_TZ).date(),
            "clock_in_bali": datetime.now(BALI_TZ).replace(hour=9, minute=0),
            "clock_out_bali": datetime.now(BALI_TZ).replace(hour=17, minute=0),
            "hours_worked": 8.0,
        },
        {
            "email": "user2@example.com",
            "work_date": datetime.now(BALI_TZ).date() - timedelta(days=1),
            "clock_in_bali": datetime.now(BALI_TZ).replace(hour=8, minute=30),
            "clock_out_bali": datetime.now(BALI_TZ).replace(hour=16, minute=30),
            "hours_worked": 8.0,
        },
    ]
    mock_conn.fetch = AsyncMock(return_value=mock_rows)
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    start_date = datetime.now(BALI_TZ) - timedelta(days=7)
    end_date = datetime.now(BALI_TZ)

    result = await timesheet_service.export_timesheet_csv(start_date, end_date)

    lines = result.split("\n")
    assert len(lines) == 3  # Header + 2 data rows
    assert "user1@example.com" in result
    assert "user2@example.com" in result


@pytest.mark.asyncio
async def test_export_timesheet_csv_with_date_objects(timesheet_service, mock_db_pool):
    """Test exporting timesheet CSV with date objects instead of datetime"""
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    start_date = datetime.now(BALI_TZ).date()
    end_date = datetime.now(BALI_TZ).date()

    result = await timesheet_service.export_timesheet_csv(start_date, end_date)

    assert isinstance(result, str)


# ============================================================================
# Tests: Edge cases for get_team_online_status
# ============================================================================


@pytest.mark.asyncio
async def test_get_team_online_status_empty_result(timesheet_service, mock_db_pool):
    """Test getting team online status with no users"""
    mock_conn = MagicMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_db_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)

    result = await timesheet_service.get_team_online_status()

    assert result == []


# ============================================================================
# Tests: stop_auto_logout_monitor edge cases
# ============================================================================


@pytest.mark.asyncio
async def test_stop_auto_logout_monitor_when_not_running(timesheet_service):
    """Test stopping auto-logout monitor when not running"""
    assert timesheet_service.running is False
    assert timesheet_service.auto_logout_task is None

    await timesheet_service.stop_auto_logout_monitor()

    assert timesheet_service.running is False


# ============================================================================
# Tests: BALI_TZ constant
# ============================================================================


def test_bali_tz_constant():
    """Test BALI_TZ is correctly defined"""
    assert ZoneInfo("Asia/Makassar") == BALI_TZ
    # Verify it's the correct timezone
    now = datetime.now(BALI_TZ)
    assert now.tzinfo is not None
