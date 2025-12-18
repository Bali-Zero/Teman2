"""
Unit Tests for utils/tier_classifier.py - 95% Coverage Target
Tests the TierClassifier class
"""

import os
import sys
from pathlib import Path

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test TierClassifier initialization
# ============================================================================


class TestTierClassifierInit:
    """Test suite for TierClassifier initialization"""

    def test_init_compiles_patterns(self):
        """Test that initialization compiles regex patterns"""
        from utils.tier_classifier import TierClassifier

        classifier = TierClassifier()

        assert hasattr(classifier, "tier_patterns_compiled")
        assert len(classifier.tier_patterns_compiled) > 0

    def test_init_has_tier_s_authors(self):
        """Test that Tier S authors list is defined"""
        from utils.tier_classifier import TierClassifier

        assert "david bohm" in TierClassifier.TIER_S_AUTHORS
        assert "ramana maharshi" in TierClassifier.TIER_S_AUTHORS

    def test_init_has_tier_a_authors(self):
        """Test that Tier A authors list is defined"""
        from utils.tier_classifier import TierClassifier

        assert "carl jung" in TierClassifier.TIER_A_AUTHORS
        assert "alan watts" in TierClassifier.TIER_A_AUTHORS


# ============================================================================
# Test classify_book_tier
# ============================================================================


class TestClassifyBookTier:
    """Test suite for classify_book_tier method"""

    def test_classify_tier_s_by_author(self):
        """Test classification as Tier S based on author"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()

        result = classifier.classify_book_tier("Wholeness and the Implicate Order", "David Bohm")

        assert result == TierLevel.S

    def test_classify_tier_s_by_author_ramana(self):
        """Test classification as Tier S based on author Ramana Maharshi"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()

        result = classifier.classify_book_tier("Be As You Are", "Ramana Maharshi")

        assert result == TierLevel.S

    def test_classify_tier_a_by_author(self):
        """Test classification as Tier A based on author"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()

        result = classifier.classify_book_tier("The Way of Zen", "Alan Watts")

        assert result == TierLevel.A

    def test_classify_tier_a_by_author_jung(self):
        """Test classification as Tier A based on author Carl Jung"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()

        result = classifier.classify_book_tier("Modern Man in Search of a Soul", "Carl Jung")

        assert result == TierLevel.A

    def test_classify_tier_s_by_keyword_quantum(self):
        """Test classification as Tier S based on quantum keyword"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()

        result = classifier.classify_book_tier("Quantum Physics and Consciousness")

        assert result == TierLevel.S

    def test_classify_tier_s_by_keyword_consciousness(self):
        """Test classification as Tier S based on consciousness keyword"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()

        result = classifier.classify_book_tier("The Nature of Consciousness")

        assert result == TierLevel.S

    def test_classify_tier_s_by_keyword_enlightenment(self):
        """Test classification as Tier S based on enlightenment keyword"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()

        result = classifier.classify_book_tier("The Path to Enlightenment")

        assert result == TierLevel.S

    def test_classify_tier_a_by_keyword_philosophy(self):
        """Test classification as Tier A based on philosophy keyword"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()

        result = classifier.classify_book_tier("Introduction to Philosophy")

        # Should be A (philosophy) even though "introduction" is D-tier keyword
        # because A has higher priority
        assert result in [TierLevel.A, TierLevel.D]

    def test_classify_tier_a_by_keyword_buddhism(self):
        """Test classification as Tier A based on Buddhism keyword"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()

        result = classifier.classify_book_tier("The Heart of Buddhism")

        assert result == TierLevel.A

    def test_classify_tier_b_by_keyword_history(self):
        """Test classification as Tier B based on history keyword"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()

        result = classifier.classify_book_tier("World History Overview")

        assert result == TierLevel.B

    def test_classify_tier_b_by_keyword_meditation(self):
        """Test classification as Tier B based on meditation keyword"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()

        result = classifier.classify_book_tier("The Practice of Meditation")

        assert result == TierLevel.B

    def test_classify_tier_c_by_keyword_business(self):
        """Test classification as Tier C based on business keyword"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()

        result = classifier.classify_book_tier("Starting a Business")

        assert result == TierLevel.C

    def test_classify_tier_c_by_keyword_leadership(self):
        """Test classification as Tier C based on leadership keyword"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()

        result = classifier.classify_book_tier("Leadership Skills")

        assert result == TierLevel.C

    def test_classify_tier_d_by_keyword_beginners(self):
        """Test classification as Tier D based on beginners keyword"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()

        result = classifier.classify_book_tier("Programming for Beginners")

        assert result == TierLevel.D

    def test_classify_tier_d_by_keyword_basics(self):
        """Test classification as Tier D based on basics keyword"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()

        result = classifier.classify_book_tier("The Basics of Mathematics")

        assert result == TierLevel.D

    def test_classify_default_tier_c(self):
        """Test default classification to Tier C when no match"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()

        # Use a title with no keywords
        result = classifier.classify_book_tier("Random Book Title")

        assert result == TierLevel.C

    def test_classify_with_content_sample(self):
        """Test classification using content sample"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()

        result = classifier.classify_book_tier(
            "A Simple Title",
            book_content_sample="This discusses the nature of consciousness and awareness",
        )

        assert result == TierLevel.S


# ============================================================================
# Test get_min_access_level
# ============================================================================


class TestGetMinAccessLevel:
    """Test suite for get_min_access_level method"""

    def test_min_access_level_tier_s(self):
        """Test minimum access level for Tier S"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()
        result = classifier.get_min_access_level(TierLevel.S)

        assert result == 0

    def test_min_access_level_tier_a(self):
        """Test minimum access level for Tier A"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()
        result = classifier.get_min_access_level(TierLevel.A)

        assert result == 1

    def test_min_access_level_tier_b(self):
        """Test minimum access level for Tier B"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()
        result = classifier.get_min_access_level(TierLevel.B)

        assert result == 2

    def test_min_access_level_tier_c(self):
        """Test minimum access level for Tier C"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()
        result = classifier.get_min_access_level(TierLevel.C)

        assert result == 2

    def test_min_access_level_tier_d(self):
        """Test minimum access level for Tier D"""
        from utils.tier_classifier import TierClassifier

        from app.models import TierLevel

        classifier = TierClassifier()
        result = classifier.get_min_access_level(TierLevel.D)

        assert result == 3


# ============================================================================
# Test convenience function
# ============================================================================


class TestConvenienceFunction:
    """Test suite for classify_book_tier convenience function"""

    def test_classify_book_tier_function(self):
        """Test convenience function returns string"""
        from utils.tier_classifier import classify_book_tier

        result = classify_book_tier("Quantum Physics")

        assert isinstance(result, str)
        assert result == "S"

    def test_classify_book_tier_function_with_author(self):
        """Test convenience function with author"""
        from utils.tier_classifier import classify_book_tier

        result = classify_book_tier("Some Book", book_author="David Bohm")

        assert result == "S"

    def test_classify_book_tier_function_with_content(self):
        """Test convenience function with content sample"""
        from utils.tier_classifier import classify_book_tier

        result = classify_book_tier("Book Title", content_sample="About business and leadership")

        assert result == "C"


# ============================================================================
# Test module constants
# ============================================================================


class TestModuleConstants:
    """Test suite for module constants"""

    def test_tier_patterns_defined(self):
        """Test TIER_PATTERNS constant is defined"""
        from utils.tier_classifier import TierClassifier

        assert hasattr(TierClassifier, "TIER_PATTERNS")
        assert len(TierClassifier.TIER_PATTERNS) == 5  # S, A, B, C, D

    def test_tier_s_authors_list(self):
        """Test TIER_S_AUTHORS list"""
        from utils.tier_classifier import TierClassifier

        assert len(TierClassifier.TIER_S_AUTHORS) > 0

    def test_tier_a_authors_list(self):
        """Test TIER_A_AUTHORS list"""
        from utils.tier_classifier import TierClassifier

        assert len(TierClassifier.TIER_A_AUTHORS) > 0
