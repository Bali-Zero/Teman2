"""
Supplementary unit tests for backend/services/analytics/attendance_monitor.py
Covers areas NOT in test_unit_attendance_monitor.py:
- _chunk_telegram_message
- _render_email_shell
- check_absent_members flow
- _get_active_members, _get_member_by_email, _get_last_clockin_date
- _count_working_days_since
- _has_approved_leave
- _post_email
- _send_gentle_reminder
- start_schedulers / stop_schedulers
- AttendanceMonitor init
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from backend.services.analytics.attendance_monitor import (
    ABSENT_THRESHOLD_DAYS,
    ADMIN_EMAIL,
    LATE_EXEMPT_EMAILS,
    AttendanceMonitor,
    _chunk_telegram_message,
    _render_email_shell,
)

BALI_TZ = ZoneInfo("Asia/Makassar")


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_pool() -> MagicMock:
    """Mock asyncpg pool."""
    pool = MagicMock()
    conn = AsyncMock()

    class _Ctx:
        async def __aenter__(self) -> AsyncMock:
            return conn

        async def __aexit__(self, *args: Any) -> None:
            pass

    pool.acquire = MagicMock(return_value=_Ctx())
    pool._conn = conn
    return pool


@pytest.fixture
def monitor(mock_pool: MagicMock) -> AttendanceMonitor:
    """Fresh AttendanceMonitor."""
    return AttendanceMonitor(mock_pool)


# ═══════════════════════════════════════════════════════════════════════════════
# _chunk_telegram_message
# ═══════════════════════════════════════════════════════════════════════════════


class TestChunkTelegramMessage:
    def test_short_message_unchanged(self) -> None:
        msg = "Hello world"
        result = _chunk_telegram_message(msg)
        assert result == [msg]

    def test_single_element_when_under_limit(self) -> None:
        msg = "A" * 100
        result = _chunk_telegram_message(msg, max_len=200)
        assert len(result) == 1

    def test_splits_long_message(self) -> None:
        lines = [f"Line {i}: {'x' * 50}" for i in range(100)]
        msg = "\n".join(lines)
        result = _chunk_telegram_message(msg, max_len=500)
        assert len(result) > 1
        for chunk in result:
            assert len(chunk) <= 500

    def test_chunks_have_part_headers(self) -> None:
        msg = "\n".join(["x" * 100] * 50)
        result = _chunk_telegram_message(msg, max_len=300)
        assert len(result) > 1
        assert result[0].startswith("(part 1/")
        assert result[-1].startswith(f"(part {len(result)}/")

    def test_hard_breaks_very_long_lines(self) -> None:
        msg = "A" * 10000  # Single very long line
        result = _chunk_telegram_message(msg, max_len=500)
        assert len(result) > 1
        # The "(part N/M)\n" header adds ~14 chars on top of the max_len body
        for chunk in result:
            assert len(chunk) <= 520  # body <= 500 + header overhead

    def test_empty_message(self) -> None:
        result = _chunk_telegram_message("")
        assert result == [""]

    def test_exact_limit(self) -> None:
        msg = "A" * 4000
        result = _chunk_telegram_message(msg, max_len=4000)
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# _render_email_shell
# ═══════════════════════════════════════════════════════════════════════════════


class TestRenderEmailShell:
    def test_contains_header(self) -> None:
        html = _render_email_shell(
            header_title="Test Title",
            accent="#ff0000",
            body_html="<p>Hello</p>",
        )
        assert "Test Title" in html
        assert "#ff0000" in html
        assert "<p>Hello</p>" in html

    def test_contains_footer(self) -> None:
        html = _render_email_shell(
            header_title="Title",
            accent="#000",
            body_html="body",
        )
        assert "Bali Zero" in html
        assert "Zantara" in html

    def test_is_valid_html(self) -> None:
        html = _render_email_shell(
            header_title="Title",
            accent="#000",
            body_html="<p>Content</p>",
        )
        assert html.strip().startswith("<!DOCTYPE html>")
        assert "</html>" in html


# ═══════════════════════════════════════════════════════════════════════════════
# AttendanceMonitor.__init__
# ═══════════════════════════════════════════════════════════════════════════════


class TestAttendanceMonitorInit:
    def test_init(self, monitor: AttendanceMonitor) -> None:
        assert monitor._running is False
        assert monitor._escalation_task is None
        assert monitor._digest_task is None


# ═══════════════════════════════════════════════════════════════════════════════
# _count_working_days_since
# ═══════════════════════════════════════════════════════════════════════════════


class TestCountWorkingDays:
    @pytest.mark.asyncio
    async def test_same_day(self, monitor: AttendanceMonitor) -> None:
        today = date(2026, 4, 7)  # Monday
        result = await monitor._count_working_days_since(today, today)
        assert result == 0

    @pytest.mark.asyncio
    async def test_future_returns_zero(self, monitor: AttendanceMonitor) -> None:
        result = await monitor._count_working_days_since(date(2026, 4, 9), date(2026, 4, 7))
        assert result == 0

    @pytest.mark.asyncio
    async def test_mon_to_wed(self, monitor: AttendanceMonitor) -> None:
        # Monday to Wednesday = Tue + Wed = 2
        result = await monitor._count_working_days_since(date(2026, 4, 6), date(2026, 4, 8))
        assert result == 2

    @pytest.mark.asyncio
    async def test_fri_to_mon(self, monitor: AttendanceMonitor) -> None:
        # Friday to Monday = 1 (Mon; weekend skipped)
        result = await monitor._count_working_days_since(date(2026, 4, 3), date(2026, 4, 6))
        assert result == 1

    @pytest.mark.asyncio
    async def test_one_full_week(self, monitor: AttendanceMonitor) -> None:
        # Monday to next Monday = 5 working days
        result = await monitor._count_working_days_since(date(2026, 4, 6), date(2026, 4, 13))
        assert result == 5


# ═══════════════════════════════════════════════════════════════════════════════
# _has_approved_leave
# ═══════════════════════════════════════════════════════════════════════════════


class TestHasApprovedLeave:
    @pytest.mark.asyncio
    async def test_has_leave(self, monitor: AttendanceMonitor, mock_pool: MagicMock) -> None:
        mock_pool._conn.fetchrow = AsyncMock(return_value={"1": 1})
        result = await monitor._has_approved_leave("test@balizero.com", date(2026, 4, 7))
        assert result is True

    @pytest.mark.asyncio
    async def test_no_leave(self, monitor: AttendanceMonitor, mock_pool: MagicMock) -> None:
        mock_pool._conn.fetchrow = AsyncMock(return_value=None)
        result = await monitor._has_approved_leave("test@balizero.com", date(2026, 4, 7))
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# _get_active_members
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetActiveMembers:
    @pytest.mark.asyncio
    async def test_returns_members(self, monitor: AttendanceMonitor, mock_pool: MagicMock) -> None:
        mock_pool._conn.fetch = AsyncMock(
            return_value=[
                {"email": "a@balizero.com", "full_name": "Alice"},
                {"email": "b@balizero.com", "full_name": "Bob"},
            ],
        )
        result = await monitor._get_active_members()
        assert len(result) == 2
        assert result[0]["email"] == "a@balizero.com"

    @pytest.mark.asyncio
    async def test_returns_empty(self, monitor: AttendanceMonitor, mock_pool: MagicMock) -> None:
        mock_pool._conn.fetch = AsyncMock(return_value=[])
        result = await monitor._get_active_members()
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# _get_member_by_email
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetMemberByEmail:
    @pytest.mark.asyncio
    async def test_found(self, monitor: AttendanceMonitor, mock_pool: MagicMock) -> None:
        mock_pool._conn.fetchrow = AsyncMock(
            return_value={"email": "a@balizero.com", "full_name": "Alice"},
        )
        result = await monitor._get_member_by_email("a@balizero.com")
        assert result is not None
        assert result["full_name"] == "Alice"

    @pytest.mark.asyncio
    async def test_not_found(self, monitor: AttendanceMonitor, mock_pool: MagicMock) -> None:
        mock_pool._conn.fetchrow = AsyncMock(return_value=None)
        result = await monitor._get_member_by_email("unknown@balizero.com")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# _get_last_clockin_date
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetLastClockinDate:
    @pytest.mark.asyncio
    async def test_has_record(self, monitor: AttendanceMonitor, mock_pool: MagicMock) -> None:
        mock_pool._conn.fetchrow = AsyncMock(
            return_value={"last_date": date(2026, 4, 5)},
        )
        result = await monitor._get_last_clockin_date("a@balizero.com")
        assert result == date(2026, 4, 5)

    @pytest.mark.asyncio
    async def test_no_record(self, monitor: AttendanceMonitor, mock_pool: MagicMock) -> None:
        mock_pool._conn.fetchrow = AsyncMock(return_value=None)
        result = await monitor._get_last_clockin_date("a@balizero.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_null_date(self, monitor: AttendanceMonitor, mock_pool: MagicMock) -> None:
        mock_pool._conn.fetchrow = AsyncMock(return_value={"last_date": None})
        result = await monitor._get_last_clockin_date("a@balizero.com")
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# _post_email
# ═══════════════════════════════════════════════════════════════════════════════


class TestPostEmail:
    @pytest.mark.asyncio
    async def test_post_email_success(self, monitor: AttendanceMonitor) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("backend.services.analytics.attendance_monitor.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            await monitor._post_email(
                to="test@example.com",
                subject="Test",
                html_body="<p>Hello</p>",
                cc="cc@example.com",
                log_tag="test_email",
            )
            mock_client.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_post_email_http_error(self, monitor: AttendanceMonitor) -> None:
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("err", request=MagicMock(), response=mock_response),
        )

        with patch("backend.services.analytics.attendance_monitor.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            # Should not raise
            await monitor._post_email(to="a@b.com", subject="Test", html_body="<p>x</p>")

    @pytest.mark.asyncio
    async def test_post_email_connection_error(self, monitor: AttendanceMonitor) -> None:
        with patch("backend.services.analytics.attendance_monitor.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=ConnectionError("Network down"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_client

            # Should not raise
            await monitor._post_email(to="a@b.com", subject="Test", html_body="<p>x</p>")


# ═══════════════════════════════════════════════════════════════════════════════
# _send_gentle_reminder
# ═══════════════════════════════════════════════════════════════════════════════


class TestSendGentleReminder:
    @pytest.mark.asyncio
    async def test_sends_email(self, monitor: AttendanceMonitor) -> None:
        monitor._post_email = AsyncMock()

        await monitor._send_gentle_reminder("alice@balizero.com", "Alice Test", "09:35")

        monitor._post_email.assert_awaited_once()
        call_kwargs = monitor._post_email.call_args.kwargs
        assert call_kwargs["to"] == "alice@balizero.com"
        assert "09:35" in call_kwargs["subject"]
        # No CC for gentle reminder
        assert call_kwargs.get("cc") is None


# ═══════════════════════════════════════════════════════════════════════════════
# check_absent_members
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckAbsentMembers:
    @pytest.mark.asyncio
    async def test_no_active_members(self, monitor: AttendanceMonitor) -> None:
        monitor._get_active_members = AsyncMock(return_value=[])

        # Should not raise, just return
        await monitor.check_absent_members()

    @pytest.mark.asyncio
    async def test_no_absences(self, monitor: AttendanceMonitor) -> None:
        monitor._get_active_members = AsyncMock(
            return_value=[
                {"email": "alice@balizero.com", "full_name": "Alice"},
            ],
        )
        monitor._get_last_clockin_date = AsyncMock(return_value=date.today())
        monitor._count_working_days_since = AsyncMock(return_value=0)
        monitor._send_absent_alert = AsyncMock()

        await monitor.check_absent_members()
        monitor._send_absent_alert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_member_never_clocked_in(self, monitor: AttendanceMonitor) -> None:
        monitor._get_active_members = AsyncMock(
            return_value=[
                {"email": "new@balizero.com", "full_name": "New Person"},
            ],
        )
        monitor._get_last_clockin_date = AsyncMock(return_value=None)
        monitor._send_absent_alert = AsyncMock()

        await monitor.check_absent_members()
        monitor._send_absent_alert.assert_awaited_once()
        absent_list = monitor._send_absent_alert.call_args[0][0]
        assert len(absent_list) == 1
        assert absent_list[0]["absent_days"] is None

    @pytest.mark.asyncio
    async def test_member_absent_threshold(self, monitor: AttendanceMonitor) -> None:
        monitor._get_active_members = AsyncMock(
            return_value=[
                {"email": "absent@balizero.com", "full_name": "Absent"},
            ],
        )
        # Last clock in was several working days ago
        last_date = date.today() - timedelta(days=5)
        monitor._get_last_clockin_date = AsyncMock(return_value=last_date)
        monitor._send_absent_alert = AsyncMock()

        await monitor.check_absent_members()
        monitor._send_absent_alert.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════════════
# start_schedulers / stop_schedulers
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchedulerLifecycle:
    @pytest.mark.asyncio
    async def test_start_schedulers(self, monitor: AttendanceMonitor) -> None:
        with (
            patch.object(monitor, "_escalation_loop", new_callable=AsyncMock),
            patch.object(monitor, "_daily_digest_loop", new_callable=AsyncMock),
        ):
            await monitor.start_schedulers()
            assert monitor._running is True
            assert monitor._escalation_task is not None
            assert monitor._digest_task is not None
            # Clean up
            await monitor.stop_schedulers()

    @pytest.mark.asyncio
    async def test_start_schedulers_idempotent(self, monitor: AttendanceMonitor) -> None:
        monitor._running = True
        # Should return early without creating tasks
        await monitor.start_schedulers()
        assert monitor._escalation_task is None

    @pytest.mark.asyncio
    async def test_stop_schedulers(self, monitor: AttendanceMonitor) -> None:
        with (
            patch.object(monitor, "_escalation_loop", new_callable=AsyncMock),
            patch.object(monitor, "_daily_digest_loop", new_callable=AsyncMock),
        ):
            await monitor.start_schedulers()
            await monitor.stop_schedulers()
            assert monitor._running is False
            assert monitor._escalation_task is None
            assert monitor._digest_task is None

    @pytest.mark.asyncio
    async def test_stop_schedulers_noop(self, monitor: AttendanceMonitor) -> None:
        # Should not raise when not started
        await monitor.stop_schedulers()


# ═══════════════════════════════════════════════════════════════════════════════
# Constants verification
# ═══════════════════════════════════════════════════════════════════════════════


class TestConstants:
    def test_admin_email(self) -> None:
        assert ADMIN_EMAIL == "zero@balizero.com"

    def test_absent_threshold(self) -> None:
        assert ABSENT_THRESHOLD_DAYS == 2

    def test_exempt_emails(self) -> None:
        assert "zero@balizero.com" in LATE_EXEMPT_EMAILS
        assert "ruslana@balizero.com" in LATE_EXEMPT_EMAILS
        assert "veronika@balizero.com" in LATE_EXEMPT_EMAILS
