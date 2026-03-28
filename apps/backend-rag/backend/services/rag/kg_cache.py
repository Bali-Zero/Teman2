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
from typing import Any

logger = logging.getLogger(__name__)

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
        """Get cached domain subgraph result."""
        cache = self._get_cache()
        if cache is None:
            return None
        key = f"zantara:kg:subgraph:{domain}:{self._hash_key(query.lower())}"
        result = await cache.get(key)
        if result is not None:
            _inc_metric("get", "hit")
        else:
            _inc_metric("get", "miss")
        return result

    async def set_subgraph_result(self, domain: str, query: str, result: dict) -> None:
        """Cache domain subgraph result."""
        cache = self._get_cache()
        if cache is None:
            return
        key = f"zantara:kg:subgraph:{domain}:{self._hash_key(query.lower())}"
        serializable = _make_serializable(result)
        await cache.set(key, serializable, TTL_SUBGRAPH)
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
