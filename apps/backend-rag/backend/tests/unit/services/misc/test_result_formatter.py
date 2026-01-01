"""
Unit tests for Result Formatter
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
    """Tests for format_search_results function"""

    def test_format_search_results_empty(self):
        """Test formatting empty results"""
        raw_results = {"documents": [], "distances": [], "metadatas": [], "ids": []}
        result = format_search_results(raw_results, "visa_oracle")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_format_search_results_basic(self):
        """Test formatting basic results"""
        raw_results = {
            "documents": ["Test document"],
            "distances": [0.3],
            "metadatas": [{"type": "visa"}],
            "ids": ["doc1"]
        }
        result = format_search_results(raw_results, "visa_oracle")
        assert len(result) == 1
        assert result[0]["id"] == "doc1"
        assert result[0]["text"] == "Test document"
        assert "score" in result[0]

    def test_format_search_results_primary_collection_boost(self):
        """Test primary collection boost"""
        raw_results = {
            "documents": ["Test document"],
            "distances": [0.3],
            "metadatas": [{"type": "visa"}],
            "ids": ["doc1"]
        }
        result = format_search_results(raw_results, "visa_oracle", primary_collection="visa_oracle")
        assert len(result) == 1
        assert result[0]["score"] > 0.7  # Should be boosted

    def test_format_search_results_pricing_boost(self):
        """Test pricing collection boost"""
        raw_results = {
            "documents": ["Test document"],
            "distances": [0.3],
            "metadatas": [{"type": "pricing"}],
            "ids": ["doc1"]
        }
        result = format_search_results(raw_results, "bali_zero_pricing")
        assert len(result) == 1
        assert result[0]["score"] > 0.7  # Should be boosted

    def test_format_search_results_team_boost(self):
        """Test team collection boost"""
        raw_results = {
            "documents": ["Test document"],
            "distances": [0.3],
            "metadatas": [{"type": "team"}],
            "ids": ["doc1"]
        }
        result = format_search_results(raw_results, "bali_zero_team")
        assert len(result) == 1
        assert result[0]["score"] > 0.7  # Should be boosted

    def test_format_search_results_metadata_enrichment(self):
        """Test metadata enrichment"""
        raw_results = {
            "documents": ["Test document"],
            "distances": [0.3],
            "metadatas": [{"type": "visa"}],
            "ids": ["doc1"]
        }
        result = format_search_results(raw_results, "visa_oracle", primary_collection="visa_oracle")
        assert result[0]["metadata"]["source_collection"] == "visa_oracle"
        assert result[0]["metadata"]["is_primary"] is True

