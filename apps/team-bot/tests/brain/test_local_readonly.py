"""Tests for team_bot.brain.local_readonly.LocalReadOnlyClient — the R0-only
structural guarantee and the always-`degraded=True` contract."""

from __future__ import annotations

import json

import httpx
import pytest

from team_bot.brain.errors import BrainErrorClass
from team_bot.brain.local_readonly import (
    DEGRADED_REASON,
    LocalReadOnlyClient,
    r0_tools_as_openai_schema,
)
from team_bot.brain.tp1_client import BrainCallError
from team_bot.registry import RiskTier

_SUCCESS_BODY = json.dumps(
    {
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "the practice is active"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "total_tokens": 20, "completion_tokens": 10},
    }
)


def _client_with(handler) -> LocalReadOnlyClient:
    return LocalReadOnlyClient(
        base_url="http://127.0.0.1:11434/v1",
        model="qwen3-14b-duebot",
        transport=httpx.MockTransport(handler),
    )


def test_requires_explicit_base_url_and_model() -> None:
    with pytest.raises(ValueError):
        LocalReadOnlyClient(base_url="", model="x")
    with pytest.raises(ValueError):
        LocalReadOnlyClient(base_url="http://127.0.0.1:11434/v1", model="")


def test_r0_tools_schema_contains_only_read_tools() -> None:
    from team_bot.registry import TOOL_REGISTRY

    schema = r0_tools_as_openai_schema()
    schema_names = {entry["function"]["name"] for entry in schema}
    r0_names = {spec.name for spec in TOOL_REGISTRY if spec.risk_tier == RiskTier.R0}
    r1_plus_names = {spec.name for spec in TOOL_REGISTRY if spec.risk_tier != RiskTier.R0}

    assert schema_names == r0_names
    assert schema_names.isdisjoint(r1_plus_names)
    assert len(schema) > 0


@pytest.mark.asyncio
async def test_chat_completion_takes_no_tools_argument_always_r0_only() -> None:
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, text=_SUCCESS_BODY)

    async with _client_with(handler) as client:
        # No `tools=` kwarg exists on this method at all (see signature) —
        # this call itself is the structural proof; if a caller could pass
        # arbitrary tools this test would need to assert against them.
        result = await client.chat_completion(
            messages=[{"role": "user", "content": "status of PR-1234?"}], max_tokens=50
        )

    sent_tool_names = {t["function"]["name"] for t in captured["body"]["tools"]}
    from team_bot.registry import TOOL_REGISTRY

    r1_plus_names = {spec.name for spec in TOOL_REGISTRY if spec.risk_tier != RiskTier.R0}
    assert sent_tool_names.isdisjoint(r1_plus_names)
    assert result.degraded is True
    assert result.degraded_reason == DEGRADED_REASON


@pytest.mark.asyncio
async def test_result_always_marked_degraded_even_on_success() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_SUCCESS_BODY)

    async with _client_with(handler) as client:
        result = await client.chat_completion(messages=[{"role": "user", "content": "x"}], max_tokens=50)
    assert result.degraded is True
    assert result.call.message["content"] == "the practice is active"


@pytest.mark.asyncio
async def test_local_server_down_raises_network_error_not_a_quota_error() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with _client_with(handler) as client:
        with pytest.raises(BrainCallError) as exc_info:
            await client.chat_completion(messages=[{"role": "user", "content": "x"}], max_tokens=50)
    assert exc_info.value.verdict.error_class is BrainErrorClass.NETWORK_ERROR
