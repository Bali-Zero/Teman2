"""
Unit tests for Request Tracing Middleware
Tests correlation ID generation and trace storage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from middleware.request_tracing import RequestTracingMiddleware, get_correlation_id


@pytest.fixture
def app():
    """Create test FastAPI app"""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(request: Request):
        return {"message": "test"}

    middleware = RequestTracingMiddleware(app, max_traces=10)
    app.add_middleware(RequestTracingMiddleware, max_traces=10)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestRequestTracingMiddleware:
    """Tests for RequestTracingMiddleware"""

    def test_middleware_adds_correlation_id(self, client):
        """Test that middleware adds correlation ID to response"""
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers
        assert "X-Request-ID" in response.headers

    def test_middleware_uses_existing_correlation_id(self, client):
        """Test that middleware uses existing correlation ID from header"""
        correlation_id = "existing-correlation-id"
        response = client.get("/test", headers={"X-Correlation-ID": correlation_id})

        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == correlation_id

    def test_middleware_stores_trace(self, client):
        """Test that middleware stores trace"""
        from middleware.request_tracing import RequestTracingMiddleware

        # Clear existing traces first
        RequestTracingMiddleware.clear_traces()

        response = client.get("/test")
        correlation_id = response.headers["X-Correlation-ID"]

        trace = RequestTracingMiddleware.get_trace(correlation_id)
        assert trace is not None
        assert trace["correlation_id"] == correlation_id
        assert trace["method"] == "GET"
        assert trace["path"] == "/test"

    def test_middleware_stores_trace_with_query_params(self, client):
        """Test that middleware stores trace with query parameters"""
        from middleware.request_tracing import RequestTracingMiddleware

        RequestTracingMiddleware.clear_traces()

        response = client.get("/test?param1=value1&param2=value2")
        correlation_id = response.headers["X-Correlation-ID"]

        trace = RequestTracingMiddleware.get_trace(correlation_id)
        assert trace is not None
        assert "param1" in trace["query_params"]
        assert trace["query_params"]["param1"] == "value1"

    def test_middleware_handles_exception(self, app):
        """Test that middleware handles exceptions and stores error in trace"""

        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")

        app.add_middleware(RequestTracingMiddleware)
        client = TestClient(app)

        RequestTracingMiddleware.clear_traces()

        try:
            client.get("/error")
        except ValueError:
            pass

        # Check that trace was stored with error
        traces = RequestTracingMiddleware.get_recent_traces(limit=1)
        if traces:
            trace = traces[-1]
            assert trace["status_code"] == 500
            assert trace["error"] is not None
            assert trace["error"]["type"] == "ValueError"

    def test_middleware_max_traces_limit(self, app):
        """Test that middleware respects max traces limit"""
        app.add_middleware(RequestTracingMiddleware, max_traces=5)
        client = TestClient(app)

        RequestTracingMiddleware.clear_traces()

        # Make more requests than max_traces
        for i in range(10):
            client.get(f"/test?i={i}")

        traces = RequestTracingMiddleware.get_recent_traces(limit=100)
        # Should not exceed max_traces
        assert len(traces) <= 5


class TestTraceStorage:
    """Tests for trace storage"""

    def test_get_trace_not_found(self):
        """Test getting non-existent trace"""
        from middleware.request_tracing import RequestTracingMiddleware

        trace = RequestTracingMiddleware.get_trace("non-existent-id")
        assert trace is None

    def test_get_recent_traces(self):
        """Test getting recent traces"""
        from middleware.request_tracing import RequestTracingMiddleware

        # Clear existing traces
        RequestTracingMiddleware.clear_traces()

        # Create some traces by making requests
        app = FastAPI()

        @app.get("/test1")
        async def test1():
            return {"message": "test1"}

        @app.get("/test2")
        async def test2():
            return {"message": "test2"}

        app.add_middleware(RequestTracingMiddleware)
        client = TestClient(app)

        client.get("/test1")
        client.get("/test2")

        traces = RequestTracingMiddleware.get_recent_traces(limit=10)
        assert len(traces) >= 2

    def test_clear_traces(self):
        """Test clearing traces"""
        from middleware.request_tracing import RequestTracingMiddleware

        # Create some traces
        app = FastAPI()

        @app.get("/test")
        async def test():
            return {"message": "test"}

        app.add_middleware(RequestTracingMiddleware)
        client = TestClient(app)

        client.get("/test")
        initial_count = len(RequestTracingMiddleware.get_recent_traces())
        assert initial_count > 0

        # Clear traces
        count = RequestTracingMiddleware.clear_traces()
        assert count == initial_count
        assert len(RequestTracingMiddleware.get_recent_traces()) == 0


class TestCorrelationID:
    """Tests for correlation ID utilities"""

    def test_get_correlation_id_from_request(self):
        """Test getting correlation ID from request"""
        request = MagicMock()
        request.state = MagicMock()
        request.state.correlation_id = "test-correlation-id"

        correlation_id = get_correlation_id(request)
        assert correlation_id == "test-correlation-id"

    def test_get_correlation_id_fallback_to_request_id(self):
        """Test getting correlation ID falls back to request_id"""
        request = MagicMock()
        request.state = MagicMock()
        request.state.correlation_id = None
        request.state.request_id = "test-request-id"

        correlation_id = get_correlation_id(request)
        assert correlation_id == "test-request-id"

    def test_get_correlation_id_generates_new(self):
        """Test getting correlation ID generates new if not present"""
        request = MagicMock()
        request.state = MagicMock()
        request.state.correlation_id = None
        request.state.request_id = None

        correlation_id = get_correlation_id(request)
        assert correlation_id is not None
        assert len(correlation_id) > 0


class TestAddStep:
    """Tests for adding steps to traces"""

    def test_add_step_to_trace(self):
        """Test adding a step to a trace"""
        from middleware.request_tracing import RequestTracingMiddleware

        # Clear existing traces
        RequestTracingMiddleware.clear_traces()

        # Create trace
        app = FastAPI()

        @app.get("/test")
        async def test():
            return {"message": "test"}

        app.add_middleware(RequestTracingMiddleware)
        client = TestClient(app)

        response = client.get("/test")
        correlation_id = response.headers["X-Correlation-ID"]

        # Verify trace exists
        trace = RequestTracingMiddleware.get_trace(correlation_id)
        assert trace is not None

        # Add step
        RequestTracingMiddleware.add_step(
            correlation_id=correlation_id,
            step_name="test_step",
            duration_ms=50.0,
            custom_attr="value",
        )

        # Verify step was added
        trace = RequestTracingMiddleware.get_trace(correlation_id)
        assert trace is not None
        assert len(trace.get("steps", [])) > 0
        # Verify metadata was included
        steps = trace.get("steps", [])
        test_step = [s for s in steps if s.get("name") == "test_step"][0]
        assert test_step["custom_attr"] == "value"

    def test_add_step_to_nonexistent_trace(self):
        """Test adding step to non-existent trace (should not fail)"""
        from middleware.request_tracing import RequestTracingMiddleware

        RequestTracingMiddleware.clear_traces()

        # Add step to non-existent trace - should not raise error
        RequestTracingMiddleware.add_step(
            correlation_id="non-existent-id",
            step_name="test_step",
            duration_ms=50.0,
        )

        # Should not fail silently
        trace = RequestTracingMiddleware.get_trace("non-existent-id")
        assert trace is None

