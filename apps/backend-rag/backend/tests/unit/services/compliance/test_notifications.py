"""
Unit tests for ComplianceNotificationService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.compliance.notifications import ComplianceNotificationService
from services.compliance.alert_generator import ComplianceAlert, AlertStatus
from services.compliance.severity_calculator import AlertSeverity


@pytest.fixture
def mock_notification_service():
    """Mock notification service"""
    service = MagicMock()
    service.send = AsyncMock(return_value=True)
    return service


@pytest.fixture
def notification_service(mock_notification_service):
    """Create ComplianceNotificationService instance"""
    return ComplianceNotificationService(notification_service=mock_notification_service)


@pytest.fixture
def mock_alert():
    """Create mock compliance alert"""
    return ComplianceAlert(
        alert_id="alert1",
        compliance_item_id="item1",
        client_id="client1",
        severity=AlertSeverity.WARNING,
        title="Test Alert",
        message="Test message",
        deadline="2025-12-31",
        days_until_deadline=15,
        action_required="Take action"
    )


class TestComplianceNotificationService:
    """Tests for ComplianceNotificationService"""

    def test_init(self, mock_notification_service):
        """Test initialization"""
        service = ComplianceNotificationService(notification_service=mock_notification_service)
        assert service.notification_service == mock_notification_service

    @pytest.mark.asyncio
    async def test_send_alert(self, notification_service, mock_notification_service):
        """Test sending alert"""
        result = await notification_service.send_alert(
            alert_id="alert1",
            client_id="client1",
            message="Test message",
            via="whatsapp"
        )
        assert result is True
        mock_notification_service.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_alert_email(self, notification_service, mock_notification_service):
        """Test sending alert via email"""
        result = await notification_service.send_alert(
            alert_id="alert1",
            client_id="client1",
            message="Test message",
            via="email"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_send_alert_no_service(self):
        """Test sending alert without notification service"""
        service = ComplianceNotificationService()
        result = await service.send_alert(
            alert_id="alert1",
            client_id="client1",
            message="Test message"
        )
        assert result is True  # Should log only
