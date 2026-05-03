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
from typing import Any

from redis.exceptions import RedisError

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

    def __init__(self) -> None:
        """Initialize cache service. Redis client obtained from RedisManager."""
        self.redis_client: Any | None = None
        self.ttl_seconds = 30 * 24 * 60 * 60  # 30 days
        self.cache_prefix = "notebooklm:qa:"

    async def initialize(self) -> None:
        """Initialize Redis connection via RedisManager."""
        try:
            from backend.core.redis_manager import RedisManager

            manager = RedisManager.get_instance()
            client = manager.get_async_client()
            if client is not None:
                self.redis_client = client
                manager.register_component("notebooklm_cache", "active")
                logger.info("NotebookLM cache initialized via RedisManager")
            else:
                manager.register_component("notebooklm_cache", "disabled")
                logger.warning("Redis not available for NotebookLM cache")
        except ImportError as e:
            logger.warning("RedisManager not available, NotebookLM cache disabled: %s", e)
            self.redis_client = None
        except (RedisError, OSError) as e:
            logger.warning("Redis connection failed for NotebookLM cache: %s", e)
            self.redis_client = None
        except Exception as e:
            logger.exception("Unexpected error initializing NotebookLM cache")
            self.redis_client = None

    async def close(self) -> None:
        """Close Redis connection. No-op — connection managed by RedisManager."""
        # Don't close the shared RedisManager client
        pass

    def _hash_question(self, question: str, notebook_id: str = "") -> str:
        """
        Generate cache key from question and optional notebook_id.

        Normalization:
        - Lowercase
        - Strip whitespace
        - Remove punctuation variations
        - MD5 hash for consistent length

        When notebook_id is provided, it is prepended to the normalized
        question before hashing so that identical questions against
        different notebooks produce distinct cache keys.

        Args:
            question: User question
            notebook_id: Optional notebook identifier to scope the cache key

        Returns:
            MD5 hash of normalized question (scoped by notebook_id if given)
        """
        # Normalize question
        normalized = question.lower().strip()
        # Remove common punctuation variations
        normalized = normalized.replace("?", "").replace("!", "").replace(".", "")
        # Include notebook_id in hash input to prevent cross-notebook collisions
        key_input = f"{notebook_id}:{normalized}" if notebook_id else normalized
        # Hash to fixed length
        return hashlib.md5(key_input.encode()).hexdigest()

    async def get(self, question: str, notebook_id: str = "") -> dict | None:
        """
        Get cached answer for question.

        Args:
            question: User question
            notebook_id: Optional notebook identifier to scope the lookup

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
            key = self.cache_prefix + self._hash_question(question, notebook_id)
            cached = await self.redis_client.get(key)

            if cached:
                logger.info(f"✅ Cache HIT: {question[:50]}...")
                return json.loads(cached)
            logger.debug(f"❌ Cache MISS: {question[:50]}...")
            return None
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Corrupt cache entry for question '%.50s': %s", question, e)
            return None
        except (RedisError, OSError) as e:
            logger.warning("Redis error during cache get: %s", e)
            return None
        except Exception as e:
            logger.exception("Unexpected error during cache get")
            return None

    async def set(
        self,
        question: str,
        answer: str,
        metadata: dict | None = None,
        notebook_id: str = "",
    ) -> bool:
        """
        Cache answer for question.

        Args:
            question: User question
            answer: Response answer
            metadata: Optional metadata (domain, language, etc.)
            notebook_id: Optional notebook identifier to scope the cache key

        Returns:
            True if cached successfully
        """
        if not self.redis_client:
            logger.warning("⚠️ Redis not connected, cannot cache")
            return False

        try:
            key = self.cache_prefix + self._hash_question(question, notebook_id)

            # Build cache entry
            from datetime import datetime, timezone

            cache_entry = {
                "question": question,
                "answer": answer,
                "cached_at": datetime.now(tz=timezone.utc).replace(tzinfo=None).isoformat() + "Z",
                "source": "cache",
                "metadata": metadata or {},
            }

            # Store with TTL
            await self.redis_client.setex(
                key, self.ttl_seconds, json.dumps(cache_entry, ensure_ascii=False),
            )

            logger.info(f"✅ Cached: {question[:50]}... (TTL: {self.ttl_seconds}s)")
            return True
        except (TypeError, ValueError) as e:
            logger.warning("Failed to serialize cache entry for '%.50s': %s", question, e)
            return False
        except (RedisError, OSError) as e:
            logger.warning("Redis error during cache set: %s", e)
            return False
        except Exception as e:
            logger.exception("Unexpected error during cache set")
            return False

    async def delete(self, question: str, notebook_id: str = "") -> bool:
        """
        Delete cached answer.

        Args:
            question: Question to remove from cache
            notebook_id: Optional notebook identifier to scope the cache key

        Returns:
            True if deleted
        """
        if not self.redis_client:
            return False

        try:
            key = self.cache_prefix + self._hash_question(question, notebook_id)
            await self.redis_client.delete(key)
            logger.info(f"✅ Deleted cache: {question[:50]}...")
            return True
        except (RedisError, OSError) as e:
            logger.warning("Redis error during cache delete: %s", e)
            return False
        except Exception as e:
            logger.exception("Unexpected error during cache delete")
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
            logger.info("ℹ️ No cache entries to clear")
            return 0
        except (RedisError, OSError) as e:
            logger.warning("Redis error during cache clear: %s", e)
            return 0
        except Exception as e:
            logger.exception("Unexpected error during cache clear")
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
        except (RedisError, OSError) as e:
            logger.warning("Redis error during cache stats: %s", e)
            return {"error": str(e)}
        except Exception as e:
            logger.exception("Unexpected error during cache stats")
            return {"error": str(e)}
