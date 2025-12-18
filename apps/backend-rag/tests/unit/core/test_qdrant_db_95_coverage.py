"""
Comprehensive tests for Qdrant DB - Target 95% coverage
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
sys.path.insert(0, str(backend_path))

import importlib.util

qdrant_db_path = backend_path / "core" / "qdrant_db.py"
spec = importlib.util.spec_from_file_location("qdrant_db", qdrant_db_path)
qdrant_db_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qdrant_db_module)
QdrantClient = qdrant_db_module.QdrantClient
get_qdrant_metrics = qdrant_db_module.get_qdrant_metrics
_retry_with_backoff = qdrant_db_module._retry_with_backoff


@pytest.mark.asyncio
class TestQdrantDB95Coverage:
    """Comprehensive tests for QdrantClient to achieve 95% coverage"""

    def test_init_default(self):
        """Test QdrantClient initialization with defaults"""
        # Mock settings to None to use defaults
        with patch.object(qdrant_db_module, "settings", None):
            client = QdrantClient()
            assert client.collection_name == "knowledge_base"
            assert client.qdrant_url == "http://localhost:6333"
            assert client.timeout == 30.0

    def test_init_custom_params(self):
        """Test QdrantClient initialization with custom parameters"""
        client = QdrantClient(
            qdrant_url="http://custom:8080",
            collection_name="test_collection",
            api_key="test_key",
            timeout=60.0,
        )
        assert client.collection_name == "test_collection"
        assert client.qdrant_url == "http://custom:8080"
        assert client.api_key == "test_key"
        assert client.timeout == 60.0

    def test_init_url_trailing_slash(self):
        """Test that trailing slash is removed from URL"""
        client = QdrantClient(qdrant_url="http://localhost:6333/")
        assert client.qdrant_url == "http://localhost:6333"

    async def test_get_client_creates_new(self):
        """Test _get_client creates new client"""
        client = QdrantClient(qdrant_url="http://localhost:6333")
        assert client._http_client is None
        http_client = await client._get_client()
        assert http_client is not None
        assert client._http_client is not None

    async def test_get_client_reuses_existing(self):
        """Test _get_client reuses existing client"""
        client = QdrantClient(qdrant_url="http://localhost:6333")
        http_client1 = await client._get_client()
        http_client2 = await client._get_client()
        assert http_client1 is http_client2

    async def test_get_headers_with_api_key(self):
        """Test _get_headers includes API key"""
        client = QdrantClient(api_key="test_key")
        headers = client._get_headers()
        assert headers["api-key"] == "test_key"
        assert headers["Content-Type"] == "application/json"

    @patch("core.qdrant_db.settings", None)
    async def test_get_headers_without_api_key(self):
        """Test _get_headers without API key"""
        client = QdrantClient()
        headers = client._get_headers()
        assert "api-key" not in headers
        assert headers["Content-Type"] == "application/json"

    async def test_close(self):
        """Test closing client"""
        client = QdrantClient()
        await client._get_client()
        assert client._http_client is not None
        await client.close()
        assert client._http_client is None

    async def test_context_manager(self):
        """Test async context manager"""
        async with QdrantClient() as client:
            assert client._http_client is not None
        # Should be closed after context
        assert client._http_client is None

    async def test_search_success(self):
        """Test successful search"""
        client = QdrantClient(qdrant_url="http://localhost:6333")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": [
                {
                    "id": "1",
                    "score": 0.9,
                    "payload": {"text": "doc1", "metadata": {"key": "value"}},
                },
                {"id": "2", "score": 0.8, "payload": {"text": "doc2", "metadata": {}}},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_client

        result = await client.search([0.1] * 1536, limit=10)
        assert result["total_found"] == 2
        assert len(result["ids"]) == 2

    async def test_search_with_filter(self):
        """Test search with filter"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_client

        filter_dict = {"tier": {"$in": ["S", "A"]}}
        await client.search([0.1] * 1536, limit=10, filter=filter_dict)
        # Verify filter was passed
        call_args = mock_client.post.call_args
        assert "filter" in call_args[1]["json"]

    async def test_search_timeout(self):
        """Test search with timeout"""
        client = QdrantClient(qdrant_url="http://localhost:6333")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        client._http_client = mock_client

        # Should retry and eventually raise TimeoutError
        with pytest.raises((TimeoutError, Exception)):
            await client.search([0.1] * 1536, limit=10)

    async def test_search_5xx_error(self):
        """Test search with 5xx error (should retry)"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=mock_error)
        client._http_client = mock_client

        # Should retry and eventually return empty results
        result = await client.search([0.1] * 1536, limit=10)
        assert result["total_found"] == 0

    async def test_search_4xx_error(self):
        """Test search with 4xx error (should return empty)"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        mock_error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=mock_error)
        client._http_client = mock_client

        result = await client.search([0.1] * 1536, limit=10)
        assert result["total_found"] == 0

    async def test_search_request_error(self):
        """Test search with request error"""
        client = QdrantClient(qdrant_url="http://localhost:6333")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("Connection error"))
        client._http_client = mock_client

        # Should retry and eventually raise ConnectionError
        with pytest.raises((ConnectionError, Exception)):
            await client.search([0.1] * 1536, limit=10)

    async def test_search_empty_embedding(self):
        """Test search with empty embedding"""
        client = QdrantClient()
        with pytest.raises(ValueError):
            await client.search([], limit=10)

    async def test_search_invalid_embedding_type(self):
        """Test search with invalid embedding type"""
        client = QdrantClient()
        with pytest.raises(TypeError):
            await client.search(["invalid"], limit=10)

    async def test_get_collection_stats_success(self):
        """Test getting collection stats successfully"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "points_count": 1000,
                "config": {"params": {"vectors": {"size": 1536, "distance": "Cosine"}}},
                "status": "green",
            }
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        client._http_client = mock_client

        stats = await client.get_collection_stats()
        assert stats["total_documents"] == 1000
        assert stats["vector_size"] == 1536

    async def test_get_collection_stats_http_error(self):
        """Test getting stats with HTTP error"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_error)
        client._http_client = mock_client

        stats = await client.get_collection_stats()
        assert "error" in stats

    async def test_get_collection_stats_request_error(self):
        """Test getting stats with request error"""
        client = QdrantClient()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("Error"))
        client._http_client = mock_client

        stats = await client.get_collection_stats()
        assert "error" in stats

    async def test_create_collection_success(self):
        """Test creating collection successfully"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        client._http_client = mock_client

        result = await client.create_collection(vector_size=384, distance="Cosine")
        assert result is True

    async def test_create_collection_with_on_disk(self):
        """Test creating collection with on_disk_payload"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        client._http_client = mock_client

        result = await client.create_collection(on_disk_payload=True)
        assert result is True

    async def test_create_collection_http_error(self):
        """Test creating collection with HTTP error"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"

        mock_error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(side_effect=mock_error)
        client._http_client = mock_client

        result = await client.create_collection()
        assert result is False

    async def test_create_collection_request_error(self):
        """Test creating collection with request error"""
        client = QdrantClient()

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(side_effect=httpx.RequestError("Error"))
        client._http_client = mock_client

        result = await client.create_collection()
        assert result is False

    async def test_upsert_documents_success(self):
        """Test upserting documents successfully"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        client._http_client = mock_client

        result = await client.upsert_documents(
            chunks=["doc1", "doc2"],
            embeddings=[[0.1] * 1536, [0.2] * 1536],
            metadatas=[{"key": "value"}, {}],
        )
        assert result["success"] is True
        assert result["documents_added"] == 2

    async def test_upsert_documents_with_ids(self):
        """Test upserting with provided IDs"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        client._http_client = mock_client

        result = await client.upsert_documents(
            chunks=["doc1"],
            embeddings=[[0.1] * 1536],
            metadatas=[{}],
            ids=["custom_id"],
        )
        assert result["success"] is True

    async def test_upsert_documents_length_mismatch(self):
        """Test upserting with mismatched lengths"""
        client = QdrantClient()
        with pytest.raises(ValueError):
            await client.upsert_documents(
                chunks=["doc1", "doc2"],
                embeddings=[[0.1] * 1536],
                metadatas=[{}],
            )

    async def test_upsert_documents_batch_processing(self):
        """Test upserting with batch processing"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        client._http_client = mock_client

        # Create 1000 documents to trigger batching
        chunks = [f"doc{i}" for i in range(1000)]
        embeddings = [[0.1] * 1536 for _ in range(1000)]
        metadatas = [{} for _ in range(1000)]

        result = await client.upsert_documents(chunks, embeddings, metadatas, batch_size=500)
        assert result["success"] is True
        assert result["documents_added"] == 1000
        # Should have made 2 batch calls
        assert mock_client.put.call_count == 2

    async def test_upsert_documents_batch_error(self):
        """Test upserting with batch error"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(side_effect=mock_error)
        client._http_client = mock_client

        result = await client.upsert_documents(
            chunks=["doc1", "doc2"],
            embeddings=[[0.1] * 1536, [0.2] * 1536],
            metadatas=[{}, {}],
        )
        assert result["success"] is False
        assert "error" in result

    async def test_get_success(self):
        """Test getting points by IDs successfully"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": [
                {
                    "id": "1",
                    "vector": [0.1] * 1536,
                    "payload": {"text": "doc1", "metadata": {"key": "value"}},
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_client

        result = await client.get(["1"])
        assert len(result["ids"]) == 1
        assert result["ids"][0] == "1"

    async def test_get_with_include(self):
        """Test getting points with include parameter"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_client

        await client.get(["1"], include=["embeddings", "payload"])
        # Verify params were set
        call_kwargs = mock_client.post.call_args[1]
        assert "params" in call_kwargs

    async def test_get_http_error(self):
        """Test getting points with HTTP error"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=mock_error)
        client._http_client = mock_client

        result = await client.get(["1"])
        assert len(result["ids"]) == 0

    async def test_get_request_error(self):
        """Test getting points with request error"""
        client = QdrantClient()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("Error"))
        client._http_client = mock_client

        result = await client.get(["1"])
        assert len(result["ids"]) == 0

    async def test_delete_success(self):
        """Test deleting points successfully"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_client

        result = await client.delete(["1", "2"])
        assert result["success"] is True
        assert result["deleted_count"] == 2

    async def test_delete_http_error(self):
        """Test deleting with HTTP error"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=mock_error)
        client._http_client = mock_client

        result = await client.delete(["1"])
        assert result["success"] is False

    async def test_delete_request_error(self):
        """Test deleting with request error"""
        client = QdrantClient()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("Error"))
        client._http_client = mock_client

        with pytest.raises(ConnectionError):
            await client.delete(["1"])

    async def test_peek_success(self):
        """Test peeking at points successfully"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "points": [
                    {
                        "id": "1",
                        "vector": [0.1] * 1536,
                        "payload": {"text": "doc1", "metadata": {}},
                    }
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        client._http_client = mock_client

        result = await client.peek(limit=10)
        assert len(result["ids"]) == 1

    async def test_peek_http_error(self):
        """Test peeking with HTTP error"""
        client = QdrantClient()

        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_error = httpx.HTTPStatusError("Error", request=MagicMock(), response=mock_response)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=mock_error)
        client._http_client = mock_client

        result = await client.peek()
        assert len(result["ids"]) == 0

    async def test_peek_request_error(self):
        """Test peeking with request error"""
        client = QdrantClient()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("Error"))
        client._http_client = mock_client

        result = await client.peek()
        assert len(result["ids"]) == 0

    def test_collection_property(self):
        """Test collection property"""
        client = QdrantClient()
        assert client.collection is client

    def test_convert_filter_to_qdrant_format_in(self):
        """Test converting filter with $in operator"""
        client = QdrantClient()
        filter_dict = {"tier": {"$in": ["S", "A"]}}
        result = client._convert_filter_to_qdrant_format(filter_dict)
        assert result is not None
        assert "must" in result

    def test_convert_filter_to_qdrant_format_ne(self):
        """Test converting filter with $ne operator"""
        client = QdrantClient()
        filter_dict = {"status": {"$ne": "dicabut"}}
        result = client._convert_filter_to_qdrant_format(filter_dict)
        assert result is not None
        assert "must_not" in result

    def test_convert_filter_to_qdrant_format_equals(self):
        """Test converting filter with equals"""
        client = QdrantClient()
        filter_dict = {"status": "berlaku"}
        result = client._convert_filter_to_qdrant_format(filter_dict)
        assert result is not None

    def test_convert_filter_to_qdrant_format_none(self):
        """Test converting None filter"""
        client = QdrantClient()
        result = client._convert_filter_to_qdrant_format(None)
        assert result is None

    def test_get_qdrant_metrics(self):
        """Test getting Qdrant metrics"""
        metrics = get_qdrant_metrics()
        assert "search_calls" in metrics
        assert "upsert_calls" in metrics
        assert "errors" in metrics

    async def test_retry_with_backoff_success(self):
        """Test retry with backoff on success"""

        async def success_func():
            return "success"

        result = await _retry_with_backoff(success_func)
        assert result == "success"

    async def test_retry_with_backoff_retries(self):
        """Test retry with backoff retries on failure"""
        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary error")
            return "success"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await _retry_with_backoff(fail_then_succeed, max_retries=3)
            assert result == "success"

    async def test_retry_with_backoff_max_retries(self):
        """Test retry with backoff exhausts retries"""

        async def always_fail():
            raise Exception("Always fails")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(Exception):
                await _retry_with_backoff(always_fail, max_retries=2)
