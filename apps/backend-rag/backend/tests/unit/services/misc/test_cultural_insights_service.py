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
    collection = MagicMock()
    collection.upsert_documents = AsyncMock()
    collection.search = AsyncMock(return_value={"documents": [], "metadatas": [], "ids": []})
    manager.get_collection = MagicMock(return_value=collection)
    return manager


@pytest.fixture
def mock_embedder():
    """Mock embedder"""
    embedder = MagicMock()
    embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 384)
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
        assert service.collection_name == "cultural_insights"

    @pytest.mark.asyncio
    async def test_add_insight(self, cultural_insights_service, mock_collection_manager):
        """Test adding cultural insight"""
        metadata = {
            "topic": "greeting",
            "language": "id",
            "when_to_use": "first_contact",
            "tone": "friendly"
        }
        result = await cultural_insights_service.add_insight("Test insight", metadata)
        assert result is True
        collection = mock_collection_manager.get_collection("cultural_insights")
        collection.upsert_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_insight_list_when_to_use(self, cultural_insights_service, mock_collection_manager):
        """Test adding insight with list when_to_use"""
        metadata = {
            "topic": "greeting",
            "when_to_use": ["first_contact", "casual_chat"]
        }
        result = await cultural_insights_service.add_insight("Test insight", metadata)
        assert result is True

    @pytest.mark.asyncio
    async def test_add_insight_collection_not_found(self, cultural_insights_service, mock_collection_manager):
        """Test adding insight when collection not found"""
        mock_collection_manager.get_collection.return_value = None
        result = await cultural_insights_service.add_insight("Test insight", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_query_insights(self, cultural_insights_service, mock_collection_manager):
        """Test querying insights"""
        collection = mock_collection_manager.get_collection("cultural_insights")
        collection.search = AsyncMock(return_value={
            "documents": ["Test insight"],
            "metadatas": [{"topic": "greeting"}],
            "ids": ["insight1"]
        })
        result = await cultural_insights_service.query_insights("test query", limit=5)
        assert isinstance(result, list)
        collection.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_insights_with_when_to_use(self, cultural_insights_service, mock_collection_manager):
        """Test querying insights with when_to_use filter"""
        collection = mock_collection_manager.get_collection("cultural_insights")
        collection.search = AsyncMock(return_value={
            "documents": ["Test insight"],
            "metadatas": [{"topic": "greeting", "when_to_use": "first_contact"}],
            "ids": ["insight1"]
        })
        result = await cultural_insights_service.query_insights(
            "test query", when_to_use="first_contact", limit=5
        )
        assert isinstance(result, list)

