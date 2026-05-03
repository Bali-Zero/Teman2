"""
Unit tests for AlertService.

Tests alert sending, rate limiting, latency digest,
and multi-channel dispatch (Telegram, Slack, Discord).
"""

import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx


def _make_service(
    *,
    telegram: bool = True,
    slack: bool = False,
    discord: bool = False,
):
    """Create AlertService with mocked settings."""
    mock_settings = MagicMock()
    mock_settings.telegram_bot_token = "bot-token" if telegram else None
    mock_settings.admin_telegram_chat_id = "12345" if telegram else None
    mock_settings.slack_webhook_url = "https://hooks.slack.com/test" if slack else None
    mock_settings.discord_webhook_url = "https://discord.com/webhook" if discord else None

    with patch("backend.app.core.config.settings", mock_settings):
        from backend.services.monitoring.alert_service import AlertService
        svc = AlertService()

    return svc


# ---------------------------------------------------------------------------
# AlertLevel
# ---------------------------------------------------------------------------


class TestAlertLevel:
    def test_enum_values(self):
        from backend.services.monitoring.alert_service import AlertLevel
        assert AlertLevel.INFO.value == "info"
        assert AlertLevel.WARNING.value == "warning"
        assert AlertLevel.ERROR.value == "error"
        assert AlertLevel.CRITICAL.value == "critical"


# ---------------------------------------------------------------------------
# Client lifecycle
# ---------------------------------------------------------------------------


class TestGetClient:
    def test_creates_client(self):
        svc = _make_service()
        client = svc._get_client()
        assert isinstance(client, httpx.AsyncClient)

    def test_reuses_client(self):
        svc = _make_service()
        c1 = svc._get_client()
        c2 = svc._get_client()
        assert c1 is c2


@pytest.mark.asyncio
class TestClose:
    async def test_close_open_client(self):
        svc = _make_service()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        svc._client = mock_client
        await svc.close()
        mock_client.aclose.assert_awaited_once()

    async def test_close_no_client(self):
        svc = _make_service()
        await svc.close()  # Should not raise


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_telegram_enabled(self):
        svc = _make_service(telegram=True)
        assert svc.enable_telegram is True

    def test_telegram_disabled(self):
        svc = _make_service(telegram=False)
        assert svc.enable_telegram is False

    def test_slack_enabled(self):
        svc = _make_service(slack=True)
        assert svc.enable_slack is True

    def test_discord_enabled(self):
        svc = _make_service(discord=True)
        assert svc.enable_discord is True

    def test_logging_always_on(self):
        svc = _make_service()
        assert svc.enable_logging is True


# ---------------------------------------------------------------------------
# _log_alert
# ---------------------------------------------------------------------------


class TestLogAlert:
    def test_log_critical(self):
        from backend.services.monitoring.alert_service import AlertLevel
        svc = _make_service()
        # Should not raise
        svc._log_alert("Title", "Message", AlertLevel.CRITICAL, {"key": "val"})

    def test_log_error(self):
        from backend.services.monitoring.alert_service import AlertLevel
        svc = _make_service()
        svc._log_alert("Title", "Message", AlertLevel.ERROR)

    def test_log_warning(self):
        from backend.services.monitoring.alert_service import AlertLevel
        svc = _make_service()
        svc._log_alert("Title", "Message", AlertLevel.WARNING)

    def test_log_info(self):
        from backend.services.monitoring.alert_service import AlertLevel
        svc = _make_service()
        svc._log_alert("Title", "Message", AlertLevel.INFO)


# ---------------------------------------------------------------------------
# send_alert + rate limiting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSendAlert:
    async def test_always_logs(self):
        from backend.services.monitoring.alert_service import AlertLevel
        svc = _make_service(telegram=False)
        result = await svc.send_alert("Title", "Msg", AlertLevel.INFO)
        assert result["logging"] is True

    async def test_sends_telegram(self):
        from backend.services.monitoring.alert_service import AlertLevel
        svc = _make_service(telegram=True)
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        svc._client = mock_client

        result = await svc.send_alert("Title", "Msg", AlertLevel.ERROR)
        assert result["telegram"] is True

    async def test_rate_limits_duplicate_alert(self):
        from backend.services.monitoring.alert_service import AlertLevel
        svc = _make_service(telegram=True)
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        svc._client = mock_client

        # First send succeeds
        result1 = await svc.send_alert("Same Title", "Msg", AlertLevel.ERROR, {"path": "/api/test"})
        assert result1["telegram"] is True

        # Second send is rate-limited
        result2 = await svc.send_alert("Same Title", "Msg", AlertLevel.ERROR, {"path": "/api/test"})
        assert result2["telegram"] is False

    async def test_global_rate_limit(self):
        from backend.services.monitoring.alert_service import AlertLevel
        svc = _make_service(telegram=True)
        svc._global_max_per_minute = 2  # Low limit for testing
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        svc._client = mock_client

        # Send 3 alerts with different keys
        for i in range(3):
            await svc.send_alert(f"Alert {i}", "Msg", AlertLevel.ERROR, {"path": f"/api/{i}"})

        # Third should have been globally rate-limited
        assert mock_client.post.call_count <= 2

    async def test_telegram_failure_handled(self):
        from backend.services.monitoring.alert_service import AlertLevel
        svc = _make_service(telegram=True)
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post.side_effect = Exception("Network error")
        svc._client = mock_client

        result = await svc.send_alert("Title", "Msg", AlertLevel.ERROR)
        assert result["telegram"] is False
        assert result["logging"] is True


# ---------------------------------------------------------------------------
# send_http_error_alert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSendHttpErrorAlert:
    async def test_5xx_critical(self):
        from backend.services.monitoring.alert_service import AlertLevel
        svc = _make_service(telegram=False)
        svc.send_alert = AsyncMock(return_value={"logging": True, "telegram": False, "slack": False, "discord": False})

        await svc.send_http_error_alert(503, "GET", "/health")
        call_args = svc.send_alert.call_args
        assert call_args.kwargs["level"] == AlertLevel.CRITICAL

    async def test_500_error(self):
        from backend.services.monitoring.alert_service import AlertLevel
        svc = _make_service(telegram=False)
        svc.send_alert = AsyncMock(return_value={"logging": True, "telegram": False, "slack": False, "discord": False})

        await svc.send_http_error_alert(500, "POST", "/api/chat")
        call_args = svc.send_alert.call_args
        assert call_args.kwargs["level"] == AlertLevel.ERROR

    async def test_4xx_warning(self):
        from backend.services.monitoring.alert_service import AlertLevel
        svc = _make_service(telegram=False)
        svc.send_alert = AsyncMock(return_value={"logging": True, "telegram": False, "slack": False, "discord": False})

        await svc.send_http_error_alert(404, "GET", "/missing")
        call_args = svc.send_alert.call_args
        assert call_args.kwargs["level"] == AlertLevel.WARNING

    async def test_includes_metadata(self):
        svc = _make_service(telegram=False)
        svc.send_alert = AsyncMock(return_value={"logging": True, "telegram": False, "slack": False, "discord": False})

        await svc.send_http_error_alert(
            500, "POST", "/api/chat", error_detail="DB timeout",
            request_id="req-123", user_agent="Mozilla/5.0",
        )
        call_args = svc.send_alert.call_args
        metadata = call_args.kwargs["metadata"]
        assert metadata["status_code"] == 500
        assert metadata["request_id"] == "req-123"
        assert metadata["error_detail"] == "DB timeout"


# ---------------------------------------------------------------------------
# send_latency_alert (buffered)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSendLatencyAlert:
    async def test_buffers_event(self):
        svc = _make_service()
        result = await svc.send_latency_alert(5000, "GET", "/api/search", 3000)
        assert result["logging"] is True
        assert result["telegram"] is False
        assert len(svc._latency_buffer) == 1
        assert svc._latency_buffer[0]["duration_ms"] == 5000

    async def test_multiple_events_buffer(self):
        svc = _make_service()
        await svc.send_latency_alert(5000, "GET", "/api/search", 3000)
        await svc.send_latency_alert(8000, "POST", "/api/chat", 3000)
        assert len(svc._latency_buffer) == 2


# ---------------------------------------------------------------------------
# send_hourly_digest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSendHourlyDigest:
    async def test_skips_when_buffer_empty(self):
        svc = _make_service(telegram=True)
        await svc.send_hourly_digest()
        # No error, no send

    async def test_sends_digest(self):
        svc = _make_service(telegram=True)
        svc._latency_buffer = [
            {"ts": "10:00", "duration_ms": 5000, "method": "GET", "path": "/api/search", "threshold_ms": 3000, "request_id": "", "user_agent": ""},
            {"ts": "10:05", "duration_ms": 8000, "method": "GET", "path": "/api/search", "threshold_ms": 3000, "request_id": "", "user_agent": ""},
        ]
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_resp = MagicMock()
        mock_client.post.return_value = mock_resp
        svc._client = mock_client

        await svc.send_hourly_digest()
        assert len(svc._latency_buffer) == 0  # Cleared
        mock_client.post.assert_awaited_once()


# ---------------------------------------------------------------------------
# send_resource_alert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSendResourceAlert:
    async def test_warning_level(self):
        from backend.services.monitoring.alert_service import AlertLevel
        svc = _make_service(telegram=False)
        svc.send_alert = AsyncMock()

        await svc.send_resource_alert("memory", 85.0, 80.0, "%")
        call_args = svc.send_alert.call_args
        assert call_args.kwargs["level"] == AlertLevel.WARNING

    async def test_critical_level(self):
        from backend.services.monitoring.alert_service import AlertLevel
        svc = _make_service(telegram=False)
        svc.send_alert = AsyncMock()

        # > threshold * 1.1 = critical
        await svc.send_resource_alert("memory", 95.0, 80.0, "%")
        call_args = svc.send_alert.call_args
        assert call_args.kwargs["level"] == AlertLevel.CRITICAL


# ---------------------------------------------------------------------------
# Slack / Discord channel dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSlackAlert:
    async def test_sends_slack(self):
        svc = _make_service(telegram=False, slack=True)
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        svc._client = mock_client

        from backend.services.monitoring.alert_service import AlertLevel
        result = await svc.send_alert("Title", "Msg", AlertLevel.ERROR)
        assert result["slack"] is True

    async def test_skips_when_no_webhook(self):
        from backend.services.monitoring.alert_service import AlertLevel
        svc = _make_service(telegram=False, slack=False)
        # _send_slack_alert should early return
        await svc._send_slack_alert("t", "m", AlertLevel.INFO)


@pytest.mark.asyncio
class TestDiscordAlert:
    async def test_sends_discord(self):
        svc = _make_service(telegram=False, discord=True)
        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        svc._client = mock_client

        from backend.services.monitoring.alert_service import AlertLevel
        result = await svc.send_alert("Title", "Msg", AlertLevel.ERROR)
        assert result["discord"] is True

    async def test_skips_when_no_webhook(self):
        from backend.services.monitoring.alert_service import AlertLevel
        svc = _make_service(telegram=False, discord=False)
        await svc._send_discord_alert("t", "m", AlertLevel.INFO)


# ---------------------------------------------------------------------------
# start_digest_loop
# ---------------------------------------------------------------------------


class TestStartDigestLoop:
    def test_creates_task(self):
        import asyncio
        svc = _make_service()
        with patch("asyncio.create_task") as mock_ct:
            mock_ct.return_value = MagicMock(done=MagicMock(return_value=False))
            svc.start_digest_loop()
            mock_ct.assert_called_once()

    def test_no_double_start(self):
        import asyncio
        svc = _make_service()
        mock_task = MagicMock()
        mock_task.done.return_value = False
        svc._digest_task = mock_task

        with patch("asyncio.create_task") as mock_ct:
            svc.start_digest_loop()
            mock_ct.assert_not_called()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestGetAlertService:
    def test_returns_instance(self):
        import backend.services.monitoring.alert_service as mod
        mod._alert_service = None
        with patch("backend.services.monitoring.alert_service.AlertService") as mock_cls:
            mock_cls.return_value = MagicMock()
            svc = mod.get_alert_service()
            assert svc is not None
