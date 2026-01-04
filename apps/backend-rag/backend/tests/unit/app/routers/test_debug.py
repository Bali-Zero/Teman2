"""
Tests for Debug Router
Target: 100% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


from app.routers.debug import router, v1_router, verify_debug_access

app = FastAPI()
app.include_router(router)
app.include_router(v1_router)

client = TestClient(app)


@pytest.fixture
def mock_settings():
    with patch("app.routers.debug.settings") as mock:
        mock.environment = "development"
        mock.admin_api_key = "secret_key"
        yield mock


# ============================================================================
# TESTS: verify_debug_access
# ============================================================================


def test_verify_debug_access_production_no_key(mock_settings):
    mock_settings.environment = "production"
    mock_settings.admin_api_key = None

    with pytest.raises(HTTPException) as exc:
        verify_debug_access(credentials=None, request=MagicMock())
    assert exc.value.status_code == 403


def test_verify_debug_access_no_creds_no_header(mock_settings):
    mock_request = MagicMock()
    mock_request.headers.get.return_value = None

    with pytest.raises(HTTPException) as exc:
        verify_debug_access(credentials=None, request=mock_request)
    assert exc.value.status_code == 401


def test_verify_debug_access_bearer_success(mock_settings):
    creds = MagicMock()
    creds.credentials = "secret_key"
    assert verify_debug_access(credentials=creds, request=MagicMock()) is True


def test_verify_debug_access_bearer_fail(mock_settings):
    creds = MagicMock()
    creds.credentials = "wrong_key"
    mock_request = MagicMock()
    mock_request.headers.get.return_value = None

    with pytest.raises(HTTPException) as exc:
        verify_debug_access(credentials=creds, request=mock_request)
    assert exc.value.status_code == 401


def test_verify_debug_access_header_success(mock_settings):
    mock_request = MagicMock()
    mock_request.headers.get.return_value = "secret_key"
    assert verify_debug_access(credentials=None, request=mock_request) is True


def test_verify_debug_access_header_fail(mock_settings):
    mock_request = MagicMock()
    mock_request.headers.get.return_value = "wrong_key"

    with pytest.raises(HTTPException) as exc:
        verify_debug_access(credentials=None, request=mock_request)
    assert exc.value.status_code == 401


# ============================================================================
# TESTS: Endpoints
# ============================================================================


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer secret_key"}


def test_get_request_trace(mock_settings, auth_headers):
    with patch("middleware.request_tracing.RequestTracingMiddleware.get_trace") as mock_get:
        mock_get.return_value = {"id": "123"}
        response = client.get("/api/debug/request/123", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is True


def test_get_request_trace_not_found(mock_settings, auth_headers):
    with patch("middleware.request_tracing.RequestTracingMiddleware.get_trace") as mock_get:
        mock_get.return_value = None
        response = client.get("/api/debug/request/123", headers=auth_headers)
        assert response.status_code == 404


def test_get_logs(mock_settings, auth_headers):
    response = client.get("/api/debug/logs", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_get_app_state(mock_settings, auth_headers):
    # We need to mock request.app.state somehow, but TestClient uses a real app instance.
    # We can inject state into the app instance used by client.
    app.state.services_initialized = True
    app.state.search_service = MagicMock()

    response = client.get("/api/debug/state", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["state"]["initialized"] is True


def test_get_services_status(mock_settings, auth_headers):
    with patch("app.core.service_health.service_registry.get_status") as mock_status:
        mock_status.return_value = {"overall": "healthy"}

        # Mock service with health_check
        app.state.search_service = AsyncMock()
        app.state.search_service.health_check.return_value = {"status": "ok"}

        # Mock service without health_check
        app.state.db_pool = MagicMock()
        del app.state.db_pool.health_check  # ensure no health_check attribute

        # Mock service failing health check
        app.state.ai_client = AsyncMock()
        app.state.ai_client.health_check.side_effect = Exception("Fail")

        response = client.get("/api/debug/services", headers=auth_headers)
        assert response.status_code == 200
        services = response.json()["services"]
        assert services["search_service"]["status"] == "ok"
        assert services["db_pool"]["status"] == "available"
        assert services["ai_client"]["status"] == "error"


def test_get_services_status_registry_fail(mock_settings, auth_headers):
    with patch(
        "app.core.service_health.service_registry.get_status", side_effect=Exception("RegFail")
    ):
        response = client.get("/api/debug/services", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["services"]["registry"]["error"] == "RegFail"


def test_get_recent_traces(mock_settings, auth_headers):
    with patch("middleware.request_tracing.RequestTracingMiddleware.get_recent_traces") as mock_get:
        mock_get.return_value = [{"id": "1"}]
        response = client.get("/api/debug/traces/recent", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()["traces"]) == 1


def test_clear_traces(mock_settings, auth_headers):
    with patch("middleware.request_tracing.RequestTracingMiddleware.clear_traces") as mock_clear:
        mock_clear.return_value = 5
        response = client.delete("/api/debug/traces", headers=auth_headers)
        assert response.status_code == 200
        assert "Cleared 5" in response.json()["message"]


def test_rag_pipeline_trace(mock_settings, auth_headers):
    response = client.get("/api/debug/rag/pipeline/123", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["success"] is False  # Not implemented


def test_db_queries_slow(mock_settings, auth_headers):
    with patch("app.utils.db_debugger.DatabaseQueryDebugger.get_slow_queries") as mock_get:
        mock_get.return_value = []
        response = client.get("/api/debug/db/queries/slow", headers=auth_headers)
        assert response.status_code == 200


def test_db_queries_recent(mock_settings, auth_headers):
    with patch("app.utils.db_debugger.DatabaseQueryDebugger.get_recent_queries") as mock_get:
        mock_get.return_value = []
        response = client.get("/api/debug/db/queries/recent", headers=auth_headers)
        assert response.status_code == 200


def test_db_queries_analyze(mock_settings, auth_headers):
    with patch(
        "app.utils.db_debugger.DatabaseQueryDebugger.analyze_query_patterns"
    ) as mock_analyze:
        mock_analyze.return_value = {}
        response = client.get("/api/debug/db/queries/analyze", headers=auth_headers)
        assert response.status_code == 200


def test_qdrant_collections_health(mock_settings, auth_headers):
    with patch("app.utils.qdrant_debugger.QdrantDebugger") as MockDebugger:
        mock_instance = MockDebugger.return_value
        # Mock HealthStatus object
        HealthStatus = MagicMock()
        HealthStatus.name = "test"
        HealthStatus.points_count = 10
        HealthStatus.vectors_count = 10
        HealthStatus.indexed = True
        HealthStatus.status = "ok"
        HealthStatus.error = None

        mock_instance.get_all_collections_health = AsyncMock(return_value=[HealthStatus])

        response = client.get("/api/debug/qdrant/collections/health", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()["collections"]) == 1


def test_qdrant_collection_stats(mock_settings, auth_headers):
    with patch("app.utils.qdrant_debugger.QdrantDebugger") as MockDebugger:
        mock_instance = MockDebugger.return_value
        mock_instance.get_collection_stats = AsyncMock(return_value={})

        response = client.get("/api/debug/qdrant/collection/test/stats", headers=auth_headers)
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_parent_documents_public_success():
    with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {
                "id": 1,
                "document_id": "doc1",
                "type": "bab",
                "title": "Bab I",
                "char_count": 100,
                "pasal_count": 5,
                "created_at": "2023-01-01",
            }
        ]
        mock_connect.return_value = mock_conn

        # Needs direct async call or TestClient
        response = client.get("/api/debug/parent-documents-public/doc1")
        assert response.status_code == 200
        assert response.json()["total_bab"] == 1


@pytest.mark.asyncio
async def test_parent_documents_public_fail():
    with patch("asyncpg.connect", side_effect=Exception("DB Fail")):
        response = client.get("/api/debug/parent-documents-public/doc1")
        assert response.status_code == 200  # Returns 200 with success=False
        assert response.json()["success"] is False


@pytest.mark.asyncio
async def test_bab_full_text_success(mock_settings, auth_headers):
    with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "id": 1,
            "title": "Bab I",
            "full_text": "Text",
            "char_count": 100,
            "pasal_count": 5,
        }
        mock_connect.return_value = mock_conn

        response = client.get("/api/debug/parent-documents/doc1/bab1/text", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_bab_full_text_not_found(mock_settings, auth_headers):
    with patch("asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None
        mock_connect.return_value = mock_conn

        response = client.get("/api/debug/parent-documents/doc1/bab1/text", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is False


@pytest.mark.asyncio
async def test_bab_full_text_fail(mock_settings, auth_headers):
    with patch("asyncpg.connect", side_effect=Exception("DB Fail")):
        response = client.get("/api/debug/parent-documents/doc1/bab1/text", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is False


def test_profile(mock_settings, auth_headers):
    # Mock sys.path and file existence
    with patch("pathlib.Path.exists", return_value=True), \
         patch("sys.path", new=sys.path):
         
         # Mock the module and class
         mock_module = MagicMock()
         mock_profiler_cls = MagicMock()
         mock_profiler_instance = AsyncMock()
         mock_profiler_instance.run_profiling.return_value = {}
         mock_profiler_cls.return_value = mock_profiler_instance
         mock_module.PerformanceProfiler = mock_profiler_cls
         
         with patch.dict("sys.modules", {"performance_profiler": mock_module}):
             response = client.post("/api/debug/profile", headers=auth_headers)
             assert response.status_code == 200
             assert response.json()["success"] is True


def test_profile_script_not_found(mock_settings, auth_headers):
    with patch("pathlib.Path.exists", return_value=False):
        response = client.post("/api/debug/profile", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is False


def test_postgres_connection(mock_settings, auth_headers):
    with patch("app.utils.postgres_debugger.PostgreSQLDebugger") as MockDebugger:
        mock_instance = MockDebugger.return_value
        mock_info = MagicMock()
        mock_info.connected = True
        mock_instance.test_connection = AsyncMock(return_value=mock_info)

        response = client.get("/api/debug/postgres/connection", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["success"] is True


def test_postgres_query(mock_settings, auth_headers):
    with patch("app.utils.postgres_debugger.PostgreSQLDebugger") as MockDebugger:
        mock_instance = MockDebugger.return_value
        mock_instance.execute_query = AsyncMock(return_value={"columns": [], "rows": []})

        response = client.post(
            "/api/debug/postgres/query", json={"query": "SELECT 1"}, headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["success"] is True


def test_postgres_query_validation_error(mock_settings, auth_headers):
    with patch("app.utils.postgres_debugger.PostgreSQLDebugger") as MockDebugger:
        mock_instance = MockDebugger.return_value
        mock_instance.execute_query = AsyncMock(side_effect=ValueError("Unsafe query"))

        response = client.post(
            "/api/debug/postgres/query", json={"query": "DELETE FROM table"}, headers=auth_headers
        )
        assert response.status_code == 400


def test_postgres_tables(mock_settings, auth_headers):
    with patch("app.utils.postgres_debugger.PostgreSQLDebugger") as MockDebugger:
        mock_instance = MockDebugger.return_value
        mock_instance.get_tables = AsyncMock(return_value=[])
        response = client.get("/api/debug/postgres/schema/tables", headers=auth_headers)
        assert response.status_code == 200


def test_postgres_table_details(mock_settings, auth_headers):
    with patch("app.utils.postgres_debugger.PostgreSQLDebugger") as MockDebugger:
        mock_instance = MockDebugger.return_value
        mock_info = MagicMock()
        mock_info.schema = "public"
        mock_info.name = "test"
        mock_instance.get_table_details = AsyncMock(return_value=mock_info)
        response = client.get("/api/debug/postgres/schema/table/test", headers=auth_headers)
        assert response.status_code == 200


def test_postgres_indexes(mock_settings, auth_headers):
    with patch("app.utils.postgres_debugger.PostgreSQLDebugger") as MockDebugger:
        mock_instance = MockDebugger.return_value
        mock_instance.get_indexes = AsyncMock(return_value=[])
        response = client.get("/api/debug/postgres/schema/indexes", headers=auth_headers)
        assert response.status_code == 200


def test_postgres_stats_tables(mock_settings, auth_headers):
    with patch("app.utils.postgres_debugger.PostgreSQLDebugger") as MockDebugger:
        mock_instance = MockDebugger.return_value
        mock_instance.get_table_stats = AsyncMock(return_value=[])
        response = client.get("/api/debug/postgres/stats/tables", headers=auth_headers)
        assert response.status_code == 200


def test_postgres_stats_database(mock_settings, auth_headers):
    with patch("app.utils.postgres_debugger.PostgreSQLDebugger") as MockDebugger:
        mock_instance = MockDebugger.return_value
        mock_instance.get_database_stats = AsyncMock(return_value={})
        response = client.get("/api/debug/postgres/stats/database", headers=auth_headers)
        assert response.status_code == 200


def test_postgres_slow_queries(mock_settings, auth_headers):
    with patch("app.utils.postgres_debugger.PostgreSQLDebugger") as MockDebugger:
        mock_instance = MockDebugger.return_value
        mock_instance.get_slow_queries = AsyncMock(return_value=[])
        response = client.get("/api/debug/postgres/performance/slow-queries", headers=auth_headers)
        assert response.status_code == 200


def test_postgres_locks(mock_settings, auth_headers):
    with patch("app.utils.postgres_debugger.PostgreSQLDebugger") as MockDebugger:
        mock_instance = MockDebugger.return_value
        mock_instance.get_active_locks = AsyncMock(return_value=[])
        response = client.get("/api/debug/postgres/performance/locks", headers=auth_headers)
        assert response.status_code == 200


def test_postgres_connections(mock_settings, auth_headers):
    with patch("app.utils.postgres_debugger.PostgreSQLDebugger") as MockDebugger:
        mock_instance = MockDebugger.return_value
        mock_instance.get_connection_stats = AsyncMock(return_value={})
        response = client.get("/api/debug/postgres/performance/connections", headers=auth_headers)
        assert response.status_code == 200


def test_sentry_test_error(mock_settings):
    # Mock get_current_user dependency
    app.dependency_overrides = {}
    from app.dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: {"id": "test"}

    with pytest.raises(ValueError, match="TEST ERROR"):
        client.get("/api/v1/debug/sentry-test")
