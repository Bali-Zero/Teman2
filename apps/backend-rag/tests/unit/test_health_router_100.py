"""
Complete 100% Coverage Tests for Health Router

Tests all endpoints and edge cases in health.py router.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


# Mock settings before importing
@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings for all tests"""
    with patch("app.routers.health.settings") as mock:
        mock.qdrant_url = "http://localhost:6333"
        mock.qdrant_api_key = "test-key"
        mock.api_keys = "test-key-1,test-key-2"
        mock.api_auth_enabled = True
        mock.jwt_secret_key = "test-jwt-secret"
        mock.environment = "test"
        yield mock


class TestGetQdrantStats:
    """Tests for get_qdrant_stats function"""

    @pytest.mark.asyncio
    async def test_get_qdrant_stats_success(self, mock_settings):
        """Test successful Qdrant stats retrieval"""
        from app.routers.health import get_qdrant_stats

        mock_collections = {
            "result": {"collections": [{"name": "collection1"}, {"name": "collection2"}]}
        }

        mock_collection_info = {"result": {"points_count": 100}}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Mock responses
            mock_instance.get = AsyncMock()
            mock_response_collections = MagicMock()
            mock_response_collections.json.return_value = mock_collections
            mock_response_collections.raise_for_status = MagicMock()

            mock_response_info = MagicMock()
            mock_response_info.json.return_value = mock_collection_info
            mock_response_info.raise_for_status = MagicMock()

            mock_instance.get.side_effect = [
                mock_response_collections,
                mock_response_info,
                mock_response_info,
            ]

            result = await get_qdrant_stats()

            assert result["collections"] == 2
            assert result["total_documents"] == 200

    @pytest.mark.asyncio
    async def test_get_qdrant_stats_no_api_key(self):
        """Test stats without API key"""
        from app.routers.health import get_qdrant_stats

        with patch("app.routers.health.settings") as mock_settings:
            mock_settings.qdrant_url = "http://localhost:6333"
            mock_settings.qdrant_api_key = None

            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_client.return_value.__aenter__.return_value = mock_instance

                mock_response = MagicMock()
                mock_response.json.return_value = {"result": {"collections": []}}
                mock_response.raise_for_status = MagicMock()
                mock_instance.get.return_value = mock_response

                result = await get_qdrant_stats()
                assert result["collections"] == 0

    @pytest.mark.asyncio
    async def test_get_qdrant_stats_connection_error(self, mock_settings):
        """Test stats with connection error"""
        from app.routers.health import get_qdrant_stats

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.get.side_effect = Exception("Connection failed")

            result = await get_qdrant_stats()

            assert result["collections"] == 0
            assert result["total_documents"] == 0
            assert "error" in result

    @pytest.mark.asyncio
    async def test_get_qdrant_stats_collection_error(self, mock_settings):
        """Test stats when individual collection fetch fails"""
        from app.routers.health import get_qdrant_stats

        mock_collections = {
            "result": {"collections": [{"name": "collection1"}, {"name": "collection2"}]}
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_response_collections = MagicMock()
            mock_response_collections.json.return_value = mock_collections
            mock_response_collections.raise_for_status = MagicMock()

            # First collection succeeds, second fails
            mock_response_info = MagicMock()
            mock_response_info.json.return_value = {"result": {"points_count": 50}}
            mock_response_info.raise_for_status = MagicMock()

            mock_instance.get.side_effect = [
                mock_response_collections,
                mock_response_info,
                Exception("Collection fetch failed"),
            ]

            result = await get_qdrant_stats()
            # Should still return partial results
            assert result["collections"] == 2
            assert result["total_documents"] == 50  # Only first collection counted


class TestHealthCheck:
    """Tests for health_check endpoint"""

    @pytest.mark.asyncio
    async def test_health_check_initializing(self):
        """Test health check when service not ready"""
        from app.routers.health import health_check

        mock_request = MagicMock()
        mock_request.app.state = MagicMock()
        mock_request.app.state.search_service = None

        result = await health_check(mock_request)

        assert result.status == "initializing"
        assert result.version == "v100-qdrant"
        assert result.database["status"] == "initializing"

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Test health check when service is healthy"""
        from app.routers.health import health_check

        mock_request = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.model = "text-embedding-3-small"
        mock_embedder.dimensions = 1536
        mock_embedder.provider = "openai"

        mock_search_service = MagicMock()
        mock_search_service.embedder = mock_embedder

        mock_request.app.state.search_service = mock_search_service

        with patch("app.routers.health.get_qdrant_stats") as mock_stats:
            mock_stats.return_value = {"collections": 5, "total_documents": 1000}

            result = await health_check(mock_request)

            assert result.status == "healthy"
            assert result.database["status"] == "connected"
            assert result.database["collections"] == 5
            assert result.embeddings["status"] == "operational"

    @pytest.mark.asyncio
    async def test_health_check_attribute_error(self):
        """Test health check with partial embedder"""
        from app.routers.health import health_check

        mock_request = MagicMock()
        mock_search_service = MagicMock()
        mock_search_service.embedder = MagicMock(spec=[])  # No attributes
        type(mock_search_service.embedder).model = property(
            lambda self: (_ for _ in ()).throw(AttributeError("no model"))
        )

        mock_request.app.state.search_service = mock_search_service

        result = await health_check(mock_request)

        assert result.status == "initializing"
        assert result.embeddings["status"] == "loading"

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        """Test health check with unexpected error"""
        from app.routers.health import health_check

        mock_request = MagicMock()
        type(mock_request.app.state).search_service = property(
            lambda self: (_ for _ in ()).throw(Exception("Unexpected error"))
        )

        result = await health_check(mock_request)

        assert result.status == "degraded"
        assert result.database["status"] == "error"


class TestDetailedHealth:
    """Tests for detailed_health endpoint"""

    @pytest.mark.asyncio
    async def test_detailed_health_all_healthy(self):
        """Test detailed health with all services healthy"""
        from app.routers.health import detailed_health

        mock_request = MagicMock()

        # Mock all services
        mock_search = MagicMock()
        mock_search.embedder = MagicMock()
        mock_search.embedder.provider = "openai"
        mock_search.embedder.model = "test-model"

        mock_ai = MagicMock()
        mock_db_pool = AsyncMock()
        mock_memory = MagicMock()
        mock_router = MagicMock()
        mock_health_monitor = MagicMock()
        mock_health_monitor._running = True
        mock_registry = MagicMock()
        mock_registry.get_status.return_value = {"status": "ok"}

        mock_request.app.state.search_service = mock_search
        mock_request.app.state.ai_client = mock_ai
        mock_request.app.state.db_pool = mock_db_pool
        mock_request.app.state.memory_service = mock_memory
        mock_request.app.state.intelligent_router = mock_router
        mock_request.app.state.health_monitor = mock_health_monitor
        mock_request.app.state.service_registry = mock_registry

        # Mock db acquire context manager
        mock_conn = AsyncMock()
        mock_db_pool.acquire.return_value.__aenter__.return_value = mock_conn

        result = await detailed_health(mock_request)

        assert result["status"] == "healthy"
        assert result["services"]["search"]["status"] == "healthy"
        assert result["services"]["ai"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_detailed_health_critical_unavailable(self):
        """Test detailed health with critical services unavailable"""
        from app.routers.health import detailed_health

        mock_request = MagicMock()
        mock_request.app.state.search_service = None
        mock_request.app.state.ai_client = None
        mock_request.app.state.db_pool = None
        mock_request.app.state.memory_service = None
        mock_request.app.state.intelligent_router = None
        mock_request.app.state.health_monitor = None
        mock_request.app.state.service_registry = None

        result = await detailed_health(mock_request)

        assert result["status"] == "critical"
        assert result["services"]["search"]["status"] == "unavailable"
        assert result["services"]["ai"]["status"] == "unavailable"

    @pytest.mark.asyncio
    async def test_detailed_health_degraded(self):
        """Test detailed health in degraded state"""
        from app.routers.health import detailed_health

        mock_request = MagicMock()

        # Critical services healthy
        mock_search = MagicMock()
        mock_search.embedder = MagicMock()
        mock_ai = MagicMock()

        mock_request.app.state.search_service = mock_search
        mock_request.app.state.ai_client = mock_ai
        mock_request.app.state.db_pool = None  # Non-critical unavailable
        mock_request.app.state.memory_service = None
        mock_request.app.state.intelligent_router = None
        mock_request.app.state.health_monitor = None
        mock_request.app.state.service_registry = None

        result = await detailed_health(mock_request)

        assert result["status"] == "degraded"  # Non-critical services down

    @pytest.mark.asyncio
    async def test_detailed_health_service_errors(self):
        """Test detailed health with service exceptions"""
        from app.routers.health import detailed_health

        mock_request = MagicMock()

        # Make services raise exceptions
        type(mock_request.app.state).search_service = property(
            lambda self: (_ for _ in ()).throw(Exception("Search error"))
        )

        delattr(type(mock_request.app.state), "search_service")
        mock_request.app.state.search_service = None
        mock_request.app.state.ai_client = None
        mock_request.app.state.db_pool = None
        mock_request.app.state.memory_service = None
        mock_request.app.state.intelligent_router = None
        mock_request.app.state.health_monitor = None
        mock_request.app.state.service_registry = None

        result = await detailed_health(mock_request)

        assert result["status"] == "critical"

    @pytest.mark.asyncio
    async def test_detailed_health_db_error(self):
        """Test detailed health with database error"""
        from app.routers.health import detailed_health

        mock_request = MagicMock()
        mock_search = MagicMock()
        mock_search.embedder = MagicMock()
        mock_ai = MagicMock()
        mock_db_pool = AsyncMock()
        mock_db_pool.acquire.side_effect = Exception("DB connection failed")

        mock_request.app.state.search_service = mock_search
        mock_request.app.state.ai_client = mock_ai
        mock_request.app.state.db_pool = mock_db_pool
        mock_request.app.state.memory_service = None
        mock_request.app.state.intelligent_router = None
        mock_request.app.state.health_monitor = None
        mock_request.app.state.service_registry = None

        result = await detailed_health(mock_request)

        assert result["services"]["database"]["status"] == "error"


class TestReadinessCheck:
    """Tests for readiness_check endpoint"""

    @pytest.mark.asyncio
    async def test_readiness_ready(self):
        """Test readiness when all services ready"""
        from app.routers.health import readiness_check

        mock_request = MagicMock()
        mock_request.app.state.search_service = MagicMock()
        mock_request.app.state.ai_client = MagicMock()
        mock_request.app.state.services_initialized = True

        result = await readiness_check(mock_request)

        assert result["ready"] == True
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_readiness_not_ready(self):
        """Test readiness when services not ready"""
        from app.routers.health import readiness_check

        mock_request = MagicMock()
        mock_request.app.state.search_service = None
        mock_request.app.state.ai_client = None
        mock_request.app.state.services_initialized = False

        with pytest.raises(HTTPException) as exc_info:
            await readiness_check(mock_request)

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["ready"] == False

    @pytest.mark.asyncio
    async def test_readiness_partial(self):
        """Test readiness with partial services"""
        from app.routers.health import readiness_check

        mock_request = MagicMock()
        mock_request.app.state.search_service = MagicMock()
        mock_request.app.state.ai_client = None  # Missing
        mock_request.app.state.services_initialized = True

        with pytest.raises(HTTPException) as exc_info:
            await readiness_check(mock_request)

        assert exc_info.value.status_code == 503


class TestLivenessCheck:
    """Tests for liveness_check endpoint"""

    @pytest.mark.asyncio
    async def test_liveness_always_alive(self):
        """Test liveness always returns alive"""
        from app.routers.health import liveness_check

        result = await liveness_check()

        assert result["alive"] == True
        assert "timestamp" in result


class TestQdrantMetrics:
    """Tests for qdrant_metrics endpoint"""

    @pytest.mark.asyncio
    async def test_qdrant_metrics_success(self):
        """Test successful metrics retrieval"""
        from app.routers.health import qdrant_metrics

        mock_metrics = {"searches": 100, "avg_latency": 0.05}

        with patch("app.routers.health.get_qdrant_metrics") as mock_get:
            mock_get.return_value = mock_metrics

            result = await qdrant_metrics()

            assert result["status"] == "ok"
            assert result["metrics"] == mock_metrics

    @pytest.mark.asyncio
    async def test_qdrant_metrics_error(self):
        """Test metrics with error"""
        from app.routers.health import qdrant_metrics

        with patch("app.routers.health.get_qdrant_metrics") as mock_get:
            mock_get.side_effect = Exception("Metrics unavailable")

            result = await qdrant_metrics()

            assert result["status"] == "error"
            assert "error" in result


class TestDebugConfig:
    """Tests for debug_config endpoint"""

    @pytest.mark.asyncio
    async def test_debug_config(self):
        """Test debug config returns expected values"""
        from app.routers.health import debug_config

        with patch("app.routers.health.settings") as mock_settings:
            mock_settings.api_keys = "key1,key2,key3"
            mock_settings.api_auth_enabled = True
            mock_settings.jwt_secret_key = "test-secret-key-12345"
            mock_settings.environment = "development"

            with patch.dict("os.environ", {"API_KEYS": "yes", "JWT_SECRET": "yes"}):
                result = await debug_config()

                assert result["api_keys_count"] == 3
                assert len(result["api_keys_preview"]) == 3
                assert result["api_auth_enabled"] == True
                assert result["jwt_secret_set"] == True
                assert result["environment"] == "development"

    @pytest.mark.asyncio
    async def test_debug_config_no_keys(self):
        """Test debug config with no API keys"""
        from app.routers.health import debug_config

        with patch("app.routers.health.settings") as mock_settings:
            mock_settings.api_keys = None
            mock_settings.api_auth_enabled = False
            mock_settings.jwt_secret_key = None
            mock_settings.environment = "test"

            with patch.dict("os.environ", {}, clear=True):
                result = await debug_config()

                assert result["api_keys_count"] == 0
                assert result["api_keys_preview"] == []
                assert result["jwt_secret_set"] == False
