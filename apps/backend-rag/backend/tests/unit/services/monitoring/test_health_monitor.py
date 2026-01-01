"""
Unit tests for HealthMonitor
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.monitoring.health_monitor import HealthMonitor
from services.monitoring.alert_service import AlertService


@pytest.fixture
def mock_alert_service():
    """Mock AlertService"""
    return MagicMock(spec=AlertService)


@pytest.fixture
def health_monitor(mock_alert_service):
    """Create HealthMonitor instance"""
    return HealthMonitor(alert_service=mock_alert_service, check_interval=60)


class TestHealthMonitor:
    """Tests for HealthMonitor"""

    def test_init(self, mock_alert_service):
        """Test initialization"""
        monitor = HealthMonitor(alert_service=mock_alert_service, check_interval=60)
        assert monitor.alert_service == mock_alert_service
        assert monitor.check_interval == 60
        assert monitor.running is False

    @pytest.mark.asyncio
    async def test_start(self, health_monitor):
        """Test starting monitor"""
        await health_monitor.start()
        assert health_monitor.running is True

    @pytest.mark.asyncio
    async def test_stop(self, health_monitor):
        """Test stopping monitor"""
        import asyncio
        health_monitor.running = True
        
        # Create a real task that can be cancelled
        async def dummy_task():
            while True:
                await asyncio.sleep(1)
        
        health_monitor.task = asyncio.create_task(dummy_task())
        await health_monitor.stop()
        assert health_monitor.running is False

    def test_set_services(self, health_monitor):
        """Test setting services"""
        mock_memory = MagicMock()
        mock_router = MagicMock()
        mock_executor = MagicMock()
        
        health_monitor.set_services(
            memory_service=mock_memory,
            intelligent_router=mock_router,
            tool_executor=mock_executor
        )
        assert health_monitor.memory_service == mock_memory
        assert health_monitor.intelligent_router == mock_router
        assert health_monitor.tool_executor == mock_executor

    def test_get_status(self, health_monitor):
        """Test getting status"""
        status = health_monitor.get_status()
        assert isinstance(status, dict)
        assert "running" in status
