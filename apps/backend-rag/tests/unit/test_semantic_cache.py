"""
Comprehensive tests for SemanticCache
Target: 100% coverage
"""

import json
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest


class TestSemanticCache:
    """Tests for SemanticCache class"""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client"""
        mock = AsyncMock()
        mock.get = AsyncMock()
        mock.setex = AsyncMock()
        mock.zadd = AsyncMock()
        mock.zcard = AsyncMock()
        mock.zrange = AsyncMock()
        mock.delete = AsyncMock()
        mock.zrem = AsyncMock()
        mock.keys = AsyncMock()
        return mock

    @pytest.fixture
    def cache(self, mock_redis):
        """Create SemanticCache instance"""
        from services.semantic_cache import SemanticCache

        return SemanticCache(mock_redis)

    @pytest.fixture
    def cache_custom(self, mock_redis):
        """Create SemanticCache with custom parameters"""
        from services.semantic_cache import SemanticCache

        return SemanticCache(
            mock_redis, similarity_threshold=0.9, default_ttl=7200, max_cache_size=5000
        )

    def test_init_default(self, cache):
        """Test default initialization"""
        assert cache.similarity_threshold == 0.95
        assert cache.default_ttl == 3600
        assert cache.max_cache_size == 10000
        assert cache.cache_prefix == "semantic_cache:"
        assert cache.embedding_prefix == "embedding:"

    def test_init_custom(self, cache_custom):
        """Test custom initialization"""
        assert cache_custom.similarity_threshold == 0.9
        assert cache_custom.default_ttl == 7200
        assert cache_custom.max_cache_size == 5000

    @pytest.mark.asyncio
    async def test_get_cached_result_exact_match(self, cache, mock_redis):
        """Test getting exact match from cache"""
        cached_data = {
            "query": "test query",
            "result": {"answer": "test answer"},
            "timestamp": "2024-01-01T00:00:00",
        }
        mock_redis.get.return_value = json.dumps(cached_data)

        result = await cache.get_cached_result("test query")

        assert result is not None
        assert result["cache_hit"] == "exact"

    @pytest.mark.asyncio
    async def test_get_cached_result_semantic_match(self, cache, mock_redis):
        """Test getting semantic match from cache"""
        mock_redis.get.return_value = None  # No exact match

        query_embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)

        with patch.object(cache, "_find_similar_query", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = {"data": {"result": "semantic result"}, "similarity": 0.98}

            result = await cache.get_cached_result("test query", query_embedding)

        assert result is not None
        assert result["cache_hit"] == "semantic"

    @pytest.mark.asyncio
    async def test_get_cached_result_no_match(self, cache, mock_redis):
        """Test no match found in cache"""
        mock_redis.get.return_value = None

        query_embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)

        with patch.object(cache, "_find_similar_query", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = None

            result = await cache.get_cached_result("test query", query_embedding)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_result_no_embedding(self, cache, mock_redis):
        """Test cache miss without embedding"""
        mock_redis.get.return_value = None

        result = await cache.get_cached_result("test query")  # No embedding provided

        assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_result_exception(self, cache, mock_redis):
        """Test exception handling in get_cached_result"""
        mock_redis.get.side_effect = Exception("Redis error")

        result = await cache.get_cached_result("test query")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_result_success(self, cache, mock_redis):
        """Test successfully caching result"""
        query = "test query"
        query_embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        result = {"answer": "test answer"}

        mock_redis.zcard.return_value = 100  # Under limit

        success = await cache.cache_result(query, query_embedding, result)

        assert success is True
        assert mock_redis.setex.call_count == 2  # Result and embedding

    @pytest.mark.asyncio
    async def test_cache_result_custom_ttl(self, cache, mock_redis):
        """Test caching with custom TTL"""
        query = "test query"
        query_embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        result = {"answer": "test answer"}

        mock_redis.zcard.return_value = 100

        success = await cache.cache_result(query, query_embedding, result, ttl=1800)

        assert success is True

    @pytest.mark.asyncio
    async def test_cache_result_exception(self, cache, mock_redis):
        """Test exception handling in cache_result"""
        query_embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        mock_redis.setex.side_effect = Exception("Redis error")

        success = await cache.cache_result("test", query_embedding, {"result": "test"})

        assert success is False

    @pytest.mark.asyncio
    async def test_find_similar_query_success(self, cache, mock_redis):
        """Test finding similar cached query"""
        cached_embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        query_embedding = np.array([0.1, 0.2, 0.31], dtype=np.float32)  # Very similar

        mock_redis.zrange.return_value = [b"embedding:abc123"]
        mock_redis.get.side_effect = [
            cached_embedding.tobytes(),  # First call: embedding
            json.dumps({"result": "cached result"}),  # Second call: data
        ]

        result = await cache._find_similar_query(query_embedding)

        assert result is not None

    @pytest.mark.asyncio
    async def test_find_similar_query_no_embeddings(self, cache, mock_redis):
        """Test finding similar with no cached embeddings"""
        mock_redis.zrange.return_value = []

        query_embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        result = await cache._find_similar_query(query_embedding)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_similar_query_below_threshold(self, cache, mock_redis):
        """Test finding similar below threshold"""
        cached_embedding = np.array([0.9, 0.9, 0.9], dtype=np.float32)
        query_embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)  # Different

        mock_redis.zrange.return_value = [b"embedding:abc123"]
        mock_redis.get.return_value = cached_embedding.tobytes()

        result = await cache._find_similar_query(query_embedding)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_similar_query_missing_embedding(self, cache, mock_redis):
        """Test handling missing cached embedding"""
        mock_redis.zrange.return_value = [b"embedding:abc123"]
        mock_redis.get.return_value = None  # Embedding not found

        query_embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        result = await cache._find_similar_query(query_embedding)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_similar_query_exception(self, cache, mock_redis):
        """Test exception handling in find_similar"""
        mock_redis.zrange.side_effect = Exception("Redis error")

        query_embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        result = await cache._find_similar_query(query_embedding)

        assert result is None

    def test_cosine_similarity(self, cache):
        """Test cosine similarity calculation"""
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([1.0, 0.0, 0.0])

        similarity = cache._cosine_similarity(vec1, vec2)

        assert similarity == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self, cache):
        """Test cosine similarity for orthogonal vectors"""
        vec1 = np.array([1.0, 0.0, 0.0])
        vec2 = np.array([0.0, 1.0, 0.0])

        similarity = cache._cosine_similarity(vec1, vec2)

        assert similarity == pytest.approx(0.0)

    def test_get_cache_key(self, cache):
        """Test cache key generation"""
        key1 = cache._get_cache_key("test query")
        key2 = cache._get_cache_key("TEST QUERY")  # Same after lowercasing
        key3 = cache._get_cache_key("different query")

        assert key1 == key2  # Case insensitive
        assert key1 != key3
        assert key1.startswith("semantic_cache:")

    def test_get_embedding_key(self, cache):
        """Test embedding key generation"""
        key1 = cache._get_embedding_key("test query")
        key2 = cache._get_embedding_key("TEST QUERY")

        assert key1 == key2
        assert key1.startswith("embedding:")

    @pytest.mark.asyncio
    async def test_enforce_cache_size_under_limit(self, cache, mock_redis):
        """Test cache size under limit"""
        mock_redis.zcard.return_value = 5000  # Under 10000 limit

        await cache._enforce_cache_size()

        mock_redis.zrange.assert_not_called()

    @pytest.mark.asyncio
    async def test_enforce_cache_size_over_limit(self, cache, mock_redis):
        """Test cache size over limit - LRU eviction"""
        mock_redis.zcard.return_value = 10005  # Over limit
        mock_redis.zrange.return_value = [
            b"embedding:old1",
            b"embedding:old2",
            b"embedding:old3",
            b"embedding:old4",
            b"embedding:old5",
        ]

        await cache._enforce_cache_size()

        # Should delete oldest entries
        assert mock_redis.delete.call_count >= 5

    @pytest.mark.asyncio
    async def test_enforce_cache_size_exception(self, cache, mock_redis):
        """Test exception handling in enforce_cache_size"""
        mock_redis.zcard.side_effect = Exception("Redis error")

        await cache._enforce_cache_size()  # Should not raise

    @pytest.mark.asyncio
    async def test_enforce_cache_size_key_decoding(self, cache, mock_redis):
        """Test key decoding in enforcement"""
        mock_redis.zcard.return_value = 10002
        mock_redis.zrange.return_value = [
            "embedding:str_key",  # String key
            b"embedding:bytes_key",  # Bytes key
        ]

        await cache._enforce_cache_size()

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, cache, mock_redis):
        """Test getting cache statistics"""
        mock_redis.zcard.return_value = 500

        stats = await cache.get_cache_stats()

        assert stats["cache_size"] == 500
        assert stats["max_cache_size"] == 10000
        assert stats["utilization"] == "5.0%"
        assert stats["similarity_threshold"] == 0.95
        assert stats["default_ttl"] == 3600

    @pytest.mark.asyncio
    async def test_get_cache_stats_exception(self, cache, mock_redis):
        """Test exception handling in get_cache_stats"""
        mock_redis.zcard.side_effect = Exception("Redis error")

        stats = await cache.get_cache_stats()

        assert stats == {}

    @pytest.mark.asyncio
    async def test_clear_cache(self, cache, mock_redis):
        """Test clearing cache"""
        mock_redis.keys.side_effect = [
            ["semantic_cache:key1", "semantic_cache:key2"],
            ["embedding:key1", "embedding:key2"],
        ]

        await cache.clear_cache()

        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_clear_cache_empty(self, cache, mock_redis):
        """Test clearing empty cache"""
        mock_redis.keys.side_effect = [[], []]

        await cache.clear_cache()

        mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_cache_exception(self, cache, mock_redis):
        """Test exception handling in clear_cache"""
        mock_redis.keys.side_effect = Exception("Redis error")

        await cache.clear_cache()  # Should not raise


class TestGetSemanticCache:
    """Tests for get_semantic_cache function"""

    def test_get_semantic_cache_creates_singleton(self):
        """Test singleton creation"""
        import services.semantic_cache as module

        # Reset singleton
        module._semantic_cache = None

        mock_redis = AsyncMock()
        cache1 = module.get_semantic_cache(mock_redis)
        cache2 = module.get_semantic_cache(mock_redis)

        assert cache1 is cache2

    def test_get_semantic_cache_returns_existing(self):
        """Test returning existing instance"""
        import services.semantic_cache as module

        mock_redis = AsyncMock()
        existing = module.SemanticCache(mock_redis)
        module._semantic_cache = existing

        result = module.get_semantic_cache(mock_redis)

        assert result is existing
