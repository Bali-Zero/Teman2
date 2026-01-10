"""
Unit tests for QdrantClient collection operations (create_collection, upsert_documents)
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.core.qdrant_db import QdrantClient


class TestQdrantClientCreateCollection:
    """Tests for QdrantClient.create_collection method"""

    @pytest.fixture
    def client(self):
        """Create QdrantClient instance"""
        return QdrantClient(qdrant_url="http://localhost:6333", collection_name="test")

    @pytest.mark.asyncio
    async def test_create_collection_basic(self, client):
        """Test creating basic collection"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.put = AsyncMock(return_value=mock_response)

            result = await client.create_collection(vector_size=1536, distance="Cosine")

            assert result is True

    @pytest.mark.asyncio
    async def test_create_collection_with_sparse(self, client):
        """Test creating collection with sparse vectors"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.put = AsyncMock(return_value=mock_response)

            result = await client.create_collection(
                vector_size=1536, distance="Cosine", enable_sparse=True
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_create_collection_with_on_disk_payload(self, client):
        """Test creating collection with on_disk_payload"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.put = AsyncMock(return_value=mock_response)

            result = await client.create_collection(
                vector_size=1536, distance="Cosine", on_disk_payload=True
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_create_collection_http_error(self, client):
        """Test create_collection with HTTP error"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Collection already exists"
        error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.put = AsyncMock(side_effect=error)

            result = await client.create_collection(vector_size=1536)

            assert result is False

    @pytest.mark.asyncio
    async def test_create_collection_exception(self, client):
        """Test create_collection with exception"""
        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.put = AsyncMock(side_effect=Exception("Connection error"))

            result = await client.create_collection(vector_size=1536)

            assert result is False


class TestQdrantClientUpsertDocuments:
    """Tests for QdrantClient.upsert_documents method"""

    @pytest.fixture
    def client(self):
        """Create QdrantClient instance"""
        return QdrantClient(qdrant_url="http://localhost:6333", collection_name="test")

    @pytest.mark.asyncio
    async def test_upsert_documents_success(self, client):
        """Test successful upsert"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
        ):
            mock_http_client = await mock_get_client()
            mock_http_client.put = AsyncMock(return_value=mock_response)

            result = await client.upsert_documents(
                chunks=["chunk1", "chunk2"],
                embeddings=[[0.1] * 1536, [0.2] * 1536],
                metadatas=[{"key": "value1"}, {"key": "value2"}],
                ids=["id1", "id2"],
            )

            assert result["success"] is True
            assert result["documents_added"] == 2

    @pytest.mark.asyncio
    async def test_upsert_documents_generate_ids(self, client):
        """Test upsert generates IDs if not provided"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
            patch("uuid.uuid4", side_effect=lambda: MagicMock(hex="test-uuid")),
        ):
            mock_http_client = await mock_get_client()
            mock_http_client.put = AsyncMock(return_value=mock_response)

            result = await client.upsert_documents(
                chunks=["chunk1"], embeddings=[[0.1] * 1536], metadatas=[{"key": "value"}], ids=None
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_upsert_documents_length_mismatch(self, client):
        """Test upsert with length mismatch"""
        with pytest.raises(ValueError, match="same length"):
            await client.upsert_documents(
                chunks=["chunk1"],
                embeddings=[[0.1] * 1536, [0.2] * 1536],  # Different length
                metadatas=[{"key": "value"}],
                ids=["id1"],
            )

    @pytest.mark.asyncio
    async def test_upsert_documents_batch_processing(self, client):
        """Test upsert with batch processing"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
        ):
            mock_http_client = await mock_get_client()
            mock_http_client.put = AsyncMock(return_value=mock_response)

            # Create 1000 chunks to trigger batching
            chunks = [f"chunk{i}" for i in range(1000)]
            embeddings = [[0.1] * 1536] * 1000
            metadatas = [{"key": f"value{i}"} for i in range(1000)]

            result = await client.upsert_documents(
                chunks=chunks, embeddings=embeddings, metadatas=metadatas, batch_size=500
            )

            assert result["success"] is True
            assert result["documents_added"] == 1000
            # Should have made 2 batch calls (500 + 500)
            assert mock_http_client.put.call_count == 2

    @pytest.mark.asyncio
    async def test_upsert_documents_batch_error(self, client):
        """Test upsert with batch error"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
        ):
            mock_http_client = await mock_get_client()
            mock_http_client.put = AsyncMock(side_effect=error)

            result = await client.upsert_documents(
                chunks=["chunk1"],
                embeddings=[[0.1] * 1536],
                metadatas=[{"key": "value"}],
                ids=["id1"],
            )

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_upsert_documents_partial_success(self, client):
        """Test upsert with partial batch success"""
        mock_response_success = MagicMock()
        mock_response_success.raise_for_status = MagicMock()

        mock_response_error = MagicMock()
        mock_response_error.status_code = 500
        mock_response_error.text = "Server error"
        error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response_error)

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
        ):
            mock_http_client = await mock_get_client()
            mock_http_client.put = AsyncMock(side_effect=[mock_response_success, error])

            result = await client.upsert_documents(
                chunks=["chunk1", "chunk2"],
                embeddings=[[0.1] * 1536, [0.2] * 1536],
                metadatas=[{"key": "value1"}, {"key": "value2"}],
                ids=["id1", "id2"],
                batch_size=1,  # Each chunk is a batch
            )

            assert result["success"] is False
            assert result["documents_added"] == 1  # One batch succeeded
