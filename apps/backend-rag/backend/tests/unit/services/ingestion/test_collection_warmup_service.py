"""
Unit tests for CollectionWarmupService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.ingestion.collection_warmup_service import CollectionWarmupService


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
def collection_warmup_service(mock_collection_manager, mock_embedder):
    """Create CollectionWarmupService instance"""
    return CollectionWarmupService(
        collection_manager=mock_collection_manager,
        embedder=mock_embedder
    )


class TestCollectionWarmupService:
    """Tests for CollectionWarmupService"""

    def test_init(self, mock_collection_manager, mock_embedder):
        """Test initialization"""
        service = CollectionWarmupService(
            collection_manager=mock_collection_manager,
            embedder=mock_embedder
        )
        assert service.collection_manager == mock_collection_manager
        assert service.embedder == mock_embedder

    @pytest.mark.asyncio
    async def test_warmup_collection(self, collection_warmup_service):
        """Test warming up a collection"""
        result = await collection_warmup_service.warmup_collection("test_collection")
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_warmup_collection_not_found(self, collection_warmup_service):
        """Test warming up non-existent collection"""
        collection_warmup_service.collection_manager.get_collection.return_value = None
        result = await collection_warmup_service.warmup_collection("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_warmup_all_collections(self, collection_warmup_service):
        """Test warming up all collections"""
        result = await collection_warmup_service.warmup_all_collections()
        assert isinstance(result, dict)
