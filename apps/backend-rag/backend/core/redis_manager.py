"""
Redis Manager — Centralized Redis connection pool for Nuzantara backend.

Single source of truth for all Redis connections. Components import from here
instead of creating their own redis.from_url() connections.

Graceful degradation: if Redis is unavailable, all consumers fall back to
their existing in-memory alternatives.
"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# TTL configuration by key prefix (seconds)
TTL_CONFIG: dict[str, int] = {
    "hybrid_search": 3600,      # 1h — RAG responses
    "kg:entity": 21600,         # 6h — KG entities
    "kg:traverse": 21600,       # 6h — KG traversals
    "query_expand": 7200,       # 2h — query expansion
    "kbli_translate": 86400,    # 24h — KBLI translations (static)
    "kbli_inspect": 86400,      # 24h — KBLI inspections (static)
    "faq": 14400,               # 4h — FAQ cache
    "notebooklm": 14400,        # 4h — NotebookLM cache
    "session": 86400,           # 24h — conversation sessions
    "default": 1800,            # 30min — fallback
}


def get_ttl(prefix: str) -> int:
    """Get TTL for a cache key prefix."""
    for key, ttl in TTL_CONFIG.items():
        if prefix.startswith(key):
            return ttl
    return TTL_CONFIG["default"]


class RedisManager:
    """
    Singleton Redis connection manager.

    Provides both async and sync clients from shared connection pools.
    All backend components should use this instead of creating their own connections.
    """

    _instance: "RedisManager | None" = None

    def __init__(self) -> None:
        self._async_client: Any | None = None
        self._sync_client: Any | None = None
        self._available: bool = False
        self._redis_url: str | None = None
        self._components: dict[str, str] = {}
        self._stats: dict[str, int] = {"connections_created": 0}

    @classmethod
    def get_instance(cls) -> "RedisManager":
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing only)."""
        if cls._instance is not None:
            cls._instance._close_sync()
        cls._instance = None

    def initialize(self, redis_url: str | None = None) -> None:
        """
        Initialize Redis connections.

        Args:
            redis_url: Redis URL. If None, reads from settings.
        """
        if redis_url is None:
            from backend.app.core.config import settings
            redis_url = settings.redis_url

        self._redis_url = redis_url

        if not redis_url:
            logger.info("No REDIS_URL configured — Redis disabled, using in-memory fallbacks")
            self._available = False
            return

        # Initialize sync client (for RateLimiter middleware)
        try:
            import redis as sync_redis

            self._sync_client = sync_redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                max_connections=5,
            )
            self._sync_client.ping()
            self._stats["connections_created"] += 1
            logger.info("Redis sync client connected")
        except Exception as e:
            logger.warning(f"Redis sync client unavailable: {e}")
            self._sync_client = None

        # Initialize async client (for all async components)
        try:
            import redis.asyncio as aioredis

            self._async_client = aioredis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                max_connections=10,
            )
            self._stats["connections_created"] += 1
            logger.info("Redis async client connected")
        except Exception as e:
            logger.warning(f"Redis async client unavailable: {e}")
            self._async_client = None

        self._available = self._sync_client is not None or self._async_client is not None

        if self._available:
            logger.info("RedisManager initialized — Redis available")
        else:
            logger.warning("RedisManager initialized — Redis unavailable, using fallbacks")

    @property
    def available(self) -> bool:
        """Whether Redis is available."""
        return self._available

    def get_async_client(self) -> Any | None:
        """Get the shared async Redis client. Returns None if unavailable."""
        return self._async_client

    def get_sync_client(self) -> Any | None:
        """Get the shared sync Redis client. Returns None if unavailable."""
        return self._sync_client

    def register_component(self, name: str, status: str) -> None:
        """Register a component's Redis status."""
        self._components[name] = status
        logger.debug(f"Redis component registered: {name}={status}")

    async def health_check(self) -> dict[str, Any]:
        """
        Perform Redis health check.

        Returns:
            Dict with connection status, latency, key count, and component registry.
        """
        result: dict[str, Any] = {
            "connected": False,
            "latency_ms": -1,
            "keys": 0,
            "memory_used": "0B",
            "components": dict(self._components),
        }

        if not self._available or self._async_client is None:
            return result

        try:
            start = time.monotonic()
            await self._async_client.ping()
            latency = (time.monotonic() - start) * 1000

            result["connected"] = True
            result["latency_ms"] = round(latency, 1)

            # Key count
            db_size = await self._async_client.dbsize()
            result["keys"] = db_size

            # Memory info
            info = await self._async_client.info("memory")
            result["memory_used"] = info.get("used_memory_human", "unknown")

        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            result["error"] = str(e)

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get Redis manager stats."""
        return {
            "available": self._available,
            "url_configured": self._redis_url is not None,
            "async_client": self._async_client is not None,
            "sync_client": self._sync_client is not None,
            "components": dict(self._components),
            "connections_created": self._stats["connections_created"],
        }

    def _close_sync(self) -> None:
        """Close sync client (for cleanup)."""
        if self._sync_client is not None:
            try:
                self._sync_client.close()
            except Exception:
                pass

    async def close(self) -> None:
        """Close all connections."""
        self._close_sync()
        if self._async_client is not None:
            try:
                await self._async_client.close()
            except Exception:
                pass
        logger.info("RedisManager connections closed")
