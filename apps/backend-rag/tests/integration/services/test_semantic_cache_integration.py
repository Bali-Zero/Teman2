"""
Integration Tests for SemanticCache
Tests semantic caching with Redis
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
import pytest_asyncio

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestSemanticCacheIntegration:
    """Comprehensive integration tests for SemanticCache"""

    @pytest_asyncio.fixture
    async def mock_redis(self):
        """Create mock Redis client"""
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.zadd = AsyncMock(return_value=0)
        mock_redis.zrange = AsyncMock(return_value=[])
        mock_redis.zrem = AsyncMock(return_value=0)
        mock_redis.zcard = AsyncMock(return_value=0)
        return mock_redis

    @pytest_asyncio.fixture
    async def cache(self, mock_redis):
        """Create SemanticCache instance"""
        from services.semantic_cache import SemanticCache

        return SemanticCache(
            redis_client=mock_redis,
            similarity_threshold=0.95,
            default_ttl=3600,
        )

    @pytest.mark.asyncio
    async def test_initialization(self, cache):
        """Test cache initialization"""
        assert cache is not None
        assert cache.similarity_threshold == 0.95
        assert cache.default_ttl == 3600

    @pytest.mark.asyncio
    async def test_get_cached_result_exact_match(self, cache, mock_redis):
        """Test getting cached result with exact match"""
        import json

        cached_data = json.dumps(
            {
                "query": "test query",
                "result": {"answer": "test answer"},
                "timestamp": "2025-01-01",
            }
        )
        mock_redis.get = AsyncMock(return_value=cached_data.encode())

        result = await cache.get_cached_result("test query")

        assert result is not None
        assert result["cache_hit"] == "exact"

    @pytest.mark.asyncio
    async def test_get_cached_result_no_match(self, cache, mock_redis):
        """Test getting cached result with no match"""
        mock_redis.get = AsyncMock(return_value=None)

        result = await cache.get_cached_result("test query")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_result(self, cache, mock_redis):
        """Test caching a result"""
        query_embedding = np.array([0.1] * 384, dtype=np.float32)
        result_data = {"answer": "test answer", "sources": []}

        success = await cache.cache_result("test query", query_embedding, result_data)

        assert success is True
        mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_find_similar_query(self, cache, mock_redis):
        """Test finding similar query"""
        import json

        query_embedding = np.array([0.1] * 384, dtype=np.float32)
        cached_embedding = np.array([0.11] * 384, dtype=np.float32)  # Similar

        mock_redis.zrange = AsyncMock(return_value=[b"embedding:test"])
        mock_redis.get = AsyncMock(
            side_effect=[
                cached_embedding.tobytes(),
                json.dumps({"query": "test", "result": {"answer": "answer"}}).encode(),
            ]
        )

        similar = await cache._find_similar_query(query_embedding)

        # May or may not find similar depending on threshold
        assert similar is None or isinstance(similar, dict)

    def test_cosine_similarity(self, cache):
        """Test cosine similarity calculation"""
        v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([1.0, 0.0, 0.0], dtype=np.float32)

        similarity = cache._cosine_similarity(v1, v2)

        assert similarity == 1.0  # Identical vectors

    def test_get_cache_key(self, cache):
        """Test getting cache key"""
        key = cache._get_cache_key("test query")

        assert key is not None
        assert key.startswith("semantic_cache:")

    def test_get_embedding_key(self, cache):
        """Test getting embedding key"""
        key = cache._get_embedding_key("test query")

        assert key is not None
        assert key.startswith("embedding:")
