"""
Unit tests for AttendanceMonitor.

Coverage focus:
- resolve_responsible_manager pure routing
- _working_hours_between (static math, weekend skipping)
- check_late_checkin two-stage logic (on time / grace / incident)
- LATE_EXEMPT_EMAILS short-circuit
- approved leave short-circuit
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

from backend.services.analytics.attendance_monitor import (
    AttendanceMonitor,
    LATE_GRACE_HOUR,
    LATE_GRACE_MINUTE,
    LATE_INCIDENT_HOUR,
    LATE_INCIDENT_MINUTE,
    resolve_responsible_manager,
)

BALI_TZ = ZoneInfo("Asia/Makassar")


# ---------------------------------------------------------------------------
# resolve_responsible_manager — pure routing
# ---------------------------------------------------------------------------


class TestResolveResponsibleManager:
    """Routing rules from Zero, 2026-04-07."""

    def test_tax_team_routes_to_veronika(self) -> None:
        assert (
            resolve_responsible_manager("kadek.tax@balizero.com")
            == "veronika@balizero.com"
        )
        assert (
            resolve_responsible_manager("angel.tax@balizero.com")
            == "veronika@balizero.com"
        )
        assert (
            resolve_responsible_manager("dewaayu.tax@balizero.com")
            == "veronika@balizero.com"
        )
        assert (
            resolve_responsible_manager("faysha.tax@balizero.com")
            == "veronika@balizero.com"
        )

    def test_dea_and_rina_route_to_ruslana(self) -> None:
        assert (
            resolve_responsible_manager("dea@balizero.com") == "ruslana@balizero.com"
        )
        assert (
            resolve_responsible_manager("rina@balizero.com") == "ruslana@balizero.com"
        )

    def test_other_emails_have_no_supervisor(self) -> None:
        assert resolve_responsible_manager("adit@balizero.com") is None
        assert resolve_responsible_manager("surya@balizero.com") is None
        assert resolve_responsible_manager("sahira@balizero.com") is None
        assert resolve_responsible_manager("damar@balizero.com") is None

    def test_routing_is_case_insensitive(self) -> None:
        assert (
            resolve_responsible_manager("KADEK.TAX@balizero.com")
            == "veronika@balizero.com"
        )
        assert (
            resolve_responsible_manager("DEA@balizero.com") == "ruslana@balizero.com"
        )
        assert resolve_responsible_manager("  Adit@balizero.com  ") is None

    def test_tax_substring_must_be_local_part_suffix(self) -> None:
        # An address whose local part merely *contains* "tax" should NOT route
        # to Veronika — only addresses ending in ".tax" do.
        assert resolve_responsible_manager("taxman@balizero.com") is None
        assert resolve_responsible_manager("ataxia@balizero.com") is None


# ---------------------------------------------------------------------------
# _working_hours_between — pure math, weekend skipping
# ---------------------------------------------------------------------------


class TestWorkingHoursBetween:
    """Pure math; no DB or async involved."""

    def test_same_instant_returns_zero(self) -> None:
        t = datetime(2026, 4, 6, 10, 0, tzinfo=BALI_TZ)
        assert AttendanceMonitor._working_hours_between(t, t) == 0.0

    def test_end_before_start_returns_zero(self) -> None:
        start = datetime(2026, 4, 6, 10, 0, tzinfo=BALI_TZ)
        end = datetime(2026, 4, 6, 9, 0, tzinfo=BALI_TZ)
        assert AttendanceMonitor._working_hours_between(start, end) == 0.0

    def test_within_a_single_weekday(self) -> None:
        # Monday 09:45 → Monday 18:45 = 9 hours.
        start = datetime(2026, 4, 6, 9, 45, tzinfo=BALI_TZ)
        end = datetime(2026, 4, 6, 18, 45, tzinfo=BALI_TZ)
        hours = AttendanceMonitor._working_hours_between(start, end)
        assert hours == pytest.approx(9.0, abs=0.001)

    def test_skips_full_weekend(self) -> None:
        # Friday 09:45 → Monday 09:45 = 24h working hours
        # (Fri 09:45 → Sat 00:00 = 14.25h, Sat+Sun skipped, Mon 00:00 → Mon 09:45 = 9.75h)
        fri = datetime(2026, 4, 3, 9, 45, tzinfo=BALI_TZ)
        mon = datetime(2026, 4, 6, 9, 45, tzinfo=BALI_TZ)
        hours = AttendanceMonitor._working_hours_between(fri, mon)
        assert hours == pytest.approx(24.0, abs=0.01)

    def test_pure_saturday_returns_zero(self) -> None:
        sat0 = datetime(2026, 4, 4, 0, 0, tzinfo=BALI_TZ)
        sat23 = datetime(2026, 4, 4, 23, 59, tzinfo=BALI_TZ)
        assert AttendanceMonitor._working_hours_between(sat0, sat23) == 0.0

    def test_24_hours_across_two_weekdays(self) -> None:
        mon = datetime(2026, 4, 6, 9, 45, tzinfo=BALI_TZ)
        tue = datetime(2026, 4, 7, 9, 45, tzinfo=BALI_TZ)
        hours = AttendanceMonitor._working_hours_between(mon, tue)
        assert hours == pytest.approx(24.0, abs=0.001)

    def test_friday_evening_to_monday_morning(self) -> None:
        # Friday 18:00 → Monday 06:00 = 6h working hours
        # (Fri 18:00 → Sat 00:00 = 6h, weekend skipped, Mon 00:00 → 06:00 = 6h)
        fri = datetime(2026, 4, 3, 18, 0, tzinfo=BALI_TZ)
        mon = datetime(2026, 4, 6, 6, 0, tzinfo=BALI_TZ)
        hours = AttendanceMonitor._working_hours_between(fri, mon)
        assert hours == pytest.approx(12.0, abs=0.01)

    def test_naive_datetime_is_assumed_bali(self) -> None:
        # If the caller forgets tzinfo we should treat it as Bali time, not UTC.
        start = datetime(2026, 4, 6, 9, 0)  # naive
        end = datetime(2026, 4, 6, 12, 0)  # naive
        hours = AttendanceMonitor._working_hours_between(start, end)
        assert hours == pytest.approx(3.0, abs=0.001)


# ---------------------------------------------------------------------------
# check_late_checkin — two-stage policy
# ---------------------------------------------------------------------------


@pytest.fixture
def monitor_with_mocks() -> tuple[AttendanceMonitor, dict]:
    """
    AttendanceMonitor whose senders and DB lookups are replaced with AsyncMocks.

    Returns the monitor and a dict of references to the mocks so each test can
    assert call counts directly.
    """
    pool = AsyncMock()
    monitor = AttendanceMonitor(db_pool=pool)

    monitor._send_gentle_reminder = AsyncMock()
    monitor._send_incident_opened_notification = AsyncMock()
    monitor._has_approved_leave = AsyncMock(return_value=False)
    monitor._get_member_by_email = AsyncMock(
        return_value={"email": "x@balizero.com", "full_name": "Test User"},
    )
    return monitor, {
        "gentle": monitor._send_gentle_reminder,
        "incident": monitor._send_incident_opened_notification,
        "leave": monitor._has_approved_leave,
        "member": monitor._get_member_by_email,
    }


def _bali_at(hour: int, minute: int) -> datetime:
    """Helper: build a Tuesday 2026-04-07 datetime in Bali time."""
    return datetime(2026, 4, 7, hour, minute, tzinfo=BALI_TZ)


class TestCheckLateCheckinStages:
    """Verify the on-time / grace / incident split at the right boundaries."""

    @pytest.mark.asyncio
    async def test_on_time_does_nothing(self, monitor_with_mocks) -> None:
        monitor, mocks = monitor_with_mocks
        await monitor.check_late_checkin("adit@balizero.com", _bali_at(9, 29))
        mocks["gentle"].assert_not_called()
        mocks["incident"].assert_not_called()
        # We should not even hit the leave check for on-time arrivals.
        mocks["leave"].assert_not_called()

    @pytest.mark.asyncio
    async def test_exactly_on_grace_boundary_is_gentle(
        self, monitor_with_mocks,
    ) -> None:
        monitor, mocks = monitor_with_mocks
        # 09:30:00 sharp — first instant inside the grace window.
        await monitor.check_late_checkin("adit@balizero.com", _bali_at(9, 30))
        mocks["gentle"].assert_awaited_once()
        mocks["incident"].assert_not_called()

    @pytest.mark.asyncio
    async def test_inside_grace_window_is_gentle(self, monitor_with_mocks) -> None:
        monitor, mocks = monitor_with_mocks
        await monitor.check_late_checkin("adit@balizero.com", _bali_at(9, 35))
        mocks["gentle"].assert_awaited_once()
        mocks["incident"].assert_not_called()

    @pytest.mark.asyncio
    async def test_exactly_on_incident_boundary_is_incident(
        self, monitor_with_mocks,
    ) -> None:
        monitor, mocks = monitor_with_mocks
        await monitor.check_late_checkin("adit@balizero.com", _bali_at(9, 40))
        mocks["gentle"].assert_not_called()
        mocks["incident"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_well_after_incident_boundary_is_incident(
        self, monitor_with_mocks,
    ) -> None:
        monitor, mocks = monitor_with_mocks
        await monitor.check_late_checkin("adit@balizero.com", _bali_at(10, 5))
        mocks["gentle"].assert_not_called()
        mocks["incident"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_exempt_member_is_skipped_completely(
        self, monitor_with_mocks,
    ) -> None:
        monitor, mocks = monitor_with_mocks
        # Even at 11:00 a totally exempt user should not trigger anything.
        await monitor.check_late_checkin("ruslana@balizero.com", _bali_at(11, 0))
        mocks["gentle"].assert_not_called()
        mocks["incident"].assert_not_called()
        mocks["leave"].assert_not_called()

    @pytest.mark.asyncio
    async def test_approved_leave_blocks_alert(self, monitor_with_mocks) -> None:
        monitor, mocks = monitor_with_mocks
        mocks["leave"].return_value = True
        await monitor.check_late_checkin("adit@balizero.com", _bali_at(9, 45))
        mocks["leave"].assert_awaited_once()
        mocks["gentle"].assert_not_called()
        mocks["incident"].assert_not_called()


# ---------------------------------------------------------------------------
# Threshold constants haven't drifted
# ---------------------------------------------------------------------------


def test_threshold_constants_match_policy() -> None:
    """Pin the policy in code so a future edit can't silently move 09:30/09:40."""
    assert (LATE_GRACE_HOUR, LATE_GRACE_MINUTE) == (9, 30)
    assert (LATE_INCIDENT_HOUR, LATE_INCIDENT_MINUTE) == (9, 40)


# ---------------------------------------------------------------------------
# _send_incident_opened_notification — duplicate clock_in handling
# ---------------------------------------------------------------------------


class TestIncidentInsertConflict:
    """
    The incident table has UNIQUE (email, late_date). A second clock_in by
    the same person on the same day must NOT open a duplicate incident and
    must NOT send a second email.
    """

    @pytest.mark.asyncio
    async def test_duplicate_same_day_does_not_resend_email(self) -> None:
        # Build a monitor whose conn.fetchrow returns None — simulating the
        # ON CONFLICT (email, late_date) DO NOTHING branch firing because a
        # row already exists.
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=None)

        pool = MagicMock()
        pool.acquire = MagicMock(return_value=conn)

        monitor = AttendanceMonitor(db_pool=pool)
        monitor._post_email = AsyncMock()  # spy on email sending

        late_dt = datetime(2026, 4, 7, 9, 45, tzinfo=BALI_TZ)
        await monitor._send_incident_opened_notification(
            email="adit@balizero.com",
            full_name="Adit Test",
            checkin_time_dt=late_dt,
        )

        # The INSERT should have been attempted exactly once.
        conn.fetchrow.assert_awaited_once()
        # But because it returned None (ON CONFLICT), no email should have been sent.
        monitor._post_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_first_incident_of_day_sends_email(self) -> None:
        # Same setup, but conn.fetchrow returns a row — simulating a freshly
        # inserted incident.
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(
            return_value={
                "id": "00000000-0000-0000-0000-000000000001",
                "reply_token": "token_xyz_long_enough_for_query",
            },
        )
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=None)

        pool = MagicMock()
        pool.acquire = MagicMock(return_value=conn)

        monitor = AttendanceMonitor(db_pool=pool)
        monitor._post_email = AsyncMock()

        late_dt = datetime(2026, 4, 7, 9, 45, tzinfo=BALI_TZ)
        await monitor._send_incident_opened_notification(
            email="adit@balizero.com",
            full_name="Adit Test",
            checkin_time_dt=late_dt,
        )

        conn.fetchrow.assert_awaited_once()
        monitor._post_email.assert_awaited_once()
        # Verify the reply link is embedded in the rendered body.
        call_kwargs = monitor._post_email.call_args.kwargs
        assert "token_xyz_long_enough_for_query" in call_kwargs["html_body"]
        assert "00000000-0000-0000-0000-000000000001" in call_kwargs["html_body"]
