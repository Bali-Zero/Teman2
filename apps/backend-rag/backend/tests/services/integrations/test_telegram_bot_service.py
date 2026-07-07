from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from backend.services.integrations import telegram_bot_service as telegram_module
from backend.services.integrations.telegram_bot_service import (
    TELEGRAM_API_BASE,
    TelegramBotService,
)


class FakeResponse:
    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        *,
        status_code: int = 200,
        content: bytes = b"payload",
    ) -> None:
        self._payload = payload or {"ok": True}
        self.status_code = status_code
        self.content = content

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://telegram.test")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("telegram error", request=request, response=response)


class FakeClient:
    def __init__(
        self,
        *,
        post_responses: list[FakeResponse] | None = None,
        get_responses: list[FakeResponse] | None = None,
    ) -> None:
        self.post_responses = post_responses or []
        self.get_responses = get_responses or []
        self.posts: list[dict[str, Any]] = []
        self.gets: list[dict[str, Any]] = []
        self.is_closed = False

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.posts.append({"url": url, **kwargs})
        if self.post_responses:
            return self.post_responses.pop(0)
        return FakeResponse({"ok": True, "result": {"message_id": 10}})

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.gets.append({"url": url, **kwargs})
        if self.get_responses:
            return self.get_responses.pop(0)
        return FakeResponse({"ok": True, "result": {"url": url}}, content=b"file-bytes")

    async def aclose(self) -> None:
        self.is_closed = True


def make_service(client: FakeClient | None = None) -> TelegramBotService:
    service = TelegramBotService.__new__(TelegramBotService)
    service._token = "telegram-token"
    service._client = client

    async def fake_get_client() -> FakeClient:
        if service._client is None:
            service._client = FakeClient()
        return service._client

    service._get_client = fake_get_client  # type: ignore[method-assign]
    return service


def test_token_and_api_url_use_instance_token() -> None:
    service = make_service()

    assert service.token == "telegram-token"
    assert service.api_url == f"{TELEGRAM_API_BASE}telegram-token"


@pytest.mark.asyncio
async def test_close_closes_open_client() -> None:
    client = FakeClient()
    service = make_service(client)

    await service.close()

    assert client.is_closed is True


@pytest.mark.asyncio
async def test_send_message_builds_payload_and_checks_ok() -> None:
    client = FakeClient()
    service = make_service(client)

    result = await service.send_message(
        chat_id=123,
        text="Hello",
        parse_mode="HTML",
        reply_to_message_id=99,
        reply_markup={"inline_keyboard": []},
    )

    assert result["ok"] is True
    assert client.posts[0]["url"] == f"{service.api_url}/sendMessage"
    assert client.posts[0]["json"] == {
        "chat_id": 123,
        "text": "Hello",
        "disable_web_page_preview": True,
        "parse_mode": "HTML",
        "reply_to_message_id": 99,
        "reply_markup": {"inline_keyboard": []},
    }


@pytest.mark.asyncio
async def test_send_message_raises_when_token_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(telegram_module, "settings", SimpleNamespace(telegram_bot_token=None))
    service = make_service()
    service._token = None

    with pytest.raises(ValueError, match="token not configured"):
        await service.send_message(chat_id=123, text="Hello")


@pytest.mark.asyncio
async def test_send_message_raises_on_telegram_error_payload() -> None:
    client = FakeClient(
        post_responses=[
            FakeResponse(
                {"ok": False, "error_code": 400, "description": "Bad request"},
            ),
        ],
    )
    service = make_service(client)

    with pytest.raises(ValueError, match=r"Telegram API error \[400\]"):
        await service.send_message(chat_id=123, text="Hello")


@pytest.mark.asyncio
async def test_send_photo_serializes_reply_markup() -> None:
    client = FakeClient()
    service = make_service(client)

    await service.send_photo(
        chat_id="chat-1",
        photo=b"jpeg",
        caption="Caption",
        reply_markup={"keyboard": [["ok"]]},
    )

    post = client.posts[0]
    assert post["url"] == f"{service.api_url}/sendPhoto"
    assert post["data"]["chat_id"] == "chat-1"
    assert post["data"]["caption"] == "Caption"
    assert post["data"]["reply_markup"] == '{"keyboard": [["ok"]]}'
    assert post["files"]["photo"] == ("photo.jpg", b"jpeg", "image/jpeg")


@pytest.mark.asyncio
async def test_send_chat_action_returns_false_when_token_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(telegram_module, "settings", SimpleNamespace(telegram_bot_token=None))
    service = make_service()
    service._token = None

    assert await service.send_chat_action(chat_id=123) is False


@pytest.mark.asyncio
async def test_webhook_and_bot_info_methods_use_expected_endpoints() -> None:
    client = FakeClient()
    service = make_service(client)

    await service.set_webhook(
        "https://example.com/hook",
        secret_token="secret",
        allowed_updates=["message"],
    )
    await service.delete_webhook()
    await service.get_webhook_info()
    await service.get_me()

    assert [call["url"] for call in client.posts] == [
        f"{service.api_url}/setWebhook",
        f"{service.api_url}/deleteWebhook",
    ]
    assert client.posts[0]["json"] == {
        "url": "https://example.com/hook",
        "secret_token": "secret",
        "allowed_updates": ["message"],
    }
    assert [call["url"] for call in client.gets] == [
        f"{service.api_url}/getWebhookInfo",
        f"{service.api_url}/getMe",
    ]


@pytest.mark.asyncio
async def test_callback_file_download_and_edit_methods() -> None:
    client = FakeClient(
        post_responses=[
            FakeResponse({"ok": True, "result": True}),
            FakeResponse({"ok": True, "result": {"file_path": "docs/file.pdf"}}),
            FakeResponse({"ok": True, "result": {"message_id": 7}}),
        ],
        get_responses=[FakeResponse({"ok": True}, content=b"pdf-bytes")],
    )
    service = make_service(client)

    callback = await service.answer_callback_query("callback-1", text="Done", show_alert=True)
    file_info = await service.get_file("file-1")
    content = await service.download_file("docs/file.pdf")
    edited = await service.edit_message_text(
        chat_id=123,
        message_id=7,
        text="Updated",
        parse_mode=None,
    )

    assert callback["result"] is True
    assert file_info == {"file_path": "docs/file.pdf"}
    assert content == b"pdf-bytes"
    assert edited["result"]["message_id"] == 7
    assert [call["url"] for call in client.posts] == [
        f"{service.api_url}/answerCallbackQuery",
        f"{service.api_url}/getFile",
        f"{service.api_url}/editMessageText",
    ]
    assert client.posts[2]["json"] == {
        "chat_id": 123,
        "message_id": 7,
        "text": "Updated",
    }
    assert client.gets[0]["url"] == (
        "https://api.telegram.org/file/bottelegram-token/docs/file.pdf"
    )
