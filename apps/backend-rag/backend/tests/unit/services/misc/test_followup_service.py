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

    def test_detect_topic_immigration(self, followup_service):
        """Test detecting immigration topic"""
        assert followup_service.detect_topic_from_query("I need a KITAS") == "immigration"
        assert followup_service.detect_topic_from_query("visa application") == "immigration"
        assert followup_service.detect_topic_from_query("permit") == "immigration"

    def test_detect_topic_tax(self, followup_service):
        """Test detecting tax topic"""
        assert followup_service.detect_topic_from_query("tax information") == "tax"
        assert followup_service.detect_topic_from_query("pajak") == "tax"
        assert followup_service.detect_topic_from_query("NPWP") == "tax"

    def test_detect_topic_technical(self, followup_service):
        """Test detecting technical topic"""
        assert followup_service.detect_topic_from_query("code error") == "technical"
        assert followup_service.detect_topic_from_query("API programming") == "technical"
        assert followup_service.detect_topic_from_query("bug fix") == "technical"

    def test_detect_topic_casual(self, followup_service):
        """Test detecting casual topic"""
        assert followup_service.detect_topic_from_query("hello") == "casual"
        assert followup_service.detect_topic_from_query("ciao") == "casual"
        assert followup_service.detect_topic_from_query("thanks") == "casual"

    def test_detect_topic_business_default(self, followup_service):
        """Test defaulting to business topic"""
        assert followup_service.detect_topic_from_query("random query") == "business"

    def test_detect_language_italian(self, followup_service):
        """Test detecting Italian language"""
        assert followup_service.detect_language_from_query("Ciao, come stai?") == "it"
        assert followup_service.detect_language_from_query("grazie") == "it"
        assert followup_service.detect_language_from_query("cosa") == "it"

    def test_detect_language_indonesian(self, followup_service):
        """Test detecting Indonesian language"""
        assert followup_service.detect_language_from_query("Halo, apa kabar?") == "id"
        assert followup_service.detect_language_from_query("terima kasih") == "id"
        assert followup_service.detect_language_from_query("saya mau") == "id"

    def test_detect_language_english_default(self, followup_service):
        """Test defaulting to English"""
        assert followup_service.detect_language_from_query("random text") == "en"

    @pytest.mark.asyncio
    async def test_get_followups_with_ai(self, followup_service):
        """Test getting followups with AI"""
        followup_service.zantara_client.chat_async = AsyncMock(return_value={
            "text": "1. First question?\n2. Second question?\n3. Third question?"
        })

        result = await followup_service.get_followups(
            query="Test query",
            response="Test response",
            use_ai=True
        )
        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_followups_without_ai(self, followup_service_no_ai):
        """Test getting followups without AI"""
        result = await followup_service_no_ai.get_followups(
            query="Test query",
            response="Test response",
            use_ai=False
        )
        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_generate_dynamic_followups_success(self, followup_service):
        """Test successful dynamic followup generation"""
        followup_service.zantara_client.chat_async = AsyncMock(return_value={
            "text": "1. First?\n2. Second?\n3. Third?"
        })

        result = await followup_service.generate_dynamic_followups(
            query="Test query",
            response="Test response",
            language="en"
        )
        assert isinstance(result, list)
        assert len(result) <= 4

    @pytest.mark.asyncio
    async def test_generate_dynamic_followups_no_ai(self, followup_service_no_ai):
        """Test dynamic followups fallback when AI not available"""
        result = await followup_service_no_ai.generate_dynamic_followups(
            query="Test query",
            response="Test response",
            language="en"
        )
        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_generate_dynamic_followups_parse_error(self, followup_service):
        """Test handling parse error in dynamic followups"""
        followup_service.zantara_client.chat_async = AsyncMock(return_value={
            "text": "Invalid format without numbers"
        })

        result = await followup_service.generate_dynamic_followups(
            query="Test query",
            response="Test response",
            language="en"
        )
        # Should fallback to topic-based
        assert isinstance(result, list)

    def test_parse_followup_list(self, followup_service):
        """Test parsing followup list from text"""
        text = "1. First question?\n2. Second question?\n3. Third question?"
        result = followup_service._parse_followup_list(text)
        assert len(result) == 3
        assert "First question?" in result[0]
        assert "Second question?" in result[1]

    def test_parse_followup_list_with_quotes(self, followup_service):
        """Test parsing followup list with quotes"""
        text = '1. "First question?"\n2. "Second question?"'
        result = followup_service._parse_followup_list(text)
        assert len(result) == 2
        assert result[0] == "First question?"
        assert result[1] == "Second question?"

    def test_parse_followup_list_empty(self, followup_service):
        """Test parsing empty followup list"""
        result = followup_service._parse_followup_list("")
        assert len(result) == 0

    def test_build_followup_generation_prompt(self, followup_service):
        """Test building followup generation prompt"""
        prompt = followup_service._build_followup_generation_prompt(
            query="Test query",
            response="Test response",
            conversation_context="Previous context",
            language="en"
        )
        assert "Test query" in prompt
        assert "Test response" in prompt
        assert "Previous context" in prompt
        assert "SAME LANGUAGE" in prompt

    @pytest.mark.asyncio
    async def test_health_check(self, followup_service):
        """Test health check"""
        result = await followup_service.health_check()
        assert isinstance(result, dict)
        assert "status" in result
        assert "ai_available" in result

    @pytest.mark.asyncio
    async def test_health_check_no_ai(self, followup_service_no_ai):
        """Test health check without AI"""
        result = await followup_service_no_ai.health_check()
        assert isinstance(result, dict)
        assert result["ai_available"] is False
