"""
Unit tests for result_formatter module.

Tests the format_search_results function extracted from SearchService.
"""

import pytest

from services.result_formatter import format_search_results


class TestFormatSearchResults:
    """Test cases for format_search_results function."""

    def test_empty_results(self):
        """Test with empty results."""
        raw_results = {"documents": [], "distances": [], "metadatas": [], "ids": []}
        result = format_search_results(raw_results, "test_collection")
        assert result == []

    def test_single_result(self):
        """Test formatting a single result."""
        raw_results = {
            "documents": ["Test document content"],
            "distances": [0.3],
            "metadatas": [{"type": "test", "source": "test"}],
            "ids": ["doc1"],
        }
        result = format_search_results(raw_results, "test_collection")
        assert len(result) == 1
        assert result[0]["id"] == "doc1"
        assert result[0]["text"] == "Test document content"
        assert result[0]["metadata"] == {"type": "test", "source": "test"}
        assert result[0]["score"] == pytest.approx(0.7692, abs=0.0001)

    def test_multiple_results(self):
        """Test formatting multiple results."""
        raw_results = {
            "documents": ["Doc 1", "Doc 2"],
            "distances": [0.2, 0.5],
            "metadatas": [{"type": "a"}, {"type": "b"}],
            "ids": ["id1", "id2"],
        }
        result = format_search_results(raw_results, "test_collection")
        assert len(result) == 2
        assert result[0]["score"] > result[1]["score"]  # Lower distance = higher score

    def test_primary_collection_boost(self):
        """Test that primary collection gets boost."""
        raw_results = {
            "documents": ["Test"],
            "distances": [0.3],
            "metadatas": [{}],
            "ids": ["doc1"],
        }
        result_primary = format_search_results(
            raw_results, "primary_collection", primary_collection="primary_collection"
        )
        result_normal = format_search_results(raw_results, "other_collection")
        assert result_primary[0]["score"] > result_normal[0]["score"]
        assert result_primary[0]["metadata"]["is_primary"] is True
        assert result_primary[0]["metadata"]["source_collection"] == "primary_collection"

    def test_pricing_collection_boost(self):
        """Test that bali_zero_pricing gets boost."""
        raw_results = {
            "documents": ["Test"],
            "distances": [0.3],
            "metadatas": [{}],
            "ids": ["doc1"],
        }
        result_pricing = format_search_results(raw_results, "bali_zero_pricing")
        result_normal = format_search_results(raw_results, "other_collection")
        assert result_pricing[0]["score"] > result_normal[0]["score"]
        assert result_pricing[0]["metadata"]["pricing_priority"] == "high"

    def test_team_collection_boost(self):
        """Test that bali_zero_team gets boost."""
        raw_results = {
            "documents": ["Test"],
            "distances": [0.3],
            "metadatas": [{}],
            "ids": ["doc1"],
        }
        result_team = format_search_results(raw_results, "bali_zero_team")
        result_normal = format_search_results(raw_results, "other_collection")
        assert result_team[0]["score"] > result_normal[0]["score"]

    def test_missing_distances(self):
        """Test handling missing distances."""
        raw_results = {
            "documents": ["Test"],
            "distances": [],
            "metadatas": [{}],
            "ids": ["doc1"],
        }
        result = format_search_results(raw_results, "test_collection")
        assert len(result) == 1
        assert result[0]["score"] == pytest.approx(0.5, abs=0.01)  # Default distance 1.0

    def test_missing_metadatas(self):
        """Test handling missing metadatas."""
        raw_results = {
            "documents": ["Test"],
            "distances": [0.3],
            "metadatas": [],
            "ids": ["doc1"],
        }
        result = format_search_results(raw_results, "test_collection")
        assert len(result) == 1
        assert result[0]["metadata"] == {}

    def test_missing_ids(self):
        """Test handling missing ids."""
        raw_results = {
            "documents": ["Test"],
            "distances": [0.3],
            "metadatas": [{}],
            "ids": [],
        }
        result = format_search_results(raw_results, "test_collection")
        assert len(result) == 1
        assert result[0]["id"] is None

    def test_multi_collection_metadata(self):
        """Test metadata enrichment for multi-collection searches."""
        raw_results = {
            "documents": ["Test"],
            "distances": [0.3],
            "metadatas": [{"original": "data"}],
            "ids": ["doc1"],
        }
        result = format_search_results(
            raw_results, "secondary_collection", primary_collection="primary_collection"
        )
        assert result[0]["metadata"]["source_collection"] == "secondary_collection"
        assert result[0]["metadata"]["is_primary"] is False
        assert result[0]["metadata"]["original"] == "data"  # Original metadata preserved

    def test_score_capping(self):
        """Test that scores are capped at MAX_SCORE."""
        # Very low distance should still be capped
        raw_results = {
            "documents": ["Test"],
            "distances": [0.001],  # Very low distance
            "metadatas": [{}],
            "ids": ["doc1"],
        }
        result = format_search_results(
            raw_results, "bali_zero_pricing", primary_collection="bali_zero_pricing"
        )
        # Score should be capped at MAX_SCORE (1.0)
        assert result[0]["score"] <= 1.0

    def test_score_precision(self):
        """Test that scores are rounded to 4 decimal places."""
        raw_results = {
            "documents": ["Test"],
            "distances": [0.333333],
            "metadatas": [{}],
            "ids": ["doc1"],
        }
        result = format_search_results(raw_results, "test_collection")
        # Score should be rounded to 4 decimal places
        score_str = str(result[0]["score"])
        decimal_places = len(score_str.split(".")[1]) if "." in score_str else 0
        assert decimal_places <= 4

