"""
Tests for cache coherence hardening.

Covers:
- Semantic cache L1+L2 async operations
- Unified invalidation (invalidate_all_caches)
- Rate limiter fallback warning
- invalidate_cache import presence in mutation routers
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Semantic Cache L1+L2 Tests
# ---------------------------------------------------------------------------


class TestSemanticCacheL2:
    """Tests for semantic_cache.py L2 Redis layer."""

    def setup_method(self) -> None:
        from backend.services.caching import semantic_cache

        semantic_cache._L1_CACHE.clear()
        # Reset Redis state for each test
        semantic_cache._redis_checked = False
        semantic_cache._redis_client = None

    def test_sync_cache_response_l1_only(self) -> None:
        """Sync cache_response stores in L1."""
        from backend.services.caching.semantic_cache import (
            _L1_CACHE,
            cache_response,
            get_cached_response,
        )

        cache_response("test query", {"answer": "42"})
        assert len(_L1_CACHE) == 1
        result = get_cached_response("test query")
        assert result is not None
        assert result["answer"] == "42"

    @pytest.mark.asyncio
    async def test_async_cache_stores_l1_and_l2(self) -> None:
        """cache_response_async stores in both L1 and L2."""
        from backend.services.caching.semantic_cache import (
            _L1_CACHE,
            _query_hash,
            _redis_key_for_domain,
            cache_response_async,
            classify_query_domain,
        )

        mock_redis = AsyncMock()
        with patch(
            "backend.services.caching.semantic_cache._get_redis_client",
            return_value=mock_redis,
        ):
            await cache_response_async("visa query", {"answer": "KITAS"})

        # L1 stored
        key = _query_hash("visa query")
        assert key in _L1_CACHE
        assert _L1_CACHE[key]["response"]["answer"] == "KITAS"

        # L2 stored via setex
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        domain = classify_query_domain("visa query")
        assert call_args[0][0] == _redis_key_for_domain(domain, key)
        from backend.services.caching.semantic_cache import ttl_for_domain
        assert call_args[0][1] == ttl_for_domain(domain)  # per-domain TTL

    @pytest.mark.asyncio
    async def test_async_get_l2_hit_promotes_to_l1(self) -> None:
        """L2 hit promotes entry to L1."""
        import json

        from backend.services.caching.semantic_cache import (
            _L1_CACHE,
            _query_hash,
            _redis_key,
            get_cached_response_async,
        )

        key = _query_hash("company setup")
        payload = json.dumps({
            "response": {"answer": "PT PMA"},
            "query": "company setup",
            "cached_at": time.time(),
        })

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=payload)

        with patch(
            "backend.services.caching.semantic_cache._get_redis_client",
            return_value=mock_redis,
        ):
            result = await get_cached_response_async("company setup")

        assert result is not None
        assert result["answer"] == "PT PMA"
        # Promoted to L1
        assert key in _L1_CACHE

    @pytest.mark.asyncio
    async def test_async_get_l1_hit_skips_l2(self) -> None:
        """L1 hit returns without touching L2."""
        from backend.services.caching.semantic_cache import (
            cache_response,
            get_cached_response_async,
        )

        cache_response("tax query", {"answer": "NPWP"})

        mock_redis = AsyncMock()
        with patch(
            "backend.services.caching.semantic_cache._get_redis_client",
            return_value=mock_redis,
        ):
            result = await get_cached_response_async("tax query")

        assert result is not None
        assert result["answer"] == "NPWP"
        mock_redis.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalidate_async_clears_l1_and_l2(self) -> None:
        """invalidate_semantic_cache_async clears both L1 and L2."""
        from backend.services.caching.semantic_cache import (
            cache_response,
            invalidate_semantic_cache_async,
        )

        cache_response("q1", {"a": 1})
        cache_response("q2", {"a": 2})

        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=["semantic_cache:abc", "semantic_cache:def"])
        mock_redis.delete = AsyncMock(return_value=2)

        with patch(
            "backend.services.caching.semantic_cache._get_redis_client",
            return_value=mock_redis,
        ):
            total = await invalidate_semantic_cache_async()

        # L1: 2 cleared + L2: 2 cleared
        assert total == 4

    @pytest.mark.asyncio
    async def test_l2_failure_graceful(self) -> None:
        """L2 Redis failure doesn't break L1 operations."""
        from backend.services.caching.semantic_cache import (
            cache_response_async,
            get_cached_response_async,
        )

        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis down"))
        mock_redis.get = AsyncMock(side_effect=Exception("Redis down"))

        with patch(
            "backend.services.caching.semantic_cache._get_redis_client",
            return_value=mock_redis,
        ):
            # Store should succeed (L1 works, L2 fails silently)
            await cache_response_async("resilient query", {"answer": "ok"})

            # Get should return L1 hit even though L2 would fail
            result = await get_cached_response_async("resilient query")
            assert result is not None
            assert result["answer"] == "ok"

    def test_cache_stats_includes_l2(self) -> None:
        """get_cache_stats includes L2 info."""
        from backend.services.caching.semantic_cache import get_cache_stats

        stats = get_cache_stats()
        assert "l2_backend" in stats
        assert "l2_default_ttl" in stats
        assert stats["l2_default_ttl"] == 3600
        assert "domain_ttls" in stats
        assert "l2_prefix" in stats

    def test_backward_compat_alias(self) -> None:
        """invalidate_cache alias still works."""
        from backend.services.caching.semantic_cache import (
            invalidate_cache as sc_invalidate,
            invalidate_semantic_cache,
        )

        assert sc_invalidate is invalidate_semantic_cache


# ---------------------------------------------------------------------------
# Unified Invalidation Tests
# ---------------------------------------------------------------------------


class TestUnifiedInvalidation:
    """Tests for invalidate_all_caches in core/cache.py."""

    @pytest.mark.asyncio
    async def test_invalidate_all_caches_calls_both(self) -> None:
        """invalidate_all_caches clears CacheService and semantic cache."""
        from backend.core.cache import invalidate_all_caches

        with (
            patch("backend.core.cache.invalidate_cache", new_callable=AsyncMock, return_value=5) as mock_cache,
            patch(
                "backend.services.caching.semantic_cache.invalidate_semantic_cache_async",
                new_callable=AsyncMock,
                return_value=3,
            ) as mock_semantic,
        ):
            result = await invalidate_all_caches("zantara:test:*")

        mock_cache.assert_called_once_with("zantara:test:*", cache_service=None)
        mock_semantic.assert_called_once()
        assert result["cache_service"] == 5
        assert result["semantic_cache"] == 3

    @pytest.mark.asyncio
    async def test_invalidate_all_caches_semantic_failure(self) -> None:
        """Semantic cache failure doesn't break unified invalidation."""
        from backend.core.cache import invalidate_all_caches

        with (
            patch("backend.core.cache.invalidate_cache", new_callable=AsyncMock, return_value=2),
            patch(
                "backend.services.caching.semantic_cache.invalidate_semantic_cache_async",
                new_callable=AsyncMock,
                side_effect=Exception("boom"),
            ),
        ):
            result = await invalidate_all_caches()

        assert result["cache_service"] == 2
        assert result["semantic_cache"] == 0


# ---------------------------------------------------------------------------
# Router Invalidation Coverage Tests
# ---------------------------------------------------------------------------


class TestRouterInvalidationCoverage:
    """Verify all 19 mutation routers import invalidate_cache (source-level check)."""

    ROUTERS_WITH_INVALIDATION = [
        "news",
        "knowledge_visa",
        "hr",
        "prime_v2",
        "team_drive",
        "agents",
        "episodic_memory",
        "lam_memory",
        "memory_vector",
        "session",
        "sheets",
        "newsletter",
        "messaging_identity",
        "conversations",
        "autonomous_execution",
        "omnichannel",
        "zoho_email",
        "intel_scraper",
        "crm_clients_documents",
    ]

    @pytest.mark.parametrize("router_name", ROUTERS_WITH_INVALIDATION)
    def test_router_imports_invalidate_cache(self, router_name: str) -> None:
        """Each mutation router must import invalidate_cache from core.cache."""
        from pathlib import Path

        router_file = (
            Path(__file__).parent.parent.parent.parent
            / "app"
            / "routers"
            / f"{router_name}.py"
        )
        assert router_file.exists(), f"Router file not found: {router_file}"
        source = router_file.read_text()
        assert "from backend.core.cache import" in source, (
            f"{router_name}.py missing 'from backend.core.cache import'"
        )
        assert "invalidate_cache" in source, (
            f"{router_name}.py missing 'invalidate_cache' usage"
        )


# ---------------------------------------------------------------------------
# Rate Limiter Tests
# ---------------------------------------------------------------------------


try:
    import fastapi  # noqa: F401
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False


@pytest.mark.skipif(not _HAS_FASTAPI, reason="fastapi not installed")
class TestRateLimiterFallback:
    """Tests for rate limiter Redis fallback behavior."""

    def test_fallback_to_memory(self) -> None:
        """Rate limiter falls back to in-memory when Redis unavailable."""
        with patch("backend.core.redis_manager.RedisManager.get_instance") as mock_mgr:
            instance = MagicMock()
            instance.get_sync_client.return_value = None
            instance.register_component = MagicMock()
            mock_mgr.return_value = instance

            from backend.middleware.rate_limiter import RateLimiter

            limiter = RateLimiter()
            assert limiter.redis_available is False
            instance.register_component.assert_called_with("rate_limiter", "fallback_memory")

    def test_in_memory_rate_limiting(self) -> None:
        """In-memory sliding window works correctly."""
        from backend.middleware.rate_limiter import _rate_limit_storage

        with patch("backend.core.redis_manager.RedisManager.get_instance") as mock_mgr:
            instance = MagicMock()
            instance.get_sync_client.return_value = None
            instance.register_component = MagicMock()
            mock_mgr.return_value = instance

            from backend.middleware.rate_limiter import RateLimiter

            limiter = RateLimiter()

            # Should allow first request
            allowed, info = limiter.is_allowed("test:ip:127.0.0.1", limit=2, window=60)
            assert allowed is True
            assert info["remaining"] >= 0

            # Should allow second request
            allowed, info = limiter.is_allowed("test:ip:127.0.0.1", limit=2, window=60)
            assert allowed is True

            # Third should be blocked
            allowed, info = limiter.is_allowed("test:ip:127.0.0.1", limit=2, window=60)
            assert allowed is False
