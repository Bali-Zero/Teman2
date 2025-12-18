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
from functools import wraps
from typing import Any

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
    ):
        """
        Initialize LRU cache.

        Args:
            max_size: Maximum number of items to store
            maxsize: Alias for max_size (for compatibility with tests)
            default_ttl: Default TTL in seconds
        """
        self.max_size = maxsize if maxsize is not None else max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[
            str, tuple[Any, float]
        ] = OrderedDict()  # key -> (value, expire_time)

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
        keys_to_delete = [k for k in self.cache.keys() if pattern.replace("*", "") in k]
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

    Usage with DI:
        from fastapi import Depends
        from core.cache import get_cache_service

        async def endpoint(cache: CacheService = Depends(get_cache_service)):
            value = cache.get("key")
    """

    def __init__(self):
        self.redis_available = False
        self.redis_client = None
        self.stats = {"hits": 0, "misses": 0, "errors": 0}

        # Instance-level in-memory cache (not module-level)
        # This prevents shared state between instances and test isolation issues
        self._memory_cache = LRUCache()

        # Try to connect to Redis (Fly.io provides REDIS_URL)
        from app.core.config import settings

        redis_url = settings.redis_url
        if redis_url:
            try:
                import redis

                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
                self.redis_available = True
                logger.info("✅ Redis cache connected")
            except Exception as e:
                logger.warning(f"⚠️ Redis not available, using memory cache: {e}")
        else:
            logger.info("ℹ️ No REDIS_URL, using in-memory cache")

    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Generate cache key from function arguments.

        Format: zantara:{prefix}:{hash}
        Hash is MD5 of JSON-serialized args/kwargs (first 12 chars).

        Example:
            >>> cache._generate_key("test", "arg1", key="value")
            'zantara:test:a1b2c3d4e5f6'
        """
        # Skip 'self' from args (first argument for instance methods)
        # This prevents "Object not JSON serializable" errors
        filtered_args = args[1:] if args and hasattr(args[0], "__dict__") else args

        # Create deterministic key from arguments
        key_data = json.dumps({"args": filtered_args, "kwargs": kwargs}, sort_keys=True)
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:CACHE_KEY_HASH_LENGTH]
        return f"zantara:{prefix}:{key_hash}"

    def get(self, key: str) -> Any | None:
        """Get value from cache"""
        try:
            if self.redis_available and self.redis_client:
                value = self.redis_client.get(key)
                if value:
                    self.stats["hits"] += 1
                    return json.loads(value)
                self.stats["misses"] += 1
                return None
            else:
                # In-memory fallback with LRU + TTL (instance-level)
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

    def set(self, key: str, value: Any, ttl: int = DEFAULT_CACHE_TTL) -> bool:
        """Set value in cache with TTL (seconds)"""
        try:
            if self.redis_available and self.redis_client:
                self.redis_client.setex(key, ttl, json.dumps(value))
                return True
            else:
                # In-memory fallback with LRU + TTL (instance-level)
                self._memory_cache.set(key, value, ttl)
                return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            self.stats["errors"] += 1
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            if self.redis_available and self.redis_client:
                self.redis_client.delete(key)
                return True
            else:
                return self._memory_cache.delete(key)
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        try:
            if self.redis_available and self.redis_client:
                keys = self.redis_client.keys(pattern)
                if keys:
                    return self.redis_client.delete(*keys)
                return 0
            else:
                # In-memory: clear keys matching pattern (instance-level)
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
        from app.dependencies import get_cache

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
):
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

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = cache_inst._generate_key(prefix, *args, **kwargs)

            # Try to get from cache
            cached_value = cache_inst.get(cache_key)
            if cached_value is not None:
                # Sanitize cache_key for logging (show only first 8 chars to avoid exposing sensitive data)
                sanitized_key = f"{cache_key[:8]}..." if len(cache_key) > 8 else cache_key[:8]
                logger.debug(f"✅ Cache HIT: {sanitized_key}")
                return cached_value

            # Cache miss - execute function
            # Sanitize cache_key for logging (show only first 8 chars to avoid exposing sensitive data)
            sanitized_key = f"{cache_key[:8]}..." if len(cache_key) > 8 else cache_key[:8]
            logger.debug(f"❌ Cache MISS: {sanitized_key}")
            result = await func(*args, **kwargs)

            # Store in cache
            cache_inst.set(cache_key, result, ttl)

            return result

        return wrapper

    return decorator


def invalidate_cache(pattern: str = "zantara:*", cache_service: CacheService | None = None):
    """
    Invalidate cache entries matching pattern

    Args:
        pattern: Redis key pattern (default: all zantara keys)
        cache_service: Optional CacheService instance (for dependency injection/testing)

    Example:
        invalidate_cache("zantara:agents:*")
    """
    cache_inst = cache_service if cache_service is not None else get_cache_service()
    count = cache_inst.clear_pattern(pattern)
    logger.info(f"🗑️ Invalidated {count} cache entries matching '{pattern}'")
    return count
