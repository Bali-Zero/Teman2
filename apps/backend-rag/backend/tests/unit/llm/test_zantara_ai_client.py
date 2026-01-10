"""
Tests for ZantaraAIClient
Target: 100% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from llm.zantara_ai_client import ZantaraAIClient


@pytest.fixture
def mock_genai_available():
    with patch("llm.zantara_ai_client.GENAI_AVAILABLE", True):
        yield


@pytest.fixture
def mock_genai_client():
    with patch("llm.zantara_ai_client.GenAIClient") as MockClient:
        instance = MockClient.return_value
        instance.is_available = True
        yield MockClient


# ============================================================================
# TESTS: Initialization
# ============================================================================
def test_init_with_api_key(mock_genai_available, mock_genai_client):
    client = ZantaraAIClient(api_key="test_key")
    assert client.api_key == "test_key"
    assert client.mock_mode is False
    assert client._genai_client is not None


def test_init_with_service_account(mock_genai_available, mock_genai_client):
    with patch("os.environ.get", return_value="path/to/creds.json"):
        client = ZantaraAIClient(api_key=None)
        assert client.mock_mode is False


def test_init_mock_mode_no_creds(mock_genai_available):
    with (
        patch("app.core.config.settings.environment", "development"),
        patch("app.core.config.settings.google_api_key", None),
        patch("app.core.config.settings.google_credentials_json", None),
        patch("os.environ.get", return_value=None),
    ):
        client = ZantaraAIClient(api_key=None)
        assert client.mock_mode is True
        assert client._genai_client is None


def test_init_production_no_creds(mock_genai_available):
    with (
        patch("app.core.config.settings.environment", "production"),
        patch("app.core.config.settings.google_api_key", None),
        patch("app.core.config.settings.google_credentials_json", None),
        patch("os.environ.get", return_value=None),
        pytest.raises(ValueError, match="GOOGLE_API_KEY or GOOGLE_CREDENTIALS_JSON is required"),
    ):
        ZantaraAIClient(api_key=None)


def test_init_genai_client_fail(mock_genai_available, mock_genai_client):
    # Simulate GenAI client failing to initialize
    mock_genai_client.side_effect = Exception("Init failed")
    with patch("app.core.config.settings.environment", "development"):
        client = ZantaraAIClient(api_key="test")
        assert client.mock_mode is True


def test_init_genai_client_fail_production(mock_genai_available, mock_genai_client):
    mock_genai_client.side_effect = Exception("Init failed")
    with patch("app.core.config.settings.environment", "production"):
        with pytest.raises(ValueError, match="Failed to configure Gemini in production"):
            ZantaraAIClient(api_key="test")


# ============================================================================
# TESTS: Helper Methods
# ============================================================================
def test_get_model_info(mock_genai_available, mock_genai_client):
    client = ZantaraAIClient(api_key="test")
    info = client.get_model_info()
    assert info["model"] == "gemini-3-flash-preview"
    assert info["provider"] == "google_native"

    client.mock_mode = True
    info = client.get_model_info()
    assert info["provider"] == "mock"


def test_validate_inputs(mock_genai_available, mock_genai_client):
    client = ZantaraAIClient(api_key="test")

    # Valid
    client._validate_inputs(
        max_tokens=100, temperature=0.5, messages=[{"role": "user", "content": "hi"}]
    )

    # Invalid max_tokens
    with pytest.raises(ValueError):
        client._validate_inputs(max_tokens=0)
    with pytest.raises(ValueError):
        client._validate_inputs(max_tokens=10000)

    # Invalid temperature
    with pytest.raises(ValueError):
        client._validate_inputs(temperature=-1)
    with pytest.raises(ValueError):
        client._validate_inputs(temperature=2.1)

    # Invalid messages
    with pytest.raises(ValueError):
        client._validate_inputs(messages=[])  # Empty
    with pytest.raises(ValueError):
        client._validate_inputs(messages="not a list")
    with pytest.raises(ValueError):
        client._validate_inputs(messages=[{"role": "user"}])  # Missing content


def test_prepare_gemini_messages(mock_genai_available, mock_genai_client):
    client = ZantaraAIClient(api_key="test")
    messages = [
        {"role": "system", "content": "sys"},  # Should be skipped
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "bye"},
    ]

    history, last_msg = client._prepare_gemini_messages(messages)

    assert len(history) == 2  # user:hi, model:hello
    assert history[0]["role"] == "user"
    assert history[0]["parts"] == ["hi"]
    assert history[1]["role"] == "model"
    assert history[1]["parts"] == ["hello"]
    assert last_msg == "bye"


def test_extract_response_text(mock_genai_available, mock_genai_client):
    client = ZantaraAIClient(api_key="test")

    # Standard response
    mock_resp = MagicMock()
    mock_resp.text = "Response text"
    mock_resp.candidates = [MagicMock()]
    assert client._extract_response_text(mock_resp) == "Response text"

    # Safety blocked but content available
    mock_candidate = MagicMock()
    mock_rating = MagicMock()
    mock_rating.probability.name = "HIGH"
    mock_candidate.safety_ratings = [mock_rating]
    mock_candidate.content.parts = [MagicMock(text="Unsafe text")]
    mock_resp.candidates = [mock_candidate]

    assert client._extract_response_text(mock_resp) == "Unsafe text"

    # Safety blocked, no content
    mock_candidate.content.parts = []
    with pytest.raises(ValueError, match="Response blocked"):
        client._extract_response_text(mock_resp)


def test_estimate_tokens(mock_genai_available, mock_genai_client):
    client = ZantaraAIClient(api_key="test")
    client.token_estimator = MagicMock()
    client.token_estimator.estimate_messages_tokens.return_value = 10
    client.token_estimator.estimate_tokens.return_value = 20

    tokens = client._estimate_tokens([], "response")
    assert tokens["input"] == 10
    assert tokens["output"] == 20


# ============================================================================
# TESTS: chat_async
# ============================================================================
@pytest.mark.asyncio
async def test_chat_async_success(mock_genai_available, mock_genai_client):
    client = ZantaraAIClient(api_key="test")
    mock_chat = AsyncMock()
    mock_chat.send_message.return_value = {"text": "Response"}
    client._genai_client.create_chat.return_value = mock_chat

    result = await client.chat_async(messages=[{"role": "user", "content": "hi"}])
    assert result["text"] == "Response"
    assert result["provider"] == "google_genai"


@pytest.mark.asyncio
async def test_chat_async_mock_mode(mock_genai_available):
    client = ZantaraAIClient(api_key="test")
    client.mock_mode = True

    result = await client.chat_async(messages=[{"role": "user", "content": "hi"}])
    assert result["provider"] == "mock"
    assert "MOCK response" in result["text"]


@pytest.mark.asyncio
async def test_chat_async_unavailable(mock_genai_available, mock_genai_client):
    client = ZantaraAIClient(api_key="test")
    client._genai_client = None

    with pytest.raises(ValueError, match="Gemini client library is not available"):
        await client.chat_async(messages=[{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_chat_async_connection_error(mock_genai_available, mock_genai_client):
    client = ZantaraAIClient(api_key="test")
    client._genai_client.create_chat.side_effect = ConnectionError("Conn Fail")

    with pytest.raises(ConnectionError):
        await client.chat_async(messages=[{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_chat_async_api_key_leak(mock_genai_available, mock_genai_client):
    client = ZantaraAIClient(api_key="test")
    client._genai_client.create_chat.side_effect = Exception("403 Forbidden: API key leaked")

    with pytest.raises(ValueError, match="API key was reported as leaked"):
        await client.chat_async(messages=[{"role": "user", "content": "hi"}])


# ============================================================================
# TESTS: stream
# ============================================================================
@pytest.mark.asyncio
async def test_stream_success(mock_genai_available, mock_genai_client):
    client = ZantaraAIClient(api_key="test")

    # Mock chat session and streaming
    mock_chat = MagicMock()

    # Mock send_message_stream as async generator
    async def mock_stream(*args, **kwargs):
        yield "Hello"
        yield " World"

    mock_chat.send_message_stream.side_effect = mock_stream
    client._genai_client.create_chat.return_value = mock_chat

    chunks = []
    async for chunk in client.stream(message="hi", user_id="user1"):
        chunks.append(chunk)

    assert "".join(chunks) == "Hello World"


@pytest.mark.asyncio
async def test_stream_mock_mode(mock_genai_available):
    client = ZantaraAIClient(api_key="test")
    client.mock_mode = True

    chunks = []
    async for chunk in client.stream(message="hi", user_id="user1"):
        chunks.append(chunk)

    assert len(chunks) > 0
    assert "MOCK" in "".join(chunks)


@pytest.mark.asyncio
async def test_stream_unavailable(mock_genai_available, mock_genai_client):
    client = ZantaraAIClient(api_key="test")
    client._genai_client = None

    chunks = []
    async for chunk in client.stream(message="hi", user_id="user1"):
        chunks.append(chunk)

    # Should yield fallback message
    assert len(chunks) > 0


@pytest.mark.asyncio
async def test_stream_no_content(mock_genai_available, mock_genai_client):
    client = ZantaraAIClient(api_key="test")

    mock_chat = MagicMock()

    async def empty_stream(*args, **kwargs):
        if False:
            yield "nothing"

    mock_chat.send_message_stream.side_effect = empty_stream
    client._genai_client.create_chat.return_value = mock_chat

    # Should retry then fail then fallback
    chunks = []
    async for chunk in client.stream(message="hi", user_id="user1"):
        chunks.append(chunk)

    assert len(chunks) > 0  # Fallback message


@pytest.mark.asyncio
async def test_stream_api_key_leak(mock_genai_available, mock_genai_client):
    client = ZantaraAIClient(api_key="test")
    client._genai_client.create_chat.side_effect = ValueError("API key leaked")

    chunks = []
    async for chunk in client.stream(message="hi", user_id="user1"):
        chunks.append(chunk)

    # Should yield fallback message for API key error
    assert len(chunks) > 0


# ============================================================================
# TESTS: conversational / conversational_with_tools
# ============================================================================
@pytest.mark.asyncio
async def test_conversational(mock_genai_available, mock_genai_client):
    client = ZantaraAIClient(api_key="test")
    with patch.object(
        client,
        "chat_async",
        return_value={"text": "Resp", "model": "gemini", "provider": "google", "tokens": {}},
    ):
        result = await client.conversational("hi", "user1")
        assert result["text"] == "Resp"
        assert result["ai_used"] == "zantara-ai"


@pytest.mark.asyncio
async def test_conversational_with_tools(mock_genai_available, mock_genai_client):
    client = ZantaraAIClient(api_key="test")
    with patch.object(
        client,
        "chat_async",
        return_value={"text": "Resp", "model": "gemini", "provider": "google", "tokens": {}},
    ):
        result = await client.conversational_with_tools("hi", "user1", tools=[{}])
        assert result["text"] == "Resp"
        assert result["used_tools"] is False


def test_is_available(mock_genai_available, mock_genai_client):
    client = ZantaraAIClient(api_key="test")
    assert client.is_available() is True

    client = ZantaraAIClient(api_key=None)
    client.mock_mode = True
    assert client.is_available() is True
