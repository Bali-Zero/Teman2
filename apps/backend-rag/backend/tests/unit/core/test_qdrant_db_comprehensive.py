"""
Unit tests for QdrantClient
Target: 100% coverage
Composer: 3
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.qdrant_db import QdrantClient


@pytest.fixture
def qdrant_client():
    """Create QdrantClient instance"""
    with patch("httpx.AsyncClient"):
        return QdrantClient(
            qdrant_url="http://localhost:6333",
            collection_name="test_collection",
            api_key=None
        )


class TestQdrantClient:
    """Tests for QdrantClient"""

    def test_init(self):
        """Test initialization"""
        with patch("httpx.AsyncClient"):
            client = QdrantClient(
                qdrant_url="http://localhost:6333",
                collection_name="test_collection"
            )
            assert client.qdrant_url == "http://localhost:6333"
            assert client.collection_name == "test_collection"

    @pytest.mark.asyncio
    async def test_search(self, qdrant_client):
        """Test search operation"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={"result": []})
        mock_response.raise_for_status = MagicMock()
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        
        with patch.object(qdrant_client, '_get_client', return_value=mock_client):
            result = await qdrant_client.search(
                query_embedding=[0.1] * 1536,
                limit=5
            )
            assert result is not None
            assert "ids" in result
            assert "documents" in result

    @pytest.mark.asyncio
    async def test_upsert_documents(self, qdrant_client):
        """Test upsert_documents operation"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        
        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        
        with patch.object(qdrant_client, '_get_client', return_value=mock_client):
            result = await qdrant_client.upsert_documents(
                chunks=["test chunk"],
                embeddings=[[0.1] * 1536],
                metadatas=[{"test": "metadata"}]
            )
            assert result is not None
            assert "success" in result or "documents_added" in result

    @pytest.mark.asyncio
    async def test_close(self, qdrant_client):
        """Test close operation"""
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        
        qdrant_client._http_client = mock_client
        
        await qdrant_client.close()
        mock_client.aclose.assert_called_once()
        assert qdrant_client._http_client is None

