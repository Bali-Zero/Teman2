"""
Caching Service for Article Composer

Best Practices 2026:
- Redis-based caching
- Cache invalidation strategies
- TTL management
"""

import hashlib
import json
import logging
import os
from typing import Any

try:
    import redis.asyncio as redis
except ImportError:
    redis = None

logger = logging.getLogger(__name__)

# Cache TTLs (in seconds)
CACHE_TTL_COMPOSE = 3600  # 1 hour
CACHE_TTL_STATUS = 300  # 5 minutes


class CacheService:
    """Redis-based cache service for Article Composer"""

    def __init__(self) -> None:
        self.redis_client: redis.Redis | None = None
        self.enabled = False

    async def initialize(self) -> None:
        """Initialize Redis connection"""
        if redis is None:
            logger.warning("Redis not available - caching disabled")
            return

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            self.redis_client = await redis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self.redis_client.ping()
            self.enabled = True
            logger.info("Redis cache initialized successfully")
        except Exception as e:
            logger.warning(f"Redis connection failed - caching disabled: {e}")
            self.enabled = False

    async def close(self) -> None:
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()

    def _generate_cache_key(self, prefix: str, *args: Any) -> str:
        """Generate cache key from arguments"""
        key_data = json.dumps(args, sort_keys=True, default=str)
        key_hash = hashlib.md5(key_data.encode()).hexdigest()[:12]
        return f"article_composer:{prefix}:{key_hash}"

    async def get(self, key: str) -> Any | None:
        """Get value from cache"""
        if not self.enabled or not self.redis_client:
            return None

        try:
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = CACHE_TTL_COMPOSE) -> None:
        """Set value in cache"""
        if not self.enabled or not self.redis_client:
            return

        try:
            await self.redis_client.setex(
                key,
                ttl,
                json.dumps(value, default=str),
            )
        except Exception as e:
            logger.warning(f"Cache set error: {e}")

    async def delete(self, key: str) -> None:
        """Delete key from cache"""
        if not self.enabled or not self.redis_client:
            return

        try:
            await self.redis_client.delete(key)
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")

    async def get_compose_cache(self, title: str, content: str, category: str) -> dict | None:
        """Get cached compose result"""
        cache_key = self._generate_cache_key("compose", title, content[:1000], category)
        return await self.get(cache_key)

    async def set_compose_cache(
        self, title: str, content: str, category: str, result: dict,
    ) -> None:
        """Cache compose result"""
        cache_key = self._generate_cache_key("compose", title, content[:1000], category)
        await self.set(cache_key, result, ttl=CACHE_TTL_COMPOSE)

    async def invalidate_compose_cache(self, title: str | None = None) -> None:
        """Invalidate compose cache (all or by title)"""
        if not self.enabled or not self.redis_client:
            return

        try:
            if title:
                # Invalidate specific title
                pattern = (
                    f"article_composer:compose:*{hashlib.md5(title.encode()).hexdigest()[:12]}*"
                )
            else:
                # Invalidate all compose cache
                pattern = "article_composer:compose:*"

            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                await self.redis_client.delete(*keys)
                logger.info(f"Invalidated {len(keys)} cache entries")
        except Exception as e:
            logger.warning(f"Cache invalidation error: {e}")


# Global cache service instance
cache_service = CacheService()
