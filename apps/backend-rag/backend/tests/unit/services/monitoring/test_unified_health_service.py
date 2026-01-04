"""
Unit tests for UnifiedHealthService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.monitoring.unified_health_service import HealthCheckResult, UnifiedHealthService


@pytest.fixture
def unified_health_service():
    """Create UnifiedHealthService instance"""
    return UnifiedHealthService()


class TestUnifiedHealthService:
    """Tests for UnifiedHealthService"""

    def test_init(self, unified_health_service):
        """Test initialization"""
        assert unified_health_service.service_registry is not None
        assert unified_health_service.start_time > 0
        assert unified_health_service.http_client is None

    @pytest.mark.asyncio
    async def test_initialize(self, unified_health_service):
        """Test initializing HTTP and Redis clients"""
        with patch("httpx.AsyncClient") as mock_client:
            with patch("services.monitoring.unified_health_service.settings") as mock_settings:
                mock_settings.redis_url = None
                await unified_health_service.initialize()
                assert unified_health_service.http_client is not None

    @pytest.mark.asyncio
    async def test_close(self, unified_health_service):
        """Test closing resources"""
        mock_client = AsyncMock()
        unified_health_service.http_client = mock_client
        await unified_health_service.close()
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_database_no_url(self, unified_health_service):
        """Test checking database when URL not set"""
        with patch("services.monitoring.unified_health_service.settings") as mock_settings:
            mock_settings.database_url = None
            result = await unified_health_service.check_database()
            assert result.status == "skipped"

    @pytest.mark.asyncio
    async def test_check_database_success(self, unified_health_service):
        """Test checking database successfully"""
        with patch("services.monitoring.unified_health_service.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test"
            with patch("asyncpg.connect") as mock_connect:
                mock_conn = AsyncMock()
                mock_conn.fetchval = AsyncMock(return_value=1)
                mock_conn.close = AsyncMock()
                mock_connect.return_value = mock_conn
                result = await unified_health_service.check_database()
                assert result.status == "ok"

    @pytest.mark.asyncio
    async def test_get_system_metrics(self, unified_health_service):
        """Test getting system metrics"""
        with patch("psutil.cpu_percent", return_value=50.0):
            with patch("psutil.virtual_memory") as mock_mem:
                mock_mem_obj = MagicMock()
                mock_mem_obj.percent = 60.0
                mock_mem.return_value = mock_mem_obj
                with patch("psutil.disk_usage") as mock_disk:
                    mock_disk_obj = MagicMock()
                    mock_disk_obj.percent = 40.0
                    mock_disk.return_value = mock_disk_obj
                    metrics = await unified_health_service.get_system_metrics()
                    assert metrics.cpu_usage == 50.0
                    assert metrics.memory_usage == 60.0
                    assert metrics.disk_usage == 40.0

    @pytest.mark.asyncio
    async def test_run_all_checks(self, unified_health_service):
        """Test running all health checks"""
        unified_health_service.check_database = AsyncMock(
            return_value=HealthCheckResult(name="database", status="ok", message="OK")
        )
        results = await unified_health_service.run_all_checks()
        assert isinstance(results, dict)
        assert "checks" in results or "overall_status" in results
