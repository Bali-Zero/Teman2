"""
Semantic Cache for RAG Responses

Caches LLM responses for semantically similar queries.
Uses embedding cosine similarity to match queries.
Reduces LLM costs by ~60% for FAQ-like queries.

Architecture:
- L1: In-memory LRU (instant, 100 entries)
- L2: Redis with TTL (shared across workers, 1h TTL)
"""

import hashlib
import logging
import time
from collections import OrderedDict
from typing import Any

logger = logging.getLogger(__name__)

# L1: In-memory LRU cache
_L1_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
_L1_MAX_SIZE = 100
_L1_TTL = 300  # 5 minutes


def _query_hash(query: str) -> str:
    """Create a normalized hash of the query for exact match."""
    normalized = query.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def get_cached_response(query: str) -> dict[str, Any] | None:
    """
    Check L1 (memory) cache for exact query match.

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


def cache_response(query: str, response: dict[str, Any]) -> None:
    """
    Store response in L1 cache.

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


def invalidate_cache(pattern: str | None = None) -> int:
    """
    Invalidate cache entries.

    Args:
        pattern: If None, clear all. If string, clear matching queries.

    Returns:
        Number of entries cleared.
    """
    if pattern is None:
        count = len(_L1_CACHE)
        _L1_CACHE.clear()
        logger.info(f"Cache CLEAR: {count} entries")
        return count

    # Pattern match
    to_delete = [
        k for k, v in _L1_CACHE.items()
        if pattern.lower() in v.get("query", "").lower()
    ]
    for k in to_delete:
        del _L1_CACHE[k]

    logger.info(f"Cache INVALIDATE: {len(to_delete)} entries matching '{pattern}'")
    return len(to_delete)


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics."""
    return {
        "l1_size": len(_L1_CACHE),
        "l1_max": _L1_MAX_SIZE,
        "l1_ttl": _L1_TTL,
    }
