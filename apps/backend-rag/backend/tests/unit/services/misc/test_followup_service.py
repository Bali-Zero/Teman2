"""
Unit tests for FollowupService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.misc.followup_service import FollowupService


@pytest.fixture
def followup_service():
    """Create FollowupService instance"""
    with patch("services.misc.followup_service.ZantaraAIClient") as mock_client:
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance
        return FollowupService()


@pytest.fixture
def followup_service_no_ai():
    """Create FollowupService instance without AI"""
    with patch("services.misc.followup_service.ZantaraAIClient", side_effect=Exception("Not available")):
        return FollowupService()


class TestFollowupService:
    """Tests for FollowupService"""

    def test_init(self):
        """Test initialization"""
        with patch("services.misc.followup_service.ZantaraAIClient") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance
            service = FollowupService()
            assert service.zantara_client is not None

    def test_init_no_ai(self):
        """Test initialization without AI"""
        with patch("services.misc.followup_service.ZantaraAIClient", side_effect=Exception("Not available")):
            service = FollowupService()
            assert service.zantara_client is None

    def test_generate_followups_with_ai(self, followup_service):
        """Test generating followups with AI"""
        followup_service.zantara_client.generate_response = MagicMock(
            return_value="Question 1\nQuestion 2\nQuestion 3"
        )
        
        result = followup_service.generate_followups(
            query="Test query",
            response="Test response",
            topic="business"
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_generate_followups_with_ai_coroutine(self, followup_service):
        """Test generating followups with AI coroutine"""
        async def mock_coroutine():
            return "Question 1\nQuestion 2\nQuestion 3"
        
        followup_service.zantara_client.generate_response = mock_coroutine()
        
        result = followup_service.generate_followups(
            query="Test query",
            response="Test response",
            topic="business"
        )
        assert isinstance(result, list)

    def test_generate_followups_fallback(self, followup_service_no_ai):
        """Test generating followups with fallback"""
        result = followup_service_no_ai.generate_followups(
            query="Test query",
            response="Test response",
            topic="business",
            language="en"
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_generate_followups_ai_error(self, followup_service):
        """Test generating followups with AI error"""
        followup_service.zantara_client.generate_response = MagicMock(side_effect=Exception("AI error"))
        
        result = followup_service.generate_followups(
            query="Test query",
            response="Test response",
            topic="business"
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_topic_based_followups_business_en(self, followup_service):
        """Test getting topic-based followups for business in English"""
        result = followup_service.get_topic_based_followups(
            _query="Test query",
            _response="Test response",
            topic="business",
            language="en"
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_topic_based_followups_business_it(self, followup_service):
        """Test getting topic-based followups for business in Italian"""
        result = followup_service.get_topic_based_followups(
            _query="Test query",
            _response="Test response",
            topic="business",
            language="it"
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_topic_based_followups_immigration(self, followup_service):
        """Test getting topic-based followups for immigration"""
        result = followup_service.get_topic_based_followups(
            _query="Test query",
            _response="Test response",
            topic="immigration",
            language="en"
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_topic_based_followups_tax(self, followup_service):
        """Test getting topic-based followups for tax"""
        result = followup_service.get_topic_based_followups(
            _query="Test query",
            _response="Test response",
            topic="tax",
            language="en"
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_topic_based_followups_casual(self, followup_service):
        """Test getting topic-based followups for casual"""
        result = followup_service.get_topic_based_followups(
            _query="Test query",
            _response="Test response",
            topic="casual",
            language="en"
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_get_topic_based_followups_technical(self, followup_service):
        """Test getting topic-based followups for technical"""
        result = followup_service.get_topic_based_followups(
            _query="Test query",
            _response="Test response",
            topic="technical",
            language="en"
        )
        assert isinstance(result, list)
        assert len(result) > 0

    def test_detect_language_from_query(self, followup_service):
        """Test detecting language from query"""
        result = followup_service.detect_language_from_query("Ciao, come stai?")
        assert result in ["it", "en", "id", "uk", "ru", "auto"]

    def test_detect_topic_from_query(self, followup_service):
        """Test detecting topic from query"""
        result = followup_service.detect_topic_from_query("How do I get a visa?")
        assert result in ["business", "immigration", "tax", "casual", "technical"]
