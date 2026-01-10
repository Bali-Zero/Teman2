from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import httpx
import pytest

from backend.app.services.audio_service import AudioService, get_audio_service


class _FakeResponse:
    def __init__(self, status_code=200, headers=None, content=b"", json_data=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content
        self._json_data = json_data

    def json(self):
        if self._json_data is None:
            raise ValueError("No JSON")
        return self._json_data


def _make_http_client(response=None, error=None):
    client = AsyncMock()
    if error:
        client.get = AsyncMock(side_effect=error)
    else:
        client.get = AsyncMock(return_value=response)
    client.aclose = AsyncMock()
    return client


def _make_openai_client(transcript_text="ok", speech_content=b"audio", error=None):
    audio = MagicMock()
    if error:
        audio.transcriptions.create = AsyncMock(side_effect=error)
        audio.speech.create = AsyncMock(side_effect=error)
    else:
        transcript = MagicMock()
        transcript.text = transcript_text
        audio.transcriptions.create = AsyncMock(return_value=transcript)
        speech = MagicMock()
        speech.content = speech_content
        audio.speech.create = AsyncMock(return_value=speech)
    client = MagicMock()
    client.audio = audio
    return client


def _build_service(openai_key="key", http_client=None, openai_client=None):
    if http_client is None:
        http_client = _make_http_client(
            _FakeResponse(status_code=200, headers={"content-type": "audio/mpeg"}, content=b"tts")
        )
    if openai_client is None and openai_key:
        openai_client = _make_openai_client()

    with patch("backend.app.services.audio_service.settings") as mock_settings:
        mock_settings.openai_api_key = openai_key
        with patch("backend.app.services.audio_service.httpx.AsyncClient", return_value=http_client):
            with patch("backend.app.services.audio_service.AsyncOpenAI") as mock_openai:
                mock_openai.return_value = openai_client
                service = AudioService()
    return service


def test_init_with_openai_key():
    service = _build_service(openai_key="test-key")

    assert service.openai_api_key == "test-key"
    assert service.openai_client is not None


def test_init_without_openai_key():
    service = _build_service(openai_key=None)

    assert service.openai_api_key is None
    assert service.openai_client is None


@pytest.mark.asyncio
async def test_transcribe_audio_from_path():
    service = _build_service(openai_key="test-key")

    with patch("builtins.open", mock_open(read_data=b"audio data")) as mock_file:
        result = await service.transcribe_audio("/path/to/audio.mp3", language="id")

    assert result == "ok"
    mock_file.assert_called_once_with("/path/to/audio.mp3", "rb")
    call_kwargs = service.openai_client.audio.transcriptions.create.call_args.kwargs
    assert call_kwargs["language"] == "id"


@pytest.mark.asyncio
async def test_transcribe_audio_from_buffer_not_closed():
    service = _build_service(openai_key="test-key")

    buffer = BytesIO(b"audio")
    buffer.close = MagicMock()

    result = await service.transcribe_audio(buffer)

    assert result == "ok"
    buffer.close.assert_not_called()


@pytest.mark.asyncio
async def test_transcribe_audio_without_openai_key():
    service = _build_service(openai_key=None)

    with pytest.raises(ValueError, match="STT requires OpenAI API key"):
        await service.transcribe_audio("/path/to/audio.mp3")


@pytest.mark.asyncio
async def test_transcribe_audio_exception_closes_file():
    error = RuntimeError("api error")
    service = _build_service(openai_key="test-key", openai_client=_make_openai_client(error=error))

    mock_file = MagicMock()
    with patch("builtins.open", return_value=mock_file):
        with pytest.raises(RuntimeError, match="api error"):
            await service.transcribe_audio("/path/to/audio.mp3")

    mock_file.close.assert_called_once()


@pytest.mark.asyncio
async def test_generate_speech_pollinations_success_returns_bytes():
    service = _build_service(openai_key="test-key")

    result = await service.generate_speech("hello", voice="alloy")

    assert result == b"tts"


@pytest.mark.asyncio
async def test_generate_speech_pollinations_success_with_output_path():
    service = _build_service(openai_key="test-key")

    with patch("builtins.open", mock_open()) as mock_file:
        result = await service.generate_speech("hello", output_path="/tmp/audio.mp3")

    assert result == "/tmp/audio.mp3"
    mock_file.assert_called_once_with("/tmp/audio.mp3", "wb")


@pytest.mark.asyncio
async def test_generate_speech_invalid_voice_defaults():
    service = _build_service(openai_key="test-key")

    result = await service.generate_speech("hello", voice="invalid")

    assert result == b"tts"


@pytest.mark.asyncio
async def test_generate_speech_fallback_to_openai():
    http_client = _make_http_client(
        _FakeResponse(status_code=500, headers={"content-type": "text/plain"})
    )
    openai_client = _make_openai_client(speech_content=b"fallback")
    service = _build_service(
        openai_key="test-key", http_client=http_client, openai_client=openai_client
    )

    result = await service.generate_speech("hello", voice="alloy")

    assert result == b"fallback"


@pytest.mark.asyncio
async def test_generate_speech_fallback_missing_openai():
    http_client = _make_http_client(
        _FakeResponse(status_code=500, headers={"content-type": "text/plain"})
    )
    service = _build_service(openai_key=None, http_client=http_client)

    with pytest.raises(ValueError, match="All TTS providers failed"):
        await service.generate_speech("hello")


@pytest.mark.asyncio
async def test_pollinations_tts_non_audio_content():
    response = _FakeResponse(
        status_code=200,
        headers={"content-type": "application/json"},
        content=b'{"error":"bad"}',
        json_data={"error": "bad"},
    )
    service = _build_service(openai_key="test-key", http_client=_make_http_client(response))

    result = await service._pollinations_tts("hello", "alloy")

    assert result is None


@pytest.mark.asyncio
async def test_pollinations_tts_timeout():
    service = _build_service(
        openai_key="test-key",
        http_client=_make_http_client(error=httpx.TimeoutException("timeout")),
    )

    result = await service._pollinations_tts("hello", "alloy")

    assert result is None


@pytest.mark.asyncio
async def test_close_closes_http_client():
    http_client = _make_http_client(
        _FakeResponse(status_code=200, headers={"content-type": "audio/mpeg"}, content=b"tts")
    )
    service = _build_service(openai_key="test-key", http_client=http_client)

    await service.close()

    http_client.aclose.assert_called_once()


def test_get_audio_service_singleton():
    with patch("backend.app.services.audio_service.settings") as mock_settings:
        mock_settings.openai_api_key = None
        with patch("backend.app.services.audio_service.httpx.AsyncClient") as mock_http:
            mock_http.return_value = _make_http_client(
                _FakeResponse(
                    status_code=200, headers={"content-type": "audio/mpeg"}, content=b"tts"
                )
            )
            import backend.app.services.audio_service as audio_service

            audio_service._audio_service = None
            first = get_audio_service()
            second = get_audio_service()

    assert first is second
