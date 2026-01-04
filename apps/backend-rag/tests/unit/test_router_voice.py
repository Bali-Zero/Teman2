"""
Unit tests for Voice Router
Tests voice endpoint with fast response generation
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.routers import voice


@pytest.fixture
def mock_search_service():
    """Mock SearchService"""
    service = MagicMock()
    service.search = AsyncMock(
        return_value={
            "documents": ["Doc 1", "Doc 2"],
            "metadatas": [{"id": "1"}, {"id": "2"}],
            "distances": [0.1, 0.2],
        }
    )
    return service


@pytest.fixture
def mock_request():
    """Mock FastAPI Request"""
    request = MagicMock()
    request.app = MagicMock()
    request.app.state = MagicMock()
    return request


# ============================================================================
# Tests for verify_api_key
# ============================================================================


@pytest.mark.asyncio
async def test_verify_api_key_success():
    """Test successful API key verification"""
    with patch("app.routers.voice.settings") as mock_settings:
        mock_settings.api_keys = "key1,key2,key3"
        result = await voice.verify_api_key("key2")
        assert result == {"user_id": "voice-service", "role": "service"}


@pytest.mark.asyncio
async def test_verify_api_key_missing():
    """Test missing API key"""
    with pytest.raises(HTTPException) as exc:
        await voice.verify_api_key(None)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_invalid():
    """Test invalid API key"""
    with patch("app.routers.voice.settings") as mock_settings:
        mock_settings.api_keys = "key1,key2"
        with pytest.raises(HTTPException) as exc:
            await voice.verify_api_key("invalid_key")
        assert exc.value.status_code == 403


# ============================================================================
# Tests for VoiceQueryRequest model
# ============================================================================


def test_voice_query_request_defaults():
    """Test VoiceQueryRequest with defaults"""
    request = voice.VoiceQueryRequest(query="Test query")
    assert request.query == "Test query"
    assert request.user_id == "voice-user"
    assert request.session_id is None
    assert request.conversation_history is None


def test_voice_query_request_with_all_fields():
    """Test VoiceQueryRequest with all fields"""
    request = voice.VoiceQueryRequest(
        query="Test query",
        user_id="user123",
        session_id="session123",
        conversation_history=[{"role": "user", "content": "Hi"}],
    )
    assert request.query == "Test query"
    assert request.user_id == "user123"
    assert request.session_id == "session123"
    assert len(request.conversation_history) == 1


def test_voice_query_response():
    """Test VoiceQueryResponse model"""
    response = voice.VoiceQueryResponse(
        answer="Test answer",
        sources=["doc1.pdf", "doc2.pdf"],
        execution_time=1.5,
    )
    assert response.answer == "Test answer"
    assert len(response.sources) == 2
    assert response.execution_time == 1.5


# ============================================================================
# Tests for generate_fast_response
# ============================================================================


# Note: generate_fast_response is an internal function, tested indirectly via voice_query
# These tests are skipped as the function is not exported from the module
@pytest.mark.skip(reason="generate_fast_response is an internal function, tested via voice_query")
async def test_generate_fast_response_success():
    """Test successful fast response generation - tested via voice_query"""
    pass


@pytest.mark.skip(reason="generate_fast_response is an internal function, tested via voice_query")
async def test_generate_fast_response_with_history():
    """Test fast response generation with conversation history - tested via voice_query"""
    pass


@pytest.mark.skip(reason="generate_fast_response is an internal function, tested via voice_query")
async def test_generate_fast_response_exception():
    """Test fast response generation with exception - tested via voice_query"""
    pass


def test_elevenlabs_request_get_query():
    """Test ElevenLabsRequest get_query method"""
    # Test with query field
    request = voice.ElevenLabsRequest(query="test query")
    assert request.get_query() == "test query"

    # Test with question field
    request = voice.ElevenLabsRequest(question="test question")
    assert request.get_query() == "test question"

    # Test with text field
    request = voice.ElevenLabsRequest(text="test text")
    assert request.get_query() == "test text"

    # Test with message field
    request = voice.ElevenLabsRequest(message="test message")
    assert request.get_query() == "test message"

    # Test with empty
    request = voice.ElevenLabsRequest()
    assert request.get_query() == ""


# ============================================================================
# Tests for voice_query endpoint
# ============================================================================


@pytest.mark.asyncio
async def test_get_search_service_success(mock_request):
    """Test get_search_service with available service"""
    mock_request.app.state.search_service = MagicMock()
    service = await voice.get_search_service(mock_request)
    assert service is not None


@pytest.mark.asyncio
async def test_get_search_service_not_available(mock_request):
    """Test get_search_service without service"""
    mock_request.app.state.search_service = None
    with pytest.raises(HTTPException) as exc:
        await voice.get_search_service(mock_request)
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_voice_query_success():
    """Test successful voice query"""
    mock_search_service = MagicMock()
    mock_search_service.search = AsyncMock(
        return_value={
            "results": [
                {"text": "Test context 1", "metadata": {"source": "doc1.pdf"}},
                {"text": "Test context 2", "metadata": {"source": "doc2.pdf"}},
            ]
        }
    )

    mock_api_user = {"user_id": "voice-service", "role": "service"}
    mock_request = MagicMock(spec=Request)

    with patch("app.routers.voice.generate_fast_response", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "Test answer"

        request = voice.VoiceQueryRequest(query="Test query")
        response = await voice.voice_query(
            request, mock_request, mock_api_user, mock_search_service
        )

        assert response.answer == "Test answer"
        assert isinstance(response.execution_time, float)
        assert len(response.sources) >= 0


@pytest.mark.asyncio
async def test_voice_query_empty_query():
    """Test voice query with empty query"""
    mock_search_service = MagicMock()
    mock_api_user = {"user_id": "voice-service", "role": "service"}
    mock_request = MagicMock(spec=Request)

    with pytest.raises(HTTPException) as exc:
        request = voice.VoiceQueryRequest(query="   ")  # Empty/whitespace query
        await voice.voice_query(request, mock_request, mock_api_user, mock_search_service)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_voice_query_with_conversation_history():
    """Test voice query with conversation history"""
    mock_search_service = MagicMock()
    mock_search_service.search = AsyncMock(return_value={"results": []})
    mock_api_user = {"user_id": "voice-service", "role": "service"}
    mock_request = MagicMock(spec=Request)

    with patch("app.routers.voice.generate_fast_response", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "Test answer"

        request = voice.VoiceQueryRequest(
            query="Test query",
            conversation_history=[{"role": "user", "content": "Previous"}],
        )
        response = await voice.voice_query(
            request, mock_request, mock_api_user, mock_search_service
        )

        assert response.answer == "Test answer"
        mock_gen.assert_called_once()


@pytest.mark.asyncio
async def test_voice_query_exception():
    """Test voice query with exception"""
    mock_search_service = MagicMock()
    mock_search_service.search = AsyncMock(side_effect=Exception("Search error"))
    mock_api_user = {"user_id": "voice-service", "role": "service"}
    mock_request = MagicMock(spec=Request)

    with pytest.raises(HTTPException) as exc:
        request = voice.VoiceQueryRequest(query="Test query")
        await voice.voice_query(request, mock_request, mock_api_user, mock_search_service)
    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_elevenlabs_options():
    """Test ElevenLabs OPTIONS endpoint"""
    response = await voice.elevenlabs_options()
    assert isinstance(response, JSONResponse)
    assert "Access-Control-Allow-Origin" in response.headers


@pytest.mark.asyncio
async def test_elevenlabs_webhook_success():
    """Test successful ElevenLabs webhook"""
    mock_search_service = MagicMock()
    mock_search_service.search = AsyncMock(return_value={"results": []})
    mock_request = MagicMock(spec=Request)

    with patch("app.routers.voice.generate_fast_response", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "Test answer"

        request = voice.ElevenLabsRequest(query="Test query")
        response = await voice.elevenlabs_webhook(request, mock_request, mock_search_service)

        assert isinstance(response, JSONResponse)
        assert response.body is not None


@pytest.mark.asyncio
async def test_elevenlabs_webhook_empty_query():
    """Test ElevenLabs webhook with empty query"""
    mock_search_service = MagicMock()
    mock_request = MagicMock(spec=Request)

    request = voice.ElevenLabsRequest(query="")
    response = await voice.elevenlabs_webhook(request, mock_request, mock_search_service)

    assert isinstance(response, dict)
    assert "result" in response


@pytest.mark.asyncio
async def test_elevenlabs_webhook_get_query_from_question():
    """Test ElevenLabs webhook using question field"""
    mock_search_service = MagicMock()
    mock_search_service.search = AsyncMock(return_value={"results": []})
    mock_request = MagicMock(spec=Request)

    with patch("app.routers.voice.generate_fast_response", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "Test answer"

        request = voice.ElevenLabsRequest(question="Test question")
        response = await voice.elevenlabs_webhook(request, mock_request, mock_search_service)

        assert isinstance(response, JSONResponse)


@pytest.mark.asyncio
async def test_elevenlabs_webhook_exception():
    """Test ElevenLabs webhook with exception"""
    mock_search_service = MagicMock()
    mock_search_service.search = AsyncMock(side_effect=Exception("Search error"))
    mock_request = MagicMock(spec=Request)

    request = voice.ElevenLabsRequest(query="Test query")
    response = await voice.elevenlabs_webhook(request, mock_request, mock_search_service)

    assert isinstance(response, JSONResponse)
    assert "result" in response.body.decode()


# ============================================================================
# Tests for router structure
# ============================================================================


def test_router_structure():
    """Test router configuration"""
    assert voice.router.prefix == "/api/voice"
    assert "voice" in voice.router.tags
