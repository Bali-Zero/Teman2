"""
Integration Tests for MemoryFactExtractor
Tests fact extraction from conversations
"""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture(scope="function")
def fact_extractor():
    """Create MemoryFactExtractor instance"""
    from services.memory_fact_extractor import MemoryFactExtractor

    return MemoryFactExtractor()


@pytest.mark.integration
class TestMemoryFactExtractorIntegration:
    """Comprehensive integration tests for MemoryFactExtractor"""

    def test_extract_preference_facts(self, fact_extractor):
        """Test extracting preference facts"""
        user_message = "I prefer to communicate in English and I like morning meetings."
        ai_response = "Understood, I will communicate in English and schedule morning meetings."

        facts = fact_extractor.extract_facts_from_conversation(
            user_message, ai_response, user_id="test_user_1"
        )

        assert len(facts) > 0
        assert any(f["type"] == "preference" for f in facts)

    def test_extract_business_facts(self, fact_extractor):
        """Test extracting business information facts"""
        user_message = (
            "I want to set up a PT PMA company with KBLI code 56101 for restaurant business."
        )
        ai_response = (
            "PT PMA setup requires capital investment and KBLI 56101 is for restaurant services."
        )

        facts = fact_extractor.extract_facts_from_conversation(
            user_message, ai_response, user_id="test_user_2"
        )

        assert len(facts) > 0
        assert any(f["type"] in ["company", "kbli", "industry"] for f in facts)

    def test_extract_personal_facts(self, fact_extractor):
        """Test extracting personal information facts"""
        user_message = "I am John Smith, I am American, and I live in Bali."
        ai_response = "Nice to meet you John Smith. As an American living in Bali..."

        facts = fact_extractor.extract_facts_from_conversation(
            user_message, ai_response, user_id="test_user_3"
        )

        assert len(facts) > 0
        assert any(f["type"] in ["identity", "nationality", "location"] for f in facts)

    def test_extract_timeline_facts(self, fact_extractor):
        """Test extracting timeline/deadline facts"""
        user_message = "I need this done by next month, it is urgent!"
        ai_response = (
            "I understand the deadline is next month. We will prioritize this urgent request."
        )

        facts = fact_extractor.extract_facts_from_conversation(
            user_message, ai_response, user_id="test_user_4"
        )

        assert len(facts) > 0
        assert any(f["type"] in ["deadline", "urgent", "upcoming"] for f in facts)

    def test_extract_from_user_message_priority(self, fact_extractor):
        """Test that user message facts have higher confidence"""
        user_message = "I prefer Italian language."
        ai_response = "OK, I will use Italian."

        facts = fact_extractor.extract_facts_from_conversation(
            user_message, ai_response, user_id="test_user_5"
        )

        user_facts = [f for f in facts if f.get("source") == "user"]
        ai_facts = [f for f in facts if f.get("source") == "ai"]

        if user_facts:
            assert user_facts[0]["confidence"] >= ai_facts[0]["confidence"] if ai_facts else True

    def test_deduplicate_facts(self, fact_extractor):
        """Test fact deduplication"""
        user_message = "I prefer Italian. I like Italian language. Italian is my preference."
        ai_response = "I understand you prefer Italian."

        facts = fact_extractor.extract_facts_from_conversation(
            user_message, ai_response, user_id="test_user_6"
        )

        # Should deduplicate similar facts
        assert len(facts) <= 3  # Limited to top 3 per conversation turn

    def test_extract_quick_facts(self, fact_extractor):
        """Test quick fact extraction"""
        text = (
            "I am John Smith, American, living in Bali, and I want to set up a PT PMA restaurant."
        )

        quick_facts = fact_extractor.extract_quick_facts(text, max_facts=2)

        assert len(quick_facts) <= 2
        assert all(isinstance(fact, str) for fact in quick_facts)
        assert all(len(fact) > 0 for fact in quick_facts)

    def test_multilingual_extraction(self, fact_extractor):
        """Test extraction from multilingual messages"""
        user_message = "Sono italiano, vivo a Bali, e voglio aprire un ristorante PT PMA."
        ai_response = "Capisco, sei italiano e vivi a Bali. Per aprire un ristorante PT PMA..."

        facts = fact_extractor.extract_facts_from_conversation(
            user_message, ai_response, user_id="test_user_7"
        )

        # Should extract facts even from Italian text
        assert len(facts) > 0

    def test_complex_conversation_extraction(self, fact_extractor):
        """Test extraction from complex multi-topic conversation"""
        user_message = """
        I am John Smith, American, living in Seminyak, Bali.
        I want to set up a PT PMA restaurant business with KBLI 56101.
        I need this done by next month as it's urgent.
        I prefer to communicate in English and have meetings in the morning.
        """
        ai_response = """
        Understood John Smith. As an American in Seminyak, we can help set up your PT PMA restaurant
        with KBLI 56101. We'll prioritize the next month deadline and communicate in English with
        morning meetings as preferred.
        """

        facts = fact_extractor.extract_facts_from_conversation(
            user_message, ai_response, user_id="test_user_8"
        )

        # Should extract multiple types of facts
        fact_types = {f["type"] for f in facts}
        assert len(fact_types) > 1  # Should have multiple fact types

    def test_empty_messages(self, fact_extractor):
        """Test handling empty messages"""
        facts = fact_extractor.extract_facts_from_conversation("", "", user_id="test_user_9")

        assert isinstance(facts, list)
        assert len(facts) == 0

    def test_fact_confidence_scoring(self, fact_extractor):
        """Test that facts have appropriate confidence scores"""
        user_message = "I am John Smith, American, living in Bali."
        ai_response = "Nice to meet you John Smith."

        facts = fact_extractor.extract_facts_from_conversation(
            user_message, ai_response, user_id="test_user_10"
        )

        for fact in facts:
            assert 0.0 <= fact["confidence"] <= 1.0
            assert "content" in fact
            assert "type" in fact
            assert "source" in fact

    def test_context_extraction(self, fact_extractor):
        """Test that extracted facts include context"""
        user_message = "I want to set up a PT PMA company for restaurant business."
        ai_response = "PT PMA setup for restaurant requires KBLI code 56101."

        facts = fact_extractor.extract_facts_from_conversation(
            user_message, ai_response, user_id="test_user_11"
        )

        for fact in facts:
            assert len(fact["content"]) > 10  # Should have meaningful context
            assert "PT PMA" in fact["content"] or "restaurant" in fact["content"].lower()

    def test_clean_context(self, fact_extractor):
        """Test context cleaning removes markdown and extra whitespace"""
        user_message = "I **prefer** Italian language and __like__ morning meetings."
        ai_response = "Understood."

        facts = fact_extractor.extract_facts_from_conversation(
            user_message, ai_response, user_id="test_user_12"
        )

        for fact in facts:
            # Should not contain markdown
            assert "**" not in fact["content"]
            assert "__" not in fact["content"]
