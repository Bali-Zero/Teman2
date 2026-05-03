"""Tests for XPublisher (mocked X API v2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest

from backend.services.publisher.base import (
    DraftPayload,
    PublisherError,
    SlidePayload,
)
from backend.services.publisher.x_publisher import (
    MAX_TWEET_CHARS,
    XPublisher,
    _build_thread,
    _truncate,
)


def _ok(id_: str) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = 201
    r.json.return_value = {"data": {"id": id_}}
    r.text = ""
    return r


def _err(status: int = 401, text: str = "bad") -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.text = text
    r.json.return_value = {}
    return r


def _draft(main_caption: str = "main", slides: int = 3) -> DraftPayload:
    return DraftPayload(
        draft_id=uuid4(),
        topic="t",
        tone_register=None,
        cover_image_url="https://x/c",
        main_caption=main_caption,
        slides=[
            SlidePayload(
                slide_number=i + 2,
                image_url=f"https://x/s{i}",
                final_text=f"thread body {i}",
            )
            for i in range(slides)
        ],
    )


# ── _truncate + _build_thread ─────────────────────────────────


def test_truncate_short_text_unchanged():
    assert _truncate("hello") == "hello"


def test_truncate_long_text_ellipsis():
    long = "x" * (MAX_TWEET_CHARS + 50)
    out = _truncate(long)
    assert len(out) <= MAX_TWEET_CHARS
    assert out.endswith("…")


def test_build_thread_includes_all_slides():
    d = _draft(slides=3)
    tweets = _build_thread(d)
    # 1 main + 3 slides = 4
    assert len(tweets) == 4


def test_build_thread_appends_link_if_present():
    d = _draft(slides=0)
    d.link_url = "https://balizero.com/kbli/51010?utm=warroom"
    tweets = _build_thread(d)
    assert any("balizero.com" in t for t in tweets)


def test_build_thread_skips_empty_slide_text():
    d = _draft(slides=3)
    d.slides[1].final_text = ""
    d.slides[1].caption = None
    tweets = _build_thread(d)
    # main + 2 non-empty
    assert len(tweets) == 3


# ── Config ────────────────────────────────────────────────────


def test_requires_bearer(monkeypatch):
    monkeypatch.delenv("X_BEARER_TOKEN", raising=False)
    with pytest.raises(PublisherError):
        XPublisher()


def test_bearer_from_env(monkeypatch):
    monkeypatch.setenv("X_BEARER_TOKEN", "env-bearer")
    x = XPublisher()
    assert x.bearer_token == "env-bearer"


# ── Validation ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_validate_requires_main_caption():
    x = XPublisher(bearer_token="t")
    d = _draft(main_caption="", slides=0)
    v = await x.validate(d)
    assert v.ok is False


@pytest.mark.asyncio
async def test_validate_too_long_thread():
    x = XPublisher(bearer_token="t")
    d = _draft(main_caption="ok", slides=30)
    v = await x.validate(d)
    assert v.ok is False


# ── Publish ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_chains_tweets():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=[_ok("100"), _ok("101"), _ok("102"), _ok("103")])
    x = XPublisher(bearer_token="t", http_client=client)
    result = await x.publish(_draft(slides=3))
    assert result.ok is True
    assert result.post_external_id == "100"
    assert result.post_url == "https://x.com/i/status/100"
    assert result.meta["thread_count"] == 4
    assert result.meta["all_ids"] == ["100", "101", "102", "103"]

    # verify first call has no reply, subsequent calls chain
    first_json = client.post.call_args_list[0].kwargs["json"]
    assert "reply" not in first_json
    second_json = client.post.call_args_list[1].kwargs["json"]
    assert second_json["reply"]["in_reply_to_tweet_id"] == "100"
    third_json = client.post.call_args_list[2].kwargs["json"]
    assert third_json["reply"]["in_reply_to_tweet_id"] == "101"


@pytest.mark.asyncio
async def test_publish_fails_if_first_tweet_fails():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_err(401, "unauthorized"))
    x = XPublisher(bearer_token="t", http_client=client)
    result = await x.publish(_draft(slides=2))
    assert result.ok is False
    assert "first tweet" in (result.error or "")


@pytest.mark.asyncio
async def test_publish_truncates_thread_on_mid_failure_but_ok():
    """Partial thread still counts as ok if the first tweet succeeded."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=[_ok("100"), _ok("101"), _err(429, "limit")])
    x = XPublisher(bearer_token="t", http_client=client)
    result = await x.publish(_draft(slides=2))
    assert result.ok is True
    assert result.meta["thread_count"] == 2
    assert result.post_external_id == "100"


@pytest.mark.asyncio
async def test_publish_exception_wrapped():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=httpx.ConnectError("down"))
    x = XPublisher(bearer_token="t", http_client=client)
    result = await x.publish(_draft(slides=2))
    assert result.ok is False
    assert "ConnectError" in (result.error or "")


# ── Delete ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_success():
    client = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    client.delete = AsyncMock(return_value=resp)
    x = XPublisher(bearer_token="t", http_client=client)
    assert await x.delete("tid") is True


@pytest.mark.asyncio
async def test_delete_returns_false_on_404():
    client = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 404
    client.delete = AsyncMock(return_value=resp)
    x = XPublisher(bearer_token="t", http_client=client)
    assert await x.delete("tid") is False
