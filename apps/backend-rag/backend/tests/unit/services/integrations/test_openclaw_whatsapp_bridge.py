"""Tests for the OpenClaw WhatsApp bridge client."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.services.integrations import openclaw_whatsapp_bridge as bridge


class _FakeAsyncClient:
    def __init__(self, response: MagicMock) -> None:
        self.response = response
        self.calls: list[dict] = []

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, json: dict, headers: dict) -> MagicMock:
        self.calls.append({"url": url, "json": json, "headers": headers})
        return self.response


@pytest.mark.asyncio
async def test_ask_openclaw_whatsapp_returns_reply(monkeypatch) -> None:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"reply": "Ciao, sono Zan da OpenClaw."}
    fake_client = _FakeAsyncClient(response)

    monkeypatch.setattr(bridge.settings, "whatsapp_openclaw_bridge_url", "https://bridge.test/reply/")
    monkeypatch.setattr(bridge.settings, "whatsapp_openclaw_bridge_secret", "secret")
    monkeypatch.setattr(bridge.settings, "openclaw_webhook_secret", None)
    monkeypatch.setattr(bridge.settings, "whatsapp_openclaw_agent", "wa")
    monkeypatch.setattr(bridge.settings, "whatsapp_openclaw_model", "openai/gpt-5.5")
    monkeypatch.setattr(bridge.settings, "whatsapp_openclaw_thinking", "high")
    monkeypatch.setattr(bridge.settings, "whatsapp_openclaw_persona", "zantara_whatsapp_v1")
    monkeypatch.setattr(
        bridge.settings,
        "whatsapp_openclaw_autonomy_mode",
        "supervised_autonomous",
    )
    monkeypatch.setattr(bridge.settings, "whatsapp_openclaw_timeout_seconds", 30.0)
    monkeypatch.setattr(bridge.httpx, "AsyncClient", lambda **_: fake_client)

    reply = await bridge.ask_openclaw_whatsapp(
        phone="628123",
        message_text="ciao",
        sender_name="Antonello",
        message_id="wamid.1",
        context={"detected_language": "it"},
    )

    assert reply == "Ciao, sono Zan da OpenClaw."
    assert fake_client.calls[0]["url"] == "https://bridge.test/reply"
    assert fake_client.calls[0]["json"]["agent"] == "wa"
    assert fake_client.calls[0]["json"]["channel"] == "whatsapp"
    assert fake_client.calls[0]["json"]["phone"] == "628123"
    assert fake_client.calls[0]["json"]["message_id"] == "wamid.1"
    assert fake_client.calls[0]["json"]["text"] == "ciao"
    assert fake_client.calls[0]["json"]["context"] == {"detected_language": "it"}
    assert fake_client.calls[0]["json"]["model"] == "openai/gpt-5.5"
    assert fake_client.calls[0]["json"]["thinking"] == "high"
    assert fake_client.calls[0]["json"]["persona"] == "zantara_whatsapp_v1"
    assert fake_client.calls[0]["json"]["autonomy_mode"] == "supervised_autonomous"
    assert fake_client.calls[0]["headers"]["Authorization"] == "Bearer secret"


@pytest.mark.asyncio
async def test_ask_openclaw_whatsapp_returns_none_when_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(bridge.settings, "whatsapp_openclaw_bridge_url", None)
    monkeypatch.setattr(bridge.settings, "whatsapp_openclaw_bridge_secret", "secret")

    reply = await bridge.ask_openclaw_whatsapp(
        phone="628123",
        message_text="ciao",
        sender_name=None,
        message_id="wamid.1",
    )

    assert reply is None
