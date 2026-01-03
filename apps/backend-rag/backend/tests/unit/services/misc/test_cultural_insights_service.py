"""
Unit tests for CulturalInsightsService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.cultural_insights_service import CulturalInsightsService


@pytest.fixture
def mock_collection_manager():
    """Mock collection manager"""
    manager = MagicMock()
    mock_collection = MagicMock()
    mock_collection.search = AsyncMock(return_value={"ids": [], "documents": []})
    manager.get_collection = MagicMock(return_value=mock_collection)
    return manager


@pytest.fixture
def mock_embedder():
    """Mock embedder"""
    embedder = MagicMock()
    embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 1536)
    return embedder


@pytest.fixture
def cultural_insights_service(mock_collection_manager, mock_embedder):
    """Create CulturalInsightsService instance"""
    return CulturalInsightsService(
        collection_manager=mock_collection_manager,
        embedder=mock_embedder
    )


class TestCulturalInsightsService:
    """Tests for CulturalInsightsService"""

    def test_init(self, mock_collection_manager, mock_embedder):
        """Test initialization"""
        service = CulturalInsightsService(
            collection_manager=mock_collection_manager,
            embedder=mock_embedder
        )
        assert service.collection_manager == mock_collection_manager
        assert service.embedder == mock_embedder

    @pytest.mark.asyncio
    async def test_add_insight(self, cultural_insights_service):
        """Test adding cultural insight"""
        result = await cultural_insights_service.add_insight(
            text="Test insight",
            metadata={"topic": "business", "language": "en"}
        )
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_add_insight_no_collection(self, cultural_insights_service):
        """Test adding insight when collection not available"""
        cultural_insights_service.collection_manager.get_collection.return_value = None
        result = await cultural_insights_service.add_insight(
            text="Test insight",
            metadata={"topic": "business"}
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_add_insight_with_list_metadata(self, cultural_insights_service):
        """Test adding insight with list metadata (when_to_use)"""
        metadata = {
            "topic": "business",
            "when_to_use": ["first_contact", "casual_chat"],
        }
        result = await cultural_insights_service.add_insight(
            text="Test insight",
            metadata=metadata
        )
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_add_insight_error(self, cultural_insights_service):
        """Test handling error when adding insight"""
        cultural_insights_service.embedder.generate_query_embedding = MagicMock(
            side_effect=Exception("Embedding error")
        )
        result = await cultural_insights_service.add_insight(
            text="Test insight",
            metadata={"topic": "business"}
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_query_insights(self, cultural_insights_service):
        """Test querying cultural insights"""
        mock_collection = MagicMock()
        mock_collection.search = AsyncMock(return_value={
            "ids": ["id1"],
            "documents": ["Test document"],
            "metadatas": [{"topic": "business"}],
        })
        cultural_insights_service.collection_manager.get_collection.return_value = mock_collection

        result = await cultural_insights_service.query_insights("business query")
        assert isinstance(result, list)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_query_insights_empty(self, cultural_insights_service):
        """Test querying insights with empty results"""
        cultural_insights_service.collection_manager.get_collection.return_value = None
        result = await cultural_insights_service.query_insights("business query")
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_query_insights_with_when_to_use(self, cultural_insights_service):
        """Test querying insights with when_to_use filter"""
        mock_collection = MagicMock()
        mock_collection.search = AsyncMock(return_value={
            "ids": [],
            "documents": [],
            "metadatas": [],
        })
        cultural_insights_service.collection_manager.get_collection.return_value = mock_collection

        result = await cultural_insights_service.query_insights(
            "business query",
            when_to_use="first_contact"
        )
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_query_insights_error(self, cultural_insights_service):
        """Test handling error when querying insights"""
        mock_collection = MagicMock()
        mock_collection.search = AsyncMock(side_effect=Exception("Search error"))
        cultural_insights_service.collection_manager.get_collection.return_value = mock_collection

        result = await cultural_insights_service.query_insights("business query")
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_query_insights_with_results(self, cultural_insights_service):
        """Test querying insights with results"""
        mock_collection = MagicMock()
        mock_collection.search = AsyncMock(return_value={
            "ids": ["id1", "id2"],
            "documents": ["Doc 1", "Doc 2"],
            "metadatas": [{"topic": "business"}, {"topic": "casual"}],
            "distances": [0.1, 0.2],
        })
        cultural_insights_service.collection_manager.get_collection.return_value = mock_collection

        result = await cultural_insights_service.query_insights("business query")
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["score"] > 0

    @pytest.mark.asyncio
    async def test_query_insights_missing_distances(self, cultural_insights_service):
        """Test querying insights with missing distances"""
        mock_collection = MagicMock()
        mock_collection.search = AsyncMock(return_value={
            "ids": ["id1"],
            "documents": ["Doc 1"],
            "metadatas": [{"topic": "business"}],
            "distances": [],
        })
        cultural_insights_service.collection_manager.get_collection.return_value = mock_collection

        result = await cultural_insights_service.query_insights("business query")
        assert isinstance(result, list)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_topics_coverage(self, cultural_insights_service):
        """Test getting topics coverage"""
        result = await cultural_insights_service.get_topics_coverage()
        assert isinstance(result, dict)
