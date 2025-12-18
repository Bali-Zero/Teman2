"""
Unit tests for distance validation in result_formatter.

Tests the validation logic added to prevent division by zero.
"""

import pytest

from services.result_formatter import format_search_results


class TestResultFormatterDistanceValidation:
    """Test distance validation in result_formatter."""

    def test_negative_distance_clamped(self):
        """Test that negative distances are clamped to 0"""
        raw_results = {
            "documents": ["Test"],
            "distances": [-0.5],  # Negative distance
            "metadatas": [{}],
            "ids": ["doc1"],
        }
        result = format_search_results(raw_results, "test_collection")
        assert len(result) == 1
        # Score should be calculated with distance=0 (clamped)
        assert result[0]["score"] == pytest.approx(1.0, abs=0.0001)

    def test_distance_minus_one_handled(self):
        """Test that distance=-1 is handled (shouldn't happen but be safe)"""
        raw_results = {
            "documents": ["Test"],
            "distances": [-1.0],  # Would cause division by zero
            "metadatas": [{}],
            "ids": ["doc1"],
        }
        result = format_search_results(raw_results, "test_collection")
        assert len(result) == 1
        # Should not raise ZeroDivisionError
        assert result[0]["score"] is not None
        assert result[0]["score"] > 0

    def test_zero_distance_handled(self):
        """Test that distance=0 is handled correctly"""
        raw_results = {
            "documents": ["Test"],
            "distances": [0.0],
            "metadatas": [{}],
            "ids": ["doc1"],
        }
        result = format_search_results(raw_results, "test_collection")
        assert len(result) == 1
        assert result[0]["score"] == pytest.approx(1.0, abs=0.0001)

    def test_normal_distance_unchanged(self):
        """Test that normal positive distances work as expected"""
        raw_results = {
            "documents": ["Test"],
            "distances": [0.3],
            "metadatas": [{}],
            "ids": ["doc1"],
        }
        result = format_search_results(raw_results, "test_collection")
        assert len(result) == 1
        # Score should be 1 / (1 + 0.3) = 0.7692...
        assert result[0]["score"] == pytest.approx(0.7692, abs=0.0001)

    def test_distance_exactly_minus_one_handled(self):
        """Test that distance exactly -1.0 is handled (clamped to 0.0 first)"""
        raw_results = {
            "documents": ["Test"],
            "distances": [-1.0],  # Exactly -1.0, but will be clamped to 0.0 first
            "metadatas": [{}],
            "ids": ["doc1"],
        }
        result = format_search_results(raw_results, "test_collection")
        assert len(result) == 1
        # Should not raise ZeroDivisionError, distance is clamped to 0.0 (not 1.0)
        # because distance < 0 check happens before distance == -1.0 check
        assert result[0]["score"] == pytest.approx(1.0, abs=0.0001)  # 1 / (1 + 0.0) = 1.0

