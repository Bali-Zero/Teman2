"""
API Tests for Performance Optimizer Router - Coverage 95% Target
Tests all performance optimization endpoints and edge cases

Coverage:
- GET /api/performance/metrics - Get performance metrics
- POST /api/performance/clear-cache - Clear all caches
- POST /api/performance/clear-cache/embedding - Clear embedding cache
- POST /api/performance/clear-cache/search - Clear search cache
- GET /api/performance/cache/stats - Get cache statistics
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
# Test Performance Metrics
# ============================================================================


class TestPerformanceMetrics:
    """Test suite for GET /api/performance/metrics"""

    def test_get_metrics_success(self, authenticated_client):
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

            response = authenticated_client.get("/api/performance/metrics")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "metrics" in data
            assert data["metrics"]["request_count"] == 100

    def test_get_metrics_error(self, authenticated_client):
        """Test metrics retrieval error"""
        with patch("app.routers.performance.perf_monitor") as mock_monitor:
            mock_monitor.get_metrics = MagicMock(side_effect=Exception("Monitor error"))

            response = authenticated_client.get("/api/performance/metrics")

            assert response.status_code == 500


# ============================================================================
# Test Clear Cache
# ============================================================================


class TestClearCache:
    """Test suite for POST /api/performance/clear-cache"""

    def test_clear_all_caches_success(self, authenticated_client):
        """Test successful cache clearing"""
        with patch("app.routers.performance.embedding_cache") as mock_embedding:
            with patch("app.routers.performance.search_cache") as mock_search:
                mock_embedding.clear = AsyncMock()
                mock_search.clear = AsyncMock()

                response = authenticated_client.post("/api/performance/clear-cache")

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["status"] == "caches_cleared"

    def test_clear_all_caches_error(self, authenticated_client):
        """Test cache clearing error"""
        with patch("app.routers.performance.embedding_cache") as mock_embedding:
            mock_embedding.clear = AsyncMock(side_effect=Exception("Cache error"))

            response = authenticated_client.post("/api/performance/clear-cache")

            assert response.status_code == 500

    def test_clear_embedding_cache_success(self, authenticated_client):
        """Test clearing embedding cache only"""
        with patch("app.routers.performance.embedding_cache") as mock_embedding:
            mock_embedding.clear = AsyncMock()

            response = authenticated_client.post("/api/performance/clear-cache/embedding")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "embedding_cache_cleared" in data["status"]

    def test_clear_search_cache_success(self, authenticated_client):
        """Test clearing search cache only"""
        with patch("app.routers.performance.search_cache") as mock_search:
            mock_search.clear = AsyncMock()

            response = authenticated_client.post("/api/performance/clear-cache/search")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "search_cache_cleared" in data["status"]


# ============================================================================
# Test Cache Stats
# ============================================================================


class TestCacheStats:
    """Test suite for GET /api/performance/cache/stats"""

    def test_get_cache_stats_success(self, authenticated_client):
        """Test successful cache stats retrieval"""
        with patch("app.routers.performance.embedding_cache") as mock_embedding:
            with patch("app.routers.performance.search_cache") as mock_search:
                mock_embedding.cache = {"key1": "value1", "key2": "value2"}
                mock_embedding.hits = 10
                mock_embedding.misses = 5

                mock_search.cache = {"key3": "value3"}
                mock_search.hits = 20
                mock_search.misses = 10

                response = authenticated_client.get("/api/performance/cache/stats")

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "embedding_cache" in data
                assert "search_cache" in data
                assert data["embedding_cache"]["size"] == 2
                assert data["search_cache"]["size"] == 1

    def test_get_cache_stats_no_cache_attr(self, authenticated_client):
        """Test cache stats when cache attribute doesn't exist"""
        with patch("app.routers.performance.embedding_cache") as mock_embedding:
            with patch("app.routers.performance.search_cache") as mock_search:
                # Remove cache attribute
                if hasattr(mock_embedding, "cache"):
                    delattr(mock_embedding, "cache")
                if hasattr(mock_search, "cache"):
                    delattr(mock_search, "cache")

                mock_embedding.hits = 0
                mock_embedding.misses = 0
                mock_search.hits = 0
                mock_search.misses = 0

                response = authenticated_client.get("/api/performance/cache/stats")

                assert response.status_code == 200
                data = response.json()
                assert data["embedding_cache"]["size"] == 0
                assert data["search_cache"]["size"] == 0

    def test_get_cache_stats_error(self, authenticated_client):
        """Test cache stats retrieval error"""
        with patch("app.routers.performance.embedding_cache") as mock_embedding:
            # Make hasattr fail
            mock_embedding.__getattr__ = MagicMock(side_effect=Exception("Error"))

            response = authenticated_client.get("/api/performance/cache/stats")

            assert response.status_code == 500
