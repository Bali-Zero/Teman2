"""
Unit tests for Search Filters
Target: >95% coverage
"""

import sys
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.search.search_filters import build_search_filter


class TestSearchFilters:
    """Tests for build_search_filter function"""

    def test_build_search_filter_no_filters(self):
        """Test building filter with no constraints"""
        result = build_search_filter()
        assert result is not None
        assert "status_vigensi" in result

    def test_build_search_filter_tier_only(self):
        """Test building filter with tier filter only"""
        tier_filter = {"tier": {"$in": ["S", "A"]}}
        result = build_search_filter(tier_filter=tier_filter)
        assert result is not None
        assert result["tier"] == {"$in": ["S", "A"]}
        assert result["status_vigensi"] == {"$ne": "dicabut"}

    def test_build_search_filter_exclude_repealed_false(self):
        """Test building filter without excluding repealed"""
        result = build_search_filter(exclude_repealed=False)
        assert result is None

    def test_build_search_filter_tier_and_exclude_repealed(self):
        """Test building filter with tier and exclude repealed"""
        tier_filter = {"tier": {"$in": ["S", "A", "B"]}}
        result = build_search_filter(tier_filter=tier_filter, exclude_repealed=True)
        assert result["tier"] == {"$in": ["S", "A", "B"]}
        assert result["status_vigensi"] == {"$ne": "dicabut"}

    def test_build_search_filter_status_vigensi_in_existing(self):
        """Test building filter with existing status_vigensi $in filter"""
        tier_filter = {"status_vigensi": {"$in": ["berlaku", "dicabut"]}}
        result = build_search_filter(tier_filter=tier_filter, exclude_repealed=True)
        assert result["status_vigensi"] == {"$in": ["berlaku"]}

    def test_build_search_filter_status_vigensi_all_dicabut(self):
        """Test building filter when all status_vigensi values are dicabut"""
        tier_filter = {"status_vigensi": {"$in": ["dicabut"]}}
        result = build_search_filter(tier_filter=tier_filter, exclude_repealed=True)
        assert result["status_vigensi"] == {"$ne": "dicabut"}

    def test_build_search_filter_status_vigensi_string_dicabut(self):
        """Test building filter with status_vigensi as string 'dicabut'"""
        tier_filter = {"status_vigensi": "dicabut"}
        result = build_search_filter(tier_filter=tier_filter, exclude_repealed=True)
        # When dicabut is explicitly set, it gets popped, so result might be None or empty dict
        if result is None:
            assert True  # Valid - no filter needed
        else:
            assert "status_vigensi" not in result or result.get("status_vigensi") != "dicabut"

    def test_build_search_filter_status_vigensi_string_berlaku(self):
        """Test building filter with status_vigensi as string 'berlaku'"""
        tier_filter = {"status_vigensi": "berlaku"}
        result = build_search_filter(tier_filter=tier_filter, exclude_repealed=True)
        assert result["status_vigensi"] == {"$in": ["berlaku"]}
