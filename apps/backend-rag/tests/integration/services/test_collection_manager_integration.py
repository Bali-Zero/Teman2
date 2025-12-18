"""
Integration Tests for CollectionManager
Tests Qdrant collection management and access
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestCollectionManagerIntegration:
    """Comprehensive integration tests for CollectionManager"""

    @pytest.fixture
    def manager(self):
        """Create CollectionManager instance"""
        with patch("services.collection_manager.QdrantClient") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            from services.collection_manager import CollectionManager

            manager = CollectionManager(qdrant_url="http://localhost:6333")
            return manager

    def test_initialization(self, manager):
        """Test manager initialization"""
        assert manager is not None
        assert manager.qdrant_url is not None
        assert len(manager.collection_definitions) > 0

    def test_get_collection_existing(self, manager):
        """Test getting existing collection"""
        with patch("services.collection_manager.QdrantClient") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            collection = manager.get_collection("visa_oracle")

            assert collection is not None
            assert collection in manager._collections_cache

    def test_get_collection_unknown(self, manager):
        """Test getting unknown collection"""
        collection = manager.get_collection("unknown_collection")

        assert collection is None

    def test_get_collection_with_alias(self, manager):
        """Test getting collection with alias"""
        with patch("services.collection_manager.QdrantClient") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            # kbli_eye has alias kbli_unified
            collection = manager.get_collection("kbli_eye")

            assert collection is not None
            # Should use alias name
            mock_client.assert_called_once()

    def test_get_all_collections(self, manager):
        """Test getting all collections"""
        with patch("services.collection_manager.QdrantClient") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            collections = manager.get_all_collections()

            assert collections is not None
            assert isinstance(collections, dict)
            assert len(collections) > 0

    def test_list_collections(self, manager):
        """Test listing collections"""
        collections = manager.list_collections()

        assert collections is not None
        assert isinstance(collections, list)
        assert len(collections) > 0
        assert "visa_oracle" in collections

    def test_get_collection_info(self, manager):
        """Test getting collection info"""
        info = manager.get_collection_info("visa_oracle")

        assert info is not None
        assert "priority" in info
        assert "doc_count" in info
        assert "actual_name" in info

    def test_get_collection_info_unknown(self, manager):
        """Test getting info for unknown collection"""
        info = manager.get_collection_info("unknown_collection")

        assert info is None

    def test_get_collection_caching(self, manager):
        """Test collection caching"""
        with patch("services.collection_manager.QdrantClient") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            # First call
            collection1 = manager.get_collection("visa_oracle")

            # Second call should use cache
            collection2 = manager.get_collection("visa_oracle")

            assert collection1 == collection2
            # QdrantClient should be called only once
            assert mock_client.call_count == 1

    def test_collection_definitions_structure(self, manager):
        """Test collection definitions structure"""
        for name, definition in manager.collection_definitions.items():
            assert "priority" in definition
            assert "doc_count" in definition
            assert definition["priority"] in ["high", "medium", "low"]
