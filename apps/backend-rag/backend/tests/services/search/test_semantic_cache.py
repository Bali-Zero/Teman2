"""
Tests for semantic_cache.py - Semantic caching for RAG queries.
"""

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from backend.services.search.semantic_cache import SemanticCache, get_semantic_cache


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    redis.zadd = AsyncMock()
    redis.zcard = AsyncMock(return_value=0)
    redis.zrange = AsyncMock(return_value=[])
    redis.delete = AsyncMock()
    redis.keys = AsyncMock(return_value=[])
    redis.zrem = AsyncMock()
    return redis


@pytest.fixture
def cache(mock_redis):
    return SemanticCache(
        redis_client=mock_redis,
        similarity_threshold=0.95,
        default_ttl=3600,
        max_cache_size=100,
    )


class TestGetCachedResult:
    """Tests for get_cached_result method."""

    @pytest.mark.asyncio
    async def test_exact_match_found(self, cache, mock_redis):
        cached_data = json.dumps({
            "query": "test query",
            "result": {"answer": "cached answer"},
        })
        mock_redis.get = AsyncMock(return_value=cached_data)

        result = await cache.get_cached_result("test query")
        assert result is not None
        assert result["cache_hit"] == "exact"

    @pytest.mark.asyncio
    async def test_no_match_returns_none(self, cache, mock_redis):
        mock_redis.get = AsyncMock(return_value=None)
        result = await cache.get_cached_result("test query")
        assert result is None

    @pytest.mark.asyncio
    async def test_error_returns_none(self, cache, mock_redis):
        mock_redis.get = AsyncMock(side_effect=Exception("Redis error"))
        result = await cache.get_cached_result("test query")
        assert result is None


class TestCacheResult:
    """Tests for cache_result method."""

    @pytest.mark.asyncio
    async def test_stores_result_and_embedding(self, cache, mock_redis):
        embedding = np.random.rand(1536).astype(np.float32)
        result = {"answer": "test answer"}

        success = await cache.cache_result("test query", embedding, result)
        assert success is True
        # Should call setex twice (result + embedding) and zadd once
        assert mock_redis.setex.call_count == 2
        assert mock_redis.zadd.call_count == 1

    @pytest.mark.asyncio
    async def test_custom_ttl(self, cache, mock_redis):
        embedding = np.random.rand(1536).astype(np.float32)
        await cache.cache_result("test", embedding, {"a": 1}, ttl=600)
        # Check first setex call uses custom ttl
        first_call = mock_redis.setex.call_args_list[0]
        assert first_call.args[1] == 600

    @pytest.mark.asyncio
    async def test_error_returns_false(self, cache, mock_redis):
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis error"))
        embedding = np.random.rand(1536).astype(np.float32)
        success = await cache.cache_result("test", embedding, {"a": 1})
        assert success is False


class TestCosineSimilarity:
    """Tests for _cosine_similarity static method."""

    def test_identical_vectors(self):
        vec = np.array([1.0, 2.0, 3.0])
        similarity = SemanticCache._cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([0.0, 1.0])
        similarity = SemanticCache._cosine_similarity(vec1, vec2)
        assert abs(similarity) < 1e-6

    def test_opposite_vectors(self):
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([-1.0, 0.0])
        similarity = SemanticCache._cosine_similarity(vec1, vec2)
        assert abs(similarity + 1.0) < 1e-6


class TestCacheKeys:
    """Tests for key generation methods."""

    def test_cache_key_format(self, cache):
        key = cache._get_cache_key("test query")
        expected_hash = hashlib.md5("test query".encode()).hexdigest()
        assert key == f"semantic_cache:{expected_hash}"

    def test_embedding_key_format(self, cache):
        key = cache._get_embedding_key("test query")
        expected_hash = hashlib.md5("test query".encode()).hexdigest()
        assert key == f"embedding:{expected_hash}"

    def test_case_insensitive_keys(self, cache):
        key1 = cache._get_cache_key("Test Query")
        key2 = cache._get_cache_key("test query")
        assert key1 == key2

    def test_whitespace_normalized(self, cache):
        key1 = cache._get_cache_key("  test query  ")
        key2 = cache._get_cache_key("test query")
        assert key1 == key2


class TestEnforceCacheSize:
    """Tests for _enforce_cache_size method."""

    @pytest.mark.asyncio
    async def test_no_eviction_under_limit(self, cache, mock_redis):
        mock_redis.zcard = AsyncMock(return_value=50)
        await cache._enforce_cache_size()
        mock_redis.zrange.assert_not_called()

    @pytest.mark.asyncio
    async def test_eviction_over_limit(self, cache, mock_redis):
        mock_redis.zcard = AsyncMock(return_value=105)
        mock_redis.zrange = AsyncMock(return_value=[b"embedding:key1", b"embedding:key2"])
        await cache._enforce_cache_size()
        # Should try to delete excess entries
        assert mock_redis.delete.call_count > 0


class TestGetCacheStats:
    """Tests for get_cache_stats method."""

    @pytest.mark.asyncio
    async def test_returns_stats(self, cache, mock_redis):
        mock_redis.zcard = AsyncMock(return_value=50)
        stats = await cache.get_cache_stats()
        assert stats["cache_size"] == 50
        assert stats["max_cache_size"] == 100
        assert stats["similarity_threshold"] == 0.95

    @pytest.mark.asyncio
    async def test_error_returns_empty(self, cache, mock_redis):
        mock_redis.zcard = AsyncMock(side_effect=Exception("Redis error"))
        stats = await cache.get_cache_stats()
        assert stats == {}


class TestClearCache:
    """Tests for clear_cache method."""

    @pytest.mark.asyncio
    async def test_clears_all_keys(self, cache, mock_redis):
        mock_redis.keys = AsyncMock(return_value=[b"key1", b"key2"])
        await cache.clear_cache()
        mock_redis.delete.assert_called_once()


class TestGetSemanticCache:
    """Tests for get_semantic_cache singleton factory."""

    def test_creates_instance(self, mock_redis):
        import backend.services.search.semantic_cache as module
        module._semantic_cache = None  # Reset singleton
        cache = get_semantic_cache(mock_redis)
        assert isinstance(cache, SemanticCache)
        module._semantic_cache = None  # Clean up
