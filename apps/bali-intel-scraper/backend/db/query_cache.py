"""
Database Query Result Caching Layer.

Provides:
- Automatic query result caching with Redis
- Cache invalidation on data changes
- Decorator for easy integration
- Query hash generation for cache keys
"""

import hashlib
import json
from functools import wraps
from typing import Any
from collections.abc import Callable

from backend.core.cache import cache, CacheKeyBuilder
from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="query_cache")


class QueryCache:
    """Cache for database query results."""

    DEFAULT_TTL = 300  # 5 minutes

    @staticmethod
    def _generate_query_hash(query: str, params: tuple) -> str:
        """Generate unique hash for query and params."""
        query_data = {
            "query": query,
            "params": params,
        }
        return hashlib.md5(
            json.dumps(query_data, sort_keys=True, default=str).encode()
        ).hexdigest()

    @staticmethod
    def _build_cache_key(query_hash: str, table: str) -> str:
        """Build cache key for query result."""
        return CacheKeyBuilder.build("query", table, query_hash)

    @classmethod
    async def get(
        cls,
        query: str,
        params: tuple = (),
        table: str = "default",
    ) -> Any | None:
        """
        Get cached query result.

        Args:
            query: SQL query string
            params: Query parameters
            table: Table name for cache invalidation

        Returns:
            Cached result or None
        """
        query_hash = cls._generate_query_hash(query, params)
        cache_key = cls._build_cache_key(query_hash, table)

        try:
            result = await cache.get(cache_key)
            if result is not None:
                logger.debug(
                    "Query cache hit",
                    action=LogAction.FETCH,
                    metadata={"table": table, "query_hash": query_hash[:8]},
                )
                return result
        except Exception as e:
            logger.warning(
                "Query cache fetch error",
                action=LogAction.ERROR,
                metadata={"error": str(e), "table": table},
            )

        return None

    @classmethod
    async def set(
        cls,
        query: str,
        params: tuple,
        result: Any,
        table: str = "default",
        ttl: int = DEFAULT_TTL,
    ) -> None:
        """
        Cache query result.

        Args:
            query: SQL query string
            params: Query parameters
            result: Query result to cache
            table: Table name for cache invalidation
            ttl: Cache TTL in seconds
        """
        query_hash = cls._generate_query_hash(query, params)
        cache_key = cls._build_cache_key(query_hash, table)

        try:
            await cache.set(cache_key, result, ttl=ttl)
            logger.debug(
                "Query cached",
                action=LogAction.CREATE,
                metadata={
                    "table": table,
                    "query_hash": query_hash[:8],
                    "ttl": ttl,
                },
            )
        except Exception as e:
            logger.warning(
                "Query cache store error",
                action=LogAction.ERROR,
                metadata={"error": str(e), "table": table},
            )

    @classmethod
    async def invalidate_table(cls, table: str) -> int:
        """
        Invalidate all cached queries for a table.

        Args:
            table: Table name

        Returns:
            Number of keys invalidated
        """
        pattern = CacheKeyBuilder.build("query", table, "*")

        try:
            keys = await cache.redis.keys(pattern)
            if keys:
                await cache.redis.delete(*keys)
                logger.info(
                    "Query cache invalidated",
                    action=LogAction.DELETE,
                    metadata={"table": table, "keys": len(keys)},
                )
                return len(keys)
        except Exception as e:
            logger.error(
                "Query cache invalidation error",
                action=LogAction.ERROR,
                metadata={"error": str(e), "table": table},
            )

        return 0

    @classmethod
    async def invalidate_all(cls) -> int:
        """Invalidate all query caches."""
        pattern = CacheKeyBuilder.build("query", "*")

        try:
            keys = await cache.redis.keys(pattern)
            if keys:
                await cache.redis.delete(*keys)
                logger.info(
                    "All query caches invalidated",
                    action=LogAction.DELETE,
                    metadata={"keys": len(keys)},
                )
                return len(keys)
        except Exception as e:
            logger.error(
                "Query cache invalidation error",
                action=LogAction.ERROR,
                metadata={"error": str(e)},
            )

        return 0


def cached_query(
    table: str,
    ttl: int = QueryCache.DEFAULT_TTL,
    skip_on_error: bool = True,
):
    """
    Decorator for caching database query results.

    Args:
        table: Table name for cache invalidation
        ttl: Cache TTL in seconds
        skip_on_error: If True, execute query on cache error

    @example
    ```python
    @cached_query(table="articles", ttl=600)
    async def get_recent_articles(days: int = 7) -> List[dict]:
        query = "SELECT * FROM articles WHERE created_at > NOW() - INTERVAL '$1 days'"
        return await db.fetch(query, days)
    ```
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key from function name and arguments
            cache_key_data = {
                "func": func.__name__,
                "args": args,
                "kwargs": kwargs,
            }

            # Try to get from cache
            try:
                cached = await QueryCache.get(
                    query=func.__name__,
                    params=(args, tuple(sorted(kwargs.items()))),
                    table=table,
                )
                if cached is not None:
                    return cached
            except Exception as e:
                if not skip_on_error:
                    raise
                logger.warning(
                    f"Cache get error in {func.__name__}",
                    action=LogAction.ERROR,
                    metadata={"error": str(e)},
                )

            # Execute query
            result = await func(*args, **kwargs)

            # Cache result
            try:
                await QueryCache.set(
                    query=func.__name__,
                    params=(args, tuple(sorted(kwargs.items()))),
                    result=result,
                    table=table,
                    ttl=ttl,
                )
            except Exception as e:
                if not skip_on_error:
                    raise
                logger.warning(
                    f"Cache set error in {func.__name__}",
                    action=LogAction.ERROR,
                    metadata={"error": str(e)},
                )

            return result

        return wrapper

    return decorator


class QueryInvalidationMixin:
    """Mixin for models to auto-invalidate query cache on changes."""

    _query_cache_table: str = ""

    async def invalidate_cache(self) -> int:
        """Invalidate query cache for this model's table."""
        if self._query_cache_table:
            return await QueryCache.invalidate_table(self._query_cache_table)
        return 0


# Common query patterns that benefit from caching
COMMON_QUERIES = {
    "articles": [
        "SELECT * FROM articles ORDER BY created_at DESC LIMIT 100",
        "SELECT COUNT(*) FROM articles WHERE status = 'published'",
    ],
    "clients": [
        "SELECT * FROM clients ORDER BY name LIMIT 50",
        "SELECT status, COUNT(*) FROM clients GROUP BY status",
    ],
}


async def prefetch_common_queries() -> None:
    """Prefetch and cache common queries on startup."""
    logger.info("Prefetching common queries", action=LogAction.START)

    for table, queries in COMMON_QUERIES.items():
        for query in queries:
            # Execute and cache will happen on first request
            logger.debug(
                "Registered common query for prefetch",
                metadata={"table": table, "query": query[:50]},
            )

    logger.info("Common queries registered", action=LogAction.END)
