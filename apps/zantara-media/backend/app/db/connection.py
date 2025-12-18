"""
ZANTARA MEDIA - Database Connection Pool
Manages PostgreSQL connections using asyncpg
"""

import logging
from typing import Optional, Any, List, Dict
import asyncpg
from app.config import settings

logger = logging.getLogger(__name__)

# Global connection pool
_db_pool: Optional[asyncpg.Pool] = None


async def get_db_pool() -> asyncpg.Pool:
    """
    Get or create the database connection pool.

    Returns:
        asyncpg.Pool: The connection pool
    """
    global _db_pool

    if _db_pool is None:
        if not settings.database_url:
            raise ValueError("DATABASE_URL not configured in settings")

        logger.info("Creating database connection pool...")
        _db_pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )
        logger.info("Database connection pool created")

    return _db_pool


async def close_db_pool():
    """Close the database connection pool."""
    global _db_pool

    if _db_pool:
        logger.info("Closing database connection pool...")
        await _db_pool.close()
        _db_pool = None
        logger.info("Database connection pool closed")


async def execute_query(query: str, *args, pool: Optional[asyncpg.Pool] = None) -> str:
    """
    Execute a query that doesn't return data (INSERT, UPDATE, DELETE).

    Args:
        query: SQL query
        *args: Query parameters
        pool: Optional connection pool (will use global if not provided)

    Returns:
        str: Query result status
    """
    if pool is None:
        pool = await get_db_pool()

    async with pool.acquire() as conn:
        result = await conn.execute(query, *args)
        return result


async def fetch_one(
    query: str, *args, pool: Optional[asyncpg.Pool] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch one row from the database.

    Args:
        query: SQL query
        *args: Query parameters
        pool: Optional connection pool

    Returns:
        Optional[Dict]: Row as dictionary or None
    """
    if pool is None:
        pool = await get_db_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def fetch_all(
    query: str, *args, pool: Optional[asyncpg.Pool] = None
) -> List[Dict[str, Any]]:
    """
    Fetch all rows from the database.

    Args:
        query: SQL query
        *args: Query parameters
        pool: Optional connection pool

    Returns:
        List[Dict]: List of rows as dictionaries
    """
    if pool is None:
        pool = await get_db_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(row) for row in rows]
