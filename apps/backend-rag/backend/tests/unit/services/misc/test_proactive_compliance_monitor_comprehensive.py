"""
Unit tests for ProactiveComplianceMonitor
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.proactive_compliance_monitor import ProactiveComplianceMonitor


@pytest.fixture
def compliance_monitor():
    """Create ProactiveComplianceMonitor instance"""
    mock_search = MagicMock()
    mock_notification = MagicMock()
    return ProactiveComplianceMonitor(
        search_service=mock_search, notification_service=mock_notification
    )


class TestProactiveComplianceMonitor:
    """Tests for ProactiveComplianceMonitor"""

    def test_init(self):
        """Test initialization"""
        monitor = ProactiveComplianceMonitor()
        assert monitor.compliance_tracker is not None
        assert monitor.alert_generator is not None
        assert monitor.severity_calculator is not None

    def test_init_with_services(self):
        """Test initialization with services"""
        mock_search = MagicMock()
        mock_notification = MagicMock()
        monitor = ProactiveComplianceMonitor(
            search_service=mock_search, notification_service=mock_notification
        )
        assert monitor.search == mock_search
        assert monitor.notification_service == mock_notification

    @pytest.mark.asyncio
    async def test_start(self, compliance_monitor):
        """Test starting monitor"""
        await compliance_monitor.start()
        assert compliance_monitor.running is True

    @pytest.mark.asyncio
    async def test_stop(self, compliance_monitor):
        """Test stopping monitor"""
        compliance_monitor.running = True
        await compliance_monitor.stop()
        assert compliance_monitor.running is False

    def test_add_compliance_item(self, compliance_monitor):
        """Test adding compliance item"""
        item = compliance_monitor.add_compliance_item(
            client_id="client1",
            compliance_type="visa_expiry",
            title="KITAS Expiry",
            deadline="2024-12-31",
            description="KITAS expiry",
        )
        assert item is not None

    def test_check_compliance_items(self, compliance_monitor):
        """Test checking compliance items"""
        alerts = compliance_monitor.check_compliance_items()
        assert isinstance(alerts, list)

    def test_get_monitor_stats(self, compliance_monitor):
        """Test getting monitor statistics"""
        stats = compliance_monitor.get_monitor_stats()
        assert isinstance(stats, dict)
