"""
NotebookLM Cache Service

Redis-based caching for NotebookLM Q&A to reduce API costs.

Strategy:
- Cache 640 common FAQ with pre-calculated answers
- Lookup by question hash (MD5)
- TTL: 30 days (refresh monthly)
- Cache hit → instant response (< 1ms)
- Cache miss → call NotebookLM API + cache result

Expected savings: ~80% API calls
"""

import hashlib
import json
import logging
import os

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class NotebookLMCacheService:
    """
    Redis cache for NotebookLM Q&A responses.

    Usage:
        cache = NotebookLMCacheService()
        await cache.initialize()

        # Check cache first
        answer = await cache.get("What is PPh Badan?")
        if answer:
            return answer  # Cache hit!

        # Cache miss - call API
        answer = await call_notebooklm_api(question)
        await cache.set(question, answer)
    """

    def __init__(self, redis_url: str | None = None):
        """
        Initialize cache service.

        Args:
            redis_url: Redis connection URL (defaults to env var REDIS_URL)
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self.redis_client: redis.Redis | None = None
        self.ttl_seconds = 30 * 24 * 60 * 60  # 30 days
        self.cache_prefix = "notebooklm:qa:"

    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = await redis.from_url(
                self.redis_url, encoding="utf-8", decode_responses=True
            )
            # Test connection
            await self.redis_client.ping()
            logger.info("✅ NotebookLM cache initialized (Redis connected)")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self.redis_client = None

    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("✅ NotebookLM cache closed")

    def _hash_question(self, question: str) -> str:
        """
        Generate cache key from question.

        Normalization:
        - Lowercase
        - Strip whitespace
        - Remove punctuation variations
        - MD5 hash for consistent length

        Args:
            question: User question

        Returns:
            MD5 hash of normalized question
        """
        # Normalize question
        normalized = question.lower().strip()
        # Remove common punctuation variations
        normalized = normalized.replace("?", "").replace("!", "").replace(".", "")
        # Hash to fixed length
        return hashlib.md5(normalized.encode()).hexdigest()

    async def get(self, question: str) -> dict | None:
        """
        Get cached answer for question.

        Args:
            question: User question

        Returns:
            Cached response dict or None if not found

        Response format:
            {
                "question": "What is PPh Badan?",
                "answer": "PPh Badan is...",
                "cached_at": "2026-02-11T10:00:00Z",
                "source": "cache"
            }
        """
        if not self.redis_client:
            logger.warning("⚠️ Redis not connected, cache disabled")
            return None

        try:
            key = self.cache_prefix + self._hash_question(question)
            cached = await self.redis_client.get(key)

            if cached:
                logger.info(f"✅ Cache HIT: {question[:50]}...")
                return json.loads(cached)
            else:
                logger.debug(f"❌ Cache MISS: {question[:50]}...")
                return None
        except Exception as e:
            logger.error(f"❌ Cache get error: {e}")
            return None

    async def set(self, question: str, answer: str, metadata: dict | None = None) -> bool:
        """
        Cache answer for question.

        Args:
            question: User question
            answer: Response answer
            metadata: Optional metadata (domain, language, etc.)

        Returns:
            True if cached successfully
        """
        if not self.redis_client:
            logger.warning("⚠️ Redis not connected, cannot cache")
            return False

        try:
            key = self.cache_prefix + self._hash_question(question)

            # Build cache entry
            from datetime import datetime

            cache_entry = {
                "question": question,
                "answer": answer,
                "cached_at": datetime.utcnow().isoformat() + "Z",
                "source": "cache",
                "metadata": metadata or {},
            }

            # Store with TTL
            await self.redis_client.setex(
                key, self.ttl_seconds, json.dumps(cache_entry, ensure_ascii=False)
            )

            logger.info(f"✅ Cached: {question[:50]}... (TTL: {self.ttl_seconds}s)")
            return True
        except Exception as e:
            logger.error(f"❌ Cache set error: {e}")
            return False

    async def delete(self, question: str) -> bool:
        """
        Delete cached answer.

        Args:
            question: Question to remove from cache

        Returns:
            True if deleted
        """
        if not self.redis_client:
            return False

        try:
            key = self.cache_prefix + self._hash_question(question)
            await self.redis_client.delete(key)
            logger.info(f"✅ Deleted cache: {question[:50]}...")
            return True
        except Exception as e:
            logger.error(f"❌ Cache delete error: {e}")
            return False

    async def clear_all(self) -> int:
        """
        Clear all NotebookLM cache entries.

        Returns:
            Number of keys deleted
        """
        if not self.redis_client:
            return 0

        try:
            # Find all keys with prefix
            keys = []
            async for key in self.redis_client.scan_iter(match=f"{self.cache_prefix}*"):
                keys.append(key)

            if keys:
                deleted = await self.redis_client.delete(*keys)
                logger.info(f"✅ Cleared {deleted} cache entries")
                return deleted
            else:
                logger.info("ℹ️ No cache entries to clear")
                return 0
        except Exception as e:
            logger.error(f"❌ Cache clear error: {e}")
            return 0

    async def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            {
                "total_keys": 640,
                "memory_usage_mb": 2.5,
                "hit_rate": 0.82
            }
        """
        if not self.redis_client:
            return {"error": "Redis not connected"}

        try:
            # Count keys
            total_keys = 0
            async for _ in self.redis_client.scan_iter(match=f"{self.cache_prefix}*"):
                total_keys += 1

            # Get memory info (requires Redis INFO command)
            info = await self.redis_client.info("memory")
            memory_mb = info.get("used_memory", 0) / (1024 * 1024)

            return {
                "total_keys": total_keys,
                "memory_usage_mb": round(memory_mb, 2),
                "cache_prefix": self.cache_prefix,
                "ttl_days": self.ttl_seconds / (24 * 60 * 60),
            }
        except Exception as e:
            logger.error(f"❌ Cache stats error: {e}")
            return {"error": str(e)}
