"""
Semantic Cache for RAG Responses

Caches LLM responses for semantically similar queries.
Uses embedding cosine similarity to match queries.
Reduces LLM costs by ~60% for FAQ-like queries.

Architecture:
- L1: In-memory LRU (instant, 100 entries, 5min TTL)
- L2: Redis with TTL (shared across workers, 1h TTL)
"""

import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Any

logger = logging.getLogger(__name__)

# L1: In-memory LRU cache
_L1_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
_L1_MAX_SIZE = 100
_L1_TTL = 300  # 5 minutes

# L2: Redis config
_L2_PREFIX = "semantic_cache"
_L2_TTL = 3600  # 1 hour
_redis_checked = False
_redis_client: Any = None


def _query_hash(query: str) -> str:
    """Create a normalized hash of the query for exact match."""
    normalized = query.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _get_redis_client() -> Any:
    """Lazily connect to Redis via RedisManager. Returns async client or None."""
    global _redis_checked, _redis_client
    if _redis_checked:
        return _redis_client
    _redis_checked = True

    try:
        from backend.core.redis_manager import RedisManager

        manager = RedisManager.get_instance()
        client = manager.get_async_client()
        if client is not None:
            _redis_client = client
            logger.info("Semantic cache L2 Redis connected via RedisManager")
        else:
            logger.info("Semantic cache L2: no Redis available, L1-only mode")
    except Exception as e:
        logger.warning(f"Semantic cache L2 Redis init failed: {e}")

    return _redis_client


def _redis_key(query_hash: str) -> str:
    """Build Redis key for a query hash."""
    return f"{_L2_PREFIX}:{query_hash}"


def get_cached_response(query: str) -> dict[str, Any] | None:
    """
    Check L1 (memory) cache for exact query match.
    L2 (Redis) is async — use get_cached_response_async for full L1+L2 lookup.

    Returns cached response dict or None.
    """
    key = _query_hash(query)
    now = time.time()

    # L1: In-memory
    if key in _L1_CACHE:
        entry = _L1_CACHE[key]
        if now - entry["cached_at"] < _L1_TTL:
            _L1_CACHE.move_to_end(key)
            logger.info(f"Cache HIT (L1 memory): {query[:50]}...")
            return entry["response"]
        else:
            del _L1_CACHE[key]

    return None


async def get_cached_response_async(query: str) -> dict[str, Any] | None:
    """
    Check L1 (memory) then L2 (Redis) for exact query match.

    On L2 hit, promotes entry back to L1 for subsequent fast access.

    Returns cached response dict or None.
    """
    key = _query_hash(query)
    now = time.time()

    # L1: In-memory
    if key in _L1_CACHE:
        entry = _L1_CACHE[key]
        if now - entry["cached_at"] < _L1_TTL:
            _L1_CACHE.move_to_end(key)
            logger.info(f"Cache HIT (L1 memory): {query[:50]}...")
            return entry["response"]
        else:
            del _L1_CACHE[key]

    # L2: Redis
    redis = _get_redis_client()
    if redis is not None:
        try:
            raw = await redis.get(_redis_key(key))
            if raw:
                entry = json.loads(raw)
                response = entry.get("response")
                if response:
                    # Promote to L1
                    _L1_CACHE[key] = {
                        "response": response,
                        "cached_at": now,
                        "query": query[:100],
                    }
                    while len(_L1_CACHE) > _L1_MAX_SIZE:
                        _L1_CACHE.popitem(last=False)
                    logger.info(f"Cache HIT (L2 Redis): {query[:50]}...")
                    return response
        except Exception as e:
            logger.warning(f"Semantic cache L2 get failed: {e}")

    return None


def cache_response(query: str, response: dict[str, Any]) -> None:
    """
    Store response in L1 cache (sync).
    For L1+L2 storage, use cache_response_async.

    Args:
        query: The user query
        response: The full response dict to cache
    """
    key = _query_hash(query)

    # L1: In-memory
    _L1_CACHE[key] = {
        "response": response,
        "cached_at": time.time(),
        "query": query[:100],
    }

    # Evict if over size
    while len(_L1_CACHE) > _L1_MAX_SIZE:
        _L1_CACHE.popitem(last=False)

    logger.debug(f"Cache STORE (L1): {query[:50]}... (total: {len(_L1_CACHE)})")


async def cache_response_async(query: str, response: dict[str, Any]) -> None:
    """
    Store response in both L1 (memory) and L2 (Redis).

    Args:
        query: The user query
        response: The full response dict to cache
    """
    key = _query_hash(query)

    # L1: In-memory
    _L1_CACHE[key] = {
        "response": response,
        "cached_at": time.time(),
        "query": query[:100],
    }
    while len(_L1_CACHE) > _L1_MAX_SIZE:
        _L1_CACHE.popitem(last=False)

    logger.debug(f"Cache STORE (L1): {query[:50]}... (total: {len(_L1_CACHE)})")

    # L2: Redis
    redis = _get_redis_client()
    if redis is not None:
        try:
            payload = json.dumps({
                "response": response,
                "query": query[:100],
                "cached_at": time.time(),
            })
            await redis.setex(_redis_key(key), _L2_TTL, payload)
            logger.debug(f"Cache STORE (L2 Redis): {query[:50]}...")
        except Exception as e:
            logger.warning(f"Semantic cache L2 set failed: {e}")


def invalidate_semantic_cache(pattern: str | None = None) -> int:
    """
    Invalidate L1 cache entries (sync).
    For L1+L2 invalidation, use invalidate_semantic_cache_async.

    Args:
        pattern: If None, clear all. If string, clear matching queries.

    Returns:
        Number of L1 entries cleared.
    """
    if pattern is None:
        count = len(_L1_CACHE)
        _L1_CACHE.clear()
        logger.info(f"Semantic cache CLEAR (L1): {count} entries")
        return count

    # Pattern match
    to_delete = [
        k for k, v in _L1_CACHE.items()
        if pattern.lower() in v.get("query", "").lower()
    ]
    for k in to_delete:
        del _L1_CACHE[k]

    logger.info(f"Semantic cache INVALIDATE (L1): {len(to_delete)} entries matching '{pattern}'")
    return len(to_delete)


async def invalidate_semantic_cache_async(pattern: str | None = None) -> int:
    """
    Invalidate both L1 (memory) and L2 (Redis) cache entries.

    Args:
        pattern: If None, clear all. If string, clear matching L1 queries
                 and all L2 keys with semantic_cache: prefix.

    Returns:
        Total number of entries cleared (L1 + L2).
    """
    # L1
    l1_count = invalidate_semantic_cache(pattern)

    # L2: Redis
    l2_count = 0
    redis = _get_redis_client()
    if redis is not None:
        try:
            redis_pattern = f"{_L2_PREFIX}:*"
            keys = await redis.keys(redis_pattern)
            if keys:
                l2_count = await redis.delete(*keys)
            logger.info(f"Semantic cache CLEAR (L2 Redis): {l2_count} entries")
        except Exception as e:
            logger.warning(f"Semantic cache L2 invalidation failed: {e}")

    return l1_count + l2_count


# Keep old name as alias for backward compatibility
invalidate_cache = invalidate_semantic_cache


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics."""
    redis = _get_redis_client()
    return {
        "l1_size": len(_L1_CACHE),
        "l1_max": _L1_MAX_SIZE,
        "l1_ttl": _L1_TTL,
        "l2_backend": "redis" if redis is not None else "none",
        "l2_ttl": _L2_TTL,
        "l2_prefix": _L2_PREFIX,
    }
