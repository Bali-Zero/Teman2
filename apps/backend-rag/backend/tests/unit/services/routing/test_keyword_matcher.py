"""
Unit tests for KeywordMatcherService
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.routing.keyword_matcher import KeywordMatcherService


@pytest.fixture
def keyword_matcher():
    """Create KeywordMatcherService instance"""
    return KeywordMatcherService()


class TestKeywordMatcherService:
    """Tests for KeywordMatcherService"""

    def test_init(self):
        """Test initialization"""
        matcher = KeywordMatcherService()
        assert matcher.domain_keywords is not None
        assert matcher.modifier_keywords is not None

    def test_calculate_domain_scores_visa(self, keyword_matcher):
        """Test calculating domain scores for visa query"""
        scores = keyword_matcher.calculate_domain_scores("visa application")
        assert scores["visa"] > 0

    def test_calculate_domain_scores_tax(self, keyword_matcher):
        """Test calculating domain scores for tax query"""
        scores = keyword_matcher.calculate_domain_scores("tax calculation")
        assert scores["tax"] > 0

    def test_calculate_domain_scores_legal(self, keyword_matcher):
        """Test calculating domain scores for legal query"""
        scores = keyword_matcher.calculate_domain_scores("company formation")
        assert scores["legal"] > 0

    def test_calculate_domain_scores_kbli(self, keyword_matcher):
        """Test calculating domain scores for KBLI query"""
        scores = keyword_matcher.calculate_domain_scores("kbli code")
        assert scores["kbli"] > 0

    def test_calculate_domain_scores_property(self, keyword_matcher):
        """Test calculating domain scores for property query"""
        scores = keyword_matcher.calculate_domain_scores("property purchase")
        assert scores["property"] > 0

    def test_calculate_domain_scores_team(self, keyword_matcher):
        """Test calculating domain scores for team query"""
        scores = keyword_matcher.calculate_domain_scores("team member")
        assert scores["team"] > 0

    def test_calculate_domain_scores_books(self, keyword_matcher):
        """Test calculating domain scores for books query"""
        scores = keyword_matcher.calculate_domain_scores("philosophy")
        assert scores["books"] > 0

    def test_get_modifier_scores(self, keyword_matcher):
        """Test getting modifier scores"""
        scores = keyword_matcher.get_modifier_scores("tax calculation example")
        assert isinstance(scores, dict)

    def test_get_matched_keywords(self, keyword_matcher):
        """Test getting matched keywords"""
        matches = keyword_matcher.get_matched_keywords("visa application", "visa")
        assert isinstance(matches, list)
        assert len(matches) > 0

    def test_get_matched_keywords_no_match(self, keyword_matcher):
        """Test getting matched keywords with no match"""
        matches = keyword_matcher.get_matched_keywords("random query", "visa")
        assert isinstance(matches, list)

