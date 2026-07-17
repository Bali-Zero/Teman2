"""
alert_wiring.py — production adapter tests.

Covers the actual defect this module fixes: AlertDispatcher's
``telegram_service.send_message(chat="owner"/"team", text=...)`` calls never
resolved to a real Telegram chat id, and (deeper) the real
``TelegramBotService.send_message`` uses a different parameter name
(``chat_id``, not ``chat``) — so even a correctly-aliased send would have
raised ``TypeError`` before this adapter existed.

No real network, no real DB: every underlying service is a mock/fake. Per
W96 discipline, tests must never touch prod notification surfaces — the
Telegram/WhatsApp/email singletons are never used un-mocked here.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.compliance.alert_dispatcher import AlertDispatcher
from backend.services.compliance.alert_wiring import (
    HttpEmailServiceAdapter,
    LoggingInAppAdapter,
    PricingToolAdapter,
    TelegramAliasAdapter,
    WhatsAppServiceAdapter,
    build_alerts_engine,
)
from backend.services.compliance.alerts_engine import AlertsEngine

# ---------------------------------------------------------------------------
# TelegramAliasAdapter — the chat_id fix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_owner_alias_resolves_to_real_chat_id_from_env(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    monkeypatch.delenv("TELEGRAM_TEAM_CHAT_ID", raising=False)
    fake_bot = AsyncMock()
    adapter = TelegramAliasAdapter(bot=fake_bot)

    await adapter.send_message(chat="owner", text="hello")

    fake_bot.send_message.assert_awaited_once_with(chat_id="1125336968", text="hello")


@pytest.mark.asyncio
async def test_owner_alias_raises_when_env_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_OWNER_CHAT_ID", raising=False)
    fake_bot = AsyncMock()
    adapter = TelegramAliasAdapter(bot=fake_bot)

    with pytest.raises(ValueError, match="TELEGRAM_OWNER_CHAT_ID"):
        await adapter.send_message(chat="owner", text="hello")

    fake_bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_team_alias_falls_back_to_owner_when_team_env_unset(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    monkeypatch.delenv("TELEGRAM_TEAM_CHAT_ID", raising=False)
    fake_bot = AsyncMock()
    adapter = TelegramAliasAdapter(bot=fake_bot)

    await adapter.send_message(chat="team", text="urgent renewal")

    # No dedicated team chat configured -> falls back to the owner chat,
    # never silently dropped.
    fake_bot.send_message.assert_awaited_once_with(chat_id="1125336968", text="urgent renewal")


@pytest.mark.asyncio
async def test_team_alias_uses_dedicated_env_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    monkeypatch.setenv("TELEGRAM_TEAM_CHAT_ID", "-100987654321")
    fake_bot = AsyncMock()
    adapter = TelegramAliasAdapter(bot=fake_bot)

    await adapter.send_message(chat="team", text="urgent renewal")

    fake_bot.send_message.assert_awaited_once_with(chat_id="-100987654321", text="urgent renewal")


@pytest.mark.asyncio
async def test_team_alias_raises_when_nothing_configured(monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_OWNER_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_TEAM_CHAT_ID", raising=False)
    fake_bot = AsyncMock()
    adapter = TelegramAliasAdapter(bot=fake_bot)

    with pytest.raises(ValueError, match="TELEGRAM_TEAM_CHAT_ID"):
        await adapter.send_message(chat="team", text="urgent renewal")


@pytest.mark.asyncio
async def test_literal_chat_id_passes_through_unresolved(monkeypatch) -> None:
    # Aliases are the only special-cased values; anything else (a real
    # numeric id passed directly) must be forwarded untouched.
    monkeypatch.delenv("TELEGRAM_OWNER_CHAT_ID", raising=False)
    fake_bot = AsyncMock()
    adapter = TelegramAliasAdapter(bot=fake_bot)

    await adapter.send_message(chat=555111222, text="direct")

    fake_bot.send_message.assert_awaited_once_with(chat_id=555111222, text="direct")


# ---------------------------------------------------------------------------
# PricingToolAdapter
# ---------------------------------------------------------------------------


def test_pricing_adapter_none_key_returns_none_without_lookup() -> None:
    pricing_service = MagicMock()
    adapter = PricingToolAdapter(pricing_service)

    assert adapter.get_price(None) is None
    pricing_service.get_pricing.assert_not_called()


def test_pricing_adapter_delegates_to_revenue_estimator_scan() -> None:
    pricing_service = MagicMock()
    pricing_service.get_pricing.return_value = {
        "services": {
            "single_entry_visas": {
                "C1 Tourism Extension": {"price": "1.500.000 IDR"},
            },
        },
    }
    adapter = PricingToolAdapter(pricing_service)

    assert adapter.get_price("C1 Tourism Extension") == 1_500_000
    pricing_service.get_pricing.assert_called_once_with("all")


def test_pricing_adapter_missing_key_returns_none() -> None:
    pricing_service = MagicMock()
    pricing_service.get_pricing.return_value = {"services": {}}
    adapter = PricingToolAdapter(pricing_service)

    assert adapter.get_price("Nonexistent Service") is None


# ---------------------------------------------------------------------------
# HttpEmailServiceAdapter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_email_adapter_posts_to_internal_endpoint_with_api_key(monkeypatch) -> None:
    monkeypatch.setenv("NUZANTARA_API_KEY", "test-internal-key")

    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock(return_value=None)
    fake_response.json = MagicMock(return_value={"ok": True})

    fake_client = AsyncMock()
    fake_client.post = AsyncMock(return_value=fake_response)

    async def _fake_get_email_client() -> Any:
        return fake_client

    monkeypatch.setattr(
        "backend.services.compliance.alert_wiring.get_email_client",
        _fake_get_email_client,
    )

    adapter = HttpEmailServiceAdapter()
    result = await adapter.send(
        from_="zantara@balizero.com",
        to="client@example.com",
        subject="Test",
        body="<p>hi</p>",
    )

    assert result == {"ok": True}
    fake_client.post.assert_awaited_once()
    call = fake_client.post.await_args
    assert call.kwargs["headers"]["X-API-Key"] == "test-internal-key"
    assert call.kwargs["json"]["to"] == "client@example.com"
    assert call.kwargs["json"]["from"] == "zantara@balizero.com"


# ---------------------------------------------------------------------------
# WhatsAppServiceAdapter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wa_adapter_maps_to_underscore_send_message() -> None:
    fake_wa = AsyncMock()
    fake_wa.send_message = AsyncMock(return_value={"ok": True})
    adapter = WhatsAppServiceAdapter(wa=fake_wa)

    result = await adapter.send(to="628123456789", body="hi there")

    assert result == {"ok": True}
    fake_wa.send_message.assert_awaited_once_with(phone="628123456789", text="hi there")


# ---------------------------------------------------------------------------
# LoggingInAppAdapter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inapp_adapter_never_raises(caplog) -> None:
    import logging

    adapter = LoggingInAppAdapter()
    with caplog.at_level(logging.INFO, logger="backend.services.compliance.alert_wiring"):
        await adapter.emit(user_id="00000000-0000-0000-0000-0000000000aa", payload={"type": "x"})
    assert "compliance alert" in caplog.text.lower()


# ---------------------------------------------------------------------------
# build_alerts_engine — end-to-end wiring shape (no real DB/network)
# ---------------------------------------------------------------------------


def test_build_alerts_engine_wires_real_adapters() -> None:
    fake_pool = MagicMock()
    pricing_service = MagicMock()

    engine = build_alerts_engine(fake_pool, pricing_service=pricing_service)

    assert isinstance(engine, AlertsEngine)
    dispatcher = engine._dispatcher  # noqa: SLF001 — whitebox wiring assertion
    assert isinstance(dispatcher, AlertDispatcher)
    assert isinstance(dispatcher._telegram, TelegramAliasAdapter)  # noqa: SLF001
    assert isinstance(engine._pricing, PricingToolAdapter)  # noqa: SLF001
