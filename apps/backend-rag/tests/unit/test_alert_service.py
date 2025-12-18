"""
Unit tests for Alert Service
100% coverage target with comprehensive mocking
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.alert_service import AlertLevel, AlertService, get_alert_service

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_settings():
    """Mock settings configuration"""
    with patch("app.core.config.settings") as mock:
        mock.slack_webhook_url = "https://hooks.slack.com/test"
        mock.discord_webhook_url = "https://discord.com/api/webhooks/test"
        yield mock


@pytest.fixture
def mock_settings_no_webhooks():
    """Mock settings without webhooks"""
    with patch("app.core.config.settings") as mock:
        mock.slack_webhook_url = None
        mock.discord_webhook_url = None
        yield mock


@pytest.fixture
def alert_service(mock_settings):
    """Create AlertService instance"""
    return AlertService()


@pytest.fixture
def alert_service_no_webhooks(mock_settings_no_webhooks):
    """Create AlertService instance without webhooks"""
    return AlertService()


# ============================================================================
# Tests: Initialization
# ============================================================================


def test_alert_service_init_with_webhooks(alert_service):
    """Test AlertService initialization with webhooks"""
    assert alert_service.enable_slack is True
    assert alert_service.enable_discord is True
    assert alert_service.enable_logging is True
    assert alert_service.slack_webhook == "https://hooks.slack.com/test"
    assert alert_service.discord_webhook == "https://discord.com/api/webhooks/test"


def test_alert_service_init_without_webhooks(alert_service_no_webhooks):
    """Test AlertService initialization without webhooks"""
    assert alert_service_no_webhooks.enable_slack is False
    assert alert_service_no_webhooks.enable_discord is False
    assert alert_service_no_webhooks.enable_logging is True


# ============================================================================
# Tests: send_alert
# ============================================================================


@pytest.mark.asyncio
async def test_send_alert_success_all_channels(alert_service):
    """Test sending alert to all channels successfully"""
    with (
        patch.object(alert_service, "_log_alert") as mock_log,
        patch.object(alert_service, "_send_slack_alert", new_callable=AsyncMock) as mock_slack,
        patch.object(alert_service, "_send_discord_alert", new_callable=AsyncMock) as mock_discord,
    ):
        result = await alert_service.send_alert(
            title="Test Alert",
            message="Test message",
            level=AlertLevel.ERROR,
            metadata={"key": "value"},
        )

        assert result["logging"] is True
        assert result["slack"] is True
        assert result["discord"] is True
        mock_log.assert_called_once()
        mock_slack.assert_called_once()
        mock_discord.assert_called_once()


@pytest.mark.asyncio
async def test_send_alert_no_webhooks(alert_service_no_webhooks):
    """Test sending alert without webhooks configured"""
    with patch.object(alert_service_no_webhooks, "_log_alert") as mock_log:
        result = await alert_service_no_webhooks.send_alert(
            title="Test Alert", message="Test message", level=AlertLevel.INFO
        )

        assert result["logging"] is True
        assert result["slack"] is False
        assert result["discord"] is False
        mock_log.assert_called_once()


@pytest.mark.asyncio
async def test_send_alert_logging_failure(alert_service):
    """Test alert handling when logging fails"""
    with (
        patch.object(alert_service, "_log_alert", side_effect=Exception("Log failed")) as mock_log,
        patch.object(alert_service, "_send_slack_alert", new_callable=AsyncMock) as mock_slack,
    ):
        result = await alert_service.send_alert(
            title="Test Alert", message="Test message", level=AlertLevel.WARNING
        )

        # When logging fails, result["logging"] is False
        assert result["logging"] is False
        mock_log.assert_called_once()
        mock_slack.assert_called_once()


@pytest.mark.asyncio
async def test_send_alert_slack_failure(alert_service):
    """Test alert handling when Slack fails"""
    with (
        patch.object(alert_service, "_log_alert"),
        patch.object(
            alert_service,
            "_send_slack_alert",
            new_callable=AsyncMock,
            side_effect=Exception("Slack failed"),
        ),
        patch.object(alert_service, "_send_discord_alert", new_callable=AsyncMock),
    ):
        result = await alert_service.send_alert(
            title="Test Alert", message="Test message", level=AlertLevel.ERROR
        )

        assert result["logging"] is True
        assert result["slack"] is False  # False when exception occurs
        assert result["discord"] is True


@pytest.mark.asyncio
async def test_send_alert_all_levels(alert_service):
    """Test sending alerts with all severity levels"""
    levels = [AlertLevel.INFO, AlertLevel.WARNING, AlertLevel.ERROR, AlertLevel.CRITICAL]

    with (
        patch.object(alert_service, "_log_alert") as mock_log,
        patch.object(alert_service, "_send_slack_alert", new_callable=AsyncMock),
        patch.object(alert_service, "_send_discord_alert", new_callable=AsyncMock),
    ):
        for level in levels:
            result = await alert_service.send_alert(
                title=f"Test {level.value}", message="Test", level=level
            )
            assert result["logging"] is True

        assert mock_log.call_count == len(levels)


# ============================================================================
# Tests: _log_alert
# ============================================================================


def test_log_alert_critical(alert_service):
    """Test logging critical alerts"""
    with patch("services.alert_service.logger") as mock_logger:
        alert_service._log_alert("Critical Alert", "Critical message", AlertLevel.CRITICAL)
        mock_logger.critical.assert_called_once()


def test_log_alert_error(alert_service):
    """Test logging error alerts"""
    with patch("services.alert_service.logger") as mock_logger:
        alert_service._log_alert("Error Alert", "Error message", AlertLevel.ERROR)
        mock_logger.error.assert_called_once()


def test_log_alert_warning(alert_service):
    """Test logging warning alerts"""
    with patch("services.alert_service.logger") as mock_logger:
        alert_service._log_alert("Warning Alert", "Warning message", AlertLevel.WARNING)
        mock_logger.warning.assert_called_once()


def test_log_alert_info(alert_service):
    """Test logging info alerts"""
    with patch("services.alert_service.logger") as mock_logger:
        alert_service._log_alert("Info Alert", "Info message", AlertLevel.INFO)
        mock_logger.info.assert_called_once()


def test_log_alert_with_metadata(alert_service):
    """Test logging alerts with metadata"""
    with patch("services.alert_service.logger") as mock_logger:
        alert_service._log_alert(
            "Test Alert", "Test message", AlertLevel.INFO, metadata={"key": "value", "num": 123}
        )
        call_args = mock_logger.info.call_args[0][0]
        assert "Metadata: {'key': 'value', 'num': 123}" in call_args


# ============================================================================
# Tests: _send_slack_alert
# ============================================================================


@pytest.mark.asyncio
async def test_send_slack_alert_success(alert_service):
    """Test sending Slack alert successfully"""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        await alert_service._send_slack_alert(
            title="Test Alert",
            message="Test message",
            level=AlertLevel.ERROR,
            metadata={"key": "value"},
        )

        mock_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_send_slack_alert_no_webhook(alert_service_no_webhooks):
    """Test sending Slack alert without webhook"""
    await alert_service_no_webhooks._send_slack_alert(
        title="Test", message="Test", level=AlertLevel.INFO
    )
    # Should return without error


@pytest.mark.asyncio
async def test_send_slack_alert_all_levels(alert_service):
    """Test Slack alert colors for all levels"""
    color_map = {
        AlertLevel.INFO: "#36a64f",
        AlertLevel.WARNING: "#ff9800",
        AlertLevel.ERROR: "#f44336",
        AlertLevel.CRITICAL: "#9c27b0",
    }

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        for level, expected_color in color_map.items():
            await alert_service._send_slack_alert("Test", "Test", level)
            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            attachment = payload["attachments"][0]
            assert attachment["color"] == expected_color


@pytest.mark.asyncio
async def test_send_slack_alert_with_metadata(alert_service):
    """Test Slack alert with metadata fields"""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        await alert_service._send_slack_alert(
            "Test", "Test", AlertLevel.INFO, metadata={"status_code": 500, "path": "/api/test"}
        )

        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        fields = payload["attachments"][0]["fields"]
        assert len(fields) > 2  # Level, Time, plus metadata fields


# ============================================================================
# Tests: _send_discord_alert
# ============================================================================


@pytest.mark.asyncio
async def test_send_discord_alert_success(alert_service):
    """Test sending Discord alert successfully"""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        await alert_service._send_discord_alert(
            title="Test Alert",
            message="Test message",
            level=AlertLevel.ERROR,
            metadata={"key": "value"},
        )

        mock_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_send_discord_alert_no_webhook(alert_service_no_webhooks):
    """Test sending Discord alert without webhook"""
    await alert_service_no_webhooks._send_discord_alert(
        title="Test", message="Test", level=AlertLevel.INFO
    )
    # Should return without error


@pytest.mark.asyncio
async def test_send_discord_alert_all_levels(alert_service):
    """Test Discord alert colors for all levels"""
    color_map = {
        AlertLevel.INFO: 0x36A64F,
        AlertLevel.WARNING: 0xFF9800,
        AlertLevel.ERROR: 0xF44336,
        AlertLevel.CRITICAL: 0x9C27B0,
    }

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client:
        mock_post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        for level, expected_color in color_map.items():
            await alert_service._send_discord_alert("Test", "Test", level)
            call_args = mock_post.call_args
            payload = call_args[1]["json"]
            embed = payload["embeds"][0]
            assert embed["color"] == expected_color


# ============================================================================
# Tests: send_http_error_alert
# ============================================================================


@pytest.mark.asyncio
async def test_send_http_error_alert_500(alert_service):
    """Test HTTP error alert for 500 status"""
    with patch.object(alert_service, "send_alert", new_callable=AsyncMock) as mock_send:
        await alert_service.send_http_error_alert(
            status_code=500,
            method="POST",
            path="/api/test",
            error_detail="Internal server error",
            request_id="req-123",
            user_agent="Mozilla/5.0",
        )

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["level"] == AlertLevel.ERROR
        assert "500" in call_kwargs["title"]
        assert call_kwargs["metadata"]["status_code"] == 500
        assert call_kwargs["metadata"]["method"] == "POST"
        assert call_kwargs["metadata"]["path"] == "/api/test"


@pytest.mark.asyncio
async def test_send_http_error_alert_503_critical(alert_service):
    """Test HTTP error alert for 503 status (critical)"""
    with patch.object(alert_service, "send_alert", new_callable=AsyncMock) as mock_send:
        await alert_service.send_http_error_alert(status_code=503, method="GET", path="/health")

        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["level"] == AlertLevel.CRITICAL


@pytest.mark.asyncio
async def test_send_http_error_alert_400_warning(alert_service):
    """Test HTTP error alert for 400 status (warning)"""
    with patch.object(alert_service, "send_alert", new_callable=AsyncMock) as mock_send:
        await alert_service.send_http_error_alert(status_code=400, method="POST", path="/api/test")

        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["level"] == AlertLevel.WARNING


@pytest.mark.asyncio
async def test_send_http_error_alert_long_user_agent(alert_service):
    """Test HTTP error alert truncates long user agent"""
    long_ua = "A" * 200
    with patch.object(alert_service, "send_alert", new_callable=AsyncMock) as mock_send:
        await alert_service.send_http_error_alert(
            status_code=500, method="GET", path="/test", user_agent=long_ua
        )

        call_kwargs = mock_send.call_args[1]
        assert len(call_kwargs["metadata"]["user_agent"]) == 100


@pytest.mark.asyncio
async def test_send_http_error_alert_long_error_detail(alert_service):
    """Test HTTP error alert truncates long error detail"""
    long_error = "A" * 1000
    with patch.object(alert_service, "send_alert", new_callable=AsyncMock) as mock_send:
        await alert_service.send_http_error_alert(
            status_code=500, method="GET", path="/test", error_detail=long_error
        )

        call_kwargs = mock_send.call_args[1]
        assert len(call_kwargs["metadata"]["error_detail"]) == 500


# ============================================================================
# Tests: get_alert_service (singleton)
# ============================================================================


def test_get_alert_service_singleton():
    """Test get_alert_service returns singleton"""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.slack_webhook_url = None
        mock_settings.discord_webhook_url = None

        # Clear singleton
        import services.alert_service

        services.alert_service._alert_service = None

        service1 = get_alert_service()
        service2 = get_alert_service()

        assert service1 is service2
        assert isinstance(service1, AlertService)
