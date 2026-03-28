"""
Caching utilities for application-wide caching strategies.

Provides decorators and helpers for intelligent caching with TTL,
cache invalidation, and cache warming.
"""

import functools
import hashlib
import json
import logging
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def generate_cache_key(*args: Any, **kwargs: Any) -> str:
    """
    Generate a deterministic cache key from arguments.

    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        MD5 hash string (first 16 chars)
    """
    key_data = {
        "args": args,
        "kwargs": kwargs,
    }
    key_str = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(key_str.encode()).hexdigest()[:16]


def cached(
    ttl: int = 300,
    key_prefix: str = "",
    cache_attr: str = "cache",
) -> Any:
    """
    Decorator for caching async method results.

    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key
        cache_attr: Attribute name of cache service on self

    Returns:
        Decorated function
    """

    def decorator(func: Any) -> Any:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Get cache service
            cache = getattr(self, cache_attr, None)
            if cache is None:
                logger.warning(f"No cache service found at {cache_attr}, executing without cache")
                return await func(self, *args, **kwargs)

            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}:{generate_cache_key(*args, **kwargs)}"

            # Try to get from cache
            try:
                cached_value = await cache.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"Cache hit: {cache_key}")
                    return cached_value
            except Exception as e:
                logger.warning(f"Cache get error: {e}")

            # Execute function
            result = await func(self, *args, **kwargs)

            # Store in cache
            try:
                await cache.set(cache_key, result, ttl=ttl)
                logger.debug(f"Cache set: {cache_key}")
            except Exception as e:
                logger.warning(f"Cache set error: {e}")

            return result

        return wrapper

    return decorator


def cached_sync(
    _ttl: int = 300,
    _key_prefix: str = "",
    maxsize: int = 128,
) -> Any:
    """
    Decorator for caching sync function results using LRU cache.

    Args:
        ttl: Time to live (not enforced by LRU, for documentation)
        key_prefix: Prefix for documentation
        maxsize: Maximum cache size

    Returns:
        Decorated function
    """
    return functools.lru_cache(maxsize=maxsize)


class CacheWarmer:
    """Cache warming utility for pre-populating cache."""

    def __init__(self, cache_service: Any) -> None:
        self.cache = cache_service
        self._warmup_tasks: list[Any] = []

    def register(self, key: str, data: Any, ttl: int = 3600) -> None:
        """Register data to be cached during warmup."""
        self._warmup_tasks.append((key, data, ttl))

    async def warmup(self) -> dict[str, bool]:
        """Execute all registered warmup tasks."""
        results = {}
        for key, data, ttl in self._warmup_tasks:
            try:
                await self.cache.set(key, data, ttl=ttl)
                results[key] = True
            except Exception as e:
                logger.warning(f"Cache warmup failed for {key}: {e}")
                results[key] = False

        self._warmup_tasks.clear()
        return results


class Memoize:
    """Memoization with TTL for instance methods."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl = ttl_seconds
        self._cache: dict[str, tuple[Any, float]] = {}

    def __call__(self, func):
        import time

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            key = generate_cache_key(args, kwargs)

            # Check cache
            if key in self._cache:
                result, timestamp = self._cache[key]
                if time.time() - timestamp < self.ttl:
                    return result

            # Execute and cache
            result = await func(*args, **kwargs)
            self._cache[key] = (result, time.time())
            return result

        # Attach cache clear method
        wrapper.clear_cache = self._clear_cache  # type: ignore
        return wrapper

    def _clear_cache(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
