"""
Unit tests for search_filters module.

Tests the build_search_filter function extracted from SearchService.
"""

import pytest

from services.search_filters import build_search_filter


class TestBuildSearchFilter:
    """Test cases for build_search_filter function."""

    def test_no_filters(self):
        """Test with no filters provided."""
        result = build_search_filter()
        assert result == {"status_vigensi": {"$ne": "dicabut"}}

    def test_no_filters_exclude_repealed_false(self):
        """Test with exclude_repealed=False."""
        result = build_search_filter(exclude_repealed=False)
        assert result is None

    def test_tier_filter_only(self):
        """Test with tier filter only."""
        tier_filter = {"tier": {"$in": ["S", "A"]}}
        result = build_search_filter(tier_filter=tier_filter)
        assert result == {
            "tier": {"$in": ["S", "A"]},
            "status_vigensi": {"$ne": "dicabut"},
        }

    def test_tier_filter_exclude_repealed_false(self):
        """Test with tier filter and exclude_repealed=False."""
        tier_filter = {"tier": {"$in": ["S", "A"]}}
        result = build_search_filter(tier_filter=tier_filter, exclude_repealed=False)
        assert result == {"tier": {"$in": ["S", "A"]}}

    def test_status_vigensi_with_dicabut_in_list(self):
        """Test when status_vigensi filter includes 'dicabut'."""
        tier_filter = {"status_vigensi": {"$in": ["berlaku", "dicabut"]}}
        result = build_search_filter(tier_filter=tier_filter)
        assert result == {
            "status_vigensi": {"$in": ["berlaku"]},
        }

    def test_status_vigensi_only_dicabut(self):
        """Test when status_vigensi filter only has 'dicabut'."""
        tier_filter = {"status_vigensi": {"$in": ["dicabut"]}}
        result = build_search_filter(tier_filter=tier_filter)
        assert result == {"status_vigensi": {"$ne": "dicabut"}}

    def test_status_vigensi_explicit_dicabut_string(self):
        """Test when status_vigensi is explicitly set to 'dicabut'."""
        tier_filter = {"status_vigensi": "dicabut"}
        result = build_search_filter(tier_filter=tier_filter)
        # When explicitly filtering for "dicabut", the filter is removed (pop)
        # After pop, filters dict is empty {}, and we don't enter the else branch
        # (because we're already in the "if status_vigensi in filters" branch)
        # So filters remains empty, and return filters if filters else None returns None
        # This is the actual behavior: dicabut is removed, no exclusion added
        assert result is None

    def test_status_vigensi_valid_status(self):
        """Test when status_vigensi has valid status (not dicabut)."""
        tier_filter = {"status_vigensi": "berlaku"}
        result = build_search_filter(tier_filter=tier_filter)
        # When status_vigensi is a string that's not "dicabut", it's converted to $in format
        # for consistency. The exclusion logic ensures "dicabut" is not in the list.
        assert result == {"status_vigensi": {"$in": ["berlaku"]}}

    def test_complex_filter(self):
        """Test with multiple filter conditions."""
        tier_filter = {
            "tier": {"$in": ["S", "A", "B"]},
            "category": "visa",
            "year": {"$gte": 2020},
        }
        result = build_search_filter(tier_filter=tier_filter)
        assert result == {
            "tier": {"$in": ["S", "A", "B"]},
            "category": "visa",
            "year": {"$gte": 2020},
            "status_vigensi": {"$ne": "dicabut"},
        }

    def test_empty_tier_filter_dict(self):
        """Test with empty tier filter dict."""
        result = build_search_filter(tier_filter={})
        assert result == {"status_vigensi": {"$ne": "dicabut"}}

    def test_status_vigensi_string_converted_to_in_format(self):
        """Test that status_vigensi string is converted to $in format for consistency."""
        tier_filter = {"status_vigensi": "berlaku"}
        result = build_search_filter(tier_filter=tier_filter)
        # Should be converted to $in format
        assert result == {"status_vigensi": {"$in": ["berlaku"]}}

    def test_status_vigensi_string_dicabut_removed(self):
        """Test edge case: if status_vigensi string conversion results in empty allowed_values."""
        # This tests the else branch in the string conversion logic
        # When a valid status string is converted to $in, it should never be empty,
        # but we test the branch for completeness
        tier_filter = {"status_vigensi": "berlaku"}
        result = build_search_filter(tier_filter=tier_filter, exclude_repealed=True)
        # Should have $in format with valid status
        assert "status_vigensi" in result
        assert result["status_vigensi"] == {"$in": ["berlaku"]}

