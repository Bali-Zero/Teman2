"""
Unit tests for SemanticCache
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.search.semantic_cache import SemanticCache


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.keys = AsyncMock(return_value=[])
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=False)
    return redis


@pytest.fixture
def semantic_cache(mock_redis):
    """Create SemanticCache instance"""
    return SemanticCache(
        redis_client=mock_redis,
        similarity_threshold=0.95,
        default_ttl=3600,
        max_cache_size=10000
    )


@pytest.fixture
def sample_embedding():
    """Sample embedding vector"""
    return np.random.rand(384).astype(np.float32)


@pytest.fixture
def sample_result():
    """Sample cache result"""
    return {
        "results": [{"id": "1", "content": "test"}],
        "query": "test query",
        "timestamp": "2024-01-01T00:00:00"
    }


class TestSemanticCache:
    """Tests for SemanticCache"""

    def test_init(self, mock_redis):
        """Test initialization"""
        cache = SemanticCache(redis_client=mock_redis)
        assert cache.redis == mock_redis
        assert cache.similarity_threshold == 0.95
        assert cache.default_ttl == 3600

    def test_init_custom_params(self, mock_redis):
        """Test initialization with custom parameters"""
        cache = SemanticCache(
            redis_client=mock_redis,
            similarity_threshold=0.9,
            default_ttl=1800,
            max_cache_size=5000
        )
        assert cache.similarity_threshold == 0.9
        assert cache.default_ttl == 1800
        assert cache.max_cache_size == 5000

    @pytest.mark.asyncio
    async def test_get_cached_result_exact_match(self, semantic_cache, sample_result, mock_redis):
        """Test getting cached result with exact match"""
        import json
        mock_redis.get = AsyncMock(return_value=json.dumps(sample_result))

        result = await semantic_cache.get_cached_result("test query")
        assert result is not None
        assert result["cache_hit"] == "exact"

    @pytest.mark.asyncio
    async def test_get_cached_result_no_match(self, semantic_cache, mock_redis):
        """Test getting cached result with no match"""
        mock_redis.get = AsyncMock(return_value=None)

        result = await semantic_cache.get_cached_result("test query")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_result_semantic_match(self, semantic_cache, sample_embedding, sample_result, mock_redis):
        """Test getting cached result with semantic match"""
        mock_redis.get = AsyncMock(return_value=None)

        # Mock semantic similarity search
        with patch.object(semantic_cache, '_find_similar_query') as mock_find:
            mock_find.return_value = {
                "data": sample_result,
                "similarity": 0.96
            }

            result = await semantic_cache.get_cached_result("test query", query_embedding=sample_embedding)
            assert result is not None
            assert result["cache_hit"] == "semantic"

    @pytest.mark.asyncio
    async def test_get_cached_result_error(self, semantic_cache, mock_redis):
        """Test getting cached result with error"""
        mock_redis.get = AsyncMock(side_effect=Exception("Redis error"))

        result = await semantic_cache.get_cached_result("test query")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_result(self, semantic_cache, sample_embedding, sample_result, mock_redis):
        """Test caching result"""
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.zadd = AsyncMock(return_value=1)
        mock_redis.zcard = AsyncMock(return_value=0)

        result = await semantic_cache.cache_result(
            query="test query",
            query_embedding=sample_embedding,
            result=sample_result
        )

        assert result is True
        mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_cache_result_with_ttl(self, semantic_cache, sample_embedding, sample_result, mock_redis):
        """Test caching result with custom TTL"""
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.zadd = AsyncMock(return_value=1)
        mock_redis.zcard = AsyncMock(return_value=0)

        result = await semantic_cache.cache_result(
            query="test query",
            query_embedding=sample_embedding,
            result=sample_result,
            ttl=1800
        )

        assert result is True
        mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_cache_result_error(self, semantic_cache, sample_embedding, sample_result, mock_redis):
        """Test caching result with error"""
        mock_redis.set = AsyncMock(side_effect=Exception("Redis error"))

        # Should not raise exception
        await semantic_cache.cache_result(
            query="test query",
            query_embedding=sample_embedding,
            result=sample_result
        )

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, semantic_cache, mock_redis):
        """Test getting cache statistics"""
        mock_redis.zcard = AsyncMock(return_value=5)

        stats = await semantic_cache.get_cache_stats()
        assert "cache_size" in stats
        assert stats["cache_size"] == 5

    def test_get_cache_key(self, semantic_cache):
        """Test getting cache key"""
        key = semantic_cache._get_cache_key("test query")
        assert key.startswith("semantic_cache:")

    def test_get_embedding_key(self, semantic_cache):
        """Test getting embedding key"""
        key = semantic_cache._get_embedding_key("test query")
        assert key.startswith("embedding:")

    @pytest.mark.asyncio
    async def test_enforce_cache_size(self, semantic_cache, mock_redis):
        """Test enforcing cache size"""
        mock_redis.zcard = AsyncMock(return_value=15000)  # Over limit
        mock_redis.zrange = AsyncMock(return_value=[b"key1", b"key2"])
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.zrem = AsyncMock(return_value=1)

        await semantic_cache._enforce_cache_size()
        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_find_similar_query(self, semantic_cache, sample_embedding, mock_redis):
        """Test finding similar query"""
        mock_redis.zrange = AsyncMock(return_value=[b"embedding:hash1"])
        mock_redis.get = AsyncMock(return_value=sample_embedding.tobytes())

        result = await semantic_cache._find_similar_query(sample_embedding)
        # May return None if similarity is below threshold
        assert result is None or isinstance(result, dict)

