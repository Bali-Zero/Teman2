"""
Database connection management with async pooling.

Provides connection pooling, retry logic, and transaction management
for PostgreSQL database operations.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, List, Any, Dict

import asyncpg
from asyncpg import Pool, Connection
from asyncpg.exceptions import (
    PostgresConnectionError,
    TooManyConnectionsError,
    ConnectionDoesNotExistError,
)

from config.settings import settings
from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="database")


class DatabaseManager:
    """Manages database connections and pooling."""

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._pool: Optional[Pool] = None
        self._config = settings.database
        self._initialized = True
        self._closing = False

    async def initialize(self) -> None:
        """Initialize the connection pool."""
        if self._pool is not None:
            return

        async with self._lock:
            if self._pool is not None:
                return

            logger.info(
                "Initializing database connection pool",
                action=LogAction.CONNECT,
                metadata={
                    "host": self._config.host,
                    "database": self._config.name,
                    "pool_size": self._config.pool_size,
                    "max_overflow": self._config.max_overflow,
                },
            )

            try:
                dsn = os.getenv("DATABASE_URL")
                if dsn:
                    self._pool = await asyncpg.create_pool(
                        dsn=dsn,
                        min_size=self._config.pool_size,
                        max_size=self._config.pool_size + self._config.max_overflow,
                        command_timeout=self._config.pool_timeout,
                        max_inactive_connection_lifetime=self._config.pool_recycle,
                        init=self._init_connection,
                    )
                else:
                    self._pool = await asyncpg.create_pool(
                        host=self._config.host,
                        port=self._config.port,
                        database=self._config.name,
                        user=self._config.user,
                        password=self._config.password,
                        min_size=self._config.pool_size,
                        max_size=self._config.pool_size + self._config.max_overflow,
                        command_timeout=self._config.pool_timeout,
                        max_inactive_connection_lifetime=self._config.pool_recycle,
                        init=self._init_connection,
                    )

                logger.info(
                    "Database connection pool initialized",
                    action=LogAction.CONNECT,
                    metadata={"status": "success"},
                )

            except Exception as e:
                logger.error(
                    "Failed to initialize database pool",
                    action=LogAction.CONNECT,
                    metadata={"error": str(e)},
                    exc_info=True,
                )
                raise

    async def _init_connection(self, conn: Connection) -> None:
        """Initialize new connections with custom settings."""
        # Set application name for monitoring
        await conn.execute("SET application_name = 'bali-intel-scraper'")

        # Set timezone
        await conn.execute("SET timezone = 'UTC'")

        # Enable JSON support
        await conn.set_type_codec("json", encoder=str, decoder=str, schema="pg_catalog")

    async def close(self) -> None:
        """Close the connection pool gracefully."""
        if self._pool is None or self._closing:
            return

        self._closing = True

        logger.info("Closing database connection pool", action=LogAction.DISCONNECT)

        try:
            await self._pool.close()
            self._pool = None
            self._closing = False

            logger.info("Database connection pool closed", action=LogAction.DISCONNECT)

        except Exception as e:
            logger.error(
                "Error closing database pool",
                action=LogAction.DISCONNECT,
                metadata={"error": str(e)},
                exc_info=True,
            )
            raise

    @asynccontextmanager
    async def acquire(
        self, timeout: Optional[float] = None
    ) -> AsyncGenerator[Connection, None]:
        """Acquire a connection from the pool with retry logic."""
        if self._pool is None:
            await self.initialize()

        conn = None
        max_retries = 3
        retry_delay = 0.5

        for attempt in range(max_retries):
            try:
                async with self._pool.acquire(timeout=timeout) as conn:
                    yield conn
                    return

            except (
                PostgresConnectionError,
                TooManyConnectionsError,
                ConnectionDoesNotExistError,
            ) as e:
                if attempt == max_retries - 1:
                    logger.error(
                        "Failed to acquire database connection after retries",
                        action=LogAction.CONNECT,
                        metadata={"attempts": max_retries, "error": str(e)},
                    )
                    raise

                logger.warning(
                    "Database connection attempt failed, retrying",
                    action=LogAction.RETRY,
                    metadata={
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                        "error": str(e),
                    },
                )
                await asyncio.sleep(retry_delay * (2**attempt))

    @asynccontextmanager
    async def transaction(
        self,
        isolation: str = "read_committed",
        readonly: bool = False,
        deferrable: bool = False,
    ) -> AsyncGenerator[Connection, None]:
        """Execute operations within a transaction."""
        async with self.acquire() as conn:
            async with conn.transaction(
                isolation=isolation, readonly=readonly, deferrable=deferrable
            ):
                yield conn

    async def execute(self, query: str, *args, timeout: Optional[float] = None) -> str:
        """Execute a query and return the status."""
        async with self.acquire() as conn:
            return await conn.execute(query, *args, timeout=timeout)

    async def fetch(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> List[asyncpg.Record]:
        """Fetch multiple rows."""
        async with self.acquire() as conn:
            return await conn.fetch(query, *args, timeout=timeout)

    async def fetchrow(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> Optional[asyncpg.Record]:
        """Fetch a single row."""
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args, timeout=timeout)

    async def fetchval(self, query: str, *args, timeout: Optional[float] = None) -> Any:
        """Fetch a single value."""
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args, timeout=timeout)

    async def executemany(
        self, query: str, args: List[tuple], timeout: Optional[float] = None
    ) -> None:
        """Execute a query multiple times with different arguments."""
        async with self.acquire() as conn:
            await conn.executemany(query, args, timeout=timeout)

    @property
    def pool_size(self) -> int:
        """Get current pool size."""
        return self._pool.get_size() if self._pool else 0

    @property
    def free_connections(self) -> int:
        """Get number of free connections in pool."""
        return self._pool.get_idle_size() if self._pool else 0

    async def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the database."""
        try:
            start_time = asyncio.get_event_loop().time()
            async with self.acquire(timeout=5) as conn:
                result = await conn.fetchval("SELECT 1")
                latency = asyncio.get_event_loop().time() - start_time

                return {
                    "status": "healthy",
                    "latency_ms": round(latency * 1000, 2),
                    "pool_size": self.pool_size,
                    "free_connections": self.free_connections,
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "pool_size": self.pool_size,
                "free_connections": self.free_connections,
            }


# Global database manager instance
db = DatabaseManager()


# Convenience functions for common operations
async def init_db() -> None:
    """Initialize database connection pool."""
    await db.initialize()


async def close_db() -> None:
    """Close database connection pool."""
    await db.close()


async def health_check() -> Dict[str, Any]:
    """Check database health."""
    return await db.health_check()


# Export
__all__ = [
    "DatabaseManager",
    "db",
    "init_db",
    "close_db",
    "health_check",
]
