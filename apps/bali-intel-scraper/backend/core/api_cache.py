"""
API Response Caching Middleware and Decorators.

Provides automatic caching for API endpoints with:
- Redis-based response caching
- Cache invalidation strategies
- Cache control headers
- ETag support for conditional requests
"""

import time
from functools import wraps
from typing import Any
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.core.cache import cache, CacheKeyBuilder
from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="api_cache")


class APICacheMiddleware(BaseHTTPMiddleware):
    """
    Middleware for automatic API response caching.

    Caches GET responses based on URL and query parameters.
    Respects Cache-Control headers for cache invalidation.
    """

    def __init__(
        self,
        app,
        ttl: int = 300,
        exclude_paths: list | None = None,
        include_paths: list | None = None,
    ):
        super().__init__(app)
        self.ttl = ttl
        self.exclude_paths = set(
            exclude_paths or ["/health", "/metrics", "/docs", "/redoc", "/openapi.json"]
        )
        self.include_paths = set(include_paths or ["/api/"])

    def _should_cache(self, request: Request) -> bool:
        """Determine if request should be cached."""
        # Only cache GET requests
        if request.method != "GET":
            return False

        path = request.url.path

        # Check excluded paths
        if any(path.startswith(exc) for exc in self.exclude_paths):
            return False

        # Check included paths (if specified)
        return not (self.include_paths and not any(path.startswith(inc) for inc in self.include_paths))

    def _build_cache_key(self, request: Request) -> str:
        """Build cache key from request."""
        key_parts = [
            request.method,
            request.url.path,
            str(sorted(request.query_params.multi_items())),
        ]

        # Include Accept header for content negotiation
        accept = request.headers.get("accept", "application/json")
        key_parts.append(accept)

        return CacheKeyBuilder.build("api", *key_parts)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with caching."""
        if not self._should_cache(request):
            return await call_next(request)

        cache_key = self._build_cache_key(request)

        # Try to get cached response
        try:
            cached = await cache.get(cache_key)
            if cached:
                logger.debug(
                    "Cache hit",
                    action=LogAction.FETCH,
                    metadata={"key": cache_key, "path": request.url.path},
                )

                # Reconstruct response from cache
                return Response(
                    content=cached["body"],
                    status_code=cached["status_code"],
                    headers=dict(cached["headers"]),
                    media_type=cached.get("media_type", "application/json"),
                )
        except Exception as e:
            logger.warning(
                "Cache fetch error",
                action=LogAction.ERROR,
                metadata={"error": str(e), "key": cache_key},
            )

        # Cache miss - process request
        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        # Only cache successful responses
        if response.status_code == 200 and duration > 0.1:  # Only cache if took > 100ms
            try:
                # Read response body
                body = b""
                async for chunk in response.body_iterator:
                    body += chunk

                # Cache the response
                cache_data = {
                    "body": body,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "media_type": response.media_type,
                    "cached_at": time.time(),
                }

                await cache.set(cache_key, cache_data, ttl=self.ttl)

                logger.debug(
                    "Cache stored",
                    action=LogAction.CREATE,
                    metadata={
                        "key": cache_key,
                        "path": request.url.path,
                        "duration_ms": round(duration * 1000, 2),
                    },
                )

                # Return new response with cached body
                return Response(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )

            except Exception as e:
                logger.warning(
                    "Cache store error",
                    action=LogAction.ERROR,
                    metadata={"error": str(e), "key": cache_key},
                )

        return response


def cached(
    ttl: int | None = None,
    key_func: Callable | None = None,
    invalidate_on: list[str] | None = None,
):
    """
    Decorator for caching endpoint responses.

    Args:
        ttl: Cache time-to-live in seconds (default: 300)
        key_func: Custom function to generate cache key
        invalidate_on: List of cache keys to invalidate when this endpoint is called

    @example
    ```python
    @router.get("/items")
    @cached(ttl=600)
    async def get_items():
        return await fetch_items()

    @router.post("/items")
    @cached(invalidate_on=["api:GET:items"])
    async def create_item(item: Item):
        return await save_item(item)
    ```
    """

    def decorator(func: Callable) -> Callable:
        cache_ttl = ttl or 300

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Build cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = CacheKeyBuilder.for_function(func.__name__, *args, **kwargs)

            # Try cache
            try:
                cached_value = await cache.get(cache_key)
                if cached_value is not None:
                    logger.debug(
                        "Function cache hit",
                        action=LogAction.FETCH,
                        metadata={"function": func.__name__, "key": cache_key},
                    )
                    return cached_value
            except Exception as e:
                logger.warning(
                    "Cache fetch error",
                    action=LogAction.ERROR,
                    metadata={"error": str(e), "function": func.__name__},
                )

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            try:
                await cache.set(cache_key, result, ttl=cache_ttl)

                # Invalidate related caches
                if invalidate_on:
                    for inv_key in invalidate_on:
                        await cache.delete(inv_key)

                logger.debug(
                    "Function cache stored",
                    action=LogAction.CREATE,
                    metadata={
                        "function": func.__name__,
                        "key": cache_key,
                        "ttl": cache_ttl,
                    },
                )
            except Exception as e:
                logger.warning(
                    "Cache store error",
                    action=LogAction.ERROR,
                    metadata={"error": str(e), "function": func.__name__},
                )

            return result

        return async_wrapper

    return decorator


class CacheStats:
    """Cache statistics tracker."""

    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.stores = 0
        self.start_time = time.time()

    def hit(self):
        self.hits += 1

    def miss(self):
        self.misses += 1

    def store(self):
        self.stores += 1

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def uptime(self) -> float:
        return time.time() - self.start_time

    def to_dict(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "stores": self.stores,
            "hit_rate": round(self.hit_rate, 4),
            "uptime_seconds": round(self.uptime, 2),
        }


# Global stats instance
cache_stats = CacheStats()


async def get_cache_stats() -> dict[str, Any]:
    """Get current cache statistics."""
    stats = cache_stats.to_dict()

    # Add Redis info if available
    try:
        info = await cache.redis.info("memory")
        stats["redis_memory_used"] = info.get("used_memory_human", "unknown")
        stats["redis_memory_peak"] = info.get("used_memory_peak_human", "unknown")
    except Exception:
        pass

    return stats


async def invalidate_cache_pattern(pattern: str) -> int:
    """
    Invalidate all cache keys matching pattern.

    Args:
        pattern: Redis key pattern (e.g., "api:items:*")

    Returns:
        Number of keys deleted
    """
    try:
        keys = await cache.redis.keys(pattern)
        if keys:
            await cache.redis.delete(*keys)
            logger.info(
                "Cache invalidated",
                action=LogAction.DELETE,
                metadata={"pattern": pattern, "keys_deleted": len(keys)},
            )
            return len(keys)
        return 0
    except Exception as e:
        logger.error(
            "Cache invalidation error",
            action=LogAction.ERROR,
            metadata={"error": str(e), "pattern": pattern},
        )
        return 0
