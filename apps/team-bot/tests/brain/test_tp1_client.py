"""Tests for team_bot.brain.tp1_client.TP1Client — all against
`httpx.MockTransport`, never the real network. Response bodies for the
success/401/404 cases are the REAL bodies captured live against TP1 on
2026-08-25 (see errors.py's evidence ledger) so this test suite proves the
client parses what the vendor actually sends, not a body this session
invented."""

from __future__ import annotations

import json

import httpx
import pytest

from team_bot.brain.errors import BrainErrorClass
from team_bot.brain.tp1_client import BrainCallError, TP1Client, TP1Model

_FAKE_KEY = "sk-test-fake-not-a-real-key-0000000000000000000000000000000"

_OBSERVED_PING_PONG_BODY = json.dumps(
    {
        "id": "chatcmpl-bf52f777-3ab0-477a-81f0-c2cd54049de1",
        "object": "chat.completion",
        "created": 1787618000,
        "model": "qwen3.6-flash",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Pong! \U0001f3d3"},
                "finish_reason": "stop",
                "logprobs": None,
            }
        ],
        "usage": {"prompt_tokens": 13, "total_tokens": 19, "completion_tokens": 6},
    }
)

_OBSERVED_TOOL_CALL_BODY = json.dumps(
    {
        "id": "chatcmpl-0226d44c-e936-47e0-843e-2448e7a1799f",
        "object": "chat.completion",
        "created": 1787618020,
        "model": "qwen3.7-plus",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_713fd91115094583ab8188a6",
                            "type": "function",
                            "function": {
                                "name": "practice_status_get",
                                "arguments": '{"practice_id": "PR-1234"}',
                            },
                            "index": 0,
                        }
                    ],
                },
                "finish_reason": "tool_calls",
                "logprobs": None,
            }
        ],
        "usage": {"prompt_tokens": 302, "total_tokens": 335, "completion_tokens": 33},
    }
)

_OBSERVED_401_BODY = (
    '{"error":{"message":"Invalid API-key provided. For details, see: '
    "https://www.alibabacloud.com/help/en/model-studio/error-code#apikey-error\","
    '"id":"67a650b7-b4a5-449b-af3f-c7fb5c01527b","type":"invalid_request_error",'
    '"code":"invalid_api_key"}}'
)

_OBSERVED_404_BODY = (
    '{"error":{"message":"Model not exist.","id":"f21dd93c-0925-4fe6-a7a4-9342868c3af1",'
    '"type":"invalid_request_error","code":"model_not_found"}}'
)


def _client_with(handler, api_key: str = _FAKE_KEY) -> TP1Client:
    return TP1Client(api_key, transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_successful_plain_text_completion() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_OBSERVED_PING_PONG_BODY)

    async with _client_with(handler) as client:
        result = await client.chat_completion(
            model=TP1Model.QWEN_3_6_FLASH,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=8,
        )
    assert result.message["content"] == "Pong! \U0001f3d3"
    assert result.usage.total_tokens == 19
    assert result.finish_reason == "stop"


@pytest.mark.asyncio
async def test_successful_tool_call_completion_is_openai_shaped() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_OBSERVED_TOOL_CALL_BODY)

    async with _client_with(handler) as client:
        result = await client.chat_completion(
            model=TP1Model.QWEN_3_7_PLUS,
            messages=[{"role": "user", "content": "status of PR-1234"}],
            tools=[{"type": "function", "function": {"name": "practice_status_get", "parameters": {}}}],
            max_tokens=200,
        )
    assert result.finish_reason == "tool_calls"
    call = result.message["tool_calls"][0]
    assert call["function"]["name"] == "practice_status_get"
    assert json.loads(call["function"]["arguments"]) == {"practice_id": "PR-1234"}


@pytest.mark.asyncio
async def test_request_body_defaults_enable_thinking_false() -> None:
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, text=_OBSERVED_PING_PONG_BODY)

    async with _client_with(handler) as client:
        await client.chat_completion(
            model=TP1Model.QWEN_3_6_FLASH, messages=[{"role": "user", "content": "ping"}], max_tokens=8
        )
    assert captured["body"]["enable_thinking"] is False


@pytest.mark.asyncio
async def test_request_body_sets_parallel_tool_calls_false_when_tools_present() -> None:
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, text=_OBSERVED_TOOL_CALL_BODY)

    async with _client_with(handler) as client:
        await client.chat_completion(
            model=TP1Model.QWEN_3_7_PLUS,
            messages=[{"role": "user", "content": "x"}],
            tools=[{"type": "function", "function": {"name": "t", "parameters": {}}}],
            max_tokens=8,
        )
    assert captured["body"]["parallel_tool_calls"] is False


@pytest.mark.asyncio
async def test_authorization_header_uses_bearer_key() -> None:
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, text=_OBSERVED_PING_PONG_BODY)

    async with _client_with(handler) as client:
        await client.chat_completion(
            model=TP1Model.QWEN_3_6_FLASH, messages=[{"role": "user", "content": "ping"}], max_tokens=8
        )
    assert captured["auth"] == f"Bearer {_FAKE_KEY}"


@pytest.mark.asyncio
async def test_401_raises_brain_call_error_with_auth_dead_verdict() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=_OBSERVED_401_BODY)

    async with _client_with(handler) as client:
        with pytest.raises(BrainCallError) as exc_info:
            await client.chat_completion(
                model=TP1Model.QWEN_3_6_FLASH, messages=[{"role": "user", "content": "ping"}], max_tokens=8
            )
    assert exc_info.value.verdict.error_class is BrainErrorClass.AUTH_DEAD
    # Never leaks the key into the exception text.
    assert _FAKE_KEY not in str(exc_info.value)


@pytest.mark.asyncio
async def test_404_model_not_found_raises_with_correct_verdict() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text=_OBSERVED_404_BODY)

    async with _client_with(handler) as client:
        with pytest.raises(BrainCallError) as exc_info:
            await client.chat_completion(
                model=TP1Model.QWEN_3_6_FLASH, messages=[{"role": "user", "content": "ping"}], max_tokens=8
            )
    assert exc_info.value.verdict.error_class is BrainErrorClass.MODEL_NOT_FOUND


@pytest.mark.asyncio
async def test_timeout_raises_timeout_verdict() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async with _client_with(handler) as client:
        with pytest.raises(BrainCallError) as exc_info:
            await client.chat_completion(
                model=TP1Model.QWEN_3_6_FLASH, messages=[{"role": "user", "content": "ping"}], max_tokens=8
            )
    assert exc_info.value.verdict.error_class is BrainErrorClass.TIMEOUT


@pytest.mark.asyncio
async def test_connect_error_raises_network_error_verdict() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with _client_with(handler) as client:
        with pytest.raises(BrainCallError) as exc_info:
            await client.chat_completion(
                model=TP1Model.QWEN_3_6_FLASH, messages=[{"role": "user", "content": "ping"}], max_tokens=8
            )
    assert exc_info.value.verdict.error_class is BrainErrorClass.NETWORK_ERROR


@pytest.mark.asyncio
async def test_malformed_200_body_raises_output_invalid() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text='{"unexpected": "shape"}')

    async with _client_with(handler) as client:
        with pytest.raises(BrainCallError) as exc_info:
            await client.chat_completion(
                model=TP1Model.QWEN_3_6_FLASH, messages=[{"role": "user", "content": "ping"}], max_tokens=8
            )
    assert exc_info.value.verdict.error_class is BrainErrorClass.OUTPUT_INVALID


@pytest.mark.asyncio
async def test_non_json_200_body_raises_output_invalid_not_a_crash() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json at all")

    async with _client_with(handler) as client:
        with pytest.raises(BrainCallError) as exc_info:
            await client.chat_completion(
                model=TP1Model.QWEN_3_6_FLASH, messages=[{"role": "user", "content": "ping"}], max_tokens=8
            )
    assert exc_info.value.verdict.error_class is BrainErrorClass.OUTPUT_INVALID


@pytest.mark.asyncio
async def test_innocent_200_with_rate_limit_sounding_content_is_not_an_error() -> None:
    # A perfectly ordinary successful reply whose CONTENT happens to
    # discuss a client's KITAS sponsor quota / login must never be
    # misrouted into an error path — the classifier only ever sees non-2xx
    # responses (verified here at the integration level, not just unit
    # level in test_errors.py).
    body = json.dumps(
        {
            "id": "chatcmpl-innocuous",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": (
                            "Your sponsor's quota exceeded this year's KITAS allocation — "
                            "please sign in to the portal to review."
                        ),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 20, "total_tokens": 40, "completion_tokens": 20},
        }
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    async with _client_with(handler) as client:
        result = await client.chat_completion(
            model=TP1Model.QWEN_3_6_FLASH, messages=[{"role": "user", "content": "x"}], max_tokens=50
        )
    assert "quota" in result.message["content"]  # ordinary content, not an exception


@pytest.mark.asyncio
async def test_list_models_returns_sorted_ids() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(
            200,
            text=json.dumps({"data": [{"id": "qwen3.7-plus"}, {"id": "glm-5.2"}, {"id": "qwen3.6-flash"}]}),
        )

    async with _client_with(handler) as client:
        ids = await client.list_models()
    assert ids == ["glm-5.2", "qwen3.6-flash", "qwen3.7-plus"]


@pytest.mark.asyncio
async def test_list_models_raises_on_error_status() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=_OBSERVED_401_BODY)

    async with _client_with(handler) as client:
        with pytest.raises(BrainCallError) as exc_info:
            await client.list_models()
    assert exc_info.value.verdict.error_class is BrainErrorClass.AUTH_DEAD


def test_pinned_slugs_match_the_live_observed_roster() -> None:
    # Locks TP1Model's three values to the exact live GET /models slugs
    # observed 2026-08-25 (errors.py evidence ledger) — a future edit that
    # accidentally aliases one (e.g. "qwen3.7" instead of "qwen3.7-plus")
    # fails this test instead of silently 404ing in production.
    assert {m.value for m in TP1Model} == {"qwen3.7-plus", "qwen3.6-flash", "glm-5.2"}
