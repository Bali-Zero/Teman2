import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
module_path = backend_path / "services" / "integrations" / "telegram_bot_service.py"
module_name = "services.integrations.telegram_bot_service"


class _FakeResponse:
    def __init__(self, json_data=None, status_code=200, error=None):
        self._json_data = json_data or {}
        self.status_code = status_code
        self._error = error

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self._error:
            raise self._error


def _load_module(monkeypatch, token="token", async_client=None):
    settings_stub = types.SimpleNamespace(telegram_bot_token=token)
    config_stub = types.SimpleNamespace(settings=settings_stub)
    monkeypatch.setitem(sys.modules, "app.core.config", config_stub)

    if async_client is None:
        async_client = AsyncMock()
        async_client.is_closed = False

    monkeypatch.setitem(sys.modules, "httpx", httpx)
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=30.0: async_client)

    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_client_lifecycle(monkeypatch):
    async_client = AsyncMock()
    async_client.is_closed = False
    module = _load_module(monkeypatch, token="token", async_client=async_client)
    service = module.TelegramBotService()

    client = await service._get_client()
    assert client is async_client

    async_client.is_closed = True
    new_client = AsyncMock()
    new_client.is_closed = False
    monkeypatch.setattr(httpx, "AsyncClient", lambda timeout=30.0: new_client)
    client2 = await service._get_client()
    assert client2 is new_client

    await service.close()
    new_client.aclose.assert_called_once()


def test_token_and_api_url(monkeypatch):
    module = _load_module(monkeypatch, token="abc123")
    service = module.TelegramBotService()

    assert service.token == "abc123"
    assert service.api_url.endswith("botabc123")


@pytest.mark.asyncio
async def test_send_message_success(monkeypatch):
    response = _FakeResponse(json_data={"ok": True})
    async_client = AsyncMock()
    async_client.is_closed = False
    async_client.post = AsyncMock(return_value=response)
    module = _load_module(monkeypatch, token="token", async_client=async_client)
    service = module.TelegramBotService()

    result = await service.send_message(1, "hello", reply_to_message_id=5)

    assert result["ok"] is True
    payload = async_client.post.call_args.kwargs["json"]
    assert payload["reply_to_message_id"] == 5
    assert payload["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_send_message_error_response(monkeypatch):
    response = _FakeResponse(json_data={"ok": False, "error_code": 400, "description": "bad"})
    async_client = AsyncMock()
    async_client.is_closed = False
    async_client.post = AsyncMock(return_value=response)
    module = _load_module(monkeypatch, token="token", async_client=async_client)
    service = module.TelegramBotService()

    with pytest.raises(ValueError, match="Telegram API error"):
        await service.send_message(1, "hello")


@pytest.mark.asyncio
async def test_send_message_http_error(monkeypatch):
    async_client = AsyncMock()
    async_client.is_closed = False
    async_client.post = AsyncMock(side_effect=httpx.HTTPError("fail"))
    module = _load_module(monkeypatch, token="token", async_client=async_client)
    service = module.TelegramBotService()

    with pytest.raises(httpx.HTTPError):
        await service.send_message(1, "hello")


@pytest.mark.asyncio
async def test_send_message_without_token(monkeypatch):
    module = _load_module(monkeypatch, token=None)
    service = module.TelegramBotService()

    with pytest.raises(ValueError, match="Telegram bot token not configured"):
        await service.send_message(1, "hello")


@pytest.mark.asyncio
async def test_send_chat_action(monkeypatch):
    response = _FakeResponse(status_code=200)
    async_client = AsyncMock()
    async_client.is_closed = False
    async_client.post = AsyncMock(return_value=response)
    module = _load_module(monkeypatch, token="token", async_client=async_client)
    service = module.TelegramBotService()

    assert await service.send_chat_action(1, "typing") is True

    response.status_code = 500
    assert await service.send_chat_action(1, "typing") is False

    async_client.post = AsyncMock(side_effect=Exception("fail"))
    assert await service.send_chat_action(1, "typing") is False


@pytest.mark.asyncio
async def test_send_chat_action_without_token(monkeypatch):
    module = _load_module(monkeypatch, token=None)
    service = module.TelegramBotService()

    assert await service.send_chat_action(1, "typing") is False


@pytest.mark.asyncio
async def test_set_webhook_success(monkeypatch):
    response = _FakeResponse(json_data={"ok": True})
    async_client = AsyncMock()
    async_client.is_closed = False
    async_client.post = AsyncMock(return_value=response)
    module = _load_module(monkeypatch, token="token", async_client=async_client)
    service = module.TelegramBotService()

    result = await service.set_webhook(
        "https://example.com/webhook",
        secret_token="secret",
        allowed_updates=["message"],
    )

    assert result["ok"] is True
    payload = async_client.post.call_args.kwargs["json"]
    assert payload["secret_token"] == "secret"
    assert payload["allowed_updates"] == ["message"]


@pytest.mark.asyncio
async def test_set_webhook_error(monkeypatch):
    response = _FakeResponse(error=httpx.HTTPError("bad"))
    async_client = AsyncMock()
    async_client.is_closed = False
    async_client.post = AsyncMock(return_value=response)
    module = _load_module(monkeypatch, token="token", async_client=async_client)
    service = module.TelegramBotService()

    with pytest.raises(httpx.HTTPError):
        await service.set_webhook("https://example.com/webhook")


@pytest.mark.asyncio
async def test_delete_webhook(monkeypatch):
    response = _FakeResponse(json_data={"ok": True})
    async_client = AsyncMock()
    async_client.is_closed = False
    async_client.post = AsyncMock(return_value=response)
    module = _load_module(monkeypatch, token="token", async_client=async_client)
    service = module.TelegramBotService()

    assert (await service.delete_webhook())["ok"] is True


@pytest.mark.asyncio
async def test_get_webhook_info(monkeypatch):
    response = _FakeResponse(json_data={"ok": True, "url": "u"})
    async_client = AsyncMock()
    async_client.is_closed = False
    async_client.get = AsyncMock(return_value=response)
    module = _load_module(monkeypatch, token="token", async_client=async_client)
    service = module.TelegramBotService()

    assert (await service.get_webhook_info())["url"] == "u"


@pytest.mark.asyncio
async def test_get_me(monkeypatch):
    response = _FakeResponse(json_data={"ok": True, "result": {"id": 1}})
    async_client = AsyncMock()
    async_client.is_closed = False
    async_client.get = AsyncMock(return_value=response)
    module = _load_module(monkeypatch, token="token", async_client=async_client)
    service = module.TelegramBotService()

    assert (await service.get_me())["result"]["id"] == 1


@pytest.mark.asyncio
async def test_answer_callback_query(monkeypatch):
    response = _FakeResponse(json_data={"ok": True})
    async_client = AsyncMock()
    async_client.is_closed = False
    async_client.post = AsyncMock(return_value=response)
    module = _load_module(monkeypatch, token="token", async_client=async_client)
    service = module.TelegramBotService()

    result = await service.answer_callback_query("cbq", text="ok", show_alert=True)

    assert result["ok"] is True
    payload = async_client.post.call_args.kwargs["json"]
    assert payload["text"] == "ok"
    assert payload["show_alert"] is True


@pytest.mark.asyncio
async def test_edit_message_text(monkeypatch):
    response = _FakeResponse(json_data={"ok": False, "error_code": 400, "description": "bad"})
    async_client = AsyncMock()
    async_client.is_closed = False
    async_client.post = AsyncMock(return_value=response)
    module = _load_module(monkeypatch, token="token", async_client=async_client)
    service = module.TelegramBotService()

    result = await service.edit_message_text(1, 2, "hi")

    assert result["ok"] is False
    payload = async_client.post.call_args.kwargs["json"]
    assert payload["parse_mode"] == "Markdown"
