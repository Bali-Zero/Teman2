"""
Unit tests for HealthMonitor Service
Tests health monitoring and alert functionality
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.alert_service import AlertLevel, AlertService
from services.health_monitor import HealthMonitor, get_health_monitor, init_health_monitor


@pytest.mark.unit
class TestHealthMonitorInit:
    """Test HealthMonitor initialization"""

    def test_init_with_alert_service(self):
        """Test initialization with alert service"""
        mock_alert = MagicMock(spec=AlertService)
        monitor = HealthMonitor(mock_alert, check_interval=30)

        assert monitor.alert_service == mock_alert
        assert monitor.check_interval == 30
        assert monitor.running is False
        assert monitor.last_status == {}
        assert monitor.last_alert_time == {}

    def test_init_default_interval(self):
        """Test initialization with default interval"""
        mock_alert = MagicMock(spec=AlertService)
        monitor = HealthMonitor(mock_alert)

        assert monitor.check_interval == 60  # Default


@pytest.mark.unit
class TestHealthMonitorLifecycle:
    """Test HealthMonitor start/stop lifecycle"""

    @pytest.mark.asyncio
    async def test_start_monitoring(self):
        """Test starting monitoring"""
        mock_alert = MagicMock(spec=AlertService)
        monitor = HealthMonitor(mock_alert, check_interval=1)

        await monitor.start()

        assert monitor.running is True
        assert monitor.task is not None

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_monitoring(self):
        """Test stopping monitoring"""
        mock_alert = MagicMock(spec=AlertService)
        monitor = HealthMonitor(mock_alert, check_interval=1)

        await monitor.start()
        await monitor.stop()

        assert monitor.running is False

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """Test starting when already running"""
        mock_alert = MagicMock(spec=AlertService)
        monitor = HealthMonitor(mock_alert, check_interval=1)

        await monitor.start()
        await monitor.start()  # Should not raise

        await monitor.stop()


@pytest.mark.unit
class TestHealthMonitorServiceInjection:
    """Test service injection"""

    def test_set_services(self):
        """Test injecting services"""
        mock_alert = MagicMock(spec=AlertService)
        monitor = HealthMonitor(mock_alert)

        mock_memory = MagicMock()
        mock_router = MagicMock()
        mock_tools = MagicMock()

        monitor.set_services(
            memory_service=mock_memory, intelligent_router=mock_router, tool_executor=mock_tools
        )

        assert monitor.memory_service == mock_memory
        assert monitor.intelligent_router == mock_router
        assert monitor.tool_executor == mock_tools


@pytest.mark.unit
class TestHealthMonitorChecks:
    """Test health check methods"""

    @pytest.mark.asyncio
    async def test_check_qdrant_with_service(self):
        """Test Qdrant check with service"""
        mock_alert = MagicMock(spec=AlertService)
        monitor = HealthMonitor(mock_alert)

        mock_search = MagicMock()
        mock_search.client = MagicMock()
        mock_search.client.list_collections = MagicMock(return_value=["collection1", "collection2"])

        result = await monitor._check_qdrant(mock_search)

        assert result is True

    @pytest.mark.asyncio
    async def test_check_qdrant_no_service(self):
        """Test Qdrant check without service"""
        mock_alert = MagicMock(spec=AlertService)
        monitor = HealthMonitor(mock_alert)

        result = await monitor._check_qdrant(None)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_qdrant_error(self):
        """Test Qdrant check with error"""
        mock_alert = MagicMock(spec=AlertService)
        monitor = HealthMonitor(mock_alert)

        mock_search = MagicMock()
        mock_search.client = MagicMock()
        mock_search.client.list_collections = MagicMock(side_effect=Exception("Connection error"))

        result = await monitor._check_qdrant(mock_search)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_postgresql_with_service(self):
        """Test PostgreSQL check with service"""
        mock_alert = MagicMock(spec=AlertService)
        monitor = HealthMonitor(mock_alert)

        mock_memory = MagicMock()
        mock_memory.use_postgres = True
        mock_memory.pool = MagicMock()

        result = await monitor._check_postgresql(mock_memory)

        assert result is True

    @pytest.mark.asyncio
    async def test_check_postgresql_no_service(self):
        """Test PostgreSQL check without service"""
        mock_alert = MagicMock(spec=AlertService)
        monitor = HealthMonitor(mock_alert)

        result = await monitor._check_postgresql(None)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_postgresql_not_using_postgres(self):
        """Test PostgreSQL check when not using postgres"""
        mock_alert = MagicMock(spec=AlertService)
        monitor = HealthMonitor(mock_alert)

        mock_memory = MagicMock()
        mock_memory.use_postgres = False

        result = await monitor._check_postgresql(mock_memory)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_ai_router_with_service(self):
        """Test AI Router check with service"""
        mock_alert = MagicMock(spec=AlertService)
        monitor = HealthMonitor(mock_alert)

        mock_router = MagicMock()
        mock_router.llama_client = MagicMock()

        result = await monitor._check_ai_router(mock_router)

        assert result is True

    @pytest.mark.asyncio
    async def test_check_ai_router_no_service(self):
        """Test AI Router check without service"""
        mock_alert = MagicMock(spec=AlertService)
        monitor = HealthMonitor(mock_alert)

        result = await monitor._check_ai_router(None)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_ai_router_no_clients(self):
        """Test AI Router check without clients"""
        mock_alert = MagicMock(spec=AlertService)
        monitor = HealthMonitor(mock_alert)

        mock_router = MagicMock()
        mock_router.llama_client = None
        mock_router.haiku_client = None

        result = await monitor._check_ai_router(mock_router)

        assert result is False


@pytest.mark.unit
class TestHealthMonitorAlerts:
    """Test alert sending"""

    @pytest.mark.asyncio
    async def test_send_downtime_alert(self):
        """Test sending downtime alert"""
        mock_alert = MagicMock(spec=AlertService)
        mock_alert.send_alert = AsyncMock()

        monitor = HealthMonitor(mock_alert)

        await monitor._send_downtime_alert("qdrant")

        mock_alert.send_alert.assert_called_once()
        call_kwargs = mock_alert.send_alert.call_args[1]
        assert call_kwargs["level"] == AlertLevel.CRITICAL
        assert "qdrant" in call_kwargs["title"]

    @pytest.mark.asyncio
    async def test_send_downtime_alert_cooldown(self):
        """Test downtime alert cooldown"""
        from datetime import datetime, timedelta

        mock_alert = MagicMock(spec=AlertService)
        mock_alert.send_alert = AsyncMock()

        monitor = HealthMonitor(mock_alert)
        monitor.last_alert_time["down_qdrant"] = datetime.now() - timedelta(minutes=1)

        await monitor._send_downtime_alert("qdrant")

        # Should not send due to cooldown
        mock_alert.send_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_recovery_alert(self):
        """Test sending recovery alert"""
        mock_alert = MagicMock(spec=AlertService)
        mock_alert.send_alert = AsyncMock()

        monitor = HealthMonitor(mock_alert)

        await monitor._send_recovery_alert("postgresql")

        mock_alert.send_alert.assert_called_once()
        call_kwargs = mock_alert.send_alert.call_args[1]
        assert call_kwargs["level"] == AlertLevel.INFO
        assert "postgresql" in call_kwargs["title"]


@pytest.mark.unit
class TestHealthMonitorStatus:
    """Test status reporting"""

    def test_get_status(self):
        """Test getting status"""
        mock_alert = MagicMock(spec=AlertService)
        monitor = HealthMonitor(mock_alert, check_interval=30)
        monitor.running = True
        monitor.last_status = {"qdrant": True, "postgresql": False}

        status = monitor.get_status()

        assert status["running"] is True
        assert status["check_interval"] == 30
        assert status["last_status"] == {"qdrant": True, "postgresql": False}


@pytest.mark.unit
class TestHealthMonitorSingleton:
    """Test singleton functions"""

    def test_get_health_monitor_none(self):
        """Test get_health_monitor when not initialized"""
        # Clear singleton
        import services.health_monitor

        services.health_monitor._health_monitor = None

        result = get_health_monitor()
        assert result is None

    def test_init_health_monitor(self):
        """Test initializing health monitor"""
        mock_alert = MagicMock(spec=AlertService)

        # Clear singleton
        import services.health_monitor

        services.health_monitor._health_monitor = None

        monitor = init_health_monitor(mock_alert, check_interval=45)

        assert isinstance(monitor, HealthMonitor)
        assert monitor.check_interval == 45
        assert get_health_monitor() == monitor
