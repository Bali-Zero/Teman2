"""
Integration tests for Debug System
Tests end-to-end debug functionality with real services
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
from middleware.request_tracing import RequestTracingMiddleware


@pytest.fixture
def app():
    """Create test FastAPI app with debug router"""
    app = FastAPI()
    app.include_router(debug.router)
    app.add_middleware(RequestTracingMiddleware)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_settings_dev():
    """Mock settings for development"""
    with patch("app.routers.debug.settings") as mock:
        mock.environment = "development"
        mock.admin_api_key = "test-admin-key"
        mock.port = 8000
        yield mock


class TestDebugEndpointsIntegration:
    """Integration tests for debug endpoints"""

    def test_request_trace_end_to_end(self, client, mock_settings_dev):
        """Test complete request trace flow"""
        # Make a request to create a trace
        response = client.get("/api/debug/state", headers={"Authorization": "Bearer test-admin-key"})
        assert response.status_code == 200

        # Get correlation ID from response
        correlation_id = response.headers.get("X-Correlation-ID")
        assert correlation_id is not None

        # Get trace for that request
        trace_response = client.get(
            f"/api/debug/request/{correlation_id}",
            headers={"Authorization": "Bearer test-admin-key"},
        )

        assert trace_response.status_code == 200
        trace_data = trace_response.json()
        assert trace_data["success"] is True
        assert trace_data["trace"]["correlation_id"] == correlation_id

    def test_traces_recent_integration(self, client, mock_settings_dev):
        """Test getting recent traces integration"""
        # Make multiple requests
        for i in range(3):
            client.get(
                "/api/debug/state",
                headers={"Authorization": "Bearer test-admin-key"},
            )

        # Get recent traces
        response = client.get(
            "/api/debug/traces/recent?limit=10",
            headers={"Authorization": "Bearer test-admin-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["traces"]) >= 3

    def test_services_status_integration(self, client, mock_settings_dev):
        """Test services status integration"""
        # Setup app state
        client.app.state.search_service = MagicMock()
        client.app.state.ai_client = MagicMock()
        client.app.state.db_pool = MagicMock()
        client.app.state.memory_service = MagicMock()
        client.app.state.intelligent_router = MagicMock()
        client.app.state.health_monitor = MagicMock()

        response = client.get(
            "/api/debug/services",
            headers={"Authorization": "Bearer test-admin-key"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "services" in data
        assert "search_service" in data["services"]


class TestDebugUtilitiesIntegration:
    """Integration tests for debug utilities"""

    def test_rag_debugger_integration(self):
        """Test RAG debugger in realistic scenario"""
        from app.utils.rag_debugger import RAGPipelineDebugger

        debugger = RAGPipelineDebugger(query="test query", correlation_id="test-correlation")

        # Simulate RAG pipeline steps
        with debugger.step("embedding"):
            embedding = [0.1] * 1536

        with debugger.step("search"):
            results = [{"id": "1", "text": "doc1", "score": 0.9}]
            debugger.add_documents(results, stage="retrieved")

        with debugger.step("rerank"):
            reranked = [{"id": "1", "text": "doc1", "score": 0.95}]
            debugger.add_documents(reranked, stage="reranked")
            debugger.add_confidence_scores([0.95])

        trace = debugger.finish(response="Test response")

        assert trace.query == "test query"
        assert len(trace.steps) == 3
        assert len(trace.documents_retrieved) == 1
        assert len(trace.documents_reranked) == 1
        assert len(trace.confidence_scores) == 1
        assert trace.final_response == "Test response"

    def test_db_debugger_integration(self):
        """Test database debugger in realistic scenario"""
        from app.utils.db_debugger import DatabaseQueryDebugger

        debugger = DatabaseQueryDebugger(slow_query_threshold_ms=1000.0)

        # Simulate multiple queries
        queries = [
            ("SELECT * FROM users WHERE id = $1", (1,)),
            ("SELECT * FROM posts WHERE user_id = $1", (1,)),
            ("SELECT COUNT(*) FROM users", None),
        ]

        for query, params in queries:
            with debugger.trace_query(query, params) as trace:
                trace.rows_returned = 10

        # Check recent queries
        recent = DatabaseQueryDebugger.get_recent_queries(limit=10)
        assert len(recent) == 3

        # Analyze patterns
        analysis = DatabaseQueryDebugger.analyze_query_patterns()
        assert "slow_patterns" in analysis

    @pytest.mark.asyncio
    async def test_qdrant_debugger_integration(self):
        """Test Qdrant debugger integration"""
        from app.utils.qdrant_debugger import QdrantDebugger

        debugger = QdrantDebugger()

        with patch("app.utils.qdrant_debugger.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Mock collections list
            mock_instance.get = AsyncMock(
                side_effect=[
                    MagicMock(
                        raise_for_status=MagicMock(),
                        json=MagicMock(
                            return_value={
                                "result": {
                                    "collections": [
                                        {"name": "legal_unified"},
                                        {"name": "tax_genius"},
                                    ]
                                }
                            }
                        ),
                    ),
                    # Mock collection health for legal_unified
                    MagicMock(
                        raise_for_status=MagicMock(),
                        json=MagicMock(
                            return_value={
                                "result": {
                                    "points_count": 5000,
                                    "vectors_count": 5000,
                                    "config": {"params": {"vectors": {"on_disk": False}}},
                                    "status": "green",
                                }
                            }
                        ),
                    ),
                    # Mock collection health for tax_genius
                    MagicMock(
                        raise_for_status=MagicMock(),
                        json=MagicMock(
                            return_value={
                                "result": {
                                    "points_count": 1000,
                                    "vectors_count": 1000,
                                    "config": {"params": {"vectors": {"on_disk": False}}},
                                    "status": "green",
                                }
                            }
                        ),
                    ),
                ]
            )

            health_statuses = await debugger.get_all_collections_health()

            assert len(health_statuses) == 2
            assert health_statuses[0].name == "legal_unified"
            assert health_statuses[0].points_count == 5000


class TestDebugContextIntegration:
    """Integration tests for debug context"""

    def test_debug_context_with_rag_pipeline(self):
        """Test debug context with RAG pipeline"""
        from app.utils.debug_context import debug_mode
        from app.utils.rag_debugger import RAGPipelineDebugger

        with debug_mode(request_id="test-123", enable_verbose_logging=True) as ctx:
            debugger = RAGPipelineDebugger(query="test", correlation_id="test-123")

            with debugger.step("search"):
                ctx.capture_api_call("POST", "https://api.qdrant.io/search")

            trace = debugger.finish()

        assert len(ctx.api_calls) == 1
        assert trace.correlation_id == "test-123"


class TestRequestTracingIntegration:
    """Integration tests for request tracing"""

    def test_correlation_id_propagation(self, client, mock_settings_dev):
        """Test correlation ID propagation through requests"""
        # Make request with custom correlation ID
        correlation_id = "custom-correlation-id-123"
        response = client.get(
            "/api/debug/state",
            headers={
                "Authorization": "Bearer test-admin-key",
                "X-Correlation-ID": correlation_id,
            },
        )

        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == correlation_id

        # Verify trace exists
        from middleware.request_tracing import RequestTracingMiddleware

        trace = RequestTracingMiddleware.get_trace(correlation_id)
        assert trace is not None
        assert trace["correlation_id"] == correlation_id

    def test_trace_steps_integration(self, client, mock_settings_dev):
        """Test adding steps to trace"""
        response = client.get(
            "/api/debug/state",
            headers={"Authorization": "Bearer test-admin-key"},
        )

        correlation_id = response.headers["X-Correlation-ID"]

        # Add step to trace
        from middleware.request_tracing import RequestTracingMiddleware

        RequestTracingMiddleware.add_step(
            correlation_id=correlation_id,
            step_name="custom_step",
            duration_ms=50.0,
            metadata={"custom": "data"},
        )

        # Verify step was added
        trace = RequestTracingMiddleware.get_trace(correlation_id)
        assert trace is not None
        assert len(trace.get("steps", [])) > 0

        # Find our custom step
        steps = trace.get("steps", [])
        custom_steps = [s for s in steps if s.get("name") == "custom_step"]
        assert len(custom_steps) > 0
        assert custom_steps[0]["duration_ms"] == 50.0

