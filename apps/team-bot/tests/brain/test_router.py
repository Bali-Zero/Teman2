"""Tests for team_bot.brain.router.BrainRouter — the fallback chain
(qwen3.7-plus -> qwen3.6-flash -> glm-5.2 -> local read-only), the kill
switch, per-model breaker integration, and the depletion probe hookup."""

from __future__ import annotations

import json

import httpx
import pytest

from team_bot.brain.circuit_breaker import BreakerConfig
from team_bot.brain.depletion_probe import DepletionProbe
from team_bot.brain.local_readonly import LocalReadOnlyClient
from team_bot.brain.router import BrainRouter, BrainRouterExhaustedError, BrainTier
from team_bot.brain.tp1_client import TP1Client

_FAKE_KEY = "sk-test-fake"


def _success_body(model: str) -> str:
    return json.dumps(
        {
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": f"answer from {model}"}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 5, "total_tokens": 10, "completion_tokens": 5},
        }
    )


_AUTH_401_BODY = json.dumps(
    {"error": {"message": "Invalid API-key provided.", "type": "invalid_request_error", "code": "invalid_api_key"}}
)
_SERVER_500_BODY = json.dumps({"error": {"message": "internal error", "type": "server_error"}})


def _tp1_client_routing_by_model(model_to_status: dict[str, int], model_to_body: dict[str, str] | None = None) -> TP1Client:
    model_to_body = model_to_body or {}

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        model = body["model"]
        status = model_to_status.get(model, 500)
        text = model_to_body.get(model) or (_success_body(model) if status == 200 else _SERVER_500_BODY)
        return httpx.Response(status, text=text)

    return TP1Client(_FAKE_KEY, transport=httpx.MockTransport(handler))


def _local_client(*, fail: bool = False) -> LocalReadOnlyClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(200, text=_success_body("local"))

    return LocalReadOnlyClient(
        base_url="http://127.0.0.1:11434/v1", model="local-qwen", transport=httpx.MockTransport(handler)
    )


def _probe() -> DepletionProbe:
    return DepletionProbe()  # unconfigured — fine for router tests, tested separately


def _messages() -> list[dict]:
    return [{"role": "user", "content": "status of PR-1234?"}]


@pytest.mark.asyncio
async def test_primary_tier_success_never_touches_fallbacks() -> None:
    tp1 = _tp1_client_routing_by_model({"qwen3.7-plus": 200, "qwen3.6-flash": 200, "glm-5.2": 200})
    router = BrainRouter(
        tp1_client=tp1, local_client=_local_client(), depletion_probe=_probe(), is_tp1_enabled=lambda: True
    )
    completion = await router.complete(messages=_messages(), max_tokens=20)
    assert completion.tier is BrainTier.TP1_QWEN_3_7_PLUS
    assert completion.degraded is False
    assert len(completion.attempts) == 1
    assert completion.attempts[0].outcome == "success"


@pytest.mark.asyncio
async def test_primary_failure_falls_back_to_secondary() -> None:
    tp1 = _tp1_client_routing_by_model({"qwen3.7-plus": 500, "qwen3.6-flash": 200, "glm-5.2": 200})
    router = BrainRouter(
        tp1_client=tp1, local_client=_local_client(), depletion_probe=_probe(), is_tp1_enabled=lambda: True
    )
    completion = await router.complete(messages=_messages(), max_tokens=20)
    assert completion.tier is BrainTier.TP1_QWEN_3_6_FLASH
    assert completion.degraded is False
    assert [a.outcome for a in completion.attempts] == ["error", "success"]


@pytest.mark.asyncio
async def test_first_two_fail_falls_to_glm() -> None:
    tp1 = _tp1_client_routing_by_model({"qwen3.7-plus": 500, "qwen3.6-flash": 500, "glm-5.2": 200})
    router = BrainRouter(
        tp1_client=tp1, local_client=_local_client(), depletion_probe=_probe(), is_tp1_enabled=lambda: True
    )
    completion = await router.complete(messages=_messages(), max_tokens=20)
    assert completion.tier is BrainTier.TP1_GLM_5_2


@pytest.mark.asyncio
async def test_all_three_cloud_tiers_fail_falls_to_local_read_only() -> None:
    tp1 = _tp1_client_routing_by_model({"qwen3.7-plus": 500, "qwen3.6-flash": 500, "glm-5.2": 500})
    router = BrainRouter(
        tp1_client=tp1, local_client=_local_client(), depletion_probe=_probe(), is_tp1_enabled=lambda: True
    )
    completion = await router.complete(messages=_messages(), max_tokens=20)
    assert completion.tier is BrainTier.LOCAL_READ_ONLY
    assert completion.degraded is True
    assert completion.degraded_reason is not None
    outcomes = [a.outcome for a in completion.attempts]
    assert outcomes == ["error", "error", "error", "success"]


@pytest.mark.asyncio
async def test_kill_switch_off_skips_all_cloud_tiers_goes_straight_to_local() -> None:
    tp1_calls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        tp1_calls.append(json.loads(request.content)["model"])
        return httpx.Response(200, text=_success_body("should never be called"))

    tp1 = TP1Client(_FAKE_KEY, transport=httpx.MockTransport(handler))
    router = BrainRouter(
        tp1_client=tp1, local_client=_local_client(), depletion_probe=_probe(), is_tp1_enabled=lambda: False
    )
    completion = await router.complete(messages=_messages(), max_tokens=20)
    assert completion.tier is BrainTier.LOCAL_READ_ONLY
    assert completion.degraded is True
    assert tp1_calls == []  # the cloud door was never even dialed
    assert completion.attempts[0].outcome == "skipped_kill_switch"


@pytest.mark.asyncio
async def test_everything_fails_raises_brain_router_exhausted_error() -> None:
    tp1 = _tp1_client_routing_by_model({"qwen3.7-plus": 500, "qwen3.6-flash": 500, "glm-5.2": 500})
    router = BrainRouter(
        tp1_client=tp1, local_client=_local_client(fail=True), depletion_probe=_probe(), is_tp1_enabled=lambda: True
    )
    with pytest.raises(BrainRouterExhaustedError) as exc_info:
        await router.complete(messages=_messages(), max_tokens=20)
    assert len(exc_info.value.attempts) == 4
    assert all(a.outcome == "error" for a in exc_info.value.attempts)


@pytest.mark.asyncio
async def test_auth_dead_trips_breaker_so_next_call_skips_that_tier() -> None:
    tp1 = _tp1_client_routing_by_model(
        {"qwen3.7-plus": 401, "qwen3.6-flash": 200, "glm-5.2": 200}, {"qwen3.7-plus": _AUTH_401_BODY}
    )
    router = BrainRouter(
        tp1_client=tp1,
        local_client=_local_client(),
        depletion_probe=_probe(),
        breaker_config=BreakerConfig(),  # AUTH_DEAD trips immediately
        is_tp1_enabled=lambda: True,
    )
    first = await router.complete(messages=_messages(), max_tokens=20)
    assert first.tier is BrainTier.TP1_QWEN_3_6_FLASH  # fell through past the dead primary

    # Second call: the primary's breaker is now OPEN, so it must be
    # SKIPPED (not attempted) rather than errored again.
    second = await router.complete(messages=_messages(), max_tokens=20)
    assert second.attempts[0].outcome == "skipped_breaker_open"
    assert second.tier is BrainTier.TP1_QWEN_3_6_FLASH


@pytest.mark.asyncio
async def test_usage_is_recorded_in_depletion_probe_on_success() -> None:
    tp1 = _tp1_client_routing_by_model({"qwen3.7-plus": 200, "qwen3.6-flash": 200, "glm-5.2": 200})
    probe = DepletionProbe(quota_tokens_7d=1000)
    router = BrainRouter(tp1_client=tp1, local_client=_local_client(), depletion_probe=probe, is_tp1_enabled=lambda: True)
    await router.complete(messages=_messages(), max_tokens=20)
    assert probe.used_tokens() == 10  # from _success_body's usage.total_tokens


@pytest.mark.asyncio
async def test_depletion_alarm_surfaces_on_the_completion() -> None:
    tp1 = _tp1_client_routing_by_model({"qwen3.7-plus": 200, "qwen3.6-flash": 200, "glm-5.2": 200})
    probe = DepletionProbe(quota_tokens_7d=11, alarm_thresholds=(0.30, 0.10))  # 10/11 used -> ~9% remaining
    router = BrainRouter(tp1_client=tp1, local_client=_local_client(), depletion_probe=probe, is_tp1_enabled=lambda: True)
    completion = await router.complete(messages=_messages(), max_tokens=20)
    thresholds = sorted(a.threshold for a in completion.alarms)
    assert thresholds == pytest.approx([0.10, 0.30])


@pytest.mark.asyncio
async def test_local_read_only_result_never_records_into_depletion_probe() -> None:
    # The depletion probe tracks TP1's shared-pool usage specifically —
    # local inference has no token-plan cost, so recording it would
    # overstate cloud consumption.
    tp1 = _tp1_client_routing_by_model({"qwen3.7-plus": 500, "qwen3.6-flash": 500, "glm-5.2": 500})
    probe = DepletionProbe(quota_tokens_7d=1000)
    router = BrainRouter(tp1_client=tp1, local_client=_local_client(), depletion_probe=probe, is_tp1_enabled=lambda: True)
    completion = await router.complete(messages=_messages(), max_tokens=20)
    assert completion.tier is BrainTier.LOCAL_READ_ONLY
    assert probe.used_tokens() == 0
