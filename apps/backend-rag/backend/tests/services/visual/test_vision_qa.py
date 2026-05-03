"""Unit tests for OllamaVisionClient + VisionFlags (mocked httpx)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from backend.services.visual.vision_qa import (
    BANNED_ELEMENTS,
    VISION_MODEL_DEFAULT,
    OllamaVisionClient,
    VisionFlags,
)


def _ok_response(flags: dict) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {
        "message": {"content": json.dumps(flags)},
    }
    return resp


@pytest.fixture
def fake_image() -> bytes:
    return b"\x89PNG_fake_image_bytes"


# ── VisionFlags helpers ──────────────────────────────────────────────

def test_rejects_any_when_fails_brief():
    f = VisionFlags(
        matches_brief=False,
        has_banned_elements=[],
        brand_fit_score_0_10=9,
        text_area_available_ratio=0.8,
        readability_issues=[],
    )
    assert f.rejects_any is True


def test_rejects_any_when_banned_element_present():
    f = VisionFlags(
        matches_brief=True,
        has_banned_elements=["mani_deformi"],
        brand_fit_score_0_10=9,
        text_area_available_ratio=0.8,
        readability_issues=[],
    )
    assert f.rejects_any is True


def test_rejects_any_when_brand_fit_low():
    f = VisionFlags(
        matches_brief=True,
        has_banned_elements=[],
        brand_fit_score_0_10=3,
        text_area_available_ratio=0.8,
        readability_issues=[],
    )
    assert f.rejects_any is True


def test_does_not_reject_when_all_green():
    f = VisionFlags(
        matches_brief=True,
        has_banned_elements=[],
        brand_fit_score_0_10=9,
        text_area_available_ratio=0.6,
        readability_issues=[],
    )
    assert f.rejects_any is False


def test_banned_elements_covers_brand_json_list():
    assert "strette_di_mano" in BANNED_ELEMENTS
    assert "passaporti_generici" in BANNED_ELEMENTS
    assert "mani_deformi" in BANNED_ELEMENTS


# ── OllamaVisionClient ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_vision_client_parses_json_flags(fake_image):
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=_ok_response({
        "matches_brief": True,
        "has_banned_elements": [],
        "brand_fit_score_0_10": 8,
        "text_area_available_ratio": 0.55,
        "readability_issues": [],
    }))
    client = OllamaVisionClient(http_client=mock_client)

    flags = await client.analyze(fake_image, brief="editorial visa scene")
    assert flags.ok is True
    assert flags.matches_brief is True
    assert flags.brand_fit_score_0_10 == 8
    assert flags.text_area_available_ratio == pytest.approx(0.55)

    posted = mock_client.post.call_args
    payload = posted.kwargs["json"]
    assert payload["model"] == VISION_MODEL_DEFAULT
    assert payload["think"] is False
    assert "images" in payload["messages"][0]
    # format schema must be pushed so Ollama enforces structure
    assert "format" in payload


@pytest.mark.asyncio
async def test_vision_client_handles_http_error(fake_image):
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    err = MagicMock(spec=httpx.Response)
    err.status_code = 500
    err.text = "boom"
    mock_client.post = AsyncMock(return_value=err)
    client = OllamaVisionClient(http_client=mock_client)

    flags = await client.analyze(fake_image, brief="x")
    assert flags.ok is False
    assert "500" in (flags.error or "")


@pytest.mark.asyncio
async def test_vision_client_handles_bad_json(fake_image):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {"message": {"content": "not json at all"}}
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=resp)
    client = OllamaVisionClient(http_client=mock_client)

    flags = await client.analyze(fake_image, brief="x")
    assert flags.ok is False
    assert "json" in (flags.error or "").lower()


@pytest.mark.asyncio
async def test_vision_client_ollama_unreachable(fake_image):
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(
        side_effect=httpx.ConnectError("conn refused"),
    )
    client = OllamaVisionClient(http_client=mock_client)

    flags = await client.analyze(fake_image, brief="x")
    assert flags.ok is False
    assert "ollama unreachable" in (flags.error or "").lower()


@pytest.mark.asyncio
async def test_vision_client_timeout(fake_image):
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("slow"))
    client = OllamaVisionClient(http_client=mock_client, timeout=5.0)

    flags = await client.analyze(fake_image, brief="x")
    assert flags.ok is False
    assert "timeout" in (flags.error or "").lower()
