"""Unit tests for backend.llm.deepseek_client — the TP1 gateway re-point.

DeepSeek's own direct-billing door (api.deepseek.com + DEEPSEEK_API_KEY) was
retired 2026-07-19. This module was re-pointed 2026-08-29 to the Alibaba TP1
gateway (BAILIAN_TOKEN_PLAN_API_KEY) for the same model family. These tests
guard the load-bearing parts of that re-point: the credential this module
reads, the default endpoint, the confirmed-live model slug, and the
reasoning_effort clamp TP1 requires ("max" -> "xhigh", HTTP 400 otherwise).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.llm import deepseek_client
from backend.llm.deepseek_client import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DeepSeekAuthError,
    complete_async,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BAILIAN_TOKEN_PLAN_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)


# ── Defaults point at the TP1 gateway, not the retired direct door ──────


def test_default_base_url_is_tp1_not_the_retired_direct_door() -> None:
    assert DEFAULT_BASE_URL == (
        "https://token-plan.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
    )
    assert "api.deepseek.com" not in DEFAULT_BASE_URL


def test_default_model_is_tp1s_confirmed_live_slug() -> None:
    """TP1 lists deepseek-v4-flash-0731, not the bare deepseek-v4-flash
    string DeepSeek's own docs use — the two are not interchangeable on
    this door (scripts/arsenal_probe.py::TP1_SEAT_MODELS)."""
    assert DEFAULT_MODEL == "deepseek-v4-flash-0731"


# ── Auth reads the TP1 credential, never falls back to the dead key ─────


@pytest.mark.asyncio
async def test_missing_bailian_key_raises_even_if_legacy_key_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The retired DEEPSEEK_API_KEY must never be treated as a valid
    credential again — even if it happens to still be set somewhere,
    this module must not read it."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "old-dead-key")

    with pytest.raises(DeepSeekAuthError, match="BAILIAN_TOKEN_PLAN_API_KEY"):
        await complete_async("hello")


@pytest.mark.asyncio
async def test_bailian_key_present_is_sent_as_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BAILIAN_TOKEN_PLAN_API_KEY", "tp1-secret")

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        "model": "deepseek-v4-flash-0731",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=fake_resp)
    monkeypatch.setattr(deepseek_client, "_get_client", lambda: mock_client)

    resp = await complete_async("hello")

    assert resp.text == "ok"
    mock_client.post.assert_awaited_once()
    call = mock_client.post.await_args
    assert call.args[0] == f"{DEFAULT_BASE_URL}/chat/completions"
    assert call.kwargs["headers"]["Authorization"] == "Bearer tp1-secret"


# ── reasoning_effort clamp: TP1 rejects "max" literally (HTTP 400) ──────


@pytest.mark.asyncio
async def test_reasoning_effort_max_is_clamped_to_xhigh_for_tp1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BAILIAN_TOKEN_PLAN_API_KEY", "tp1-secret")

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=fake_resp)
    monkeypatch.setattr(deepseek_client, "_get_client", lambda: mock_client)

    await complete_async("hello", reasoning_effort="max")

    sent_payload = mock_client.post.await_args.kwargs["json"]
    assert sent_payload["reasoning_effort"] == "xhigh"


@pytest.mark.asyncio
async def test_reasoning_effort_high_passes_through_unclamped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Innocence check: only "max" is remapped — "high"/"low" already match
    what TP1 accepts and must reach the API unchanged."""
    monkeypatch.setenv("BAILIAN_TOKEN_PLAN_API_KEY", "tp1-secret")

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=fake_resp)
    monkeypatch.setattr(deepseek_client, "_get_client", lambda: mock_client)

    await complete_async("hello", reasoning_effort="high")

    sent_payload = mock_client.post.await_args.kwargs["json"]
    assert sent_payload["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_401_error_names_tp1_and_bailian_key_not_deepseek_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BAILIAN_TOKEN_PLAN_API_KEY", "wrong-secret")

    fake_resp = MagicMock()
    fake_resp.status_code = 401
    fake_resp.text = "invalid token"
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=fake_resp)
    monkeypatch.setattr(deepseek_client, "_get_client", lambda: mock_client)

    with pytest.raises(DeepSeekAuthError, match="TP1"):
        await complete_async("hello")
