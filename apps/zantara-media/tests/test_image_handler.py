"""Tests for zantara_media.handlers.image_handler.

Kept from the old tests/test_handlers.py when the GARUDA indexer was removed
(2026-08-07): the magazine's media_resolver uses extract_image as its default
describer, so these two are the corpus that still has an owner.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


from zantara_media.handlers.image_handler import extract_image


def _mock_ollama_response(text: str) -> MagicMock:
    """Return a mock httpx response simulating Ollama /api/generate."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"response": text}
    return mock_resp


# ---------------------------------------------------------------------------
# 1. PDF extraction via pypdf (text-layer PDF)
# ---------------------------------------------------------------------------

async def test_image_ollama_response():
    """extract_image should return Ollama's description text."""
    expected_desc = "A scenic beach at sunset with golden hues."

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=_mock_ollama_response(expected_desc))

    with patch("zantara_media.handlers.image_handler.httpx.AsyncClient", return_value=mock_client):
        text, meta = await extract_image(b"\xff\xd8\xff", "beach.jpg")

    assert text == expected_desc
    assert meta["model"] == "qwen2.5vl:7b"
    assert meta["source"] == "ollama_vision"


# ---------------------------------------------------------------------------
# 4. Image handler — Ollama timeout
# ---------------------------------------------------------------------------
async def test_image_ollama_timeout():
    """On httpx timeout, extract_image should return empty string with error key."""
    import httpx as real_httpx

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=real_httpx.TimeoutException("timed out"))

    with patch("zantara_media.handlers.image_handler.httpx.AsyncClient", return_value=mock_client):
        text, meta = await extract_image(b"\xff\xd8\xff", "photo.jpg")

    assert text == ""
    assert meta.get("error") == "vision_timeout"


# ---------------------------------------------------------------------------
# 5. Audio transcription
# ---------------------------------------------------------------------------
