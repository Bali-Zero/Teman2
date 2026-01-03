"""
Unit tests for AlertService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.monitoring.alert_service import AlertLevel, AlertService


@pytest.fixture
def alert_service():
    """Create AlertService instance"""
    with patch('app.core.config.settings') as mock_settings:
        mock_settings.slack_webhook_url = None
        mock_settings.discord_webhook_url = None
        service = AlertService()
        return service


class TestAlertService:
    """Tests for AlertService"""

    def test_init(self):
        """Test initialization"""
        with patch('app.core.config.settings') as mock_settings:
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
            title="Test Alert",
            message="Test message",
            level=AlertLevel.ERROR
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
            metadata={"key": "value"}
        )
        assert results["logging"] is True

    @pytest.mark.asyncio
    async def test_send_alert_critical(self, alert_service):
        """Test sending critical alert"""
        results = await alert_service.send_alert(
            title="Critical Alert",
            message="Critical message",
            level=AlertLevel.CRITICAL
        )
        assert results["logging"] is True

    @pytest.mark.asyncio
    async def test_send_alert_info(self, alert_service):
        """Test sending info alert"""
        results = await alert_service.send_alert(
            title="Info Alert",
            message="Info message",
            level=AlertLevel.INFO
        )
        assert results["logging"] is True

