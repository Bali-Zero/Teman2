"""
🧪 EXTENDED UNIT TESTS - Qdrant DB Client
Focus: Increase coverage from 11.3% to ≥95%

Tests cover previously untested paths:
- get_qdrant_metrics (all branches)
- _retry_with_backoff (success, retries, failures)
- QdrantClient initialization (all parameter combinations)
- _get_client (lazy initialization, connection pooling)
- close (cleanup)
- __aenter__ and __aexit__ (context manager)
- _get_headers (with/without API key)
- _convert_filter_to_qdrant_format (all filter types: $in, $ne, $nin, direct match)
- search (success, errors, timeout, retry, filters)
- get_collection_stats (success, errors)
- create_collection (success, errors, with/without on_disk_payload)
- upsert_documents (success, batching, errors, validation)
- get (success, errors, with/without include)
- delete (success, errors)
- peek (success, errors)
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.qdrant_db import (
    QdrantClient,
    _retry_with_backoff,
    get_qdrant_metrics,
)

# ============================================================================
# get_qdrant_metrics TESTS
# ============================================================================


def test_get_qdrant_metrics_no_calls():
    """Test get_qdrant_metrics with no calls"""
    metrics = get_qdrant_metrics()

    assert "search_calls" in metrics
    assert "upsert_calls" in metrics
    assert metrics["search_avg_time_ms"] == 0.0
    assert metrics["upsert_avg_time_ms"] == 0.0
    assert metrics["upsert_avg_docs_per_call"] == 0.0


def test_get_qdrant_metrics_with_search_calls():
    """Test get_qdrant_metrics calculates search averages"""
    # Reset metrics
    from core.qdrant_db import _qdrant_metrics

    _qdrant_metrics["search_calls"] = 5
    _qdrant_metrics["search_total_time"] = 2.5  # 500ms average

    metrics = get_qdrant_metrics()

    assert metrics["search_avg_time_ms"] == 500.0
    assert metrics["search_calls"] == 5


def test_get_qdrant_metrics_with_upsert_calls():
    """Test get_qdrant_metrics calculates upsert averages"""
    from core.qdrant_db import _qdrant_metrics

    _qdrant_metrics["upsert_calls"] = 3
    _qdrant_metrics["upsert_total_time"] = 1.5  # 500ms average
    _qdrant_metrics["upsert_documents_total"] = 1500  # 500 docs per call

    metrics = get_qdrant_metrics()

    assert metrics["upsert_avg_time_ms"] == 500.0
    assert metrics["upsert_avg_docs_per_call"] == 500.0


# ============================================================================
# _retry_with_backoff TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_retry_with_backoff_success_first_attempt():
    """Test _retry_with_backoff succeeds on first attempt"""

    async def success_func():
        return "success"

    result = await _retry_with_backoff(success_func)

    assert result == "success"


@pytest.mark.asyncio
async def test_retry_with_backoff_success_after_retry():
    """Test _retry_with_backoff succeeds after retry"""
    attempt_count = 0

    async def retry_func():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 2:
            raise Exception("Temporary error")
        return "success"

    result = await _retry_with_backoff(retry_func, max_retries=3)

    assert result == "success"
    assert attempt_count == 2


@pytest.mark.asyncio
async def test_retry_with_backoff_all_retries_fail():
    """Test _retry_with_backoff raises after all retries fail"""

    async def fail_func():
        raise Exception("Persistent error")

    with pytest.raises(Exception, match="Persistent error"):
        await _retry_with_backoff(fail_func, max_retries=2)


@pytest.mark.asyncio
async def test_retry_with_backoff_custom_delay():
    """Test _retry_with_backoff uses custom base delay"""
    attempt_times = []

    async def retry_func():
        attempt_times.append(pytest.current_time if hasattr(pytest, "current_time") else 0)
        raise Exception("Error")

    with patch("asyncio.sleep") as mock_sleep:
        try:
            await _retry_with_backoff(retry_func, max_retries=2, base_delay=0.5)
        except Exception:
            pass

        # Should sleep with exponential backoff: 0.5s, 1.0s
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(0.5)  # First retry
        mock_sleep.assert_any_call(1.0)  # Second retry (0.5 * 2^1)


# ============================================================================
# QdrantClient INITIALIZATION TESTS
# ============================================================================


def test_qdrant_client_init_defaults():
    """Test QdrantClient initialization with defaults"""
    with patch("core.qdrant_db.settings", None):
        client = QdrantClient()

        assert client.qdrant_url == "http://localhost:6333"
        assert client.collection_name == "knowledge_base"
        assert client.api_key is None
        assert client.timeout == 30.0
        assert client._http_client is None


def test_qdrant_client_init_custom_params():
    """Test QdrantClient initialization with custom parameters"""
    client = QdrantClient(
        qdrant_url="http://custom:6333",
        collection_name="custom_collection",
        api_key="test-key",
        timeout=60.0,
    )

    assert client.qdrant_url == "http://custom:6333"
    assert client.collection_name == "custom_collection"
    assert client.api_key == "test-key"
    assert client.timeout == 60.0


def test_qdrant_client_init_removes_trailing_slash():
    """Test QdrantClient removes trailing slash from URL"""
    client = QdrantClient(qdrant_url="http://localhost:6333/")

    assert client.qdrant_url == "http://localhost:6333"


def test_qdrant_client_init_from_settings():
    """Test QdrantClient initialization from settings"""
    mock_settings = MagicMock()
    mock_settings.qdrant_url = "http://settings:6333"
    mock_settings.qdrant_api_key = "settings-key"
    mock_settings.qdrant_timeout = 45.0

    with patch("core.qdrant_db.settings", mock_settings):
        client = QdrantClient()

        assert client.qdrant_url == "http://settings:6333"
        assert client.api_key == "settings-key"
        assert client.timeout == 45.0


# ============================================================================
# _get_client TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_get_client_lazy_initialization():
    """Test _get_client creates client on first call"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    assert client._http_client is None

    http_client = await client._get_client()

    assert http_client is not None
    assert isinstance(http_client, httpx.AsyncClient)
    assert client._http_client == http_client


@pytest.mark.asyncio
async def test_get_client_reuses_existing():
    """Test _get_client reuses existing client"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    client1 = await client._get_client()
    client2 = await client._get_client()

    assert client1 is client2


@pytest.mark.asyncio
async def test_get_client_with_api_key():
    """Test _get_client includes API key in headers"""
    client = QdrantClient(qdrant_url="http://localhost:6333", api_key="test-key")

    http_client = await client._get_client()

    # Verify headers include API key
    assert http_client.headers.get("api-key") == "test-key"


# ============================================================================
# close TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_close_closes_client():
    """Test close closes HTTP client"""
    client = QdrantClient(qdrant_url="http://localhost:6333")
    await client._get_client()

    assert client._http_client is not None

    await client.close()

    assert client._http_client is None


@pytest.mark.asyncio
async def test_close_idempotent():
    """Test close can be called multiple times safely"""
    client = QdrantClient(qdrant_url="http://localhost:6333")
    await client._get_client()

    await client.close()
    await client.close()  # Should not raise

    assert client._http_client is None


# ============================================================================
# CONTEXT MANAGER TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_context_manager_creates_client():
    """Test async context manager creates client"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    async with client as ctx:
        assert ctx is client
        assert ctx._http_client is not None

    # Client should be closed after context
    assert client._http_client is None


@pytest.mark.asyncio
async def test_context_manager_closes_on_exit():
    """Test context manager closes client on exit"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    async with client:
        pass

    assert client._http_client is None


# ============================================================================
# _get_headers TESTS
# ============================================================================


def test_get_headers_without_api_key():
    """Test _get_headers without API key"""
    # Mock settings to have no API key
    mock_settings = MagicMock()
    mock_settings.qdrant_api_key = None

    with patch("core.qdrant_db.settings", mock_settings):
        client = QdrantClient(qdrant_url="http://localhost:6333", api_key=None)

        headers = client._get_headers()

        assert headers["Content-Type"] == "application/json"
        assert "api-key" not in headers


def test_get_headers_with_api_key():
    """Test _get_headers with API key"""
    client = QdrantClient(qdrant_url="http://localhost:6333", api_key="test-key")

    headers = client._get_headers()

    assert headers["Content-Type"] == "application/json"
    assert headers["api-key"] == "test-key"


# ============================================================================
# _convert_filter_to_qdrant_format TESTS
# ============================================================================


def test_convert_filter_empty():
    """Test _convert_filter_to_qdrant_format with empty filter"""
    client = QdrantClient()

    result = client._convert_filter_to_qdrant_format({})

    assert result is None


def test_convert_filter_direct_value():
    """Test _convert_filter_to_qdrant_format with direct value match"""
    client = QdrantClient()

    result = client._convert_filter_to_qdrant_format({"status": "active"})

    assert result is not None
    assert "must" in result
    assert len(result["must"]) == 1
    assert result["must"][0]["key"] == "metadata.status"
    assert result["must"][0]["match"]["value"] == "active"


def test_convert_filter_in_operator():
    """Test _convert_filter_to_qdrant_format with $in operator"""
    client = QdrantClient()

    result = client._convert_filter_to_qdrant_format({"tier": {"$in": ["S", "A"]}})

    assert result is not None
    assert "must" in result
    assert result["must"][0]["key"] == "metadata.tier"
    assert result["must"][0]["match"]["any"] == ["S", "A"]


def test_convert_filter_ne_operator():
    """Test _convert_filter_to_qdrant_format with $ne operator"""
    client = QdrantClient()

    result = client._convert_filter_to_qdrant_format({"status": {"$ne": "inactive"}})

    assert result is not None
    assert "must_not" in result
    assert result["must_not"][0]["key"] == "metadata.status"
    assert result["must_not"][0]["match"]["value"] == "inactive"


def test_convert_filter_nin_operator():
    """Test _convert_filter_to_qdrant_format with $nin operator"""
    client = QdrantClient()

    result = client._convert_filter_to_qdrant_format({"status": {"$nin": ["deleted", "archived"]}})

    assert result is not None
    assert "must_not" in result
    assert len(result["must_not"]) == 2  # One for each excluded value


def test_convert_filter_multiple_conditions():
    """Test _convert_filter_to_qdrant_format with multiple conditions"""
    client = QdrantClient()

    result = client._convert_filter_to_qdrant_format(
        {"status": "active", "tier": {"$in": ["S", "A"]}, "archived": {"$ne": True}}
    )

    assert result is not None
    assert "must" in result
    assert "must_not" in result
    assert len(result["must"]) == 2  # status and tier
    assert len(result["must_not"]) == 1  # archived


def test_convert_filter_in_empty_list():
    """Test _convert_filter_to_qdrant_format with empty $in list"""
    client = QdrantClient()

    result = client._convert_filter_to_qdrant_format({"tier": {"$in": []}})

    # Empty $in should not create a condition
    assert result is None or "must" not in result or len(result.get("must", [])) == 0


# ============================================================================
# search TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_search_success():
    """Test search returns results successfully"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "result": [
            {"id": "1", "score": 0.9, "payload": {"text": "Document 1", "metadata": {"tier": "S"}}},
            {"id": "2", "score": 0.8, "payload": {"text": "Document 2", "metadata": {"tier": "A"}}},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    client._http_client = mock_client

    result = await client.search([0.1] * 1536, limit=5)

    assert result["total_found"] == 2
    assert len(result["ids"]) == 2
    assert len(result["documents"]) == 2
    assert result["ids"][0] == "1"
    assert result["documents"][0] == "Document 1"


@pytest.mark.asyncio
async def test_search_with_filter():
    """Test search with metadata filter"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response = MagicMock()
    mock_response.json.return_value = {"result": []}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    client._http_client = mock_client

    result = await client.search([0.1] * 1536, filter={"tier": "S"}, limit=5)

    # Verify filter was included in request
    call_args = mock_client.post.call_args
    assert "filter" in call_args[1]["json"]


@pytest.mark.asyncio
async def test_search_empty_embedding():
    """Test search raises ValueError for empty embedding"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    with pytest.raises(ValueError, match="query_embedding cannot be empty"):
        await client.search([])


@pytest.mark.asyncio
async def test_search_invalid_embedding_type():
    """Test search raises TypeError for invalid embedding type"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    with pytest.raises(TypeError, match="query_embedding must be list of numbers"):
        await client.search(["not", "numbers"])


@pytest.mark.asyncio
async def test_search_timeout():
    """Test search handles timeout"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
    client._http_client = mock_client

    # TimeoutException raises TimeoutError which triggers retry
    # After all retries fail, search returns empty results (caught in outer try-except)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await client.search([0.1] * 1536)

    # Should return empty results after retries fail
    assert result["total_found"] == 0


@pytest.mark.asyncio
async def test_search_5xx_error_triggers_retry():
    """Test search retries on 5xx errors"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response_error = MagicMock()
    mock_response_error.status_code = 500
    mock_response_error.text = "Internal Server Error"

    mock_response_success = MagicMock()
    mock_response_success.json.return_value = {"result": []}
    mock_response_success.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        side_effect=[
            httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=mock_response_error
            ),
            mock_response_success,
        ]
    )
    client._http_client = mock_client

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await client.search([0.1] * 1536)

    assert result["total_found"] == 0


@pytest.mark.asyncio
async def test_search_4xx_error_returns_empty():
    """Test search returns empty results on 4xx errors"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        side_effect=httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)
    )
    client._http_client = mock_client

    result = await client.search([0.1] * 1536)

    assert result["total_found"] == 0
    assert len(result["ids"]) == 0


@pytest.mark.asyncio
async def test_search_connection_error():
    """Test search handles connection errors"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
    client._http_client = mock_client

    # RequestError raises ConnectionError which triggers retry
    # After all retries fail, search returns empty results (caught in outer try-except)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await client.search([0.1] * 1536)

    # Should return empty results after retries fail (caught by outer exception handler)
    assert result["total_found"] == 0


@pytest.mark.asyncio
async def test_search_all_retries_fail():
    """Test search returns empty results after all retries fail"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Server Error"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )
    )
    client._http_client = mock_client

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await client.search([0.1] * 1536)

    # Should return empty results after retries fail
    assert result["total_found"] == 0


# ============================================================================
# get_collection_stats TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_get_collection_stats_success():
    """Test get_collection_stats returns stats successfully"""
    client = QdrantClient(qdrant_url="http://localhost:6333", collection_name="test_collection")

    mock_response = MagicMock()
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

    assert stats["collection_name"] == "test_collection"
    assert stats["total_documents"] == 1000
    assert stats["vector_size"] == 1536
    assert stats["distance"] == "Cosine"
    assert stats["status"] == "green"


@pytest.mark.asyncio
async def test_get_collection_stats_http_error():
    """Test get_collection_stats handles HTTP errors"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response = MagicMock()
    mock_response.status_code = 404

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(
        side_effect=httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)
    )
    client._http_client = mock_client

    stats = await client.get_collection_stats()

    assert "error" in stats
    assert "404" in stats["error"]


@pytest.mark.asyncio
async def test_get_collection_stats_request_error():
    """Test get_collection_stats handles request errors"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
    client._http_client = mock_client

    stats = await client.get_collection_stats()

    assert "error" in stats
    assert "Connection failed" in stats["error"]


@pytest.mark.asyncio
async def test_get_collection_stats_exception():
    """Test get_collection_stats handles general exceptions"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("Unexpected error"))
    client._http_client = mock_client

    stats = await client.get_collection_stats()

    assert "error" in stats


# ============================================================================
# create_collection TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_create_collection_success():
    """Test create_collection creates collection successfully"""
    client = QdrantClient(qdrant_url="http://localhost:6333", collection_name="new_collection")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    client._http_client = mock_client

    result = await client.create_collection(vector_size=384, distance="Cosine")

    assert result is True
    call_args = mock_client.put.call_args
    assert call_args[1]["json"]["vectors"]["size"] == 384
    assert call_args[1]["json"]["vectors"]["distance"] == "Cosine"


@pytest.mark.asyncio
async def test_create_collection_with_on_disk_payload():
    """Test create_collection with on_disk_payload"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    client._http_client = mock_client

    result = await client.create_collection(on_disk_payload=True)

    assert result is True
    call_args = mock_client.put.call_args
    assert call_args[1]["json"]["on_disk_payload"] is True


@pytest.mark.asyncio
async def test_create_collection_http_error():
    """Test create_collection handles HTTP errors"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Bad request", request=MagicMock(), response=mock_response
        )
    )
    client._http_client = mock_client

    result = await client.create_collection()

    assert result is False


@pytest.mark.asyncio
async def test_create_collection_request_error():
    """Test create_collection handles request errors"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
    client._http_client = mock_client

    result = await client.create_collection()

    assert result is False


@pytest.mark.asyncio
async def test_create_collection_exception():
    """Test create_collection handles exceptions"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(side_effect=Exception("Unexpected error"))
    client._http_client = mock_client

    result = await client.create_collection()

    assert result is False


# ============================================================================
# upsert_documents TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_upsert_documents_success():
    """Test upsert_documents inserts documents successfully"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    client._http_client = mock_client

    chunks = ["Doc 1", "Doc 2"]
    embeddings = [[0.1] * 1536, [0.2] * 1536]
    metadatas = [{"tier": "S"}, {"tier": "A"}]

    result = await client.upsert_documents(chunks, embeddings, metadatas)

    assert result["success"] is True
    assert result["documents_added"] == 2
    assert result["collection"] == "knowledge_base"


@pytest.mark.asyncio
async def test_upsert_documents_with_ids():
    """Test upsert_documents with provided IDs"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    client._http_client = mock_client

    chunks = ["Doc 1"]
    embeddings = [[0.1] * 1536]
    metadatas = [{"tier": "S"}]
    ids = ["custom-id-1"]

    result = await client.upsert_documents(chunks, embeddings, metadatas, ids=ids)

    assert result["success"] is True
    # Verify custom ID was used
    call_args = mock_client.put.call_args
    assert call_args[1]["json"]["points"][0]["id"] == "custom-id-1"


@pytest.mark.asyncio
async def test_upsert_documents_batching():
    """Test upsert_documents batches large uploads"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    client._http_client = mock_client

    # Create 1200 documents (should be batched into 3 batches of 500)
    chunks = [f"Doc {i}" for i in range(1200)]
    embeddings = [[0.1] * 1536] * 1200
    metadatas = [{"tier": "S"}] * 1200

    result = await client.upsert_documents(chunks, embeddings, metadatas, batch_size=500)

    assert result["success"] is True
    assert result["documents_added"] == 1200
    assert mock_client.put.call_count == 3  # 3 batches


@pytest.mark.asyncio
async def test_upsert_documents_length_mismatch():
    """Test upsert_documents raises ValueError for length mismatch"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    chunks = ["Doc 1", "Doc 2"]
    embeddings = [[0.1] * 1536]
    metadatas = [{"tier": "S"}]

    with pytest.raises(ValueError, match="must have same length"):
        await client.upsert_documents(chunks, embeddings, metadatas)


@pytest.mark.asyncio
async def test_upsert_documents_batch_error():
    """Test upsert_documents handles batch errors"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response_error = MagicMock()
    mock_response_error.status_code = 500
    mock_response_error.text = "Server Error"

    mock_response_success = MagicMock()
    mock_response_success.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(
        side_effect=[
            httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=mock_response_error
            ),
            mock_response_success,
        ]
    )
    client._http_client = mock_client

    chunks = ["Doc 1", "Doc 2"]
    embeddings = [[0.1] * 1536, [0.2] * 1536]
    metadatas = [{"tier": "S"}, {"tier": "A"}]

    result = await client.upsert_documents(chunks, embeddings, metadatas)

    assert result["success"] is False
    assert "error" in result
    assert result["documents_added"] >= 0  # Some batches may succeed


@pytest.mark.asyncio
async def test_upsert_documents_request_error():
    """Test upsert_documents handles request errors in batches"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_client = AsyncMock()
    # RequestError in batch is caught and added to errors list, doesn't raise
    mock_client.put = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
    client._http_client = mock_client

    chunks = ["Doc 1"]
    embeddings = [[0.1] * 1536]
    metadatas = [{"tier": "S"}]

    # RequestError in batch is caught, added to errors, returns failure result
    result = await client.upsert_documents(chunks, embeddings, metadatas)

    assert result["success"] is False
    assert "error" in result
    assert "Request error" in result["error"]


# ============================================================================
# get TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_get_success():
    """Test get retrieves points successfully"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "result": [
            {
                "id": "1",
                "vector": [0.1] * 1536,
                "payload": {"text": "Doc 1", "metadata": {"tier": "S"}},
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
    assert result["documents"][0] == "Doc 1"
    assert len(result["embeddings"]) == 1


@pytest.mark.asyncio
async def test_get_with_include():
    """Test get with include parameter"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response = MagicMock()
    mock_response.json.return_value = {"result": []}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    client._http_client = mock_client

    await client.get(["1"], include=["payload", "embeddings"])

    # Verify params were set correctly
    call_args = mock_client.post.call_args
    assert call_args[1]["params"]["with_payload"] is True
    assert call_args[1]["params"]["with_vectors"] is True


@pytest.mark.asyncio
async def test_get_http_error():
    """Test get handles HTTP errors"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        side_effect=httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)
    )
    client._http_client = mock_client

    result = await client.get(["1"])

    assert len(result["ids"]) == 0


@pytest.mark.asyncio
async def test_get_request_error():
    """Test get handles request errors"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
    client._http_client = mock_client

    result = await client.get(["1"])

    assert len(result["ids"]) == 0


@pytest.mark.asyncio
async def test_get_exception():
    """Test get handles exceptions"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("Unexpected error"))
    client._http_client = mock_client

    result = await client.get(["1"])

    assert len(result["ids"]) == 0


# ============================================================================
# delete TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_delete_success():
    """Test delete deletes points successfully"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    client._http_client = mock_client

    result = await client.delete(["1", "2"])

    assert result["success"] is True
    assert result["deleted_count"] == 2


@pytest.mark.asyncio
async def test_delete_http_error():
    """Test delete handles HTTP errors"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        side_effect=httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)
    )
    client._http_client = mock_client

    result = await client.delete(["1"])

    assert result["success"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_delete_request_error():
    """Test delete raises ConnectionError on request errors"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
    client._http_client = mock_client

    with pytest.raises(ConnectionError):
        await client.delete(["1"])


@pytest.mark.asyncio
async def test_delete_exception():
    """Test delete raises exception on error"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("Unexpected error"))
    client._http_client = mock_client

    with pytest.raises(Exception):
        await client.delete(["1"])


# ============================================================================
# peek TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_peek_success():
    """Test peek returns sample points"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "result": {"points": [{"id": "1", "payload": {"text": "Doc 1", "metadata": {"tier": "S"}}}]}
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    client._http_client = mock_client

    result = await client.peek(limit=10)

    assert len(result["ids"]) == 1
    assert result["ids"][0] == "1"
    assert result["documents"][0] == "Doc 1"


@pytest.mark.asyncio
async def test_peek_http_error():
    """Test peek handles HTTP errors"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_response = MagicMock()
    mock_response.status_code = 404

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        side_effect=httpx.HTTPStatusError("Not found", request=MagicMock(), response=mock_response)
    )
    client._http_client = mock_client

    result = await client.peek()

    assert len(result["ids"]) == 0


@pytest.mark.asyncio
async def test_peek_request_error():
    """Test peek handles request errors"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
    client._http_client = mock_client

    result = await client.peek()

    assert len(result["ids"]) == 0


@pytest.mark.asyncio
async def test_peek_exception():
    """Test peek handles exceptions"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("Unexpected error"))
    client._http_client = mock_client

    result = await client.peek()

    assert len(result["ids"]) == 0


# ============================================================================
# collection PROPERTY TESTS
# ============================================================================


def test_collection_property():
    """Test collection property returns self"""
    client = QdrantClient(qdrant_url="http://localhost:6333")

    assert client.collection is client
