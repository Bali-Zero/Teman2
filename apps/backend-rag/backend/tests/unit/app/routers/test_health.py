"""
Unit tests for health router
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

from app.routers.health import get_qdrant_stats, router


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


class TestHealthRouter:
    """Tests for health router"""

    def test_health_check_initializing(self, app, client):
        """Test health check when service is initializing"""
        # No search_service in app.state
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "initializing"

    def test_health_check_ready(self, app, client):
        """Test health check when service is ready"""
        mock_search_service = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.model = "test-model"
        mock_embedder.dimensions = 384
        mock_search_service.embedder = mock_embedder
        app.state.search_service = mock_search_service

        with patch("app.routers.health.get_qdrant_stats") as mock_stats:
            mock_stats.return_value = AsyncMock(return_value={"collections": 5, "total_documents": 1000})

            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ["healthy", "degraded"]

    def test_health_check_with_trailing_slash(self, app, client):
        """Test health check with trailing slash"""
        response = client.get("/health/")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_qdrant_stats_success(self):
        """Test getting Qdrant stats successfully"""
        with patch("app.routers.health.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "result": {
                    "collections": [
                        {"name": "collection1"},
                        {"name": "collection2"}
                    ]
                }
            }
            mock_response.raise_for_status = MagicMock()

            mock_coll_response = MagicMock()
            mock_coll_response.json.return_value = {
                "result": {"points_count": 100}
            }
            mock_coll_response.raise_for_status = MagicMock()

            async def get_side_effect(url):
                if url == "/collections":
                    return mock_response
                else:
                    return mock_coll_response

            mock_client.get = AsyncMock(side_effect=get_side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await get_qdrant_stats()
            assert result["collections"] == 2
            assert result["total_documents"] == 200

    @pytest.mark.asyncio
    async def test_get_qdrant_stats_error(self):
        """Test getting Qdrant stats with error"""
        with patch("app.routers.health.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await get_qdrant_stats()
            assert result["collections"] == 0
            assert "error" in result

