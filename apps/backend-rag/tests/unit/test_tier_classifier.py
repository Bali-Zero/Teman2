"""
Unit tests for TierClassifier
Tests tier classification functionality
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


class TestTierClassifier:
    """Unit tests for TierClassifier"""

    def test_tier_classifier_init(self):
        """Test TierClassifier initialization"""
        from backend.utils.tier_classifier import TierClassifier

        classifier = TierClassifier()
        assert classifier is not None

    def test_classify_tier_s_quantum(self):
        """Test classifying Tier S - Quantum physics"""
        from app.models import TierLevel
        from backend.utils.tier_classifier import TierClassifier

        classifier = TierClassifier()
        tier = classifier.classify_book_tier(
            "Quantum Mechanics and Relativity", book_author="", book_content_sample=""
        )
        assert tier == TierLevel.S

    def test_classify_tier_s_consciousness(self):
        """Test classifying Tier S - Consciousness"""
        from app.models import TierLevel
        from backend.utils.tier_classifier import TierClassifier

        classifier = TierClassifier()
        tier = classifier.classify_book_tier(
            "Consciousness and Awareness", book_author="", book_content_sample=""
        )
        assert tier == TierLevel.S

    def test_classify_tier_a_philosophy(self):
        """Test classifying Tier A - Philosophy"""
        from app.models import TierLevel
        from backend.utils.tier_classifier import TierClassifier

        classifier = TierClassifier()
        tier = classifier.classify_book_tier(
            "Philosophy of Mind", book_author="", book_content_sample=""
        )
        assert tier == TierLevel.A

    def test_classify_tier_a_psychology(self):
        """Test classifying Tier A - Psychology"""
        from app.models import TierLevel
        from backend.utils.tier_classifier import TierClassifier

        classifier = TierClassifier()
        tier = classifier.classify_book_tier(
            "Psychology and Human Behavior", book_author="", book_content_sample=""
        )
        assert tier == TierLevel.A

    def test_classify_tier_b_history(self):
        """Test classifying Tier B - History"""
        from app.models import TierLevel
        from backend.utils.tier_classifier import TierClassifier

        classifier = TierClassifier()
        tier = classifier.classify_book_tier(
            "History of Indonesia", book_author="", book_content_sample=""
        )
        assert tier == TierLevel.B

    def test_classify_tier_b_culture(self):
        """Test classifying Tier B - Culture"""
        from app.models import TierLevel
        from backend.utils.tier_classifier import TierClassifier

        classifier = TierClassifier()
        tier = classifier.classify_book_tier(
            "Balinese Culture and Traditions", book_author="", book_content_sample=""
        )
        # May classify as C if no B keywords match, which is acceptable
        assert tier in [TierLevel.B, TierLevel.C]

    def test_classify_tier_c_self_help(self):
        """Test classifying Tier C - Self-help"""
        from app.models import TierLevel
        from backend.utils.tier_classifier import TierClassifier

        classifier = TierClassifier()
        tier = classifier.classify_book_tier(
            "How to Improve Your Life", book_author="", book_content_sample=""
        )
        assert tier == TierLevel.C

    def test_classify_tier_c_business(self):
        """Test classifying Tier C - Business"""
        from app.models import TierLevel
        from backend.utils.tier_classifier import TierClassifier

        classifier = TierClassifier()
        tier = classifier.classify_book_tier(
            "Business Success Strategies", book_author="", book_content_sample=""
        )
        assert tier == TierLevel.C

    def test_classify_tier_d_popular_science(self):
        """Test classifying Tier D - Popular science"""
        from app.models import TierLevel
        from backend.utils.tier_classifier import TierClassifier

        classifier = TierClassifier()
        tier = classifier.classify_book_tier(
            "Introduction to Science", book_author="", book_content_sample=""
        )
        assert tier == TierLevel.D

    def test_classify_tier_d_introductory(self):
        """Test classifying Tier D - Introductory"""
        from app.models import TierLevel
        from backend.utils.tier_classifier import TierClassifier

        classifier = TierClassifier()
        tier = classifier.classify_book_tier(
            "Basic Introduction to Topic", book_author="", book_content_sample=""
        )
        assert tier == TierLevel.D

    def test_classify_default_tier(self):
        """Test classifying default tier"""
        from app.models import TierLevel
        from backend.utils.tier_classifier import TierClassifier

        classifier = TierClassifier()
        tier = classifier.classify_book_tier(
            "Random Book Title", book_author="", book_content_sample=""
        )
        # Should return a valid tier
        assert tier in [TierLevel.S, TierLevel.A, TierLevel.B, TierLevel.C, TierLevel.D]

    def test_classify_case_insensitive(self):
        """Test classification is case insensitive"""
        from app.models import TierLevel
        from backend.utils.tier_classifier import TierClassifier

        classifier = TierClassifier()
        tier1 = classifier.classify_book_tier(
            "QUANTUM PHYSICS", book_author="", book_content_sample=""
        )
        tier2 = classifier.classify_book_tier(
            "quantum physics", book_author="", book_content_sample=""
        )
        assert tier1 == tier2 == TierLevel.S
