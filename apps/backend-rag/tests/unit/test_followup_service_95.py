"""
Unit Tests for services/followup_service.py - 95% Coverage Target
Tests the FollowupService class
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test FollowupService initialization
# ============================================================================


class TestFollowupServiceInit:
    """Test suite for FollowupService initialization"""

    def test_init_with_zantara_client(self):
        """Test initialization with ZANTARA AI client"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            from services.followup_service import FollowupService

            service = FollowupService()

            assert service.zantara_client == mock_client

    def test_init_without_zantara_client(self):
        """Test initialization when ZANTARA AI fails"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("Client init failed")

            from services.followup_service import FollowupService

            service = FollowupService()

            assert service.zantara_client is None


# ============================================================================
# Test generate_followups (sync)
# ============================================================================


class TestGenerateFollowups:
    """Test suite for generate_followups method"""

    def test_generate_followups_ai_success_string_result(self):
        """Test generate_followups with AI returning string"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate_response.return_value = "Question 1?\nQuestion 2?\nQuestion 3?"
            mock_client_class.return_value = mock_client

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.generate_followups(
                "What is KITAS?", "KITAS is a visa...", "immigration"
            )

            assert len(result) >= 1
            assert "Question 1?" in result

    def test_generate_followups_ai_returns_coroutine(self):
        """Test generate_followups handles coroutine from AI"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client = MagicMock()

            async def mock_async_response(*args, **kwargs):
                return "1. First?\n2. Second?\n3. Third?"

            mock_client.generate_response.return_value = mock_async_response()
            mock_client_class.return_value = mock_client

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.generate_followups("Test query", "Test response", "business")

            assert len(result) >= 1

    def test_generate_followups_fallback_no_client(self):
        """Test generate_followups falls back when no client"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("Client not available")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.generate_followups("What is KITAS?", "KITAS is...", "immigration")

            assert len(result) >= 1
            assert isinstance(result[0], str)

    def test_generate_followups_fallback_ai_exception(self):
        """Test generate_followups falls back on AI exception"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.generate_response.side_effect = Exception("AI error")
            mock_client_class.return_value = mock_client

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.generate_followups("Test", "Response", "business")

            assert len(result) >= 1

    def test_generate_followups_with_language(self):
        """Test generate_followups with language parameter"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.generate_followups("Ciao", "Ciao!", "casual", language="it")

            assert len(result) >= 1


# ============================================================================
# Test get_topic_based_followups
# ============================================================================


class TestGetTopicBasedFollowups:
    """Test suite for get_topic_based_followups method"""

    def test_business_english(self):
        """Test business followups in English"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.get_topic_based_followups("Query", "Response", "business", "en")

            assert len(result) == 3
            assert all(isinstance(q, str) for q in result)

    def test_business_italian(self):
        """Test business followups in Italian"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.get_topic_based_followups("Query", "Response", "business", "it")

            assert len(result) == 3

    def test_immigration_english(self):
        """Test immigration followups in English"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.get_topic_based_followups("Query", "Response", "immigration", "en")

            assert len(result) == 3

    def test_tax_indonesian(self):
        """Test tax followups in Indonesian"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.get_topic_based_followups("Query", "Response", "tax", "id")

            assert len(result) == 3

    def test_casual_topic(self):
        """Test casual topic followups"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.get_topic_based_followups("Hi", "Hello!", "casual", "en")

            assert len(result) == 3

    def test_technical_topic(self):
        """Test technical topic followups"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.get_topic_based_followups("Code?", "Here...", "technical", "en")

            assert len(result) == 3

    def test_unknown_topic_fallback(self):
        """Test unknown topic falls back to business"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.get_topic_based_followups("Query", "Response", "unknown_topic", "en")

            assert len(result) == 3

    def test_unknown_language_fallback(self):
        """Test unknown language falls back to English"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.get_topic_based_followups("Query", "Response", "business", "fr")

            assert len(result) == 3


# ============================================================================
# Test generate_dynamic_followups
# ============================================================================


class TestGenerateDynamicFollowups:
    """Test suite for generate_dynamic_followups method"""

    @pytest.mark.asyncio
    async def test_dynamic_no_client_fallback(self):
        """Test dynamic generation falls back when no client"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = await service.generate_dynamic_followups("Query", "Response", None, "en")

            assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_dynamic_ai_success(self):
        """Test dynamic generation with AI success"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat_async = AsyncMock(
                return_value={"text": "1. First question?\n2. Second question?\n3. Third question?"}
            )
            mock_client_class.return_value = mock_client

            from services.followup_service import FollowupService

            service = FollowupService()
            result = await service.generate_dynamic_followups(
                "What is KITAS?", "KITAS is...", None, "en"
            )

            assert len(result) >= 1
            assert "First question?" in result

    @pytest.mark.asyncio
    async def test_dynamic_ai_parse_failure_fallback(self):
        """Test dynamic generation falls back on parse failure"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat_async = AsyncMock(return_value={"text": "No numbered list here"})
            mock_client_class.return_value = mock_client

            from services.followup_service import FollowupService

            service = FollowupService()
            result = await service.generate_dynamic_followups("Query", "Response", None, "en")

            assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_dynamic_ai_exception_fallback(self):
        """Test dynamic generation falls back on exception"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat_async = AsyncMock(side_effect=Exception("AI failed"))
            mock_client_class.return_value = mock_client

            from services.followup_service import FollowupService

            service = FollowupService()
            result = await service.generate_dynamic_followups("Query", "Response", None, "en")

            assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_dynamic_with_context(self):
        """Test dynamic generation with conversation context"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat_async = AsyncMock(
                return_value={"text": "1. Context question?\n2. Another?\n3. More?"}
            )
            mock_client_class.return_value = mock_client

            from services.followup_service import FollowupService

            service = FollowupService()
            result = await service.generate_dynamic_followups(
                "Query", "Response", "Previous conversation here", "en"
            )

            assert len(result) >= 1


# ============================================================================
# Test _build_followup_generation_prompt
# ============================================================================


class TestBuildFollowupGenerationPrompt:
    """Test suite for _build_followup_generation_prompt method"""

    def test_build_prompt_english(self):
        """Test building prompt in English"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            prompt = service._build_followup_generation_prompt(
                "What is KITAS?", "KITAS is a permit", None, "en"
            )

            assert "English" in prompt
            assert "KITAS" in prompt

    def test_build_prompt_italian(self):
        """Test building prompt in Italian"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            prompt = service._build_followup_generation_prompt("Ciao", "Ciao!", None, "it")

            assert "italiano" in prompt

    def test_build_prompt_indonesian(self):
        """Test building prompt in Indonesian"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            prompt = service._build_followup_generation_prompt("Halo", "Halo!", None, "id")

            assert "Indonesia" in prompt

    def test_build_prompt_with_context(self):
        """Test building prompt with conversation context"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            prompt = service._build_followup_generation_prompt(
                "Query", "Response", "Previous context", "en"
            )

            assert "Previous context" in prompt


# ============================================================================
# Test _parse_followup_list
# ============================================================================


class TestParseFollowupList:
    """Test suite for _parse_followup_list method"""

    def test_parse_numbered_list(self):
        """Test parsing numbered list with dots"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            text = "1. First question?\n2. Second question?\n3. Third question?"

            result = service._parse_followup_list(text)

            assert len(result) == 3
            assert "First question?" in result
            assert "Second question?" in result
            assert "Third question?" in result

    def test_parse_numbered_list_parentheses(self):
        """Test parsing numbered list with parentheses"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            text = "1) Question one?\n2) Question two?"

            result = service._parse_followup_list(text)

            assert len(result) == 2

    def test_parse_removes_quotes(self):
        """Test parsing removes surrounding quotes"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            text = '1. "Quoted question?"'

            result = service._parse_followup_list(text)

            assert len(result) == 1
            assert result[0] == "Quoted question?"

    def test_parse_empty_text(self):
        """Test parsing empty text"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()

            result = service._parse_followup_list("")

            assert result == []

    def test_parse_no_numbered_list(self):
        """Test parsing text without numbered list"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            text = "Just some text without numbers"

            result = service._parse_followup_list(text)

            assert result == []


# ============================================================================
# Test detect_topic_from_query
# ============================================================================


class TestDetectTopicFromQuery:
    """Test suite for detect_topic_from_query method"""

    def test_detect_immigration_visa(self):
        """Test detecting immigration topic with visa keyword"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.detect_topic_from_query("What visa do I need?")

            assert result == "immigration"

    def test_detect_immigration_kitas(self):
        """Test detecting immigration topic with KITAS keyword"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.detect_topic_from_query("How do I get KITAS?")

            assert result == "immigration"

    def test_detect_tax(self):
        """Test detecting tax topic"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.detect_topic_from_query("What is the tax rate?")

            assert result == "tax"

    def test_detect_tax_pajak(self):
        """Test detecting tax topic with Indonesian keyword"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.detect_topic_from_query("Berapa pajak?")

            assert result == "tax"

    def test_detect_technical(self):
        """Test detecting technical topic"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.detect_topic_from_query("How do I fix this code error?")

            assert result == "technical"

    def test_detect_casual_hello(self):
        """Test detecting casual topic with hello"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.detect_topic_from_query("Hello, how are you?")

            assert result == "casual"

    def test_detect_casual_ciao(self):
        """Test detecting casual topic with ciao"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.detect_topic_from_query("Ciao!")

            assert result == "casual"

    def test_detect_default_business(self):
        """Test default to business topic"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.detect_topic_from_query("How do I start a company?")

            assert result == "business"


# ============================================================================
# Test detect_language_from_query
# ============================================================================


class TestDetectLanguageFromQuery:
    """Test suite for detect_language_from_query method"""

    def test_detect_italian(self):
        """Test detecting Italian language"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.detect_language_from_query("Ciao, come stai?")

            assert result == "it"

    def test_detect_indonesian(self):
        """Test detecting Indonesian language"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.detect_language_from_query("Halo, apa kabar?")

            assert result == "id"

    def test_detect_default_english(self):
        """Test default to English language"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = service.detect_language_from_query("How are you?")

            assert result == "en"


# ============================================================================
# Test get_followups
# ============================================================================


class TestGetFollowups:
    """Test suite for get_followups method"""

    @pytest.mark.asyncio
    async def test_get_followups_with_ai(self):
        """Test get_followups using AI"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat_async = AsyncMock(
                return_value={"text": "1. Question one?\n2. Question two?\n3. Question three?"}
            )
            mock_client_class.return_value = mock_client

            from services.followup_service import FollowupService

            service = FollowupService()
            result = await service.get_followups("What is KITAS?", "KITAS is a permit", use_ai=True)

            assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_get_followups_without_ai(self):
        """Test get_followups without AI"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = await service.get_followups("What is KITAS?", "KITAS...", use_ai=False)

            assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_get_followups_with_context(self):
        """Test get_followups with conversation context"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat_async = AsyncMock(return_value={"text": "1. Q1?\n2. Q2?\n3. Q3?"})
            mock_client_class.return_value = mock_client

            from services.followup_service import FollowupService

            service = FollowupService()
            result = await service.get_followups(
                "Query", "Response", use_ai=True, conversation_context="Previous context"
            )

            assert len(result) >= 1


# ============================================================================
# Test health_check
# ============================================================================


class TestHealthCheck:
    """Test suite for health_check method"""

    @pytest.mark.asyncio
    async def test_health_check_with_client(self):
        """Test health check with AI client available"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            from services.followup_service import FollowupService

            service = FollowupService()
            result = await service.health_check()

            assert result["status"] == "healthy"
            assert result["ai_available"] is True
            assert result["features"]["dynamic_generation"] is True

    @pytest.mark.asyncio
    async def test_health_check_without_client(self):
        """Test health check without AI client"""
        with patch("services.followup_service.ZantaraAIClient") as mock_client_class:
            mock_client_class.side_effect = Exception("No client")

            from services.followup_service import FollowupService

            service = FollowupService()
            result = await service.health_check()

            assert result["status"] == "healthy"
            assert result["ai_available"] is False
            assert result["features"]["dynamic_generation"] is False
            assert result["features"]["topic_based_fallback"] is True
