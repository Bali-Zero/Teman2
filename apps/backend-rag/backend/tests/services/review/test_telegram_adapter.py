"""Tests for TelegramReviewAdapter (mocked httpx)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from backend.services.review.telegram_adapter import TelegramReviewAdapter


def _tg_ok(message_id: int = 111) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {"ok": True, "result": {"message_id": message_id}}
    return resp


def _tg_err(description: str = "bad request", status: int = 400) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.json.return_value = {
        "ok": False,
        "error_code": status,
        "description": description,
    }
    return resp


def test_adapter_requires_bot_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(ValueError):
        TelegramReviewAdapter(bot_token="")


def test_adapter_picks_up_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token-xyz")
    a = TelegramReviewAdapter()
    assert a.bot_token == "env-token-xyz"
    assert a.api_url.endswith("env-token-xyz")


@pytest.mark.asyncio
async def test_send_photo_url_sends_expected_payload():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_tg_ok(42))
    a = TelegramReviewAdapter(bot_token="t", http_client=client)

    result = await a.send_photo_url(
        chat_id=1125336968,
        photo_url="https://tigris/cover.png",
        caption="Test caption",
        reply_markup={"inline_keyboard": [[{"text": "x", "callback_data": "y"}]]},
    )
    assert result.ok is True
    assert result.message_id == 42
    called_url = client.post.call_args.args[0]
    payload = client.post.call_args.kwargs["data"]
    assert called_url.endswith("/sendPhoto")
    assert payload["chat_id"] == "1125336968"
    assert payload["photo"] == "https://tigris/cover.png"
    assert payload["caption"] == "Test caption"
    assert payload["parse_mode"] == "HTML"
    # reply_markup is sent as JSON string
    rm = json.loads(payload["reply_markup"])
    assert rm["inline_keyboard"][0][0]["text"] == "x"


@pytest.mark.asyncio
async def test_send_message_basic():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_tg_ok())
    a = TelegramReviewAdapter(bot_token="t", http_client=client)

    result = await a.send_message(chat_id=1, text="<b>hi</b>")
    assert result.ok is True
    payload = client.post.call_args.kwargs["data"]
    assert payload["text"] == "<b>hi</b>"
    assert payload["parse_mode"] == "HTML"


@pytest.mark.asyncio
async def test_answer_callback_query_trims_long_text():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_tg_ok())
    a = TelegramReviewAdapter(bot_token="t", http_client=client)
    long_text = "x" * 500

    await a.answer_callback_query(callback_query_id="abc", text=long_text)
    payload = client.post.call_args.kwargs["data"]
    assert len(payload["text"]) == 200  # trimmed


@pytest.mark.asyncio
async def test_edit_message_reply_markup_null_clears():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_tg_ok())
    a = TelegramReviewAdapter(bot_token="t", http_client=client)

    await a.edit_message_reply_markup(
        chat_id=1, message_id=42, reply_markup=None,
    )
    payload = client.post.call_args.kwargs["data"]
    rm = json.loads(payload["reply_markup"])
    assert rm == {"inline_keyboard": []}


@pytest.mark.asyncio
async def test_non_ok_response_surfaces_description():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=_tg_err("chat not found"))
    a = TelegramReviewAdapter(bot_token="t", http_client=client)

    result = await a.send_message(chat_id=1, text="x")
    assert result.ok is False
    assert "chat not found" in (result.error or "")


@pytest.mark.asyncio
async def test_exception_wraps_cleanly():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
    a = TelegramReviewAdapter(bot_token="t", http_client=client)

    result = await a.send_message(chat_id=1, text="x")
    assert result.ok is False
    assert "ConnectError" in (result.error or "")
