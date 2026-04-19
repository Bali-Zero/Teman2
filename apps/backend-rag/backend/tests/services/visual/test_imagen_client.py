"""Unit tests for ImagenClient (mocked httpx) + quality routing + cost mapping."""

from __future__ import annotations

import base64
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from backend.services.visual.imagen_client import (
    ImagenClient,
    ImagenError,
    ImagenQuality,
    _parse_response,
)


def _fake_b64_image() -> str:
    # 3-byte minimal "image" is enough to verify the pipeline
    return base64.b64encode(b"\x89PNG_x").decode("ascii")


def _ok_response(b64: str | None = None, mime: str = "image/png") -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {
        "predictions": [
            {"bytesBase64Encoded": b64 or _fake_b64_image(), "mimeType": mime},
        ],
    }
    return response


def _err_response(status: int, text: str = "error") -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status
    response.text = text
    return response


# ── Configuration ─────────────────────────────────────────────────────

def test_requires_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ImagenError):
        ImagenClient()


def test_picks_up_gemini_api_key_env(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key-xyz")
    client = ImagenClient()
    assert client.api_key == "gemini-key-xyz"


def test_google_api_key_takes_precedence(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    client = ImagenClient()
    assert client.api_key == "google-key"


# ── Quality routing ───────────────────────────────────────────────────

def test_quality_cost_mapping():
    assert ImagenQuality.ULTRA.cost_usd == Decimal("0.06")
    assert ImagenQuality.STANDARD.cost_usd == Decimal("0.04")
    assert ImagenQuality.FAST.cost_usd == Decimal("0.02")


def test_quality_model_ids():
    assert "ultra" in ImagenQuality.ULTRA.model_id.lower()
    assert "fast" in ImagenQuality.FAST.model_id.lower()


# ── _parse_response ──────────────────────────────────────────────────

def test_parse_response_happy_path():
    body = {
        "predictions": [
            {"bytesBase64Encoded": _fake_b64_image(), "mimeType": "image/png"},
        ],
    }
    raw, mime, err = _parse_response(body)
    assert err is None
    assert mime == "image/png"
    assert raw and raw.startswith(b"\x89PNG")


def test_parse_response_missing_predictions():
    raw, mime, err = _parse_response({})
    assert raw is None
    assert err is not None
    assert "predictions" in err


def test_parse_response_alt_imageBytes_field():
    body = {
        "predictions": [{"imageBytes": _fake_b64_image()}],
    }
    raw, _, err = _parse_response(body)
    assert err is None
    assert raw is not None


def test_parse_response_nested_image_dict():
    body = {
        "predictions": [
            {"image": {"bytesBase64Encoded": _fake_b64_image()}}
        ],
    }
    raw, _, err = _parse_response(body)
    assert err is None
    assert raw is not None


def test_parse_response_bad_base64():
    body = {
        "predictions": [
            {"bytesBase64Encoded": "!!!!not-base64!!!!"},
        ],
    }
    raw, _, err = _parse_response(body)
    assert raw is None
    assert err is not None
    assert "base64" in err.lower()


# ── Generate with mock httpx ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_success_fast_quality():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=_ok_response())
    client = ImagenClient(api_key="k", http_client=mock_client)

    result = await client.generate("a prompt", quality=ImagenQuality.FAST)
    assert result.ok is True
    assert result.quality == ImagenQuality.FAST
    assert result.cost_usd == Decimal("0.02")
    assert result.image_bytes is not None
    # verify URL contains the fast model id
    posted_url = mock_client.post.call_args.args[0]
    assert "fast" in posted_url


@pytest.mark.asyncio
async def test_generate_success_ultra_quality():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=_ok_response())
    client = ImagenClient(api_key="k", http_client=mock_client)
    result = await client.generate("hero", quality=ImagenQuality.ULTRA)
    assert result.cost_usd == Decimal("0.06")
    posted_url = mock_client.post.call_args.args[0]
    assert "ultra" in posted_url


@pytest.mark.asyncio
async def test_generate_http_error_sets_not_ok():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=_err_response(429, "rate limited"))
    client = ImagenClient(api_key="k", http_client=mock_client)

    result = await client.generate("x")
    assert result.ok is False
    assert result.cost_usd == Decimal("0")
    assert "429" in (result.error or "")
    assert result.image_bytes is None


@pytest.mark.asyncio
async def test_generate_exception_wraps_error():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=RuntimeError("boom"))
    client = ImagenClient(api_key="k", http_client=mock_client)

    result = await client.generate("x")
    assert result.ok is False
    assert "RuntimeError" in (result.error or "")


@pytest.mark.asyncio
async def test_generate_passes_negative_prompt_when_provided():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=_ok_response())
    client = ImagenClient(api_key="k", http_client=mock_client)
    await client.generate("p", negative_prompt="no stock")
    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["instances"][0]["negativePrompt"] == "no stock"


@pytest.mark.asyncio
async def test_generate_aspect_ratio_override():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=_ok_response())
    client = ImagenClient(api_key="k", aspect_ratio="3:4", http_client=mock_client)

    await client.generate("p", aspect_ratio="16:9")
    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["parameters"]["aspectRatio"] == "16:9"

    await client.generate("p")
    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["parameters"]["aspectRatio"] == "3:4"


def test_constructor_rejects_unsupported_aspect_ratio():
    """Imagen 4.0 rejects 4:5 with HTTP 400. Fail fast client-side."""
    from backend.services.visual.imagen_client import ImagenError

    with pytest.raises(ImagenError, match="not supported by Imagen"):
        ImagenClient(api_key="k", aspect_ratio="4:5")


@pytest.mark.asyncio
async def test_generate_rejects_override_to_unsupported_aspect():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=_ok_response())
    client = ImagenClient(api_key="k", aspect_ratio="3:4", http_client=mock_client)

    result = await client.generate("p", aspect_ratio="4:5")
    assert result.ok is False
    assert "4:5" in (result.error or "")
    # Should NOT have made any HTTP call
    mock_client.post.assert_not_called()
