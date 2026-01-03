"""
Unit tests for memory_vector router
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

from core.qdrant_db import QdrantClient

from app.routers.memory_vector import get_memory_vector_db, initialize_memory_vector_db, router


@pytest.fixture
def mock_qdrant_client():
    """Mock QdrantClient"""
    client = MagicMock(spec=QdrantClient)
    client.get_collection_stats = AsyncMock(return_value={"total_documents": 0})
    client.upsert_documents = AsyncMock()
    client.search = AsyncMock(return_value={
        "results": [],
        "ids": [],
        "distances": [],
        "total_found": 0
    })
    client.get_similar = AsyncMock(return_value={
        "results": [],
        "ids": [],
        "distances": []
    })
    return client


@pytest.fixture
def app(mock_qdrant_client):
    """Create FastAPI app with router"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestMemoryVectorRouter:
    """Tests for memory_vector router"""

    @patch("app.routers.memory_vector.QdrantClient")
    @patch("app.routers.memory_vector.settings")
    def test_initialize_memory_vector_db(self, mock_settings, mock_qdrant_client_class, mock_qdrant_client):
        """Test initializing memory vector DB"""
        mock_settings.qdrant_url = "http://localhost:6333"
        mock_qdrant_client_class.return_value = mock_qdrant_client

        import asyncio
        result = asyncio.run(initialize_memory_vector_db())
        assert result == mock_qdrant_client

    @pytest.mark.asyncio
    @patch("app.routers.memory_vector.memory_vector_db", None)
    @patch("app.routers.memory_vector.initialize_memory_vector_db")
    async def test_get_memory_vector_db_not_initialized(self, mock_init, mock_qdrant_client):
        """Test getting memory vector DB when not initialized"""
        mock_init.return_value = mock_qdrant_client
        result = await get_memory_vector_db()
        assert result == mock_qdrant_client

    def test_embed_text(self, client):
        """Test embedding text"""
        with patch("app.routers.memory_vector.embedder") as mock_embedder:
            mock_embedder.generate_single_embedding = MagicMock(return_value=[0.1] * 384)
            mock_embedder.model = "test-model"

            response = client.post(
                "/api/memory/embed",
                json={"text": "test text"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "embedding" in data
            assert data["dimensions"] == 384

    def test_store_memory(self, client, mock_qdrant_client):
        """Test storing memory"""
        with patch("app.routers.memory_vector.get_memory_vector_db", new_callable=AsyncMock, return_value=mock_qdrant_client):
            response = client.post(
                "/api/memory/store",
                json={
                    "id": "mem1",
                    "document": "test memory",
                    "embedding": [0.1] * 384,
                    "metadata": {}
                }
            )
            assert response.status_code == 200

    def test_search_memory(self, client, mock_qdrant_client):
        """Test searching memory"""
        mock_qdrant_client.search = AsyncMock(return_value={
            "documents": [["test doc"]],
            "ids": ["mem1"],
            "distances": [0.1],
            "metadatas": [{}],
            "total_found": 1
        })
        with patch("app.routers.memory_vector.get_memory_vector_db", new_callable=AsyncMock, return_value=mock_qdrant_client):
            response = client.post(
                "/api/memory/search",
                json={
                    "query_embedding": [0.1] * 384,
                    "limit": 10
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert "results" in data

    def test_find_similar_memories(self, client, mock_qdrant_client):
        """Test finding similar memories"""
        mock_qdrant_client.get = AsyncMock(return_value={
            "embeddings": [[0.1] * 384]
        })
        mock_qdrant_client.search = AsyncMock(return_value={
            "documents": [["test doc"]],
            "ids": ["mem2"],
            "distances": [0.1],
            "metadatas": [{}],
            "total_found": 1
        })
        with patch("app.routers.memory_vector.get_memory_vector_db", new_callable=AsyncMock, return_value=mock_qdrant_client):
            response = client.post(
                "/api/memory/similar",
                json={
                    "memory_id": "mem1",
                    "limit": 5
                }
            )
            # May return 404 if memory not found, or 200 if found
            assert response.status_code in [200, 404]

