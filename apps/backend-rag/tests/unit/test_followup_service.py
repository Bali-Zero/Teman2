"""
Unit tests for FollowupService
Tests follow-up question generation
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.followup_service import FollowupService


@pytest.mark.unit
class TestFollowupServiceInit:
    """Test FollowupService initialization"""

    def test_init_with_ai_client(self):
        """Test initialization with AI client"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            service = FollowupService()

            assert service.zantara_client == mock_client

    def test_init_without_ai_client(self):
        """Test initialization when AI client fails"""
        with patch("services.followup_service.ZantaraAIClient", side_effect=Exception("AI error")):
            service = FollowupService()

            assert service.zantara_client is None


@pytest.mark.unit
class TestFollowupServiceGeneration:
    """Test follow-up generation"""

    def test_generate_followups_with_ai(self):
        """Test generating followups with AI"""
        service = FollowupService()
        mock_client = MagicMock()
        mock_client.generate_response = MagicMock(return_value="Question 1\nQuestion 2\nQuestion 3")
        service.zantara_client = mock_client

        result = service.generate_followups(
            query="What is KITAS?",
            response="KITAS is a work permit...",
            topic="immigration",
            language="en",
        )

        assert len(result) > 0
        assert isinstance(result, list)

    def test_generate_followups_fallback(self):
        """Test fallback to topic-based followups"""
        service = FollowupService()
        service.zantara_client = None

        result = service.generate_followups(
            query="What is KITAS?", response="KITAS is...", topic="immigration", language="en"
        )

        assert len(result) >= 3
        assert all(isinstance(q, str) for q in result)

    def test_get_topic_based_followups_business_en(self):
        """Test business topic followups in English"""
        service = FollowupService()

        result = service.get_topic_based_followups(
            _query="How to set up a company?",
            _response="Setting up a company requires...",
            topic="business",
            language="en",
        )

        assert len(result) >= 3
        # Check that at least one question contains cost-related keywords
        assert any("cost" in q.lower() or "costs" in q.lower() for q in result)

    def test_get_topic_based_followups_immigration_it(self):
        """Test immigration topic followups in Italian"""
        service = FollowupService()

        result = service.get_topic_based_followups(
            _query="Come ottenere un visto?",
            _response="Per ottenere un visto...",
            topic="immigration",
            language="it",
        )

        assert len(result) >= 3
        assert any("visto" in q.lower() for q in result)

    def test_get_topic_based_followups_tax_id(self):
        """Test tax topic followups in Indonesian"""
        service = FollowupService()

        result = service.get_topic_based_followups(
            _query="Bagaimana cara daftar pajak?",
            _response="Untuk mendaftar pajak...",
            topic="tax",
            language="id",
        )

        assert len(result) >= 3

    def test_get_topic_based_followups_casual(self):
        """Test casual topic followups"""
        service = FollowupService()

        result = service.get_topic_based_followups(
            _query="Hello", _response="Hi there!", topic="casual", language="en"
        )

        assert len(result) >= 3

    def test_get_topic_based_followups_technical(self):
        """Test technical topic followups"""
        service = FollowupService()

        result = service.get_topic_based_followups(
            _query="What is the API endpoint?",
            _response="The API endpoint is...",
            topic="technical",
            language="en",
        )

        assert len(result) >= 3

    def test_detect_language_from_query(self):
        """Test language detection from query"""
        service = FollowupService()

        assert service.detect_language_from_query("Ciao come stai?") == "it"
        assert service.detect_language_from_query("Hello how are you?") == "en"
        assert service.detect_language_from_query("Apa kabar?") == "id"

    def test_detect_topic_from_query(self):
        """Test topic detection from query"""
        service = FollowupService()

        assert service.detect_topic_from_query("How to get a visa?") == "immigration"
        assert service.detect_topic_from_query("How to register for tax?") == "tax"
        assert service.detect_topic_from_query("How to set up a company?") == "business"
        assert service.detect_topic_from_query("Hello") == "casual"
