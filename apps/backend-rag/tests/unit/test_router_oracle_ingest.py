"""
Unit tests for Oracle Ingest Router
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.routers.oracle_ingest import (
    DocumentChunk,
    IngestRequest,
    ingest_documents,
    list_collections,
)


@pytest.fixture
def mock_search_service():
    """Mock SearchService"""
    service = MagicMock()
    service.ingest_documents = AsyncMock(return_value={"success": True, "count": 10})
    return service


@pytest.fixture
def sample_ingest_request():
    """Create sample ingest request"""
    return IngestRequest(
        collection="legal_intelligence",
        documents=[
            DocumentChunk(
                content="Test document content with sufficient length",
                metadata={"law_id": "PP-28-2025", "pasal": "1"},
            )
        ],
        batch_size=100,
    )


# ============================================================================
# Tests for ingest_documents
# ============================================================================


@pytest.mark.asyncio
async def test_ingest_documents_success(mock_search_service, sample_ingest_request):
    """Test successful document ingestion"""
    # Mock the service to have collections
    mock_vector_db = MagicMock()
    mock_vector_db.upsert_documents = AsyncMock()
    mock_search_service.collections = {"legal_intelligence": mock_vector_db}

    # Mock EmbeddingsGenerator
    mock_embedder = MagicMock()
    mock_embedder.generate_batch_embeddings = MagicMock(
        return_value=[[0.1] * 1536]
    )  # Return embeddings

    with patch("backend.core.embeddings.create_embeddings_generator", return_value=mock_embedder):
        response = await ingest_documents(sample_ingest_request, mock_search_service)

        assert response.success is True
        assert response.collection == "legal_intelligence"
        assert response.documents_ingested == 1


@pytest.mark.asyncio
async def test_ingest_documents_empty_list(mock_search_service):
    """Test ingestion with empty document list - Pydantic validation prevents this"""
    # Pydantic will validate min_items=1 before reaching the endpoint
    # So we test that Pydantic validation works
    with pytest.raises(Exception):  # Pydantic validation error
        request = IngestRequest(
            collection="legal_intelligence",
            documents=[],  # This will fail Pydantic validation
        )


@pytest.mark.asyncio
async def test_ingest_documents_error_handling(mock_search_service, sample_ingest_request):
    """Test ingestion error handling"""
    # Mock the service to have collections but fail on embedding generation
    mock_vector_db = MagicMock()
    mock_search_service.collections = {"legal_intelligence": mock_vector_db}

    # Mock EmbeddingsGenerator to raise exception
    mock_embedder = MagicMock()
    mock_embedder.generate_batch_embeddings = MagicMock(side_effect=Exception("Embedding error"))

    with patch("backend.core.embeddings.create_embeddings_generator", return_value=mock_embedder):
        response = await ingest_documents(sample_ingest_request, mock_search_service)

        # The function catches exceptions and returns error response
        assert response.success is False
        assert "error" in response.error.lower() or "Embedding error" in response.error


@pytest.mark.asyncio
async def test_ingest_documents_auto_create_collection(mock_search_service, sample_ingest_request):
    """Test auto-creation of legal_intelligence collection when it doesn't exist"""
    # Mock service with empty collections
    mock_search_service.collections = {}

    # Mock QdrantClient to be created
    mock_qdrant_client = MagicMock()
    mock_qdrant_client.upsert_documents = AsyncMock()

    # Mock EmbeddingsGenerator
    mock_embedder = MagicMock()
    mock_embedder.generate_batch_embeddings = MagicMock(return_value=[[0.1] * 1536])

    with patch("backend.core.qdrant_db.QdrantClient", return_value=mock_qdrant_client) as mock_qdrant:
        with patch("backend.core.embeddings.create_embeddings_generator", return_value=mock_embedder):
            response = await ingest_documents(sample_ingest_request, mock_search_service)

            # Verify QdrantClient was instantiated with correct collection name
            mock_qdrant.assert_called_once_with(collection_name="legal_intelligence")

            # Verify collection was added to service.collections
            assert "legal_intelligence" in mock_search_service.collections

            # Verify ingestion succeeded
            assert response.success is True


@pytest.mark.asyncio
async def test_ingest_documents_collection_not_found():
    """Test error when collection doesn't exist and is not legal_intelligence"""
    # Mock service with empty collections
    mock_service = MagicMock()
    mock_service.collections = {}

    # Create request for a different collection
    request = IngestRequest(
        collection="unknown_collection",
        documents=[
            DocumentChunk(
                content="Test document content with sufficient length",
                metadata={"law_id": "TEST-1", "pasal": "1"},
            )
        ],
    )

    response = await ingest_documents(request, mock_service)

    assert response.success is False
    assert response.collection == "unknown_collection"
    assert response.documents_ingested == 0
    assert "not found" in response.error.lower()


@pytest.mark.asyncio
async def test_ingest_documents_multiple_documents(mock_search_service):
    """Test ingestion with multiple documents"""
    # Mock the service to have collections
    mock_vector_db = MagicMock()
    mock_vector_db.upsert_documents = AsyncMock()
    mock_search_service.collections = {"legal_intelligence": mock_vector_db}

    # Mock EmbeddingsGenerator
    mock_embedder = MagicMock()
    mock_embedder.generate_batch_embeddings = MagicMock(
        return_value=[[0.1] * 1536, [0.2] * 1536, [0.3] * 1536]
    )

    request = IngestRequest(
        collection="legal_intelligence",
        documents=[
            DocumentChunk(
                content="First document content with sufficient length here",
                metadata={"law_id": "PP-28-2025", "pasal": "1"},
            ),
            DocumentChunk(
                content="Second document content with sufficient length here",
                metadata={"law_id": "PP-28-2025", "pasal": "2"},
            ),
            DocumentChunk(
                content="Third document content with sufficient length here",
                metadata={"law_id": "PP-29-2025", "pasal": "1"},
            ),
        ],
        batch_size=100,
    )

    with patch("backend.core.embeddings.create_embeddings_generator", return_value=mock_embedder):
        response = await ingest_documents(request, mock_search_service)

        assert response.success is True
        assert response.collection == "legal_intelligence"
        assert response.documents_ingested == 3
        assert response.execution_time_ms > 0
        assert mock_vector_db.upsert_documents.called
        # Verify upsert was called with correct number of documents
        call_args = mock_vector_db.upsert_documents.call_args
        assert len(call_args[1]["chunks"]) == 3
        assert len(call_args[1]["embeddings"]) == 3
        assert len(call_args[1]["ids"]) == 3


@pytest.mark.asyncio
async def test_ingest_documents_metadata_missing_fields(mock_search_service):
    """Test ingestion with metadata missing law_id and pasal"""
    # Mock the service to have collections
    mock_vector_db = MagicMock()
    mock_vector_db.upsert_documents = AsyncMock()
    mock_search_service.collections = {"legal_intelligence": mock_vector_db}

    # Mock EmbeddingsGenerator
    mock_embedder = MagicMock()
    mock_embedder.generate_batch_embeddings = MagicMock(return_value=[[0.1] * 1536])

    request = IngestRequest(
        collection="legal_intelligence",
        documents=[
            DocumentChunk(
                content="Test document content with sufficient length",
                metadata={"category": "test"},  # No law_id or pasal
            )
        ],
        batch_size=100,
    )

    with patch("backend.core.embeddings.create_embeddings_generator", return_value=mock_embedder):
        response = await ingest_documents(request, mock_search_service)

        assert response.success is True
        assert response.documents_ingested == 1
        # Verify ID was generated with UNKNOWN and index
        call_args = mock_vector_db.upsert_documents.call_args
        assert "UNKNOWN_pasal_0_0" in call_args[1]["ids"]


@pytest.mark.asyncio
async def test_ingest_documents_upsert_failure(mock_search_service, sample_ingest_request):
    """Test ingestion when upsert_documents fails"""
    # Mock the service to have collections
    mock_vector_db = MagicMock()
    mock_vector_db.upsert_documents = AsyncMock(side_effect=Exception("Upsert error"))
    mock_search_service.collections = {"legal_intelligence": mock_vector_db}

    # Mock EmbeddingsGenerator
    mock_embedder = MagicMock()
    mock_embedder.generate_batch_embeddings = MagicMock(return_value=[[0.1] * 1536])

    with patch("backend.core.embeddings.create_embeddings_generator", return_value=mock_embedder):
        response = await ingest_documents(sample_ingest_request, mock_search_service)

        assert response.success is False
        assert response.collection == "legal_intelligence"
        assert response.documents_ingested == 0
        assert "Upsert error" in response.error or "error" in response.error.lower()
        assert response.execution_time_ms > 0


@pytest.mark.asyncio
async def test_ingest_documents_execution_time(mock_search_service, sample_ingest_request):
    """Test that execution_time_ms is calculated correctly"""
    # Mock the service to have collections
    mock_vector_db = MagicMock()
    mock_vector_db.upsert_documents = AsyncMock()
    mock_search_service.collections = {"legal_intelligence": mock_vector_db}

    # Mock EmbeddingsGenerator
    mock_embedder = MagicMock()
    mock_embedder.generate_batch_embeddings = MagicMock(return_value=[[0.1] * 1536])

    with patch("backend.core.embeddings.create_embeddings_generator", return_value=mock_embedder):
        response = await ingest_documents(sample_ingest_request, mock_search_service)

        assert response.success is True
        assert response.execution_time_ms >= 0
        assert isinstance(response.execution_time_ms, float)


@pytest.mark.asyncio
async def test_ingest_documents_batch_size_validation():
    """Test IngestRequest batch_size validation"""
    # Test batch_size too small
    with pytest.raises(ValidationError) as exc_info:
        IngestRequest(
            collection="legal_intelligence",
            documents=[
                DocumentChunk(
                    content="Test document content with sufficient length",
                    metadata={"law_id": "TEST-1"},
                )
            ],
            batch_size=5,  # Less than minimum 10
        )
    assert "greater than or equal to 10" in str(exc_info.value)

    # Test batch_size too large
    with pytest.raises(ValidationError) as exc_info:
        IngestRequest(
            collection="legal_intelligence",
            documents=[
                DocumentChunk(
                    content="Test document content with sufficient length",
                    metadata={"law_id": "TEST-1"},
                )
            ],
            batch_size=600,  # Greater than maximum 500
        )
    assert "less than or equal to 500" in str(exc_info.value)

    # Test valid batch_size at boundaries
    request_min = IngestRequest(
        collection="legal_intelligence",
        documents=[
            DocumentChunk(
                content="Test document content with sufficient length",
                metadata={"law_id": "TEST-1"},
            )
        ],
        batch_size=10,  # Minimum
    )
    assert request_min.batch_size == 10

    request_max = IngestRequest(
        collection="legal_intelligence",
        documents=[
            DocumentChunk(
                content="Test document content with sufficient length",
                metadata={"law_id": "TEST-1"},
            )
        ],
        batch_size=500,  # Maximum
    )
    assert request_max.batch_size == 500


@pytest.mark.asyncio
async def test_ingest_documents_content_min_length():
    """Test DocumentChunk content min_length validation"""
    # Test content too short
    with pytest.raises(ValidationError) as exc_info:
        DocumentChunk(
            content="short",  # Less than minimum 10 characters
            metadata={"law_id": "TEST-1"},
        )
    assert "at least 10 characters" in str(
        exc_info.value
    ) or "ensure this value has at least 10 characters" in str(exc_info.value)

    # Test valid content
    chunk = DocumentChunk(
        content="This is a valid content with sufficient length",
        metadata={"law_id": "TEST-1"},
    )
    assert len(chunk.content) >= 10


@pytest.mark.asyncio
async def test_ingest_documents_max_items_validation():
    """Test IngestRequest max_items validation"""
    # Test too many documents
    too_many_docs = [
        DocumentChunk(
            content=f"Document {i} content with sufficient length here",
            metadata={"law_id": f"TEST-{i}"},
        )
        for i in range(1001)  # More than maximum 1000
    ]
    with pytest.raises(ValidationError) as exc_info:
        IngestRequest(
            collection="legal_intelligence",
            documents=too_many_docs,
        )
    assert "at most 1000 items" in str(
        exc_info.value
    ) or "ensure this value has at most 1000 items" in str(exc_info.value)


# ============================================================================
# Tests for list_collections
# ============================================================================


@pytest.mark.asyncio
async def test_list_collections_success(mock_search_service):
    """Test successfully listing collections"""
    # Mock collections with stats
    mock_vector_db1 = MagicMock()
    mock_vector_db1.get_collection_stats = MagicMock(return_value={"total_documents": 100})

    mock_vector_db2 = MagicMock()
    mock_vector_db2.get_collection_stats = MagicMock(return_value={"total_documents": 50})

    mock_search_service.collections = {
        "legal_intelligence": mock_vector_db1,
        "regulations": mock_vector_db2,
    }

    response = await list_collections(mock_search_service)

    assert response["success"] is True
    assert "legal_intelligence" in response["collections"]
    assert "regulations" in response["collections"]
    assert response["details"]["legal_intelligence"]["document_count"] == 100
    assert response["details"]["regulations"]["document_count"] == 50


@pytest.mark.asyncio
async def test_list_collections_stats_error(mock_search_service):
    """Test list_collections when getting stats fails for one collection"""
    # Mock one collection that raises error on get_collection_stats
    mock_vector_db1 = MagicMock()
    mock_vector_db1.get_collection_stats = MagicMock(side_effect=Exception("Stats error"))

    mock_vector_db2 = MagicMock()
    mock_vector_db2.get_collection_stats = MagicMock(return_value={"total_documents": 50})

    mock_search_service.collections = {
        "broken_collection": mock_vector_db1,
        "working_collection": mock_vector_db2,
    }

    response = await list_collections(mock_search_service)

    assert response["success"] is True
    assert "broken_collection" in response["collections"]
    assert response["details"]["broken_collection"]["document_count"] == 0
    assert "error" in response["details"]["broken_collection"]
    assert response["details"]["working_collection"]["document_count"] == 50


@pytest.mark.asyncio
async def test_list_collections_general_exception(mock_search_service):
    """Test list_collections when general exception occurs"""
    # Make collections property raise exception
    type(mock_search_service).collections = property(
        lambda self: (_ for _ in ()).throw(Exception("Critical error"))
    )

    with pytest.raises(HTTPException) as exc_info:
        await list_collections(mock_search_service)

    assert exc_info.value.status_code == 500
    assert "Critical error" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_list_collections_empty_collections(mock_search_service):
    """Test list_collections with empty collections"""
    mock_search_service.collections = {}

    response = await list_collections(mock_search_service)

    assert response["success"] is True
    assert response["collections"] == []
    assert response["details"] == {}


@pytest.mark.asyncio
async def test_list_collections_stats_missing_total_documents(mock_search_service):
    """Test list_collections when stats don't have total_documents"""
    # Mock collection with stats missing total_documents
    mock_vector_db = MagicMock()
    mock_vector_db.get_collection_stats = MagicMock(return_value={})  # Empty stats

    mock_search_service.collections = {"test_collection": mock_vector_db}

    response = await list_collections(mock_search_service)

    assert response["success"] is True
    assert "test_collection" in response["collections"]
    assert response["details"]["test_collection"]["document_count"] == 0


@pytest.mark.asyncio
async def test_list_collections_stats_with_extra_fields(mock_search_service):
    """Test list_collections when stats have extra fields"""
    # Mock collection with stats having extra fields
    mock_vector_db = MagicMock()
    mock_vector_db.get_collection_stats = MagicMock(
        return_value={"total_documents": 42, "extra_field": "value"}
    )

    mock_search_service.collections = {"test_collection": mock_vector_db}

    response = await list_collections(mock_search_service)

    assert response["success"] is True
    assert response["details"]["test_collection"]["document_count"] == 42
    assert response["details"]["test_collection"]["name"] == "test_collection"
