"""
Exception Handlers for FastAPI Application

Provides global exception handlers to ensure proper error serialization
and prevent TypeError when serializing HTTPException with non-serializable objects.
"""

import logging
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("zantara.backend")


def sanitize_detail(detail: Any) -> str | dict[str, Any]:
    """
    Sanitize exception detail to ensure JSON serialization.

    Args:
        detail: Exception detail (can be str, dict, or any object)

    Returns:
        Sanitized detail (str or dict with only serializable values)
    """
    if isinstance(detail, str):
        return detail
    elif isinstance(detail, dict):
        # Create a copy and sanitize any non-serializable values
        sanitized = {}
        for key, value in detail.items():
            if isinstance(value, (str, int, float, bool, type(None))):
                sanitized[key] = value
            elif isinstance(value, (list, tuple)):
                # Recursively sanitize list items
                sanitized[key] = [
                    str(item) if not isinstance(item, (str, int, float, bool, type(None))) else item
                    for item in value
                ]
            else:
                # Convert non-serializable objects to string
                sanitized[key] = str(value)
        return sanitized
    else:
        # Convert non-serializable objects to string
        return str(detail)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Global handler for HTTPException.

    Ensures proper serialization of HTTPException.detail even if it contains
    non-serializable objects (e.g., asyncpg.Pool).

    Args:
        request: FastAPI request
        exc: HTTPException instance

    Returns:
        JSONResponse with sanitized error detail
    """
    correlation_id = (
        getattr(request.state, "correlation_id", None)
        or getattr(request.state, "request_id", None)
        or "unknown"
    )

    # Sanitize detail to prevent JSON serialization errors
    sanitized_detail = sanitize_detail(exc.detail)

    logger.warning(
        f"[{correlation_id}] HTTPException: {exc.status_code} - {request.method} {request.url.path}. "
        f"Detail: {sanitized_detail if isinstance(sanitized_detail, str) else 'See detail object'}"
    )

    # Build response headers
    headers = dict(exc.headers) if exc.headers else {}
    headers["X-Correlation-ID"] = correlation_id

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": sanitized_detail, "correlation_id": correlation_id},
        headers=headers,
    )


async def starlette_http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """
    Global handler for Starlette HTTPException (used by FastAPI internally).

    Args:
        request: FastAPI request
        exc: StarletteHTTPException instance

    Returns:
        JSONResponse with sanitized error detail
    """
    correlation_id = (
        getattr(request.state, "correlation_id", None)
        or getattr(request.state, "request_id", None)
        or "unknown"
    )

    # Sanitize detail
    sanitized_detail = sanitize_detail(exc.detail)

    logger.warning(
        f"[{correlation_id}] StarletteHTTPException: {exc.status_code} - {request.method} {request.url.path}"
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": sanitized_detail, "correlation_id": correlation_id},
        headers={"X-Correlation-ID": correlation_id},
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler for RequestValidationError (Pydantic validation errors).

    Args:
        request: FastAPI request
        exc: RequestValidationError instance

    Returns:
        JSONResponse with validation error details
    """

    correlation_id = (
        getattr(request.state, "correlation_id", None)
        or getattr(request.state, "request_id", None)
        or "unknown"
    )

    # Get validation errors
    errors = exc.errors() if hasattr(exc, "errors") else []

    logger.warning(
        f"[{correlation_id}] ValidationError: {len(errors)} validation errors - "
        f"{request.method} {request.url.path}"
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": errors,
            "correlation_id": correlation_id,
        },
        headers={"X-Correlation-ID": correlation_id},
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global handler for unhandled exceptions.

    Prevents TypeError when serializing exceptions with non-serializable objects.

    Args:
        request: FastAPI request
        exc: Exception instance

    Returns:
        JSONResponse with sanitized error detail
    """
    correlation_id = (
        getattr(request.state, "correlation_id", None)
        or getattr(request.state, "request_id", None)
        or "unknown"
    )

    error_type = type(exc).__name__
    error_module = getattr(type(exc), "__module__", "unknown")

    logger.critical(
        f"[{correlation_id}] Unhandled exception: Type={error_type}, Module={error_module}, "
        f"Request={request.method} {request.url.path}",
        exc_info=True,
    )

    # Sanitize error message
    try:
        error_msg = str(exc)
        # Remove any Pool references
        if "Pool" in error_msg or "asyncpg" in error_msg.lower():
            error_msg = "Database connection error"
        elif len(error_msg) > 200:
            error_msg = f"{error_type}: {error_msg[:200]}..."
    except Exception:
        error_msg = f"{error_type} error"

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": f"Internal server error: {error_msg}",
            "correlation_id": correlation_id,
            "error_type": error_type,
        },
        headers={"X-Correlation-ID": correlation_id},
    )
