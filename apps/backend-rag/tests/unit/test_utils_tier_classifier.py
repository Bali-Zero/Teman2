"""
Unit tests for Tier Classifier
Target: 100% coverage for backend/utils/tier_classifier.py
"""

import sys
from pathlib import Path

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from utils.tier_classifier import TierClassifier, classify_book_tier

from app.models import TierLevel

# ============================================================================
# Tests for TierClassifier.__init__
# ============================================================================


def test_tier_classifier_initialization():
    """Test TierClassifier initialization"""
    classifier = TierClassifier()

    # Verify patterns are compiled
    assert hasattr(classifier, "tier_patterns_compiled")
    assert len(classifier.tier_patterns_compiled) == 5  # S, A, B, C, D

    # Verify all tiers have compiled patterns
    for tier in [TierLevel.S, TierLevel.A, TierLevel.B, TierLevel.C, TierLevel.D]:
        assert tier in classifier.tier_patterns_compiled
        assert len(classifier.tier_patterns_compiled[tier]) > 0


# ============================================================================
# Tests for TierClassifier.classify_book_tier - Author-based classification
# ============================================================================


def test_classify_tier_s_by_author_david_bohm():
    """Test Tier S classification by author - David Bohm"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(
        book_title="Wholeness and the Implicate Order", book_author="David Bohm"
    )

    assert tier == TierLevel.S


def test_classify_tier_s_by_author_ramana_maharshi():
    """Test Tier S classification by author - Ramana Maharshi"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(book_title="Who Am I?", book_author="Ramana Maharshi")

    assert tier == TierLevel.S


def test_classify_tier_s_by_author_nisargadatta():
    """Test Tier S classification by author - Nisargadatta"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(book_title="I Am That", book_author="Nisargadatta Maharaj")

    assert tier == TierLevel.S


def test_classify_tier_s_by_author_jiddu_krishnamurti():
    """Test Tier S classification by author - Jiddu Krishnamurti"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(
        book_title="Freedom from the Known", book_author="Jiddu Krishnamurti"
    )

    assert tier == TierLevel.S


def test_classify_tier_a_by_author_carl_jung():
    """Test Tier A classification by author - Carl Jung"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(book_title="Man and His Symbols", book_author="Carl Jung")

    assert tier == TierLevel.A


def test_classify_tier_a_by_author_alan_watts():
    """Test Tier A classification by author - Alan Watts"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(book_title="The Way of Zen", book_author="Alan Watts")

    assert tier == TierLevel.A


def test_classify_tier_a_by_author_joseph_campbell():
    """Test Tier A classification by author - Joseph Campbell"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(
        book_title="The Hero with a Thousand Faces", book_author="Joseph Campbell"
    )

    assert tier == TierLevel.A


def test_classify_tier_a_by_author_ram_dass():
    """Test Tier A classification by author - Ram Dass"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(book_title="Be Here Now", book_author="Ram Dass")

    assert tier == TierLevel.A


# ============================================================================
# Tests for TierClassifier.classify_book_tier - Keyword-based classification
# ============================================================================


def test_classify_tier_s_by_keyword_quantum():
    """Test Tier S classification by keyword - quantum"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(
        book_title="Introduction to Quantum Mechanics", book_author="Unknown Author"
    )

    assert tier == TierLevel.S


def test_classify_tier_s_by_keyword_consciousness():
    """Test Tier S classification by keyword - consciousness"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(
        book_title="The Nature of Consciousness", book_author="John Doe"
    )

    assert tier == TierLevel.S


def test_classify_tier_s_by_keyword_enlightenment():
    """Test Tier S classification by keyword - enlightenment"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(
        book_title="The Path to Enlightenment", book_author="Unknown"
    )

    assert tier == TierLevel.S


def test_classify_tier_s_by_content_sample():
    """Test Tier S classification using content sample with nonduality"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(
        book_title="Spiritual Teachings",
        book_author="Unknown",
        book_content_sample="This book explores nonduality and the nature of awareness",
    )

    assert tier == TierLevel.S


def test_classify_tier_a_by_keyword_philosophy():
    """Test Tier A classification by keyword - philosophy"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(
        book_title="Introduction to Philosophy", book_author="Jane Smith"
    )

    assert tier == TierLevel.A


def test_classify_tier_a_by_keyword_psychology():
    """Test Tier A classification by keyword - psychology"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(book_title="Modern Psychology", book_author="Dr. Smith")

    assert tier == TierLevel.A


def test_classify_tier_a_by_keyword_buddhism():
    """Test Tier A classification by keyword - buddhism"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(book_title="Teachings of Buddhism", book_author="Unknown")

    assert tier == TierLevel.A


def test_classify_tier_b_by_keyword_history():
    """Test Tier B classification by keyword - history"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(book_title="World History", book_author="Historian")

    assert tier == TierLevel.B


def test_classify_tier_b_by_keyword_mythology():
    """Test Tier B classification by keyword - mythology"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(book_title="Greek Mythology", book_author="Unknown")

    assert tier == TierLevel.B


def test_classify_tier_b_by_keyword_meditation():
    """Test Tier B classification by keyword - meditation"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(book_title="The Art of Meditation", book_author="Unknown")

    assert tier == TierLevel.B


def test_classify_tier_c_by_keyword_business():
    """Test Tier C classification by keyword - business"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(
        book_title="Business Management", book_author="MBA Professor"
    )

    assert tier == TierLevel.C


def test_classify_tier_c_by_keyword_leadership():
    """Test Tier C classification by keyword - leadership"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(
        book_title="Leadership Principles", book_author="Executive Coach"
    )

    assert tier == TierLevel.C


def test_classify_tier_c_by_keyword_self_help():
    """Test Tier C classification by keyword - self-help"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(book_title="Self-Help Guide", book_author="Life Coach")

    assert tier == TierLevel.C


def test_classify_tier_d_by_keyword_introduction():
    """Test Tier D classification by keyword - introduction"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(
        book_title="Introduction to Programming", book_author="Tech Writer"
    )

    assert tier == TierLevel.D


def test_classify_tier_d_by_keyword_for_dummies():
    """Test Tier D classification by keyword - for dummies"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(book_title="Python for Dummies", book_author="Tech Author")

    assert tier == TierLevel.D


def test_classify_tier_d_by_keyword_beginners():
    """Test Tier D classification by keyword - beginners"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(
        book_title="Beginners Guide to Coding", book_author="Unknown"
    )

    assert tier == TierLevel.D


def test_classify_tier_d_by_keyword_basics():
    """Test Tier D classification by keyword - basics"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(
        book_title="JavaScript Basics", book_author="Web Developer"
    )

    assert tier == TierLevel.D


# ============================================================================
# Tests for TierClassifier.classify_book_tier - Default behavior
# ============================================================================


def test_classify_default_to_tier_c_no_matches():
    """Test default classification to Tier C when no keywords match"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(
        book_title="Random Book Title", book_author="Unknown Author"
    )

    assert tier == TierLevel.C


def test_classify_with_empty_strings():
    """Test classification with empty strings defaults to Tier C"""
    classifier = TierClassifier()

    tier = classifier.classify_book_tier(book_title="", book_author="", book_content_sample="")

    assert tier == TierLevel.C


def test_classify_case_insensitive():
    """Test that classification is case-insensitive"""
    classifier = TierClassifier()

    # Test uppercase
    tier_upper = classifier.classify_book_tier(
        book_title="QUANTUM PHYSICS", book_author="SCIENTIST"
    )

    # Test lowercase
    tier_lower = classifier.classify_book_tier(
        book_title="quantum physics", book_author="scientist"
    )

    # Test mixed case
    tier_mixed = classifier.classify_book_tier(
        book_title="QuAnTuM PhYsIcS", book_author="ScIeNtIsT"
    )

    assert tier_upper == TierLevel.S
    assert tier_lower == TierLevel.S
    assert tier_mixed == TierLevel.S


# ============================================================================
# Tests for TierClassifier.get_min_access_level
# ============================================================================


def test_get_min_access_level_tier_s():
    """Test minimum access level for Tier S"""
    classifier = TierClassifier()

    level = classifier.get_min_access_level(TierLevel.S)

    assert level == 0


def test_get_min_access_level_tier_a():
    """Test minimum access level for Tier A"""
    classifier = TierClassifier()

    level = classifier.get_min_access_level(TierLevel.A)

    assert level == 1


def test_get_min_access_level_tier_b():
    """Test minimum access level for Tier B"""
    classifier = TierClassifier()

    level = classifier.get_min_access_level(TierLevel.B)

    assert level == 2


def test_get_min_access_level_tier_c():
    """Test minimum access level for Tier C"""
    classifier = TierClassifier()

    level = classifier.get_min_access_level(TierLevel.C)

    assert level == 2


def test_get_min_access_level_tier_d():
    """Test minimum access level for Tier D"""
    classifier = TierClassifier()

    level = classifier.get_min_access_level(TierLevel.D)

    assert level == 3


# ============================================================================
# Tests for classify_book_tier convenience function
# ============================================================================


def test_convenience_function_classify_book_tier():
    """Test convenience function classify_book_tier"""
    tier = classify_book_tier(
        book_title="Introduction to Quantum Mechanics",
        book_author="Physicist",
        content_sample="This book covers quantum theory",
    )

    assert tier == "S"


def test_convenience_function_tier_a():
    """Test convenience function returns Tier A"""
    tier = classify_book_tier(book_title="Philosophy of Mind", book_author="Philosopher")

    assert tier == "A"


def test_convenience_function_tier_b():
    """Test convenience function returns Tier B"""
    tier = classify_book_tier(book_title="World History", book_author="Historian")

    assert tier == "B"


def test_convenience_function_tier_c():
    """Test convenience function returns Tier C"""
    tier = classify_book_tier(book_title="Business Leadership", book_author="CEO")

    assert tier == "C"


def test_convenience_function_tier_d():
    """Test convenience function returns Tier D"""
    tier = classify_book_tier(book_title="Introduction to Coding", book_author="Teacher")

    assert tier == "D"


def test_convenience_function_default():
    """Test convenience function defaults to Tier C"""
    tier = classify_book_tier(book_title="Some Random Book", book_author="")

    assert tier == "C"


# ============================================================================
# Edge cases and complex scenarios
# ============================================================================


def test_multiple_tier_keywords_highest_wins():
    """Test that when multiple tier keywords match, the one with most matches wins"""
    classifier = TierClassifier()

    # Book with both Tier S and Tier D keywords - Tier S should win if more matches
    tier = classifier.classify_book_tier(
        book_title="Introduction to Quantum Consciousness and Awakening", book_author="Unknown"
    )

    # Should be Tier S because "quantum", "consciousness", "awakening" are Tier S keywords
    # Even though "introduction" is a Tier D keyword
    assert tier == TierLevel.S


def test_author_overrides_keywords():
    """Test that author-based classification overrides keyword-based"""
    classifier = TierClassifier()

    # Book by Tier S author with Tier D keyword in title
    tier = classifier.classify_book_tier(
        book_title="Introduction to Something", book_author="David Bohm"
    )

    # Should be Tier S because author is Tier S, despite "introduction" keyword
    assert tier == TierLevel.S


def test_tier_a_author_overrides_lower_tier_keywords():
    """Test that Tier A author overrides lower tier keywords"""
    classifier = TierClassifier()

    # Book by Tier A author with Tier C and D keywords
    tier = classifier.classify_book_tier(
        book_title="Business Guide for Beginners", book_author="Carl Jung"
    )

    # Should be Tier A because author is Tier A
    assert tier == TierLevel.A


def test_content_sample_contributes_to_classification():
    """Test that content sample is included in classification"""
    classifier = TierClassifier()

    # Generic title but content sample has Tier S keywords
    tier = classifier.classify_book_tier(
        book_title="Advanced Topics",
        book_author="Unknown",
        book_content_sample="This book explores the nature of consciousness and quantum mechanics",
    )

    assert tier == TierLevel.S
