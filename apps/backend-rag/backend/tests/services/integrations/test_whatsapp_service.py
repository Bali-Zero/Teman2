from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from backend.services.integrations import whatsapp_service as whatsapp_module
from backend.services.integrations.whatsapp_service import WhatsAppService


class FakeResponse:
    def __init__(self, payload: dict[str, Any], *, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeClient:
    def __init__(self, responses: list[FakeResponse] | None = None) -> None:
        self.responses = responses or []
        self.posts: list[dict[str, Any]] = []
        self.is_closed = False

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.posts.append({"url": url, **kwargs})
        if self.responses:
            return self.responses.pop(0)
        return FakeResponse({"messages": [{"id": "wamid.1"}]})

    async def aclose(self) -> None:
        self.is_closed = True


def make_service(client: FakeClient | None = None) -> WhatsAppService:
    service = WhatsAppService.__new__(WhatsAppService)
    service._token = "wa-token"
    service._phone_number_id = "phone-id"
    service._client = client

    async def fake_get_client() -> FakeClient:
        if service._client is None:
            service._client = FakeClient()
        return service._client

    service._get_client = fake_get_client  # type: ignore[method-assign]
    return service


def test_properties_use_instance_configuration() -> None:
    service = make_service()

    assert service.token == "wa-token"
    assert service.phone_number_id == "phone-id"
    assert service.api_url == "https://graph.facebook.com/v22.0/phone-id"


@pytest.mark.asyncio
async def test_close_closes_open_client() -> None:
    client = FakeClient()
    service = make_service(client)

    await service.close()

    assert client.is_closed is True


@pytest.mark.asyncio
async def test_send_message_strips_plus_truncates_and_adds_reply_context() -> None:
    client = FakeClient()
    service = make_service(client)

    result = await service.send_message(
        "+6281234567890",
        "x" * 5000,
        reply_to_message_id="reply-1",
    )

    assert result["messages"][0]["id"] == "wamid.1"
    post = client.posts[0]
    assert post["url"] == f"{service.api_url}/messages"
    assert post["headers"] == {
        "Authorization": "Bearer wa-token",
        "Content-Type": "application/json",
    }
    assert post["json"]["to"] == "6281234567890"
    assert post["json"]["text"] == {"body": "x" * 4096}
    assert post["json"]["context"] == {"message_id": "reply-1"}


@pytest.mark.asyncio
async def test_send_message_requires_token_and_phone_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        whatsapp_module,
        "settings",
        SimpleNamespace(whatsapp_api_token=None, whatsapp_phone_number_id=None),
    )
    service = make_service()
    service._token = None
    service._phone_number_id = "phone-id"

    with pytest.raises(ValueError, match="token not configured"):
        await service.send_message("6281", "Hello")

    service._token = "wa-token"
    service._phone_number_id = None
    with pytest.raises(ValueError, match="phone number ID not configured"):
        await service.send_message("6281", "Hello")


@pytest.mark.asyncio
async def test_send_message_raises_on_meta_error_response() -> None:
    client = FakeClient(
        [
            FakeResponse(
                {"error": {"message": "Invalid recipient", "code": 131030}},
                status_code=400,
            ),
        ],
    )
    service = make_service(client)

    with pytest.raises(ValueError, match=r"WhatsApp API error \[131030\]"):
        await service.send_message("6281", "Hello")


@pytest.mark.asyncio
async def test_send_typing_action_is_noop_success() -> None:
    service = make_service()

    assert await service.send_typing_action("6281") is True


@pytest.mark.asyncio
async def test_mark_message_read_returns_false_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        whatsapp_module,
        "settings",
        SimpleNamespace(whatsapp_api_token=None, whatsapp_phone_number_id=None),
    )
    service = make_service()
    service._token = None

    assert await service.mark_message_read("wamid.1") is False


@pytest.mark.asyncio
async def test_mark_message_read_posts_read_status() -> None:
    client = FakeClient()
    service = make_service(client)

    assert await service.mark_message_read("wamid.1") is True
    assert client.posts[0]["url"] == f"{service.api_url}/messages"
    assert client.posts[0]["json"] == {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": "wamid.1",
    }


def test_format_message_passes_text_through() -> None:
    service = make_service()

    assert service.format_message("*bold* _italic_") == "*bold* _italic_"


def test_chunk_message_prefers_paragraph_boundaries() -> None:
    service = make_service()

    chunks = service.chunk_message("A" * 10 + "\n\n" + "B" * 10, max_length=15)

    assert chunks == ["A" * 10, "B" * 10]


def test_chunk_message_splits_long_paragraph_by_lines() -> None:
    service = make_service()

    chunks = service.chunk_message("A" * 8 + "\n" + "B" * 8 + "\n" + "C" * 8, max_length=10)

    assert chunks == ["A" * 8, "B" * 8, "C" * 8]
