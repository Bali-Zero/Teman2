"""
Complete 100% Coverage Tests for Semantic Cache Service

Tests all methods and edge cases in semantic_cache.py.
"""

import json
from unittest.mock import AsyncMock

import numpy as np
import pytest


@pytest.fixture
def mock_redis():
    """Create mock Redis client"""
    return AsyncMock()


@pytest.fixture
def cache_service(mock_redis):
    """Create SemanticCache instance"""
    from services.semantic_cache import SemanticCache

    return SemanticCache(
        redis_client=mock_redis, similarity_threshold=0.95, default_ttl=3600, max_cache_size=1000
    )


class TestSemanticCacheInit:
    """Tests for SemanticCache initialization"""

    def test_init_default_values(self, mock_redis):
        """Test initialization with default values"""
        from services.semantic_cache import SemanticCache

        cache = SemanticCache(mock_redis)

        assert cache.redis is mock_redis
        assert cache.similarity_threshold == 0.95
        assert cache.default_ttl == 3600
        assert cache.max_cache_size == 10000
        assert cache.cache_prefix == "semantic_cache:"
        assert cache.embedding_prefix == "embedding:"

    def test_init_custom_values(self, mock_redis):
        """Test initialization with custom values"""
        from services.semantic_cache import SemanticCache

        cache = SemanticCache(
            mock_redis, similarity_threshold=0.9, default_ttl=7200, max_cache_size=5000
        )

        assert cache.similarity_threshold == 0.9
        assert cache.default_ttl == 7200
        assert cache.max_cache_size == 5000


class TestGetCachedResult:
    """Tests for get_cached_result method"""

    @pytest.mark.asyncio
    async def test_exact_match_found(self, cache_service, mock_redis):
        """Test exact match cache hit"""
        cached_data = {"query": "test query", "result": {"answer": "test answer"}}
        mock_redis.get.return_value = json.dumps(cached_data)

        result = await cache_service.get_cached_result("test query")

        assert result is not None
        assert result["cache_hit"] == "exact"

    @pytest.mark.asyncio
    async def test_no_exact_match_no_embedding(self, cache_service, mock_redis):
        """Test no match without embedding"""
        mock_redis.get.return_value = None

        result = await cache_service.get_cached_result("test query")

        assert result is None

    @pytest.mark.asyncio
    async def test_semantic_match_found(self, cache_service, mock_redis):
        """Test semantic similarity match"""
        mock_redis.get.side_effect = [
            None,  # No exact match
            json.dumps({"query": "similar", "result": {"data": "test"}}),  # Semantic match
        ]

        # Mock _find_similar_query
        cache_service._find_similar_query = AsyncMock(
            return_value={"data": {"result": {"data": "test"}}, "similarity": 0.97}
        )

        query_embedding = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = await cache_service.get_cached_result("test query", query_embedding)

        assert result is not None
        assert result["cache_hit"] == "semantic"

    @pytest.mark.asyncio
    async def test_no_semantic_match(self, cache_service, mock_redis):
        """Test no semantic match found"""
        mock_redis.get.return_value = None
        cache_service._find_similar_query = AsyncMock(return_value=None)

        query_embedding = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = await cache_service.get_cached_result("test query", query_embedding)

        assert result is None

    @pytest.mark.asyncio
    async def test_error_handling(self, cache_service, mock_redis):
        """Test error handling returns None"""
        mock_redis.get.side_effect = Exception("Redis error")

        result = await cache_service.get_cached_result("test query")

        assert result is None


class TestCacheResult:
    """Tests for cache_result method"""

    @pytest.mark.asyncio
    async def test_cache_success(self, cache_service, mock_redis):
        """Test successful caching"""
        mock_redis.setex = AsyncMock()
        mock_redis.zadd = AsyncMock()
        cache_service._enforce_cache_size = AsyncMock()

        query_embedding = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = {"answer": "test"}

        success = await cache_service.cache_result("test query", query_embedding, result)

        assert success is True
        assert mock_redis.setex.call_count == 2  # Cache + embedding
        mock_redis.zadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_with_custom_ttl(self, cache_service, mock_redis):
        """Test caching with custom TTL"""
        mock_redis.setex = AsyncMock()
        mock_redis.zadd = AsyncMock()
        cache_service._enforce_cache_size = AsyncMock()

        query_embedding = np.array([1.0, 2.0, 3.0], dtype=np.float32)

        await cache_service.cache_result("test query", query_embedding, {}, ttl=7200)

        # Verify custom TTL was used
        call_args = mock_redis.setex.call_args_list[0]
        assert call_args[0][1] == 7200

    @pytest.mark.asyncio
    async def test_cache_error_handling(self, cache_service, mock_redis):
        """Test caching error handling"""
        mock_redis.setex.side_effect = Exception("Redis error")

        query_embedding = np.array([1.0, 2.0, 3.0], dtype=np.float32)

        success = await cache_service.cache_result("test query", query_embedding, {})

        assert success is False


class TestFindSimilarQuery:
    """Tests for _find_similar_query method"""

    @pytest.mark.asyncio
    async def test_no_cached_embeddings(self, cache_service, mock_redis):
        """Test when no embeddings in cache"""
        mock_redis.zrange.return_value = []

        query_embedding = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = await cache_service._find_similar_query(query_embedding)

        assert result is None

    @pytest.mark.asyncio
    async def test_similar_found_above_threshold(self, cache_service, mock_redis):
        """Test finding similar embedding above threshold"""
        mock_redis.zrange.return_value = [b"embedding:test1"]

        # Create similar embedding
        cached_embedding = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        mock_redis.get.side_effect = [
            cached_embedding.tobytes(),
            json.dumps({"query": "similar", "result": {"data": "test"}}),
        ]

        query_embedding = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = await cache_service._find_similar_query(query_embedding)

        assert result is not None
        assert result["similarity"] >= 0.95

    @pytest.mark.asyncio
    async def test_no_similar_below_threshold(self, cache_service, mock_redis):
        """Test no match when below threshold"""
        mock_redis.zrange.return_value = [b"embedding:test1"]

        # Create very different embedding
        cached_embedding = np.array([-1.0, -2.0, -3.0], dtype=np.float32)
        mock_redis.get.return_value = cached_embedding.tobytes()

        query_embedding = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = await cache_service._find_similar_query(query_embedding)

        assert result is None

    @pytest.mark.asyncio
    async def test_missing_embedding_skipped(self, cache_service, mock_redis):
        """Test missing embeddings are skipped"""
        mock_redis.zrange.return_value = [b"embedding:test1", b"embedding:test2"]
        mock_redis.get.return_value = None  # Missing embedding

        query_embedding = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = await cache_service._find_similar_query(query_embedding)

        assert result is None

    @pytest.mark.asyncio
    async def test_error_handling(self, cache_service, mock_redis):
        """Test error handling"""
        mock_redis.zrange.side_effect = Exception("Redis error")

        query_embedding = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = await cache_service._find_similar_query(query_embedding)

        assert result is None


class TestCosineSimilarity:
    """Tests for _cosine_similarity method"""

    def test_identical_vectors(self, cache_service):
        """Test similarity of identical vectors"""
        from services.semantic_cache import SemanticCache

        vec = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        similarity = SemanticCache._cosine_similarity(vec, vec)

        assert abs(similarity - 1.0) < 0.0001

    def test_orthogonal_vectors(self, cache_service):
        """Test similarity of orthogonal vectors"""
        from services.semantic_cache import SemanticCache

        vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        similarity = SemanticCache._cosine_similarity(vec1, vec2)

        assert abs(similarity) < 0.0001

    def test_opposite_vectors(self, cache_service):
        """Test similarity of opposite vectors"""
        from services.semantic_cache import SemanticCache

        vec1 = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        vec2 = np.array([-1.0, -2.0, -3.0], dtype=np.float32)
        similarity = SemanticCache._cosine_similarity(vec1, vec2)

        assert abs(similarity + 1.0) < 0.0001


class TestCacheKeys:
    """Tests for cache key generation"""

    def test_get_cache_key(self, cache_service):
        """Test cache key generation"""
        key1 = cache_service._get_cache_key("test query")
        key2 = cache_service._get_cache_key("TEST QUERY")  # Case insensitive
        key3 = cache_service._get_cache_key("  test query  ")  # Strips whitespace

        assert key1 == key2 == key3
        assert key1.startswith("semantic_cache:")

    def test_get_embedding_key(self, cache_service):
        """Test embedding key generation"""
        key = cache_service._get_embedding_key("test query")

        assert key.startswith("embedding:")


class TestEnforceCacheSize:
    """Tests for _enforce_cache_size method"""

    @pytest.mark.asyncio
    async def test_under_limit_no_eviction(self, cache_service, mock_redis):
        """Test no eviction when under limit"""
        mock_redis.zcard.return_value = 500  # Under max_cache_size

        await cache_service._enforce_cache_size()

        mock_redis.zrange.assert_not_called()

    @pytest.mark.asyncio
    async def test_over_limit_eviction(self, cache_service, mock_redis):
        """Test eviction when over limit"""
        cache_service.max_cache_size = 100
        mock_redis.zcard.return_value = 110
        mock_redis.zrange.return_value = [b"embedding:key1", b"embedding:key2"]
        mock_redis.delete = AsyncMock()
        mock_redis.zrem = AsyncMock()

        await cache_service._enforce_cache_size()

        mock_redis.zrange.assert_called_once()
        assert mock_redis.delete.call_count >= 2
        assert mock_redis.zrem.call_count >= 1

    @pytest.mark.asyncio
    async def test_eviction_error_handling(self, cache_service, mock_redis):
        """Test eviction error handling"""
        mock_redis.zcard.side_effect = Exception("Redis error")

        # Should not raise
        await cache_service._enforce_cache_size()


class TestGetCacheStats:
    """Tests for get_cache_stats method"""

    @pytest.mark.asyncio
    async def test_get_stats_success(self, cache_service, mock_redis):
        """Test successful stats retrieval"""
        mock_redis.zcard.return_value = 500

        stats = await cache_service.get_cache_stats()

        assert stats["cache_size"] == 500
        assert stats["max_cache_size"] == 1000
        assert "utilization" in stats
        assert stats["similarity_threshold"] == 0.95

    @pytest.mark.asyncio
    async def test_get_stats_error(self, cache_service, mock_redis):
        """Test stats error handling"""
        mock_redis.zcard.side_effect = Exception("Redis error")

        stats = await cache_service.get_cache_stats()

        assert stats == {}


class TestClearCache:
    """Tests for clear_cache method"""

    @pytest.mark.asyncio
    async def test_clear_success(self, cache_service, mock_redis):
        """Test successful cache clear"""
        mock_redis.keys.side_effect = [
            [b"semantic_cache:key1", b"semantic_cache:key2"],
            [b"embedding:key1", b"embedding:key2"],
        ]
        mock_redis.delete = AsyncMock()

        await cache_service.clear_cache()

        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_empty_cache(self, cache_service, mock_redis):
        """Test clearing empty cache"""
        mock_redis.keys.return_value = []
        mock_redis.delete = AsyncMock()

        await cache_service.clear_cache()

        mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_error_handling(self, cache_service, mock_redis):
        """Test clear error handling"""
        mock_redis.keys.side_effect = Exception("Redis error")

        # Should not raise
        await cache_service.clear_cache()


class TestGetSemanticCache:
    """Tests for get_semantic_cache function"""

    def test_creates_new_instance(self, mock_redis):
        """Test get_semantic_cache creates new instance"""
        import services.semantic_cache as module

        # Reset singleton
        module._semantic_cache = None

        cache = module.get_semantic_cache(mock_redis)

        assert cache is not None
        assert isinstance(cache, module.SemanticCache)

    def test_returns_singleton(self, mock_redis):
        """Test get_semantic_cache returns singleton"""
        import services.semantic_cache as module

        # Reset singleton
        module._semantic_cache = None

        cache1 = module.get_semantic_cache(mock_redis)
        cache2 = module.get_semantic_cache(mock_redis)

        assert cache1 is cache2
