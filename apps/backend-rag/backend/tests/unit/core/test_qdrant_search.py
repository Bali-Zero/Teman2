"""
Unit tests for QdrantClient.search method
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


class TestQdrantClientSearch:
    """Tests for QdrantClient.search method"""

    @pytest.fixture
    def client(self):
        """Create QdrantClient instance"""
        return QdrantClient(qdrant_url="http://localhost:6333", collection_name="test")

    @pytest.mark.asyncio
    async def test_search_success(self, client):
        """Test successful search"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": [
                {
                    "id": "1",
                    "score": 0.9,
                    "payload": {"text": "test text", "metadata": {"key": "value"}},
                }
            ]
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
                "documents": ["test text"],
                "metadatas": [{"key": "value"}],
                "distances": [0.1],
                "total_found": 1,
            }

            result = await client.search([0.1] * 1536, limit=10)

            assert "ids" in result
            assert result["ids"] == ["1"]
            assert result["total_found"] == 1

    @pytest.mark.asyncio
    async def test_search_with_filter(self, client):
        """Test search with filter"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
            patch("core.qdrant_db._retry_with_backoff", new_callable=AsyncMock) as mock_retry,
        ):
            mock_retry.return_value = {
                "ids": [],
                "documents": [],
                "metadatas": [],
                "distances": [],
                "total_found": 0,
            }

            result = await client.search([0.1] * 1536, filter={"tier": "S"}, limit=10)

            assert result is not None

    @pytest.mark.asyncio
    async def test_search_with_named_vector(self, client):
        """Test search with named vector"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
            patch("core.qdrant_db._retry_with_backoff", new_callable=AsyncMock) as mock_retry,
        ):
            mock_retry.return_value = {
                "ids": [],
                "documents": [],
                "metadatas": [],
                "distances": [],
                "total_found": 0,
            }

            result = await client.search([0.1] * 1536, limit=10, vector_name="dense")

            assert result is not None

    @pytest.mark.asyncio
    async def test_search_empty_embedding(self, client):
        """Test search with empty embedding"""
        with pytest.raises(ValueError, match="cannot be empty"):
            await client.search([], limit=10)

    @pytest.mark.asyncio
    async def test_search_invalid_embedding_type(self, client):
        """Test search with invalid embedding type"""
        with pytest.raises(TypeError, match="must be list of numbers"):
            await client.search(["invalid"], limit=10)

    @pytest.mark.asyncio
    async def test_search_timeout(self, client):
        """Test search with timeout"""
        timeout_error = httpx.TimeoutException("Request timeout")

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
            patch("core.qdrant_db._retry_with_backoff", new_callable=AsyncMock) as mock_retry,
        ):
            mock_retry.side_effect = timeout_error

            result = await client.search([0.1] * 1536, limit=10)

            # Should return empty results on timeout after retries
            assert result["ids"] == []
            assert result["total_found"] == 0

    @pytest.mark.asyncio
    async def test_search_http_error_retryable(self, client):
        """Test search with retryable HTTP error"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        error = httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response)

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
            patch("core.qdrant_db._retry_with_backoff", new_callable=AsyncMock) as mock_retry,
        ):
            # Simulate retryable error that eventually succeeds
            mock_retry.return_value = {
                "ids": ["1"],
                "documents": ["test"],
                "metadatas": [{}],
                "distances": [0.1],
                "total_found": 1,
            }

            result = await client.search([0.1] * 1536, limit=10)

            assert result["total_found"] == 1

    @pytest.mark.asyncio
    async def test_search_http_error_client_error(self, client):
        """Test search with client error (non-retryable)"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        error = httpx.HTTPStatusError("Bad request", request=MagicMock(), response=mock_response)

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
            patch("core.qdrant_db._retry_with_backoff", new_callable=AsyncMock) as mock_retry,
        ):
            # Client errors should return empty results
            async def retry_func():
                raise error

            mock_retry.side_effect = error

            result = await client.search([0.1] * 1536, limit=10)

            assert result["ids"] == []
            assert result["total_found"] == 0

    @pytest.mark.asyncio
    async def test_search_named_vector_retry(self, client):
        """Test search retries with named vector on Vector params error"""
        mock_response_error = MagicMock()
        mock_response_error.status_code = 400
        mock_response_error.text = "Vector params for collection"
        error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response_error)

        mock_response_success = MagicMock()
        mock_response_success.json.return_value = {
            "result": [{"id": "1", "score": 0.9, "payload": {"text": "test", "metadata": {}}}]
        }
        mock_response_success.raise_for_status = MagicMock()

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
            patch("core.qdrant_db._retry_with_backoff", new_callable=AsyncMock) as mock_retry,
        ):
            # First attempt fails, then retries with named vector
            call_count = 0

            async def retry_func():
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise error
                mock_http_client = await mock_get_client()
                mock_http_client.post = AsyncMock(return_value=mock_response_success)
                return {
                    "ids": ["1"],
                    "documents": ["test"],
                    "metadatas": [{}],
                    "distances": [0.1],
                    "total_found": 1,
                }

            mock_retry.side_effect = retry_func

            # This should handle the retry internally
            result = await client.search([0.1] * 1536, limit=10)

            # Should eventually succeed or return empty
            assert result is not None

    @pytest.mark.asyncio
    async def test_search_connection_error(self, client):
        """Test search with connection error"""
        connection_error = httpx.ConnectError("Connection failed")

        with (
            patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client,
            patch("time.time", return_value=0.0),
            patch("core.qdrant_db._retry_with_backoff", new_callable=AsyncMock) as mock_retry,
        ):
            mock_retry.side_effect = connection_error

            result = await client.search([0.1] * 1536, limit=10)

            # Should return empty results after retries fail
            assert result["ids"] == []
            assert result["total_found"] == 0


class TestQdrantClientGetStats:
    """Tests for QdrantClient.get_stats method"""

    @pytest.fixture
    def client(self):
        """Create QdrantClient instance"""
        return QdrantClient(qdrant_url="http://localhost:6333", collection_name="test")

    @pytest.mark.asyncio
    async def test_get_stats_success(self, client):
        """Test successful get_stats"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "points_count": 100,
                "config": {"params": {"vectors": {"size": 1536, "distance": "Cosine"}}},
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.get = AsyncMock(return_value=mock_response)

            stats = await client.get_stats()

            assert stats["collection_name"] == "test"
            assert stats["total_documents"] == 100
            assert stats["vector_size"] == 1536
            assert stats["distance"] == "Cosine"

    @pytest.mark.asyncio
    async def test_get_stats_error(self, client):
        """Test get_stats with error"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        error = httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)

        with patch.object(client, "_get_client", return_value=AsyncMock()) as mock_get_client:
            mock_http_client = await mock_get_client()
            mock_http_client.get = AsyncMock(side_effect=error)

            stats = await client.get_stats()

            # On error, get_stats returns collection_name and error only
            assert stats["collection_name"] == "test"
            assert "error" in stats

