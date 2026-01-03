"""
Unit tests for result_formatter
Target: >95% coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.result_formatter import format_search_results


class TestResultFormatter:
    """Tests for result formatter"""

    def test_format_search_results(self):
        """Test formatting search results"""
        raw_results = {
            "ids": ["1", "2"],
            "documents": ["Test document 1", "Test document 2"],
            "distances": [0.1, 0.2],
            "metadatas": [
                {"tier": "S", "source": "test"},
                {"tier": "A", "source": "test"}
            ]
        }
        formatted = format_search_results(raw_results, "test_collection")
        assert isinstance(formatted, list)
        assert len(formatted) == 2

    def test_format_search_results_empty(self):
        """Test formatting empty search results"""
        raw_results = {
            "ids": [],
            "documents": [],
            "distances": [],
            "metadatas": []
        }
        formatted = format_search_results(raw_results, "test_collection")
        assert isinstance(formatted, list)
        assert len(formatted) == 0

    def test_format_search_results_with_primary_collection(self):
        """Test formatting search results with primary collection boost"""
        raw_results = {
            "ids": ["1"],
            "documents": ["Test document"],
            "distances": [0.1],
            "metadatas": [{"tier": "S", "source": "test"}]
        }
        formatted = format_search_results(
            raw_results,
            "test_collection",
            primary_collection="test_collection"
        )
        assert isinstance(formatted, list)
        assert len(formatted) == 1
        assert formatted[0]["score"] > 0

    def test_format_search_results_pricing_collection(self):
        """Test formatting search results from pricing collection"""
        raw_results = {
            "ids": ["1"],
            "documents": ["Test document"],
            "distances": [0.1],
            "metadatas": [{"tier": "S", "source": "test"}]
        }
        formatted = format_search_results(
            raw_results,
            "bali_zero_pricing"
        )
        assert isinstance(formatted, list)
        assert len(formatted) == 1
        assert formatted[0]["score"] > 0
        assert formatted[0]["metadata"]["pricing_priority"] == "high"

    def test_format_search_results_team_collection(self):
        """Test formatting search results from team collection"""
        raw_results = {
            "ids": ["1"],
            "documents": ["Test document"],
            "distances": [0.1],
            "metadatas": [{"tier": "S", "source": "test"}]
        }
        formatted = format_search_results(
            raw_results,
            "bali_zero_team"
        )
        assert isinstance(formatted, list)
        assert len(formatted) == 1
        assert formatted[0]["score"] > 0

    def test_format_search_results_negative_distance(self):
        """Test formatting with negative distance (should be clamped)"""
        raw_results = {
            "ids": ["1"],
            "documents": ["Test document"],
            "distances": [-0.1],
            "metadatas": [{"tier": "S"}]
        }
        formatted = format_search_results(raw_results, "test_collection")
        assert len(formatted) == 1
        assert formatted[0]["score"] >= 0

    def test_format_search_results_missing_fields(self):
        """Test formatting with missing optional fields"""
        raw_results = {
            "ids": ["1"],
            "documents": ["Test document"],
            "distances": [0.1]
            # Missing metadatas
        }
        formatted = format_search_results(raw_results, "test_collection")
        assert len(formatted) == 1
        assert formatted[0]["metadata"] == {}

    def test_format_search_results_mismatched_lengths(self):
        """Test formatting with mismatched array lengths"""
        raw_results = {
            "ids": ["1", "2"],
            "documents": ["Test document"],
            "distances": [0.1],
            "metadatas": [{"tier": "S"}]
        }
        formatted = format_search_results(raw_results, "test_collection")
        assert len(formatted) == 1  # Should only format available data

    def test_format_search_results_primary_collection_boost(self):
        """Test primary collection boost is applied"""
        raw_results = {
            "ids": ["1"],
            "documents": ["Test document"],
            "distances": [0.1],
            "metadatas": [{"tier": "S"}]
        }
        formatted_with_boost = format_search_results(
            raw_results,
            "primary_collection",
            primary_collection="primary_collection"
        )
        formatted_without_boost = format_search_results(
            raw_results,
            "primary_collection"
        )
        assert formatted_with_boost[0]["score"] > formatted_without_boost[0]["score"]
        assert formatted_with_boost[0]["metadata"]["is_primary"] is True

    def test_format_search_results_non_primary_collection(self):
        """Test non-primary collection metadata"""
        raw_results = {
            "ids": ["1"],
            "documents": ["Test document"],
            "distances": [0.1],
            "metadatas": [{"tier": "S"}]
        }
        formatted = format_search_results(
            raw_results,
            "other_collection",
            primary_collection="primary_collection"
        )
        assert formatted[0]["metadata"]["is_primary"] is False
        assert formatted[0]["metadata"]["source_collection"] == "other_collection"
