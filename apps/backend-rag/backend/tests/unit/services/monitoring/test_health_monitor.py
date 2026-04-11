"""
Unit tests for HealthMonitor service.
Covers: initialization, service checks (qdrant, postgresql, ai_router),
resource monitoring, alert logic, status reporting, module-level helpers.
"""

import asyncio
import os
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1")
os.environ.setdefault("OPENAI_API_KEY", "test_key")
os.environ.setdefault("GOOGLE_API_KEY", "test_key")

from backend.services.monitoring.health_monitor import (
    HealthMonitor,
    get_health_monitor,
    init_health_monitor,
)


@pytest.fixture
def mock_alert_service() -> MagicMock:
    svc = MagicMock()
    svc.send_alert = AsyncMock()
    svc.send_resource_alert = AsyncMock()
    return svc


@pytest.fixture
def monitor(mock_alert_service: MagicMock) -> HealthMonitor:
    return HealthMonitor(alert_service=mock_alert_service, check_interval=5)


# --------------------------------------------------------------------------- #
# Initialization
# --------------------------------------------------------------------------- #

class TestInit:
    def test_defaults(self, monitor: HealthMonitor) -> None:
        assert monitor.check_interval == 5
        assert monitor.running is False
        assert monitor.task is None
        assert monitor.last_status == {}
        assert monitor.memory_service is None

    def test_set_services(self, monitor: HealthMonitor) -> None:
        mem = MagicMock()
        router = MagicMock()
        tools = MagicMock()
        app = MagicMock()
        monitor.set_services(memory_service=mem, intelligent_router=router,
                             tool_executor=tools, app_state=app)
        assert monitor.memory_service is mem
        assert monitor.intelligent_router is router
        assert monitor.tool_executor is tools
        assert monitor.app_state is app


# --------------------------------------------------------------------------- #
# HTTP client management
# --------------------------------------------------------------------------- #

class TestClientManagement:
    def test_get_client_creates_once(self, monitor: HealthMonitor) -> None:
        with patch("backend.services.monitoring.health_monitor.httpx") as mock_httpx:
            mock_client = MagicMock()
            mock_client.is_closed = False
            mock_httpx.AsyncClient.return_value = mock_client
            mock_httpx.Limits.return_value = MagicMock()

            c1 = monitor._get_client()
            c2 = monitor._get_client()
            assert c1 is c2
            mock_httpx.AsyncClient.assert_called_once()

    def test_get_client_recreates_if_closed(self, monitor: HealthMonitor) -> None:
        with patch("backend.services.monitoring.health_monitor.httpx") as mock_httpx:
            new_client = MagicMock()
            new_client.is_closed = False
            mock_httpx.AsyncClient.return_value = new_client
            mock_httpx.Limits.return_value = MagicMock()

            closed_client = MagicMock()
            closed_client.is_closed = True
            monitor._client = closed_client

            result = monitor._get_client()
            assert result is new_client
            mock_httpx.AsyncClient.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_client(self, monitor: HealthMonitor) -> None:
        mock_client = AsyncMock()
        mock_client.is_closed = False
        monitor._client = mock_client
        await monitor.close()
        mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_no_client(self, monitor: HealthMonitor) -> None:
        # Should not raise
        await monitor.close()


# --------------------------------------------------------------------------- #
# Cold start tracking
# --------------------------------------------------------------------------- #

class TestColdStart:
    def test_record_first_request(self, monitor: HealthMonitor) -> None:
        assert monitor._first_request_seen is False
        monitor.record_first_request()
        assert monitor._first_request_seen is True
        assert monitor._cold_start_duration is not None
        assert monitor._cold_start_duration >= 0

    def test_record_first_request_idempotent(self, monitor: HealthMonitor) -> None:
        monitor.record_first_request()
        first_duration = monitor._cold_start_duration
        monitor.record_first_request()
        assert monitor._cold_start_duration == first_duration


# --------------------------------------------------------------------------- #
# Start / Stop
# --------------------------------------------------------------------------- #

class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_creates_task(self, monitor: HealthMonitor) -> None:
        with patch.object(monitor, "_monitoring_loop", new_callable=AsyncMock):
            await monitor.start()
            assert monitor.running is True
            assert monitor.task is not None
            # Cleanup
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(self, monitor: HealthMonitor) -> None:
        with patch.object(monitor, "_monitoring_loop", new_callable=AsyncMock):
            await monitor.start()
            task1 = monitor.task
            await monitor.start()  # Should warn but not create new task
            assert monitor.task is task1
            await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self, monitor: HealthMonitor) -> None:
        with patch.object(monitor, "_monitoring_loop", new_callable=AsyncMock):
            await monitor.start()
            await monitor.stop()
            assert monitor.running is False


# --------------------------------------------------------------------------- #
# Qdrant health check
# --------------------------------------------------------------------------- #

class TestCheckQdrant:
    @pytest.mark.asyncio
    async def test_qdrant_healthy(self, monitor: HealthMonitor) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        monitor._client = mock_client

        with patch("backend.services.monitoring.health_monitor.httpx") as mock_httpx:
            mock_httpx.AsyncClient.return_value = mock_client
            mock_httpx.Limits.return_value = MagicMock()

            mock_settings = MagicMock()
            mock_settings.qdrant_url = "http://localhost:6333"
            mock_settings.qdrant_api_key = "test-key"

            with patch("backend.app.core.config.settings", mock_settings):
                result = await monitor._check_qdrant(None)
                assert result is True

    @pytest.mark.asyncio
    async def test_qdrant_unhealthy(self, monitor: HealthMonitor) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False
        monitor._client = mock_client

        mock_settings = MagicMock()
        mock_settings.qdrant_url = "http://localhost:6333"
        mock_settings.qdrant_api_key = None

        with patch("backend.app.core.config.settings", mock_settings):
            result = await monitor._check_qdrant(None)
            assert result is False

    @pytest.mark.asyncio
    async def test_qdrant_exception(self, monitor: HealthMonitor) -> None:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.is_closed = False
        monitor._client = mock_client

        mock_settings = MagicMock()
        mock_settings.qdrant_url = "http://localhost:6333"
        mock_settings.qdrant_api_key = None

        with patch("backend.app.core.config.settings", mock_settings):
            result = await monitor._check_qdrant(None)
            assert result is False


# --------------------------------------------------------------------------- #
# PostgreSQL health check
# --------------------------------------------------------------------------- #

class TestCheckPostgresql:
    @pytest.mark.asyncio
    async def test_pg_via_memory_service_pool(self, monitor: HealthMonitor) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        memory_service = MagicMock()
        memory_service.pool = mock_pool

        with patch("backend.app.core.config.settings", MagicMock(database_url="postgresql://fake")):
            result = await monitor._check_postgresql(memory_service)
            assert result is True

    @pytest.mark.asyncio
    async def test_pg_via_app_state_db_pool(self, monitor: HealthMonitor) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        app_state = MagicMock()
        app_state.db_pool = mock_pool
        app_state.memory_service = None
        monitor.app_state = app_state

        with patch("backend.app.core.config.settings", MagicMock(database_url="postgresql://fake")):
            result = await monitor._check_postgresql(None)
            assert result is True

    @pytest.mark.asyncio
    async def test_pg_all_strategies_fail(self, monitor: HealthMonitor) -> None:
        mock_settings = MagicMock()
        mock_settings.database_url = None

        with patch("backend.app.core.config.settings", mock_settings):
            result = await monitor._check_postgresql(None)
            assert result is False

    @pytest.mark.asyncio
    async def test_pg_direct_connection(self, monitor: HealthMonitor) -> None:
        mock_settings = MagicMock()
        mock_settings.database_url = "postgresql://fake"

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.close = AsyncMock()

        with patch("backend.app.core.config.settings", mock_settings):
            with patch("asyncpg.connect", new_callable=AsyncMock, return_value=mock_conn):
                result = await monitor._check_postgresql(None)
                assert result is True

    @pytest.mark.asyncio
    async def test_pg_direct_connection_fail(self, monitor: HealthMonitor) -> None:
        mock_settings = MagicMock()
        mock_settings.database_url = "postgresql://fake"

        with patch("backend.app.core.config.settings", mock_settings):
            with patch("asyncpg.connect", new_callable=AsyncMock,
                       side_effect=Exception("Connection refused")):
                result = await monitor._check_postgresql(None)
                assert result is False


# --------------------------------------------------------------------------- #
# AI Router health check
# --------------------------------------------------------------------------- #

class TestCheckAIRouter:
    @pytest.mark.asyncio
    async def test_router_none(self, monitor: HealthMonitor) -> None:
        result = await monitor._check_ai_router(None)
        assert result is False

    @pytest.mark.asyncio
    async def test_router_with_orchestrator(self, monitor: HealthMonitor) -> None:
        router = MagicMock()
        router.orchestrator = MagicMock()
        result = await monitor._check_ai_router(router)
        assert result is True

    @pytest.mark.asyncio
    async def test_router_with_llama_client(self, monitor: HealthMonitor) -> None:
        router = MagicMock(spec=[])
        router.llama_client = MagicMock()
        result = await monitor._check_ai_router(router)
        assert result is True

    @pytest.mark.asyncio
    async def test_router_no_orchestrator_no_llama(self, monitor: HealthMonitor) -> None:
        router = MagicMock(spec=[])
        # Has no orchestrator or llama_client attributes
        result = await monitor._check_ai_router(router)
        assert result is False

    @pytest.mark.asyncio
    async def test_router_from_app_state(self, monitor: HealthMonitor) -> None:
        router = MagicMock()
        router.orchestrator = MagicMock()
        app_state = MagicMock()
        app_state.intelligent_router = router
        monitor.app_state = app_state
        result = await monitor._check_ai_router(None)
        assert result is True

    @pytest.mark.asyncio
    async def test_router_exception(self, monitor: HealthMonitor) -> None:
        router = MagicMock()
        type(router).orchestrator = property(lambda self: (_ for _ in ()).throw(RuntimeError("boom")))
        result = await monitor._check_ai_router(router)
        assert result is False


# --------------------------------------------------------------------------- #
# Alert sending
# --------------------------------------------------------------------------- #

class TestAlerts:
    @pytest.mark.asyncio
    async def test_send_downtime_alert(
        self, monitor: HealthMonitor, mock_alert_service: MagicMock,
    ) -> None:
        await monitor._send_downtime_alert("qdrant")
        mock_alert_service.send_alert.assert_awaited_once()
        call_kwargs = mock_alert_service.send_alert.call_args[1]
        assert "Down" in call_kwargs["title"]

    @pytest.mark.asyncio
    async def test_send_downtime_alert_cooldown(
        self, monitor: HealthMonitor, mock_alert_service: MagicMock,
    ) -> None:
        monitor.last_alert_time["down_qdrant"] = datetime.now(tz=timezone.utc)
        await monitor._send_downtime_alert("qdrant")
        mock_alert_service.send_alert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_recovery_alert(
        self, monitor: HealthMonitor, mock_alert_service: MagicMock,
    ) -> None:
        await monitor._send_recovery_alert("postgresql")
        mock_alert_service.send_alert.assert_awaited_once()
        call_kwargs = mock_alert_service.send_alert.call_args[1]
        assert "Recovered" in call_kwargs["title"]

    @pytest.mark.asyncio
    async def test_send_resource_alert_throttled(
        self, monitor: HealthMonitor, mock_alert_service: MagicMock,
    ) -> None:
        await monitor._send_resource_alert_throttled("memory", 95.0, 80.0, unit="%")
        mock_alert_service.send_resource_alert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_resource_alert_throttled_cooldown(
        self, monitor: HealthMonitor, mock_alert_service: MagicMock,
    ) -> None:
        monitor._resource_alert_cooldown["memory"] = datetime.now(tz=timezone.utc)
        await monitor._send_resource_alert_throttled("memory", 95.0, 80.0)
        mock_alert_service.send_resource_alert.assert_not_awaited()


# --------------------------------------------------------------------------- #
# _check_health (integration of individual checks)
# --------------------------------------------------------------------------- #

class TestCheckHealth:
    @pytest.mark.asyncio
    async def test_check_health_all_healthy(
        self, monitor: HealthMonitor, mock_alert_service: MagicMock,
    ) -> None:
        monitor.tool_executor = MagicMock()
        with patch.object(monitor, "_check_qdrant", new_callable=AsyncMock, return_value=True), \
             patch.object(monitor, "_check_postgresql", new_callable=AsyncMock, return_value=True), \
             patch.object(monitor, "_check_ai_router", new_callable=AsyncMock, return_value=True), \
             patch("backend.app.dependencies.get_search_service", return_value=MagicMock()):
            await monitor._check_health()
            mock_alert_service.send_alert.assert_not_awaited()
            assert monitor.last_status["qdrant"] is True

    @pytest.mark.asyncio
    async def test_check_health_sends_downtime(
        self, monitor: HealthMonitor, mock_alert_service: MagicMock,
    ) -> None:
        monitor.last_status = {"qdrant": True, "postgresql": True, "ai_router": True, "tools": True}
        monitor.tool_executor = MagicMock()
        with patch.object(monitor, "_check_qdrant", new_callable=AsyncMock, return_value=False), \
             patch.object(monitor, "_check_postgresql", new_callable=AsyncMock, return_value=True), \
             patch.object(monitor, "_check_ai_router", new_callable=AsyncMock, return_value=True), \
             patch("backend.app.dependencies.get_search_service", return_value=MagicMock()):
            await monitor._check_health()
            mock_alert_service.send_alert.assert_awaited_once()
            assert "Down" in mock_alert_service.send_alert.call_args[1]["title"]

    @pytest.mark.asyncio
    async def test_check_health_sends_recovery(
        self, monitor: HealthMonitor, mock_alert_service: MagicMock,
    ) -> None:
        monitor.last_status = {"qdrant": False, "postgresql": True, "ai_router": True, "tools": True}
        monitor.tool_executor = MagicMock()
        with patch.object(monitor, "_check_qdrant", new_callable=AsyncMock, return_value=True), \
             patch.object(monitor, "_check_postgresql", new_callable=AsyncMock, return_value=True), \
             patch.object(monitor, "_check_ai_router", new_callable=AsyncMock, return_value=True), \
             patch("backend.app.dependencies.get_search_service", return_value=MagicMock()):
            await monitor._check_health()
            mock_alert_service.send_alert.assert_awaited_once()
            assert "Recovered" in mock_alert_service.send_alert.call_args[1]["title"]

    @pytest.mark.asyncio
    async def test_check_health_search_service_exception(
        self, monitor: HealthMonitor,
    ) -> None:
        """get_search_service raising should not crash _check_health."""
        monitor.tool_executor = MagicMock()
        with patch.object(monitor, "_check_qdrant", new_callable=AsyncMock, return_value=True), \
             patch.object(monitor, "_check_postgresql", new_callable=AsyncMock, return_value=True), \
             patch.object(monitor, "_check_ai_router", new_callable=AsyncMock, return_value=True), \
             patch("backend.app.dependencies.get_search_service",
                   side_effect=Exception("not init")):
            await monitor._check_health()  # Should not raise


# --------------------------------------------------------------------------- #
# Resource monitoring
# --------------------------------------------------------------------------- #

class TestCheckResources:
    @pytest.mark.asyncio
    async def test_check_resources_normal(
        self, monitor: HealthMonitor, mock_alert_service: MagicMock,
    ) -> None:
        mock_process = MagicMock()
        mock_mem_info = MagicMock()
        mock_mem_info.rss = 500 * 1024 * 1024  # 500MB
        mock_process.memory_info.return_value = mock_mem_info
        mock_process.cpu_percent.return_value = 10.0

        mock_settings = MagicMock()
        mock_settings.memory_alert_threshold_percent = 80
        mock_settings.cpu_alert_threshold_percent = 90

        with patch("psutil.Process", return_value=mock_process), \
             patch("backend.app.core.config.settings", mock_settings), \
             patch.object(monitor, "_check_db_pool_saturation", new_callable=AsyncMock), \
             patch.object(monitor, "_check_pg_health", new_callable=AsyncMock), \
             patch.object(monitor, "_update_resource_metrics"):
            await monitor._check_resources()
            mock_alert_service.send_resource_alert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_check_resources_memory_alert(
        self, monitor: HealthMonitor, mock_alert_service: MagicMock,
    ) -> None:
        mock_process = MagicMock()
        mock_mem_info = MagicMock()
        mock_mem_info.rss = 3800 * 1024 * 1024  # 3800MB of 4096MB = ~93%
        mock_process.memory_info.return_value = mock_mem_info
        mock_process.cpu_percent.return_value = 10.0

        mock_settings = MagicMock()
        mock_settings.memory_alert_threshold_percent = 80
        mock_settings.cpu_alert_threshold_percent = 90

        with patch("psutil.Process", return_value=mock_process), \
             patch("backend.app.core.config.settings", mock_settings), \
             patch.object(monitor, "_check_db_pool_saturation", new_callable=AsyncMock), \
             patch.object(monitor, "_check_pg_health", new_callable=AsyncMock), \
             patch.object(monitor, "_update_resource_metrics"):
            await monitor._check_resources()
            mock_alert_service.send_resource_alert.assert_awaited()

    @pytest.mark.asyncio
    async def test_check_resources_exception_noncritical(self, monitor: HealthMonitor) -> None:
        with patch("psutil.Process", side_effect=Exception("no proc")), \
             patch("backend.app.core.config.settings", MagicMock()):
            # Should not raise
            await monitor._check_resources()


# --------------------------------------------------------------------------- #
# DB pool saturation
# --------------------------------------------------------------------------- #

class TestDBPoolSaturation:
    @pytest.mark.asyncio
    async def test_no_app_state(self, monitor: HealthMonitor) -> None:
        monitor.app_state = None
        await monitor._check_db_pool_saturation()  # Should not raise

    @pytest.mark.asyncio
    async def test_pool_below_threshold(
        self, monitor: HealthMonitor, mock_alert_service: MagicMock,
    ) -> None:
        mock_pool = MagicMock()
        mock_pool.get_size.return_value = 5
        mock_pool.get_max_size.return_value = 20
        app_state = MagicMock()
        app_state.db_pool = mock_pool
        monitor.app_state = app_state
        await monitor._check_db_pool_saturation()
        mock_alert_service.send_resource_alert.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pool_above_threshold(
        self, monitor: HealthMonitor, mock_alert_service: MagicMock,
    ) -> None:
        mock_pool = MagicMock()
        mock_pool.get_size.return_value = 18
        mock_pool.get_max_size.return_value = 20
        app_state = MagicMock()
        app_state.db_pool = mock_pool
        monitor.app_state = app_state
        await monitor._check_db_pool_saturation()
        mock_alert_service.send_resource_alert.assert_awaited_once()


# --------------------------------------------------------------------------- #
# PG health (dead tuples + WAL)
# --------------------------------------------------------------------------- #

class TestPGHealth:
    @pytest.mark.asyncio
    async def test_no_app_state(self, monitor: HealthMonitor) -> None:
        monitor.app_state = None
        await monitor._check_pg_health()

    @pytest.mark.asyncio
    async def test_no_db_pool(self, monitor: HealthMonitor) -> None:
        monitor.app_state = MagicMock()
        monitor.app_state.db_pool = None
        await monitor._check_pg_health()

    @pytest.mark.asyncio
    async def test_dead_tuples_above_10k(
        self, monitor: HealthMonitor, mock_alert_service: MagicMock,
    ) -> None:
        mock_conn = AsyncMock()
        # First fetchval = dead tuples, second = WAL
        mock_conn.fetchval = AsyncMock(side_effect=[15000, 100 * 1024 * 1024])
        mock_conn.execute = AsyncMock()

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        monitor.app_state = MagicMock()
        monitor.app_state.db_pool = mock_pool

        await monitor._check_pg_health()
        mock_alert_service.send_resource_alert.assert_awaited()

    @pytest.mark.asyncio
    async def test_dead_tuples_warning_level(
        self, monitor: HealthMonitor, mock_alert_service: MagicMock,
    ) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[7000, 50 * 1024 * 1024])

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        monitor.app_state = MagicMock()
        monitor.app_state.db_pool = mock_pool

        await monitor._check_pg_health()
        mock_alert_service.send_resource_alert.assert_awaited()

    @pytest.mark.asyncio
    async def test_wal_privilege_error(self, monitor: HealthMonitor) -> None:
        mock_conn = AsyncMock()
        # dead_tuples ok, WAL query raises
        mock_conn.fetchval = AsyncMock(side_effect=[100, Exception("permission denied")])

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        monitor.app_state = MagicMock()
        monitor.app_state.db_pool = mock_pool

        await monitor._check_pg_health()  # Should not raise

    @pytest.mark.asyncio
    async def test_wal_high(
        self, monitor: HealthMonitor, mock_alert_service: MagicMock,
    ) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[100, 600 * 1024 * 1024])  # 600MB WAL

        mock_pool = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        monitor.app_state = MagicMock()
        monitor.app_state.db_pool = mock_pool

        await monitor._check_pg_health()
        mock_alert_service.send_resource_alert.assert_awaited()


# --------------------------------------------------------------------------- #
# Metrics update
# --------------------------------------------------------------------------- #

class TestUpdateResourceMetrics:
    def test_metrics_update_success(self, monitor: HealthMonitor) -> None:
        mock_memory = MagicMock()
        mock_cpu = MagicMock()
        with patch("backend.app.metrics.memory_usage", mock_memory), \
             patch("backend.app.metrics.cpu_usage", mock_cpu):
            monitor._update_resource_metrics(500.0, 12.2, 5.0)
            mock_memory.set.assert_called_once_with(500.0)
            mock_cpu.set.assert_called_once_with(5.0)

    def test_metrics_import_error(self, monitor: HealthMonitor) -> None:
        with patch.dict("sys.modules", {"backend.app.metrics": None}):
            # Should not raise
            monitor._update_resource_metrics(500.0, 12.2, 5.0)


# --------------------------------------------------------------------------- #
# Restart tracking
# --------------------------------------------------------------------------- #

class TestRestartCount:
    def test_read_restart_count_success(self) -> None:
        mock_counter = MagicMock()
        with patch("backend.app.metrics.safe_register_counter", return_value=mock_counter):
            result = HealthMonitor._read_restart_count()
            assert result == 1
            mock_counter.inc.assert_called_once()

    def test_read_restart_count_import_error(self) -> None:
        with patch.dict("sys.modules", {"backend.app.metrics": None}):
            result = HealthMonitor._read_restart_count()
            assert result == 0


# --------------------------------------------------------------------------- #
# get_status
# --------------------------------------------------------------------------- #

class TestGetStatus:
    def test_basic_status(self, monitor: HealthMonitor) -> None:
        mock_process = MagicMock()
        mock_mem_info = MagicMock()
        mock_mem_info.rss = 500 * 1024 * 1024
        mock_process.memory_info.return_value = mock_mem_info
        mock_process.cpu_percent.return_value = 5.0

        with patch("psutil.Process", return_value=mock_process):
            status = monitor.get_status()
            assert status["running"] is False
            assert status["task_status"] == "dead/not_started"
            assert status["check_interval"] == 5
            assert "resources" in status
            assert status["resources"]["memory_rss_mb"] == 500.0

    def test_status_with_db_pool(self, monitor: HealthMonitor) -> None:
        mock_pool = MagicMock()
        mock_pool.get_size.return_value = 5
        mock_pool.get_min_size.return_value = 1
        mock_pool.get_max_size.return_value = 20
        mock_pool.get_idle_size.return_value = 15

        monitor.app_state = MagicMock()
        monitor.app_state.db_pool = mock_pool

        with patch("psutil.Process", side_effect=Exception("no proc")):
            status = monitor.get_status()
            assert status["db_pool"]["size"] == 5
            assert status["db_pool"]["max_size"] == 20

    def test_status_psutil_exception(self, monitor: HealthMonitor) -> None:
        with patch("psutil.Process", side_effect=Exception("boom")):
            status = monitor.get_status()
            assert status["resources"] == {}


# --------------------------------------------------------------------------- #
# Module-level functions
# --------------------------------------------------------------------------- #

class TestModuleFunctions:
    def test_init_and_get_health_monitor(self, mock_alert_service: MagicMock) -> None:
        with patch("backend.services.monitoring.health_monitor._health_monitor", None):
            with patch("backend.services.monitoring.health_monitor._health_monitor", None):
                result = init_health_monitor(mock_alert_service, check_interval=30)
                assert isinstance(result, HealthMonitor)
                assert result.check_interval == 30

    def test_get_health_monitor_returns_none(self) -> None:
        with patch("backend.services.monitoring.health_monitor._health_monitor", None):
            assert get_health_monitor() is None
