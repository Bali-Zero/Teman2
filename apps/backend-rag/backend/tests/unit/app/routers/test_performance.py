"""
Unit tests for performance router
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.performance import router


@pytest.fixture
def app():
    """Create FastAPI app with router"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestPerformanceRouter:
    """Tests for performance router"""

    @patch("app.routers.performance.perf_monitor")
    def test_get_performance_metrics(self, mock_monitor, client):
        """Test getting performance metrics"""
        mock_monitor.get_metrics.return_value = {"cpu": 50, "memory": 60}
        
        response = client.get("/api/performance/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "metrics" in data

    @patch("app.routers.performance.perf_monitor")
    def test_get_performance_metrics_error(self, mock_monitor, client):
        """Test getting performance metrics with error"""
        mock_monitor.get_metrics.side_effect = Exception("Monitor error")
        
        response = client.get("/api/performance/metrics")
        assert response.status_code == 500

    @patch("app.routers.performance.embedding_cache")
    @patch("app.routers.performance.search_cache")
    async def test_clear_caches(self, mock_search_cache, mock_embedding_cache, client):
        """Test clearing all caches"""
        mock_embedding_cache.clear = AsyncMock()
        mock_search_cache.clear = AsyncMock()
        
        response = client.post("/api/performance/clear-cache")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "caches_cleared"

    @patch("app.routers.performance.embedding_cache")
    async def test_clear_embedding_cache(self, mock_cache, client):
        """Test clearing embedding cache"""
        mock_cache.clear = AsyncMock()
        
        response = client.post("/api/performance/clear-cache/embedding")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "embedding_cache_cleared"

    @patch("app.routers.performance.search_cache")
    async def test_clear_search_cache(self, mock_cache, client):
        """Test clearing search cache"""
        mock_cache.clear = AsyncMock()
        
        response = client.post("/api/performance/clear-cache/search")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "search_cache_cleared"

    @patch("app.routers.performance.embedding_cache")
    @patch("app.routers.performance.search_cache")
    def test_get_cache_stats(self, mock_search_cache, mock_embedding_cache, client):
        """Test getting cache statistics"""
        mock_embedding_cache.cache = {"key1": "value1"}
        mock_embedding_cache.hits = 10
        mock_embedding_cache.misses = 5
        mock_search_cache.cache = {"key2": "value2"}
        mock_search_cache.hits = 20
        mock_search_cache.misses = 10
        
        response = client.get("/api/performance/cache/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "embedding_cache" in data
        assert "search_cache" in data
        assert data["embedding_cache"]["size"] == 1
        assert data["embedding_cache"]["hits"] == 10

    @patch("app.routers.performance.embedding_cache")
    @patch("app.routers.performance.search_cache")
    def test_get_cache_stats_no_attributes(self, mock_search_cache, mock_embedding_cache, client):
        """Test getting cache stats when attributes don't exist"""
        # Remove cache attribute
        if hasattr(mock_embedding_cache, "cache"):
            delattr(mock_embedding_cache, "cache")
        if hasattr(mock_search_cache, "cache"):
            delattr(mock_search_cache, "cache")
        
        response = client.get("/api/performance/cache/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

