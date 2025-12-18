"""
Unit tests for Debug Router
Tests debug endpoints for troubleshooting and monitoring
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers import debug


@pytest.fixture
def app():
    """Create test FastAPI app"""
    app = FastAPI()
    app.include_router(debug.router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_settings_dev():
    """Mock settings for development environment"""
    with patch("app.routers.debug.settings") as mock:
        mock.environment = "development"
        mock.admin_api_key = "test-admin-key"
        yield mock


@pytest.fixture
def mock_settings_prod():
    """Mock settings for production environment"""
    with patch("app.routers.debug.settings") as mock:
        mock.environment = "production"
        mock.admin_api_key = "test-admin-key"
        yield mock


@pytest.fixture
def mock_request():
    """Mock FastAPI request"""
    request = MagicMock()
    request.state = MagicMock()
    request.state.correlation_id = "test-correlation-id"
    request.state.request_id = "test-request-id"
    request.app = MagicMock()
    request.app.state = MagicMock()
    request.app.state.search_service = MagicMock()
    request.app.state.ai_client = MagicMock()
    request.app.state.db_pool = MagicMock()
    request.app.state.memory_service = MagicMock()
    request.app.state.intelligent_router = MagicMock()
    request.app.state.health_monitor = MagicMock()
    request.app.state.services_initialized = True
    return request


class TestDebugAccess:
    """Tests for debug access verification"""

    def test_verify_debug_access_dev_with_token(self, mock_settings_dev):
        """Test debug access in development with valid token"""
        from app.routers.debug import verify_debug_access
        from fastapi.security import HTTPAuthorizationCredentials

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-admin-key")
        request = MagicMock()
        request.headers = {}

        result = verify_debug_access(credentials=credentials, request=request)
        assert result is True

    def test_verify_debug_access_prod_denied(self, mock_settings_prod):
        """Test debug access denied in production"""
        from app.routers.debug import verify_debug_access
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-admin-key")
        request = MagicMock()
        request.headers = {}

        with pytest.raises(HTTPException):  # Should raise HTTPException
            verify_debug_access(credentials=credentials, request=request)

    def test_verify_debug_access_no_credentials(self, mock_settings_dev):
        """Test debug access without credentials"""
        from app.routers.debug import verify_debug_access

        request = MagicMock()
        request.headers = {"X-Debug-Key": "test-admin-key"}

        # Should work with X-Debug-Key header
        result = verify_debug_access(credentials=None, request=request)
        assert result is True

    def test_verify_debug_access_invalid_token(self, mock_settings_dev):
        """Test debug access with invalid token"""
        from app.routers.debug import verify_debug_access
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-key")
        request = MagicMock()
        request.headers = {}

        with pytest.raises(HTTPException) as exc_info:
            verify_debug_access(credentials=credentials, request=request)

        assert exc_info.value.status_code == 401

    def test_verify_debug_access_no_header_no_credentials(self, mock_settings_dev):
        """Test debug access with no credentials and no header"""
        from app.routers.debug import verify_debug_access
        from fastapi import HTTPException

        request = MagicMock()
        request.headers = {}

        with pytest.raises(HTTPException) as exc_info:
            verify_debug_access(credentials=None, request=request)

        assert exc_info.value.status_code == 401


class TestRequestTrace:
    """Tests for request trace endpoint"""

    def test_get_request_trace_not_found(self, client, mock_settings_dev):
        """Test getting trace for non-existent request"""
        with patch("app.routers.debug.RequestTracingMiddleware.get_trace", return_value=None):
            response = client.get(
                "/api/debug/request/non-existent-id",
                headers={"Authorization": "Bearer test-admin-key"},
            )

            assert response.status_code == 404

    def test_get_request_trace_success(self, client, mock_settings_dev):
        """Test getting trace successfully"""
        trace_data = {
            "correlation_id": "test-id",
            "request_id": "test-id",
            "method": "GET",
            "path": "/test",
            "duration_ms": 100.5,
            "status_code": 200,
        }

        with patch("app.routers.debug.RequestTracingMiddleware.get_trace", return_value=trace_data):
            response = client.get(
                "/api/debug/request/test-id",
                headers={"Authorization": "Bearer test-admin-key"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["trace"]["correlation_id"] == "test-id"


class TestLogs:
    """Tests for logs endpoint"""

    def test_get_logs(self, client, mock_settings_dev):
        """Test getting logs endpoint"""
        response = client.get(
            "/api/debug/logs?module=test&level=INFO&limit=50",
            headers={"Authorization": "Bearer test-admin-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "filters" in data
        assert data["filters"]["module"] == "test"
        assert data["filters"]["level"] == "INFO"


class TestApplicationState:
    """Tests for application state endpoint"""

    def test_get_app_state(self, client, mock_settings_dev, mock_request):
        """Test getting application state"""
        with patch("app.routers.debug.Request") as mock_request_class:
            mock_request_class.return_value = mock_request
            with patch("app.routers.debug.get_correlation_id", return_value="test-id"):
                response = client.get(
                    "/api/debug/state",
                    headers={"Authorization": "Bearer test-admin-key"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "state" in data
                assert "services" in data["state"]

    def test_get_services_status(self, client, mock_settings_dev, mock_request):
        """Test getting services status"""
        with patch("app.routers.debug.Request") as mock_request_class:
            mock_request_class.return_value = mock_request
            with patch("app.core.service_health.service_registry") as mock_registry:
                mock_registry.get_status.return_value = {"healthy": True}

                response = client.get(
                    "/api/debug/services",
                    headers={"Authorization": "Bearer test-admin-key"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "services" in data

    def test_get_services_status_with_health_check(self, client, mock_settings_dev, mock_request):
        """Test getting services status with service that has health_check method"""
        mock_service = MagicMock()
        mock_service.health_check = AsyncMock(return_value={"status": "healthy"})
        mock_request.app.state.search_service = mock_service

        with patch("app.routers.debug.Request") as mock_request_class:
            mock_request_class.return_value = mock_request
            with patch("app.core.service_health.service_registry") as mock_registry:
                mock_registry.get_status.return_value = {"healthy": True}

                response = client.get(
                    "/api/debug/services",
                    headers={"Authorization": "Bearer test-admin-key"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True

    def test_get_services_status_with_health_check(self, client, mock_settings_dev, mock_request):
        """Test getting services status with service that has health_check method"""
        mock_service = MagicMock()
        mock_service.health_check = AsyncMock(return_value={"status": "healthy"})
        mock_request.app.state.search_service = mock_service

        with patch("app.routers.debug.Request") as mock_request_class:
            mock_request_class.return_value = mock_request
            with patch("app.core.service_health.service_registry") as mock_registry:
                mock_registry.get_status.return_value = {"healthy": True}

                response = client.get(
                    "/api/debug/services",
                    headers={"Authorization": "Bearer test-admin-key"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True

    def test_get_services_status_service_error(self, client, mock_settings_dev, mock_request):
        """Test getting services status when service raises error"""
        mock_service = MagicMock()
        mock_service.health_check = AsyncMock(side_effect=Exception("Service error"))
        mock_request.app.state.search_service = mock_service

        with patch("app.routers.debug.Request") as mock_request_class:
            mock_request_class.return_value = mock_request
            with patch("app.core.service_health.service_registry") as mock_registry:
                mock_registry.get_status.side_effect = Exception("Registry error")

                response = client.get(
                    "/api/debug/services",
                    headers={"Authorization": "Bearer test-admin-key"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "services" in data


class TestDatabaseDebugger:
    """Tests for database debugger endpoints"""

    def test_get_slow_queries(self, client, mock_settings_dev):
        """Test getting slow queries"""
        from app.utils.db_debugger import DatabaseQueryDebugger

        slow_queries = [
            {
                "query": "SELECT * FROM users",
                "duration_ms": 1500.0,
                "rows_returned": 100,
            }
        ]

        with patch.object(DatabaseQueryDebugger, "get_slow_queries", return_value=slow_queries):
            response = client.get(
                "/api/debug/db/queries/slow?limit=50",
                headers={"Authorization": "Bearer test-admin-key"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "queries" in data

    def test_get_recent_queries(self, client, mock_settings_dev):
        """Test getting recent queries"""
        from app.utils.db_debugger import DatabaseQueryDebugger

        recent_queries = [
            {
                "query": "SELECT * FROM users WHERE id = $1",
                "duration_ms": 50.0,
                "rows_returned": 1,
            }
        ]

        with patch.object(
            DatabaseQueryDebugger, "get_recent_queries", return_value=recent_queries
        ):
            response = client.get(
                "/api/debug/db/queries/recent?limit=100",
                headers={"Authorization": "Bearer test-admin-key"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_analyze_query_patterns(self, client, mock_settings_dev):
        """Test analyzing query patterns"""
        from app.utils.db_debugger import DatabaseQueryDebugger

        analysis = {
            "n_plus_one_patterns": [],
            "missing_indexes": [],
            "slow_patterns": [],
        }

        with patch.object(
            DatabaseQueryDebugger, "analyze_query_patterns", return_value=analysis
        ):
            response = client.get(
                "/api/debug/db/queries/analyze",
                headers={"Authorization": "Bearer test-admin-key"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "analysis" in data


class TestQdrantDebugger:
    """Tests for Qdrant debugger endpoints"""

    @pytest.mark.asyncio
    async def test_get_collections_health(self, client, mock_settings_dev):
        """Test getting Qdrant collections health"""
        from app.utils.qdrant_debugger import QdrantDebugger, CollectionHealth

        health_statuses = [
            CollectionHealth(
                name="test_collection",
                points_count=1000,
                vectors_count=1000,
                indexed=True,
                status="green",
            )
        ]

        with patch.object(QdrantDebugger, "get_all_collections_health", return_value=health_statuses):
            response = client.get(
                "/api/debug/qdrant/collections/health",
                headers={"Authorization": "Bearer test-admin-key"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "collections" in data

    @pytest.mark.asyncio
    async def test_get_collection_stats(self, client, mock_settings_dev):
        """Test getting collection stats"""
        from app.utils.qdrant_debugger import QdrantDebugger

        stats = {
            "name": "test_collection",
            "points_count": 1000,
            "status": "green",
        }

        with patch.object(QdrantDebugger, "get_collection_stats", return_value=stats):
            response = client.get(
                "/api/debug/qdrant/collection/test_collection/stats",
                headers={"Authorization": "Bearer test-admin-key"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "stats" in data


class TestRAGPipeline:
    """Tests for RAG pipeline trace endpoint"""

    def test_get_rag_pipeline_trace(self, client, mock_settings_dev):
        """Test getting RAG pipeline trace"""
        response = client.get(
            "/api/debug/rag/pipeline/test-id",
            headers={"Authorization": "Bearer test-admin-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False  # Not yet implemented
        assert "correlation_id" in data


class TestPerformanceProfiling:
    """Tests for performance profiling endpoint"""

    def test_run_performance_profiling_not_found(self, client, mock_settings_dev):
        """Test running performance profiling when script not found"""
        with patch("app.routers.debug.Path") as mock_path_class:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_path_class.return_value = mock_path

            response = client.post(
                "/api/debug/profile",
                headers={"Authorization": "Bearer test-admin-key"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "not found" in data["message"].lower()

    def test_run_performance_profiling_error(self, client, mock_settings_dev):
        """Test running performance profiling with error"""
        with patch("app.routers.debug.Path") as mock_path_class:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path.parent = MagicMock()
            mock_path_class.return_value = mock_path

            with patch("app.routers.debug.sys.path.insert"):
                with patch("app.routers.debug.PerformanceProfiler", side_effect=ImportError("Module not found")):
                    response = client.post(
                        "/api/debug/profile",
                        headers={"Authorization": "Bearer test-admin-key"},
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] is False
                    assert "error" in data


class TestTraces:
    """Tests for traces endpoints"""

    def test_get_recent_traces(self, client, mock_settings_dev):
        """Test getting recent traces"""
        traces = [
            {
                "correlation_id": "test-1",
                "method": "GET",
                "path": "/test",
                "duration_ms": 100.0,
            }
        ]

        with patch("app.routers.debug.RequestTracingMiddleware.get_recent_traces", return_value=traces):
            response = client.get(
                "/api/debug/traces/recent?limit=50",
                headers={"Authorization": "Bearer test-admin-key"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "traces" in data

    def test_clear_traces(self, client, mock_settings_dev):
        """Test clearing traces"""
        from middleware.request_tracing import RequestTracingMiddleware

        # Add some traces first
        RequestTracingMiddleware.clear_traces()  # Clear first
        # Create a trace by making a request
        client.get("/test", headers={"Authorization": "Bearer test-admin-key"})

        # Now clear traces
        with patch("app.routers.debug.RequestTracingMiddleware.clear_traces") as mock_clear:
            mock_clear.return_value = 5

            response = client.delete(
                "/api/debug/traces",
                headers={"Authorization": "Bearer test-admin-key"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "Cleared" in data["message"]

