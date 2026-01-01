"""
Unit tests for result_formatter
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

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
