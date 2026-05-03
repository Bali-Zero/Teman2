"""
Structured Error Handling for Article Composer

Best Practices 2026:
- Structured error responses
- Error context preservation
- Error recovery strategies
"""

import json
import logging
import traceback
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import httpx
from fastapi import HTTPException
from pydantic import BaseModel

from backend.llm.deepseek_client import DeepSeekAuthError, DeepSeekError

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """Standard error codes for Article Composer"""

    # API Errors
    API_KEY_NOT_CONFIGURED = "API_KEY_NOT_CONFIGURED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    API_CONNECTION_ERROR = "API_CONNECTION_ERROR"
    API_TIMEOUT = "API_TIMEOUT"
    API_ERROR = "API_ERROR"

    # Validation Errors
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_CATEGORY = "INVALID_CATEGORY"
    CONTENT_TOO_LARGE = "CONTENT_TOO_LARGE"
    INVALID_JSON_RESPONSE = "INVALID_JSON_RESPONSE"

    # Processing Errors
    ENRICHMENT_FAILED = "ENRICHMENT_FAILED"
    JSON_PARSE_ERROR = "JSON_PARSE_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # GitHub Errors
    GITHUB_NOT_CONFIGURED = "GITHUB_NOT_CONFIGURED"
    GITHUB_API_ERROR = "GITHUB_API_ERROR"
    SLUG_ALREADY_EXISTS = "SLUG_ALREADY_EXISTS"

    # Generic
    INTERNAL_ERROR = "INTERNAL_ERROR"
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"


class APIError(BaseModel):
    """Structured error response model"""

    code: str
    message: str
    details: dict[str, Any] | None = None
    timestamp: str
    request_id: str | None = None

    @classmethod
    def create(
        cls,
        code: ErrorCode | str,
        message: str,
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> "APIError":
        """Create a new APIError instance"""
        return cls(
            code=code.value if isinstance(code, ErrorCode) else code,
            message=message,
            details=details or {},
            timestamp=datetime.now(tz=timezone.utc).replace(tzinfo=None).isoformat(),
            request_id=request_id,
        )


def handle_anthropic_error(
    error: Exception,
    article_title: str | None = None,
    category: str | None = None,
    request_id: str | None = None,
) -> HTTPException:
    """Handle LLM API errors with structured responses.

    Name retained from the Claude era for router backward-compat. Now
    maps DeepSeek / httpx errors to structured ``APIError`` responses.
    """
    error_context = {
        "article_title": article_title,
        "category": category,
        "error_type": type(error).__name__,
        "error_message": str(error),
    }

    if isinstance(error, DeepSeekAuthError):
        api_error = APIError.create(
            code=ErrorCode.API_KEY_NOT_CONFIGURED,
            message="Invalid or missing DEEPSEEK_API_KEY",
            details={
                **error_context,
                "suggestion": "Check the DEEPSEEK_API_KEY environment variable",
            },
            request_id=request_id,
        )
        logger.error("DeepSeek auth error", extra=error_context)
        return HTTPException(status_code=401, detail=api_error.model_dump())

    if isinstance(error, httpx.TimeoutException):
        api_error = APIError.create(
            code=ErrorCode.API_TIMEOUT,
            message="DeepSeek request timed out",
            details={
                **error_context,
                "suggestion": "Request took too long, please retry",
            },
            request_id=request_id,
        )
        logger.error("DeepSeek timeout", extra=error_context)
        return HTTPException(status_code=504, detail=api_error.model_dump())

    if isinstance(error, httpx.ConnectError):
        api_error = APIError.create(
            code=ErrorCode.API_CONNECTION_ERROR,
            message="Failed to connect to DeepSeek API",
            details={
                **error_context,
                "suggestion": "Check network connectivity and retry",
            },
            request_id=request_id,
        )
        logger.error("DeepSeek connection error", extra=error_context, exc_info=True)
        return HTTPException(status_code=503, detail=api_error.model_dump())

    msg = str(error).lower()
    if isinstance(error, DeepSeekError) and ("429" in msg or "rate" in msg):
        api_error = APIError.create(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message="DeepSeek API rate limit exceeded",
            details={
                **error_context,
                "suggestion": "Please retry after a short backoff",
            },
            request_id=request_id,
        )
        logger.warning("DeepSeek rate limit", extra=error_context)
        return HTTPException(status_code=429, detail=api_error.model_dump())

    api_error = APIError.create(
        code=ErrorCode.API_ERROR,
        message=f"LLM API error: {str(error)}",
        details={
            **error_context,
            "traceback": traceback.format_exc(),
        },
        request_id=request_id,
    )
    logger.error("LLM API error", extra=error_context, exc_info=True)
    return HTTPException(status_code=500, detail=api_error.model_dump())


def handle_json_error(
    error: json.JSONDecodeError,
    response_text: str | None = None,
    article_title: str | None = None,
    request_id: str | None = None,
) -> APIError:
    """
    Handle JSON parsing errors with structured responses.

    Args:
        error: JSONDecodeError exception
        response_text: Raw response text that failed to parse
        article_title: Article title for context
        request_id: Request ID for tracing

    Returns:
        APIError instance
    """
    error_context = {
        "article_title": article_title,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "error_line": getattr(error, "lineno", None),
        "error_column": getattr(error, "colno", None),
        "response_preview": response_text[:500] if response_text else None,
    }

    logger.error("JSON parse error", extra=error_context)

    return APIError.create(
        code=ErrorCode.JSON_PARSE_ERROR,
        message=f"Failed to parse Claude response as JSON: {str(error)}",
        details=error_context,
        request_id=request_id,
    )


def handle_validation_error(
    error: Exception,
    article_title: str | None = None,
    request_id: str | None = None,
) -> APIError:
    """
    Handle validation errors with structured responses.

    Args:
        error: Validation error exception
        article_title: Article title for context
        request_id: Request ID for tracing

    Returns:
        APIError instance
    """
    error_context = {
        "article_title": article_title,
        "error_type": type(error).__name__,
        "error_message": str(error),
    }

    logger.error("Validation error", extra=error_context, exc_info=True)

    return APIError.create(
        code=ErrorCode.VALIDATION_ERROR,
        message=f"Validation failed: {str(error)}",
        details=error_context,
        request_id=request_id,
    )


def log_error_with_context(
    error: Exception,
    context: dict[str, Any],
    level: str = "ERROR",
) -> Any:
    """
    Log error with full context for debugging.

    Args:
        error: The exception
        context: Additional context dictionary
        level: Log level (ERROR, WARNING, etc.)
    """
    log_data = {
        **context,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback.format_exc(),
    }

    if level.upper() == "ERROR":
        logger.error("Error occurred", extra=log_data, exc_info=True)
    elif level.upper() == "WARNING":
        logger.warning("Warning occurred", extra=log_data)
    else:
        logger.info("Info", extra=log_data)
