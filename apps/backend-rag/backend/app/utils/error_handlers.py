"""
Standardized error handling utilities for routers.

Provides consistent error handling across all API endpoints.

Error response envelope (all endpoints should use this format):
    {
        "detail": "Human-readable message",
        "code": "machine_readable_code",   # optional, for programmatic handling
        "field": "field_name"              # optional, for validation errors
    }
"""

import logging
from typing import Any

import asyncpg
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def api_error(
    status_code: int,
    message: str,
    code: str | None = None,
    field: str | None = None,
) -> HTTPException:
    """
    Create a standardized HTTPException with consistent detail envelope.

    Args:
        status_code: HTTP status code
        message: Human-readable error message
        code: Machine-readable error code (e.g. "not_found", "forbidden")
        field: Field name for validation errors

    Returns:
        HTTPException with structured detail dict
    """
    detail: dict[str, Any] = {"message": message}
    if code:
        detail["code"] = code
    if field:
        detail["field"] = field
    return HTTPException(status_code=status_code, detail=detail)


def handle_database_error(e: Exception) -> HTTPException:
    """
    Handle database errors consistently across all routers.

    Args:
        e: The exception that occurred

    Returns:
        HTTPException: Appropriate HTTP exception with user-friendly message
    """
    if isinstance(e, asyncpg.UniqueViolationError):
        logger.warning(f"Unique constraint violation: {e}")
        return HTTPException(
            status_code=400, detail="A record with this information already exists",
        )

    if isinstance(e, asyncpg.ForeignKeyViolationError):
        logger.warning(f"Foreign key violation: {e}")
        return HTTPException(status_code=400, detail="Referenced record does not exist")

    if isinstance(e, asyncpg.CheckViolationError):
        logger.warning(f"Check constraint violation: {e}")
        return HTTPException(status_code=400, detail="Invalid data provided")

    if isinstance(e, asyncpg.PostgresError):
        logger.error(f"Database error: {e}", exc_info=True)
        return HTTPException(status_code=503, detail="Database service temporarily unavailable")

    # asyncpg.InterfaceError: "connection was closed in the middle of operation"
    # Happens on first request after Fly.io cold start — stale pool connection.
    # Return 503 so the client retries; the next request will get a fresh connection.
    if isinstance(e, asyncpg.InterfaceError):
        logger.warning(f"Stale DB connection (likely cold start): {e}")
        return HTTPException(
            status_code=503,
            detail="Database connection temporarily unavailable. Please retry.",
            headers={"Retry-After": "3"},
        )

    # Generic fallback
    logger.error(f"Unexpected error [{type(e).__name__}]: {e}", exc_info=True)
    return HTTPException(status_code=500, detail="Internal server error")
