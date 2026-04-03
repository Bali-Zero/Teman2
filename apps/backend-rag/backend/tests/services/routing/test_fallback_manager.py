"""
Tests for fallback_manager.py - Fallback chain management for collection selection.
"""

import pytest

from backend.services.routing.fallback_manager import FallbackManagerService


@pytest.fixture
def manager():
    return FallbackManagerService()


class TestGetFallbackCollections:
    """Tests for get_fallback_collections method."""

    def test_high_confidence_returns_primary_only(self, manager):
        result = manager.get_fallback_collections("visa_oracle", confidence=0.8)
        assert result == ["visa_oracle"]

    def test_medium_confidence_returns_one_fallback(self, manager):
        result = manager.get_fallback_collections("visa_oracle", confidence=0.5)
        assert len(result) == 2
        assert result[0] == "visa_oracle"

    def test_low_confidence_returns_multiple_fallbacks(self, manager):
        result = manager.get_fallback_collections("visa_oracle", confidence=0.1)
        assert len(result) >= 2
        assert result[0] == "visa_oracle"

    def test_exact_high_threshold_primary_only(self, manager):
        result = manager.get_fallback_collections("visa_oracle", confidence=0.7)
        assert result == ["visa_oracle"]

    def test_just_below_high_threshold_gets_fallback(self, manager):
        result = manager.get_fallback_collections("visa_oracle", confidence=0.69)
        assert len(result) == 2

    def test_zero_confidence_max_fallbacks(self, manager):
        result = manager.get_fallback_collections("visa_oracle", confidence=0.0)
        assert len(result) == 4  # primary + 3 fallbacks

    def test_max_fallbacks_parameter(self, manager):
        result = manager.get_fallback_collections(
            "visa_oracle", confidence=0.0, max_fallbacks=1
        )
        # Low confidence but max_fallbacks=1 means min(1, 3) = 1 fallback
        assert len(result) == 2  # primary + 1

    def test_unknown_collection_returns_primary_only(self, manager):
        result = manager.get_fallback_collections("nonexistent_collection", confidence=0.0)
        assert result == ["nonexistent_collection"]

    def test_visa_oracle_fallback_chain(self, manager):
        result = manager.get_fallback_collections("visa_oracle", confidence=0.1)
        # Should include immigration_circulars as first fallback
        assert "immigration_circulars" in result

    def test_tax_genius_fallback_chain(self, manager):
        result = manager.get_fallback_collections("tax_genius", confidence=0.1)
        assert "tax_knowledge" in result


class TestGetFallbackChain:
    """Tests for get_fallback_chain method."""

    def test_known_collection_returns_full_chain(self, manager):
        chain = manager.get_fallback_chain("visa_oracle")
        assert chain[0] == "visa_oracle"
        assert len(chain) > 1

    def test_unknown_collection_returns_self(self, manager):
        chain = manager.get_fallback_chain("nonexistent")
        assert chain == ["nonexistent"]

    def test_all_defined_collections_have_chains(self, manager):
        for collection in manager.FALLBACK_CHAINS:
            chain = manager.get_fallback_chain(collection)
            assert len(chain) >= 2, f"{collection} should have fallbacks"
            assert chain[0] == collection
