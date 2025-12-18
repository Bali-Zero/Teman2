"""
Unit tests for CollectionManager Service
Tests Qdrant collection lifecycle and access management
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.collection_manager import CollectionManager


@pytest.mark.unit
class TestCollectionManagerInit:
    """Test CollectionManager initialization"""

    def test_init_default(self):
        """Test default initialization"""
        with patch("services.collection_manager.settings") as mock_settings:
            mock_settings.qdrant_url = "http://localhost:6333"

            manager = CollectionManager()

            assert manager.qdrant_url == "http://localhost:6333"
            assert manager._collections_cache == {}
            assert len(manager.collection_definitions) > 0

    def test_init_with_custom_url(self):
        """Test initialization with custom URL"""
        manager = CollectionManager(qdrant_url="http://custom:6333")

        assert manager.qdrant_url == "http://custom:6333"


@pytest.mark.unit
class TestCollectionManagerGetCollection:
    """Test get_collection method"""

    def test_get_collection_cached(self):
        """Test getting cached collection"""
        manager = CollectionManager()
        mock_client = MagicMock()
        manager._collections_cache["test_collection"] = mock_client

        result = manager.get_collection("test_collection")

        assert result == mock_client

    def test_get_collection_unknown(self):
        """Test getting unknown collection"""
        manager = CollectionManager()

        result = manager.get_collection("unknown_collection")

        assert result is None

    def test_get_collection_with_alias(self):
        """Test getting collection with alias"""
        manager = CollectionManager()

        with patch("services.collection_manager.QdrantClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = manager.get_collection("kbli_eye")

            assert result == mock_client
            # Should resolve alias
            assert "kbli_eye" in manager._collections_cache

    def test_get_collection_creation_error(self):
        """Test collection creation error handling"""
        manager = CollectionManager()

        with patch(
            "services.collection_manager.QdrantClient", side_effect=Exception("Connection error")
        ):
            result = manager.get_collection("visa_oracle")

            assert result is None

    def test_get_collection_direct_name(self):
        """Test getting collection by direct name"""
        manager = CollectionManager()

        with patch("services.collection_manager.QdrantClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = manager.get_collection("visa_oracle")

            assert result == mock_client
            assert "visa_oracle" in manager._collections_cache


@pytest.mark.unit
class TestCollectionManagerListCollections:
    """Test list_collections method"""

    def test_list_collections(self):
        """Test listing all collections"""
        manager = CollectionManager()

        collections = manager.list_collections()

        assert isinstance(collections, list)
        assert len(collections) > 0
        assert all(isinstance(c, str) for c in collections)  # Returns list of names

    def test_get_all_collections(self):
        """Test getting all collection clients"""
        manager = CollectionManager()

        with patch("services.collection_manager.QdrantClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            collections = manager.get_all_collections()

            assert isinstance(collections, dict)
            assert len(collections) > 0


@pytest.mark.unit
class TestCollectionManagerInfo:
    """Test collection info methods"""

    def test_get_collection_info_existing(self):
        """Test getting info for existing collection"""
        manager = CollectionManager()

        info = manager.get_collection_info("visa_oracle")

        assert info is not None
        assert "priority" in info
        assert "doc_count" in info
        assert info["actual_name"] == "visa_oracle"

    def test_get_collection_info_with_alias(self):
        """Test getting info for collection with alias"""
        manager = CollectionManager()

        info = manager.get_collection_info("kbli_eye")

        assert info is not None
        assert info["actual_name"] == "kbli_unified"  # Alias resolved

    def test_get_collection_info_nonexistent(self):
        """Test getting info for nonexistent collection"""
        manager = CollectionManager()

        info = manager.get_collection_info("nonexistent")

        assert info is None
