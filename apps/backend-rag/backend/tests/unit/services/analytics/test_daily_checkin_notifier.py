"""
Tests for DailyCheckinNotifier
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from services.analytics.daily_checkin_notifier import (
    DailyCheckinNotifier,
    init_daily_notifier,
)

BALI_TZ = ZoneInfo("Asia/Makassar")


class TestDailyCheckinNotifier:
    """Test suite for DailyCheckinNotifier"""

    def test_init(self):
        """Test notifier initialization"""
        mock_pool = MagicMock()
        notifier = DailyCheckinNotifier(mock_pool)

        assert notifier.pool == mock_pool
        assert notifier.task is None
        assert notifier.running is False

    @pytest.mark.asyncio
    async def test_start(self):
        """Test starting the notifier"""
        mock_pool = MagicMock()
        notifier = DailyCheckinNotifier(mock_pool)

        await notifier.start()

        assert notifier.running is True
        assert notifier.task is not None

        # Cleanup
        await notifier.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """Test starting when already running"""
        mock_pool = MagicMock()
        notifier = DailyCheckinNotifier(mock_pool)
        notifier.running = True

        await notifier.start()

        # Should not create new task
        assert notifier.running is True

    @pytest.mark.asyncio
    async def test_stop(self):
        """Test stopping the notifier"""
        mock_pool = MagicMock()
        notifier = DailyCheckinNotifier(mock_pool)
        notifier.running = True
        notifier.task = asyncio.create_task(asyncio.sleep(1))

        await notifier.stop()

        assert notifier.running is False

    @pytest.mark.asyncio
    async def test_stop_no_task(self):
        """Test stopping when no task exists"""
        mock_pool = MagicMock()
        notifier = DailyCheckinNotifier(mock_pool)
        notifier.running = True
        notifier.task = None

        await notifier.stop()

        assert notifier.running is False

    @pytest.mark.asyncio
    async def test_get_checkin_data(self):
        """Test getting check-in data from database"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_acquire():
            yield mock_conn

        mock_pool.acquire = mock_acquire

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "email": "test@example.com",
            "action_type": "clock_in",
            "action_time": datetime.now(BALI_TZ),
        }[key]
        mock_row.email = "test@example.com"
        mock_row.action_type = "clock_in"
        mock_row.action_time = datetime.now(BALI_TZ)

        mock_conn.fetch = AsyncMock(return_value=[mock_row])

        notifier = DailyCheckinNotifier(mock_pool)
        result = await notifier._get_checkin_data()

        assert len(result) == 1
        assert result[0]["email"] == "test@example.com"
        assert result[0]["action"] == "clock_in"
        assert "time" in result[0]

    @pytest.mark.asyncio
    async def test_get_checkin_data_empty(self):
        """Test getting check-in data when empty"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_acquire():
            yield mock_conn

        mock_pool.acquire = mock_acquire
        mock_conn.fetch = AsyncMock(return_value=[])

        notifier = DailyCheckinNotifier(mock_pool)
        result = await notifier._get_checkin_data()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_online_status(self):
        """Test getting online status from database"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_acquire():
            yield mock_conn

        mock_pool.acquire = mock_acquire

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "email": "test@example.com",
            "is_online": True,
            "last_action_bali": datetime.now(BALI_TZ),
        }[key]
        mock_row.email = "test@example.com"
        mock_row.is_online = True
        mock_row.last_action_bali = datetime.now(BALI_TZ)

        mock_conn.fetch = AsyncMock(return_value=[mock_row])

        notifier = DailyCheckinNotifier(mock_pool)
        result = await notifier._get_online_status()

        assert len(result) == 1
        assert result[0]["email"] == "test@example.com"
        assert result[0]["online"] is True
        assert "last_action" in result[0]

    @pytest.mark.asyncio
    async def test_get_online_status_no_last_action(self):
        """Test getting online status with no last action"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_acquire():
            yield mock_conn

        mock_pool.acquire = mock_acquire

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "email": "test@example.com",
            "is_online": False,
            "last_action_bali": None,
        }[key]
        mock_row.email = "test@example.com"
        mock_row.is_online = False
        mock_row.last_action_bali = None

        mock_conn.fetch = AsyncMock(return_value=[mock_row])

        notifier = DailyCheckinNotifier(mock_pool)
        result = await notifier._get_online_status()

        assert len(result) == 1
        assert result[0]["last_action"] == "-"

    def test_build_html_email(self):
        """Test building HTML email"""
        mock_pool = MagicMock()
        notifier = DailyCheckinNotifier(mock_pool)

        checkins = [{"email": "test@example.com", "action": "clock_in", "time": "09:00"}]
        online_status = [{"email": "test@example.com", "online": True, "last_action": "09:00"}]

        html = notifier._build_html_email(checkins, online_status)

        assert "Team Check-in Report" in html
        assert "test@example.com" in html
        assert "Check-in" in html
        assert "Online" in html

    def test_build_html_email_no_checkins(self):
        """Test building HTML email with no check-ins"""
        mock_pool = MagicMock()
        notifier = DailyCheckinNotifier(mock_pool)

        checkins = []
        online_status = [{"email": "test@example.com", "online": False, "last_action": "-"}]

        html = notifier._build_html_email(checkins, online_status)

        assert "Nessun check-in oggi" in html
        assert "test@example.com" in html

    def test_build_html_email_multiple_checkins(self):
        """Test building HTML email with multiple check-ins"""
        mock_pool = MagicMock()
        notifier = DailyCheckinNotifier(mock_pool)

        checkins = [
            {"email": "test1@example.com", "action": "clock_in", "time": "09:00"},
            {"email": "test2@example.com", "action": "clock_out", "time": "10:00"},
        ] * 15  # 30 check-ins, should limit to 20

        online_status = [
            {"email": "test1@example.com", "online": True, "last_action": "09:00"},
            {"email": "test2@example.com", "online": False, "last_action": "10:00"},
        ]

        html = notifier._build_html_email(checkins, online_status)

        assert "test1@example.com" in html
        assert "test2@example.com" in html
        # Should limit to 20 check-ins
        assert html.count("Check-in") <= 20

    @pytest.mark.asyncio
    @patch("services.analytics.daily_checkin_notifier.settings")
    async def test_send_daily_report_no_smtp_config(self, mock_settings):
        """Test sending daily report without SMTP config"""
        mock_settings.smtp_host = None
        mock_settings.smtp_user = None

        mock_pool = MagicMock()
        notifier = DailyCheckinNotifier(mock_pool)

        await notifier._send_daily_report()

        # Should return early without error

    @pytest.mark.asyncio
    @patch("services.analytics.daily_checkin_notifier.smtplib.SMTP")
    @patch("services.analytics.daily_checkin_notifier.settings")
    async def test_send_daily_report_success(self, mock_settings, mock_smtp):
        """Test successfully sending daily report"""
        mock_settings.smtp_host = "smtp.example.com"
        mock_settings.smtp_user = "user@example.com"
        mock_settings.smtp_password = "password"
        mock_settings.smtp_port = 587
        mock_settings.smtp_use_tls = True
        mock_settings.smtp_from = "from@example.com"

        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_acquire():
            yield mock_conn

        mock_pool.acquire = mock_acquire
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=None)

        notifier = DailyCheckinNotifier(mock_pool)
        await notifier._send_daily_report()

        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@example.com", "password")
        mock_server.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("services.analytics.daily_checkin_notifier.smtplib.SMTP")
    @patch("services.analytics.daily_checkin_notifier.settings")
    async def test_send_daily_report_no_tls(self, mock_settings, mock_smtp):
        """Test sending daily report without TLS"""
        mock_settings.smtp_host = "smtp.example.com"
        mock_settings.smtp_user = "user@example.com"
        mock_settings.smtp_password = "password"
        mock_settings.smtp_port = 25
        mock_settings.smtp_use_tls = False
        mock_settings.smtp_from = "from@example.com"

        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_acquire():
            yield mock_conn

        mock_pool.acquire = mock_acquire
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=None)

        notifier = DailyCheckinNotifier(mock_pool)
        await notifier._send_daily_report()

        mock_server.starttls.assert_not_called()
        mock_server.login.assert_called_once()

    @pytest.mark.asyncio
    @patch("services.analytics.daily_checkin_notifier.smtplib.SMTP")
    @patch("services.analytics.daily_checkin_notifier.settings")
    async def test_send_daily_report_error(self, mock_settings, mock_smtp):
        """Test sending daily report with error"""
        mock_settings.smtp_host = "smtp.example.com"
        mock_settings.smtp_user = "user@example.com"
        mock_settings.smtp_password = "password"
        mock_settings.smtp_port = 587
        mock_settings.smtp_use_tls = True
        mock_settings.smtp_from = "from@example.com"

        mock_pool = MagicMock()
        mock_conn = AsyncMock()

        @asynccontextmanager
        async def mock_acquire():
            yield mock_conn

        mock_pool.acquire = mock_acquire
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_smtp.side_effect = Exception("SMTP error")

        notifier = DailyCheckinNotifier(mock_pool)
        # Should not raise
        await notifier._send_daily_report()

    @pytest.mark.asyncio
    @patch("services.analytics.daily_checkin_notifier.settings")
    async def test_send_now(self, mock_settings):
        """Test send_now method"""
        mock_settings.smtp_host = None
        mock_settings.smtp_user = None

        mock_pool = MagicMock()
        notifier = DailyCheckinNotifier(mock_pool)

        # Should not raise
        await notifier.send_now()


class TestDailyCheckinNotifierFunctions:
    """Test module-level functions"""

    def test_init_daily_notifier(self):
        """Test init_daily_notifier function"""
        mock_pool = MagicMock()
        notifier = init_daily_notifier(mock_pool)

        assert notifier is not None
        assert notifier.pool == mock_pool

    def test_get_daily_notifier(self):
        """Test get_daily_notifier function"""
        from services.analytics.daily_checkin_notifier import get_daily_notifier

        # Initially None
        result = get_daily_notifier()
        # Could be None or a notifier instance depending on initialization
        assert result is None or isinstance(result, DailyCheckinNotifier)
