"""
Comprehensive tests for QdrantClient
Target: 100% coverage
Composer: 1
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.core.qdrant_db import (  # noqa: E402
    QdrantClient,
    QdrantErrorClassifier,
    QdrantErrorType,
    _retry_with_backoff,
    get_qdrant_metrics,
)


@pytest.fixture
def qdrant_client():
    """Create QdrantClient instance"""
    with patch("httpx.AsyncClient"):
        return QdrantClient(
            qdrant_url="http://localhost:6333", collection_name="test_collection", api_key=None
        )


@pytest.fixture
def mock_http_client():
    """Mock HTTP client"""
    client = AsyncMock()
    return client


class TestQdrantErrorClassifier:
    """Tests for QdrantErrorClassifier"""

    def test_classify_timeout(self):
        """Test classifying timeout error"""
        classifier = QdrantErrorClassifier()
        error = httpx.TimeoutException("Timeout")
        error_type, retryable = classifier.classify(error)
        assert error_type == QdrantErrorType.TIMEOUT
        assert retryable is True

    def test_classify_connection_error(self):
        """Test classifying connection error"""
        classifier = QdrantErrorClassifier()
        error = httpx.ConnectError("Connection failed")
        error_type, retryable = classifier.classify(error)
        assert error_type == QdrantErrorType.CONNECTION
        assert retryable is True

    def test_classify_retryable_status(self):
        """Test classifying retryable HTTP status"""
        classifier = QdrantErrorClassifier()
        response = MagicMock()
        response.status_code = 500
        error = httpx.HTTPStatusError("Server error", request=MagicMock(), response=response)
        error_type, retryable = classifier.classify(error)
        assert error_type == QdrantErrorType.SERVER_ERROR
        assert retryable is True

    def test_classify_non_retryable_status(self):
        """Test classifying non-retryable HTTP status"""
        classifier = QdrantErrorClassifier()
        response = MagicMock()
        response.status_code = 400
        error = httpx.HTTPStatusError("Bad request", request=MagicMock(), response=response)
        error_type, retryable = classifier.classify(error)
        assert error_type == QdrantErrorType.CLIENT_ERROR
        assert retryable is False

    def test_classify_unknown_error(self):
        """Test classifying unknown error"""
        classifier = QdrantErrorClassifier()
        error = ValueError("Unknown error")
        error_type, retryable = classifier.classify(error)
        assert error_type == QdrantErrorType.NON_RETRYABLE
        assert retryable is False


class TestQdrantClient:
    """Tests for QdrantClient"""

    def test_init(self):
        """Test initialization"""
        with patch("httpx.AsyncClient"):
            client = QdrantClient(
                qdrant_url="http://localhost:6333", collection_name="test_collection"
            )
            assert client.qdrant_url == "http://localhost:6333"
            assert client.collection_name == "test_collection"
            assert client._error_classifier is not None

    def test_init_with_api_key(self):
        """Test initialization with API key"""
        with patch("httpx.AsyncClient"):
            client = QdrantClient(
                qdrant_url="http://localhost:6333",
                collection_name="test_collection",
                api_key="test-key",
            )
            assert client.api_key == "test-key"

    def test_init_with_timeout(self):
        """Test initialization with custom timeout"""
        with patch("httpx.AsyncClient"):
            client = QdrantClient(
                qdrant_url="http://localhost:6333", collection_name="test_collection", timeout=60.0
            )
            assert client.timeout == 60.0

    def test_init_url_trailing_slash(self):
        """Test initialization removes trailing slash"""
        with patch("httpx.AsyncClient"):
            client = QdrantClient(
                qdrant_url="http://localhost:6333/", collection_name="test_collection"
            )
            assert client.qdrant_url == "http://localhost:6333"

    @pytest.mark.asyncio
    async def test_get_client(self, qdrant_client):
        """Test getting HTTP client"""
        client = await qdrant_client._get_client()
        assert client is not None
        assert qdrant_client._http_client is not None

    @pytest.mark.asyncio
    async def test_get_client_cached(self, qdrant_client):
        """Test getting cached HTTP client"""
        client1 = await qdrant_client._get_client()
        client2 = await qdrant_client._get_client()
        assert client1 == client2

    @pytest.mark.asyncio
    async def test_close(self, qdrant_client):
        """Test close operation"""
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        qdrant_client._http_client = mock_client

        await qdrant_client.close()
        mock_client.aclose.assert_called_once()
        assert qdrant_client._http_client is None

    @pytest.mark.asyncio
    async def test_close_no_client(self, qdrant_client):
        """Test close when no client exists"""
        qdrant_client._http_client = None
        await qdrant_client.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test context manager usage"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            async with QdrantClient(
                qdrant_url="http://localhost:6333", collection_name="test_collection"
            ) as client:
                assert client is not None

            mock_client.aclose.assert_called_once()

    def test_get_headers_with_api_key(self):
        """Test getting headers with API key"""
        with patch("httpx.AsyncClient"):
            client = QdrantClient(
                qdrant_url="http://localhost:6333",
                collection_name="test_collection",
                api_key="test-key",
            )
            headers = client._get_headers()
            assert headers["api-key"] == "test-key"

    def test_get_headers_without_api_key(self):
        """Test getting headers without API key"""
        with patch("httpx.AsyncClient"):
            # Create client with explicit api_key=None to override any settings
            client = QdrantClient(
                qdrant_url="http://localhost:6333", collection_name="test_collection", api_key=None
            )
            # Ensure api_key is None
            client.api_key = None
            headers = client._get_headers()
            assert "api-key" not in headers

    def test_convert_filter_to_qdrant_format_simple(self, qdrant_client):
        """Test converting simple filter"""
        filter_dict = {"tier": "S"}
        result = qdrant_client._convert_filter_to_qdrant_format(filter_dict)
        assert result is not None
        assert "must" in result

    def test_convert_filter_to_qdrant_format_in(self, qdrant_client):
        """Test converting filter with $in"""
        filter_dict = {"tier": {"$in": ["S", "A"]}}
        result = qdrant_client._convert_filter_to_qdrant_format(filter_dict)
        assert result is not None
        assert "must" in result

    def test_convert_filter_to_qdrant_format_ne(self, qdrant_client):
        """Test converting filter with $ne"""
        filter_dict = {"status": {"$ne": "invalid"}}
        result = qdrant_client._convert_filter_to_qdrant_format(filter_dict)
        assert result is not None
        assert "must_not" in result

    def test_convert_filter_to_qdrant_format_empty(self, qdrant_client):
        """Test converting empty filter"""
        result = qdrant_client._convert_filter_to_qdrant_format({})
        assert result is None

    @pytest.mark.asyncio
    async def test_search_success(self, qdrant_client):
        """Test search operation success"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "result": [{"id": "1", "score": 0.9, "payload": {"text": "test", "metadata": {}}}]
            }
        )
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(qdrant_client, "_get_client", return_value=mock_client):
            result = await qdrant_client.search(query_embedding=[0.1] * 1536, limit=5)
            assert result is not None
            assert "ids" in result
            assert "documents" in result
            assert len(result["ids"]) == 1

    @pytest.mark.asyncio
    async def test_search_with_filter(self, qdrant_client):
        """Test search with filter"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={"result": []})
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(qdrant_client, "_get_client", return_value=mock_client):
            result = await qdrant_client.search(
                query_embedding=[0.1] * 1536, limit=5, filter={"tier": "S"}
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_search_error(self, qdrant_client):
        """Test search with error"""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))

        with patch.object(qdrant_client, "_get_client", return_value=mock_client):
            result = await qdrant_client.search(query_embedding=[0.1] * 1536, limit=5)
            assert result["total_found"] == 0

    @pytest.mark.asyncio
    async def test_create_collection(self, qdrant_client):
        """Test creating collection"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)

        with patch.object(qdrant_client, "_get_client", return_value=mock_client):
            result = await qdrant_client.create_collection(vector_size=1536)
            assert result is True

    @pytest.mark.asyncio
    async def test_create_collection_with_sparse(self, qdrant_client):
        """Test creating collection with sparse vectors"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)

        with patch.object(qdrant_client, "_get_client", return_value=mock_client):
            result = await qdrant_client.create_collection(vector_size=1536, enable_sparse=True)
            assert result is True

    @pytest.mark.asyncio
    async def test_create_collection_error(self, qdrant_client):
        """Test creating collection with error"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Collection exists"
        error = httpx.HTTPStatusError("Bad request", request=MagicMock(), response=mock_response)
        mock_response.raise_for_status = MagicMock(side_effect=error)

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)

        with patch.object(qdrant_client, "_get_client", return_value=mock_client):
            result = await qdrant_client.create_collection(vector_size=1536)
            assert result is False

    @pytest.mark.asyncio
    async def test_upsert_documents_success(self, qdrant_client):
        """Test upsert_documents success"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)

        with patch.object(qdrant_client, "_get_client", return_value=mock_client):
            result = await qdrant_client.upsert_documents(
                chunks=["test chunk"], embeddings=[[0.1] * 1536], metadatas=[{"test": "metadata"}]
            )
            assert result is not None
            assert "documents_added" in result or "success" in result

    @pytest.mark.asyncio
    async def test_upsert_documents_with_ids(self, qdrant_client):
        """Test upsert_documents with provided IDs"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)

        with patch.object(qdrant_client, "_get_client", return_value=mock_client):
            result = await qdrant_client.upsert_documents(
                chunks=["test chunk"],
                embeddings=[[0.1] * 1536],
                metadatas=[{"test": "metadata"}],
                ids=["custom-id"],
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_upsert_documents_length_mismatch(self, qdrant_client):
        """Test upsert_documents with length mismatch"""
        with pytest.raises(ValueError):
            await qdrant_client.upsert_documents(
                chunks=["chunk1", "chunk2"],
                embeddings=[[0.1] * 1536],
                metadatas=[{"test": "metadata"}],
            )

    @pytest.mark.asyncio
    async def test_get_success(self, qdrant_client):
        """Test get operation success"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "result": [
                    {"id": "1", "vector": [0.1] * 1536, "payload": {"text": "test", "metadata": {}}}
                ]
            }
        )
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(qdrant_client, "_get_client", return_value=mock_client):
            result = await qdrant_client.get(ids=["1"])
            assert result is not None
            assert "ids" in result
            assert len(result["ids"]) == 1

    @pytest.mark.asyncio
    async def test_get_with_include(self, qdrant_client):
        """Test get with include parameter"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(return_value={"result": []})
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(qdrant_client, "_get_client", return_value=mock_client):
            result = await qdrant_client.get(ids=["1"], include=["embeddings"])
            assert result is not None

    @pytest.mark.asyncio
    async def test_get_error(self, qdrant_client):
        """Test get with error"""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))

        with patch.object(qdrant_client, "_get_client", return_value=mock_client):
            result = await qdrant_client.get(ids=["1"])
            assert result["ids"] == []

    @pytest.mark.asyncio
    async def test_delete_success(self, qdrant_client):
        """Test delete operation success"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(qdrant_client, "_get_client", return_value=mock_client):
            result = await qdrant_client.delete(ids=["1", "2"])
            assert result["success"] is True
            assert result["deleted_count"] == 2

    @pytest.mark.asyncio
    async def test_delete_error(self, qdrant_client):
        """Test delete with error"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        error = httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)
        mock_response.raise_for_status = MagicMock(side_effect=error)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(qdrant_client, "_get_client", return_value=mock_client):
            result = await qdrant_client.delete(ids=["1"])
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_peek(self, qdrant_client):
        """Test peek operation"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = AsyncMock(
            return_value={"result": {"points": [{"id": "1", "payload": {"text": "test"}}]}}
        )
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.object(qdrant_client, "_get_client", return_value=mock_client):
            result = await qdrant_client.peek(limit=5)
            assert result is not None

    @pytest.mark.asyncio
    async def test_hybrid_search(self, qdrant_client):
        """Test hybrid search"""
        # Mock search method since hybrid_search falls back to search when no sparse vector
        with patch.object(qdrant_client, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {
                "ids": [],
                "documents": [],
                "metadatas": [],
                "distances": [],
                "total_found": 0,
            }
            result = await qdrant_client.hybrid_search(
                query_embedding=[0.1] * 1536,
                query_sparse=None,  # No sparse vector, will fall back to search
                limit=5,
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_collection_property(self, qdrant_client):
        """Test collection property"""
        result = qdrant_client.collection()
        assert result == qdrant_client

    @pytest.mark.asyncio
    async def test_upsert_documents_with_sparse_success(self, qdrant_client):
        """Test upsert_documents_with_sparse success"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)

        with patch.object(qdrant_client, "_get_client", return_value=mock_client):
            result = await qdrant_client.upsert_documents_with_sparse(
                chunks=["test chunk"],
                embeddings=[[0.1] * 1536],
                sparse_vectors=[{"indices": [1, 2], "values": [0.5, 0.3]}],
                metadatas=[{"test": "metadata"}],
            )
            assert result is not None
            assert result["success"] is True
            assert result["has_sparse_vectors"] is True

    @pytest.mark.asyncio
    async def test_upsert_documents_with_sparse_with_ids(self, qdrant_client):
        """Test upsert_documents_with_sparse with provided IDs"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)

        with patch.object(qdrant_client, "_get_client", return_value=mock_client):
            result = await qdrant_client.upsert_documents_with_sparse(
                chunks=["test chunk"],
                embeddings=[[0.1] * 1536],
                sparse_vectors=[{"indices": [1, 2], "values": [0.5, 0.3]}],
                metadatas=[{"test": "metadata"}],
                ids=["custom-id"],
            )
            assert result is not None
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_upsert_documents_with_sparse_length_mismatch(self, qdrant_client):
        """Test upsert_documents_with_sparse with length mismatch"""
        with pytest.raises(ValueError):
            await qdrant_client.upsert_documents_with_sparse(
                chunks=["chunk1", "chunk2"],
                embeddings=[[0.1] * 1536],
                sparse_vectors=[{"indices": [1], "values": [0.5]}],
                metadatas=[{"test": "metadata"}],
            )

    @pytest.mark.asyncio
    async def test_upsert_documents_with_sparse_batch_error(self, qdrant_client):
        """Test upsert_documents_with_sparse with batch error"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        error = httpx.HTTPStatusError("Bad request", request=MagicMock(), response=mock_response)
        mock_response.raise_for_status = MagicMock(side_effect=error)

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)

        with patch.object(qdrant_client, "_get_client", return_value=mock_client):
            result = await qdrant_client.upsert_documents_with_sparse(
                chunks=["test chunk"],
                embeddings=[[0.1] * 1536],
                sparse_vectors=[{"indices": [1, 2], "values": [0.5, 0.3]}],
                metadatas=[{"test": "metadata"}],
            )
            assert result is not None
            assert result["success"] is False
            assert "error" in result


class TestQdrantMetrics:
    """Tests for Qdrant metrics"""

    def test_get_qdrant_metrics_empty(self):
        """Test getting metrics when no operations"""
        # Reset metrics to ensure clean state
        from backend.core.qdrant_db import _qdrant_metrics

        original_metrics = _qdrant_metrics.copy()
        _qdrant_metrics.update(
            {
                "search_calls": 0,
                "search_total_time": 0.0,
                "upsert_calls": 0,
                "upsert_total_time": 0.0,
                "upsert_documents_total": 0,
                "retry_count": 0,
                "errors": 0,
            }
        )

        try:
            metrics = get_qdrant_metrics()
            assert metrics["search_calls"] == 0
            assert metrics["upsert_calls"] == 0
            assert metrics["search_avg_time_ms"] == 0.0
            assert metrics["upsert_avg_time_ms"] == 0.0
            assert metrics["upsert_avg_docs_per_call"] == 0.0
        finally:
            # Restore original metrics
            _qdrant_metrics.update(original_metrics)

    def test_get_qdrant_metrics_with_data(self):
        """Test getting metrics with operation data"""
        from backend.core.qdrant_db import _qdrant_metrics

        original_metrics = _qdrant_metrics.copy()
        _qdrant_metrics.update(
            {
                "search_calls": 10,
                "search_total_time": 5.0,  # 5 seconds total
                "upsert_calls": 5,
                "upsert_total_time": 2.5,  # 2.5 seconds total
                "upsert_documents_total": 50,  # 50 documents total
                "retry_count": 2,
                "errors": 1,
            }
        )

        try:
            metrics = get_qdrant_metrics()
            assert metrics["search_calls"] == 10
            assert metrics["upsert_calls"] == 5
            assert metrics["search_avg_time_ms"] == 500.0  # 5.0 / 10 * 1000
            assert metrics["upsert_avg_time_ms"] == 500.0  # 2.5 / 5 * 1000
            assert metrics["upsert_avg_docs_per_call"] == 10.0  # 50 / 5
            assert metrics["retry_count"] == 2
            assert metrics["errors"] == 1
        finally:
            # Restore original metrics
            _qdrant_metrics.update(original_metrics)

    def test_get_qdrant_metrics_search_only(self):
        """Test getting metrics with only search operations"""
        from backend.core.qdrant_db import _qdrant_metrics

        original_metrics = _qdrant_metrics.copy()
        _qdrant_metrics.update(
            {
                "search_calls": 3,
                "search_total_time": 1.5,
                "upsert_calls": 0,
                "upsert_total_time": 0.0,
                "upsert_documents_total": 0,
                "retry_count": 0,
                "errors": 0,
            }
        )

        try:
            metrics = get_qdrant_metrics()
            assert metrics["search_avg_time_ms"] == 500.0
            assert metrics["upsert_avg_time_ms"] == 0.0
            assert metrics["upsert_avg_docs_per_call"] == 0.0
        finally:
            _qdrant_metrics.update(original_metrics)

    def test_get_qdrant_metrics_upsert_only(self):
        """Test getting metrics with only upsert operations"""
        from backend.core.qdrant_db import _qdrant_metrics

        original_metrics = _qdrant_metrics.copy()
        _qdrant_metrics.update(
            {
                "search_calls": 0,
                "search_total_time": 0.0,
                "upsert_calls": 4,
                "upsert_total_time": 2.0,
                "upsert_documents_total": 20,
                "retry_count": 0,
                "errors": 0,
            }
        )

        try:
            metrics = get_qdrant_metrics()
            assert metrics["search_avg_time_ms"] == 0.0
            assert metrics["upsert_avg_time_ms"] == 500.0
            assert metrics["upsert_avg_docs_per_call"] == 5.0
        finally:
            _qdrant_metrics.update(original_metrics)


class TestRetryWithBackoff:
    """Tests for _retry_with_backoff function"""

    @pytest.mark.asyncio
    async def test_retry_success_first_attempt(self):
        """Test retry succeeds on first attempt"""
        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await _retry_with_backoff(success_func, max_retries=3)
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_success_after_retries(self):
        """Test retry succeeds after some failures"""
        call_count = 0

        async def retry_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = await _retry_with_backoff(retry_func, max_retries=3)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_fails_after_max_retries(self):
        """Test retry fails after max retries"""
        call_count = 0

        async def fail_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Persistent error")

        with pytest.raises(ValueError, match="Persistent error"):
            await _retry_with_backoff(fail_func, max_retries=2)

        assert call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_retry_custom_max_retries(self):
        """Test retry with custom max_retries"""
        call_count = 0

        async def fail_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Error")

        with pytest.raises(ValueError):
            await _retry_with_backoff(fail_func, max_retries=1)

        assert call_count == 2  # Initial + 1 retry

    @pytest.mark.asyncio
    async def test_retry_custom_base_delay(self):
        """Test retry with custom base delay"""
        import time

        call_count = 0
        start_time = None

        async def retry_func():
            nonlocal call_count, start_time
            call_count += 1
            if call_count == 1:
                start_time = time.time()
                raise ValueError("Error")
            return "success"

        result = await _retry_with_backoff(retry_func, max_retries=1, base_delay=0.1)
        assert result == "success"
        assert call_count == 2
        # Verify delay was approximately correct (allow some tolerance)
        elapsed = time.time() - start_time
        assert elapsed >= 0.09  # At least 90ms

    @pytest.mark.asyncio
    async def test_retry_exponential_backoff(self):
        """Test that retry uses exponential backoff"""
        import time

        call_count = 0
        timestamps = []

        async def retry_func():
            nonlocal call_count
            call_count += 1
            timestamps.append(time.time())
            if call_count < 3:
                raise ValueError("Error")
            return "success"

        await _retry_with_backoff(retry_func, max_retries=2, base_delay=0.1)

        assert call_count == 3
        # Verify delays increase exponentially
        delay1 = timestamps[1] - timestamps[0]
        delay2 = timestamps[2] - timestamps[1]
        # delay2 should be approximately 2x delay1 (exponential backoff)
        assert delay2 >= delay1 * 1.5  # Allow some tolerance
