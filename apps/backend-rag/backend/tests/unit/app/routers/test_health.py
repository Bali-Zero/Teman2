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

import backend.app.routers.health as health_mod
from backend.app.routers.health import get_qdrant_stats, router


@pytest.fixture(autouse=True)
def _reset_qdrant_client():
    # health.py caches a module-level persistent _qdrant_client. An earlier test
    # (e.g. the reachability integration test hitting /health) leaves a real
    # client cached, which _get_qdrant_client() returns ahead of any
    # patch("...health.httpx.AsyncClient") here → mock bypassed. Reset per-test.
    health_mod._qdrant_client = None
    yield
    health_mod._qdrant_client = None


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

        with patch(
            "backend.app.routers.health.get_qdrant_stats",
            new_callable=AsyncMock,
        ) as mock_stats:
            mock_stats.return_value = {"collections": 5, "total_documents": 1000}

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
        with patch("backend.app.routers.health.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "result": {"collections": [{"name": "collection1"}, {"name": "collection2"}]},
            }
            mock_response.raise_for_status = MagicMock()

            mock_coll_response = MagicMock()
            mock_coll_response.json.return_value = {"result": {"points_count": 100}}
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
        with patch("backend.app.routers.health.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            result = await get_qdrant_stats()
            assert result["collections"] == 0
            assert "error" in result

    def test_collections_health_includes_vector_config(self, app, client):
        """2026-07-19 audit lever #11: /health/collections must return real
        per-collection vector_size/distance/status/segments_count, not just a
        bare point count — get_collection_stats' docstring promised this and
        the MCP tool used to proxy a different, always-near-zero endpoint
        instead. Pin the fields here so a regression is caught at this layer,
        not rediscovered by re-auditing the MCP tool by hand."""
        mock_client = AsyncMock()

        collections_resp = MagicMock()
        collections_resp.json.return_value = {
            "result": {"collections": [{"name": "kbli_2025_final"}]},
        }
        collections_resp.raise_for_status = MagicMock()

        detail_resp = MagicMock()
        detail_resp.json.return_value = {
            "result": {
                "points_count": 1563,
                "status": "green",
                "segments_count": 4,
                "config": {"params": {"vectors": {"size": 1536, "distance": "Cosine"}}},
            },
        }
        detail_resp.raise_for_status = MagicMock()

        async def get_side_effect(url):
            return collections_resp if url == "/collections" else detail_resp

        mock_client.get = AsyncMock(side_effect=get_side_effect)
        # AsyncMock().is_closed is itself a truthy auto-attribute, so without
        # this _get_qdrant_client() reads "closed" and silently replaces the
        # mock with a brand-new REAL httpx.AsyncClient (proved live: the first
        # draft of this test hit actual Qdrant Cloud and got real collections).
        mock_client.is_closed = False
        health_mod._qdrant_client = mock_client

        response = client.get("/health/collections")
        assert response.status_code == 200
        entry = response.json()["collections"]["kbli_2025_final"]
        assert entry["live_points"] == 1563
        assert entry["vector_size"] == 1536
        assert entry["distance"] == "Cosine"
        assert entry["status"] == "green"
        assert entry["segments_count"] == 4
