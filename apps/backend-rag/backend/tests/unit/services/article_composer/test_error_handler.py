"""
Unit tests for Error Handler
"""

import json
from unittest.mock import MagicMock

import anthropic
from fastapi import HTTPException

from backend.services.article_composer.error_handler import (
    APIError,
    ErrorCode,
    handle_anthropic_error,
    handle_json_error,
    handle_validation_error,
)


class TestAPIError:
    """Test APIError model"""

    def test_create_api_error(self):
        """Test creating APIError instance"""
        error = APIError.create(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message="Rate limit exceeded",
            details={"retry_after": 60},
            request_id="test-123",
        )

        assert error.code == "RATE_LIMIT_EXCEEDED"
        assert error.message == "Rate limit exceeded"
        assert error.details == {"retry_after": 60}
        assert error.request_id == "test-123"
        assert error.timestamp is not None

    def test_api_error_serialization(self):
        """Test APIError can be serialized"""
        error = APIError.create(
            code=ErrorCode.API_ERROR,
            message="Test error",
        )

        error_dict = error.model_dump()
        assert isinstance(error_dict, dict)
        assert error_dict["code"] == "API_ERROR"
        assert error_dict["message"] == "Test error"


class TestHandleAnthropicError:
    """Test Anthropic error handlers"""

    def test_handle_rate_limit_error(self):
        """Test handling rate limit error"""
        # Create mock response object
        mock_response = MagicMock()
        mock_response.request = MagicMock()
        error = anthropic.RateLimitError("Rate limit exceeded", response=mock_response, body=None)

        http_exception = handle_anthropic_error(
            error, article_title="Test", category="business", request_id="test-123"
        )

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == 429
        error_detail = http_exception.detail
        assert error_detail["code"] == "RATE_LIMIT_EXCEEDED"

    def test_handle_connection_error(self):
        """Test handling connection error"""
        error = anthropic.APIConnectionError(
            message="Connection failed",
            request=None,
        )

        http_exception = handle_anthropic_error(
            error, article_title="Test", category="business", request_id="test-123"
        )

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == 503
        error_detail = http_exception.detail
        assert error_detail["code"] == "API_CONNECTION_ERROR"

    def test_handle_timeout_error(self):
        """Test handling timeout error"""
        mock_request = MagicMock()
        error = anthropic.APITimeoutError("Request timed out", request=mock_request)

        http_exception = handle_anthropic_error(
            error, article_title="Test", category="business", request_id="test-123"
        )

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == 504
        error_detail = http_exception.detail
        assert error_detail["code"] == "API_TIMEOUT"

    def test_handle_authentication_error(self):
        """Test handling authentication error"""
        mock_response = MagicMock()
        mock_response.request = MagicMock()
        error = anthropic.AuthenticationError("Invalid API key", response=mock_response, body=None)

        http_exception = handle_anthropic_error(
            error, article_title="Test", category="business", request_id="test-123"
        )

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == 401
        error_detail = http_exception.detail
        assert error_detail["code"] == "API_KEY_NOT_CONFIGURED"

    def test_handle_generic_api_error(self):
        """Test handling generic API error"""
        mock_response = MagicMock()
        mock_response.request = MagicMock()
        error = anthropic.APIError("Generic error", response=mock_response, body=None, request=None)

        http_exception = handle_anthropic_error(
            error, article_title="Test", category="business", request_id="test-123"
        )

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == 500
        error_detail = http_exception.detail
        assert error_detail["code"] == "API_ERROR"


class TestHandleJsonError:
    """Test JSON error handlers"""

    def test_handle_json_decode_error(self):
        """Test handling JSON decode error"""
        error = json.JSONDecodeError("Expecting value", "invalid json", 0)
        response_text = '{"invalid": json}'

        api_error = handle_json_error(
            error, response_text, article_title="Test", request_id="test-123"
        )

        assert isinstance(api_error, APIError)
        assert api_error.code == "JSON_PARSE_ERROR"
        assert api_error.details["response_preview"] == response_text[:500]


class TestHandleValidationError:
    """Test validation error handlers"""

    def test_handle_validation_error(self):
        """Test handling validation error"""
        error = ValueError("Invalid category")

        api_error = handle_validation_error(
            error, article_title="Test", request_id="test-123"
        )

        assert isinstance(api_error, APIError)
        assert api_error.code == "VALIDATION_ERROR"
        assert "Invalid category" in api_error.message
