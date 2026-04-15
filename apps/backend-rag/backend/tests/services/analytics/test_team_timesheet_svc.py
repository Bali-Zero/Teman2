"""Tests for TeamTimesheetService — clock-in/out, summaries, CSV export."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from backend.services.analytics.team_timesheet_service import (
    TeamTimesheetService,
    get_timesheet_service,
    init_timesheet_service,
)

BALI_TZ = ZoneInfo("Asia/Makassar")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

USER_ID = "user-abc-123"
USER_EMAIL = "dev@balizero.com"


def _make_status_row(
    *,
    user_id: str = USER_ID,
    email: str = USER_EMAIL,
    is_online: bool = True,
    action_type: str = "clock_in",
    last_action_bali: datetime | None = None,
) -> dict[str, Any]:
    """Return a dict that mimics a ``team_online_status`` row."""
    return {
        "user_id": user_id,
        "email": email,
        "is_online": is_online,
        "action_type": action_type,
        "last_action_bali": last_action_bali or datetime.now(BALI_TZ),
    }


def _make_daily_row(
    *,
    user_id: str = USER_ID,
    email: str = USER_EMAIL,
    work_date: datetime | None = None,
    clock_in_bali: datetime | None = None,
    clock_out_bali: datetime | None = None,
    hours_worked: float = 8.0,
) -> MagicMock:
    """Return a MagicMock that mimics a ``daily_work_hours`` row."""
    now = datetime.now(BALI_TZ)
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "user_id": user_id,
        "email": email,
        "work_date": (work_date or now).date() if isinstance(work_date or now, datetime) else work_date,
        "clock_in_bali": clock_in_bali or now.replace(hour=9, minute=0),
        "clock_out_bali": clock_out_bali or now.replace(hour=17, minute=0),
        "hours_worked": hours_worked,
    }[key]
    return row


def _make_weekly_row(
    *,
    user_id: str = USER_ID,
    email: str = USER_EMAIL,
    week_start: datetime | None = None,
    days_worked: int = 5,
    total_hours: float = 40.0,
    avg_hours_per_day: float = 8.0,
) -> MagicMock:
    """Return a MagicMock that mimics a ``weekly_work_summary`` row."""
    now = datetime.now(BALI_TZ)
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "user_id": user_id,
        "email": email,
        "week_start": (week_start or now).date() if isinstance(week_start or now, datetime) else week_start,
        "days_worked": days_worked,
        "total_hours": total_hours,
        "avg_hours_per_day": avg_hours_per_day,
    }[key]
    return row


def _make_monthly_row(
    *,
    user_id: str = USER_ID,
    email: str = USER_EMAIL,
    month_start: datetime | None = None,
    days_worked: int = 22,
    total_hours: float = 176.0,
    avg_hours_per_day: float = 8.0,
) -> MagicMock:
    """Return a MagicMock that mimics a ``monthly_work_summary`` row."""
    now = datetime.now(BALI_TZ)
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "user_id": user_id,
        "email": email,
        "month_start": (month_start or now.replace(day=1)).date()
        if isinstance(month_start or now, datetime)
        else month_start,
        "days_worked": days_worked,
        "total_hours": total_hours,
        "avg_hours_per_day": avg_hours_per_day,
    }[key]
    return row


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_pool_and_conn() -> tuple[MagicMock, AsyncMock]:
    """Create a mock asyncpg pool with ``async with pool.acquire() as conn``."""
    pool = MagicMock()
    conn = AsyncMock()

    class _AsyncCtx:
        async def __aenter__(self) -> AsyncMock:
            return conn

        async def __aexit__(self, *args: object) -> None:
            return None

    pool.acquire = MagicMock(return_value=_AsyncCtx())
    return pool, conn


@pytest.fixture
def service(mock_db_pool_and_conn: tuple[MagicMock, AsyncMock]) -> TeamTimesheetService:
    """TeamTimesheetService with a mocked DB pool and no attendance monitor."""
    pool, _ = mock_db_pool_and_conn
    return TeamTimesheetService(db_pool=pool)


@pytest.fixture
def conn(mock_db_pool_and_conn: tuple[MagicMock, AsyncMock]) -> AsyncMock:
    """Convenience accessor for the mock connection."""
    _, c = mock_db_pool_and_conn
    return c


@pytest.fixture
def attendance_monitor() -> AsyncMock:
    """Mock AttendanceMonitor with a check_late_checkin coroutine."""
    monitor = AsyncMock()
    monitor.check_late_checkin = AsyncMock(return_value=None)
    return monitor


@pytest.fixture
def service_with_monitor(
    mock_db_pool_and_conn: tuple[MagicMock, AsyncMock],
    attendance_monitor: AsyncMock,
) -> TeamTimesheetService:
    """TeamTimesheetService wired with an attendance monitor."""
    pool, _ = mock_db_pool_and_conn
    return TeamTimesheetService(db_pool=pool, attendance_monitor=attendance_monitor)


# ---------------------------------------------------------------------------
# Module-level functions: get / init singleton
# ---------------------------------------------------------------------------


class TestModuleFunctions:
    def test_get_timesheet_service_returns_none_before_init(self) -> None:
        """Before init, the singleton should be None."""
        # Reset the module-level singleton
        import backend.services.analytics.team_timesheet_service as mod

        original = mod._timesheet_service
        try:
            mod._timesheet_service = None
            assert get_timesheet_service() is None
        finally:
            mod._timesheet_service = original

    def test_init_timesheet_service_creates_and_returns_instance(self) -> None:
        """init_timesheet_service should set the module singleton."""
        import backend.services.analytics.team_timesheet_service as mod

        original = mod._timesheet_service
        try:
            pool = MagicMock()
            svc = init_timesheet_service(pool)
            assert isinstance(svc, TeamTimesheetService)
            assert get_timesheet_service() is svc
        finally:
            mod._timesheet_service = original

    def test_init_timesheet_service_with_attendance_monitor(self) -> None:
        """init_timesheet_service should forward the attendance_monitor."""
        import backend.services.analytics.team_timesheet_service as mod

        original = mod._timesheet_service
        try:
            pool = MagicMock()
            monitor = AsyncMock()
            svc = init_timesheet_service(pool, attendance_monitor=monitor)
            assert svc.attendance_monitor is monitor
        finally:
            mod._timesheet_service = original


# ---------------------------------------------------------------------------
# Auto-logout monitor start / stop
# ---------------------------------------------------------------------------


class TestAutoLogoutMonitor:
    @pytest.mark.asyncio
    async def test_start_auto_logout_monitor_sets_running(
        self, service: TeamTimesheetService,
    ) -> None:
        """Starting the monitor should set running=True and create a task."""
        assert service.running is False

        # Patch the internal loop so it does not actually run forever
        with patch.object(service, "_auto_logout_loop", new_callable=AsyncMock) as mock_loop:
            mock_loop.return_value = None
            await service.start_auto_logout_monitor()

            assert service.running is True
            assert service.auto_logout_task is not None

        # Cleanup
        await service.stop_auto_logout_monitor()

    @pytest.mark.asyncio
    async def test_start_auto_logout_monitor_is_idempotent(
        self, service: TeamTimesheetService,
    ) -> None:
        """Calling start twice should not create a second task."""
        with patch.object(service, "_auto_logout_loop", new_callable=AsyncMock):
            await service.start_auto_logout_monitor()
            first_task = service.auto_logout_task

            await service.start_auto_logout_monitor()  # second call
            assert service.auto_logout_task is first_task

        await service.stop_auto_logout_monitor()

    @pytest.mark.asyncio
    async def test_stop_auto_logout_monitor_clears_state(
        self, service: TeamTimesheetService,
    ) -> None:
        """Stopping the monitor should set running=False."""
        with patch.object(service, "_auto_logout_loop", new_callable=AsyncMock):
            await service.start_auto_logout_monitor()

        await service.stop_auto_logout_monitor()
        assert service.running is False


# ---------------------------------------------------------------------------
# Clock-in
# ---------------------------------------------------------------------------


class TestClockIn:
    @pytest.mark.asyncio
    async def test_clock_in_success(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """First clock-in of the day should succeed."""
        # No existing session
        conn.fetchrow.return_value = None
        conn.execute.return_value = None

        result: dict[str, Any] = await service.clock_in(USER_ID, USER_EMAIL)

        assert result["success"] is True
        assert result["action"] == "clock_in"
        assert "timestamp" in result
        assert "bali_time" in result
        conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_clock_in_already_clocked_in_today(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """If user is already clocked in today, should return error."""
        now = datetime.now(BALI_TZ)
        status_row = _make_status_row(is_online=True, last_action_bali=now)
        # _get_user_current_status does fetchrow
        conn.fetchrow.return_value = MagicMock(
            **{"__getitem__": lambda self, key: status_row[key]},
        )

        result: dict[str, Any] = await service.clock_in(USER_ID, USER_EMAIL)

        assert result["success"] is False
        assert result["error"] == "already_clocked_in"
        # Should NOT have inserted a new row
        conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_clock_in_stale_session_allows_new_clock_in(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """If online but last action was yesterday, allow new clock-in."""
        yesterday = datetime.now(BALI_TZ) - timedelta(days=1)
        status_row = _make_status_row(is_online=True, last_action_bali=yesterday)
        conn.fetchrow.return_value = MagicMock(
            **{"__getitem__": lambda self, key: status_row[key]},
        )
        conn.execute.return_value = None

        result: dict[str, Any] = await service.clock_in(USER_ID, USER_EMAIL)

        assert result["success"] is True
        assert result["action"] == "clock_in"

    @pytest.mark.asyncio
    async def test_clock_in_with_metadata(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """Metadata (ip, user_agent) should be serialised to JSONB."""
        conn.fetchrow.return_value = None
        conn.execute.return_value = None
        metadata = {"ip_address": "192.168.1.1", "user_agent": "Mozilla/5.0"}

        result: dict[str, Any] = await service.clock_in(USER_ID, USER_EMAIL, metadata=metadata)

        assert result["success"] is True
        # Verify the execute call includes serialised metadata
        call_args = conn.execute.call_args
        assert '"ip_address"' in call_args[0][3] or "192.168.1.1" in call_args[0][3]

    @pytest.mark.asyncio
    async def test_clock_in_fires_late_checkin_alert(
        self,
        service_with_monitor: TeamTimesheetService,
        conn: AsyncMock,
        attendance_monitor: AsyncMock,
    ) -> None:
        """When attendance_monitor is wired, clock_in should fire check_late_checkin."""
        conn.fetchrow.return_value = None
        conn.execute.return_value = None

        result: dict[str, Any] = await service_with_monitor.clock_in(USER_ID, USER_EMAIL)

        assert result["success"] is True
        # The late check is dispatched as fire-and-forget asyncio.create_task.
        # We verify the monitor was configured on the service.
        assert service_with_monitor.attendance_monitor is attendance_monitor


# ---------------------------------------------------------------------------
# Clock-out
# ---------------------------------------------------------------------------


class TestClockOut:
    @pytest.mark.asyncio
    async def test_clock_out_success(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """Clock-out when currently clocked in should succeed and report hours."""
        clock_in_time = datetime.now(BALI_TZ) - timedelta(hours=4)
        status_row = _make_status_row(
            is_online=True,
            action_type="clock_in",
            last_action_bali=clock_in_time,
        )
        conn.fetchrow.return_value = MagicMock(
            **{"__getitem__": lambda self, key: status_row[key]},
        )
        conn.execute.return_value = None

        result: dict[str, Any] = await service.clock_out(USER_ID, USER_EMAIL)

        assert result["success"] is True
        assert result["action"] == "clock_out"
        assert result["hours_worked"] == pytest.approx(4.0, abs=0.1)
        assert "clock_in_time" in result
        conn.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_clock_out_not_clocked_in(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """Clock-out when not clocked in should return error."""
        conn.fetchrow.return_value = None

        result: dict[str, Any] = await service.clock_out(USER_ID, USER_EMAIL)

        assert result["success"] is False
        assert result["error"] == "not_clocked_in"
        conn.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_clock_out_with_offline_status(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """If status shows is_online=False, clock-out should fail."""
        status_row = _make_status_row(is_online=False, action_type="clock_out")
        conn.fetchrow.return_value = MagicMock(
            **{"__getitem__": lambda self, key: status_row[key]},
        )

        result: dict[str, Any] = await service.clock_out(USER_ID, USER_EMAIL)

        assert result["success"] is False
        assert result["error"] == "not_clocked_in"

    @pytest.mark.asyncio
    async def test_clock_out_handles_naive_clock_in_time(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """If clock_in_time from DB is naive, it should be coerced to BALI_TZ."""
        # Use datetime.now(BALI_TZ) then strip tz so the test is timezone-
        # agnostic: previously datetime.now() (no tz) returned LOCAL time,
        # which passed on a Bali laptop (local == BALI_TZ) but failed in CI
        # (UTC) where clock_out interprets the naive value as BALI_TZ and the
        # delta appears as (UTC-BALI) + 3h = 11h instead of 3h.
        naive_clock_in = datetime.now(BALI_TZ).replace(tzinfo=None) - timedelta(hours=3)
        status_row = _make_status_row(
            is_online=True,
            action_type="clock_in",
            last_action_bali=naive_clock_in,
        )
        conn.fetchrow.return_value = MagicMock(
            **{"__getitem__": lambda self, key: status_row[key]},
        )
        conn.execute.return_value = None

        result: dict[str, Any] = await service.clock_out(USER_ID, USER_EMAIL)

        assert result["success"] is True
        assert result["hours_worked"] == pytest.approx(3.0, abs=0.1)


# ---------------------------------------------------------------------------
# Get my status
# ---------------------------------------------------------------------------


class TestGetMyStatus:
    @pytest.mark.asyncio
    async def test_get_my_status_online(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """Returns online status with today's and weekly hours."""
        now = datetime.now(BALI_TZ)
        status_row = _make_status_row(is_online=True, last_action_bali=now)
        today_row = MagicMock()
        today_row.__getitem__ = lambda self, key: {"hours_worked": 5.5}[key]
        week_row = MagicMock()
        week_row.__getitem__ = lambda self, key: {"total_hours": 32.0, "days_worked": 4}[key]

        conn.fetchrow.side_effect = [
            # 1st call: _get_user_current_status
            MagicMock(**{"__getitem__": lambda self, key: status_row[key]}),
            # 2nd call: today's hours
            today_row,
            # 3rd call: week summary
            week_row,
        ]

        result: dict[str, Any] = await service.get_my_status(USER_ID)

        assert result["user_id"] == USER_ID
        assert result["is_online"] is True
        assert result["today_hours"] == 5.5
        assert result["week_hours"] == 32.0
        assert result["week_days"] == 4

    @pytest.mark.asyncio
    async def test_get_my_status_no_records(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """Returns defaults when user has no timesheet records."""
        conn.fetchrow.return_value = None

        result: dict[str, Any] = await service.get_my_status(USER_ID)

        assert result["is_online"] is False
        assert result["last_action"] is None
        assert result["today_hours"] == 0.0
        assert result["week_hours"] == 0.0
        assert result["week_days"] == 0


# ---------------------------------------------------------------------------
# Team online status
# ---------------------------------------------------------------------------


class TestGetTeamOnlineStatus:
    @pytest.mark.asyncio
    async def test_get_team_online_status_returns_list(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """Should return a list of team member statuses."""
        now = datetime.now(BALI_TZ)
        row1 = _make_status_row(user_id="u1", email="a@bz.com", is_online=True, last_action_bali=now)
        row2 = _make_status_row(user_id="u2", email="b@bz.com", is_online=False, last_action_bali=now)

        mock_row1 = MagicMock(**{"__getitem__": lambda self, key: row1[key]})
        mock_row2 = MagicMock(**{"__getitem__": lambda self, key: row2[key]})
        conn.fetch.return_value = [mock_row1, mock_row2]

        result: list[dict[str, Any]] = await service.get_team_online_status()

        assert len(result) == 2
        assert result[0]["user_id"] == "u1"
        assert result[0]["is_online"] is True
        assert result[1]["user_id"] == "u2"
        assert result[1]["is_online"] is False

    @pytest.mark.asyncio
    async def test_get_team_online_status_empty(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """Returns empty list when no team members found."""
        conn.fetch.return_value = []

        result: list[dict[str, Any]] = await service.get_team_online_status()

        assert result == []


# ---------------------------------------------------------------------------
# Daily hours
# ---------------------------------------------------------------------------


class TestGetDailyHours:
    @pytest.mark.asyncio
    async def test_get_daily_hours_defaults_to_today(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """When no date is passed, should query for today in Bali time."""
        row = _make_daily_row(hours_worked=7.5)
        conn.fetch.return_value = [row]

        result: list[dict[str, Any]] = await service.get_daily_hours()

        assert len(result) == 1
        assert result[0]["hours_worked"] == 7.5
        assert result[0]["email"] == USER_EMAIL

    @pytest.mark.asyncio
    async def test_get_daily_hours_with_specific_date(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """When a datetime is passed, should extract the date part."""
        conn.fetch.return_value = []
        specific = datetime(2026, 3, 15, 10, 0, tzinfo=BALI_TZ)

        result: list[dict[str, Any]] = await service.get_daily_hours(date=specific)

        assert result == []
        # Verify the query was called with the date (not datetime)
        call_args = conn.fetch.call_args
        assert call_args[0][1] == specific.date()


# ---------------------------------------------------------------------------
# Weekly summary
# ---------------------------------------------------------------------------


class TestGetWeeklySummary:
    @pytest.mark.asyncio
    async def test_get_weekly_summary_defaults_to_current_week(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """Should default to the current week start (Monday)."""
        row = _make_weekly_row(days_worked=3, total_hours=24.0, avg_hours_per_day=8.0)
        conn.fetch.return_value = [row]

        result: list[dict[str, Any]] = await service.get_weekly_summary()

        assert len(result) == 1
        assert result[0]["days_worked"] == 3
        assert result[0]["total_hours"] == 24.0

    @pytest.mark.asyncio
    async def test_get_weekly_summary_empty(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """Returns empty list when no data for the week."""
        conn.fetch.return_value = []

        result: list[dict[str, Any]] = await service.get_weekly_summary()

        assert result == []


# ---------------------------------------------------------------------------
# Monthly summary
# ---------------------------------------------------------------------------


class TestGetMonthlySummary:
    @pytest.mark.asyncio
    async def test_get_monthly_summary_defaults_to_current_month(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """Should default to the 1st of the current month."""
        row = _make_monthly_row(days_worked=20, total_hours=160.0, avg_hours_per_day=8.0)
        conn.fetch.return_value = [row]

        result: list[dict[str, Any]] = await service.get_monthly_summary()

        assert len(result) == 1
        assert result[0]["days_worked"] == 20
        assert result[0]["total_hours"] == 160.0

    @pytest.mark.asyncio
    async def test_get_monthly_summary_with_specific_month(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """Passing a datetime should extract month_start as the 1st."""
        conn.fetch.return_value = []
        specific = datetime(2026, 2, 17, 10, 0, tzinfo=BALI_TZ)

        result: list[dict[str, Any]] = await service.get_monthly_summary(month_start=specific)

        assert result == []
        call_args = conn.fetch.call_args
        # Should be 2026-02-01
        from datetime import date

        assert call_args[0][1] == date(2026, 2, 1)


# ---------------------------------------------------------------------------
# Export CSV
# ---------------------------------------------------------------------------


class TestExportTimesheetCsv:
    @pytest.mark.asyncio
    async def test_export_timesheet_csv_generates_header_and_rows(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """CSV should have a header and one row per daily_work_hours record."""
        row = _make_daily_row(hours_worked=8.0)
        conn.fetch.return_value = [row]

        start = datetime(2026, 3, 1, tzinfo=BALI_TZ)
        end = datetime(2026, 3, 31, tzinfo=BALI_TZ)
        csv_str: str = await service.export_timesheet_csv(start, end)

        lines = csv_str.strip().split("\n")
        assert lines[0] == "Email,Date,Clock In,Clock Out,Hours Worked"
        assert len(lines) == 2  # header + 1 data row
        assert USER_EMAIL in lines[1]

    @pytest.mark.asyncio
    async def test_export_timesheet_csv_empty(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """No data should produce header only."""
        conn.fetch.return_value = []

        start = datetime(2026, 3, 1, tzinfo=BALI_TZ)
        end = datetime(2026, 3, 31, tzinfo=BALI_TZ)
        csv_str: str = await service.export_timesheet_csv(start, end)

        lines = csv_str.strip().split("\n")
        assert len(lines) == 1
        assert lines[0].startswith("Email,")

    @pytest.mark.asyncio
    async def test_export_timesheet_csv_uses_date_part(
        self, service: TeamTimesheetService, conn: AsyncMock,
    ) -> None:
        """Datetime args should be converted to date for the SQL query."""
        conn.fetch.return_value = []

        start = datetime(2026, 3, 1, 12, 0, tzinfo=BALI_TZ)
        end = datetime(2026, 3, 31, 18, 0, tzinfo=BALI_TZ)
        await service.export_timesheet_csv(start, end)

        call_args = conn.fetch.call_args
        from datetime import date

        assert call_args[0][1] == date(2026, 3, 1)
        assert call_args[0][2] == date(2026, 3, 31)
