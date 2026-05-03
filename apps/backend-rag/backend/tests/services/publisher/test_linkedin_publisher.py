"""Tests for LinkedInPublisher (mocked httpx)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest

from backend.services.publisher.base import (
    DraftPayload,
    PublisherError,
)
from backend.services.publisher.linkedin_publisher import (
    LINKEDIN_API_VERSION,
    LinkedInPublisher,
    _urn_to_url,
)


def _draft(caption: str = "LinkedIn caption") -> DraftPayload:
    return DraftPayload(
        draft_id=uuid4(),
        topic="Permenkumham 22/2023",
        tone_register=None,
        cover_image_url="https://tigris/cover.png",
        main_caption=caption,
        link_url="https://balizero.com/kbli/51010?utm=warroom",
    )


def _resp(
    *,
    status: int = 201,
    urn: str = "urn:li:share:7194",
    headers: dict | None = None,
    body: dict | None = None,
) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.headers = headers if headers is not None else {"x-restli-id": urn}
    r.json.return_value = body or {}
    r.text = str(body or {})
    return r


# ── Config ────────────────────────────────────────────────────────


def test_requires_token_and_urn(monkeypatch):
    monkeypatch.delenv("LINKEDIN_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("LINKEDIN_AUTHOR_URN", raising=False)
    with pytest.raises(PublisherError):
        LinkedInPublisher()


def test_invalid_urn_rejected():
    with pytest.raises(PublisherError):
        LinkedInPublisher(access_token="t", author_urn="not-a-urn")


def test_headers_include_linkedin_version():
    li = LinkedInPublisher(
        access_token="abc",
        author_urn="urn:li:person:123",
    )
    h = li._headers()
    assert h["Authorization"] == "Bearer abc"
    assert h["LinkedIn-Version"] == LINKEDIN_API_VERSION
    assert h["X-Restli-Protocol-Version"] == "2.0.0"


# ── Validation ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_validate_empty_caption_fails():
    li = LinkedInPublisher(access_token="t", author_urn="urn:li:person:1")
    d = _draft(caption="")
    v = await li.validate(d)
    assert v.ok is False


@pytest.mark.asyncio
async def test_validate_commentary_cap():
    li = LinkedInPublisher(access_token="t", author_urn="urn:li:person:1")
    d = _draft(caption="x" * 3500)
    v = await li.validate(d)
    assert v.ok is False
    assert any("3000" in i for i in v.issues)


# ── Publish ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_happy_path_via_header():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_resp(urn="urn:li:share:999"))
    li = LinkedInPublisher(
        access_token="abc",
        author_urn="urn:li:person:me",
        http_client=client,
    )
    result = await li.publish(_draft())
    assert result.ok is True
    assert result.post_external_id == "urn:li:share:999"
    assert "linkedin.com/feed/update" in (result.post_url or "")
    called_body = client.post.call_args.kwargs["json"]
    assert called_body["author"] == "urn:li:person:me"
    assert called_body["visibility"] == "PUBLIC"
    assert called_body["lifecycleState"] == "PUBLISHED"
    # link attachment included when link_url + cover present
    assert called_body["content"]["article"]["source"].startswith("https://balizero.com")


@pytest.mark.asyncio
async def test_publish_falls_back_to_body_id_if_no_header():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_resp(
        headers={},  # no x-restli-id
        body={"id": "urn:li:ugcPost:777"},
    ))
    li = LinkedInPublisher(
        access_token="t", author_urn="urn:li:person:1",
        http_client=client,
    )
    result = await li.publish(_draft())
    assert result.ok is True
    assert result.post_external_id == "urn:li:ugcPost:777"


@pytest.mark.asyncio
async def test_publish_missing_urn_fails():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_resp(headers={}, body={}))
    li = LinkedInPublisher(
        access_token="t", author_urn="urn:li:person:1",
        http_client=client,
    )
    result = await li.publish(_draft())
    assert result.ok is False
    assert "URN" in (result.error or "")


@pytest.mark.asyncio
async def test_publish_http_error():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_resp(status=401))
    li = LinkedInPublisher(
        access_token="t", author_urn="urn:li:person:1",
        http_client=client,
    )
    result = await li.publish(_draft())
    assert result.ok is False
    assert "401" in (result.error or "")


@pytest.mark.asyncio
async def test_publish_exception_wrapped():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=httpx.ConnectError("down"))
    li = LinkedInPublisher(
        access_token="t", author_urn="urn:li:person:1",
        http_client=client,
    )
    result = await li.publish(_draft())
    assert result.ok is False
    assert "ConnectError" in (result.error or "")


# ── Delete ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_success():
    client = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 204
    client.delete = AsyncMock(return_value=resp)
    li = LinkedInPublisher(
        access_token="t", author_urn="urn:li:person:1",
        http_client=client,
    )
    assert await li.delete("urn:li:share:1") is True


@pytest.mark.asyncio
async def test_delete_failure_returns_false():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.delete = AsyncMock(side_effect=httpx.ConnectError("down"))
    li = LinkedInPublisher(
        access_token="t", author_urn="urn:li:person:1",
        http_client=client,
    )
    assert await li.delete("urn:li:share:1") is False


# ── URL helper ────────────────────────────────────────────────────


def test_urn_to_url_percent_encodes_colons():
    url = _urn_to_url("urn:li:share:7194")
    # colons must be percent-encoded inside the path segment
    assert url is not None
    assert "urn%3Ali%3Ashare%3A7194" in url


def test_urn_to_url_returns_none_for_invalid():
    assert _urn_to_url("not-a-urn") is None
