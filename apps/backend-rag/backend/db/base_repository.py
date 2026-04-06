"""
Base repository with common database access patterns.

All repositories should inherit from this to ensure consistent
connection handling, error logging, and transaction management.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import asyncpg

T = TypeVar("T")


class BaseRepository:
    """Base class for all database repositories.

    Provides:
    - Consistent pool injection
    - ``execute_in_transaction`` for multi-step atomic ops
    - ``fetchrow_safe`` / ``fetch_safe`` with structured error logging
    """

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool
        self.logger = logging.getLogger(self.__class__.__qualname__)

    # ── Transaction helper ──────────────────────────────────────────────
    async def execute_in_transaction(
        self,
        callback: Callable[[asyncpg.Connection], Awaitable[T]],
    ) -> T:
        """Run *callback(conn)* inside an atomic transaction."""
        async with self.db_pool.acquire() as conn, conn.transaction():
            return await callback(conn)

    # ── Safe fetch helpers ──────────────────────────────────────────────
    async def fetchrow_safe(
        self, query: str, *args: Any,
    ) -> asyncpg.Record | None:
        """Fetch a single row, logging errors with context."""
        async with self.db_pool.acquire() as conn:
            try:
                return await conn.fetchrow(query, *args)
            except asyncpg.PostgresError as exc:
                self.logger.error("fetchrow failed: %s | query=%s", exc, query[:120], exc_info=True)
                raise

    async def fetch_safe(
        self, query: str, *args: Any,
    ) -> list[asyncpg.Record]:
        """Fetch multiple rows, logging errors with context."""
        async with self.db_pool.acquire() as conn:
            try:
                return await conn.fetch(query, *args)
            except asyncpg.PostgresError as exc:
                self.logger.error("fetch failed: %s | query=%s", exc, query[:120], exc_info=True)
                raise

    async def execute_safe(
        self, query: str, *args: Any,
    ) -> str:
        """Execute a statement, logging errors with context."""
        async with self.db_pool.acquire() as conn:
            try:
                return await conn.execute(query, *args)
            except asyncpg.PostgresError as exc:
                self.logger.error("execute failed: %s | query=%s", exc, query[:120], exc_info=True)
                raise
