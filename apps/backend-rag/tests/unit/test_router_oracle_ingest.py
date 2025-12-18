"""
Unit tests for Oracle Ingest Router
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers.oracle_ingest import (
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

    with patch("core.embeddings.create_embeddings_generator", return_value=mock_embedder):
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

    with patch("core.embeddings.create_embeddings_generator", return_value=mock_embedder):
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

    with patch("core.qdrant_db.QdrantClient", return_value=mock_qdrant_client) as mock_qdrant:
        with patch("core.embeddings.create_embeddings_generator", return_value=mock_embedder):
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
