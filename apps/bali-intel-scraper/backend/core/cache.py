"""
Caching layer with Redis backend.

Provides caching for:
- Scraped content
- AI processing results
- API responses
- Database query results
"""

import asyncio
import hashlib
import json
import pickle
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Generic, Optional, TypeVar, List
from functools import wraps

import redis.asyncio as redis
from redis.asyncio import Redis

from config.settings import settings
from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="cache")

T = TypeVar("T")


class CacheStrategy(Enum):
    """Cache expiration strategies."""

    TTL_SHORT = 300  # 5 minutes
    TTL_MEDIUM = 3600  # 1 hour
    TTL_LONG = 86400  # 1 day
    TTL_PERMANENT = 0  # No expiration


@dataclass
class CacheConfig:
    """Cache configuration."""

    default_ttl: int = 3600
    max_key_length: int = 250
    prefix: str = "bali"
    serializer: str = "json"  # json or pickle


class CacheKeyBuilder:
    """Builds cache keys from various inputs."""

    @staticmethod
    def build(*parts: Any, prefix: str = "bali") -> str:
        """Build a cache key from parts."""
        key_parts = [prefix]

        for part in parts:
            if isinstance(part, str):
                key_parts.append(part)
            elif isinstance(part, (int, float)):
                key_parts.append(str(part))
            elif isinstance(part, dict):
                # Sort dict items for consistent keys
                key_parts.append(
                    hashlib.md5(json.dumps(part, sort_keys=True).encode()).hexdigest()[
                        :16
                    ]
                )
            else:
                key_parts.append(str(part))

        key = ":".join(key_parts)

        # Truncate if too long
        if len(key) > 250:
            key = key[:200] + ":" + hashlib.md5(key.encode()).hexdigest()[:16]

        return key

    @staticmethod
    def for_url(url: str, suffix: Optional[str] = None) -> str:
        """Build cache key for URL."""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        parts = ["url", url_hash]
        if suffix:
            parts.append(suffix)
        return CacheKeyBuilder.build(*parts)

    @staticmethod
    def for_function(func_name: str, *args, **kwargs) -> str:
        """Build cache key for function call."""
        key_data = {"args": args, "kwargs": kwargs}
        sig_hash = hashlib.md5(
            json.dumps(key_data, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
        return CacheKeyBuilder.build("func", func_name, sig_hash)


class CacheManager(Generic[T]):
    """Manages caching operations."""

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self._redis: Optional[Redis] = None
        self._lock = asyncio.Lock()

    @property
    def redis(self) -> Optional[Redis]:
        """Access to raw Redis client for advanced operations."""
        return self._redis

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        if self._redis is not None:
            return

        async with self._lock:
            if self._redis is not None:
                return

            try:
                self._redis = redis.from_url(
                    settings.redis.url,
                    socket_timeout=settings.redis.socket_timeout,
                    socket_connect_timeout=settings.redis.socket_connect_timeout,
                    decode_responses=False,  # We handle encoding ourselves
                )

                # Test connection
                await self._redis.ping()

                logger.info(
                    "Cache manager initialized",
                    action=LogAction.CONNECT,
                    metadata={"host": settings.redis.host},
                )

            except Exception as e:
                logger.error(
                    "Failed to initialize cache",
                    action=LogAction.CONNECT,
                    metadata={"error": str(e)},
                )
                raise

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis is None:
            return

        try:
            await self._redis.close()
            self._redis = None

            logger.info("Cache manager closed", action=LogAction.DISCONNECT)

        except Exception as e:
            logger.error(
                "Error closing cache",
                action=LogAction.DISCONNECT,
                metadata={"error": str(e)},
            )

    def _serialize(self, value: Any) -> bytes:
        """Serialize value to bytes."""
        if self.config.serializer == "json":
            return json.dumps(value, default=str).encode()
        else:
            return pickle.dumps(value)

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to value."""
        if self.config.serializer == "json":
            return json.loads(data.decode())
        else:
            return pickle.loads(data)

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if self._redis is None:
            await self.initialize()

        try:
            data = await self._redis.get(key)
            if data is None:
                return None

            return self._deserialize(data)

        except Exception as e:
            logger.error(
                f"Cache get failed for key {key}",
                action=LogAction.ERROR,
                metadata={"error": str(e)},
            )
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        strategy: Optional[CacheStrategy] = None,
    ) -> bool:
        """Set value in cache."""
        if self._redis is None:
            await self.initialize()

        # Determine TTL
        if strategy is not None:
            ttl = strategy.value if strategy != CacheStrategy.TTL_PERMANENT else None
        elif ttl is None:
            ttl = self.config.default_ttl

        try:
            data = self._serialize(value)

            if ttl:
                await self._redis.setex(key, ttl, data)
            else:
                await self._redis.set(key, data)

            return True

        except Exception as e:
            logger.error(
                f"Cache set failed for key {key}",
                action=LogAction.ERROR,
                metadata={"error": str(e)},
            )
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if self._redis is None:
            return False

        try:
            result = await self._redis.delete(key)
            return result > 0
        except Exception as e:
            logger.error(
                f"Cache delete failed for key {key}",
                action=LogAction.ERROR,
                metadata={"error": str(e)},
            )
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if self._redis is None:
            return False

        try:
            return await self._redis.exists(key) > 0
        except Exception as e:
            logger.error(
                f"Cache exists check failed for key {key}",
                action=LogAction.ERROR,
                metadata={"error": str(e)},
            )
            return False

    async def ttl(self, key: str) -> int:
        """Get remaining TTL for key."""
        if self._redis is None:
            return -2

        try:
            return await self._redis.ttl(key)
        except Exception as e:
            logger.error(
                f"Cache TTL check failed for key {key}",
                action=LogAction.ERROR,
                metadata={"error": str(e)},
            )
            return -2

    async def get_or_set(
        self,
        key: str,
        factory: callable,
        ttl: Optional[int] = None,
        strategy: Optional[CacheStrategy] = None,
    ) -> Any:
        """Get value from cache or set it using factory."""
        value = await self.get(key)

        if value is None:
            value = await factory()
            await self.set(key, value, ttl, strategy)

        return value

    async def increment(self, key: str, amount: int = 1) -> int:
        """Atomically increment a counter."""
        if self._redis is None:
            await self.initialize()

        try:
            return await self._redis.incrby(key, amount)
        except Exception as e:
            logger.error(
                f"Cache increment failed for key {key}",
                action=LogAction.ERROR,
                metadata={"error": str(e)},
            )
            raise

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on existing key."""
        if self._redis is None:
            return False

        try:
            return await self._redis.expire(key, ttl)
        except Exception as e:
            logger.error(
                f"Cache expire failed for key {key}",
                action=LogAction.ERROR,
                metadata={"error": str(e)},
            )
            return False

    async def keys(self, pattern: str) -> List[str]:
        """Get keys matching pattern."""
        if self._redis is None:
            return []

        try:
            keys = await self._redis.keys(pattern)
            return [k.decode() if isinstance(k, bytes) else k for k in keys]
        except Exception as e:
            logger.error(
                f"Cache keys failed for pattern {pattern}",
                action=LogAction.ERROR,
                metadata={"error": str(e)},
            )
            return []

    async def clear_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        keys = await self.keys(pattern)

        if not keys:
            return 0

        count = 0
        for key in keys:
            if await self.delete(key):
                count += 1

        logger.info(
            f"Cleared {count} keys matching pattern {pattern}", action=LogAction.DELETE
        )

        return count

    async def health_check(self) -> Dict[str, Any]:
        """Check cache health."""
        try:
            if self._redis is None:
                return {"status": "not_initialized"}

            await self._redis.ping()
            info = await self._redis.info()

            return {
                "status": "healthy",
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "uptime_days": info.get("uptime_in_days", 0),
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}


# Global cache instance
cache = CacheManager()


async def init_cache() -> None:
    """Initialize global cache."""
    await cache.initialize()


async def close_cache() -> None:
    """Close global cache."""
    await cache.close()


def cached(
    ttl: Optional[int] = None,
    strategy: Optional[CacheStrategy] = None,
    key_builder: Optional[callable] = None,
    skip_args: Optional[List[int]] = None,
):
    """Decorator for caching function results."""

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Skip 'self' or 'cls' if present
                start_idx = 1 if skip_args else 0
                cache_key = CacheKeyBuilder.for_function(
                    func.__name__, *args[start_idx:], **kwargs
                )

            # Try to get from cache
            result = await cache.get(cache_key)
            if result is not None:
                logger.debug(
                    f"Cache hit for {func.__name__}", metadata={"key": cache_key}
                )
                return result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl, strategy)

            logger.debug(f"Cache set for {func.__name__}", metadata={"key": cache_key})

            return result

        # Expose cache clear method
        async def clear_cache(*args, **kwargs):
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                start_idx = 1 if skip_args else 0
                cache_key = CacheKeyBuilder.for_function(
                    func.__name__, *args[start_idx:], **kwargs
                )
            await cache.delete(cache_key)

        async_wrapper.clear_cache = clear_cache

        return async_wrapper

    return decorator


__all__ = [
    "CacheManager",
    "CacheStrategy",
    "CacheKeyBuilder",
    "cache",
    "init_cache",
    "close_cache",
    "cached",
]
