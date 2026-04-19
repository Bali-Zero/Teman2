"""Tests: @llm_cost_tracked wraps ImagenClient.generate.

generate() catches all HTTP exceptions internally and returns ImagenResult(ok=False)
rather than raising. Therefore the decorator always sees success=True (no exception
escapes). These tests verify that record_llm_call is invoked with the correct
provider/model/tokens/cost on both the happy path and the internally-swallowed
exception path.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.visual.imagen_client import ImagenClient, ImagenQuality


def _ok_body() -> dict:
    import base64
    b64 = base64.b64encode(b"\x89PNG_x").decode("ascii")
    return {"predictions": [{"bytesBase64Encoded": b64, "mimeType": "image/png"}]}


@pytest.mark.asyncio
async def test_generate_records_cost_fast():
    """Happy path: decorator records correct provider/model/tokens/cost for FAST quality."""
    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=False):
        client = ImagenClient()

    fake_resp = MagicMock()
    fake_resp.json.return_value = _ok_body()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.status_code = 200

    fake_http = AsyncMock()
    fake_http.post = AsyncMock(return_value=fake_resp)
    client._client = fake_http

    with patch(
        "backend.services.observability.tracking_decorator.record_llm_call",
        new=AsyncMock(),
    ) as mock_rec:
        result = await client.generate(prompt="sunset bali", quality=ImagenQuality.FAST)

    assert result.ok is True
    mock_rec.assert_awaited_once()
    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "imagen"
    assert kwargs["model"] == "imagen-4.0-fast-generate-001"
    assert kwargs["input_tokens"] == 1
    assert kwargs["output_tokens"] == 0
    assert kwargs["cost_usd"] == 0.02
    assert kwargs["success"] is True


@pytest.mark.asyncio
async def test_generate_records_cost_ultra():
    """Happy path: ULTRA quality maps to correct model slug and cost=$0.06."""
    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=False):
        client = ImagenClient()

    fake_resp = MagicMock()
    fake_resp.json.return_value = _ok_body()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.status_code = 200

    fake_http = AsyncMock()
    fake_http.post = AsyncMock(return_value=fake_resp)
    client._client = fake_http

    with patch(
        "backend.services.observability.tracking_decorator.record_llm_call",
        new=AsyncMock(),
    ) as mock_rec:
        await client.generate(prompt="hero bali", quality=ImagenQuality.ULTRA)

    mock_rec.assert_awaited_once()
    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "imagen"
    assert kwargs["model"] == "imagen-4.0-ultra-generate-001"
    assert kwargs["input_tokens"] == 1
    assert kwargs["output_tokens"] == 0
    assert kwargs["cost_usd"] == 0.06
    assert kwargs["success"] is True


@pytest.mark.asyncio
async def test_generate_records_on_internal_failure():
    """Exception path: generate() swallows the exception and returns ImagenResult(ok=False).

    The decorator still fires (finally block) and records the call with the correct
    model slug (set before the HTTP call) and input_tokens=1 (set via set_usage before
    the HTTP call). success=True because no exception escaped generate().
    """
    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=False):
        client = ImagenClient()

    fake_http = AsyncMock()
    fake_http.post = AsyncMock(side_effect=RuntimeError("quota exceeded"))
    client._client = fake_http

    with patch(
        "backend.services.observability.tracking_decorator.record_llm_call",
        new=AsyncMock(),
    ) as mock_rec:
        result = await client.generate(prompt="x", quality=ImagenQuality.ULTRA)

    # generate() swallows the exception and returns ImagenResult(ok=False)
    assert result.ok is False
    assert "RuntimeError" in (result.error or "")

    # decorator still fires with correct model (set before the HTTP call)
    mock_rec.assert_awaited_once()
    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "imagen"
    assert kwargs["model"] == "imagen-4.0-ultra-generate-001"
    assert kwargs["input_tokens"] == 1
    assert kwargs["output_tokens"] == 0
    # success=True because generate() caught the exception and returned normally
    assert kwargs["success"] is True


@pytest.mark.asyncio
async def test_generate_records_cost_standard():
    """STANDARD quality maps to correct model slug and cost=$0.04."""
    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=False):
        client = ImagenClient()

    fake_resp = MagicMock()
    fake_resp.json.return_value = _ok_body()
    fake_resp.raise_for_status = MagicMock()
    fake_resp.status_code = 200

    fake_http = AsyncMock()
    fake_http.post = AsyncMock(return_value=fake_resp)
    client._client = fake_http

    with patch(
        "backend.services.observability.tracking_decorator.record_llm_call",
        new=AsyncMock(),
    ) as mock_rec:
        await client.generate(prompt="body slide", quality=ImagenQuality.STANDARD)

    mock_rec.assert_awaited_once()
    kwargs = mock_rec.await_args.kwargs
    assert kwargs["model"] == "imagen-4.0-generate-001"
    assert kwargs["cost_usd"] == 0.04
