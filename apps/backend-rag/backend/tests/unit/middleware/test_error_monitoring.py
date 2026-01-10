"""
Unit tests for middleware/error_monitoring.py
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from middleware.error_monitoring import (
    ErrorMonitoringMiddleware,
    create_error_monitoring_middleware,
)


class TestErrorMonitoringMiddleware:
    """Tests for ErrorMonitoringMiddleware"""

    @pytest.fixture
    def mock_app(self):
        """Create a mock FastAPI app"""
        app = MagicMock()
        app.state = MagicMock()
        return app

    @pytest.fixture
    def mock_alert_service(self):
        """Create a mock alert service"""
        service = MagicMock()
        service.send_http_error_alert = AsyncMock()
        service.send_latency_alert = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_init_with_alert_service(self, mock_app, mock_alert_service):
        """Test middleware initialization with alert service"""
        middleware = ErrorMonitoringMiddleware(mock_app, mock_alert_service)
        assert middleware.alert_service == mock_alert_service

    @pytest.mark.asyncio
    async def test_init_without_alert_service(self, mock_app):
        """Test middleware initialization without alert service"""
        middleware = ErrorMonitoringMiddleware(mock_app, None)
        assert middleware.alert_service is None

    @pytest.mark.asyncio
    async def test_dispatch_success(self, mock_app):
        """Test successful request dispatch"""
        middleware = ErrorMonitoringMiddleware(mock_app, None)

        mock_request = MagicMock()
        mock_request.app.state = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        async def call_next(request):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)

        assert result == mock_response
        assert "X-Request-ID" in result.headers

    @pytest.mark.asyncio
    async def test_dispatch_4xx_error(self, mock_app, mock_alert_service):
        """Test dispatch with 4xx error"""
        middleware = ErrorMonitoringMiddleware(mock_app, mock_alert_service)

        mock_request = MagicMock()
        mock_request.app.state = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.headers.get.return_value = "test-agent"

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}
        mock_response.body = b'{"detail": "Not found"}'

        async def call_next(request):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)

        assert result == mock_response
        # 404 should not trigger alert (only 5xx, 429, 403)
        mock_alert_service.send_http_error_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_5xx_error(self, mock_app, mock_alert_service):
        """Test dispatch with 5xx error"""
        middleware = ErrorMonitoringMiddleware(mock_app, mock_alert_service)

        mock_request = MagicMock()
        mock_request.app.state = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.headers.get.return_value = "test-agent"

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}
        mock_response.body = b'{"detail": "Internal error"}'

        async def call_next(request):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)

        assert result == mock_response
        mock_alert_service.send_http_error_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_429_error(self, mock_app, mock_alert_service):
        """Test dispatch with 429 error (should alert)"""
        middleware = ErrorMonitoringMiddleware(mock_app, mock_alert_service)

        mock_request = MagicMock()
        mock_request.app.state = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.headers.get.return_value = "test-agent"

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_response.body = b'{"detail": "Too many requests"}'

        async def call_next(request):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)

        assert result == mock_response
        mock_alert_service.send_http_error_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_403_error(self, mock_app, mock_alert_service):
        """Test dispatch with 403 error (should alert)"""
        middleware = ErrorMonitoringMiddleware(mock_app, mock_alert_service)

        mock_request = MagicMock()
        mock_request.app.state = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.headers.get.return_value = "test-agent"

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {}
        mock_response.body = b'{"detail": "Forbidden"}'

        async def call_next(request):
            return mock_response

        result = await middleware.dispatch(mock_request, call_next)

        assert result == mock_response
        mock_alert_service.send_http_error_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_high_latency(self, mock_app, mock_alert_service):
        """Test dispatch with high latency"""
        middleware = ErrorMonitoringMiddleware(mock_app, mock_alert_service)

        mock_request = MagicMock()
        mock_request.app.state = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.method = "GET"
        mock_request.url.path = "/api/test"
        mock_request.headers.get.return_value = "test-agent"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}

        async def call_next(request):
            import asyncio

            await asyncio.sleep(0.1)  # Simulate slow request
            return mock_response

        # Settings is imported inside the function, so patch at the source
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.latency_alert_threshold_ms = 50  # 50ms threshold

            result = await middleware.dispatch(mock_request, call_next)

            assert result == mock_response
            # Should send latency alert
            mock_alert_service.send_latency_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_exception(self, mock_app, mock_alert_service):
        """Test dispatch with exception"""
        middleware = ErrorMonitoringMiddleware(mock_app, mock_alert_service)

        mock_request = MagicMock()
        mock_request.app.state = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.headers.get.return_value = "test-agent"

        async def call_next(request):
            raise ValueError("Test error")

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 500
        mock_alert_service.send_http_error_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_exception_alert_failure(self, mock_app, mock_alert_service):
        """Test dispatch with exception when alert fails"""
        middleware = ErrorMonitoringMiddleware(mock_app, mock_alert_service)
        mock_alert_service.send_http_error_alert.side_effect = Exception("Alert failed")

        mock_request = MagicMock()
        mock_request.app.state = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.headers.get.return_value = "test-agent"

        async def call_next(request):
            raise ValueError("Test error")

        result = await middleware.dispatch(mock_request, call_next)

        assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_resolve_alert_service_from_app_state(self, mock_app):
        """Test resolving alert service from app.state"""
        mock_alert_service = MagicMock()
        mock_app.state.alert_service = mock_alert_service

        middleware = ErrorMonitoringMiddleware(mock_app, None)

        mock_request = MagicMock()
        mock_request.app.state = mock_app.state

        resolved = middleware._resolve_alert_service(mock_request)
        assert resolved == mock_alert_service

    @pytest.mark.asyncio
    async def test_handle_error_response_with_json_body(self, mock_app, mock_alert_service):
        """Test handling error response with JSON body"""
        middleware = ErrorMonitoringMiddleware(mock_app, mock_alert_service)

        mock_request = MagicMock()
        mock_request.app.state = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.headers.get.return_value = "test-agent"

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.body = b'{"detail": "Server error"}'

        await middleware._handle_error_response(mock_request, mock_response, "req-123", 100.0)

        mock_alert_service.send_http_error_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_error_response_invalid_json(self, mock_app, mock_alert_service):
        """Test handling error response with invalid JSON"""
        middleware = ErrorMonitoringMiddleware(mock_app, mock_alert_service)

        mock_request = MagicMock()
        mock_request.app.state = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.headers.get.return_value = "test-agent"

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.body = b"invalid json"

        await middleware._handle_error_response(mock_request, mock_response, "req-123", 100.0)

        mock_alert_service.send_http_error_alert.assert_called_once()

    def test_create_error_monitoring_middleware(self, mock_app):
        """Test factory function"""
        mock_alert_service = MagicMock()
        factory = create_error_monitoring_middleware(mock_alert_service)
        middleware = factory(mock_app)

        assert isinstance(middleware, ErrorMonitoringMiddleware)
        assert middleware.alert_service == mock_alert_service
