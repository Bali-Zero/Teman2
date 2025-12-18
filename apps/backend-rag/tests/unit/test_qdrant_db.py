"""
Unit tests for Qdrant DB Client (Async Operations)
100% coverage target with comprehensive mocking
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from core.qdrant_db import QdrantClient

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_settings():
    """Mock settings configuration"""
    with patch("core.qdrant_db.settings") as mock:
        mock.qdrant_url = "https://test-qdrant.example.com"
        yield mock


@pytest.fixture
def mock_httpx_client():
    """Mock httpx async client with proper response handling"""
    mock_client = AsyncMock()

    # Mock response object
    def create_mock_response(status_code=200, json_data=None, text=""):
        response = MagicMock()
        response.status_code = status_code
        response.text = text
        # json() is synchronous in httpx (not async)
        response.json = MagicMock(return_value=json_data or {})
        response.raise_for_status = MagicMock()
        return response

    # Initialize methods as AsyncMock
    mock_client.post = AsyncMock()
    mock_client.get = AsyncMock()
    mock_client.put = AsyncMock()
    mock_client.aclose = AsyncMock()

    # Store the create function for tests to use
    mock_client._create_response = create_mock_response

    yield mock_client


@pytest.fixture
def qdrant_client(mock_settings, mock_httpx_client):
    """Create a QdrantClient instance with mocked httpx"""
    with patch("core.qdrant_db.httpx.AsyncClient", return_value=mock_httpx_client):
        client = QdrantClient()
        # Pre-initialize the client to use our mock
        client._http_client = mock_httpx_client
        yield client


@pytest.fixture
def qdrant_client_custom():
    """Create a QdrantClient with custom parameters"""
    with patch("core.qdrant_db.settings") as mock_settings:
        mock_settings.qdrant_url = "https://custom-qdrant.example.com"
        return QdrantClient(
            qdrant_url="https://custom-qdrant.example.com", collection_name="custom_collection"
        )


# ============================================================================
# Tests for __init__
# ============================================================================


def test_init_with_default_settings(mock_settings):
    """Test initialization with default settings"""
    client = QdrantClient()
    assert client.qdrant_url == "https://test-qdrant.example.com"
    assert client.collection_name == "knowledge_base"


def test_init_with_custom_url(mock_settings):
    """Test initialization with custom URL"""
    client = QdrantClient(qdrant_url="https://custom.example.com")
    assert client.qdrant_url == "https://custom.example.com"
    assert client.collection_name == "knowledge_base"


def test_init_with_custom_collection(mock_settings):
    """Test initialization with custom collection name"""
    client = QdrantClient(collection_name="custom_collection")
    assert client.qdrant_url == "https://test-qdrant.example.com"
    assert client.collection_name == "custom_collection"


def test_init_with_url_trailing_slash(mock_settings):
    """Test initialization removes trailing slash from URL"""
    client = QdrantClient(qdrant_url="https://test.example.com/")
    assert client.qdrant_url == "https://test.example.com"


def test_init_with_settings_none():
    """Test initialization when settings is None (graceful fallback)"""
    with patch("core.qdrant_db.settings", None):
        client = QdrantClient()
        # Should use default fallback values
        assert client.qdrant_url == "http://localhost:6333"
        assert client.collection_name == "knowledge_base"
        assert client.api_key is None


# ============================================================================
# Tests for search method
# ============================================================================


@pytest.mark.asyncio
async def test_search_success(qdrant_client, mock_httpx_client):
    """Test successful search"""
    query_embedding = [0.1, 0.2, 0.3]
    mock_response = mock_httpx_client._create_response(
        status_code=200,
        json_data={
            "result": [
                {
                    "id": "1",
                    "score": 0.95,
                    "payload": {"text": "Test document", "metadata": {"source": "test"}},
                },
                {
                    "id": "2",
                    "score": 0.85,
                    "payload": {"text": "Another document", "metadata": {"source": "test2"}},
                },
            ]
        },
    )
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.search(query_embedding, limit=5)

    assert result["ids"] == ["1", "2"]
    assert result["documents"] == ["Test document", "Another document"]
    assert result["metadatas"] == [{"source": "test"}, {"source": "test2"}]
    assert len(result["distances"]) == 2
    assert result["distances"][0] == pytest.approx(0.05)  # 1.0 - 0.95
    assert result["distances"][1] == pytest.approx(0.15)  # 1.0 - 0.85
    assert result["total_found"] == 2

    # Verify request was made correctly
    mock_httpx_client.post.assert_called_once()
    call_args = mock_httpx_client.post.call_args
    assert call_args[0][0] == "/collections/knowledge_base/points/search"
    assert call_args[1]["json"] == {"vector": query_embedding, "limit": 5, "with_payload": True}


@pytest.mark.asyncio
async def test_search_with_filter(qdrant_client, mock_httpx_client):
    """Test search with filter (filter is now implemented)"""
    query_embedding = [0.1, 0.2, 0.3]
    filter_dict = {"tier": {"$in": ["S", "A"]}}
    mock_response = mock_httpx_client._create_response(status_code=200, json_data={"result": []})
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.search(query_embedding, filter=filter_dict, limit=5)

    # Verify filter was converted and included in payload
    call_args = mock_httpx_client.post.call_args
    assert call_args is not None
    payload = call_args[1].get("json", {})
    assert "filter" in payload
    assert payload["filter"] is not None
    # Verify filter structure (must conditions for $in)
    assert "must" in payload["filter"]


@pytest.mark.asyncio
async def test_search_http_error(qdrant_client, mock_httpx_client):
    """Test search with HTTP error response"""
    query_embedding = [0.1, 0.2, 0.3]
    # Make raise_for_status raise an HTTPStatusError
    error_response = httpx.Response(500, text="Internal Server Error")
    http_error = httpx.HTTPStatusError("Server Error", request=MagicMock(), response=error_response)
    mock_httpx_client.post.side_effect = http_error

    with patch("core.qdrant_db.logger") as mock_logger:
        # Mock asyncio.sleep to speed up retries
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await qdrant_client.search(query_embedding)

            assert result["ids"] == []
            assert result["documents"] == []
            assert result["metadatas"] == []
            assert result["distances"] == []
            assert result["total_found"] == 0
            # Multiple calls due to retries
            assert mock_logger.error.called


@pytest.mark.asyncio
async def test_search_exception(qdrant_client, mock_httpx_client):
    """Test search when exception occurs"""
    query_embedding = [0.1, 0.2, 0.3]
    mock_httpx_client.post.side_effect = httpx.RequestError(
        "Connection failed", request=MagicMock()
    )

    with patch("core.qdrant_db.logger") as mock_logger:
        # Mock asyncio.sleep to speed up retries
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await qdrant_client.search(query_embedding)

            assert result["ids"] == []
            assert result["documents"] == []
            assert result["metadatas"] == []
            assert result["distances"] == []
            assert result["total_found"] == 0
            # Multiple calls due to retries
            assert mock_logger.error.called


@pytest.mark.asyncio
async def test_search_empty_results(qdrant_client, mock_httpx_client):
    """Test search with empty results"""
    query_embedding = [0.1, 0.2, 0.3]
    mock_response = mock_httpx_client._create_response(status_code=200, json_data={"result": []})
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.search(query_embedding)

    assert result["ids"] == []
    assert result["documents"] == []
    assert result["metadatas"] == []
    assert result["distances"] == []
    assert result["total_found"] == 0


@pytest.mark.asyncio
async def test_search_missing_payload_fields(qdrant_client, mock_httpx_client):
    """Test search with missing payload fields"""
    query_embedding = [0.1, 0.2, 0.3]
    mock_response = mock_httpx_client._create_response(
        status_code=200,
        json_data={
            "result": [
                {"id": "1", "score": 0.95, "payload": {}},  # Missing text and metadata
                {"id": "2", "score": 0.85, "payload": {"text": "Only text"}},  # Missing metadata
            ]
        },
    )
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.search(query_embedding)

    assert result["ids"] == ["1", "2"]
    assert result["documents"] == ["", "Only text"]
    assert result["metadatas"] == [{}, {}]


@pytest.mark.asyncio
async def test_search_with_none_filter(qdrant_client, mock_httpx_client):
    """Test search with None filter"""
    query_embedding = [0.1, 0.2, 0.3]
    mock_response = mock_httpx_client._create_response(status_code=200, json_data={"result": []})
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.search(query_embedding, filter=None)

    assert result["total_found"] == 0
    # Verify no warning was logged for None filter
    with patch("core.qdrant_db.logger") as mock_logger:
        await qdrant_client.search(query_embedding, filter=None)
        mock_logger.warning.assert_not_called()


# ============================================================================
# Tests for get_collection_stats method
# ============================================================================


@pytest.mark.asyncio
async def test_get_collection_stats_success(qdrant_client, mock_httpx_client):
    """Test successful collection stats retrieval"""
    mock_response = mock_httpx_client._create_response(
        status_code=200,
        json_data={
            "result": {
                "points_count": 1000,
                "config": {
                    "params": {
                        "vectors": {"size": 1536, "distance": "Cosine"},
                    }
                },
                "status": "green",
            }
        },
    )
    mock_httpx_client.get.return_value = mock_response

    result = await qdrant_client.get_collection_stats()

    assert result["collection_name"] == "knowledge_base"
    assert result["total_documents"] == 1000
    assert result["vector_size"] == 1536
    assert result["distance"] == "Cosine"
    assert result["status"] == "green"

    # Verify call was made with relative path (base_url is set on client)
    call_args = mock_httpx_client.get.call_args
    assert call_args[0][0] == "/collections/knowledge_base"


@pytest.mark.asyncio
async def test_get_collection_stats_http_error(qdrant_client, mock_httpx_client):
    """Test collection stats with HTTP error"""
    # Create HTTPStatusError
    mock_request = MagicMock()
    mock_response = httpx.Response(404, text="Not Found")
    http_error = httpx.HTTPStatusError("Not Found", request=mock_request, response=mock_response)
    mock_httpx_client.get.side_effect = http_error

    with patch("core.qdrant_db.logger") as mock_logger:
        result = await qdrant_client.get_collection_stats()

        assert result["collection_name"] == "knowledge_base"
        assert "error" in result
        assert result["error"] == "HTTP 404"
        mock_logger.error.assert_called_once()


@pytest.mark.asyncio
async def test_get_collection_stats_exception(qdrant_client, mock_httpx_client):
    """Test collection stats when exception occurs"""
    mock_httpx_client.get.side_effect = httpx.Timeout("Timeout")

    with patch("core.qdrant_db.logger") as mock_logger:
        result = await qdrant_client.get_collection_stats()

        assert result["collection_name"] == "knowledge_base"
        assert "error" in result
        assert "Timeout" in result["error"]
        mock_logger.error.assert_called_once()


@pytest.mark.asyncio
async def test_get_collection_stats_missing_fields(qdrant_client, mock_httpx_client):
    """Test collection stats with missing fields in response"""
    mock_response = mock_httpx_client._create_response(
        status_code=200,
        json_data={
            "result": {
                "points_count": 500,
                # Missing config fields
                "status": "yellow",
            }
        },
    )
    mock_httpx_client.get.return_value = mock_response

    result = await qdrant_client.get_collection_stats()

    assert result["collection_name"] == "knowledge_base"
    assert result["total_documents"] == 500
    assert result["vector_size"] == 1536  # Default value
    assert result["distance"] == "Cosine"  # Default value
    assert result["status"] == "yellow"


@pytest.mark.asyncio
async def test_get_collection_stats_empty_result(qdrant_client, mock_httpx_client):
    """Test collection stats with empty result"""
    mock_response = mock_httpx_client._create_response(status_code=200, json_data={"result": {}})
    mock_httpx_client.get.return_value = mock_response

    result = await qdrant_client.get_collection_stats()

    assert result["collection_name"] == "knowledge_base"
    assert result["total_documents"] == 0
    assert result["vector_size"] == 1536  # Default value


# ============================================================================
# Tests for upsert_documents method
# ============================================================================


@pytest.mark.asyncio
async def test_upsert_documents_success_with_ids(qdrant_client, mock_httpx_client):
    """Test successful upsert with provided IDs"""
    chunks = ["Document 1", "Document 2"]
    embeddings = [[0.1, 0.2], [0.3, 0.4]]
    metadatas = [{"source": "test1"}, {"source": "test2"}]
    ids = ["id1", "id2"]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_httpx_client.put.return_value = mock_response

    with patch("core.qdrant_db.logger") as mock_logger:
        result = await qdrant_client.upsert_documents(chunks, embeddings, metadatas, ids=ids)

        assert result["success"] is True
        assert result["documents_added"] == 2
        assert result["collection"] == "knowledge_base"

        # Verify request payload
        call_args = mock_httpx_client.put.call_args
        assert "collections/knowledge_base/points" in call_args[0][0]
        payload = call_args[1]["json"]
        assert len(payload["points"]) == 2
        assert payload["points"][0]["id"] == "id1"
        assert payload["points"][0]["vector"] == [0.1, 0.2]
        assert payload["points"][0]["payload"]["text"] == "Document 1"
        assert payload["points"][0]["payload"]["metadata"] == {"source": "test1"}
        assert call_args[1]["params"] == {"wait": "true"}
        mock_logger.info.assert_called()


@pytest.mark.asyncio
async def test_upsert_documents_success_without_ids(qdrant_client, mock_httpx_client):
    """Test successful upsert without provided IDs (auto-generated)"""
    chunks = ["Document 1", "Document 2"]
    embeddings = [[0.1, 0.2], [0.3, 0.4]]
    metadatas = [{"source": "test1"}, {"source": "test2"}]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_httpx_client.put.return_value = mock_response

    # Patch uuid module where it's imported (inside the method)
    with patch("uuid.uuid4") as mock_uuid4:
        mock_uuid4.side_effect = [
            MagicMock(__str__=lambda x: "uuid1"),
            MagicMock(__str__=lambda x: "uuid2"),
        ]
        result = await qdrant_client.upsert_documents(chunks, embeddings, metadatas)

        assert result["success"] is True
        assert result["documents_added"] == 2

        # Verify UUIDs were generated
        call_args = mock_httpx_client.put.call_args
        payload = call_args[1]["json"]
        assert len(payload["points"]) == 2
        # UUIDs are converted to strings, so check they're present
        assert payload["points"][0]["id"] is not None
        assert payload["points"][1]["id"] is not None
        assert len(payload["points"][0]["id"]) > 0
        assert len(payload["points"][1]["id"]) > 0


@pytest.mark.asyncio
async def test_upsert_documents_http_error(qdrant_client, mock_httpx_client):
    """Test upsert with HTTP error response"""
    chunks = ["Document 1"]
    embeddings = [[0.1, 0.2]]
    metadatas = [{"source": "test1"}]

    # Create HTTPStatusError
    mock_request = MagicMock()
    mock_error_response = httpx.Response(400, text="Bad Request")
    http_error = httpx.HTTPStatusError(
        "Bad Request", request=mock_request, response=mock_error_response
    )
    mock_httpx_client.put.side_effect = http_error

    with patch("core.qdrant_db.logger") as mock_logger:
        result = await qdrant_client.upsert_documents(chunks, embeddings, metadatas)

        assert result["success"] is False
        assert "HTTP 400" in result["error"]
        assert result["collection"] == "knowledge_base"
        mock_logger.error.assert_called()


@pytest.mark.asyncio
async def test_upsert_documents_exception(qdrant_client, mock_httpx_client):
    """Test upsert when exception occurs"""
    chunks = ["Document 1"]
    embeddings = [[0.1, 0.2]]
    metadatas = [{"source": "test1"}]

    mock_httpx_client.put.side_effect = httpx.RequestError("Request failed", request=MagicMock())

    with patch("core.qdrant_db.logger") as mock_logger:
        # The implementation catches RequestError and returns error dict
        result = await qdrant_client.upsert_documents(chunks, embeddings, metadatas)

        assert result["success"] is False
        assert "Request error" in result["error"]
        mock_logger.error.assert_called()


@pytest.mark.asyncio
async def test_upsert_documents_empty_lists(qdrant_client, mock_httpx_client):
    """Test upsert with empty lists"""
    chunks = []
    embeddings = []
    metadatas = []

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_httpx_client.put.return_value = mock_response

    result = await qdrant_client.upsert_documents(chunks, embeddings, metadatas)

    assert result["success"] is True
    assert result["documents_added"] == 0
    # When empty, no API call is made (the loop doesn't execute)
    # OR the implementation still makes the call with empty points
    if mock_httpx_client.put.called:
        call_args = mock_httpx_client.put.call_args
        payload = call_args[1]["json"]
        assert payload["points"] == []


# ============================================================================
# Tests for collection property
# ============================================================================


def test_collection_property(qdrant_client):
    """Test collection property returns self"""
    assert qdrant_client.collection is qdrant_client


# ============================================================================
# Tests for get method
# ============================================================================


@pytest.mark.asyncio
async def test_get_success_with_all_fields(qdrant_client, mock_httpx_client):
    """Test successful get with all fields"""
    ids = ["id1", "id2"]
    mock_response = mock_httpx_client._create_response(
        status_code=200,
        json_data={
            "result": [
                {
                    "id": "id1",
                    "vector": [0.1, 0.2, 0.3],
                    "payload": {"text": "Document 1", "metadata": {"source": "test1"}},
                },
                {
                    "id": "id2",
                    "vector": [0.4, 0.5, 0.6],
                    "payload": {"text": "Document 2", "metadata": {"source": "test2"}},
                },
            ]
        },
    )
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.get(ids)

    assert result["ids"] == ["id1", "id2"]
    assert result["embeddings"] == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert result["documents"] == ["Document 1", "Document 2"]
    assert result["metadatas"] == [{"source": "test1"}, {"source": "test2"}]

    # Verify request
    call_args = mock_httpx_client.post.call_args
    assert "collections/knowledge_base/points" in call_args[0][0]
    assert call_args[1]["json"] == {"ids": ids}
    assert call_args[1]["params"] == {"with_payload": True, "with_vectors": True}


@pytest.mark.asyncio
async def test_get_with_payload_include(qdrant_client, mock_httpx_client):
    """Test get with payload include"""
    ids = ["id1"]
    mock_response = mock_httpx_client._create_response(
        status_code=200,
        json_data={
            "result": [
                {
                    "id": "id1",
                    "payload": {"text": "Document 1", "metadata": {"source": "test1"}},
                }
            ]
        },
    )
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.get(ids, include=["payload"])

    assert result["ids"] == ["id1"]
    assert result["documents"] == ["Document 1"]
    assert result["metadatas"] == [{"source": "test1"}]

    # Verify params
    call_args = mock_httpx_client.post.call_args
    assert call_args[1]["params"] == {"with_payload": True}


@pytest.mark.asyncio
async def test_get_with_embeddings_include(qdrant_client, mock_httpx_client):
    """Test get with embeddings include"""
    ids = ["id1"]
    mock_response = mock_httpx_client._create_response(
        status_code=200,
        json_data={
            "result": [
                {
                    "id": "id1",
                    "vector": [0.1, 0.2, 0.3],
                    "payload": {},
                }
            ]
        },
    )
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.get(ids, include=["embeddings"])

    assert result["ids"] == ["id1"]
    assert result["embeddings"] == [[0.1, 0.2, 0.3]]

    # Verify params
    call_args = mock_httpx_client.post.call_args
    assert call_args[1]["params"] == {"with_vectors": True}


@pytest.mark.asyncio
async def test_get_with_metadatas_include(qdrant_client, mock_httpx_client):
    """Test get with metadatas include (should include payload)"""
    ids = ["id1"]
    mock_response = mock_httpx_client._create_response(
        status_code=200,
        json_data={
            "result": [
                {
                    "id": "id1",
                    "payload": {"text": "Doc", "metadata": {"source": "test"}},
                }
            ]
        },
    )
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.get(ids, include=["metadatas"])

    assert result["metadatas"] == [{"source": "test"}]

    # Verify params
    call_args = mock_httpx_client.post.call_args
    assert call_args[1]["params"] == {"with_payload": True}


@pytest.mark.asyncio
async def test_get_with_multiple_includes(qdrant_client, mock_httpx_client):
    """Test get with multiple includes"""
    ids = ["id1"]
    mock_response = mock_httpx_client._create_response(
        status_code=200,
        json_data={
            "result": [
                {
                    "id": "id1",
                    "vector": [0.1, 0.2],
                    "payload": {"text": "Doc", "metadata": {"source": "test"}},
                }
            ]
        },
    )
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.get(ids, include=["embeddings", "payload", "metadatas"])

    assert result["ids"] == ["id1"]
    assert result["embeddings"] == [[0.1, 0.2]]
    assert result["documents"] == ["Doc"]
    assert result["metadatas"] == [{"source": "test"}]

    # Verify params
    call_args = mock_httpx_client.post.call_args
    assert call_args[1]["params"] == {"with_payload": True, "with_vectors": True}


@pytest.mark.asyncio
async def test_get_http_error(qdrant_client, mock_httpx_client):
    """Test get with HTTP error"""
    ids = ["id1"]
    # Create HTTPStatusError
    mock_request = MagicMock()
    mock_error_response = httpx.Response(404, text="Not Found")
    http_error = httpx.HTTPStatusError(
        "Not Found", request=mock_request, response=mock_error_response
    )
    mock_httpx_client.post.side_effect = http_error

    with patch("core.qdrant_db.logger") as mock_logger:
        result = await qdrant_client.get(ids)

        assert result["ids"] == []
        assert result["embeddings"] == []
        assert result["documents"] == []
        assert result["metadatas"] == []
        mock_logger.error.assert_called()


@pytest.mark.asyncio
async def test_get_exception(qdrant_client, mock_httpx_client):
    """Test get when exception occurs"""
    ids = ["id1"]
    mock_httpx_client.post.side_effect = httpx.RequestError("Request failed")

    with patch("core.qdrant_db.logger") as mock_logger:
        result = await qdrant_client.get(ids)

        assert result["ids"] == []
        assert result["embeddings"] == []
        assert result["documents"] == []
        assert result["metadatas"] == []
        mock_logger.error.assert_called_once()


@pytest.mark.asyncio
async def test_get_missing_vector(qdrant_client, mock_httpx_client):
    """Test get with missing vector field"""
    ids = ["id1"]
    mock_response = mock_httpx_client._create_response(
        status_code=200,
        json_data={
            "result": [
                {
                    "id": "id1",
                    # Missing vector
                    "payload": {"text": "Document 1", "metadata": {"source": "test1"}},
                }
            ]
        },
    )
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.get(ids)

    assert result["ids"] == ["id1"]
    assert result["embeddings"] == [None]
    assert result["documents"] == ["Document 1"]


@pytest.mark.asyncio
async def test_get_missing_payload_fields(qdrant_client, mock_httpx_client):
    """Test get with missing payload fields"""
    ids = ["id1"]
    mock_response = mock_httpx_client._create_response(
        status_code=200,
        json_data={
            "result": [
                {
                    "id": "id1",
                    "vector": [0.1, 0.2],
                    "payload": {},  # Missing text and metadata
                }
            ]
        },
    )
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.get(ids)

    assert result["ids"] == ["id1"]
    assert result["documents"] == [""]
    assert result["metadatas"] == [{}]


@pytest.mark.asyncio
async def test_get_empty_result(qdrant_client, mock_httpx_client):
    """Test get with empty result"""
    ids = ["id1"]
    mock_response = mock_httpx_client._create_response(status_code=200, json_data={"result": []})
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.get(ids)

    assert result["ids"] == []
    assert result["embeddings"] == []
    assert result["documents"] == []
    assert result["metadatas"] == []


# ============================================================================
# Tests for delete method
# ============================================================================


@pytest.mark.asyncio
async def test_delete_success(qdrant_client, mock_httpx_client):
    """Test successful delete"""
    ids = ["id1", "id2"]
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_httpx_client.post.return_value = mock_response

    with patch("core.qdrant_db.logger") as mock_logger:
        result = await qdrant_client.delete(ids)

        assert result["success"] is True
        assert result["deleted_count"] == 2

        # Verify request
        call_args = mock_httpx_client.post.call_args
        assert "collections/knowledge_base/points/delete" in call_args[0][0]
        assert call_args[1]["json"] == {"points": ids}
        assert call_args[1]["params"] == {"wait": "true"}
        mock_logger.info.assert_called()


@pytest.mark.asyncio
async def test_delete_http_error(qdrant_client, mock_httpx_client):
    """Test delete with HTTP error"""
    ids = ["id1"]
    # Create HTTPStatusError
    mock_request = MagicMock()
    mock_error_response = httpx.Response(404, text="Not Found")
    http_error = httpx.HTTPStatusError(
        "Not Found", request=mock_request, response=mock_error_response
    )
    mock_httpx_client.post.side_effect = http_error

    with patch("core.qdrant_db.logger") as mock_logger:
        result = await qdrant_client.delete(ids)

        assert result["success"] is False
        assert result["error"] == "HTTP 404"
        mock_logger.error.assert_called()


@pytest.mark.asyncio
async def test_delete_exception(qdrant_client, mock_httpx_client):
    """Test delete when exception occurs - raises ConnectionError"""
    ids = ["id1"]
    mock_httpx_client.post.side_effect = httpx.RequestError("Request failed", request=MagicMock())

    with patch("core.qdrant_db.logger") as mock_logger:
        with pytest.raises(ConnectionError):
            await qdrant_client.delete(ids)

        mock_logger.error.assert_called()


@pytest.mark.asyncio
async def test_delete_empty_ids(qdrant_client, mock_httpx_client):
    """Test delete with empty IDs list"""
    ids = []
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.delete(ids)

    assert result["success"] is True
    assert result["deleted_count"] == 0


# ============================================================================
# Tests for peek method
# ============================================================================


@pytest.mark.asyncio
async def test_peek_success(qdrant_client, mock_httpx_client):
    """Test successful peek"""
    mock_response = mock_httpx_client._create_response(
        status_code=200,
        json_data={
            "result": {
                "points": [
                    {
                        "id": "id1",
                        "payload": {"text": "Document 1", "metadata": {"source": "test1"}},
                    },
                    {
                        "id": "id2",
                        "payload": {"text": "Document 2", "metadata": {"source": "test2"}},
                    },
                ]
            }
        },
    )
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.peek(limit=10)

    assert result["ids"] == ["id1", "id2"]
    assert result["documents"] == ["Document 1", "Document 2"]
    assert result["metadatas"] == [{"source": "test1"}, {"source": "test2"}]

    # Verify request
    call_args = mock_httpx_client.post.call_args
    assert "collections/knowledge_base/points/scroll" in call_args[0][0]
    assert call_args[1]["json"] == {
        "limit": 10,
        "with_payload": True,
        "with_vectors": False,
    }


@pytest.mark.asyncio
async def test_peek_http_error(qdrant_client, mock_httpx_client):
    """Test peek with HTTP error"""
    # Create HTTPStatusError
    mock_request = MagicMock()
    mock_error_response = httpx.Response(500, text="Server Error")
    http_error = httpx.HTTPStatusError(
        "Server Error", request=mock_request, response=mock_error_response
    )
    mock_httpx_client.post.side_effect = http_error

    with patch("core.qdrant_db.logger") as mock_logger:
        result = await qdrant_client.peek()

        assert result["ids"] == []
        assert result["documents"] == []
        assert result["metadatas"] == []
        mock_logger.error.assert_called()


@pytest.mark.asyncio
async def test_peek_exception(qdrant_client, mock_httpx_client):
    """Test peek when exception occurs"""
    mock_httpx_client.post.side_effect = httpx.RequestError("Request failed")

    with patch("core.qdrant_db.logger") as mock_logger:
        result = await qdrant_client.peek()

        assert result["ids"] == []
        assert result["documents"] == []
        assert result["metadatas"] == []
        mock_logger.error.assert_called_once()


@pytest.mark.asyncio
async def test_peek_empty_points(qdrant_client, mock_httpx_client):
    """Test peek with empty points"""
    mock_response = mock_httpx_client._create_response(
        status_code=200, json_data={"result": {"points": []}}
    )
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.peek()

    assert result["ids"] == []
    assert result["documents"] == []
    assert result["metadatas"] == []


@pytest.mark.asyncio
async def test_peek_missing_payload_fields(qdrant_client, mock_httpx_client):
    """Test peek with missing payload fields"""
    mock_response = mock_httpx_client._create_response(
        status_code=200,
        json_data={
            "result": {
                "points": [
                    {
                        "id": "id1",
                        "payload": {},  # Missing text and metadata
                    }
                ]
            }
        },
    )
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.peek()

    assert result["ids"] == ["id1"]
    assert result["documents"] == [""]
    assert result["metadatas"] == [{}]


@pytest.mark.asyncio
async def test_peek_missing_points_key(qdrant_client, mock_httpx_client):
    """Test peek with missing points key in result"""
    mock_response = mock_httpx_client._create_response(
        status_code=200,
        json_data={"result": {}},  # Missing points key
    )
    mock_httpx_client.post.return_value = mock_response

    result = await qdrant_client.peek()

    assert result["ids"] == []
    assert result["documents"] == []
    assert result["metadatas"] == []


@pytest.mark.asyncio
async def test_peek_custom_limit(qdrant_client, mock_httpx_client):
    """Test peek with custom limit"""
    mock_response = mock_httpx_client._create_response(
        status_code=200, json_data={"result": {"points": []}}
    )
    mock_httpx_client.post.return_value = mock_response

    await qdrant_client.peek(limit=5)

    call_args = mock_httpx_client.post.call_args
    assert call_args[1]["json"]["limit"] == 5
