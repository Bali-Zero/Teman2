"""Tests for IGPublisher (mocked Meta Graph API)."""

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
from backend.services.publisher.ig_publisher import IGPublisher
from backend.services.war_room.models import Platform


def _draft(slides: int = 5) -> DraftPayload:
    return DraftPayload(
        draft_id=uuid4(),
        topic="B211A extension",
        tone_register=None,
        cover_image_url="https://tigris/cover.png",
        main_caption="Caption for B211A",
        slides=[
            SlidePayload(
                slide_number=i + 2,
                image_url=f"https://tigris/s{i}.png",
            )
            for i in range(slides)
        ],
    )


def _ok_resp(payload: dict, status: int = 200) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.json.return_value = payload
    r.text = str(payload)
    return r


def _err_resp(status: int = 400, text: str = "error") -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.text = text
    r.json.return_value = {"error": {"message": text}}
    return r


# ── Config ──────────────────────────────────────────────────────


def test_requires_ig_user_id_and_token(monkeypatch):
    for k in (
        "IG_USER_ID",
        "IG_LONG_LIVED_TOKEN",
        "INSTAGRAM_ACCOUNT_ID",
        "INSTAGRAM_ACCESS_TOKEN",
    ):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(PublisherError):
        IGPublisher()


def test_pulls_env(monkeypatch):
    for k in ("INSTAGRAM_ACCOUNT_ID", "INSTAGRAM_ACCESS_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("IG_USER_ID", "99999")
    monkeypatch.setenv("IG_LONG_LIVED_TOKEN", "EAABsomething")
    ig = IGPublisher()
    assert ig.ig_user_id == "99999"
    assert ig.access_token == "EAABsomething"


def test_instagram_env_fallback(monkeypatch):
    """IG_* vars take precedence but INSTAGRAM_* vars are accepted as fallback.

    Platform secrets on Fly use the INSTAGRAM_* naming (shared with the
    existing channels/instagram flow). War Room publisher reads both.
    """
    monkeypatch.delenv("IG_USER_ID", raising=False)
    monkeypatch.delenv("IG_LONG_LIVED_TOKEN", raising=False)
    monkeypatch.setenv("INSTAGRAM_ACCOUNT_ID", "77777")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "EAABfallback")
    ig = IGPublisher()
    assert ig.ig_user_id == "77777"
    assert ig.access_token == "EAABfallback"


def test_ig_vars_win_over_instagram_fallback(monkeypatch):
    monkeypatch.setenv("IG_USER_ID", "primary")
    monkeypatch.setenv("IG_LONG_LIVED_TOKEN", "primary_tok")
    monkeypatch.setenv("INSTAGRAM_ACCOUNT_ID", "fallback")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "fallback_tok")
    ig = IGPublisher()
    assert ig.ig_user_id == "primary"
    assert ig.access_token == "primary_tok"


# ── Validation ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_validate_fails_without_cover():
    ig = IGPublisher(ig_user_id="1", access_token="t")
    d = _draft(slides=2)
    d.cover_image_url = ""
    v = await ig.validate(d)
    assert v.ok is False
    assert any("cover" in i.lower() for i in v.issues)


@pytest.mark.asyncio
async def test_validate_fails_when_carousel_too_big():
    ig = IGPublisher(ig_user_id="1", access_token="t")
    d = _draft(slides=15)  # cover + 15 = 16 > 10
    v = await ig.validate(d)
    assert v.ok is False
    assert any("10" in i for i in v.issues)


@pytest.mark.asyncio
async def test_validate_fails_on_long_caption():
    ig = IGPublisher(ig_user_id="1", access_token="t")
    d = _draft(slides=2)
    d.main_caption = "x" * 2500
    v = await ig.validate(d)
    assert v.ok is False
    assert any("2200" in i for i in v.issues)


@pytest.mark.asyncio
async def test_validate_ok_on_typical_carousel():
    ig = IGPublisher(ig_user_id="1", access_token="t")
    d = _draft(slides=5)
    v = await ig.validate(d)
    assert v.ok is True


# ── Publish flow ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_happy_path_six_slide_carousel():
    # 1 cover + 5 body = 6 child containers + 1 parent + 1 publish + 1 permalink
    client = AsyncMock(spec=httpx.AsyncClient)
    # children: 6 POSTs returning ids 100..105
    children_posts = [_ok_resp({"id": f"10{i}"}) for i in range(6)]
    # parent POST returns id 999
    parent_post = _ok_resp({"id": "999"})
    # publish POST returns id 555
    publish_post = _ok_resp({"id": "555"})
    client.post = AsyncMock(
        side_effect=[*children_posts, parent_post, publish_post],
    )
    client.get = AsyncMock(
        return_value=_ok_resp({"permalink": "https://instagram.com/p/abc/"}),
    )

    ig = IGPublisher(
        ig_user_id="99999",
        access_token="tok",
        http_client=client,
    )
    draft = _draft(slides=5)
    result = await ig.publish(draft)

    assert result.ok is True
    assert result.platform == Platform.INSTAGRAM
    assert result.post_external_id == "555"
    assert result.post_url == "https://instagram.com/p/abc/"
    assert result.meta["carousel_items"] == 6
    assert result.meta["parent_id"] == "999"
    # 6 children + 1 parent + 1 publish = 8 POST calls
    assert client.post.call_count == 8


@pytest.mark.asyncio
async def test_publish_fails_if_child_container_fails():
    client = AsyncMock(spec=httpx.AsyncClient)
    # first child OK, second child fails
    client.post = AsyncMock(
        side_effect=[_ok_resp({"id": "100"}), _err_resp(400, "bad image url")],
    )
    ig = IGPublisher(ig_user_id="1", access_token="t", http_client=client)
    result = await ig.publish(_draft(slides=5))
    assert result.ok is False
    assert "create_child" in (result.error or "")


@pytest.mark.asyncio
async def test_publish_fails_if_parent_container_fails():
    client = AsyncMock(spec=httpx.AsyncClient)
    children = [_ok_resp({"id": f"c{i}"}) for i in range(6)]
    parent_err = _err_resp(400, "parent bad")
    client.post = AsyncMock(side_effect=[*children, parent_err])
    ig = IGPublisher(ig_user_id="1", access_token="t", http_client=client)
    result = await ig.publish(_draft(slides=5))
    assert result.ok is False
    assert "create_parent" in (result.error or "")


@pytest.mark.asyncio
async def test_publish_fails_if_media_publish_fails():
    client = AsyncMock(spec=httpx.AsyncClient)
    children = [_ok_resp({"id": f"c{i}"}) for i in range(6)]
    parent = _ok_resp({"id": "parent"})
    publish_err = _err_resp(500, "publish fail")
    client.post = AsyncMock(side_effect=[*children, parent, publish_err])
    ig = IGPublisher(ig_user_id="1", access_token="t", http_client=client)
    result = await ig.publish(_draft(slides=5))
    assert result.ok is False
    assert "media_publish" in (result.error or "")


@pytest.mark.asyncio
async def test_publish_tolerates_missing_permalink():
    """If permalink GET fails, post is still considered OK."""
    client = AsyncMock(spec=httpx.AsyncClient)
    children = [_ok_resp({"id": f"c{i}"}) for i in range(6)]
    parent = _ok_resp({"id": "parent"})
    publish = _ok_resp({"id": "final"})
    client.post = AsyncMock(side_effect=[*children, parent, publish])
    client.get = AsyncMock(return_value=_err_resp(404, "not found"))

    ig = IGPublisher(ig_user_id="1", access_token="t", http_client=client)
    result = await ig.publish(_draft(slides=5))
    assert result.ok is True
    assert result.post_external_id == "final"
    assert result.post_url is None


# ── Delete ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_success():
    client = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    client.delete = AsyncMock(return_value=resp)
    ig = IGPublisher(ig_user_id="1", access_token="t", http_client=client)
    assert await ig.delete("media-id") is True


@pytest.mark.asyncio
async def test_delete_failure_returns_false():
    client = AsyncMock(spec=httpx.AsyncClient)
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 404
    client.delete = AsyncMock(return_value=resp)
    ig = IGPublisher(ig_user_id="1", access_token="t", http_client=client)
    assert await ig.delete("media-id") is False


@pytest.mark.asyncio
async def test_delete_exception_returns_false():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.delete = AsyncMock(side_effect=httpx.ConnectError("nope"))
    ig = IGPublisher(ig_user_id="1", access_token="t", http_client=client)
    assert await ig.delete("media-id") is False
