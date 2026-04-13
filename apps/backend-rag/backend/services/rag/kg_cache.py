"""
Knowledge Graph Query Cache

Redis-backed caching layer for KG operations:
- Entity resolution results (fuzzy match is expensive without trigram index)
- BFS traversal results (identical queries traverse the same subgraph)
- KG stats (node/edge counts change rarely)

Falls back to in-memory LRU when Redis is unavailable.
"""

import hashlib
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


def get_kg_version() -> int:
    """Return the current KG version counter."""
    return _kg_version


def increment_kg_version() -> int:
    """
    Increment the KG version counter (thread-safe).

    Call this after any KG mutation (node/edge addition).

    Returns:
        The new version number.
    """
    global _kg_version
    with _kg_version_lock:
        _kg_version += 1
        new_version = _kg_version
    logger.debug("KG version incremented to %d", new_version)
    return new_version

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
