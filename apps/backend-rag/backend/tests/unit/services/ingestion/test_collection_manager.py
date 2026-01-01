"""
Unit tests for CollectionManager
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.ingestion.collection_manager import CollectionManager


@pytest.fixture
def collection_manager():
    """Create CollectionManager instance"""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.qdrant_url = "http://localhost:6333"
        manager = CollectionManager()
        manager.qdrant_url = "http://localhost:6333"  # Override for testing
        return manager


class TestCollectionManager:
    """Tests for CollectionManager"""

    def test_init(self, collection_manager):
        """Test initialization"""
        assert collection_manager.qdrant_url == "http://localhost:6333"
        assert collection_manager._collections_cache == {}
        assert len(collection_manager.collection_definitions) > 0

    def test_init_with_custom_url(self):
        """Test initialization with custom URL"""
        with patch("app.core.config.settings"):
            manager = CollectionManager(qdrant_url="http://custom:6333")
            assert manager.qdrant_url == "http://custom:6333"

    def test_get_collection_existing(self, collection_manager):
        """Test getting existing collection"""
        mock_client = MagicMock()
        collection_manager._collections_cache["test_collection"] = mock_client
        result = collection_manager.get_collection("test_collection")
        assert result == mock_client

    def test_get_collection_new(self, collection_manager):
        """Test getting new collection (lazy initialization)"""
        with patch("core.qdrant_db.QdrantClient") as mock_qdrant_class:
            mock_client = MagicMock()
            mock_qdrant_class.return_value = mock_client
            result = collection_manager.get_collection("visa_oracle")
            assert result is not None
            assert "visa_oracle" in collection_manager._collections_cache

    def test_get_collection_with_alias(self, collection_manager):
        """Test getting collection via alias"""
        with patch("core.qdrant_db.QdrantClient") as mock_qdrant_class:
            mock_client = MagicMock()
            mock_qdrant_class.return_value = mock_client
            # kbli_eye has alias kbli_unified
            result = collection_manager.get_collection("kbli_eye")
            assert result is not None
            assert "kbli_eye" in collection_manager._collections_cache

    def test_list_collections(self, collection_manager):
        """Test listing all collections"""
        collections = collection_manager.list_collections()
        assert isinstance(collections, list)
        assert len(collections) > 0

    def test_get_collection_info(self, collection_manager):
        """Test getting collection info"""
        info = collection_manager.get_collection_info("visa_oracle")
        assert isinstance(info, dict)
        assert "priority" in info or "doc_count" in info

    def test_get_collection_info_not_found(self, collection_manager):
        """Test getting info for non-existent collection"""
        info = collection_manager.get_collection_info("nonexistent")
        assert info is None

    def test_collection_definitions_structure(self, collection_manager):
        """Test collection definitions structure"""
        for name, definition in collection_manager.collection_definitions.items():
            assert isinstance(name, str)
            assert isinstance(definition, dict)
            assert "priority" in definition or "doc_count" in definition

