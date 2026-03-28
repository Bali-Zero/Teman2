"""
Redis Caching Layer for ZANTARA
Provides intelligent caching for expensive operations

Features:
- TTL-based expiration
- Automatic key generation
- Cache invalidation
- Hit/miss metrics
"""

import hashlib
import json
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from decimal import Decimal
from functools import wraps
from typing import Any


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types and Pydantic models."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        # Handle Pydantic v2 models
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        # Handle Pydantic v1 models
        if hasattr(obj, "dict"):
            return obj.dict()
        return super().default(obj)


logger = logging.getLogger(__name__)

# Constants
CACHE_KEY_HASH_LENGTH = 12
DEFAULT_CACHE_TTL = 300
DEFAULT_MAX_MEMORY_CACHE_SIZE = 1000


class LRUCache:
    """
    LRU Cache with TTL support for in-memory fallback.
    Automatically evicts least recently used items when max size reached.
    """

    def __init__(
        self,
        max_size: int = DEFAULT_MAX_MEMORY_CACHE_SIZE,
        maxsize: int | None = None,  # Alias for max_size (for compatibility)
        default_ttl: int = DEFAULT_CACHE_TTL,
    ) -> None:
        """
        Initialize LRU cache.

        Args:
            max_size: Maximum number of items to store
            maxsize: Alias for max_size (for compatibility with tests)
            default_ttl: Default TTL in seconds
        """
        self.max_size = maxsize if maxsize is not None else max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, tuple[Any, float]] = (
            OrderedDict()
        )  # key -> (value, expire_time)

    def get(self, key: str) -> Any | None:
        """Get value from cache if not expired."""
        if key not in self.cache:
            return None

        value, expire_time = self.cache[key]

        # Check if expired
        if time.time() > expire_time:
            del self.cache[key]
            return None

        # Move to end (most recently used)
        self.cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache with TTL."""
        ttl = ttl if ttl is not None else self.default_ttl
        expire_time = time.time() + ttl

        if key in self.cache:
            # Update existing
            self.cache.move_to_end(key)
        else:
            # Check if we need to evict
            if len(self.cache) >= self.max_size:
                # Remove least recently used (first item)
                self.cache.popitem(last=False)

        self.cache[key] = (value, expire_time)

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if key in self.cache:
            del self.cache[key]
            return True
        return False

    def clear(self) -> int:
        """Clear all cache entries."""
        count = len(self.cache)
        self.cache.clear()
        return count

    def clear_pattern(self, pattern: str) -> int:
        """Clear keys matching pattern."""
        keys_to_delete = [k for k in self.cache if pattern.replace("*", "") in k]
        for key in keys_to_delete:
            del self.cache[key]
        return len(keys_to_delete)

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count of removed items."""
        now = time.time()
        expired_keys = [k for k, (_, expire_time) in self.cache.items() if now > expire_time]
        for key in expired_keys:
            del self.cache[key]
        return len(expired_keys)


class CacheService:
    """
    Intelligent caching service with Redis backend
    Falls back to in-memory cache if Redis unavailable

    Uses dependency injection instead of global state.
    Each instance has its own in-memory cache (instance-level, not module-level).
    """

    def __init__(self) -> None:
        self.redis_available = False
        self.redis_client = None
        self.stats = {"hits": 0, "misses": 0, "errors": 0}

        # Instance-level in-memory cache
        self._memory_cache = LRUCache()

        # Get Redis client from centralized RedisManager
        from backend.core.redis_manager import RedisManager

        manager = RedisManager.get_instance()
        client = manager.get_async_client()
        if client is not None:
            self.redis_client = client
            self.redis_available = True
            manager.register_component("cache_service", "active")
            logger.info("Redis cache connected via RedisManager (async)")
        else:
            manager.register_component("cache_service", "fallback_memory")
            logger.info("No Redis available, using in-memory cache")

    def _is_serializable(self, obj: Any) -> bool:
        """Check if an object is JSON serializable."""
        type_name = type(obj).__name__
        non_serializable_types = {
            "Pool",
            "Connection",
            "Request",
            "Response",
            "WebSocket",
            "BackgroundTasks",
            "State",
            "HTTPConnection",
        }
        if type_name in non_serializable_types:
            return False

        try:
            json.dumps(obj)
            return True
        except (TypeError, ValueError):
            return False

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from function arguments."""
        filtered_args = []
        for i, arg in enumerate(args):
            if i == 0 and hasattr(arg, "__dict__"):
                continue
            if not self._is_serializable(arg):
                continue
            filtered_args.append(arg)

        filtered_kwargs = {k: v for k, v in kwargs.items() if self._is_serializable(v)}

        key_data = json.dumps(
            {"args": filtered_args, "kwargs": filtered_kwargs},
            sort_keys=True,
            default=str,
        )
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:CACHE_KEY_HASH_LENGTH]
        return f"zantara:{prefix}:{key_hash}"

    async def get(self, key: str) -> Any | None:
        """Get value from cache"""
        try:
            if self.redis_available and self.redis_client:
                value = await self.redis_client.get(key)
                if value:
                    self.stats["hits"] += 1
                    return json.loads(value)
                self.stats["misses"] += 1
                return None
            else:
                value = self._memory_cache.get(key)
                if value is not None:
                    self.stats["hits"] += 1
                    return value
                self.stats["misses"] += 1
                return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            self.stats["errors"] += 1
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set value in cache with TTL (seconds). Uses RedisManager TTL strategy if ttl not provided."""
        if ttl is None:
            # Extract prefix from key format "zantara:{prefix}:{hash}"
            from backend.core.redis_manager import get_ttl

            parts = key.split(":")
            prefix = parts[1] if len(parts) >= 3 else "default"
            ttl = get_ttl(prefix)
        try:
            if self.redis_available and self.redis_client:
                await self.redis_client.setex(key, ttl, json.dumps(value, cls=DecimalEncoder))
                return True
            else:
                self._memory_cache.set(key, value, ttl)
                return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            self.stats["errors"] += 1
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            if self.redis_available and self.redis_client:
                await self.redis_client.delete(key)
                return True
            else:
                return self._memory_cache.delete(key)
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        try:
            if self.redis_available and self.redis_client:
                keys = await self.redis_client.keys(pattern)
                if keys:
                    return await self.redis_client.delete(*keys)
                return 0
            else:
                return self._memory_cache.clear_pattern(pattern)
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0

    def get_stats(self) -> dict:
        """Get cache statistics"""
        total = self.stats["hits"] + self.stats["misses"]
        hit_rate = (self.stats["hits"] / total * 100) if total > 0 else 0

        return {
            "backend": "redis" if self.redis_available else "memory",
            "connected": self.redis_available,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "errors": self.stats["errors"],
            "hit_rate": f"{hit_rate:.1f}%",
        }


# Global cache instance (singleton used by get_cache_service)
_cache_instance: CacheService | None = None


def get_cache_service() -> CacheService:
    """
    Factory function to get cache service instance.

    Uses singleton pattern internally but allows for dependency injection.
    For testing, you can create new instances: CacheService() for isolation.

    For FastAPI endpoints, use dependency injection:
        from fastapi import Depends
        from backend.app.dependencies import get_cache

        async def endpoint(cache: CacheService = Depends(get_cache)):
            value = cache.get("key")

    Returns:
        CacheService instance (singleton)
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheService()
    return _cache_instance


def cached(
    ttl: int = DEFAULT_CACHE_TTL, prefix: str = "default", cache_service: CacheService | None = None
) -> Any:
    """
    Decorator to cache function results

    Args:
        ttl: Time to live in seconds (default: 5 minutes)
        prefix: Cache key prefix
        cache_service: Optional CacheService instance (for dependency injection/testing)

    Example:
        @cached(ttl=600, prefix="agents")
        async def get_agents_status():
            return expensive_operation()
    """
    # Use provided cache service or get default
    cache_inst = cache_service if cache_service is not None else get_cache_service()

    def decorator(func: Callable) -> Any:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = cache_inst._generate_key(prefix, *args, **kwargs)

            # Try to get from cache
            cached_value = await cache_inst.get(cache_key)
            if cached_value is not None:
                # Sanitize cache_key for logging
                sanitized_key = f"{cache_key[:8]}..." if len(cache_key) > 8 else cache_key[:8]
                logger.debug(f"✅ Cache HIT: {sanitized_key}")
                return cached_value

            # Cache miss - execute function
            sanitized_key = f"{cache_key[:8]}..." if len(cache_key) > 8 else cache_key[:8]
            logger.debug(f"❌ Cache MISS: {sanitized_key}")
            result = await func(*args, **kwargs)

            # Store in cache
            await cache_inst.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


async def invalidate_cache(pattern: str = "zantara:*", cache_service: CacheService | None = None):
    """
    Invalidate cache entries matching pattern

    Args:
        pattern: Redis key pattern (default: all zantara keys)
        cache_service: Optional CacheService instance (for dependency injection/testing)

    Example:
        await invalidate_cache("zantara:agents:*")
    """
    cache_inst = cache_service if cache_service is not None else get_cache_service()
    count = await cache_inst.clear_pattern(pattern)
    logger.info(f"🗑️ Invalidated {count} cache entries matching '{pattern}'")
    return count


async def invalidate_namespace(namespace: str, cache_service: CacheService | None = None):
    """
    Invalidate all cache entries in a namespace.

    Convenience wrapper for invalidate_cache with namespace prefix.

    Args:
        namespace: Cache namespace (e.g., 'clients', 'practices', 'analytics')

    Example:
        # After a client INSERT/UPDATE/DELETE:
        await invalidate_namespace("clients")
    """
    return await invalidate_cache(f"zantara:{namespace}:*", cache_service=cache_service)


def cached_query(
    namespace: str,
    ttl: int = DEFAULT_CACHE_TTL,
    cache_service: CacheService | None = None,
) -> Any:
    """
    Decorator to cache database query results with namespace-based invalidation.

    Similar to @cached but uses explicit namespaces for targeted cache invalidation
    on INSERT/UPDATE/DELETE operations.

    Args:
        namespace: Cache namespace for grouped invalidation (e.g., 'clients', 'practices')
        ttl: Time to live in seconds (default: 5 minutes)
        cache_service: Optional CacheService instance (for testing)

    Example:
        @cached_query(namespace="clients", ttl=300)
        async def get_all_clients(db_pool, status=None):
            ...

        # After mutation:
        await invalidate_namespace("clients")
    """
    cache_inst = cache_service if cache_service is not None else get_cache_service()

    def decorator(func: Callable) -> Any:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = cache_inst._generate_key(namespace, *args, **kwargs)

            cached_value = await cache_inst.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache HIT [{namespace}]: {func.__name__}")
                return cached_value

            logger.debug(f"Cache MISS [{namespace}]: {func.__name__}")
            result = await func(*args, **kwargs)

            await cache_inst.set(cache_key, result, ttl)
            return result

        wrapper.cache_namespace = namespace
        wrapper.invalidate = lambda: invalidate_namespace(namespace, cache_service=cache_inst)
        return wrapper

    return decorator
