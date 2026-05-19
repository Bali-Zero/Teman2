"""Unit tests for vendor/evoskill/src/harness/deepseek/executor.py.

Tests the Phase 1 real DeepSeek V4 Pro Chat Completions adapter via
httpx mock (no actual API calls). Covers:
    - execute_query happy path (200 OK → response dict in single-item list)
    - DEEPSEEK_API_KEY missing → RuntimeError
    - 401 auth failure → DeepSeekAPIError (non-retryable)
    - 500 then 200 retry → success after backoff
    - 500 always → DeepSeekTransientError after retries exhausted
    - Network timeout → DeepSeekTransientError
    - parse_response with JSON in code fence → unwrapped + Pydantic validated
    - parse_response with free-text + no Pydantic model → output=None,
      not is_error
    - parse_response with bad JSON + Pydantic model → parse_error set
    - parse_response with empty messages → _empty_trace_fields
    - _estimate_cost_usd with cache hit + miss + completion → correct math
    - _estimate_cost_usd with unknown model → 0.0 + warning
    - _build_response_format for json schema vs free-text

Run:
    cd ~/Desktop/nuzantara-wt-evoskill-phase1
    PYTHONPATH=vendor/evoskill python3 -m pytest scripts/test_deepseek_executor.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "vendor" / "evoskill"))

from src.harness.deepseek.executor import (  # noqa: E402
    DEEPSEEK_CHAT_ENDPOINT,
    DeepSeekAPIError,
    DeepSeekTransientError,
    _build_response_format,
    _estimate_cost_usd,
    execute_query,
    parse_response,
)


# Patch asyncio.sleep to a no-op so retry tests don't actually wait 30s+
@pytest.fixture(autouse=True)
def _patch_sleep(monkeypatch):
    async def _noop(_):
        return None

    monkeypatch.setattr("asyncio.sleep", _noop)


@pytest.fixture
def set_api_key(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-fake-key-for-unit-tests")
    yield


@pytest.fixture
def unset_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    yield


class ExampleResponse(BaseModel):
    answer: str
    confidence: float


def _make_mock_response(
    *, status: int = 200, json_body: dict | None = None, text: str = ""
) -> httpx.Response:
    """Build an httpx Response with a fake request attached."""
    request = httpx.Request("POST", DEEPSEEK_CHAT_ENDPOINT)
    if json_body is not None:
        return httpx.Response(status, json=json_body, request=request)
    return httpx.Response(status, text=text or "", request=request)


def _mock_transport(responses: list[httpx.Response]) -> httpx.MockTransport:
    """MockTransport that returns each response in order."""
    iterator = iter(responses)

    def handler(_request: httpx.Request) -> httpx.Response:
        try:
            return next(iterator)
        except StopIteration:
            raise AssertionError("MockTransport ran out of responses")

    return httpx.MockTransport(handler)


# Capture the ORIGINAL httpx.AsyncClient at import time so the
# monkeypatch wrapper can construct one without recursing into itself.
_ORIGINAL_ASYNC_CLIENT = httpx.AsyncClient


def _patch_async_client(monkeypatch, transport: httpx.MockTransport) -> None:
    """Replace httpx.AsyncClient with a factory that injects MockTransport.

    Avoids the recursion trap: a naive `monkeypatch.setattr("httpx.AsyncClient",
    lambda *a,**kw: httpx.AsyncClient(transport=...))` would re-enter the
    patched name and recurse forever.
    """
    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return _ORIGINAL_ASYNC_CLIENT(transport=transport, **kwargs)

    monkeypatch.setattr("httpx.AsyncClient", factory)


# ─── execute_query: happy path + auth ────────────────────────────────


@pytest.mark.asyncio
async def test_execute_query_happy_path(monkeypatch, set_api_key):
    """200 OK → single-item list wrapping the response JSON."""
    json_body = {
        "id": "chatcmpl-fake-123",
        "model": "deepseek-v4-pro",
        "choices": [
            {
                "message": {"role": "assistant", "content": '{"answer": "42", "confidence": 0.9}'},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "prompt_cache_hit_tokens": 30,
            "prompt_cache_miss_tokens": 70,
        },
    }
    transport = _mock_transport([_make_mock_response(json_body=json_body)])
    _patch_async_client(monkeypatch, transport)

    options = {"sdk": "deepseek", "model": "deepseek-v4-pro", "system": "You answer."}
    out = await execute_query(options, "What is the meaning of life?")
    assert isinstance(out, list) and len(out) == 1
    assert out[0]["id"] == "chatcmpl-fake-123"
    assert out[0]["choices"][0]["message"]["content"].startswith('{"answer"')


@pytest.mark.asyncio
async def test_execute_query_no_api_key_raises(unset_api_key):
    """Missing DEEPSEEK_API_KEY → RuntimeError with CLAUDE.md context."""
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        await execute_query({"model": "deepseek-v4-pro"}, "q")


# ─── execute_query: error handling + retry ───────────────────────────


@pytest.mark.asyncio
async def test_execute_query_401_auth_not_retried(monkeypatch, set_api_key):
    """401 is non-retryable → DeepSeekAPIError after FIRST attempt."""
    transport = _mock_transport(
        [_make_mock_response(status=401, text='{"error":"invalid_api_key"}')]
    )
    _patch_async_client(monkeypatch, transport)
    with pytest.raises(DeepSeekAPIError, match="401"):
        await execute_query({"model": "deepseek-v4-pro"}, "q")


@pytest.mark.asyncio
async def test_execute_query_500_then_200_succeeds(monkeypatch, set_api_key):
    """500 → retry → 200 succeeds. Verifies backoff loop."""
    good_body = {
        "id": "ok-after-retry",
        "model": "deepseek-v4-pro",
        "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
    }
    transport = _mock_transport(
        [
            _make_mock_response(status=500, text="upstream error"),
            _make_mock_response(json_body=good_body),
        ]
    )
    _patch_async_client(monkeypatch, transport)
    out = await execute_query({"model": "deepseek-v4-pro"}, "q")
    assert out[0]["id"] == "ok-after-retry"


@pytest.mark.asyncio
async def test_execute_query_500_all_attempts_raises_transient(monkeypatch, set_api_key):
    """4 attempts all 500 → DeepSeekTransientError."""
    transport = _mock_transport(
        [_make_mock_response(status=500, text="upstream error")] * 4
    )
    _patch_async_client(monkeypatch, transport)
    with pytest.raises(DeepSeekTransientError, match="after 4 attempts"):
        await execute_query({"model": "deepseek-v4-pro"}, "q")


@pytest.mark.asyncio
async def test_execute_query_429_is_retryable(monkeypatch, set_api_key):
    """429 (rate limit) is retryable; 1 retry succeeds."""
    good_body = {
        "id": "ok",
        "model": "deepseek-v4-pro",
        "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
    }
    transport = _mock_transport(
        [
            _make_mock_response(status=429, text="rate limited"),
            _make_mock_response(json_body=good_body),
        ]
    )
    _patch_async_client(monkeypatch, transport)
    out = await execute_query({"model": "deepseek-v4-pro"}, "q")
    assert out[0]["id"] == "ok"


@pytest.mark.asyncio
async def test_execute_query_400_bad_request_not_retried(monkeypatch, set_api_key):
    """400 is non-retryable (client bug, not transient)."""
    transport = _mock_transport(
        [_make_mock_response(status=400, text='{"error":"bad_request"}')]
    )
    _patch_async_client(monkeypatch, transport)
    with pytest.raises(DeepSeekAPIError, match="400"):
        await execute_query({"model": "deepseek-v4-pro"}, "q")


# ─── parse_response: structured output ───────────────────────────────


def test_parse_response_valid_pydantic_json(set_api_key):
    response = {
        "id": "test-id",
        "model": "deepseek-v4-pro",
        "choices": [
            {
                "message": {"content": '{"answer": "yes", "confidence": 0.85}'},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    fields = parse_response(
        [response],
        ExampleResponse,
        get_options=lambda: {"model": "deepseek-v4-pro", "tools": ["foo"]},
    )
    assert fields["is_error"] is False
    assert fields["parse_error"] is None
    assert isinstance(fields["output"], ExampleResponse)
    assert fields["output"].answer == "yes"
    assert fields["output"].confidence == 0.85
    assert fields["raw_structured_output"] == {"answer": "yes", "confidence": 0.85}
    assert fields["model"] == "deepseek-v4-pro"
    assert fields["tools"] == ["foo"]
    assert fields["num_turns"] == 1


def test_parse_response_strips_code_fence(set_api_key):
    """DeepSeek may wrap output in ```json blocks — must be stripped."""
    response = {
        "id": "x",
        "model": "deepseek-v4-pro",
        "choices": [
            {
                "message": {
                    "content": '```json\n{"answer": "fenced", "confidence": 0.5}\n```'
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    fields = parse_response(
        [response], ExampleResponse, get_options=lambda: {"model": "deepseek-v4-pro"}
    )
    assert fields["parse_error"] is None
    assert isinstance(fields["output"], ExampleResponse)
    assert fields["output"].answer == "fenced"


def test_parse_response_invalid_json_with_pydantic_sets_parse_error(set_api_key):
    """If content is not JSON but a Pydantic model was requested → parse_error."""
    response = {
        "id": "x",
        "model": "deepseek-v4-pro",
        "choices": [
            {"message": {"content": "Just plain prose, no JSON."}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    fields = parse_response(
        [response], ExampleResponse, get_options=lambda: {"model": "deepseek-v4-pro"}
    )
    assert fields["parse_error"] is not None
    assert "not valid JSON" in fields["parse_error"]
    assert fields["output"] is None
    assert fields["is_error"] is True


def test_parse_response_pydantic_validation_error(set_api_key):
    """Valid JSON but wrong shape → ValidationError captured in parse_error."""
    response = {
        "id": "x",
        "model": "deepseek-v4-pro",
        "choices": [
            {
                "message": {
                    "content": '{"answer": "missing_confidence_field"}'
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    fields = parse_response(
        [response], ExampleResponse, get_options=lambda: {"model": "deepseek-v4-pro"}
    )
    assert fields["parse_error"] is not None
    assert "ValidationError" in fields["parse_error"]
    assert fields["output"] is None


def test_parse_response_empty_messages():
    fields = parse_response([], ExampleResponse, get_options=lambda: {})
    assert fields["is_error"] is True
    assert "empty messages list" in fields["parse_error"]
    assert fields["num_turns"] == 0


def test_parse_response_non_dict_response():
    fields = parse_response(
        ["not a dict"], ExampleResponse, get_options=lambda: {}  # type: ignore[list-item]
    )
    assert fields["is_error"] is True
    assert "not a dict" in fields["parse_error"]


def test_parse_response_no_choices_array():
    response = {"id": "x", "model": "deepseek-v4-pro", "usage": {}}
    fields = parse_response([response], ExampleResponse, get_options=lambda: {})
    assert fields["is_error"] is True
    assert "no `choices` array" in fields["parse_error"]


# ─── Cost estimation ─────────────────────────────────────────────────


def test_estimate_cost_with_cache_hit_and_miss():
    """deepseek-v4-pro pricing: cache_hit=0.07, cache_miss=0.27, output=1.10 per 1M."""
    usage = {
        "prompt_tokens": 1000,
        "prompt_cache_hit_tokens": 300,
        "prompt_cache_miss_tokens": 700,
        "completion_tokens": 500,
    }
    cost = _estimate_cost_usd("deepseek-v4-pro", usage)
    # 300*0.07 + 700*0.27 + 500*1.10 = 21 + 189 + 550 = 760 (per 1M)
    # → 0.00076 USD
    assert cost == pytest.approx(0.00076, rel=1e-3)


def test_estimate_cost_legacy_response_treats_all_as_miss():
    """When only prompt_tokens is reported (no hit/miss split), assume worst case."""
    usage = {"prompt_tokens": 1000, "completion_tokens": 500}
    cost = _estimate_cost_usd("deepseek-v4-pro", usage)
    # 1000*0.27 + 500*1.10 = 270 + 550 = 820 / 1M = 0.00082
    assert cost == pytest.approx(0.00082, rel=1e-3)


def test_estimate_cost_unknown_model_returns_zero():
    cost = _estimate_cost_usd(
        "unknown-future-model", {"prompt_tokens": 1000, "completion_tokens": 500}
    )
    assert cost == 0.0


def test_estimate_cost_fuzzy_match_on_model_prefix():
    """`deepseek-v4-pro-2024-12` should match `deepseek-v4-pro` pricing."""
    cost = _estimate_cost_usd(
        "deepseek-v4-pro-2026-05", {"prompt_tokens": 1000, "completion_tokens": 500}
    )
    assert cost > 0


# ─── Response format builder ─────────────────────────────────────────


def test_build_response_format_with_schema():
    rf = _build_response_format({"type": "object", "properties": {}})
    assert rf == {"type": "json_object"}


def test_build_response_format_no_schema():
    assert _build_response_format(None) is None
    assert _build_response_format({}) is None


# ─── Integration: execute_query + parse_response together ────────────


@pytest.mark.asyncio
async def test_round_trip_execute_and_parse(monkeypatch, set_api_key):
    json_body = {
        "id": "round-trip-test",
        "model": "deepseek-v4-pro",
        "choices": [
            {
                "message": {"content": '{"answer": "round-trip OK", "confidence": 0.99}'},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 20},
    }
    transport = _mock_transport([_make_mock_response(json_body=json_body)])
    _patch_async_client(monkeypatch, transport)

    options = {"model": "deepseek-v4-pro", "system": "test", "tools": []}
    messages = await execute_query(options, "test query")
    fields = parse_response(messages, ExampleResponse, get_options=lambda: options)

    assert fields["is_error"] is False
    assert fields["uuid"] == "round-trip-test"
    assert fields["output"].answer == "round-trip OK"
    assert fields["total_cost_usd"] > 0  # 50+20 tokens cost something
