"""
Tests for QdrantClient - covers headers, search error paths, get_stats, collection property.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


@pytest.fixture
def qdrant_client():
    """Create a QdrantClient with mocked settings."""
    with patch("backend.core.qdrant_db.settings") as mock_settings:
        mock_settings.qdrant_url = "https://qdrant.test.com"
        mock_settings.qdrant_api_key = "test-api-key"
        mock_settings.qdrant_timeout = 10.0
        from backend.core.qdrant_db import QdrantClient
        client = QdrantClient(
            qdrant_url="https://qdrant.test.com",
            collection_name="test_collection",
            api_key="test-api-key",
            timeout=10.0,
        )
        return client


@pytest.fixture
def qdrant_client_no_key():
    """Create a QdrantClient without API key."""
    with patch("backend.core.qdrant_db.settings") as mock_settings:
        mock_settings.qdrant_url = "https://qdrant.test.com"
        mock_settings.qdrant_api_key = None
        mock_settings.qdrant_timeout = 10.0
        from backend.core.qdrant_db import QdrantClient
        client = QdrantClient(
            qdrant_url="https://qdrant.test.com",
            collection_name="test_collection",
            api_key=None,
            timeout=10.0,
        )
        return client


class TestQdrantDB95Coverage:
    """Coverage tests for QdrantClient."""

    def test_get_headers_without_api_key(self, qdrant_client_no_key):
        """Headers should not include api-key when no API key is set."""
        headers = qdrant_client_no_key._get_headers()
        assert "Content-Type" in headers
        assert headers["Content-Type"] == "application/json"
        assert "api-key" not in headers

    def test_get_headers_with_api_key(self, qdrant_client):
        """Headers should include api-key when API key is set."""
        headers = qdrant_client._get_headers()
        assert headers["api-key"] == "test-api-key"
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_search_timeout(self, qdrant_client):
        """Search should return empty results on timeout (outer except catches all)."""
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=httpx.ReadTimeout("timeout"))
        qdrant_client._http_client = mock_http_client

        with patch("backend.core.qdrant_db.RETRY_BASE_DELAY", 0.001), \
             patch("backend.core.qdrant_db.MAX_RETRIES", 0):
            result = await qdrant_client.search(
                query_embedding=[0.1] * 1536,
                limit=5,
            )
        assert result["total_found"] == 0
        assert result["ids"] == []

    @pytest.mark.asyncio
    async def test_search_request_error(self, qdrant_client):
        """Search should return empty results on connection error (outer except catches all)."""
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        qdrant_client._http_client = mock_http_client

        with patch("backend.core.qdrant_db.RETRY_BASE_DELAY", 0.001), \
             patch("backend.core.qdrant_db.MAX_RETRIES", 0):
            result = await qdrant_client.search(
                query_embedding=[0.1] * 1536,
                limit=5,
            )
        assert result["total_found"] == 0
        assert result["ids"] == []

    @pytest.mark.asyncio
    async def test_get_collection_stats_success(self, qdrant_client):
        """get_stats should return collection statistics on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "points_count": 1000,
                "config": {
                    "params": {
                        "vectors": {
                            "size": 1536,
                            "distance": "Cosine",
                        }
                    }
                },
                "status": "green",
            }
        }

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        qdrant_client._http_client = mock_http_client

        stats = await qdrant_client.get_stats()
        assert stats["collection_name"] == "test_collection"
        assert stats["total_documents"] == 1000
        assert stats["vector_size"] == 1536
        assert stats["status"] == "green"

    @pytest.mark.asyncio
    async def test_get_collection_stats_http_error(self, qdrant_client):
        """get_stats should handle HTTP errors gracefully."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_request = MagicMock()

        http_error = httpx.HTTPStatusError(
            "Not Found",
            request=mock_request,
            response=mock_response,
        )
        mock_response.raise_for_status = MagicMock(side_effect=http_error)

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(return_value=mock_response)
        qdrant_client._http_client = mock_http_client

        stats = await qdrant_client.get_stats()
        assert "error" in stats
        assert "404" in stats["error"]
        assert stats["collection_name"] == "test_collection"

    @pytest.mark.asyncio
    async def test_get_collection_stats_request_error(self, qdrant_client):
        """get_stats should handle connection errors gracefully."""
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(side_effect=Exception("connection lost"))
        qdrant_client._http_client = mock_http_client

        stats = await qdrant_client.get_stats()
        assert "error" in stats
        assert "connection lost" in stats["error"]

    def test_collection_property(self, qdrant_client):
        """collection() should return self for compat."""
        assert qdrant_client.collection() is qdrant_client
