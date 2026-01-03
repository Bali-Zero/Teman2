"""
Unit tests for tier classifier
Target: >95% coverage
"""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from utils.tier_classifier import TierClassifier

from app.models import TierLevel


@pytest.fixture
def classifier():
    """Create TierClassifier instance"""
    return TierClassifier()


class TestTierClassifier:
    """Tests for TierClassifier"""

    def test_classify_tier_s_quantum(self, classifier):
        """Test classifying Tier S - quantum physics"""
        result = classifier.classify_book_tier("Quantum Mechanics and Relativity", "Author")
        assert result == TierLevel.S

    def test_classify_tier_s_consciousness(self, classifier):
        """Test classifying Tier S - consciousness"""
        result = classifier.classify_book_tier("The Nature of Consciousness and Awareness", "Author")
        assert result == TierLevel.S

    def test_classify_tier_a_philosophy(self, classifier):
        """Test classifying Tier A - philosophy"""
        result = classifier.classify_book_tier("Introduction to Philosophy", "Author")
        assert result == TierLevel.A

    def test_classify_tier_b_history(self, classifier):
        """Test classifying Tier B - history"""
        result = classifier.classify_book_tier("World History and Culture", "Author")
        assert result == TierLevel.B

    def test_classify_tier_c_business(self, classifier):
        """Test classifying Tier C - business"""
        result = classifier.classify_book_tier("Business Management and Strategy", "Author")
        assert result == TierLevel.C

    def test_classify_tier_d_popular(self, classifier):
        """Test classifying Tier D - popular science"""
        result = classifier.classify_book_tier("Popular Science Introduction", "Author")
        assert result == TierLevel.D

    def test_classify_default_tier(self, classifier):
        """Test default tier classification"""
        result = classifier.classify_book_tier("Random Book Title", "Author")
        assert result in [TierLevel.S, TierLevel.A, TierLevel.B, TierLevel.C, TierLevel.D]

    def test_get_min_access_level(self, classifier):
        """Test getting minimum access level"""
        assert classifier.get_min_access_level(TierLevel.S) == 0
        assert classifier.get_min_access_level(TierLevel.A) == 1
        assert classifier.get_min_access_level(TierLevel.B) == 2
        assert classifier.get_min_access_level(TierLevel.C) == 2
        assert classifier.get_min_access_level(TierLevel.D) == 3

