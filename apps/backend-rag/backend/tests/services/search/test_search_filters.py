"""
Tests for search_filters.py - Tier-based access control and repealed law exclusion.
"""


from backend.services.search.search_filters import build_search_filter


class TestBuildSearchFilterNoInputs:
    """Tests for build_search_filter with no inputs."""

    def test_no_filters_returns_none(self):
        result = build_search_filter(tier_filter=None, exclude_repealed=False)
        assert result is None

    def test_default_excludes_repealed(self):
        result = build_search_filter()
        assert result == {"status_vigensi": {"$ne": "dicabut"}}


class TestBuildSearchFilterTierOnly:
    """Tests for tier filter without repealed exclusion."""

    def test_tier_filter_passed_through(self):
        tier = {"tier": {"$in": ["S", "A"]}}
        result = build_search_filter(tier_filter=tier, exclude_repealed=False)
        assert result == {"tier": {"$in": ["S", "A"]}}

    def test_tier_filter_with_repealed_exclusion(self):
        tier = {"tier": {"$in": ["S", "A"]}}
        result = build_search_filter(tier_filter=tier, exclude_repealed=True)
        assert result["tier"] == {"$in": ["S", "A"]}
        assert result["status_vigensi"] == {"$ne": "dicabut"}


class TestBuildSearchFilterRepealedExclusion:
    """Tests for repealed law exclusion edge cases."""

    def test_existing_status_in_filter_removes_dicabut(self):
        tier = {"status_vigensi": {"$in": ["berlaku", "dicabut"]}}
        result = build_search_filter(tier_filter=tier, exclude_repealed=True)
        assert result["status_vigensi"] == {"$in": ["berlaku"]}

    def test_existing_status_all_dicabut_becomes_ne(self):
        tier = {"status_vigensi": {"$in": ["dicabut"]}}
        result = build_search_filter(tier_filter=tier, exclude_repealed=True)
        assert result["status_vigensi"] == {"$ne": "dicabut"}

    def test_explicit_dicabut_string_removed(self):
        tier = {"status_vigensi": "dicabut"}
        result = build_search_filter(tier_filter=tier, exclude_repealed=True)
        # When explicitly requesting dicabut with exclude=True, filter is removed
        assert result is None or "status_vigensi" not in result

    def test_valid_status_string_converted_to_in_format(self):
        tier = {"status_vigensi": "berlaku"}
        result = build_search_filter(tier_filter=tier, exclude_repealed=True)
        assert result["status_vigensi"] == {"$in": ["berlaku"]}

    def test_exclude_repealed_false_preserves_status(self):
        tier = {"status_vigensi": {"$in": ["berlaku", "dicabut"]}}
        result = build_search_filter(tier_filter=tier, exclude_repealed=False)
        assert result["status_vigensi"] == {"$in": ["berlaku", "dicabut"]}

    def test_multiple_valid_statuses_preserved(self):
        tier = {"status_vigensi": {"$in": ["berlaku", "direvisi", "dicabut"]}}
        result = build_search_filter(tier_filter=tier, exclude_repealed=True)
        assert "dicabut" not in result["status_vigensi"]["$in"]
        assert "berlaku" in result["status_vigensi"]["$in"]
        assert "direvisi" in result["status_vigensi"]["$in"]
