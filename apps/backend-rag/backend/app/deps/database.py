"""
Database pool dependencies.

Provides asyncpg pool access to all routers via FastAPI Depends().
No heavy service imports — only asyncpg.
"""

import logging
from typing import Any

import asyncpg
from fastapi import Depends, HTTPException, Request

logger = logging.getLogger(__name__)

__all__ = [
    "get_database_pool",
    "get_database",
    "get_db",
    "get_optional_database_pool",
]


def get_database_pool(request: Request) -> asyncpg.Pool:
    """
    Dependency injection for database connection pool.

    Returns:
        asyncpg.Pool: The database connection pool.

    Raises:
        HTTPException 503: If pool is not initialized or unusable.
    """
    db_pool = getattr(request.app.state, "db_pool", None)

    if db_pool is None or not hasattr(db_pool, "acquire"):
        db_init_error = getattr(request.app.state, "db_init_error", None)
        error_message = "The database connection pool is not initialized."
        if db_init_error:
            error_message += f" Initialization error: {db_init_error}"

        raise HTTPException(
            status_code=503,
            detail=error_message,
            headers={
                "X-Error-Type": "database_unavailable",
                "Retry-After": "30",
            },
        )
    return db_pool


# Aliases for backward compatibility
get_database = get_database_pool
get_db = get_database_pool


def get_optional_database_pool(request: Request) -> Any:
    """
    Get database pool with graceful degradation.

    Unlike get_database_pool(), returns None instead of raising HTTPException
    when database is unavailable. Use for endpoints that can work with reduced functionality.

    Returns:
        asyncpg.Pool | None: The pool, or None if unavailable.
    """
    try:
        return get_database_pool(request)
    except HTTPException as exc:
        if exc.status_code == 503:
            return None
        raise
