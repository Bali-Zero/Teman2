"""
Unit tests for input validation in SearchService.

Tests the validation logic added to _prepare_search_context.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from services.search_service import SearchService


class TestSearchServiceInputValidation:
    """Test input validation in SearchService."""

    @pytest.fixture
    def mock_collection_manager(self):
        """Create mock collection manager"""
        mock_manager = MagicMock()
        mock_collection = MagicMock()
        mock_collection.search = AsyncMock(return_value={"documents": [], "distances": [], "metadatas": [], "ids": []})
        mock_manager.get_collection = MagicMock(return_value=mock_collection)
        return mock_manager

    @pytest.fixture
    def mock_query_router(self):
        """Create mock query router"""
        mock_router = MagicMock()
        mock_router.route_query = MagicMock(return_value={"collection_name": "visa_oracle", "confidence": 0.9})
        return mock_router

    @pytest.fixture
    def mock_embedder(self):
        """Create mock embedder"""
        mock_embedder = MagicMock()
        mock_embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 384)
        mock_embedder.provider = "test"
        mock_embedder.dimensions = 384
        return mock_embedder

    @pytest.fixture
    def search_service(self, mock_collection_manager, mock_query_router, mock_embedder):
        """Create SearchService instance"""
        service = SearchService(
            collection_manager=mock_collection_manager,
            query_router=mock_query_router,
        )
        service.embedder = mock_embedder
        return service

    def test_prepare_search_context_empty_query(self, search_service):
        """Test that empty query raises ValueError"""
        with pytest.raises(ValueError, match="Query cannot be empty"):
            search_service._prepare_search_context("", user_level=1, tier_filter=None, collection_override=None, apply_filters=None)

    def test_prepare_search_context_whitespace_only_query(self, search_service):
        """Test that whitespace-only query raises ValueError"""
        with pytest.raises(ValueError, match="Query cannot be empty"):
            search_service._prepare_search_context("   ", user_level=1, tier_filter=None, collection_override=None, apply_filters=None)

    def test_prepare_search_context_none_query(self, search_service):
        """Test that None query raises ValueError"""
        with pytest.raises((ValueError, AttributeError)):  # AttributeError if None.strip() is called
            search_service._prepare_search_context(None, user_level=1, tier_filter=None, collection_override=None, apply_filters=None)

    def test_prepare_search_context_user_level_negative(self, search_service):
        """Test that negative user_level raises ValueError"""
        with pytest.raises(ValueError, match="User level must be between 0 and 3"):
            search_service._prepare_search_context("test query", user_level=-1, tier_filter=None, collection_override=None, apply_filters=None)

    def test_prepare_search_context_user_level_too_high(self, search_service):
        """Test that user_level > 3 raises ValueError"""
        with pytest.raises(ValueError, match="User level must be between 0 and 3"):
            search_service._prepare_search_context("test query", user_level=4, tier_filter=None, collection_override=None, apply_filters=None)

    def test_prepare_search_context_empty_embedding(self, search_service, mock_embedder):
        """Test that empty embedding raises ValueError"""
        mock_embedder.generate_query_embedding.return_value = []
        with pytest.raises(ValueError, match="Failed to generate query embedding"):
            search_service._prepare_search_context("test query", user_level=1, tier_filter=None, collection_override=None, apply_filters=None)

    def test_prepare_search_context_none_embedding(self, search_service, mock_embedder):
        """Test that None embedding raises ValueError"""
        mock_embedder.generate_query_embedding.return_value = None
        with pytest.raises(ValueError, match="Failed to generate query embedding"):
            search_service._prepare_search_context("test query", user_level=1, tier_filter=None, collection_override=None, apply_filters=None)

    def test_prepare_search_context_valid_inputs(self, search_service):
        """Test that valid inputs work correctly"""
        result = search_service._prepare_search_context(
            "test query", user_level=1, tier_filter=None, collection_override=None, apply_filters=None
        )
        assert result is not None
        query_embedding, collection_name, vector_db, chroma_filter, tier_values = result
        assert query_embedding is not None
        assert len(query_embedding) > 0
        assert collection_name == "visa_oracle"
        assert vector_db is not None

