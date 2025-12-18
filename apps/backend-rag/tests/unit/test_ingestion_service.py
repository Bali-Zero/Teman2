"""
Unit tests for Ingestion Service
100% coverage target with comprehensive mocking
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.models import TierLevel
from services.ingestion_service import IngestionService

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def ingestion_service():
    """Create IngestionService instance"""
    with (
        patch("services.ingestion_service.TextChunker"),
        patch("services.ingestion_service.create_embeddings_generator") as mock_create_embedder,
        patch("services.ingestion_service.QdrantClient"),
        patch("services.ingestion_service.TierClassifier"),
        patch("services.ingestion_service.logger"),
    ):
        mock_embedder = MagicMock()
        mock_create_embedder.return_value = mock_embedder

        service = IngestionService()
        service.chunker = MagicMock()
        service.embedder = mock_embedder
        service.vector_db = MagicMock()
        service.classifier = MagicMock()
        return service


# ============================================================================
# Tests: Initialization
# ============================================================================


def test_ingestion_service_init(ingestion_service):
    """Test IngestionService initialization"""
    assert ingestion_service.chunker is not None
    assert ingestion_service.embedder is not None
    assert ingestion_service.vector_db is not None
    assert ingestion_service.classifier is not None


# ============================================================================
# Tests: ingest_book
# ============================================================================


@pytest.mark.asyncio
async def test_ingest_book_success(ingestion_service):
    """Test ingesting book successfully"""
    # Mock dependencies
    ingestion_service.chunker.semantic_chunk.return_value = [
        {"text": "Chunk 1", "chunk_index": 0, "total_chunks": 2},
        {"text": "Chunk 2", "chunk_index": 1, "total_chunks": 2},
    ]
    ingestion_service.embedder.generate_embeddings.return_value = [[0.1] * 384, [0.2] * 384]
    ingestion_service.classifier.classify_book_tier.return_value = TierLevel.D  # Public tier
    ingestion_service.classifier.get_min_access_level.return_value = 1

    with (
        patch("services.ingestion_service.get_document_info") as mock_info,
        patch("services.ingestion_service.auto_detect_and_parse") as mock_parse,
    ):
        mock_info.return_value = {"title": "Test Book", "author": "Test Author"}
        mock_parse.return_value = "Sample book text content here"

        result = await ingestion_service.ingest_book(file_path="/path/to/book.pdf", language="en")

        assert result["success"] is True
        assert result["book_title"] == "Test Book"
        assert result["book_author"] == "Test Author"
        assert result["chunks_created"] == 2
        ingestion_service.vector_db.upsert_documents.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_book_with_tier_override(ingestion_service):
    """Test ingesting book with tier override"""
    ingestion_service.chunker.semantic_chunk.return_value = [
        {"text": "Chunk 1", "chunk_index": 0, "total_chunks": 1}
    ]
    ingestion_service.embedder.generate_embeddings.return_value = [[0.1] * 384]
    ingestion_service.classifier.get_min_access_level.return_value = 3

    with (
        patch("services.ingestion_service.get_document_info"),
        patch("services.ingestion_service.auto_detect_and_parse") as mock_parse,
    ):
        mock_parse.return_value = "Sample text"

        result = await ingestion_service.ingest_book(
            file_path="/path/to/book.pdf",
            title="Custom Title",
            author="Custom Author",
            tier_override=TierLevel.S,  # Supreme tier
        )

        assert result["success"] is True
        assert result["tier"] == TierLevel.S.value
        # Should not call classifier.classify_book_tier when override provided
        ingestion_service.classifier.classify_book_tier.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_book_exception(ingestion_service):
    """Test ingesting book with exception"""
    with patch(
        "services.ingestion_service.get_document_info", side_effect=Exception("Parse error")
    ):
        result = await ingestion_service.ingest_book(file_path="/path/to/book.pdf")

        assert result["success"] is False
        assert "error" in result
        assert result["chunks_created"] == 0


@pytest.mark.asyncio
async def test_ingest_book_auto_detect_title_author(ingestion_service):
    """Test auto-detecting title and author"""
    ingestion_service.chunker.semantic_chunk.return_value = [
        {"text": "Chunk", "chunk_index": 0, "total_chunks": 1}
    ]
    ingestion_service.embedder.generate_embeddings.return_value = [[0.1] * 384]
    ingestion_service.classifier.classify_book_tier.return_value = TierLevel.D  # Public tier
    ingestion_service.classifier.get_min_access_level.return_value = 1

    with (
        patch("services.ingestion_service.get_document_info") as mock_info,
        patch("services.ingestion_service.auto_detect_and_parse"),
        patch("pathlib.Path.stem", "book_file"),
    ):
        mock_info.return_value = {"title": "Detected Title", "author": "Detected Author"}

        result = await ingestion_service.ingest_book(file_path="/path/to/book.pdf")

        assert result["book_title"] == "Detected Title"
        assert result["book_author"] == "Detected Author"
