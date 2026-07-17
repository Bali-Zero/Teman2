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

# P7 (SPEC v2 D3): provenance metadata required on every set() call. This is the
# safety guardrail behind "NO verbatim serving from any similarity-based layer;
# verbatim only from exact-match FAQ cache with pre-vetted provenance" — an
# entry with no source_ref/source_date/domain/confidence_class/source_priority
# has no provable provenance and must never be written.
REQUIRED_FAQ_PROVENANCE_KEYS: tuple[str, ...] = (
    "source_ref",
    "source_date",
    "domain",
    "confidence_class",
    "source_priority",
)


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
        except Exception:
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

    @staticmethod
    def _is_valid_cache_shape(entry: Any) -> bool:
        """Validate the cached JSON shape: {"answer": str, "metadata": dict, ...}.

        Anything else (missing answer, non-string answer, non-dict metadata) is
        treated as corrupt — get() self-heals by deleting it (see get()).
        """
        return (
            isinstance(entry, dict)
            and isinstance(entry.get("answer"), str)
            and isinstance(entry.get("metadata"), dict)
        )

    async def _self_heal_delete(self, key: str) -> None:
        """Best-effort delete of a corrupt/malformed cache entry."""
        try:
            await self.redis_client.delete(key)
        except (RedisError, OSError) as e:
            logger.warning("Redis error during self-heal delete of corrupt key: %s", e)
        except Exception:
            logger.exception("Unexpected error during self-heal delete of corrupt key")

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
                "source": "cache",
                "metadata": {...}
            }

        Malformed entries (invalid JSON, or valid JSON that doesn't match the
        expected shape) are treated as a cache MISS and self-heal by deleting
        the corrupt key — a stale/garbled entry must never be served.
        """
        if not self.redis_client:
            logger.warning("⚠️ Redis not connected, cache disabled")
            return None

        key = self.cache_prefix + self._hash_question(question, notebook_id)
        try:
            cached = await self.redis_client.get(key)

            if not cached:
                logger.debug(f"❌ Cache MISS: {question[:50]}...")
                return None

            try:
                entry = json.loads(cached)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(
                    "Corrupt cache entry (invalid JSON) for question '%.50s': %s — self-healing",
                    question,
                    e,
                )
                await self._self_heal_delete(key)
                return None

            if not self._is_valid_cache_shape(entry):
                logger.warning(
                    "Malformed cache entry shape for question '%.50s' — self-healing",
                    question,
                )
                await self._self_heal_delete(key)
                return None

            logger.info(f"✅ Cache HIT: {question[:50]}...")
            return entry
        except (RedisError, OSError) as e:
            logger.warning("Redis error during cache get: %s", e)
            return None
        except Exception:
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
            metadata: REQUIRED provenance metadata — must include source_ref,
                source_date, domain, confidence_class, and source_priority (int).
                This is the P7 (SPEC v2 D3) safety guardrail: verbatim serving
                from this cache is only safe when every entry carries provable,
                pre-vetted provenance.
            notebook_id: Optional notebook identifier to scope the cache key

        Returns:
            True if cached successfully. False if a collision was refused
            (an existing entry has a strictly higher source_priority) or if
            the write failed for infra reasons (Redis unavailable/error).

        Raises:
            ValueError: If metadata is missing a required provenance key, or
                source_priority is not an int. This is a caller-contract
                violation and is raised even when Redis is unavailable — it
                must never be silently swallowed as a "degraded mode".
        """
        metadata = metadata or {}
        missing = [k for k in REQUIRED_FAQ_PROVENANCE_KEYS if k not in metadata]
        if missing:
            raise ValueError(
                f"NotebookLMCacheService.set() requires provenance metadata keys "
                f"{missing} (P7 — verbatim FAQ entries must carry pre-vetted "
                f"provenance: source_ref, source_date, domain, confidence_class, "
                f"source_priority)."
            )
        source_priority = metadata["source_priority"]
        if not isinstance(source_priority, int) or isinstance(source_priority, bool):
            raise ValueError(
                "NotebookLMCacheService.set() requires metadata['source_priority'] "
                "to be an int (used for the collision policy — higher wins)."
            )

        if not self.redis_client:
            logger.warning("⚠️ Redis not connected, cannot cache")
            return False

        try:
            key = self.cache_prefix + self._hash_question(question, notebook_id)

            # Collision policy (P7): an existing entry with a HIGHER
            # source_priority is never silently overwritten by a lower-
            # priority write — last-writer-wins is exactly what provenance
            # enforcement exists to prevent.
            if not await self._existing_entry_outranks(key, source_priority, question):
                return False

            # Build cache entry
            from datetime import datetime, timezone

            cache_entry = {
                "question": question,
                "answer": answer,
                "cached_at": datetime.now(tz=timezone.utc).replace(tzinfo=None).isoformat() + "Z",
                "source": "cache",
                "metadata": metadata,
            }

            # Store with TTL
            await self.redis_client.setex(
                key,
                self.ttl_seconds,
                json.dumps(cache_entry, ensure_ascii=False),
            )

            logger.info(f"✅ Cached: {question[:50]}... (TTL: {self.ttl_seconds}s)")
            return True
        except (TypeError, ValueError) as e:
            logger.warning("Failed to serialize cache entry for '%.50s': %s", question, e)
            return False
        except (RedisError, OSError) as e:
            logger.warning("Redis error during cache set: %s", e)
            return False
        except Exception:
            logger.exception("Unexpected error during cache set")
            return False

    async def _existing_entry_outranks(
        self,
        key: str,
        incoming_priority: int,
        question: str,
    ) -> bool:
        """Return False iff an existing, well-formed entry at `key` has a
        strictly higher source_priority than `incoming_priority` (i.e. the
        write must be refused). Malformed existing entries never block a
        write — they self-heal via overwrite."""
        try:
            existing_raw = await self.redis_client.get(key)
        except (RedisError, OSError):
            return True  # can't check collision — best-effort, allow write

        if not existing_raw:
            return True

        try:
            existing_entry = json.loads(existing_raw)
            existing_priority = existing_entry.get("metadata", {}).get("source_priority")
        except (json.JSONDecodeError, TypeError, AttributeError):
            return True  # corrupt existing entry — allow overwrite (self-heal)

        if isinstance(existing_priority, int) and existing_priority > incoming_priority:
            logger.warning(
                "FAQ cache set() collision refused for '%.50s': existing "
                "source_priority=%d > incoming=%d",
                question,
                existing_priority,
                incoming_priority,
            )
            return False

        return True

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
        except Exception:
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
                logger.info("✅ Cleared %s cache entries", deleted)
                return deleted
            logger.info("ℹ️ No cache entries to clear")
            return 0
        except (RedisError, OSError) as e:
            logger.warning("Redis error during cache clear: %s", e)
            return 0
        except Exception:
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
