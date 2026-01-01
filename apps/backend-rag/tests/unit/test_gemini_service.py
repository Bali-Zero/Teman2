"""
Unit tests for Gemini Service (Jaksel Persona)

UPDATED 2025-12-23:
- Updated mocks for new google-genai SDK via GenAIClient wrapper
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.llm_clients.gemini_service import GeminiJakselService, gemini_jaksel

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_genai_client():
    """Mock GenAIClient from llm.genai_client"""
    mock_client = MagicMock()
    mock_client.is_available = True

    # Mock chat session
    mock_chat = MagicMock()

    async def mock_send_message_stream(message):
        yield "Hello"
        yield " World"

    mock_chat.send_message_stream = mock_send_message_stream
    mock_chat.send_message = AsyncMock(return_value={"text": "Hello World"})

    mock_client.create_chat = MagicMock(return_value=mock_chat)

    return mock_client


@pytest.fixture
def gemini_service(mock_genai_client):
    """Create GeminiJakselService instance with mocked GenAIClient"""
    with patch("services.llm_clients.gemini_service.GenAIClient", return_value=mock_genai_client):
        with patch("services.llm_clients.gemini_service.GENAI_AVAILABLE", True):
            with patch("services.llm_clients.gemini_service.settings") as mock_settings:
                mock_settings.google_api_key = "test-api-key"
                service = GeminiJakselService(model_name="gemini-2.0-flash")
                # Manually set the client for tests
                service._genai_client = mock_genai_client
                service._available = True
                return service


# ============================================================================
# Tests for __init__
# ============================================================================


def test_init_default_model(mock_genai_client):
    """Test initialization with default model"""
    with patch("services.llm_clients.gemini_service.GenAIClient", return_value=mock_genai_client):
        with patch("services.llm_clients.gemini_service.GENAI_AVAILABLE", True):
            with patch("services.llm_clients.gemini_service.settings") as mock_settings:
                mock_settings.google_api_key = "test-api-key"
                service = GeminiJakselService()
                # Default model is now gemini-3-flash-preview (updated Dec 2025)
                assert service.model_name == "gemini-3-flash-preview"
                assert service.system_instruction is not None
                assert len(service.few_shot_history) > 0


def test_init_custom_model(mock_genai_client):
    """Test initialization with custom model"""
    with patch("services.llm_clients.gemini_service.GenAIClient", return_value=mock_genai_client):
        with patch("services.llm_clients.gemini_service.GENAI_AVAILABLE", True):
            with patch("services.llm_clients.gemini_service.settings") as mock_settings:
                mock_settings.google_api_key = "test-api-key"
                service = GeminiJakselService(model_name="gemini-3-flash-preview")
                assert service.model_name == "gemini-3-flash-preview"


def test_init_custom_model_with_prefix(mock_genai_client):
    """Test initialization with custom model that already has models/ prefix"""
    with patch("services.llm_clients.gemini_service.GenAIClient", return_value=mock_genai_client):
        with patch("services.llm_clients.gemini_service.GENAI_AVAILABLE", True):
            with patch("services.llm_clients.gemini_service.settings") as mock_settings:
                mock_settings.google_api_key = "test-api-key"
                # New SDK strips 'models/' prefix
                service = GeminiJakselService(model_name="models/gemini-3-flash-preview")
                assert service.model_name == "gemini-3-flash-preview"


def test_init_few_shot_history(mock_genai_client):
    """Test that few-shot history is populated"""
    with patch("services.llm_clients.gemini_service.GenAIClient", return_value=mock_genai_client):
        with patch("services.llm_clients.gemini_service.GENAI_AVAILABLE", True):
            with patch("services.llm_clients.gemini_service.settings") as mock_settings:
                mock_settings.google_api_key = "test-api-key"
                with patch("services.llm_clients.gemini_service.FEW_SHOT_EXAMPLES", [{"role": "user", "content": "test"}]):
                    service = GeminiJakselService()
                    assert len(service.few_shot_history) == 1
                    assert service.few_shot_history[0]["role"] == "user"


def test_init_without_api_key():
    """Test initialization without API key - service becomes unavailable"""
    with patch("services.llm_clients.gemini_service.GENAI_AVAILABLE", False):
        with patch("services.llm_clients.gemini_service.settings") as mock_settings:
            mock_settings.google_api_key = None
            service = GeminiJakselService()
            # When GENAI_AVAILABLE is False, service is not available
            assert service._available is False


# ============================================================================
# Tests for generate_response_stream
# ============================================================================


@pytest.mark.asyncio
async def test_generate_response_stream_basic(gemini_service):
    """Test basic streaming response"""
    chunks = []
    async for chunk in gemini_service.generate_response_stream("Hello"):
        chunks.append(chunk)

    assert len(chunks) > 0


@pytest.mark.asyncio
async def test_generate_response_stream_with_history(gemini_service, mock_genai_client):
    """Test streaming with conversation history"""
    history = [
        {"role": "user", "content": "Previous message"},
        {"role": "assistant", "content": "Previous response"},
    ]

    chunks = []
    async for chunk in gemini_service.generate_response_stream("Follow-up", history=history):
        chunks.append(chunk)

    # Verify create_chat was called
    mock_genai_client.create_chat.assert_called()


@pytest.mark.asyncio
async def test_generate_response_stream_with_context(gemini_service, mock_genai_client):
    """Test streaming with RAG context"""
    context = "Context: This is important information"

    chunks = []
    async for chunk in gemini_service.generate_response_stream("Query", context=context):
        chunks.append(chunk)

    # Verify create_chat was called
    mock_genai_client.create_chat.assert_called()


@pytest.mark.asyncio
async def test_generate_response_stream_none_history(gemini_service):
    """Test streaming with None history (should use empty list)"""
    chunks = []
    async for chunk in gemini_service.generate_response_stream("Test", history=None):
        chunks.append(chunk)

    assert len(chunks) >= 0  # Should not raise error


# ============================================================================
# Tests for generate_response
# ============================================================================


@pytest.mark.asyncio
async def test_generate_response_basic(gemini_service):
    """Test non-streaming response generation"""
    result = await gemini_service.generate_response("Hello")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_generate_response_with_history(gemini_service):
    """Test response generation with history"""
    history = [{"role": "user", "content": "Previous"}]
    result = await gemini_service.generate_response("Follow-up", history=history)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_generate_response_with_context(gemini_service):
    """Test response generation with context"""
    result = await gemini_service.generate_response("Query", context="Context info")
    assert isinstance(result, str)


# ============================================================================
# Tests for OpenRouter fallback
# ============================================================================


@pytest.mark.asyncio
async def test_fallback_to_openrouter_on_quota_exceeded(mock_genai_client):
    """Test fallback to OpenRouter when Gemini quota exceeded"""
    from google.api_core.exceptions import ResourceExhausted

    # Make create_chat return a chat that raises ResourceExhausted when streaming
    mock_chat = MagicMock()

    # Create async generator that raises ResourceExhausted
    async def raise_quota_error_gen(msg):
        raise ResourceExhausted("Quota exceeded")
        yield  # Make it a generator (never reached)

    mock_chat.send_message_stream = raise_quota_error_gen
    mock_genai_client.create_chat.return_value = mock_chat

    with patch("services.llm_clients.gemini_service.GenAIClient", return_value=mock_genai_client):
        with patch("services.llm_clients.gemini_service.GENAI_AVAILABLE", True):
            with patch("services.llm_clients.gemini_service.settings") as mock_settings:
                mock_settings.google_api_key = "test-api-key"
                service = GeminiJakselService()
                service._genai_client = mock_genai_client
                service._available = True

                # Mock OpenRouter fallback as async generator
                async def mock_openrouter_stream(message, history, context):
                    yield "OpenRouter response"

                with patch.object(
                    service, "_fallback_to_openrouter_stream", return_value=mock_openrouter_stream(None, None, None)
                ):
                    chunks = []
                    async for chunk in service.generate_response_stream("Test"):
                        chunks.append(chunk)

                    assert "OpenRouter response" in chunks


# ============================================================================
# Tests for singleton
# ============================================================================


def test_gemini_jaksel_singleton():
    """Test that gemini_jaksel is a singleton instance"""
    assert gemini_jaksel is not None
    assert isinstance(gemini_jaksel, GeminiJakselService)


# ============================================================================
# Tests for GeminiService wrapper (backward compatibility)
# ============================================================================


def test_gemini_service_wrapper():
    """Test GeminiService wrapper for backward compatibility"""
    from services.llm_clients.gemini_service import GeminiService

    with patch("services.llm_clients.gemini_service.GeminiJakselService") as mock_jaksel:
        mock_jaksel.return_value = MagicMock()
        service = GeminiService()
        assert service._service is not None


@pytest.mark.asyncio
async def test_gemini_service_wrapper_generate_response():
    """Test GeminiService wrapper generate_response method"""
    from services.llm_clients.gemini_service import GeminiService

    mock_jaksel = MagicMock()
    mock_jaksel.generate_response = AsyncMock(return_value="Test response")

    with patch("services.llm_clients.gemini_service.GeminiJakselService", return_value=mock_jaksel):
        service = GeminiService()
        result = await service.generate_response("Test prompt")
        assert result == "Test response"
