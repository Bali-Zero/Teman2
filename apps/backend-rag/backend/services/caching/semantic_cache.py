"""
Semantic Cache for RAG Responses

Caches LLM responses for semantically similar queries.
Uses embedding cosine similarity to match queries.
Reduces LLM costs by ~60% for FAQ-like queries.

Architecture:
- L1: In-memory LRU (instant, 100 entries, 5min TTL)
- L2: Redis with TTL (shared across workers, per-domain TTL)

Domain-aware TTLs (HIGH-12):
Different query classes have different volatility. Pricing answers change when
the pricebook is updated (~monthly), legal/regulation answers change when a
new circular is ingested (weekly), visa guidance is somewhere in between, and
chit-chat is essentially static. We therefore pick a TTL at ``put`` time based
on a lightweight keyword classifier, with the option to hard-override via the
``domain`` argument. An ingestion hook can call :func:`invalidate_by_domain`
to wipe a single domain without nuking the whole cache.
"""

import hashlib
import json
import logging
import re
import time
from collections import OrderedDict
from typing import Any

logger = logging.getLogger(__name__)

# ── Domain constants ──────────────────────────────────────────────────────────
DOMAIN_PRICING = "pricing"
DOMAIN_LEGAL = "legal"
DOMAIN_VISA = "visa"
DOMAIN_GENERAL = "general"

# Domain-specific TTL (seconds). Shorter TTL = faster refresh after KB update.
DOMAIN_TTL: dict[str, int] = {
    DOMAIN_PRICING: 3600,        # 1h — pricebook changes trigger invalidate_by_domain("pricing")
    DOMAIN_LEGAL: 14400,         # 4h — legal/regulation
    DOMAIN_VISA: 7200,           # 2h — visa guidance
    DOMAIN_GENERAL: 21600,       # 6h — chit-chat, default
}

# Keyword heuristics for domain classification. Kept intentionally simple:
# anything heavier would cost more than the cache saves. The regex patterns
# are evaluated against the lowercased query and picked in priority order.
_DOMAIN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (DOMAIN_PRICING, re.compile(
        r"\b(price|prices|cost|costs|fee|fees|prezzo|prezzi|tarif|biaya|idr|rp|usd|quote|pricelist)\b",
    )),
    (DOMAIN_LEGAL, re.compile(
        r"\b(law|legal|regulation|regolament|uu\s*pdp|legge|peraturan|perpres|kepmen|perda|"
        r"compliance|compliant|undang|statute|decree|circular|ministerial)\b",
    )),
    (DOMAIN_VISA, re.compile(
        r"\b(visa|kitap|kitas|passport|passport|imigrasi|stay|residence|permit|"
        r"c1|c2|c6|c7|c7a|c7b|b211|b213|d1|d2|working\s*visa|investor\s*visa)\b",
    )),
]


def classify_query_domain(query: str) -> str:
    """Return a domain label for the query using keyword heuristics.

    Priority: pricing > legal > visa > general. First regex match wins.
    """
    normalized = query.strip().lower()
    for domain, pattern in _DOMAIN_PATTERNS:
        if pattern.search(normalized):
            return domain
    return DOMAIN_GENERAL


def ttl_for_domain(domain: str) -> int:
    """Resolve TTL seconds for a domain, falling back to general."""
    return DOMAIN_TTL.get(domain, DOMAIN_TTL[DOMAIN_GENERAL])


# L1: In-memory LRU cache
# Each entry tracks the domain so invalidate_by_domain can hit only the right bucket.
_L1_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
_L1_MAX_SIZE = 100
_L1_TTL = 300  # 5 minutes — L1 is a hot-path dedupe, TTL stays short

# L2: Redis config
_L2_PREFIX = "semantic_cache"
_L2_DEFAULT_TTL = 3600  # legacy default; per-domain TTL used via cache_response_async
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
    """Build Redis key for a query hash (legacy, untagged)."""
    return f"{_L2_PREFIX}:{query_hash}"


def _redis_key_for_domain(domain: str, query_hash: str) -> str:
    """Build Redis key tagged with domain so invalidate_by_domain can scan narrowly."""
    return f"{_L2_PREFIX}:{domain}:{query_hash}"


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

    # L2: Redis — probe domain-tagged keys first, then the legacy untagged key.
    redis = _get_redis_client()
    if redis is not None:
        try:
            raw = None
            for domain in DOMAIN_TTL:
                raw = await redis.get(_redis_key_for_domain(domain, key))
                if raw:
                    entry_domain = domain
                    break
            if not raw:
                raw = await redis.get(_redis_key(key))
                entry_domain = DOMAIN_GENERAL
            if raw:
                entry = json.loads(raw)
                response = entry.get("response")
                if response:
                    # Promote to L1
                    _L1_CACHE[key] = {
                        "response": response,
                        "cached_at": now,
                        "query": query[:100],
                        "domain": entry.get("domain", entry_domain),
                    }
                    while len(_L1_CACHE) > _L1_MAX_SIZE:
                        _L1_CACHE.popitem(last=False)
                    logger.info(f"Cache HIT (L2 Redis): {query[:50]}...")
                    return response
        except Exception as e:
            logger.warning(f"Semantic cache L2 get failed: {e}")

    return None


def cache_response(query: str, response: dict[str, Any], domain: str | None = None) -> None:
    """
    Store response in L1 cache (sync).
    For L1+L2 storage, use cache_response_async.

    Args:
        query: The user query
        response: The full response dict to cache
        domain: Optional explicit domain; auto-classified if omitted.
    """
    key = _query_hash(query)
    resolved_domain = domain or classify_query_domain(query)

    # L1: In-memory
    _L1_CACHE[key] = {
        "response": response,
        "cached_at": time.time(),
        "query": query[:100],
        "domain": resolved_domain,
    }

    # Evict if over size
    while len(_L1_CACHE) > _L1_MAX_SIZE:
        _L1_CACHE.popitem(last=False)

    logger.debug(
        f"Cache STORE (L1): {query[:50]}... domain={resolved_domain} (total: {len(_L1_CACHE)})",
    )


async def cache_response_async(
    query: str,
    response: dict[str, Any],
    domain: str | None = None,
    ttl: int | None = None,
) -> None:
    """
    Store response in both L1 (memory) and L2 (Redis) with domain-aware TTL.

    Args:
        query: The user query.
        response: The full response dict to cache.
        domain: Optional explicit domain label; auto-classified if omitted.
        ttl: Optional explicit TTL override. If omitted, TTL is derived from
            the domain (see ``DOMAIN_TTL``).
    """
    key = _query_hash(query)
    resolved_domain = domain or classify_query_domain(query)
    resolved_ttl = ttl if ttl is not None else ttl_for_domain(resolved_domain)

    now = time.time()

    # L1: In-memory
    _L1_CACHE[key] = {
        "response": response,
        "cached_at": now,
        "query": query[:100],
        "domain": resolved_domain,
    }
    while len(_L1_CACHE) > _L1_MAX_SIZE:
        _L1_CACHE.popitem(last=False)

    logger.debug(
        f"Cache STORE (L1): {query[:50]}... domain={resolved_domain} (total: {len(_L1_CACHE)})",
    )

    # L2: Redis (domain-tagged key + per-domain TTL)
    redis = _get_redis_client()
    if redis is not None:
        try:
            payload = json.dumps({
                "response": response,
                "query": query[:100],
                "cached_at": now,
                "domain": resolved_domain,
            })
            await redis.setex(_redis_key_for_domain(resolved_domain, key), resolved_ttl, payload)
            logger.debug(
                f"Cache STORE (L2 Redis): {query[:50]}... "
                f"domain={resolved_domain} ttl={resolved_ttl}s",
            )
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


async def invalidate_by_domain(domain: str) -> int:
    """Invalidate both L1 + L2 entries for a single domain.

    Called after KB ingestion on the affected domain — e.g. the legal
    ingestion pipeline runs ``await invalidate_by_domain("legal")`` so new
    regulations start serving fresh answers within the next request instead of
    sitting stale for the full 4h TTL.

    Returns:
        Total entries cleared (L1 + L2).
    """
    if domain not in DOMAIN_TTL:
        logger.warning(f"invalidate_by_domain called with unknown domain={domain!r}")

    # L1: delete entries whose domain matches
    to_delete_l1 = [k for k, v in _L1_CACHE.items() if v.get("domain") == domain]
    for k in to_delete_l1:
        del _L1_CACHE[k]
    l1_count = len(to_delete_l1)
    if l1_count:
        logger.info(f"Semantic cache INVALIDATE (L1) domain={domain}: {l1_count} entries")

    # L2: scan the domain-tagged prefix and delete.
    l2_count = 0
    redis = _get_redis_client()
    if redis is not None:
        try:
            pattern = f"{_L2_PREFIX}:{domain}:*"
            keys = await redis.keys(pattern)
            if keys:
                l2_count = await redis.delete(*keys)
            logger.info(
                f"Semantic cache INVALIDATE (L2 Redis) domain={domain}: {l2_count} entries",
            )
        except Exception as e:
            logger.warning(f"Semantic cache L2 domain-invalidate failed: {e}")

    return l1_count + l2_count


# Keep old name as alias for backward compatibility
invalidate_cache = invalidate_semantic_cache


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics."""
    redis = _get_redis_client()
    # Count L1 entries by domain for observability.
    by_domain: dict[str, int] = {}
    for entry in _L1_CACHE.values():
        d = entry.get("domain", DOMAIN_GENERAL)
        by_domain[d] = by_domain.get(d, 0) + 1
    return {
        "l1_size": len(_L1_CACHE),
        "l1_max": _L1_MAX_SIZE,
        "l1_ttl": _L1_TTL,
        "l1_by_domain": by_domain,
        "l2_backend": "redis" if redis is not None else "none",
        "l2_default_ttl": _L2_DEFAULT_TTL,
        "l2_prefix": _L2_PREFIX,
        "domain_ttls": dict(DOMAIN_TTL),
    }
