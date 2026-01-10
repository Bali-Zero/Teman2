"""
Unit tests for AlertService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.monitoring.alert_service import AlertLevel, AlertService


@pytest.fixture
def alert_service():
    """Create AlertService instance"""
    with patch("backend.app.core.config.settings") as mock_settings:
        mock_settings.slack_webhook_url = None
        mock_settings.discord_webhook_url = None
        service = AlertService()
        return service


class TestAlertService:
    """Tests for AlertService"""

    def test_init(self):
        """Test initialization"""
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.slack_webhook_url = None
            mock_settings.discord_webhook_url = None
            service = AlertService()
            assert service.enable_logging is True
            assert service.enable_slack is False
            assert service.enable_discord is False

    @pytest.mark.asyncio
    async def test_send_alert_logging_only(self, alert_service):
        """Test sending alert with logging only"""
        results = await alert_service.send_alert(
            title="Test Alert", message="Test message", level=AlertLevel.ERROR
        )
        assert results["logging"] is True
        assert results["slack"] is False
        assert results["discord"] is False

    @pytest.mark.asyncio
    async def test_send_alert_with_metadata(self, alert_service):
        """Test sending alert with metadata"""
        results = await alert_service.send_alert(
            title="Test Alert",
            message="Test message",
            level=AlertLevel.WARNING,
            metadata={"key": "value"},
        )
        assert results["logging"] is True

    @pytest.mark.asyncio
    async def test_send_alert_critical(self, alert_service):
        """Test sending critical alert"""
        results = await alert_service.send_alert(
            title="Critical Alert", message="Critical message", level=AlertLevel.CRITICAL
        )
        assert results["logging"] is True

    @pytest.mark.asyncio
    async def test_send_alert_info(self, alert_service):
        """Test sending info alert"""
        results = await alert_service.send_alert(
            title="Info Alert", message="Info message", level=AlertLevel.INFO
        )
        assert results["logging"] is True

    @pytest.mark.asyncio
    async def test_send_alert_with_slack(self):
        """Test sending alert with Slack enabled"""
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.slack_webhook_url = "https://hooks.slack.com/test"
            mock_settings.discord_webhook_url = None
            service = AlertService()
            assert service.enable_slack is True

            with patch("httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_response
                )

                results = await service.send_alert(
                    title="Test Alert", message="Test message", level=AlertLevel.ERROR
                )
                assert results["logging"] is True
                assert results["slack"] is True

    @pytest.mark.asyncio
    async def test_send_alert_with_discord(self):
        """Test sending alert with Discord enabled"""
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.slack_webhook_url = None
            mock_settings.discord_webhook_url = "https://discord.com/api/webhooks/test"
            service = AlertService()
            assert service.enable_discord is True

            with patch("httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_response
                )

                results = await service.send_alert(
                    title="Test Alert", message="Test message", level=AlertLevel.ERROR
                )
                assert results["logging"] is True
                assert results["discord"] is True

    @pytest.mark.asyncio
    async def test_send_alert_all_channels(self):
        """Test sending alert to all channels"""
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.slack_webhook_url = "https://hooks.slack.com/test"
            mock_settings.discord_webhook_url = "https://discord.com/api/webhooks/test"
            service = AlertService()

            with patch("httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    return_value=mock_response
                )

                results = await service.send_alert(
                    title="Test Alert",
                    message="Test message",
                    level=AlertLevel.WARNING,
                    metadata={"key": "value"},
                )
                assert results["logging"] is True
                assert results["slack"] is True
                assert results["discord"] is True

    @pytest.mark.asyncio
    async def test_send_alert_slack_error(self):
        """Test sending alert when Slack fails"""
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.slack_webhook_url = "https://hooks.slack.com/test"
            mock_settings.discord_webhook_url = None
            service = AlertService()

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    side_effect=Exception("Network error")
                )

                results = await service.send_alert(
                    title="Test Alert", message="Test message", level=AlertLevel.ERROR
                )
                assert results["logging"] is True
                assert results["slack"] is False  # Failed

    @pytest.mark.asyncio
    async def test_send_alert_discord_error(self):
        """Test sending alert when Discord fails"""
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.slack_webhook_url = None
            mock_settings.discord_webhook_url = "https://discord.com/api/webhooks/test"
            service = AlertService()

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                    side_effect=Exception("Network error")
                )

                results = await service.send_alert(
                    title="Test Alert", message="Test message", level=AlertLevel.ERROR
                )
                assert results["logging"] is True
                assert results["discord"] is False  # Failed

    @pytest.mark.asyncio
    async def test_send_http_error_alert(self):
        """Test sending HTTP error alert"""
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.slack_webhook_url = None
            mock_settings.discord_webhook_url = None
            service = AlertService()

            results = await service.send_http_error_alert(
                status_code=500,
                method="POST",
                path="/api/test",
                error_detail="Internal error",
                request_id="req-123",
                user_agent="Mozilla/5.0",
            )
            assert results["logging"] is True

    @pytest.mark.asyncio
    async def test_send_http_error_alert_4xx(self):
        """Test sending HTTP 4xx error alert (WARNING level)"""
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.slack_webhook_url = None
            mock_settings.discord_webhook_url = None
            service = AlertService()

            results = await service.send_http_error_alert(
                status_code=404, method="GET", path="/api/notfound"
            )
            assert results["logging"] is True

    @pytest.mark.asyncio
    async def test_send_http_error_alert_503(self):
        """Test sending HTTP 503 error alert (CRITICAL level)"""
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.slack_webhook_url = None
            mock_settings.discord_webhook_url = None
            service = AlertService()

            results = await service.send_http_error_alert(
                status_code=503, method="GET", path="/api/service"
            )
            assert results["logging"] is True

    @pytest.mark.asyncio
    async def test_send_latency_alert(self):
        """Test sending latency alert"""
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.slack_webhook_url = None
            mock_settings.discord_webhook_url = None
            service = AlertService()

            results = await service.send_latency_alert(
                duration_ms=2000.0,
                method="POST",
                path="/api/slow",
                threshold_ms=1000.0,
                request_id="req-456",
                user_agent="Mozilla/5.0",
            )
            assert results["logging"] is True

    @pytest.mark.asyncio
    async def test_send_alert_logging_error(self):
        """Test sending alert when logging fails"""
        with patch("backend.app.core.config.settings") as mock_settings:
            mock_settings.slack_webhook_url = None
            mock_settings.discord_webhook_url = None
            service = AlertService()

            with patch.object(service, "_log_alert", side_effect=Exception("Logging error")):
                results = await service.send_alert(
                    title="Test Alert", message="Test message", level=AlertLevel.ERROR
                )
                assert results["logging"] is False  # Failed
