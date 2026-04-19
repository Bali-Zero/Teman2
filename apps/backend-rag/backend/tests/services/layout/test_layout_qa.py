"""Tests for LayoutQAClient (mocked httpx)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from backend.services.layout.layout_qa import LayoutFlags, LayoutQAClient


def _ok_resp(flags: dict) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {"message": {"content": json.dumps(flags)}}
    return resp


@pytest.fixture
def png() -> bytes:
    return b"\x89PNG_fake"


# ── LayoutFlags.requires_patch ─────────────────────────────────────

def test_requires_patch_true_on_overflow():
    f = LayoutFlags(
        text_overflow=True,
        low_contrast_regions=[],
        element_overlap=False,
        logo_visible=True,
        logo_position_ok=True,
        readability_score_0_10=9,
    )
    assert f.requires_patch is True


def test_requires_patch_true_on_low_contrast():
    f = LayoutFlags(
        text_overflow=False,
        low_contrast_regions=["headline over lighter background"],
        element_overlap=False,
        logo_visible=True,
        logo_position_ok=True,
        readability_score_0_10=9,
    )
    assert f.requires_patch is True


def test_requires_patch_true_on_overlap():
    f = LayoutFlags(
        text_overflow=False,
        low_contrast_regions=[],
        element_overlap=True,
        logo_visible=True,
        logo_position_ok=True,
        readability_score_0_10=9,
    )
    assert f.requires_patch is True


def test_requires_patch_true_on_missing_logo():
    f = LayoutFlags(
        text_overflow=False,
        low_contrast_regions=[],
        element_overlap=False,
        logo_visible=False,
        logo_position_ok=True,
        readability_score_0_10=9,
    )
    assert f.requires_patch is True


def test_requires_patch_true_on_low_readability():
    f = LayoutFlags(
        text_overflow=False,
        low_contrast_regions=[],
        element_overlap=False,
        logo_visible=True,
        logo_position_ok=True,
        readability_score_0_10=3,
    )
    assert f.requires_patch is True


def test_requires_patch_false_on_clean():
    f = LayoutFlags(
        text_overflow=False,
        low_contrast_regions=[],
        element_overlap=False,
        logo_visible=True,
        logo_position_ok=True,
        readability_score_0_10=9,
    )
    assert f.requires_patch is False


# ── LayoutQAClient ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_layout_qa_parses_flags(png):
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=_ok_resp({
        "text_overflow": False,
        "low_contrast_regions": [],
        "element_overlap": False,
        "logo_visible": True,
        "logo_position_ok": True,
        "readability_score_0_10": 9,
    }))
    client = LayoutQAClient(http_client=mock_client)

    flags = await client.analyze(png)
    assert flags.ok is True
    assert flags.readability_score_0_10 == 9
    assert not flags.requires_patch


@pytest.mark.asyncio
async def test_layout_qa_detects_problems(png):
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=_ok_resp({
        "text_overflow": True,
        "low_contrast_regions": ["body paragraph"],
        "element_overlap": False,
        "logo_visible": True,
        "logo_position_ok": True,
        "readability_score_0_10": 5,
    }))
    client = LayoutQAClient(http_client=mock_client)

    flags = await client.analyze(png)
    assert flags.ok is True
    assert flags.requires_patch is True


@pytest.mark.asyncio
async def test_layout_qa_http_error(png):
    err = MagicMock(spec=httpx.Response)
    err.status_code = 500
    err.text = "boom"
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=err)
    client = LayoutQAClient(http_client=mock_client)

    flags = await client.analyze(png)
    assert flags.ok is False
    assert "500" in (flags.error or "")


@pytest.mark.asyncio
async def test_layout_qa_bad_json_handled(png):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {"message": {"content": "not json"}}
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=resp)
    client = LayoutQAClient(http_client=mock_client)

    flags = await client.analyze(png)
    assert flags.ok is False
    assert "json" in (flags.error or "").lower()


@pytest.mark.asyncio
async def test_layout_qa_connect_error(png):
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("nope"))
    client = LayoutQAClient(http_client=mock_client)

    flags = await client.analyze(png)
    assert flags.ok is False
    assert "unreachable" in (flags.error or "").lower()


@pytest.mark.asyncio
async def test_layout_qa_payload_shape(png):
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = AsyncMock(return_value=_ok_resp({
        "text_overflow": False,
        "low_contrast_regions": [],
        "element_overlap": False,
        "logo_visible": True,
        "logo_position_ok": True,
        "readability_score_0_10": 8,
    }))
    client = LayoutQAClient(http_client=mock_client)

    await client.analyze(png)
    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["think"] is False
    assert "images" in payload["messages"][0]
    assert "format" in payload
