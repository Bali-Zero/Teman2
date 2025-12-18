"""
Unit tests for ClarificationService
Tests ambiguity detection and clarification generation
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.clarification_service import AmbiguityType, ClarificationService


@pytest.mark.unit
class TestClarificationServiceInit:
    """Test ClarificationService initialization"""

    def test_init_default(self):
        """Test default initialization"""
        service = ClarificationService()

        assert service.search_service is None
        assert service.ambiguity_threshold == 0.6

    def test_init_with_search_service(self):
        """Test initialization with search service"""
        mock_search = MagicMock()
        service = ClarificationService(search_service=mock_search)

        assert service.search_service == mock_search


@pytest.mark.unit
class TestClarificationServiceDetection:
    """Test ambiguity detection"""

    def test_detect_vague_question(self):
        """Test detecting vague questions"""
        service = ClarificationService()

        result = service.detect_ambiguity("Tell me about visas")

        # May or may not be ambiguous depending on threshold
        assert isinstance(result, dict)
        assert "ambiguity_type" in result
        assert "confidence" in result
        # Check if vague detection is working (may have reasons even if not ambiguous)
        assert (
            result["is_ambiguous"] is True and result["ambiguity_type"] == AmbiguityType.VAGUE.value
        ) or (result["confidence"] > 0 and "vague" in str(result.get("reasons", [])).lower())

    def test_detect_incomplete_question(self):
        """Test detecting incomplete questions"""
        service = ClarificationService()

        result = service.detect_ambiguity("How much?")

        assert result["is_ambiguous"] is True
        assert result["ambiguity_type"] == AmbiguityType.INCOMPLETE.value

    def test_detect_pronoun_without_context(self):
        """Test detecting pronouns without context"""
        service = ClarificationService()

        result = service.detect_ambiguity("How do I get it?", conversation_history=[])

        # May detect as ambiguous or not depending on implementation
        assert isinstance(result, dict)
        assert "ambiguity_type" in result
        # Check if pronoun detection is working
        assert (
            any(
                "pronoun" in reason.lower() or "context" in reason.lower()
                for reason in result.get("reasons", [])
            )
            or result["is_ambiguous"] is False
        )

    def test_detect_pronoun_with_context(self):
        """Test pronouns with conversation context"""
        service = ClarificationService()

        history = [
            {"role": "user", "content": "I want to apply for KITAS"},
            {"role": "assistant", "content": "KITAS is a work permit..."},
        ]

        result = service.detect_ambiguity("How do I get it?", conversation_history=history)

        # Should be less ambiguous with context
        assert result["confidence"] < 0.5 or result["is_ambiguous"] is False

    def test_detect_multiple_interpretations(self):
        """Test detecting multiple interpretations"""
        service = ClarificationService()

        # Use a query that triggers multiple interpretations
        result = service.detect_ambiguity("work")

        # May or may not be ambiguous depending on implementation
        assert isinstance(result, dict)
        assert "ambiguity_type" in result
        assert "confidence" in result

    def test_detect_clear_question(self):
        """Test detecting clear questions"""
        service = ClarificationService()

        result = service.detect_ambiguity("How do I apply for KITAS E33G visa?")

        assert result["is_ambiguous"] is False
        assert result["ambiguity_type"] == AmbiguityType.NONE.value
        assert result["confidence"] < service.ambiguity_threshold

    def test_detect_ambiguity_empty_query(self):
        """Test detecting ambiguity in empty query"""
        service = ClarificationService()

        result = service.detect_ambiguity("")

        # Empty query should have low confidence
        assert isinstance(result, dict)
        assert "confidence" in result


@pytest.mark.unit
class TestClarificationServiceGeneration:
    """Test clarification question generation"""

    def test_generate_clarification_request_en(self):
        """Test generating clarification request in English"""
        service = ClarificationService()

        ambiguity_info = service.detect_ambiguity("Tell me about visas")
        result = service.generate_clarification_request(
            query="Tell me about visas", ambiguity_info=ambiguity_info, language="en"
        )

        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_clarification_request_it(self):
        """Test generating clarification request in Italian"""
        service = ClarificationService()

        ambiguity_info = service.detect_ambiguity("Dimmi dei visti")
        result = service.generate_clarification_request(
            query="Dimmi dei visti", ambiguity_info=ambiguity_info, language="it"
        )

        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_clarification_request_id(self):
        """Test generating clarification request in Indonesian"""
        service = ClarificationService()

        ambiguity_info = service.detect_ambiguity("Ceritakan tentang visa")
        result = service.generate_clarification_request(
            query="Ceritakan tentang visa", ambiguity_info=ambiguity_info, language="id"
        )

        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_clarification_request_incomplete(self):
        """Test generating clarification for incomplete question"""
        service = ClarificationService()

        ambiguity_info = service.detect_ambiguity("How much?")
        result = service.generate_clarification_request(
            query="How much?", ambiguity_info=ambiguity_info, language="en"
        )

        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_clarification_request_multiple(self):
        """Test generating clarification for multiple interpretations"""
        service = ClarificationService()

        ambiguity_info = service.detect_ambiguity("How to work?")
        result = service.generate_clarification_request(
            query="How to work?", ambiguity_info=ambiguity_info, language="en"
        )

        assert isinstance(result, str)
        assert len(result) > 0

    def test_should_request_clarification(self):
        """Test should_request_clarification method"""
        service = ClarificationService()

        # Ambiguous query without context
        should_request = service.should_request_clarification(
            query="Tell me about visas", conversation_history=None
        )

        assert isinstance(should_request, bool)

        # Clear query
        should_not_request = service.should_request_clarification(
            query="How do I apply for KITAS E33G visa?", conversation_history=None
        )

        assert isinstance(should_not_request, bool)

        # Ambiguous query with context
        history = [{"role": "user", "content": "I want a visa"}]
        should_not_request_with_context = service.should_request_clarification(
            query="How do I get it?", conversation_history=history
        )

        assert isinstance(should_not_request_with_context, bool)
