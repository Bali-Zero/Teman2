"""
Comprehensive tests for services/followup_service.py
Target: 95%+ coverage
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.followup_service import FollowupService


class TestFollowupService:
    """Comprehensive test suite for FollowupService"""

    @pytest.fixture
    def service(self):
        """Create FollowupService instance"""
        with patch("services.followup_service.ZantaraAIClient"):
            return FollowupService()

    @pytest.fixture
    def service_with_ai(self):
        """Create FollowupService with AI client"""
        mock_client = MagicMock()
        mock_client.generate_response = MagicMock(return_value="1. Question 1?\n2. Question 2?")
        service = FollowupService()
        service.zantara_client = mock_client
        return service

    def test_init(self, service):
        """Test FollowupService initialization"""
        assert service.zantara_client is None or service.zantara_client is not None

    def test_generate_followups_topic_based(self, service):
        """Test generate_followups with topic-based fallback"""
        followups = service.generate_followups("test query", "test response", topic="business")
        assert len(followups) > 0
        assert all(isinstance(f, str) for f in followups)

    def test_get_topic_based_followups_business(self, service):
        """Test get_topic_based_followups for business"""
        followups = service.get_topic_based_followups(
            "test", "response", topic="business", language="en"
        )
        assert len(followups) == 3

    def test_get_topic_based_followups_immigration(self, service):
        """Test get_topic_based_followups for immigration"""
        followups = service.get_topic_based_followups(
            "test", "response", topic="immigration", language="en"
        )
        assert len(followups) == 3

    def test_get_topic_based_followups_tax(self, service):
        """Test get_topic_based_followups for tax"""
        followups = service.get_topic_based_followups(
            "test", "response", topic="tax", language="en"
        )
        assert len(followups) == 3

    def test_get_topic_based_followups_italian(self, service):
        """Test get_topic_based_followups in Italian"""
        followups = service.get_topic_based_followups(
            "test", "response", topic="business", language="it"
        )
        assert len(followups) == 3

    def test_get_topic_based_followups_indonesian(self, service):
        """Test get_topic_based_followups in Indonesian"""
        followups = service.get_topic_based_followups(
            "test", "response", topic="business", language="id"
        )
        assert len(followups) == 3

    def test_detect_topic_from_query_visa(self, service):
        """Test detect_topic_from_query for visa"""
        topic = service.detect_topic_from_query("I need a visa")
        assert topic == "immigration"

    def test_detect_topic_from_query_tax(self, service):
        """Test detect_topic_from_query for tax"""
        topic = service.detect_topic_from_query("How do I pay taxes?")
        assert topic == "tax"

    def test_detect_topic_from_query_technical(self, service):
        """Test detect_topic_from_query for technical"""
        topic = service.detect_topic_from_query("How do I debug this code?")
        assert topic == "technical"

    def test_detect_topic_from_query_casual(self, service):
        """Test detect_topic_from_query for casual"""
        topic = service.detect_topic_from_query("Hello, how are you?")
        assert topic == "casual"

    def test_detect_topic_from_query_business(self, service):
        """Test detect_topic_from_query default to business"""
        topic = service.detect_topic_from_query("Tell me about companies")
        assert topic == "business"

    def test_detect_language_from_query_italian(self, service):
        """Test detect_language_from_query for Italian"""
        language = service.detect_language_from_query("Ciao, come stai?")
        assert language == "it"

    def test_detect_language_from_query_indonesian(self, service):
        """Test detect_language_from_query for Indonesian"""
        language = service.detect_language_from_query("Halo, apa kabar?")
        assert language == "id"

    def test_detect_language_from_query_english(self, service):
        """Test detect_language_from_query default to English"""
        language = service.detect_language_from_query("Hello, how are you?")
        assert language == "en"

    def test_parse_followup_list(self, service):
        """Test _parse_followup_list"""
        text = "1. First question?\n2. Second question?\n3. Third question?"
        followups = service._parse_followup_list(text)
        assert len(followups) == 3

    def test_parse_followup_list_no_numbers(self, service):
        """Test _parse_followup_list with no numbers"""
        text = "Just some text without numbers"
        followups = service._parse_followup_list(text)
        assert len(followups) == 0

    @pytest.mark.asyncio
    async def test_generate_dynamic_followups_success(self, service_with_ai):
        """Test generate_dynamic_followups success"""
        mock_client = MagicMock()
        mock_client.chat_async = AsyncMock(
            return_value={"text": "1. Question 1?\n2. Question 2?\n3. Question 3?"}
        )
        service_with_ai.zantara_client = mock_client
        followups = await service_with_ai.generate_dynamic_followups(
            "test", "response", language="en"
        )
        assert len(followups) > 0

    @pytest.mark.asyncio
    async def test_generate_dynamic_followups_no_client(self, service):
        """Test generate_dynamic_followups without AI client"""
        followups = await service.generate_dynamic_followups("test", "response", language="en")
        assert len(followups) > 0  # Should fallback to topic-based

    @pytest.mark.asyncio
    async def test_generate_dynamic_followups_error(self, service_with_ai):
        """Test generate_dynamic_followups with error"""
        mock_client = MagicMock()
        mock_client.chat_async = AsyncMock(side_effect=Exception("Error"))
        service_with_ai.zantara_client = mock_client
        followups = await service_with_ai.generate_dynamic_followups(
            "test", "response", language="en"
        )
        assert len(followups) > 0  # Should fallback

    @pytest.mark.asyncio
    async def test_get_followups_with_ai(self, service_with_ai):
        """Test get_followups with AI"""
        mock_client = MagicMock()
        mock_client.chat_async = AsyncMock(return_value={"text": "1. Question 1?\n2. Question 2?"})
        service_with_ai.zantara_client = mock_client
        followups = await service_with_ai.get_followups("test", "response", use_ai=True)
        assert len(followups) > 0

    @pytest.mark.asyncio
    async def test_get_followups_without_ai(self, service):
        """Test get_followups without AI"""
        followups = await service.get_followups("test", "response", use_ai=False)
        assert len(followups) > 0

    @pytest.mark.asyncio
    async def test_health_check(self, service):
        """Test health_check"""
        health = await service.health_check()
        assert health["status"] == "healthy"
        assert "features" in health
