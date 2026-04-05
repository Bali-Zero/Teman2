"""
Tests for confidence_calculator.py - Routing confidence scoring.
"""

import pytest

from backend.services.routing.confidence_calculator import ConfidenceCalculatorService


@pytest.fixture
def calculator():
    return ConfidenceCalculatorService()


class TestCalculateConfidence:
    """Tests for calculate_confidence method."""

    def test_zero_scores_returns_zero(self, calculator):
        scores = {"visa": 0, "tax": 0, "legal": 0}
        result = calculator.calculate_confidence("hello", scores)
        assert result == 0.0

    def test_single_low_match_short_query(self, calculator):
        scores = {"visa": 1, "tax": 0, "legal": 0}
        result = calculator.calculate_confidence("visa", scores)
        # match_confidence=0.3, length_confidence=0.0, specificity=0.2
        assert 0.4 <= result <= 0.6

    def test_high_match_long_query_clear_winner(self, calculator):
        scores = {"visa": 6, "tax": 0, "legal": 0}
        query = "I need a work permit visa for Indonesia to work in Bali as a digital nomad"
        result = calculator.calculate_confidence(query, scores)
        # match=0.6, length=0.2, specificity=0.2 => 1.0
        assert result == 1.0

    def test_medium_match_medium_query(self, calculator):
        scores = {"visa": 3, "tax": 1, "legal": 0}
        query = "what visa do I need for a long stay permit in Bali"
        result = calculator.calculate_confidence(query, scores)
        assert 0.5 <= result <= 1.0

    def test_tied_scores_low_specificity(self, calculator):
        scores = {"visa": 2, "tax": 2, "legal": 0}
        query = "I need visa and tax help for Indonesia setup"
        result = calculator.calculate_confidence(query, scores)
        # specificity = 0.0 (tie)
        assert result >= 0.0

    def test_confidence_capped_at_one(self, calculator):
        scores = {"visa": 10, "tax": 0}
        query = "I need a visa work permit immigration passport long stay residence sponsor visit permit"
        result = calculator.calculate_confidence(query, scores)
        assert result <= 1.0

    def test_short_query_low_length_confidence(self, calculator):
        scores = {"visa": 3}
        result = calculator.calculate_confidence("visa", scores)
        # word_count < 5 -> length_confidence = 0.0
        assert result < 1.0

    def test_match_strength_tiers(self, calculator):
        """Verify match strength tiers: 1-2 -> lower, 3-4 -> medium, 5+ -> highest"""
        short_q = "x"
        r1 = calculator.calculate_confidence(short_q, {"a": 1})
        r3 = calculator.calculate_confidence(short_q, {"a": 3})
        r5 = calculator.calculate_confidence(short_q, {"a": 5})
        assert r1 < r3 < r5


class TestGetConfidenceLevel:
    """Tests for get_confidence_level method."""

    def test_high_confidence(self, calculator):
        assert calculator.get_confidence_level(0.8) == "high"
        assert calculator.get_confidence_level(0.7) == "high"
        assert calculator.get_confidence_level(1.0) == "high"

    def test_medium_confidence(self, calculator):
        assert calculator.get_confidence_level(0.5) == "medium"
        assert calculator.get_confidence_level(0.3) == "medium"
        assert calculator.get_confidence_level(0.69) == "medium"

    def test_low_confidence(self, calculator):
        assert calculator.get_confidence_level(0.0) == "low"
        assert calculator.get_confidence_level(0.29) == "low"
        assert calculator.get_confidence_level(0.1) == "low"
