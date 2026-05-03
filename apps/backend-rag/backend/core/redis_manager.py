"""
Redis Manager — Centralized Redis connection pool for Nuzantara backend.

Single source of truth for all Redis connections. Components import from here
instead of creating their own redis.from_url() connections.

Graceful degradation: if Redis is unavailable, all consumers fall back to
their existing in-memory alternatives.

Auto-reconnect: if Redis goes down, a background task retries with exponential
backoff (30s → 60s → 120s → 300s max). Rate limiting becomes distributed again
automatically when Redis comes back.
"""

import asyncio
import contextlib
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# TTL configuration by key prefix (seconds)
TTL_CONFIG: dict[str, int] = {
    "hybrid_search": 3600,  # 1h — RAG responses
    "kg:entity": 21600,  # 6h — KG entities
    "kg:traverse": 21600,  # 6h — KG traversals
    "query_expand": 7200,  # 2h — query expansion
    "kbli_translate": 86400,  # 24h — KBLI translations (static)
    "kbli_inspect": 86400,  # 24h — KBLI inspections (static)
    "faq": 14400,  # 4h — FAQ cache
    "notebooklm": 14400,  # 4h — NotebookLM cache
    "session": 86400,  # 24h — conversation sessions
    "default": 1800,  # 30min — fallback
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
        self._stats: dict[str, int] = {"connections_created": 0, "reconnect_attempts": 0}
        self._reconnect_task: asyncio.Task | None = None

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
            # Start background reconnect loop
            self._start_reconnect_loop()

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

        Also ensures any deferred reconnect loop (started from a sync context)
        is activated now that we are inside an async context.

        Returns:
            Dict with connection status, latency, key count, and component registry.
        """
        self._ensure_reconnect_loop()
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

    def _start_reconnect_loop(self) -> None:
        """
        Start background reconnect loop if not already running.

        If called from a synchronous context with no running event loop (e.g.,
        tests or CLI), the task cannot be created immediately.  In that case
        ``_reconnect_pending`` is set to True so that the first async caller
        (e.g., ``health_check`` or ``close``) can call
        ``_ensure_reconnect_loop()`` to start it lazily.
        """
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
            self._reconnect_task = loop.create_task(self._reconnect_loop())
        except RuntimeError:
            # No running event loop — mark as pending so an async caller can
            # start it later via _ensure_reconnect_loop().
            self._reconnect_pending = True
            logger.debug("Redis reconnect loop deferred — no running event loop at initialize()")

    def _ensure_reconnect_loop(self) -> None:
        """
        Start the reconnect loop now if it was deferred during initialize().

        Must be called from an async context (event loop is running).
        """
        if not getattr(self, "_reconnect_pending", False):
            return
        if self._reconnect_task is not None and not self._reconnect_task.done():
            return
        if self._available:
            self._reconnect_pending = False
            return
        try:
            loop = asyncio.get_running_loop()
            self._reconnect_task = loop.create_task(self._reconnect_loop())
            self._reconnect_pending = False
            logger.info("Redis reconnect loop started (deferred from sync context)")
        except RuntimeError:
            pass  # Still no loop — will retry next time

    async def _reconnect_loop(self) -> None:
        """
        Background task: retry Redis connection with exponential backoff.
        30s → 60s → 120s → 300s (max). Stops when connection restored.

        Restores BOTH async and sync clients so that all consumers
        (including the rate-limiter middleware that requires a sync client)
        become fully operational again after a Redis outage.
        """
        delays = [30, 60, 120, 300]
        idx = 0
        while not self._available and self._redis_url:
            delay = delays[min(idx, len(delays) - 1)]
            self._stats["reconnect_attempts"] += 1
            logger.info(f"Redis reconnect attempt #{self._stats['reconnect_attempts']} in {delay}s")
            await asyncio.sleep(delay)
            idx += 1

            if self._available:
                break  # Already restored by another path

            try:
                import redis as sync_redis
                import redis.asyncio as aioredis

                # Restore async client first (ping proves connectivity)
                async_client = aioredis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    max_connections=10,
                )
                await async_client.ping()
                self._async_client = async_client
                self._stats["connections_created"] += 1

                # Restore sync client so rate-limiter becomes distributed again
                try:
                    sync_client = sync_redis.from_url(
                        self._redis_url,
                        decode_responses=True,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                        retry_on_timeout=True,
                        max_connections=5,
                    )
                    sync_client.ping()
                    self._sync_client = sync_client
                    self._stats["connections_created"] += 1
                    logger.info("Redis sync client restored — rate limiting is now distributed")
                except Exception as sync_err:
                    logger.warning(f"Redis sync client restore failed (async-only mode): {sync_err}")
                    self._sync_client = None

                self._available = True
                logger.info("Redis reconnected successfully — distributed rate limiting restored")
                return
            except Exception as e:
                logger.warning(f"Redis reconnect failed: {e}")

        logger.debug("Redis reconnect loop exited")

    # ── Event-Driven Cache Invalidation ────────────────────────────
    #
    # Redis maxmemory-policy recommendation:
    #   Configure Redis with `maxmemory 256mb` and `maxmemory-policy allkeys-lru`
    #   to auto-evict least-recently-used keys when memory is exhausted.
    #   This prevents OOM kills on Fly.io's 2GB RAM constraint.
    #   Set via: redis-cli CONFIG SET maxmemory 256mb
    #            redis-cli CONFIG SET maxmemory-policy allkeys-lru

    async def invalidate_by_pattern(self, pattern: str) -> int:
        """Delete all Redis keys matching a glob pattern.

        Uses SCAN (not KEYS) to avoid blocking Redis on large datasets.

        Args:
            pattern: Redis glob pattern (e.g., 'zantara:hybrid_search:*')

        Returns:
            Number of keys deleted
        """
        if not self._available or self._async_client is None:
            logger.debug(f"Redis unavailable — skipping invalidation for pattern: {pattern}")
            return 0

        try:
            deleted = 0
            cursor = 0
            while True:
                cursor, keys = await self._async_client.scan(
                    cursor=cursor, match=pattern, count=100,
                )
                if keys:
                    deleted += await self._async_client.delete(*keys)
                if cursor == 0:
                    break
            if deleted > 0:
                logger.info(f"Cache invalidated: {deleted} keys matching '{pattern}'")
            return deleted
        except Exception as e:
            logger.error(f"Cache invalidation failed for pattern '{pattern}': {e}")
            return 0

    async def invalidate_collection_cache(self, collection_name: str) -> int:
        """Invalidate all search result caches for a specific collection.

        Called when documents are upserted or deleted in a collection to ensure
        stale search results are not served.

        Args:
            collection_name: Qdrant collection name (e.g., 'visa_oracle')

        Returns:
            Number of keys deleted
        """
        # Hybrid search results are keyed by collection name
        pattern = f"zantara:hybrid_search:{collection_name}:*"
        count = await self.invalidate_by_pattern(pattern)
        # Also invalidate any general search cache that may reference this collection
        count += await self.invalidate_by_pattern(f"zantara:search:{collection_name}:*")
        return count

    async def invalidate_session_cache(self, session_id: str | None = None) -> int:
        """Invalidate session cache on user logout.

        Args:
            session_id: Specific session to invalidate, or None for all sessions

        Returns:
            Number of keys deleted
        """
        if session_id:
            pattern = f"zantara:session:{session_id}:*"
        else:
            pattern = "zantara:session:*"
        return await self.invalidate_by_pattern(pattern)

    async def invalidate_faq_cache(self) -> int:
        """Invalidate FAQ cache when FAQ content is updated.

        Returns:
            Number of keys deleted
        """
        return await self.invalidate_by_pattern("zantara:faq:*")

    async def get_redis_memory_info(self) -> dict[str, Any]:
        """Get Redis memory health information.

        Returns:
            Dict with used_memory, maxmemory, evicted_keys, and policy.
        """
        result: dict[str, Any] = {
            "used_memory": 0,
            "used_memory_human": "0B",
            "maxmemory": 0,
            "maxmemory_human": "0B",
            "maxmemory_policy": "unknown",
            "evicted_keys": 0,
            "connected_clients": 0,
        }

        if not self._available or self._async_client is None:
            result["error"] = "Redis unavailable"
            return result

        try:
            # Memory stats
            mem_info = await self._async_client.info("memory")
            result["used_memory"] = mem_info.get("used_memory", 0)
            result["used_memory_human"] = mem_info.get("used_memory_human", "0B")
            result["maxmemory"] = mem_info.get("maxmemory", 0)
            result["maxmemory_human"] = mem_info.get("maxmemory_human", "0B")
            result["maxmemory_policy"] = mem_info.get("maxmemory_policy", "unknown")

            # Eviction stats
            stats_info = await self._async_client.info("stats")
            result["evicted_keys"] = stats_info.get("evicted_keys", 0)

            # Client stats
            client_info = await self._async_client.info("clients")
            result["connected_clients"] = client_info.get("connected_clients", 0)

            # Update Prometheus gauges
            try:
                from backend.app.metrics import metrics_collector
                metrics_collector.set_redis_memory_usage(result["used_memory"])
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Failed to get Redis memory info: {e}")
            result["error"] = str(e)

        return result

    def _close_sync(self) -> None:
        """Close sync client (for cleanup)."""
        if self._sync_client is not None:
            with contextlib.suppress(Exception):
                self._sync_client.close()

    async def close(self) -> None:
        """Close all connections."""
        if self._reconnect_task is not None and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._reconnect_task
        self._close_sync()
        if self._async_client is not None:
            with contextlib.suppress(Exception):
                await self._async_client.close()
        logger.info("RedisManager connections closed")
