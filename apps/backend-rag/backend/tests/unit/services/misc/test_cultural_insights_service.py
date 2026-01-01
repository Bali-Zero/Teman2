"""
Unit tests for CulturalInsightsService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
    async def test_query_insights(self, cultural_insights_service):
        """Test querying cultural insights"""
        result = await cultural_insights_service.query_insights("business query")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_query_insights_empty(self, cultural_insights_service):
        """Test querying insights with empty results"""
        cultural_insights_service.collection_manager.get_collection.return_value = None
        result = await cultural_insights_service.query_insights("business query")
        assert isinstance(result, list)
