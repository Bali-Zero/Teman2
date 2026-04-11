"""Semantic cache service — Redis-backed query/answer cache with vector similarity.

Two-layer cache strategy:
  1. Exact match: SHA-256 hash of normalized query (instant, zero cost)
  2. Semantic match: cosine similarity via Qdrant collection `v6_cache_vectors`
     — catches paraphrases / rephrasings of the same question (cuts 40%+ LLM costs)

Redis key prefix v6:cache: isolates from V5's namespace.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import redis.asyncio as aioredis
import structlog

from nuzantara_graph.config import Settings
from nuzantara_graph.services.collection_registry import resolve_collection_name

logger = structlog.get_logger()

KEY_PREFIX = "v6:cache:"
STREAM_PREFIX = "v6:stream:"
SEMANTIC_COLLECTION = resolve_collection_name("v6_cache_vectors")
SEMANTIC_SIMILARITY_THRESHOLD = 0.92  # cosine similarity — higher = stricter matching


class SemanticCache:
    """Redis-backed semantic cache for query responses.

    Supports two lookup modes:
      - Exact: fast SHA-256 hash lookup (zero latency overhead)
      - Semantic: embedding similarity via Qdrant (catches paraphrases)

    Usage:
        cache = SemanticCache.from_settings(settings)
        cached = await cache.get_semantic("How to set up a PT PMA?", embeddings, qdrant)
        if not cached:
            result = ... # run graph
            await cache.set_semantic("How to set up a PT PMA?", result, embeddings, qdrant)
    """

    def __init__(self, redis_url: str = "", ttl_seconds: int = 3600) -> None:
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self._client: aioredis.Redis | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> SemanticCache:
        return cls(
            redis_url=settings.redis_url,
            ttl_seconds=settings.semantic_cache_ttl_seconds,
        )

    async def _get_client(self) -> aioredis.Redis | None:
        """Return the Redis client, or ``None`` if no redis_url is configured.

        The cache is opt-in: when running in test mode or local dev without
        a Redis instance, ``redis_url`` is empty and every cache operation
        should behave as a cache miss rather than crash with a ValueError
        from ``aioredis.from_url``.
        """
        if not self.redis_url:
            return None
        if self._client is None:
            try:
                self._client = aioredis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                )
            except ValueError as e:
                logger.warning("cache_disabled", reason=str(e))
                return None
        return self._client

    # ------------------------------------------------------------------
    # Exact cache (hash-based)
    # ------------------------------------------------------------------

    async def get(self, query: str) -> dict[str, Any] | None:
        """Exact hash lookup — O(1), no LLM call."""
        client = await self._get_client()
        if client is None:
            return None
        key = self._make_key(query)

        try:
            raw = await client.get(key)
            if raw is None:
                return None
            logger.debug("cache_hit_exact", query=query[:60])
            return json.loads(raw)
        except Exception as e:
            logger.warning("cache_get_error", error=str(e))
            return None

    async def set(
        self,
        query: str,
        response: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        """Store response with exact hash key."""
        client = await self._get_client()
        if client is None:
            return
        key = self._make_key(query)
        effective_ttl = ttl or self.ttl_seconds

        try:
            await client.setex(key, effective_ttl, json.dumps(response))
            logger.debug("cache_set_exact", query=query[:60], ttl=effective_ttl)
        except Exception as e:
            logger.warning("cache_set_error", error=str(e))

    # ------------------------------------------------------------------
    # Semantic cache (embedding similarity via Qdrant)
    # ------------------------------------------------------------------

    async def get_semantic(
        self,
        query: str,
        embeddings_service: Any,
        qdrant_client: Any,
    ) -> dict[str, Any] | None:
        """Two-phase lookup: exact hash first, then embedding similarity.

        Args:
            query: The user query string.
            embeddings_service: EmbeddingsService instance (has embed_query method).
            qdrant_client: Qdrant async client instance.

        Returns:
            Cached response dict or None if not found.
        """
        # Phase 1: exact match (no embedding cost)
        exact = await self.get(query)
        if exact is not None:
            return exact

        # Phase 2: semantic similarity search
        try:
            vector = await embeddings_service.embed_query(query)
            results = await qdrant_client.search(
                collection_name=SEMANTIC_COLLECTION,
                query_vector=vector,
                limit=1,
                score_threshold=SEMANTIC_SIMILARITY_THRESHOLD,
            )

            if not results:
                return None

            best = results[0]
            cache_key = best.payload.get("cache_key")
            if not cache_key:
                return None

            # Retrieve the actual response from Redis using the stored key
            client = await self._get_client()
            if client is None:
                return None
            raw = await client.get(cache_key)
            if raw is None:
                return None

            logger.info(
                "cache_hit_semantic",
                query=query[:60],
                similarity=round(best.score, 3),
                matched_query=best.payload.get("query", "")[:60],
            )
            return json.loads(raw)

        except Exception as e:
            logger.warning("semantic_cache_get_error", error=str(e))
            return None

    async def set_semantic(
        self,
        query: str,
        response: dict[str, Any],
        embeddings_service: Any,
        qdrant_client: Any,
        ttl: int | None = None,
    ) -> None:
        """Store response in both Redis (exact) and Qdrant (semantic vector).

        Args:
            query: The user query string.
            response: The graph response to cache.
            embeddings_service: EmbeddingsService instance.
            qdrant_client: Qdrant async client instance.
            ttl: Optional TTL override in seconds.
        """
        effective_ttl = ttl or self.ttl_seconds
        cache_key = self._make_key(query)

        # Always store exact copy in Redis
        await self.set(query, response, ttl=effective_ttl)

        # Store embedding in Qdrant for similarity lookup
        try:
            from qdrant_client.models import PointStruct
            import uuid

            vector = await embeddings_service.embed_query(query)
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "query": query[:200],
                    "cache_key": cache_key,
                    "ttl_seconds": effective_ttl,
                },
            )

            await qdrant_client.upsert(
                collection_name=SEMANTIC_COLLECTION,
                points=[point],
            )
            logger.debug(
                "cache_set_semantic",
                query=query[:60],
                ttl=effective_ttl,
            )
        except Exception as e:
            # Non-fatal: exact cache is already stored
            logger.warning("semantic_cache_set_error", error=str(e))

    async def ensure_collection(self, qdrant_client: Any) -> None:
        """Create the Qdrant cache collection if it doesn't exist.

        Call this once at startup from the lifespan handler.
        Embedding dimension: 1536 (text-embedding-3-small — FROZEN).
        """
        try:
            from qdrant_client.models import Distance, VectorParams

            collections = await qdrant_client.get_collections()
            existing = {c.name for c in collections.collections}

            if SEMANTIC_COLLECTION not in existing:
                await qdrant_client.create_collection(
                    collection_name=SEMANTIC_COLLECTION,
                    vectors_config=VectorParams(
                        size=1536,  # text-embedding-3-small — FROZEN
                        distance=Distance.COSINE,
                    ),
                )
                logger.info("semantic_cache_collection_created", collection=SEMANTIC_COLLECTION)
        except Exception as e:
            logger.warning("semantic_cache_collection_error", error=str(e))

    # ------------------------------------------------------------------
    # Pub/Sub for SSE streaming
    # ------------------------------------------------------------------

    async def invalidate(self, query: str) -> None:
        """Remove a cached entry."""
        client = await self._get_client()
        if client is None:
            return
        key = self._make_key(query)
        await client.delete(key)

    async def publish_node_event(
        self,
        run_id: str,
        event: dict[str, Any],
    ) -> None:
        """Publish a graph node event to Redis Pub/Sub for SSE streaming."""
        client = await self._get_client()
        if client is None:
            return
        channel = f"{STREAM_PREFIX}{run_id}"
        try:
            await client.publish(channel, json.dumps(event))
        except Exception as e:
            logger.warning("pubsub_publish_error", error=str(e), run_id=run_id)

    # ------------------------------------------------------------------
    # Health & lifecycle
    # ------------------------------------------------------------------

    async def health_check(self) -> dict[str, Any]:
        """Verify Redis is reachable."""
        try:
            client = await self._get_client()
            if client is None:
                return {
                    "status": "disabled",
                    "url": self.redis_url,
                    "reason": "redis_url not configured",
                    "ok": True,
                }
            pong = await client.ping()
            info = await client.info("server")
            return {
                "status": "healthy",
                "url": self.redis_url,
                "ping": pong,
                "redis_version": info.get("redis_version", "unknown"),
                "ok": True,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "url": self.redis_url,
                "error": str(e),
                "ok": False,
            }

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _make_key(query: str) -> str:
        """Create a deterministic cache key from a query string."""
        normalized = query.strip().lower()
        digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
        return f"{KEY_PREFIX}{digest}"
