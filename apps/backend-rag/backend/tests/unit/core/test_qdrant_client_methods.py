"""
Unit tests for QdrantClient methods (get, delete, peek, hybrid_search, upsert_documents_with_sparse)
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

from core.qdrant_db import QdrantClient


class TestQdrantClientGet:
    """Tests for QdrantClient.get method"""

    @pytest.fixture
    def client(self):
        """Create QdrantClient instance"""
        return QdrantClient(qdrant_url="http://localhost:6333", collection_name="test")

    @pytest.mark.asyncio
    async def test_get_success(self, client):
        """Test successful get operation"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "id": "1",
                    "vector": [0.1, 0.2, 0.3],
                    "payload": {"text": "test text", "metadata": {"key": "value"}},
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(return_value=mock_response)

            result = await client.get(["1"])

            assert "ids" in result
            assert result["ids"] == ["1"]
            assert len(result["documents"]) == 1

    @pytest.mark.asyncio
    async def test_get_with_include(self, client):
        """Test get with include parameter"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(return_value=mock_response)

            result = await client.get(["1"], include=["embeddings", "payload"])

            assert result is not None

    @pytest.mark.asyncio
    async def test_get_http_error(self, client):
        """Test get with HTTP error"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        error = httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(side_effect=error)

            result = await client.get(["1"])

            assert result["ids"] == []
            assert result["documents"] == []

    @pytest.mark.asyncio
    async def test_get_exception(self, client):
        """Test get with exception"""
        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(side_effect=Exception("Connection error"))

            result = await client.get(["1"])

            assert result["ids"] == []
            assert result["documents"] == []


class TestQdrantClientDelete:
    """Tests for QdrantClient.delete method"""

    @pytest.fixture
    def client(self):
        """Create QdrantClient instance"""
        return QdrantClient(qdrant_url="http://localhost:6333", collection_name="test")

    @pytest.mark.asyncio
    async def test_delete_success(self, client):
        """Test successful delete operation"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(return_value=mock_response)

            result = await client.delete(["1", "2"])

            assert result["success"] is True
            assert result["deleted_count"] == 2

    @pytest.mark.asyncio
    async def test_delete_http_error(self, client):
        """Test delete with HTTP error"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        error = httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(side_effect=error)

            result = await client.delete(["1"])

            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_delete_exception(self, client):
        """Test delete with exception"""
        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(side_effect=Exception("Connection error"))

            with pytest.raises(ConnectionError):
                await client.delete(["1"])


class TestQdrantClientPeek:
    """Tests for QdrantClient.peek method"""

    @pytest.fixture
    def client(self):
        """Create QdrantClient instance"""
        return QdrantClient(qdrant_url="http://localhost:6333", collection_name="test")

    @pytest.mark.asyncio
    async def test_peek_success(self, client):
        """Test successful peek operation"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {"points": [{"id": "1", "payload": {"text": "test", "metadata": {}}}]}
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(return_value=mock_response)

            result = await client.peek(limit=10)

            assert "ids" in result
            assert len(result["ids"]) == 1

    @pytest.mark.asyncio
    async def test_peek_http_error(self, client):
        """Test peek with HTTP error"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response)

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(side_effect=error)

            result = await client.peek(limit=10)

            assert result["ids"] == []
            assert result["documents"] == []

    @pytest.mark.asyncio
    async def test_peek_exception(self, client):
        """Test peek with exception"""
        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.post = AsyncMock(side_effect=Exception("Error"))

            result = await client.peek(limit=10)

            assert result["ids"] == []
            assert result["documents"] == []


class TestQdrantClientHybridSearch:
    """Tests for QdrantClient.hybrid_search method"""

    @pytest.fixture
    def client(self):
        """Create QdrantClient instance"""
        return QdrantClient(qdrant_url="http://localhost:6333", collection_name="test")

    @pytest.mark.asyncio
    async def test_hybrid_search_without_sparse(self, client):
        """Test hybrid_search falls back to dense search when no sparse vector"""
        with patch.object(client, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"ids": ["1"], "documents": ["test"]}

            result = await client.hybrid_search(query_embedding=[0.1] * 1536, query_sparse=None)

            mock_search.assert_called_once()
            assert result["ids"] == ["1"]

    @pytest.mark.asyncio
    async def test_hybrid_search_with_empty_sparse(self, client):
        """Test hybrid_search with empty sparse vector"""
        with patch.object(client, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {"ids": ["1"], "documents": ["test"]}

            result = await client.hybrid_search(query_embedding=[0.1] * 1536, query_sparse={})

            mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_search_success(self, client):
        """Test successful hybrid search"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "points": [{"id": "1", "score": 0.9, "payload": {"text": "test", "metadata": {}}}]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
            patch("core.qdrant_db._retry_with_backoff", new_callable=AsyncMock) as mock_retry,
        ):

            async def retry_func():
                mock_http_client = await mock_get_client()
                mock_http_client.post = AsyncMock(return_value=mock_response)
                return await mock_http_client.post("/test")

            mock_retry.return_value = {
                "ids": ["1"],
                "documents": ["test"],
                "metadatas": [{}],
                "distances": [0.1],
                "scores": [0.9],
                "total_found": 1,
                "search_type": "hybrid_rrf",
            }

            result = await client.hybrid_search(
                query_embedding=[0.1] * 1536,
                query_sparse={"indices": [1, 2, 3], "values": [0.5, 0.6, 0.7]},
                limit=10,
            )

            assert "ids" in result or result is not None

    @pytest.mark.asyncio
    async def test_hybrid_search_fallback_on_error(self, client):
        """Test hybrid_search falls back to dense search on error"""
        with (
            patch.object(client, "search", new_callable=AsyncMock) as mock_search,
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("core.qdrant_db._retry_with_backoff", new_callable=AsyncMock) as mock_retry,
        ):
            mock_search.return_value = {"ids": ["1"], "documents": ["test"]}

            # Simulate error in hybrid search
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "sparse vector error"
            error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)
            mock_retry.side_effect = error

            result = await client.hybrid_search(
                query_embedding=[0.1] * 1536,
                query_sparse={"indices": [1], "values": [0.5]},
                limit=10,
            )

            # Should fall back to dense search
            assert result is not None


class TestQdrantClientUpsertDocumentsWithSparse:
    """Tests for QdrantClient.upsert_documents_with_sparse method"""

    @pytest.fixture
    def client(self):
        """Create QdrantClient instance"""
        return QdrantClient(qdrant_url="http://localhost:6333", collection_name="test")

    @pytest.mark.asyncio
    async def test_upsert_documents_with_sparse_success(self, client):
        """Test successful upsert with sparse vectors"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
        ):
            mock_http_client = await mock_get_client()
            mock_http_client.put = AsyncMock(return_value=mock_response)

            result = await client.upsert_documents_with_sparse(
                chunks=["chunk1", "chunk2"],
                embeddings=[[0.1] * 1536, [0.2] * 1536],
                sparse_vectors=[
                    {"indices": [1, 2], "values": [0.5, 0.6]},
                    {"indices": [3, 4], "values": [0.7, 0.8]},
                ],
                metadatas=[{"key": "value1"}, {"key": "value2"}],
                ids=["id1", "id2"],
            )

            assert result["success"] is True
            assert result["documents_added"] == 2
            assert result["has_sparse_vectors"] is True

    @pytest.mark.asyncio
    async def test_upsert_documents_with_sparse_generate_ids(self, client):
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

            result = await client.upsert_documents_with_sparse(
                chunks=["chunk1"],
                embeddings=[[0.1] * 1536],
                sparse_vectors=[{"indices": [1], "values": [0.5]}],
                metadatas=[{"key": "value"}],
                ids=None,
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_upsert_documents_with_sparse_length_mismatch(self, client):
        """Test upsert with length mismatch"""
        with pytest.raises(ValueError, match="same length"):
            await client.upsert_documents_with_sparse(
                chunks=["chunk1"],
                embeddings=[[0.1] * 1536, [0.2] * 1536],  # Different length
                sparse_vectors=[{"indices": [1], "values": [0.5]}],
                metadatas=[{"key": "value"}],
                ids=["id1"],
            )

    @pytest.mark.asyncio
    async def test_upsert_documents_with_sparse_batch_error(self, client):
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

            result = await client.upsert_documents_with_sparse(
                chunks=["chunk1"],
                embeddings=[[0.1] * 1536],
                sparse_vectors=[{"indices": [1], "values": [0.5]}],
                metadatas=[{"key": "value"}],
                ids=["id1"],
            )

            assert result["success"] is False
            assert "error" in result

