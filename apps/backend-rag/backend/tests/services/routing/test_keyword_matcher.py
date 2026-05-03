"""
Tests for keyword_matcher.py - Domain keyword matching for query routing.
"""

import pytest

from backend.services.routing.keyword_matcher import KeywordMatcherService


@pytest.fixture
def matcher():
    return KeywordMatcherService()


class TestCalculateDomainScores:
    """Tests for calculate_domain_scores method."""

    def test_visa_query_scores_visa_domain(self, matcher):
        scores = matcher.calculate_domain_scores("I need a visa for Indonesia")
        assert scores["visa"] > 0
        assert scores["kbli"] == 0

    def test_kbli_query_scores_kbli_domain(self, matcher):
        scores = matcher.calculate_domain_scores("What is the KBLI code for restaurant business?")
        assert scores["kbli"] > 0

    def test_tax_query(self, matcher):
        scores = matcher.calculate_domain_scores("How to calculate income tax in Indonesia?")
        assert scores["tax"] > 0

    def test_legal_query(self, matcher):
        scores = matcher.calculate_domain_scores("What are the requirements for company formation?")
        assert scores["legal"] > 0

    def test_property_query(self, matcher):
        scores = matcher.calculate_domain_scores("I want to buy a villa in Bali")
        assert scores["property"] > 0

    def test_multi_domain_query(self, matcher):
        scores = matcher.calculate_domain_scores(
            "I need a visa and want to set up a company with KBLI code"
        )
        assert scores["visa"] > 0
        assert scores["legal"] > 0
        assert scores["kbli"] > 0

    def test_italian_keywords_recognized(self, matcher):
        scores = matcher.calculate_domain_scores("Ho bisogno di un visto per l'immigrazione")
        assert scores["visa"] > 0

    def test_empty_query_zero_scores(self, matcher):
        scores = matcher.calculate_domain_scores("")
        assert all(v == 0 for v in scores.values())

    def test_case_insensitive(self, matcher):
        scores_lower = matcher.calculate_domain_scores("visa immigration")
        scores_upper = matcher.calculate_domain_scores("VISA IMMIGRATION")
        assert scores_lower["visa"] == scores_upper["visa"]

    def test_team_query(self, matcher):
        scores = matcher.calculate_domain_scores("Who are the team members? Chi lavora qui?")
        assert scores["team"] > 0

    def test_news_query(self, matcher):
        scores = matcher.calculate_domain_scores("What are the latest news and updates?")
        assert scores["news"] > 0

    def test_business_setup_query(self, matcher):
        scores = matcher.calculate_domain_scores("How to set up a PT PMA in Bali? Minimum capital?")
        assert scores["business"] > 0

    def test_books_query(self, matcher):
        scores = matcher.calculate_domain_scores("Tell me about Plato and the Republic")
        assert scores["books"] > 0

    def test_circular_keywords(self, matcher):
        scores = matcher.calculate_domain_scores("alih status kesamaan sponsor surat edaran kemnaker")
        assert scores["circular"] > 0


class TestGetModifierScores:
    """Tests for get_modifier_scores method."""

    def test_update_modifier(self, matcher):
        scores = matcher.get_modifier_scores("What are the latest updates on visa regulations?")
        assert scores["updates"] > 0

    def test_tax_genius_modifier(self, matcher):
        scores = matcher.get_modifier_scores("How to calculate tax rate step by step?")
        assert scores["tax_genius"] > 0

    def test_no_modifiers(self, matcher):
        scores = matcher.get_modifier_scores("hello world")
        assert scores["updates"] == 0
        assert scores["tax_genius"] == 0


class TestGetMatchedKeywords:
    """Tests for get_matched_keywords method."""

    def test_returns_matched_keywords(self, matcher):
        keywords = matcher.get_matched_keywords("I need a visa and passport", "visa")
        assert "visa" in keywords
        assert "passport" in keywords

    def test_unknown_domain_returns_empty(self, matcher):
        keywords = matcher.get_matched_keywords("visa", "nonexistent_domain")
        assert keywords == []

    def test_no_match_returns_empty(self, matcher):
        keywords = matcher.get_matched_keywords("hello world", "visa")
        assert keywords == []


class TestDetectMultiDomain:
    """Tests for detect_multi_domain method."""

    def test_single_domain(self, matcher):
        domains = matcher.detect_multi_domain("I need a visa")
        assert "visa" in domains

    def test_multi_domain_detected(self, matcher):
        domains = matcher.detect_multi_domain(
            "I need a visa and also want to know the KBLI code for my company"
        )
        assert len(domains) >= 2

    def test_high_threshold_filters_weak_matches(self, matcher):
        domains = matcher.detect_multi_domain("visa", threshold=5)
        # "visa" query matches few keywords, should be filtered with threshold=5
        assert len(domains) == 0

    def test_no_domains_on_generic_query(self, matcher):
        domains = matcher.detect_multi_domain("hello there how are you today", threshold=1)
        assert len(domains) == 0
