"""
Unit tests for ConfidenceCalculatorService
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.routing.confidence_calculator import ConfidenceCalculatorService


@pytest.fixture
def confidence_calculator():
    """Create ConfidenceCalculatorService instance"""
    return ConfidenceCalculatorService()


class TestConfidenceCalculatorService:
    """Tests for ConfidenceCalculatorService"""

    def test_init(self):
        """Test initialization"""
        calculator = ConfidenceCalculatorService()
        assert calculator.CONFIDENCE_THRESHOLD_HIGH > 0
        assert calculator.CONFIDENCE_THRESHOLD_LOW > 0

    def test_calculate_confidence_no_matches(self, confidence_calculator):
        """Test calculating confidence with no matches"""
        confidence = confidence_calculator.calculate_confidence(
            "random query", {"visa": 0, "legal": 0, "tax": 0}
        )
        assert confidence == 0.0

    def test_calculate_confidence_low_matches(self, confidence_calculator):
        """Test calculating confidence with low matches"""
        confidence = confidence_calculator.calculate_confidence(
            "visa", {"visa": 1, "legal": 0, "tax": 0}
        )
        assert 0.0 <= confidence <= 1.0

    def test_calculate_confidence_medium_matches(self, confidence_calculator):
        """Test calculating confidence with medium matches"""
        confidence = confidence_calculator.calculate_confidence(
            "visa application", {"visa": 3, "legal": 1, "tax": 0}
        )
        assert 0.0 <= confidence <= 1.0

    def test_calculate_confidence_high_matches(self, confidence_calculator):
        """Test calculating confidence with high matches"""
        confidence = confidence_calculator.calculate_confidence(
            "visa visa visa visa visa", {"visa": 5, "legal": 0, "tax": 0}
        )
        assert confidence > 0.5

    def test_calculate_confidence_long_query(self, confidence_calculator):
        """Test calculating confidence with long query"""
        long_query = " ".join(["visa"] * 15)
        confidence = confidence_calculator.calculate_confidence(
            long_query, {"visa": 2, "legal": 0, "tax": 0}
        )
        assert confidence > 0.0

    def test_calculate_confidence_clear_winner(self, confidence_calculator):
        """Test calculating confidence with clear winner"""
        confidence = confidence_calculator.calculate_confidence(
            "visa application", {"visa": 5, "legal": 1, "tax": 1}
        )
        assert confidence > 0.0

    def test_calculate_confidence_tie(self, confidence_calculator):
        """Test calculating confidence with tie"""
        confidence = confidence_calculator.calculate_confidence(
            "visa tax", {"visa": 2, "legal": 0, "tax": 2}
        )
        assert 0.0 <= confidence <= 1.0

    def test_get_confidence_level_high(self, confidence_calculator):
        """Test getting confidence level - high"""
        level = confidence_calculator.get_confidence_level(0.8)
        assert level == "high"

    def test_get_confidence_level_medium(self, confidence_calculator):
        """Test getting confidence level - medium"""
        level = confidence_calculator.get_confidence_level(0.5)
        assert level == "medium"

    def test_get_confidence_level_low(self, confidence_calculator):
        """Test getting confidence level - low"""
        level = confidence_calculator.get_confidence_level(0.2)
        assert level == "low"
