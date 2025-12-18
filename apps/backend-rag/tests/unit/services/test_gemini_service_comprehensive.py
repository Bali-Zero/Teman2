"""
Comprehensive tests for services/gemini_service.py
Target: 95%+ coverage
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.gemini_service import GeminiJakselService


class TestGeminiJakselService:
    """Comprehensive test suite for GeminiJakselService"""

    @pytest.fixture
    def service(self):
        """Create GeminiJakselService instance"""
        with patch("services.gemini_service.settings") as mock_settings:
            mock_settings.google_api_key = "test_key"
            with patch("services.gemini_service.genai.configure"):
                with patch("services.gemini_service.genai.GenerativeModel"):
                    return GeminiJakselService()

    def test_init(self, service):
        """Test GeminiJakselService initialization"""
        assert service.model_name.startswith("models/")
        assert service.system_instruction is not None

    def test_init_custom_model(self):
        """Test initialization with custom model"""
        with patch("services.gemini_service.settings") as mock_settings:
            mock_settings.google_api_key = "test_key"
            with patch("services.gemini_service.genai.configure"):
                with patch("services.gemini_service.genai.GenerativeModel"):
                    service = GeminiJakselService(model_name="gemini-2.5-pro")
                    assert "gemini-2.5-pro" in service.model_name

    def test_init_no_api_key(self):
        """Test initialization without API key"""
        with patch("services.gemini_service.settings") as mock_settings:
            mock_settings.google_api_key = None
            service = GeminiJakselService()
            assert service.model is None

    def test_convert_to_openai_messages(self, service):
        """Test _convert_to_openai_messages"""
        messages = service._convert_to_openai_messages("test query", None, "test context")
        assert len(messages) > 0
        assert any(msg["role"] == "system" for msg in messages)

    def test_convert_to_openai_messages_with_history(self, service):
        """Test _convert_to_openai_messages with history"""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        messages = service._convert_to_openai_messages("test", history, "")
        assert len(messages) > 2

    @pytest.mark.asyncio
    async def test_generate_text_success(self, service):
        """Test generate_text success"""
        mock_response = MagicMock()
        mock_response.text = "Test response"
        service.model = MagicMock()
        service.model.generate_content = MagicMock(return_value=mock_response)

        result = await service.generate_text("test query")
        assert result == "Test response"

    @pytest.mark.asyncio
    async def test_generate_text_with_fallback(self, service):
        """Test generate_text with OpenRouter fallback"""
        service.model = MagicMock()
        service.model.generate_content = MagicMock(side_effect=Exception("429"))
        mock_openrouter = MagicMock()
        mock_openrouter.generate_text = AsyncMock(return_value="Fallback response")
        service._get_openrouter_client = MagicMock(return_value=mock_openrouter)

        result = await service.generate_text("test query")
        assert result == "Fallback response"

    @pytest.mark.asyncio
    async def test_stream_text(self, service):
        """Test stream_text"""
        mock_chunk = MagicMock()
        mock_chunk.text = "chunk"
        mock_response = MagicMock()
        mock_response.__aiter__ = MagicMock(return_value=iter([mock_chunk]))
        service.model = MagicMock()
        service.model.generate_content = MagicMock(return_value=mock_response)

        chunks = []
        async for chunk in service.stream_text("test query"):
            chunks.append(chunk)
        assert len(chunks) > 0
