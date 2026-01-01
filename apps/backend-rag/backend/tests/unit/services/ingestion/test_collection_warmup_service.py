"""
Unit tests for CollectionWarmupService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.ingestion.collection_warmup_service import CollectionWarmupService


@pytest.fixture
def mock_collection_manager():
    """Mock collection manager"""
    manager = MagicMock()
    return manager


@pytest.fixture
def mock_embedder():
    """Mock embedder"""
    embedder = MagicMock()
    embedder.generate_query_embedding = MagicMock(return_value=[0.1] * 384)
    return embedder


@pytest.fixture
def warmup_service(mock_collection_manager, mock_embedder):
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
        assert len(service.priority_collections) > 0

    @pytest.mark.asyncio
    async def test_warmup_collection_success(self, warmup_service, mock_collection_manager):
        """Test warming up a collection successfully"""
        mock_vector_db = AsyncMock()
        mock_vector_db.search = AsyncMock(return_value={"documents": []})
        mock_collection_manager.get_collection = MagicMock(return_value=mock_vector_db)
        result = await warmup_service.warmup_collection("visa_oracle")
        assert result is True

    @pytest.mark.asyncio
    async def test_warmup_collection_not_found(self, warmup_service, mock_collection_manager):
        """Test warming up non-existent collection"""
        mock_collection_manager.get_collection = MagicMock(return_value=None)
        result = await warmup_service.warmup_collection("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_warmup_priority_collections(self, warmup_service, mock_collection_manager):
        """Test warming up priority collections"""
        mock_vector_db = AsyncMock()
        mock_vector_db.search = AsyncMock(return_value={"documents": []})
        mock_collection_manager.get_collection = MagicMock(return_value=mock_vector_db)
        # Warmup each priority collection individually
        for collection in warmup_service.priority_collections:
            result = await warmup_service.warmup_collection(collection)
            assert isinstance(result, bool)

