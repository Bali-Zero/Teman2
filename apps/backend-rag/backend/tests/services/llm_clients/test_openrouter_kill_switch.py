"""OpenRouter kill-switch tests (COS-LAW-013, ratified 2026-07-11).

OpenRouter egress is OFF by default: client-channel content (WhatsApp/IG/
webchat messages) must never reach a third-party endpoint without Zero's
explicit authorization. The gate lives in OpenRouterClient.complete /
complete_stream — the single choke point every caller traverses.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.llm_clients.openrouter_client import (
    OpenRouterClient,
    OpenRouterDisabledError,
)

_SETTINGS_PATH = "backend.services.llm_clients.openrouter_client.settings"


def test_default_is_disabled_in_shipped_config():
    """The shipped default must be OFF — the PII boundary is opt-in to break.

    Tripwire on the source declaration itself: the conftest replaces both the
    settings singleton and the Settings class with fakes, so the only honest
    assertion in-suite is on what ships in config.py.
    """
    config_src = Path(__file__).parents[3] / "app" / "core" / "config.py"
    assert "openrouter_enabled: bool = False" in config_src.read_text()


@pytest.mark.asyncio
async def test_complete_blocked_when_disabled():
    """complete() raises BEFORE any egress, even with a valid API key."""
    client = OpenRouterClient(api_key="test-key")
    fake_http = AsyncMock()

    with patch(_SETTINGS_PATH) as mock_settings:
        mock_settings.openrouter_enabled = False
        with patch.object(client, "_get_client", return_value=fake_http):
            with pytest.raises(OpenRouterDisabledError):
                await client.complete(messages=[{"role": "user", "content": "hi"}])

    fake_http.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_stream_blocked_when_disabled():
    """complete_stream() raises on first iteration, before any egress."""
    client = OpenRouterClient(api_key="test-key")

    with patch(_SETTINGS_PATH) as mock_settings:
        mock_settings.openrouter_enabled = False
        stream = client.complete_stream(messages=[{"role": "user", "content": "hi"}])
        with pytest.raises(OpenRouterDisabledError):
            await stream.__anext__()


@pytest.mark.asyncio
async def test_check_credits_blocked_when_disabled():
    """OFF means OFF: even the billing probe must not exercise the key."""
    client = OpenRouterClient(api_key="test-key")
    fake_http = AsyncMock()

    with patch(_SETTINGS_PATH) as mock_settings:
        mock_settings.openrouter_enabled = False
        with patch.object(client, "_get_client", return_value=fake_http):
            result = await client.check_credits()

    assert "disabled" in result.get("error", "")
    fake_http.get.assert_not_awaited()


def test_provider_unavailable_when_disabled():
    """The provider registry must not advertise a gated egress as available."""
    from backend.llm.providers.openrouter import OpenRouterProvider

    provider = OpenRouterProvider.__new__(OpenRouterProvider)
    provider._available = True
    provider._client = MagicMock()

    with patch("backend.app.core.config.settings") as mock_settings:
        mock_settings.openrouter_enabled = False
        assert provider.is_available is False

    with patch("backend.app.core.config.settings") as mock_settings:
        mock_settings.openrouter_enabled = True
        assert provider.is_available is True


@pytest.mark.asyncio
async def test_complete_allowed_when_enabled():
    """Innocence check: with the flag explicitly ON the call goes through."""
    client = OpenRouterClient(api_key="test-key")
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "choices": [{"message": {"content": "ok"}}],
        "model": "test/model",
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    fake_resp.raise_for_status = MagicMock()
    fake_http = AsyncMock()
    fake_http.post = AsyncMock(return_value=fake_resp)

    with patch(_SETTINGS_PATH) as mock_settings:
        mock_settings.openrouter_enabled = True
        mock_settings.openrouter_api_key = "test-key"
        with patch.object(client, "_get_client", return_value=fake_http):
            result = await client.complete(messages=[{"role": "user", "content": "hi"}])

    assert result.content == "ok"
    fake_http.post.assert_awaited_once()
