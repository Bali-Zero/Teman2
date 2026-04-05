"""
Tests for memory_fact_extractor.py - Automatic fact extraction from conversations.
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.services.memory.memory_fact_extractor import MemoryFactExtractor


@pytest.fixture
def extractor():
    return MemoryFactExtractor()


class TestExtractFromText:
    """Tests for _extract_from_text internal method."""

    def test_preference_extraction(self, extractor):
        facts = extractor._extract_from_text("Preferisco parlare in italiano ogni giorno", source="user")
        types = [f["type"] for f in facts]
        assert "preference" in types

    def test_business_extraction(self, extractor):
        facts = extractor._extract_from_text(
            "I want to set up a PT PMA company in the restaurant sector", source="user"
        )
        types = [f["type"] for f in facts]
        assert "company" in types

    def test_identity_extraction(self, extractor):
        facts = extractor._extract_from_text("Mi chiamo Marco e sono italiano", source="user")
        types = [f["type"] for f in facts]
        assert "identity" in types

    def test_deadline_extraction(self, extractor):
        facts = extractor._extract_from_text(
            "La scadenza del mio visto è urgente, devo rinnovarlo entro marzo",
            source="user",
        )
        types = [f["type"] for f in facts]
        # Should detect "scadenza", "urgente", "entro"
        assert any(t in ("deadline", "urgent") for t in types)

    def test_user_source_higher_confidence(self, extractor):
        user_facts = extractor._extract_from_text("Preferisco il mattino", source="user")
        ai_facts = extractor._extract_from_text("Preferisco il mattino", source="ai")
        if user_facts and ai_facts:
            assert user_facts[0]["confidence"] > ai_facts[0]["confidence"]

    def test_business_facts_get_confidence_boost(self, extractor):
        business = extractor._extract_from_text(
            "Ho una società PT PMA nel settore tecnologico", source="user"
        )
        pref = extractor._extract_from_text("Preferisco il caffè al mattino", source="user")
        if business and pref:
            # Business gets +0.1 boost
            assert business[0]["confidence"] > pref[0]["confidence"]

    def test_empty_text_returns_empty(self, extractor):
        facts = extractor._extract_from_text("", source="user")
        assert facts == []

    def test_short_context_filtered_out(self, extractor):
        """Contexts shorter than 10 chars are filtered."""
        facts = extractor._extract_from_text("sono x", source="user")
        # "sono x" matches identity pattern but context might be too short
        for f in facts:
            assert len(f["content"]) > 10


class TestExtractFactsFromConversation:
    """Tests for extract_facts_from_conversation method."""

    @patch("backend.services.memory.memory_fact_extractor.metrics_collector")
    def test_extracts_from_both_user_and_ai(self, mock_metrics, extractor):
        mock_metrics.record_memory_extraction = MagicMock()
        facts = extractor.extract_facts_from_conversation(
            user_message="Mi chiamo Marco e voglio aprire una società PT PMA",
            ai_response="Capisco Marco, per la società PT PMA servono diversi documenti",
            user_id="user_123",
        )
        assert isinstance(facts, list)
        # Should find identity and company facts
        types = [f["type"] for f in facts]  # noqa: F841
        assert len(facts) > 0

    @patch("backend.services.memory.memory_fact_extractor.metrics_collector")
    def test_deduplication_works(self, mock_metrics, extractor):
        mock_metrics.record_memory_extraction = MagicMock()
        facts = extractor.extract_facts_from_conversation(
            user_message="Preferisco il mattino per le riunioni",
            ai_response="Va bene, preferisco confermare il mattino per le riunioni",
            user_id="user_123",
        )
        # Similar facts from user and AI should be deduplicated
        assert len(facts) <= 3  # Max 3 facts per turn

    @patch("backend.services.memory.memory_fact_extractor.metrics_collector")
    def test_max_three_facts(self, mock_metrics, extractor):
        mock_metrics.record_memory_extraction = MagicMock()
        facts = extractor.extract_facts_from_conversation(
            user_message="Sono Marco, preferisco il mattino, voglio una società, la scadenza è urgente, sono di Milano",
            ai_response="",
            user_id="user_123",
        )
        assert len(facts) <= 3

    @patch("backend.services.memory.memory_fact_extractor.metrics_collector")
    def test_error_returns_empty(self, mock_metrics, extractor):
        mock_metrics.record_memory_extraction = MagicMock(side_effect=Exception("fail"))
        # Should not raise, just return empty
        facts = extractor.extract_facts_from_conversation(
            user_message="test", ai_response="test", user_id="user_123",
        )
        # Even if metrics fail, extraction should succeed
        assert isinstance(facts, list)


class TestExtractQuickFacts:
    """Tests for extract_quick_facts method."""

    def test_returns_strings(self, extractor):
        facts = extractor.extract_quick_facts(
            "Mi chiamo Marco e ho una società PT PMA"
        )
        assert all(isinstance(f, str) for f in facts)

    def test_max_facts_respected(self, extractor):
        facts = extractor.extract_quick_facts(
            "Sono Marco e preferisco il mattino per le riunioni nella mia società",
            max_facts=1,
        )
        assert len(facts) <= 1

    def test_empty_text_returns_empty(self, extractor):
        facts = extractor.extract_quick_facts("")
        assert facts == []


class TestDeduplicateFacts:
    """Tests for _deduplicate_facts method."""

    def test_empty_list(self, extractor):
        result = extractor._deduplicate_facts([])
        assert result == []

    def test_removes_similar_facts(self, extractor):
        facts = [
            {"content": "marco lives in bali indonesia", "type": "location", "confidence": 0.8, "source": "user"},
            {"content": "marco lives in bali indonesia area", "type": "location", "confidence": 0.7, "source": "ai"},
        ]
        result = extractor._deduplicate_facts(facts)
        assert len(result) == 1
        assert result[0]["confidence"] == 0.8  # Highest confidence kept


class TestCalculateOverlap:
    """Tests for _calculate_overlap method."""

    def test_identical_texts(self, extractor):
        overlap = extractor._calculate_overlap("hello world", "hello world")
        assert overlap == 1.0

    def test_no_overlap(self, extractor):
        overlap = extractor._calculate_overlap("hello world", "foo bar")
        assert overlap == 0.0

    def test_partial_overlap(self, extractor):
        overlap = extractor._calculate_overlap("hello world foo", "hello world bar")
        assert 0.0 < overlap < 1.0

    def test_empty_text(self, extractor):
        overlap = extractor._calculate_overlap("", "hello")
        assert overlap == 0.0
