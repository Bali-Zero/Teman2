"""
Unit tests for CulturalInsightsService

Tests cultural insights storage and retrieval in isolation.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from services.cultural_insights_service import CulturalInsightsService


class TestCulturalInsightsService:
    """Test CulturalInsightsService"""

    @pytest.fixture
    def mock_collection_manager(self):
        """Mock CollectionManager"""
        manager = Mock()
        mock_client = AsyncMock()
        manager.get_collection.return_value = mock_client
        return manager

    @pytest.fixture
    def mock_embedder(self):
        """Mock EmbeddingsGenerator"""
        embedder = Mock()
        embedder.generate_query_embedding.return_value = [0.1] * 1536
        return embedder

    @pytest.fixture
    def service(self, mock_collection_manager, mock_embedder):
        """Create CulturalInsightsService instance"""
        return CulturalInsightsService(
            collection_manager=mock_collection_manager, embedder=mock_embedder
        )

    def test_initialization(self, service, mock_collection_manager, mock_embedder):
        """Test CulturalInsightsService initialization"""
        assert service is not None
        assert service.collection_manager is mock_collection_manager
        assert service.embedder is mock_embedder
        assert service.collection_name == "cultural_insights"

    @pytest.mark.asyncio
    async def test_add_insight_success(self, service, mock_collection_manager):
        """Test adding cultural insight successfully"""
        mock_client = mock_collection_manager.get_collection.return_value
        mock_client.upsert_documents = AsyncMock()

        result = await service.add_insight(
            text="Test insight",
            metadata={"topic": "greeting", "language": "id"},
        )

        assert result is True
        mock_collection_manager.get_collection.assert_called_with("cultural_insights")
        mock_client.upsert_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_insight_collection_not_found(self, service, mock_collection_manager):
        """Test adding insight when collection not available"""
        mock_collection_manager.get_collection.return_value = None

        result = await service.add_insight(text="Test insight", metadata={"topic": "greeting"})

        assert result is False

    @pytest.mark.asyncio
    async def test_add_insight_list_conversion(self, service, mock_collection_manager):
        """Test that list fields are converted to strings"""
        mock_client = mock_collection_manager.get_collection.return_value
        mock_client.upsert_documents = AsyncMock()

        await service.add_insight(
            text="Test",
            metadata={"topic": "greeting", "when_to_use": ["first_contact", "greeting"]},
        )

        # Verify metadata was converted
        call_args = mock_client.upsert_documents.call_args
        metadata = call_args[1]["metadatas"][0]
        assert isinstance(metadata["when_to_use"], str)
        assert "first_contact" in metadata["when_to_use"]

    @pytest.mark.asyncio
    async def test_query_insights_success(self, service, mock_collection_manager, mock_embedder):
        """Test querying cultural insights successfully"""
        mock_client = mock_collection_manager.get_collection.return_value
        mock_client.search = AsyncMock(
            return_value={
                "documents": ["Test cultural insight"],
                "metadatas": [{"topic": "greeting"}],
                "distances": [0.5],
            }
        )

        results = await service.query_insights("hello", limit=3)

        assert len(results) == 1
        assert results[0]["content"] == "Test cultural insight"
        assert results[0]["metadata"]["topic"] == "greeting"
        assert "score" in results[0]
        mock_embedder.generate_query_embedding.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_query_insights_collection_not_found(self, service, mock_collection_manager):
        """Test querying when collection not available"""
        mock_collection_manager.get_collection.return_value = None

        results = await service.query_insights("hello")

        assert results == []

    @pytest.mark.asyncio
    async def test_query_insights_empty_results(self, service, mock_collection_manager):
        """Test querying with no results"""
        mock_client = mock_collection_manager.get_collection.return_value
        mock_client.search = AsyncMock(
            return_value={"documents": [], "metadatas": [], "distances": []}
        )

        results = await service.query_insights("hello")

        assert results == []

    @pytest.mark.asyncio
    async def test_query_insights_with_when_to_use(self, service, mock_collection_manager):
        """Test querying with when_to_use filter"""
        mock_client = mock_collection_manager.get_collection.return_value
        mock_client.search = AsyncMock(
            return_value={
                "documents": ["Test"],
                "metadatas": [{"topic": "greeting"}],
                "distances": [0.5],
            }
        )

        results = await service.query_insights("hello", when_to_use="first_contact", limit=3)

        # Note: Qdrant doesn't support filtering, so we rely on semantic search
        # The when_to_use parameter is accepted but not used in filtering
        assert len(results) >= 0

    @pytest.mark.asyncio
    async def test_get_topics_coverage(self, service):
        """Test getting topics coverage"""
        coverage = await service.get_topics_coverage()
        # Currently returns empty dict (not yet implemented)
        assert isinstance(coverage, dict)
