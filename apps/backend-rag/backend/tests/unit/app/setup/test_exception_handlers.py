"""
Unit tests for exception handlers
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request, status
from starlette.exceptions import HTTPException as StarletteHTTPException

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.setup.exception_handlers import (
    general_exception_handler,
    http_exception_handler,
    sanitize_detail,
    starlette_http_exception_handler,
)


@pytest.fixture
def mock_request():
    """Mock FastAPI request"""
    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.method = "GET"
    request.url.path = "/test"
    return request


class TestSanitizeDetail:
    """Tests for sanitize_detail function"""

    def test_sanitize_string(self):
        """Test sanitizing string detail"""
        result = sanitize_detail("Test error")
        assert result == "Test error"

    def test_sanitize_dict(self):
        """Test sanitizing dict detail"""
        detail = {"error": "test", "code": 123}
        result = sanitize_detail(detail)
        assert result == {"error": "test", "code": 123}

    def test_sanitize_dict_with_list(self):
        """Test sanitizing dict with list"""
        detail = {"errors": ["error1", "error2"]}
        result = sanitize_detail(detail)
        assert result == {"errors": ["error1", "error2"]}

    def test_sanitize_dict_with_non_serializable(self):
        """Test sanitizing dict with non-serializable object"""
        non_serializable = object()
        detail = {"error": non_serializable}
        result = sanitize_detail(detail)
        assert isinstance(result["error"], str)

    def test_sanitize_non_serializable_object(self):
        """Test sanitizing non-serializable object"""
        non_serializable = object()
        result = sanitize_detail(non_serializable)
        assert isinstance(result, str)


class TestHTTPExceptionHandler:
    """Tests for http_exception_handler"""

    @pytest.mark.asyncio
    async def test_http_exception_handler_with_string_detail(self, mock_request):
        """Test handling HTTPException with string detail"""
        exc = HTTPException(status_code=400, detail="Bad request")
        mock_request.state.correlation_id = "test-id"

        response = await http_exception_handler(mock_request, exc)

        assert response.status_code == 400
        assert hasattr(response, "status_code")

    @pytest.mark.asyncio
    async def test_http_exception_handler_with_dict_detail(self, mock_request):
        """Test handling HTTPException with dict detail"""
        exc = HTTPException(status_code=400, detail={"error": "Bad request"})
        mock_request.state.correlation_id = None
        mock_request.state.request_id = "request-id"

        response = await http_exception_handler(mock_request, exc)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_http_exception_handler_without_correlation_id(self, mock_request):
        """Test handling HTTPException without correlation ID"""
        exc = HTTPException(status_code=500, detail="Internal error")
        mock_request.state.correlation_id = None
        mock_request.state.request_id = None

        response = await http_exception_handler(mock_request, exc)

        assert response.status_code == 500


class TestStarletteHTTPExceptionHandler:
    """Tests for starlette_http_exception_handler"""

    @pytest.mark.asyncio
    async def test_starlette_http_exception_handler(self, mock_request):
        """Test handling StarletteHTTPException"""
        exc = StarletteHTTPException(status_code=404, detail="Not found")
        mock_request.state.correlation_id = "test-id"

        response = await starlette_http_exception_handler(mock_request, exc)

        assert response.status_code == 404
        assert hasattr(response, "status_code")


class TestGeneralExceptionHandler:
    """Tests for general_exception_handler"""

    @pytest.mark.asyncio
    async def test_general_exception_handler(self, mock_request):
        """Test handling general exception"""
        exc = ValueError("Test error")
        mock_request.state.correlation_id = "test-id"

        response = await general_exception_handler(mock_request, exc)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert hasattr(response, "status_code")

    @pytest.mark.asyncio
    async def test_general_exception_handler_with_pool_error(self, mock_request):
        """Test handling exception with Pool reference"""

        # Use a simple object instead of MagicMock to avoid serialization issues
        class SimpleState:
            correlation_id = None
            request_id = None

        mock_request.state = SimpleState()
        exc = Exception("Pool connection error")

        response = await general_exception_handler(mock_request, exc)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_general_exception_handler_long_message(self, mock_request):
        """Test handling exception with long message"""
        exc = Exception("A" * 300)  # Very long message
        mock_request.state.correlation_id = "test-id"

        response = await general_exception_handler(mock_request, exc)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
