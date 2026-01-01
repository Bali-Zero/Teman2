"""
Unit tests for ClarificationService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.clarification_service import ClarificationService, AmbiguityType


@pytest.fixture
def clarification_service():
    """Create ClarificationService instance"""
    return ClarificationService()


class TestClarificationService:
    """Tests for ClarificationService"""

    def test_init(self):
        """Test initialization"""
        service = ClarificationService()
        assert service.ambiguity_threshold == 0.6
        assert service.search_service is None

    def test_init_with_search_service(self):
        """Test initialization with search service"""
        mock_search = MagicMock()
        service = ClarificationService(search_service=mock_search)
        assert service.search_service == mock_search

    def test_detect_ambiguity_vague(self, clarification_service):
        """Test detecting vague ambiguity"""
        result = clarification_service.detect_ambiguity("Tell me about visas")
        assert result["is_ambiguous"] is True
        assert result["ambiguity_type"] == AmbiguityType.VAGUE.value

    def test_detect_ambiguity_incomplete(self, clarification_service):
        """Test detecting incomplete ambiguity"""
        result = clarification_service.detect_ambiguity("How much does it cost?")
        assert result["is_ambiguous"] is True
        assert result["ambiguity_type"] == AmbiguityType.INCOMPLETE.value

    def test_detect_ambiguity_multiple_interpretations(self, clarification_service):
        """Test detecting multiple interpretations"""
        result = clarification_service.detect_ambiguity("Can I work?")
        assert result["is_ambiguous"] is True
        assert result["ambiguity_type"] == AmbiguityType.MULTIPLE_INTERPRETATIONS.value

    def test_detect_ambiguity_unclear_context(self, clarification_service):
        """Test detecting unclear context"""
        result = clarification_service.detect_ambiguity("What about it?")
        assert result["is_ambiguous"] is True
        assert result["ambiguity_type"] == AmbiguityType.UNCLEAR_CONTEXT.value

    def test_detect_ambiguity_none(self, clarification_service):
        """Test detecting no ambiguity"""
        result = clarification_service.detect_ambiguity("How do I apply for a KITAS visa?")
        assert result["is_ambiguous"] is False
        assert result["ambiguity_type"] == AmbiguityType.NONE.value

    def test_detect_ambiguity_with_history(self, clarification_service):
        """Test detecting ambiguity with conversation history"""
        history = [
            {"role": "user", "content": "Tell me about visas"},
            {"role": "assistant", "content": "There are several types..."}
        ]
        result = clarification_service.detect_ambiguity("What about it?", history)
        assert isinstance(result, dict)
        assert "is_ambiguous" in result

    def test_generate_clarification_question(self, clarification_service):
        """Test generating clarification question"""
        result = clarification_service.generate_clarification_question(
            query="Tell me about visas",
            ambiguity_type=AmbiguityType.VAGUE,
            language="en"
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_clarification_question_italian(self, clarification_service):
        """Test generating clarification question in Italian"""
        result = clarification_service.generate_clarification_question(
            query="Dimmi dei visti",
            ambiguity_type=AmbiguityType.VAGUE,
            language="it"
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_clarification_question_indonesian(self, clarification_service):
        """Test generating clarification question in Indonesian"""
        result = clarification_service.generate_clarification_question(
            query="Ceritakan tentang visa",
            ambiguity_type=AmbiguityType.VAGUE,
            language="id"
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_should_request_clarification_true(self, clarification_service):
        """Test should request clarification when ambiguous"""
        ambiguity_result = {
            "is_ambiguous": True,
            "confidence": 0.8,
            "ambiguity_type": AmbiguityType.VAGUE.value
        }
        result = clarification_service.should_request_clarification(ambiguity_result)
        assert result is True

    def test_should_request_clarification_false(self, clarification_service):
        """Test should not request clarification when not ambiguous"""
        ambiguity_result = {
            "is_ambiguous": False,
            "confidence": 0.3,
            "ambiguity_type": AmbiguityType.NONE.value
        }
        result = clarification_service.should_request_clarification(ambiguity_result)
        assert result is False

    def test_should_request_clarification_low_confidence(self, clarification_service):
        """Test should not request clarification with low confidence"""
        ambiguity_result = {
            "is_ambiguous": True,
            "confidence": 0.4,  # Below threshold
            "ambiguity_type": AmbiguityType.VAGUE.value
        }
        result = clarification_service.should_request_clarification(ambiguity_result)
        assert result is False
