"""
Unit Tests for Performance Router - 95% Coverage Target
Tests all endpoints in backend/app/routers/performance.py directly
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test Performance Metrics Endpoint
# ============================================================================


class TestGetPerformanceMetrics:
    """Test suite for GET /api/performance/metrics"""

    @pytest.mark.asyncio
    async def test_get_metrics_success(self):
        """Test successful metrics retrieval"""
        with patch("app.routers.performance.perf_monitor") as mock_monitor:
            mock_monitor.get_metrics = MagicMock(
                return_value={
                    "request_count": 100,
                    "total_time": 50.0,
                    "avg_response_time": 0.5,
                    "cache_hits": 60,
                    "cache_misses": 40,
                    "cache_hit_rate": 0.6,
                    "requests_per_second": 2.0,
                }
            )

            from app.routers.performance import get_performance_metrics

            result = await get_performance_metrics()

            assert result["success"] is True
            assert "metrics" in result
            assert result["metrics"]["request_count"] == 100
            assert result["metrics"]["cache_hit_rate"] == 0.6
            mock_monitor.get_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_metrics_empty(self):
        """Test metrics retrieval with empty/default values"""
        with patch("app.routers.performance.perf_monitor") as mock_monitor:
            mock_monitor.get_metrics = MagicMock(
                return_value={
                    "request_count": 0,
                    "total_time": 0,
                    "avg_response_time": 0,
                    "cache_hits": 0,
                    "cache_misses": 0,
                    "cache_hit_rate": 0,
                    "requests_per_second": 0,
                }
            )

            from app.routers.performance import get_performance_metrics

            result = await get_performance_metrics()

            assert result["success"] is True
            assert result["metrics"]["request_count"] == 0

    @pytest.mark.asyncio
    async def test_get_metrics_error(self):
        """Test metrics retrieval error handling"""
        with patch("app.routers.performance.perf_monitor") as mock_monitor:
            mock_monitor.get_metrics = MagicMock(side_effect=Exception("Monitor error"))

            from fastapi import HTTPException

            from app.routers.performance import get_performance_metrics

            with pytest.raises(HTTPException) as exc_info:
                await get_performance_metrics()

            assert exc_info.value.status_code == 500
            assert "Monitor error" in str(exc_info.value.detail)


# ============================================================================
# Test Clear All Caches Endpoint
# ============================================================================


class TestClearCaches:
    """Test suite for POST /api/performance/clear-cache"""

    @pytest.mark.asyncio
    async def test_clear_all_caches_success(self):
        """Test successful clearing of all caches"""
        with patch("app.routers.performance.embedding_cache") as mock_embedding:
            with patch("app.routers.performance.search_cache") as mock_search:
                mock_embedding.clear = AsyncMock()
                mock_search.clear = AsyncMock()

                from app.routers.performance import clear_caches

                result = await clear_caches()

                assert result["success"] is True
                assert result["status"] == "caches_cleared"
                mock_embedding.clear.assert_called_once()
                mock_search.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_all_caches_embedding_error(self):
        """Test error when clearing embedding cache fails"""
        with patch("app.routers.performance.embedding_cache") as mock_embedding:
            mock_embedding.clear = AsyncMock(side_effect=Exception("Embedding cache error"))

            from fastapi import HTTPException

            from app.routers.performance import clear_caches

            with pytest.raises(HTTPException) as exc_info:
                await clear_caches()

            assert exc_info.value.status_code == 500
            assert "Embedding cache error" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_clear_all_caches_search_error(self):
        """Test error when clearing search cache fails"""
        with patch("app.routers.performance.embedding_cache") as mock_embedding:
            with patch("app.routers.performance.search_cache") as mock_search:
                mock_embedding.clear = AsyncMock()
                mock_search.clear = AsyncMock(side_effect=Exception("Search cache error"))

                from fastapi import HTTPException

                from app.routers.performance import clear_caches

                with pytest.raises(HTTPException) as exc_info:
                    await clear_caches()

                assert exc_info.value.status_code == 500
                assert "Search cache error" in str(exc_info.value.detail)


# ============================================================================
# Test Clear Embedding Cache Endpoint
# ============================================================================


class TestClearEmbeddingCache:
    """Test suite for POST /api/performance/clear-cache/embedding"""

    @pytest.mark.asyncio
    async def test_clear_embedding_cache_success(self):
        """Test successful clearing of embedding cache"""
        with patch("app.routers.performance.embedding_cache") as mock_embedding:
            mock_embedding.clear = AsyncMock()

            from app.routers.performance import clear_embedding_cache

            result = await clear_embedding_cache()

            assert result["success"] is True
            assert result["status"] == "embedding_cache_cleared"
            mock_embedding.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_embedding_cache_error(self):
        """Test error handling when clearing embedding cache fails"""
        with patch("app.routers.performance.embedding_cache") as mock_embedding:
            mock_embedding.clear = AsyncMock(side_effect=Exception("Clear failed"))

            from fastapi import HTTPException

            from app.routers.performance import clear_embedding_cache

            with pytest.raises(HTTPException) as exc_info:
                await clear_embedding_cache()

            assert exc_info.value.status_code == 500
            assert "Clear failed" in str(exc_info.value.detail)


# ============================================================================
# Test Clear Search Cache Endpoint
# ============================================================================


class TestClearSearchCache:
    """Test suite for POST /api/performance/clear-cache/search"""

    @pytest.mark.asyncio
    async def test_clear_search_cache_success(self):
        """Test successful clearing of search cache"""
        with patch("app.routers.performance.search_cache") as mock_search:
            mock_search.clear = AsyncMock()

            from app.routers.performance import clear_search_cache

            result = await clear_search_cache()

            assert result["success"] is True
            assert result["status"] == "search_cache_cleared"
            mock_search.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_search_cache_error(self):
        """Test error handling when clearing search cache fails"""
        with patch("app.routers.performance.search_cache") as mock_search:
            mock_search.clear = AsyncMock(side_effect=Exception("Search clear failed"))

            from fastapi import HTTPException

            from app.routers.performance import clear_search_cache

            with pytest.raises(HTTPException) as exc_info:
                await clear_search_cache()

            assert exc_info.value.status_code == 500
            assert "Search clear failed" in str(exc_info.value.detail)


# ============================================================================
# Test Cache Stats Endpoint
# ============================================================================


class TestGetCacheStats:
    """Test suite for GET /api/performance/cache/stats"""

    @pytest.mark.asyncio
    async def test_get_cache_stats_success(self):
        """Test successful cache stats retrieval"""
        with patch("app.routers.performance.embedding_cache") as mock_embedding:
            with patch("app.routers.performance.search_cache") as mock_search:
                mock_embedding.cache = {"key1": "value1", "key2": "value2"}
                mock_embedding.hits = 10
                mock_embedding.misses = 5

                mock_search.cache = {"key3": "value3"}
                mock_search.hits = 20
                mock_search.misses = 10

                from app.routers.performance import get_cache_stats

                result = await get_cache_stats()

                assert result["success"] is True
                assert "embedding_cache" in result
                assert "search_cache" in result
                assert result["embedding_cache"]["size"] == 2
                assert result["embedding_cache"]["hits"] == 10
                assert result["embedding_cache"]["misses"] == 5
                assert result["search_cache"]["size"] == 1
                assert result["search_cache"]["hits"] == 20
                assert result["search_cache"]["misses"] == 10

    @pytest.mark.asyncio
    async def test_get_cache_stats_no_cache_attribute(self):
        """Test cache stats when cache attribute doesn't exist"""
        with patch("app.routers.performance.embedding_cache") as mock_embedding:
            with patch("app.routers.performance.search_cache") as mock_search:
                # Configure spec to not have cache attribute
                del mock_embedding.cache
                del mock_search.cache

                mock_embedding.hits = 0
                mock_embedding.misses = 0
                mock_search.hits = 0
                mock_search.misses = 0

                from app.routers.performance import get_cache_stats

                result = await get_cache_stats()

                assert result["success"] is True
                assert result["embedding_cache"]["size"] == 0
                assert result["search_cache"]["size"] == 0

    @pytest.mark.asyncio
    async def test_get_cache_stats_no_hits_attribute(self):
        """Test cache stats when hits/misses attributes don't exist"""
        with patch("app.routers.performance.embedding_cache") as mock_embedding:
            with patch("app.routers.performance.search_cache") as mock_search:
                mock_embedding.cache = {}
                mock_search.cache = {}

                # Remove hits/misses attributes
                del mock_embedding.hits
                del mock_embedding.misses
                del mock_search.hits
                del mock_search.misses

                from app.routers.performance import get_cache_stats

                result = await get_cache_stats()

                assert result["success"] is True
                # getattr should return 0 for missing attributes
                assert result["embedding_cache"]["hits"] == 0
                assert result["embedding_cache"]["misses"] == 0

    @pytest.mark.asyncio
    async def test_get_cache_stats_error(self):
        """Test cache stats retrieval error handling"""
        with patch("app.routers.performance.embedding_cache") as mock_embedding:
            # Make hasattr raise an exception
            type(mock_embedding).cache = property(
                lambda self: (_ for _ in ()).throw(Exception("Cache access error"))
            )

            from fastapi import HTTPException

            from app.routers.performance import get_cache_stats

            with pytest.raises(HTTPException) as exc_info:
                await get_cache_stats()

            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_get_cache_stats_large_cache(self):
        """Test cache stats with large cache sizes"""
        with patch("app.routers.performance.embedding_cache") as mock_embedding:
            with patch("app.routers.performance.search_cache") as mock_search:
                # Simulate large cache
                mock_embedding.cache = {f"key_{i}": f"value_{i}" for i in range(1000)}
                mock_embedding.hits = 10000
                mock_embedding.misses = 500

                mock_search.cache = {f"search_{i}": f"result_{i}" for i in range(500)}
                mock_search.hits = 5000
                mock_search.misses = 250

                from app.routers.performance import get_cache_stats

                result = await get_cache_stats()

                assert result["success"] is True
                assert result["embedding_cache"]["size"] == 1000
                assert result["search_cache"]["size"] == 500
                assert result["embedding_cache"]["hits"] == 10000


# ============================================================================
# Test Router Configuration
# ============================================================================


class TestRouterConfiguration:
    """Test router prefix and tags configuration"""

    def test_router_prefix(self):
        """Test that router has correct prefix"""
        from app.routers.performance import router

        assert router.prefix == "/api/performance"

    def test_router_tags(self):
        """Test that router has correct tags"""
        from app.routers.performance import router

        assert "performance" in router.tags
