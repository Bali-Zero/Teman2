"""
Unit tests for FallbackManagerService
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.routing.fallback_manager import FallbackManagerService


@pytest.fixture
def fallback_manager():
    """Create FallbackManagerService instance"""
    return FallbackManagerService()


class TestFallbackManagerService:
    """Tests for FallbackManagerService"""

    def test_init(self):
        """Test initialization"""
        manager = FallbackManagerService()
        assert manager.FALLBACK_CHAINS is not None
        assert manager.CONFIDENCE_THRESHOLD_HIGH > 0
        assert manager.CONFIDENCE_THRESHOLD_LOW > 0

    def test_get_fallback_collections_high_confidence(self, fallback_manager):
        """Test getting fallback collections with high confidence"""
        collections = fallback_manager.get_fallback_collections(
            "visa_oracle", confidence=0.8, max_fallbacks=3
        )
        assert len(collections) == 1
        assert collections[0] == "visa_oracle"

    def test_get_fallback_collections_medium_confidence(self, fallback_manager):
        """Test getting fallback collections with medium confidence"""
        collections = fallback_manager.get_fallback_collections(
            "visa_oracle", confidence=0.5, max_fallbacks=3
        )
        assert len(collections) == 2  # Primary + 1 fallback
        assert collections[0] == "visa_oracle"

    def test_get_fallback_collections_low_confidence(self, fallback_manager):
        """Test getting fallback collections with low confidence"""
        collections = fallback_manager.get_fallback_collections(
            "visa_oracle", confidence=0.2, max_fallbacks=3
        )
        assert len(collections) >= 2  # Primary + fallbacks
        assert collections[0] == "visa_oracle"

    def test_get_fallback_collections_unknown_collection(self, fallback_manager):
        """Test getting fallback collections for unknown collection"""
        collections = fallback_manager.get_fallback_collections(
            "unknown_collection", confidence=0.2, max_fallbacks=3
        )
        assert len(collections) == 1  # Only primary
        assert collections[0] == "unknown_collection"

    def test_get_fallback_chain(self, fallback_manager):
        """Test getting full fallback chain"""
        chain = fallback_manager.get_fallback_chain("visa_oracle")
        assert len(chain) > 1
        assert chain[0] == "visa_oracle"

    def test_get_fallback_chain_unknown(self, fallback_manager):
        """Test getting fallback chain for unknown collection"""
        chain = fallback_manager.get_fallback_chain("unknown_collection")
        assert len(chain) == 1
        assert chain[0] == "unknown_collection"
