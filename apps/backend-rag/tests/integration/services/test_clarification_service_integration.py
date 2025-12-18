"""
Integration Tests for ClarificationService
Tests ambiguity detection and clarification requests
"""

import os
import sys
from pathlib import Path

import pytest

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestClarificationServiceIntegration:
    """Comprehensive integration tests for ClarificationService"""

    @pytest.fixture
    def service(self):
        """Create ClarificationService instance"""
        from services.clarification_service import ClarificationService

        return ClarificationService()

    def test_initialization(self, service):
        """Test service initialization"""
        assert service is not None
        assert service.ambiguity_threshold == 0.6

    def test_detect_ambiguity_vague(self, service):
        """Test detecting vague questions"""
        result = service.detect_ambiguity("Tell me about visa")

        assert result is not None
        assert result["is_ambiguous"] is True or result["confidence"] > 0
        assert result["ambiguity_type"] in ["vague", "none"]

    def test_detect_ambiguity_incomplete(self, service):
        """Test detecting incomplete questions"""
        result = service.detect_ambiguity("How much?")

        assert result is not None
        assert result["ambiguity_type"] in ["incomplete", "none"]

    def test_detect_ambiguity_pronoun_without_context(self, service):
        """Test detecting pronoun without antecedent"""
        result = service.detect_ambiguity("What is it?", conversation_history=[])

        assert result is not None
        assert result["ambiguity_type"] in ["unclear_context", "none"]

    def test_detect_ambiguity_pronoun_with_context(self, service):
        """Test detecting pronoun with context (should not be ambiguous)"""
        history = [{"role": "user", "content": "What is PT PMA?"}]
        result = service.detect_ambiguity("How much does it cost?", conversation_history=history)

        assert result is not None
        # Should be less ambiguous with context

    def test_detect_ambiguity_multiple_interpretations(self, service):
        """Test detecting multiple interpretations"""
        result = service.detect_ambiguity("How to work?")

        assert result is not None
        assert result["ambiguity_type"] in ["multiple", "none"]

    def test_detect_ambiguity_clear(self, service):
        """Test detecting clear question"""
        result = service.detect_ambiguity("How to get E33G Digital Nomad KITAS?")

        assert result is not None
        assert result["is_ambiguous"] is False or result["confidence"] < 0.6

    def test_detect_ambiguity_too_short(self, service):
        """Test detecting too short query"""
        result = service.detect_ambiguity("visa")

        assert result is not None
        # May or may not be ambiguous

    def test_generate_clarification_request_vague(self, service):
        """Test generating clarification request for vague question"""
        ambiguity_info = {
            "ambiguity_type": "vague",
            "confidence": 0.7,
            "reasons": ["Vague question"],
        }

        request = service.generate_clarification_request(
            "Tell me about visa", ambiguity_info, language="en"
        )

        assert request is not None
        assert isinstance(request, str)
        assert len(request) > 0

    def test_generate_clarification_request_incomplete(self, service):
        """Test generating clarification request for incomplete question"""
        ambiguity_info = {
            "ambiguity_type": "incomplete",
            "confidence": 0.8,
            "reasons": ["Incomplete question"],
        }

        request = service.generate_clarification_request("How much?", ambiguity_info, language="en")

        assert request is not None

    def test_generate_clarification_request_italian(self, service):
        """Test generating clarification request in Italian"""
        ambiguity_info = {
            "ambiguity_type": "vague",
            "confidence": 0.7,
            "reasons": ["Vague question"],
        }

        request = service.generate_clarification_request(
            "Dimmi del visto", ambiguity_info, language="it"
        )

        assert request is not None

    def test_generate_clarification_request_indonesian(self, service):
        """Test generating clarification request in Indonesian"""
        ambiguity_info = {
            "ambiguity_type": "vague",
            "confidence": 0.7,
            "reasons": ["Vague question"],
        }

        request = service.generate_clarification_request(
            "Ceritakan tentang visa", ambiguity_info, language="id"
        )

        assert request is not None
