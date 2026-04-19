"""
Unit tests for LLM cost tracking in AudioService.

Tests verify that @llm_cost_tracked is applied to the OpenAI paths only:
- _openai_tts  → provider=openai_audio, model=tts-1, input_tokens=len(text)
- _openai_stt  → provider=openai_audio, model=whisper-1, input_tokens=duration_seconds

Pollinations path is NOT tested here (it is free and intentionally untracked).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.services.audio_service import AudioService


@pytest.mark.asyncio
async def test_openai_tts_records_cost():
    """_openai_tts must emit a record_llm_call with correct cost fields."""
    svc = AudioService.__new__(AudioService)
    svc.openai_client = MagicMock()
    svc.openai_client.audio.speech.create = AsyncMock(
        return_value=MagicMock(content=b"audio-bytes"),
    )

    with patch(
        "backend.services.observability.tracking_decorator.record_llm_call",
        new=AsyncMock(),
    ) as mock_rec:
        result = await svc._openai_tts(text="hello world", voice="alloy")

    assert result == b"audio-bytes"
    mock_rec.assert_awaited_once()
    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "openai_audio"
    assert kwargs["model"] == "tts-1"
    assert kwargs["input_tokens"] == len("hello world")
    assert kwargs["output_tokens"] == 0
    assert kwargs["success"] is True


@pytest.mark.asyncio
async def test_openai_stt_records_cost():
    """_openai_stt must emit a record_llm_call with correct cost fields."""
    svc = AudioService.__new__(AudioService)
    svc.openai_client = MagicMock()
    svc.openai_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="hello world"),
    )

    with patch("builtins.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock()), __exit__=MagicMock(return_value=False)))), \
         patch(
             "backend.services.observability.tracking_decorator.record_llm_call",
             new=AsyncMock(),
         ) as mock_rec:
        result = await svc._openai_stt(file_path="/tmp/x.mp3", duration_seconds=12)

    assert result == "hello world"
    mock_rec.assert_awaited_once()
    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "openai_audio"
    assert kwargs["model"] == "whisper-1"
    assert kwargs["input_tokens"] == 12        # seconds passed verbatim
    assert kwargs["output_tokens"] == len("hello world") // 4
    assert kwargs["success"] is True


@pytest.mark.asyncio
async def test_openai_tts_records_on_failure():
    """_openai_tts must still emit record_llm_call with success=False on exception."""
    svc = AudioService.__new__(AudioService)
    svc.openai_client = MagicMock()
    svc.openai_client.audio.speech.create = AsyncMock(side_effect=RuntimeError("quota"))

    with patch(
        "backend.services.observability.tracking_decorator.record_llm_call",
        new=AsyncMock(),
    ) as mock_rec:
        with pytest.raises(RuntimeError, match="quota"):
            await svc._openai_tts(text="x", voice="alloy")

    mock_rec.assert_awaited_once()
    kwargs = mock_rec.await_args.kwargs
    assert kwargs["success"] is False
    assert kwargs["error_class"] == "RuntimeError"


@pytest.mark.asyncio
async def test_openai_tts_input_tokens_match_char_count():
    """input_tokens for TTS must equal len(text) in characters (matches $15/1M chars pricing)."""
    svc = AudioService.__new__(AudioService)
    svc.openai_client = MagicMock()
    svc.openai_client.audio.speech.create = AsyncMock(
        return_value=MagicMock(content=b"x"),
    )
    text = "hello Bali 🌴"  # mix of ASCII + emoji to confirm char count, not byte count

    with patch(
        "backend.services.observability.tracking_decorator.record_llm_call",
        new=AsyncMock(),
    ) as mock_rec:
        await svc._openai_tts(text=text, voice="alloy")

    kwargs = mock_rec.await_args.kwargs
    assert kwargs["input_tokens"] == len(text)


@pytest.mark.asyncio
async def test_openai_stt_float_duration_is_truncated():
    """duration_seconds as float must be safely cast to int for input_tokens."""
    svc = AudioService.__new__(AudioService)
    svc.openai_client = MagicMock()
    svc.openai_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="ciao"),
    )

    with patch("builtins.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock()), __exit__=MagicMock(return_value=False)))), \
         patch(
             "backend.services.observability.tracking_decorator.record_llm_call",
             new=AsyncMock(),
         ) as mock_rec:
        await svc._openai_stt(file_path="/tmp/y.mp3", duration_seconds=7.9)

    kwargs = mock_rec.await_args.kwargs
    assert kwargs["input_tokens"] == 7   # int(7.9) == 7


@pytest.mark.asyncio
async def test_pollinations_path_not_tracked(monkeypatch):
    """generate_speech via Pollinations must NOT call record_llm_call."""

    svc = AudioService.__new__(AudioService)
    svc.tts_timeout = 5.0
    svc.openai_client = None  # OpenAI unavailable → ensure fallback path is dead

    # Simulate Pollinations returning valid audio bytes
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "audio/mpeg"}
    mock_response.content = b"fake-audio"

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=mock_response)
    svc.http_client = mock_http

    with patch(
        "backend.services.observability.tracking_decorator.record_llm_call",
        new=AsyncMock(),
    ) as mock_rec:
        result = await svc.generate_speech(text="ciao", voice="alloy")

    assert result == b"fake-audio"
    mock_rec.assert_not_awaited()
