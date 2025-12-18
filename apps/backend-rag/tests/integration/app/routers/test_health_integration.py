"""
Integration Tests for Health Router
Tests health check endpoints
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture
def app():
    """Create FastAPI app with health router"""
    from fastapi import FastAPI

    from app.routers.health import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.mark.integration
class TestHealthRouterIntegration:
    """Comprehensive integration tests for health router"""

    @pytest.mark.asyncio
    async def test_health_check_basic(self, client):
        """Test basic health check"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "initializing", "degraded"]

    @pytest.mark.asyncio
    async def test_health_check_with_service(self, client):
        """Test health check with search service available"""
        with patch("app.routers.health.get_qdrant_stats", new_callable=AsyncMock) as mock_stats:
            mock_stats.return_value = {"collections": 5, "total_documents": 1000}

            # Mock app.state.search_service
            mock_search_service = MagicMock()
            mock_embedder = MagicMock()
            mock_embedder.model = "test-model"
            mock_embedder.dimensions = 384
            mock_embedder.provider = "sentence-transformers"
            mock_search_service.embedder = mock_embedder

            client.app.state.search_service = mock_search_service

            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ["healthy", "initializing", "degraded"]

    @pytest.mark.asyncio
    async def test_health_check_initializing(self, client):
        """Test health check when service is initializing"""
        # No search_service in app.state
        client.app.state.search_service = None

        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "initializing"

    @pytest.mark.asyncio
    async def test_detailed_health(self, client):
        """Test detailed health check"""
        response = client.get("/health/detailed")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_get_qdrant_stats_success(self):
        """Test getting Qdrant stats successfully"""
        from app.routers.health import get_qdrant_stats

        with patch("app.routers.health.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "result": {
                    "collections": [
                        {"name": "collection1"},
                        {"name": "collection2"},
                    ]
                }
            }
            mock_response.raise_for_status = MagicMock()

            mock_collection_response = MagicMock()
            mock_collection_response.json.return_value = {"result": {"points_count": 100}}
            mock_collection_response.raise_for_status = MagicMock()

            async def mock_get(url):
                if "collections" in url and "/collections/" not in url:
                    return mock_response
                return mock_collection_response

            mock_client_instance = MagicMock()
            mock_client_instance.get = AsyncMock(side_effect=mock_get)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            stats = await get_qdrant_stats()

            assert stats is not None
            assert "collections" in stats
            assert stats["collections"] >= 0

    @pytest.mark.asyncio
    async def test_get_qdrant_stats_error(self):
        """Test getting Qdrant stats with error"""
        from app.routers.health import get_qdrant_stats

        with patch("app.routers.health.httpx.AsyncClient") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.get = AsyncMock(side_effect=Exception("Connection error"))
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            stats = await get_qdrant_stats()

            assert stats is not None
            assert "error" in stats or stats["collections"] == 0
