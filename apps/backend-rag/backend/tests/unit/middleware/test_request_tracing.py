"""
Unit tests for middleware/request_tracing.py
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from middleware.request_tracing import (
    RequestTracingMiddleware,
    get_correlation_id,
)


class TestRequestTracingMiddleware:
    """Tests for RequestTracingMiddleware"""

    @pytest.fixture
    def mock_app(self):
        """Create a mock FastAPI app"""
        app = MagicMock()
        return app

    @pytest.fixture
    def middleware(self, mock_app):
        """Create middleware instance"""
        return RequestTracingMiddleware(mock_app, max_traces=10)

    @pytest.mark.asyncio
    async def test_dispatch_success(self, middleware):
        """Test successful request dispatch"""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.state = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.query_params = {}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        async def call_next(request):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)

        assert result == mock_response
        assert "X-Correlation-ID" in result.headers
        assert "X-Request-ID" in result.headers

    @pytest.mark.asyncio
    async def test_dispatch_with_existing_correlation_id(self, middleware):
        """Test dispatch with existing correlation ID"""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "existing-correlation-id"
        mock_request.state = MagicMock()
        mock_request.state.request_id = "existing-request-id"
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.query_params = {}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        async def call_next(request):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)

        assert result.headers["X-Correlation-ID"] == "existing-correlation-id"
        assert result.headers["X-Request-ID"] == "existing-request-id"

    @pytest.mark.asyncio
    async def test_dispatch_with_exception(self, middleware):
        """Test dispatch with exception"""
        mock_request = MagicMock()
        mock_request.headers.get.return_value = None
        mock_request.state = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.query_params = {}

        async def call_next(request):
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await middleware.dispatch(mock_request, call_next)

        # Trace should be stored with error
        correlation_id = mock_request.state.correlation_id
        trace = RequestTracingMiddleware.get_trace(correlation_id)
        assert trace is not None
        assert trace["error"] is not None
        assert trace["status_code"] == 500

    def test_store_trace(self, middleware):
        """Test storing trace"""
        correlation_id = "test-correlation-id"
        trace = {
            "correlation_id": correlation_id,
            "method": "GET",
            "path": "/test",
        }

        middleware._store_trace(correlation_id, trace)

        stored = RequestTracingMiddleware.get_trace(correlation_id)
        assert stored == trace

    def test_store_trace_max_capacity(self, middleware):
        """Test storing trace when at max capacity"""
        # Fill up to max capacity
        for i in range(10):
            correlation_id = f"test-{i}"
            trace = {"correlation_id": correlation_id}
            middleware._store_trace(correlation_id, trace)

        # Add one more - should remove oldest
        correlation_id = "test-new"
        trace = {"correlation_id": correlation_id}
        middleware._store_trace(correlation_id, trace)

        # Oldest should be removed
        oldest = RequestTracingMiddleware.get_trace("test-0")
        assert oldest is None

        # New one should be present
        new_one = RequestTracingMiddleware.get_trace("test-new")
        assert new_one is not None

    def test_add_step(self, middleware):
        """Test adding step to trace"""
        correlation_id = "test-correlation-id"
        trace = {
            "correlation_id": correlation_id,
            "steps": [],
        }
        middleware._store_trace(correlation_id, trace)

        RequestTracingMiddleware.add_step(correlation_id, "step1", 10.5, extra="data")

        stored = RequestTracingMiddleware.get_trace(correlation_id)
        assert len(stored["steps"]) == 1
        assert stored["steps"][0]["name"] == "step1"
        assert stored["steps"][0]["duration_ms"] == 10.5
        assert stored["steps"][0]["extra"] == "data"

    def test_add_step_no_trace(self, middleware):
        """Test adding step when trace doesn't exist"""
        # Should not raise error
        RequestTracingMiddleware.add_step("non-existent", "step1", 10.5)

    def test_get_trace(self, middleware):
        """Test getting trace"""
        correlation_id = "test-correlation-id"
        trace = {"correlation_id": correlation_id}
        middleware._store_trace(correlation_id, trace)

        retrieved = RequestTracingMiddleware.get_trace(correlation_id)
        assert retrieved == trace

    def test_get_trace_not_found(self, middleware):
        """Test getting non-existent trace"""
        retrieved = RequestTracingMiddleware.get_trace("non-existent")
        assert retrieved is None

    def test_get_recent_traces(self, middleware):
        """Test getting recent traces"""
        # Clear existing traces
        RequestTracingMiddleware.clear_traces()

        # Add multiple traces
        for i in range(5):
            correlation_id = f"test-{i}"
            trace = {"correlation_id": correlation_id}
            middleware._store_trace(correlation_id, trace)

        recent = RequestTracingMiddleware.get_recent_traces(limit=3)
        assert len(recent) == 3
        # Should return most recent ones
        assert recent[-1]["correlation_id"] == "test-4"

    def test_clear_traces(self, middleware):
        """Test clearing traces"""
        # Add some traces
        for i in range(5):
            correlation_id = f"test-{i}"
            trace = {"correlation_id": correlation_id}
            middleware._store_trace(correlation_id, trace)

        count = RequestTracingMiddleware.clear_traces()
        assert count == 5

        # All traces should be gone
        retrieved = RequestTracingMiddleware.get_trace("test-0")
        assert retrieved is None

    def test_get_correlation_id_from_state(self):
        """Test getting correlation ID from request state"""
        mock_request = MagicMock()
        mock_request.state.correlation_id = "test-correlation-id"

        result = get_correlation_id(mock_request)
        assert result == "test-correlation-id"

    def test_get_correlation_id_from_request_id(self):
        """Test getting correlation ID from request_id"""
        mock_request = MagicMock()
        mock_request.state.correlation_id = None
        mock_request.state.request_id = "test-request-id"

        result = get_correlation_id(mock_request)
        assert result == "test-request-id"

    def test_get_correlation_id_generate_new(self):
        """Test generating new correlation ID"""
        mock_request = MagicMock()
        mock_request.state.correlation_id = None
        mock_request.state.request_id = None

        result = get_correlation_id(mock_request)
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
