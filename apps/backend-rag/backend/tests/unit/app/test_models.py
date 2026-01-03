"""
Unit tests for Pydantic models
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.models import (
    AccessLevel,
    BatchIngestionRequest,
    BookIngestionRequest,
    BookIngestionResponse,
    ChunkMetadata,
    SearchQuery,
    SearchResponse,
    SearchResult,
    TierLevel,
)


class TestTierLevel:
    """Tests for TierLevel enum"""

    def test_tier_level_values(self):
        """Test tier level enum values"""
        assert TierLevel.S == "S"
        assert TierLevel.A == "A"
        assert TierLevel.B == "B"
        assert TierLevel.C == "C"
        assert TierLevel.D == "D"


class TestAccessLevel:
    """Tests for AccessLevel enum"""

    def test_access_level_values(self):
        """Test access level enum values"""
        assert AccessLevel.LEVEL_0 == 0
        assert AccessLevel.LEVEL_1 == 1
        assert AccessLevel.LEVEL_2 == 2
        assert AccessLevel.LEVEL_3 == 3


class TestChunkMetadata:
    """Tests for ChunkMetadata model"""

    def test_chunk_metadata_creation(self):
        """Test creating ChunkMetadata"""
        metadata = ChunkMetadata(
            book_title="Test Book",
            book_author="Test Author",
            tier=TierLevel.A,
            min_level=1,
            chunk_index=0,
            page_number=1,
            language="en",
            topics=["test"],
            file_path="/path/to/file",
            total_chunks=10,
        )
        assert metadata.book_title == "Test Book"
        assert metadata.tier == TierLevel.A
        assert metadata.min_level == 1

    def test_chunk_metadata_defaults(self):
        """Test ChunkMetadata with defaults"""
        metadata = ChunkMetadata(
            book_title="Test",
            book_author="Author",
            tier=TierLevel.B,
            min_level=0,
            chunk_index=0,
            file_path="/path",
            total_chunks=1,
        )
        assert metadata.page_number is None
        assert metadata.language == "en"
        assert metadata.topics == []


class TestSearchQuery:
    """Tests for SearchQuery model"""

    def test_search_query_creation(self):
        """Test creating SearchQuery"""
        query = SearchQuery(
            query="test query",
            level=1,
            limit=10,
            tier_filter=[TierLevel.A],
            collection="test_collection",
        )
        assert query.query == "test query"
        assert query.level == 1
        assert query.limit == 10

    def test_search_query_defaults(self):
        """Test SearchQuery with defaults"""
        query = SearchQuery(query="test")
        assert query.level == 0
        assert query.limit == 5
        assert query.tier_filter is None
        assert query.collection is None

    def test_search_query_validation(self):
        """Test SearchQuery validation"""
        with pytest.raises(Exception):  # Pydantic validation error
            SearchQuery(query="")  # Empty query should fail

        with pytest.raises(Exception):
            SearchQuery(query="test", level=5)  # Level > 3 should fail

        with pytest.raises(Exception):
            SearchQuery(query="test", limit=100)  # Limit > 50 should fail


class TestSearchResult:
    """Tests for SearchResult model"""

    def test_search_result_creation(self):
        """Test creating SearchResult"""
        metadata = ChunkMetadata(
            book_title="Test",
            book_author="Author",
            tier=TierLevel.A,
            min_level=0,
            chunk_index=0,
            file_path="/path",
            total_chunks=1,
        )
        result = SearchResult(
            text="Result text",
            metadata=metadata,
            similarity_score=0.95,
        )
        assert result.text == "Result text"
        assert result.similarity_score == 0.95


class TestSearchResponse:
    """Tests for SearchResponse model"""

    def test_search_response_creation(self):
        """Test creating SearchResponse"""
        metadata = ChunkMetadata(
            book_title="Test",
            book_author="Author",
            tier=TierLevel.A,
            min_level=0,
            chunk_index=0,
            file_path="/path",
            total_chunks=1,
        )
        result = SearchResult(
            text="Result",
            metadata=metadata,
            similarity_score=0.9,
        )
        response = SearchResponse(
            query="test",
            results=[result],
            total_found=1,
            user_level=1,
            execution_time_ms=100.0,
        )
        assert response.query == "test"
        assert len(response.results) == 1
        assert response.total_found == 1


class TestBookIngestionRequest:
    """Tests for BookIngestionRequest model"""

    def test_book_ingestion_request_creation(self):
        """Test creating BookIngestionRequest"""
        request = BookIngestionRequest(
            file_path="/path/to/book.pdf",
            title="Test Book",
            author="Test Author",
            language="en",
            tier_override=TierLevel.A,
        )
        assert request.file_path == "/path/to/book.pdf"
        assert request.title == "Test Book"
        assert request.tier_override == TierLevel.A

    def test_book_ingestion_request_defaults(self):
        """Test BookIngestionRequest with defaults"""
        request = BookIngestionRequest(file_path="/path/to/book.pdf")
        assert request.title is None
        assert request.author is None
        assert request.language == "en"
        assert request.tier_override is None


class TestBookIngestionResponse:
    """Tests for BookIngestionResponse model"""

    def test_book_ingestion_response_creation(self):
        """Test creating BookIngestionResponse"""
        response = BookIngestionResponse(
            success=True,
            book_title="Test Book",
            book_author="Test Author",
            tier=TierLevel.A,
            chunks_created=100,
            message="Success",
            error=None,
        )
        assert response.success is True
        assert response.chunks_created == 100
        assert response.error is None


class TestBatchIngestionRequest:
    """Tests for BatchIngestionRequest model"""

    def test_batch_ingestion_request_creation(self):
        """Test creating BatchIngestionRequest"""
        request = BatchIngestionRequest(
            directory_path="/path/to/books",
            file_patterns=["*.pdf", "*.epub"],
            skip_existing=True,
        )
        assert request.directory_path == "/path/to/books"
        assert len(request.file_patterns) == 2
        assert request.skip_existing is True

    def test_batch_ingestion_request_defaults(self):
        """Test BatchIngestionRequest with defaults"""
        request = BatchIngestionRequest(directory_path="/path")
        assert "*.pdf" in request.file_patterns
        assert "*.epub" in request.file_patterns
        assert request.skip_existing is True




