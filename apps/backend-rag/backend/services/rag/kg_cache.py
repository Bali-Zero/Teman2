"""
Knowledge Graph Query Cache

Redis-backed caching layer for KG operations:
- Entity resolution results (fuzzy match is expensive without trigram index)
- BFS traversal results (identical queries traverse the same subgraph)
- KG stats (node/edge counts change rarely)

Falls back to in-memory LRU when Redis is unavailable.

Invalidation model (HIGH-13):
Historically a reader detected staleness by comparing its cached ``_kg_version``
with the current counter *on read*. That meant between a successful write and
the first read on a peer cell, any reader in the middle got a stale hit.
We now publish an async ``zantara:kg:invalidate`` event on every version bump.
Peers subscribe at startup and locally wipe the affected keys the moment a
write lands. If Redis pub/sub is unavailable the lazy on-read check still
catches stale entries (Legge 4 — graceful degradation), so readers never
block.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import threading
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# KG Version Counter
# ---------------------------------------------------------------------------
# Monotonically increasing counter incremented on every KG mutation
# (node/edge add). Used to invalidate stale cache entries: cached results
# store the version at write time; on read, a version mismatch triggers
# a cache miss.
# ---------------------------------------------------------------------------
_kg_version: int = 0
_kg_version_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Pub/sub invalidation (HIGH-13)
# ---------------------------------------------------------------------------
KG_INVALIDATE_CHANNEL = "zantara:kg:invalidate"
_DEFAULT_INVALIDATE_PATTERNS: tuple[str, ...] = (
    "zantara:kg:entity:*",
    "zantara:kg:traverse:*",
    "zantara:kg:subgraph:*",
    "zantara:kg:stats",
)
# Debounce window in seconds. Multiple writes within this window coalesce into
# a single publish. Keeps high-throughput ingestion from hammering pub/sub.
_PUBLISH_DEBOUNCE_SEC = 0.05

_publish_state: dict[str, Any] = {
    "pending": False,           # there is a scheduled publish not yet fired
    "last_version": 0,          # last published version (stops duplicate publishes)
    "task": None,               # asyncio.Task for the in-flight debounced publish
}
_publish_state_lock = threading.Lock()


def get_kg_version() -> int:
    """Return the current KG version counter."""
    return _kg_version


def increment_kg_version() -> int:
    """
    Increment the KG version counter (thread-safe) and schedule a pub/sub
    invalidation broadcast. Listeners (peer cells) will wipe their local
    KG cache on receipt.

    Pub/sub failures are swallowed — readers still fall back to on-read
    version checks. Call-site contract: safe to call from any thread; if no
    event loop is running, only the in-process counter is updated.

    Returns:
        The new version number.
    """
    global _kg_version
    with _kg_version_lock:
        _kg_version += 1
        new_version = _kg_version
    logger.debug("KG version incremented to %d", new_version)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return new_version

    _schedule_invalidate_publish(loop, new_version)
    return new_version


def _schedule_invalidate_publish(loop: asyncio.AbstractEventLoop, version: int) -> None:
    """Debounced publisher scheduler.

    If a publish is already pending, do nothing — the scheduled task will pick
    up the freshest version when it fires. Otherwise spawn a debounced task.
    """
    with _publish_state_lock:
        if _publish_state["pending"]:
            return
        _publish_state["pending"] = True

    async def _fire() -> None:
        try:
            await asyncio.sleep(_PUBLISH_DEBOUNCE_SEC)
        finally:
            with _publish_state_lock:
                _publish_state["pending"] = False
        await _publish_invalidate(version)

    task = loop.create_task(_fire())
    with _publish_state_lock:
        _publish_state["task"] = task


async def _publish_invalidate(version: int) -> None:
    """Publish a single invalidation notice on ``KG_INVALIDATE_CHANNEL``.

    Payload shape:
        {"version": <int>, "keys": ["zantara:kg:entity:*", ...]}

    Redis down or unconfigured → log at debug level and return (Legge 4).
    """
    with _publish_state_lock:
        if version <= _publish_state["last_version"]:
            return
        _publish_state["last_version"] = version

    redis_client = _get_async_redis()
    if redis_client is None:
        return

    try:
        payload = json.dumps({
            "version": version,
            "keys": list(_DEFAULT_INVALIDATE_PATTERNS),
        })
        subscribers = await redis_client.publish(KG_INVALIDATE_CHANNEL, payload)
        logger.debug(
            "Published KG invalidate v=%d → %s subscribers", version, subscribers,
        )
    except Exception as exc:
        logger.warning("KG invalidate publish failed (v=%d): %s", version, exc)


def _get_async_redis() -> Any:
    """Resolve the shared async Redis client via RedisManager (or None)."""
    try:
        from backend.core.redis_manager import RedisManager

        return RedisManager.get_instance().get_async_client()
    except Exception:
        return None


# TTL constants (seconds)
TTL_ENTITY_RESOLUTION = 600  # 10 min — entities don't change often
TTL_TRAVERSAL = 300  # 5 min — graph structure is stable
TTL_STATS = 120  # 2 min — aggregate counts
TTL_SUBGRAPH = 300  # 5 min — domain subgraph results

# Prometheus metrics
try:
    from prometheus_client import Counter

    kg_cache_ops = Counter(
        "kg_cache_operations_total",
        "KG cache operations",
        ["operation", "result"],  # get/set, hit/miss/error
    )
except ImportError:
    kg_cache_ops = None


def _inc_metric(operation: str, result: str) -> None:
    if kg_cache_ops is not None:
        kg_cache_ops.labels(operation=operation, result=result).inc()


class KGCache:
    """
    Thin cache wrapper around CacheService for KG-specific operations.

    Uses the existing CacheService singleton (Redis or in-memory fallback).
    All keys are namespaced under 'kg:' for targeted invalidation.
    """

    def __init__(self) -> None:
        self._cache = None
        self._initialized = False

    def _get_cache(self) -> Any:
        """Lazy init to avoid import-time side effects."""
        if not self._initialized:
            try:
                from backend.core.cache import get_cache_service

                self._cache = get_cache_service()
            except Exception as e:
                logger.warning(f"KG cache init failed, caching disabled: {e}")
                self._cache = None
            self._initialized = True
        return self._cache

    @staticmethod
    def _hash_key(*parts: str) -> str:
        """Create a short deterministic cache key."""
        raw = "|".join(str(p) for p in parts)
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Entity Resolution Cache
    # ------------------------------------------------------------------

    async def get_resolved_entity(self, entity_str: str) -> dict | None:
        """Get cached entity resolution result."""
        cache = self._get_cache()
        if cache is None:
            return None
        key = f"zantara:kg:entity:{self._hash_key(entity_str.lower())}"
        result = await cache.get(key)
        if result is not None:
            _inc_metric("get", "hit")
            return result
        _inc_metric("get", "miss")
        return None

    async def set_resolved_entity(self, entity_str: str, resolution: dict) -> None:
        """Cache entity resolution result."""
        cache = self._get_cache()
        if cache is None:
            return
        key = f"zantara:kg:entity:{self._hash_key(entity_str.lower())}"
        await cache.set(key, resolution, TTL_ENTITY_RESOLUTION)
        _inc_metric("set", "ok")

    # ------------------------------------------------------------------
    # Traversal Cache
    # ------------------------------------------------------------------

    async def get_traversal(self, entity_ids: list[str], max_depth: int) -> list[list[dict]] | None:
        """Get cached BFS traversal result."""
        cache = self._get_cache()
        if cache is None:
            return None
        sorted_ids = sorted(entity_ids)
        key = f"zantara:kg:traverse:{self._hash_key(*sorted_ids, str(max_depth))}"
        result = await cache.get(key)
        if result is not None:
            _inc_metric("get", "hit")
            return result
        _inc_metric("get", "miss")
        return None

    async def set_traversal(
        self, entity_ids: list[str], max_depth: int, chains: list[list[dict]],
    ) -> None:
        """Cache BFS traversal result."""
        cache = self._get_cache()
        if cache is None:
            return
        sorted_ids = sorted(entity_ids)
        key = f"zantara:kg:traverse:{self._hash_key(*sorted_ids, str(max_depth))}"
        # Serialize datetime objects to string
        serializable = _make_serializable(chains)
        await cache.set(key, serializable, TTL_TRAVERSAL)
        _inc_metric("set", "ok")

    # ------------------------------------------------------------------
    # Stats Cache
    # ------------------------------------------------------------------

    async def get_stats(self) -> dict | None:
        """Get cached KG stats."""
        cache = self._get_cache()
        if cache is None:
            return None
        result = await cache.get("zantara:kg:stats")
        if result is not None:
            _inc_metric("get", "hit")
        else:
            _inc_metric("get", "miss")
        return result

    async def set_stats(self, stats: dict) -> None:
        """Cache KG stats."""
        cache = self._get_cache()
        if cache is None:
            return
        await cache.set("zantara:kg:stats", stats, TTL_STATS)
        _inc_metric("set", "ok")

    # ------------------------------------------------------------------
    # Subgraph Result Cache
    # ------------------------------------------------------------------

    async def get_subgraph_result(self, domain: str, query: str) -> dict | None:
        """
        Get cached domain subgraph result.

        Returns None (cache miss) if:
        - Cache is unavailable
        - No cached entry exists
        - Cached entry was written at a different KG version
        """
        cache = self._get_cache()
        if cache is None:
            return None
        key = f"zantara:kg:subgraph:{domain}:{self._hash_key(query.lower())}"
        wrapper = await cache.get(key)
        if wrapper is None:
            _inc_metric("get", "miss")
            return None

        # Version check: if the KG was mutated since this entry was cached,
        # treat as a miss so a fresh subgraph query is executed.
        if isinstance(wrapper, dict) and "_kg_version" in wrapper:
            cached_version = wrapper.get("_kg_version", -1)
            current_version = get_kg_version()
            if cached_version != current_version:
                logger.info(
                    "KG cache version mismatch for %s (cached=%d, current=%d) — miss",
                    domain,
                    cached_version,
                    current_version,
                )
                _inc_metric("get", "version_miss")
                return None
            _inc_metric("get", "hit")
            return wrapper.get("_data")

        # Legacy entries without version wrapper — treat as hit
        _inc_metric("get", "hit")
        return wrapper

    async def set_subgraph_result(self, domain: str, query: str, result: dict) -> None:
        """Cache domain subgraph result with current KG version."""
        cache = self._get_cache()
        if cache is None:
            return
        key = f"zantara:kg:subgraph:{domain}:{self._hash_key(query.lower())}"
        serializable = _make_serializable(result)
        wrapper = {"_kg_version": get_kg_version(), "_data": serializable}
        await cache.set(key, wrapper, TTL_SUBGRAPH)
        _inc_metric("set", "ok")

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    async def invalidate_all(self) -> int:
        """Invalidate all KG cache entries (e.g., after ingestion)."""
        cache = self._get_cache()
        if cache is None:
            return 0
        count = await cache.clear_pattern("zantara:kg:*")
        logger.info(f"KG cache invalidated: {count} entries cleared")
        return count


def _make_serializable(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable types."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serializable(item) for item in obj]
    if isinstance(obj, set):
        return list(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


# Module-level singleton
_kg_cache: KGCache | None = None


def get_kg_cache() -> KGCache:
    """Get the KG cache singleton."""
    global _kg_cache
    if _kg_cache is None:
        _kg_cache = KGCache()
    return _kg_cache


# ---------------------------------------------------------------------------
# Invalidation listener (HIGH-13 reader side)
# ---------------------------------------------------------------------------


class KGCacheInvalidationListener:
    """Subscribe to ``zantara:kg:invalidate`` and clear local KG cache on events.

    Started once at app startup via :func:`start_invalidation_listener`. Runs a
    single background task that consumes the pub/sub stream; each message
    contains the patterns to clear, so if the publisher ever adds a new
    namespace (e.g. ``zantara:kg:community:*``) no reader code change is
    required.

    Graceful degradation: if Redis pub/sub is unavailable or the subscriber
    connection drops, the listener logs a warning and exits. Readers keep
    working via the existing on-read version check in
    :meth:`KGCache.get_subgraph_result`.
    """

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="kg-cache-invalidate-listener")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        redis_client = _get_async_redis()
        if redis_client is None:
            logger.info("KG invalidate listener: Redis unavailable — lazy mode only")
            return

        pubsub = None
        try:
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(KG_INVALIDATE_CHANNEL)
            logger.info("KG invalidate listener subscribed to %s", KG_INVALIDATE_CHANNEL)

            while not self._stop_event.is_set():
                try:
                    msg = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=1.0,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.warning("KG invalidate listener get_message failed: %s", exc)
                    await asyncio.sleep(1.0)
                    continue

                if msg is None:
                    continue
                await self._handle_message(msg)
        except asyncio.CancelledError:
            logger.info("KG invalidate listener cancelled")
            raise
        except Exception as exc:
            logger.warning("KG invalidate listener crashed: %s", exc)
        finally:
            if pubsub is not None:
                try:
                    await pubsub.unsubscribe(KG_INVALIDATE_CHANNEL)
                    await pubsub.close()
                except Exception:
                    pass

    async def _handle_message(self, msg: dict[str, Any]) -> None:
        data = msg.get("data")
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="replace")
        try:
            parsed = json.loads(data) if data else {}
        except json.JSONDecodeError:
            logger.debug("KG invalidate listener: malformed payload %r", data)
            return

        patterns = parsed.get("keys") or list(_DEFAULT_INVALIDATE_PATTERNS)
        cache = get_kg_cache()._get_cache()
        if cache is None:
            return

        total_cleared = 0
        for pattern in patterns:
            try:
                total_cleared += await cache.clear_pattern(pattern)
            except Exception as exc:
                logger.warning(
                    "KG invalidate listener: clear_pattern %s failed: %s", pattern, exc,
                )
        logger.info(
            "KG invalidate listener: version=%s cleared=%d patterns=%d",
            parsed.get("version"),
            total_cleared,
            len(patterns),
        )


_invalidation_listener: KGCacheInvalidationListener | None = None


async def start_invalidation_listener() -> KGCacheInvalidationListener:
    """Idempotently start the singleton listener. Safe to call at app startup."""
    global _invalidation_listener
    if _invalidation_listener is None:
        _invalidation_listener = KGCacheInvalidationListener()
    await _invalidation_listener.start()
    return _invalidation_listener


async def stop_invalidation_listener() -> None:
    """Stop the singleton listener (called on app shutdown)."""
    if _invalidation_listener is not None:
        await _invalidation_listener.stop()
