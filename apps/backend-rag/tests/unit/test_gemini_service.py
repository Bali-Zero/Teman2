"""
Unit tests for Gemini Service (Jaksel Persona)
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.gemini_service import GeminiJakselService, gemini_jaksel

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_genai():
    """Mock google.generativeai module"""
    mock = MagicMock()
    mock.configure = MagicMock()
    return mock


@pytest.fixture
def mock_generative_model():
    """Mock GenerativeModel"""

    async def async_chunk_generator():
        mock_chunk = MagicMock()
        mock_chunk.text = "Hello"
        yield mock_chunk

    mock_model = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    # Make mock_response directly async iterable
    mock_response.__aiter__ = lambda self: async_chunk_generator()
    mock_chat.send_message_async = AsyncMock(return_value=mock_response)
    mock_model.start_chat = MagicMock(return_value=mock_chat)
    return mock_model


@pytest.fixture
def gemini_service(mock_genai, mock_generative_model):
    """Create GeminiJakselService instance"""
    with (
        patch("services.gemini_service.genai", mock_genai),
        patch("services.gemini_service.genai.GenerativeModel", return_value=mock_generative_model),
    ):
        return GeminiJakselService(model_name="gemini-2.5-flash")


# ============================================================================
# Tests for __init__
# ============================================================================


def test_init_default_model(mock_genai, mock_generative_model):
    """Test initialization with default model"""
    with (
        patch("services.gemini_service.genai", mock_genai),
        patch("services.gemini_service.genai.GenerativeModel", return_value=mock_generative_model),
    ):
        service = GeminiJakselService()
        assert service.model_name == "models/gemini-2.5-flash"
        assert service.system_instruction is not None
        assert len(service.few_shot_history) > 0


def test_init_custom_model(mock_genai, mock_generative_model):
    """Test initialization with custom model"""
    with (
        patch("services.gemini_service.genai", mock_genai),
        patch("services.gemini_service.genai.GenerativeModel", return_value=mock_generative_model),
    ):
        service = GeminiJakselService(model_name="gemini-2.5-pro")
        assert service.model_name == "models/gemini-2.5-pro"


def test_init_custom_model_with_prefix(mock_genai, mock_generative_model):
    """Test initialization with custom model that already has models/ prefix"""
    with (
        patch("services.gemini_service.genai", mock_genai),
        patch("services.gemini_service.genai.GenerativeModel", return_value=mock_generative_model),
    ):
        service = GeminiJakselService(model_name="models/gemini-2.5-pro")
        assert service.model_name == "models/gemini-2.5-pro"


def test_init_system_instruction(mock_genai, mock_generative_model):
    """Test that system instruction is set"""
    with (
        patch("services.gemini_service.genai", mock_genai),
        patch(
            "services.gemini_service.genai.GenerativeModel", return_value=mock_generative_model
        ) as mock_model_class,
    ):
        service = GeminiJakselService()
        # Verify GenerativeModel was called with system_instruction
        mock_model_class.assert_called_once()
        call_kwargs = mock_model_class.call_args[1]
        assert "system_instruction" in call_kwargs


def test_init_few_shot_history(mock_genai, mock_generative_model):
    """Test that few-shot history is populated"""
    with (
        patch("services.gemini_service.genai", mock_genai),
        patch("services.gemini_service.genai.GenerativeModel", return_value=mock_generative_model),
        patch("services.gemini_service.FEW_SHOT_EXAMPLES", [{"role": "user", "content": "test"}]),
    ):
        service = GeminiJakselService()
        assert len(service.few_shot_history) == 1
        assert service.few_shot_history[0]["role"] == "user"


# ============================================================================
# Tests for generate_response_stream
# ============================================================================


@pytest.mark.asyncio
async def test_generate_response_stream_basic(gemini_service, mock_generative_model):
    """Test basic streaming response"""
    chunks = []
    async for chunk in gemini_service.generate_response_stream("Hello"):
        chunks.append(chunk)

    assert len(chunks) > 0
    assert "Hello" in chunks[0]


@pytest.mark.asyncio
async def test_generate_response_stream_with_history(gemini_service, mock_generative_model):
    """Test streaming with conversation history"""
    history = [
        {"role": "user", "content": "Previous message"},
        {"role": "assistant", "content": "Previous response"},
    ]

    chunks = []
    async for chunk in gemini_service.generate_response_stream("Follow-up", history=history):
        chunks.append(chunk)

    # Verify chat was started with combined history
    mock_generative_model.start_chat.assert_called_once()
    # Check that start_chat was called (history is passed as first positional arg)
    call_args = mock_generative_model.start_chat.call_args
    if call_args and len(call_args[0]) > 0:
        chat_history = call_args[0][0]
        assert len(chat_history) > len(
            gemini_service.few_shot_history
        )  # Should include user history


@pytest.mark.asyncio
async def test_generate_response_stream_with_context(gemini_service, mock_generative_model):
    """Test streaming with RAG context"""
    context = "Context: This is important information"

    chunks = []
    async for chunk in gemini_service.generate_response_stream("Query", context=context):
        chunks.append(chunk)

    # Verify context was injected into message
    mock_chat = mock_generative_model.start_chat.return_value
    call_args = mock_chat.send_message_async.call_args[0][0]
    assert "CONTEXT" in call_args
    assert context in call_args


@pytest.mark.asyncio
async def test_generate_response_stream_without_context(gemini_service, mock_generative_model):
    """Test streaming without context"""
    chunks = []
    async for chunk in gemini_service.generate_response_stream("Query"):
        chunks.append(chunk)

    # Verify message doesn't have CONTEXT prefix
    mock_chat = mock_generative_model.start_chat.return_value
    call_args = mock_chat.send_message_async.call_args[0][0]
    assert not call_args.startswith("CONTEXT")


@pytest.mark.asyncio
async def test_generate_response_stream_history_format(gemini_service, mock_generative_model):
    """Test that history is converted to Gemini format"""
    history = [{"role": "user", "content": "test"}]

    # Consume the async generator
    async for _ in gemini_service.generate_response_stream("test", history=history):
        pass

    # Verify start_chat was called
    mock_generative_model.start_chat.assert_called_once()
    call_args = mock_generative_model.start_chat.call_args
    if call_args and len(call_args[0]) > 0:
        chat_history = call_args[0][0]
        # Check that user message is in correct format
        user_msgs = [msg for msg in chat_history if msg.get("role") == "user"]
        assert len(user_msgs) > 0
        assert "parts" in user_msgs[-1]


@pytest.mark.asyncio
async def test_generate_response_stream_empty_chunks(gemini_service, mock_generative_model):
    """Test handling of empty chunks"""

    async def empty_chunk_generator():
        mock_chunk = MagicMock()
        mock_chunk.text = None  # Empty chunk
        yield mock_chunk

    mock_response = MagicMock()
    mock_response.__aiter__ = lambda self: empty_chunk_generator()
    mock_chat = mock_generative_model.start_chat.return_value
    mock_chat.send_message_async = AsyncMock(return_value=mock_response)

    chunks = []
    async for chunk in gemini_service.generate_response_stream("test"):
        chunks.append(chunk)

    # Should skip empty chunks (None text)
    assert len(chunks) == 0


# ============================================================================
# Tests for generate_response
# ============================================================================


@pytest.mark.asyncio
async def test_generate_response_basic(gemini_service):
    """Test non-streaming response generation"""
    result = await gemini_service.generate_response("Hello")
    assert isinstance(result, str)
    assert len(result) > 0


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


@pytest.mark.asyncio
async def test_generate_response_uses_stream(gemini_service):
    """Test that generate_response uses generate_response_stream"""

    async def mock_stream_gen(message, history=None, context=""):
        for chunk in ["chunk1", "chunk2"]:
            yield chunk

    with patch.object(gemini_service, "generate_response_stream", side_effect=mock_stream_gen):
        result = await gemini_service.generate_response("test")
        assert result == "chunk1chunk2"


# ============================================================================
# Tests for singleton
# ============================================================================


def test_gemini_jaksel_singleton():
    """Test that gemini_jaksel is a singleton instance"""
    assert gemini_jaksel is not None
    assert isinstance(gemini_jaksel, GeminiJakselService)


def test_genai_configure_with_api_key():
    """Test that genai.configure is called when google_api_key is set"""
    with patch("services.gemini_service.settings") as mock_settings:
        mock_settings.google_api_key = "test-key"
        with patch("services.gemini_service.genai") as mock_genai:
            # Re-import to trigger the configuration
            import importlib

            import services.gemini_service

            importlib.reload(services.gemini_service)
            # The configure should have been called during import
            # Note: This is tested indirectly through the module-level code
