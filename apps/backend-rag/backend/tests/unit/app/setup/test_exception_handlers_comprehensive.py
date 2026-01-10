"""
Comprehensive unit tests for app/setup/exception_handlers.py
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.setup.exception_handlers import (
    http_exception_handler,
    sanitize_detail,
    starlette_http_exception_handler,
    validation_exception_handler,
)


class TestSanitizeDetail:
    """Tests for sanitize_detail function"""

    def test_sanitize_string(self):
        """Test sanitizing string detail"""
        result = sanitize_detail("Error message")
        assert result == "Error message"

    def test_sanitize_dict(self):
        """Test sanitizing dict detail"""
        detail = {"error": "message", "code": 500}
        result = sanitize_detail(detail)
        assert result == {"error": "message", "code": 500}

    def test_sanitize_dict_with_list(self):
        """Test sanitizing dict with list"""
        detail = {"errors": ["error1", "error2"], "code": 500}
        result = sanitize_detail(detail)
        assert result == {"errors": ["error1", "error2"], "code": 500}

    def test_sanitize_dict_with_non_serializable(self):
        """Test sanitizing dict with non-serializable values"""
        non_serializable = MagicMock()
        detail = {"error": "message", "obj": non_serializable}
        result = sanitize_detail(detail)
        assert result["error"] == "message"
        assert isinstance(result["obj"], str)

    def test_sanitize_non_serializable_object(self):
        """Test sanitizing non-serializable object"""
        non_serializable = MagicMock()
        result = sanitize_detail(non_serializable)
        assert isinstance(result, str)


class TestHTTPExceptionHandler:
    """Tests for http_exception_handler"""

    @pytest.fixture
    def mock_request(self):
        """Create mock request"""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.correlation_id = "test-correlation-id"
        request.method = "GET"
        request.url.path = "/api/test"
        return request

    @pytest.mark.asyncio
    async def test_handler_with_string_detail(self, mock_request):
        """Test handler with string detail"""
        exc = HTTPException(status_code=404, detail="Not found")
        response = await http_exception_handler(mock_request, exc)

        assert response.status_code == 404
        assert "correlation_id" in response.body.decode()

    @pytest.mark.asyncio
    async def test_handler_with_dict_detail(self, mock_request):
        """Test handler with dict detail"""
        exc = HTTPException(status_code=400, detail={"error": "Bad request", "code": 400})
        response = await http_exception_handler(mock_request, exc)

        assert response.status_code == 400
        content = response.body.decode()
        assert "error" in content

    @pytest.mark.asyncio
    async def test_handler_with_headers(self, mock_request):
        """Test handler preserves headers"""
        exc = HTTPException(status_code=401, detail="Unauthorized", headers={"X-Custom": "value"})
        response = await http_exception_handler(mock_request, exc)

        assert response.status_code == 401
        assert "X-Correlation-ID" in response.headers

    @pytest.mark.asyncio
    async def test_handler_without_correlation_id(self, mock_request):
        """Test handler without correlation ID"""
        mock_request.state.correlation_id = None
        mock_request.state.request_id = None

        exc = HTTPException(status_code=500, detail="Error")
        response = await http_exception_handler(mock_request, exc)

        assert response.status_code == 500
        assert "correlation_id" in response.body.decode()


class TestStarletteHTTPExceptionHandler:
    """Tests for starlette_http_exception_handler"""

    @pytest.fixture
    def mock_request(self):
        """Create mock request"""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.correlation_id = "test-correlation-id"
        request.method = "POST"
        request.url.path = "/api/test"
        return request

    @pytest.mark.asyncio
    async def test_handler_starlette_exception(self, mock_request):
        """Test handler for Starlette HTTPException"""
        exc = StarletteHTTPException(status_code=404, detail="Not found")
        response = await starlette_http_exception_handler(mock_request, exc)

        assert response.status_code == 404
        assert "correlation_id" in response.body.decode()


class TestValidationExceptionHandler:
    """Tests for validation_exception_handler"""

    @pytest.fixture
    def mock_request(self):
        """Create mock request"""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.correlation_id = "test-correlation-id"
        request.method = "POST"
        request.url.path = "/api/test"
        return request

    @pytest.mark.asyncio
    async def test_handler_validation_error(self, mock_request):
        """Test handler for validation error"""
        errors = [{"loc": ["body", "field"], "msg": "field required", "type": "value_error"}]
        exc = RequestValidationError(errors=errors)

        response = await validation_exception_handler(mock_request, exc)

        assert response.status_code == 422
        assert "detail" in response.body.decode()
