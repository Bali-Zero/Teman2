"""
Tests for `backend/llm/openai_responses_client.py` — an OFFLINE, unwired
OpenAI Responses adapter (nothing in this repo imports it outside tests
and the standalone `scripts/bot/wa_blind_bench.py` harness).

Every HTTP-shaped case is faked at the `httpx` transport boundary with
realistic Responses-API payloads (never a mock of the client's own
methods — see cicatrix W114: a fake at the SERVICE layer tends to share
the test author's own assumptions about the wire format instead of the
real API's, and both sides confirming each other is not evidence).

Covers:
    - key absent -> disabled, `available` is a LIVE read (not cached)
    - dedicated env var (`OPENAI_WA_PROVIDER_API_KEY`), never the
      embeddings `OPENAI_API_KEY`
    - refusal on HTTP 200 status=completed
    - fail-closed on status != "completed" (failed/incomplete/cancelled/
      unknown), and on `incomplete_details`
    - fail-closed on an unrecognised output-item type and an unrecognised
      message content-part type
    - tool_call parsing
    - positive tool allowlist: empty by default -> any tools= call raises;
      a request mixing an allowed name with an unknown one is rejected
      FAIL-CLOSED in its entirety — never partially filtered down to just
      the allowed names (R13-2 binding correction, 2026-08-15, Kimi K3
      round-13 review: this line previously described the REJECTED
      partial-filter design; the real, pinned semantics is whole-request
      fail-closed, see `test_mixed_allowed_and_unknown_tools_rejects_entire_request`)
    - usage accounting
    - network error vs API error vs response-shape error, distinct types
    - retry behaviour (transient vs non-transient)
    - OpenAIAPIError never carries the remote response body
    - statelessness: every request body carries `store: false` and NO
      `previous_response_id` key ever appears in a payload
    - approved model constants (MODEL_TERRA default, MODEL_SOL never
      silently selected)
"""

from __future__ import annotations

import json

import httpx
import pytest

from backend.llm import openai_responses_client as client_module
from backend.llm.openai_responses_client import (
    DEFAULT_MODEL,
    MODEL_LUNA,
    MODEL_SOL,
    MODEL_TERRA,
    OpenAIAPIError,
    OpenAIClientUnavailableError,
    OpenAICredentialFormatError,
    OpenAIModelNotAllowedError,
    OpenAINetworkError,
    OpenAIResponsesClient,
    OpenAIResponseShapeError,
    OpenAIToolNotAllowedError,
    _extract_refusal_reason,
    _get_str_field,
    _parse_responses_payload,
    _validate_api_key_ascii,
)


def _text_response_payload(text: str, *, model: str = "gpt-5.6-terra", status: str = "completed") -> dict:
    return {
        "id": "resp_abc123",
        "model": model,
        "status": status,
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            },
        ],
        "usage": {"input_tokens": 12, "output_tokens": 7},
    }


def _refusal_response_payload(*, model: str = "gpt-5.6-terra") -> dict:
    return {
        "id": "resp_refuse1",
        "model": model,
        "status": "completed",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {"type": "refusal", "refusal": "I can't help with that request."},
                ],
            },
        ],
        "usage": {"input_tokens": 5, "output_tokens": 3},
    }


def _tool_call_response_payload(*, model: str = "gpt-5.6-terra") -> dict:
    return {
        "id": "resp_tool1",
        "model": model,
        "status": "completed",
        "output": [
            {
                "type": "function_call",
                "call_id": "call_1",
                "name": "get_weather",
                "arguments": '{"city": "Bali"}',
            },
        ],
        "usage": {"input_tokens": 20, "output_tokens": 4},
    }


def _client_with_transport(handler, *, api_key: str = "test-key") -> OpenAIResponsesClient:
    """Build a client whose persistent httpx.AsyncClient is pre-wired to a
    MockTransport — no real network I/O, ever. Mirrors the
    `test_instagram_adapter.py` pattern already established in this repo.
    """
    client = OpenAIResponsesClient(api_key=api_key, max_retries=2)
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


class TestAvailability:
    def test_no_key_env_unset_is_unavailable(self, monkeypatch):
        monkeypatch.delenv("OPENAI_WA_PROVIDER_API_KEY", raising=False)
        client = OpenAIResponsesClient()
        assert client.available is False

    def test_explicit_key_is_available(self):
        client = OpenAIResponsesClient(api_key="sk-explicit")
        assert client.available is True

    def test_available_is_a_live_read_not_cached(self, monkeypatch):
        """An earlier draft cached `self.api_key` at construction while
        documenting `available` as a live read — a lie. This test would
        have failed against that draft."""
        monkeypatch.delenv("OPENAI_WA_PROVIDER_API_KEY", raising=False)
        client = OpenAIResponsesClient()
        assert client.available is False
        monkeypatch.setenv("OPENAI_WA_PROVIDER_API_KEY", "sk-now-present")
        assert client.available is True  # must flip WITHOUT re-constructing the client

    def test_generate_raises_when_unavailable(self, monkeypatch):
        monkeypatch.delenv("OPENAI_WA_PROVIDER_API_KEY", raising=False)
        client = OpenAIResponsesClient()
        with pytest.raises(OpenAIClientUnavailableError):
            import asyncio

            asyncio.run(client.generate(input_text="hello"))

    def test_dedicated_env_var_not_embeddings_key(self, monkeypatch):
        """The single most load-bearing test in this file (binding
        correction, 2026-08-15): the client must NEVER become available
        just because the pre-existing embeddings `OPENAI_API_KEY` happens
        to be set."""
        monkeypatch.delenv("OPENAI_WA_PROVIDER_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-embeddings-key-not-mine")
        client = OpenAIResponsesClient()
        assert client.available is False, (
            "OpenAIResponsesClient must not ride on the embeddings OPENAI_API_KEY — "
            "identity/billing separation is non-negotiable."
        )


class TestR11_4MaxRetriesValidation:
    """R11-4 (Kimi K3 round-11 review): `max_retries` was never validated
    in `__init__`. Two concrete failure modes: `2.5` reaches
    `range(1, self.max_retries + 2)` inside `generate()` and raises a raw
    `TypeError`, entirely outside this module's own typed exception
    taxonomy; `-1` produces an EMPTY range — zero network calls ever
    made — and falls through to the loop's trailing
    `raise OpenAINetworkError(...)`, a transport-flavored exception for a
    call the transport never touched. Both are now caught at construction
    time with a `ValueError`."""

    def test_guilt_float_max_retries_raises_value_error_at_construction(self):
        with pytest.raises(ValueError):
            OpenAIResponsesClient(api_key="sk-test", max_retries=2.5)

    def test_guilt_negative_max_retries_raises_value_error_at_construction(self):
        with pytest.raises(ValueError):
            OpenAIResponsesClient(api_key="sk-test", max_retries=-1)

    def test_guilt_bool_max_retries_raises_value_error_at_construction(self):
        """`bool` is a subtype of `int` in Python — `isinstance(True, int)`
        is `True` — so a bare `isinstance(max_retries, int)` check alone
        would silently accept `True`/`False` as `1`/`0`, the same
        bool-exclusion trap R8-6 already had to guard against for `seed`
        in `wa_blind_bench.py`."""
        with pytest.raises(ValueError):
            OpenAIResponsesClient(api_key="sk-test", max_retries=True)

    def test_innocence_zero_max_retries_constructs_normally(self):
        client = OpenAIResponsesClient(api_key="sk-test", max_retries=0)
        assert client.max_retries == 0

    def test_innocence_default_max_retries_constructs_normally(self):
        client = OpenAIResponsesClient(api_key="sk-test")
        assert client.max_retries == 2


class TestR12_1TimeoutValidation:
    """R12-1 (Kimi K3 round-12 review): `timeout` was never validated in
    `__init__` and is handed to `httpx.AsyncClient(timeout=...)` unexamined.
    A non-numeric or `bool` value would only fail deep inside httpx's own
    timeout parsing, outside this module's typed exception taxonomy;
    `float("nan")` is worse — httpx does not reject NaN, so every deadline
    comparison against it is silently always-false and a hung connection
    would never time out. Non-positive values are rejected as a deadline
    that has already elapsed before the first request is sent."""

    def test_guilt_string_timeout_raises_value_error_at_construction(self):
        with pytest.raises(ValueError):
            OpenAIResponsesClient(api_key="sk-test", timeout="abc")

    def test_guilt_bool_timeout_raises_value_error_at_construction(self):
        """Same bool-exclusion trap as `max_retries` (R11-4) and `seed`
        (R8-6) — `bool` is a subtype of `int`, so a bare
        `isinstance(timeout, (int, float))` check alone would silently
        accept `True`/`False` as `1`/`0`."""
        with pytest.raises(ValueError):
            OpenAIResponsesClient(api_key="sk-test", timeout=True)

    def test_guilt_negative_timeout_raises_value_error_at_construction(self):
        with pytest.raises(ValueError):
            OpenAIResponsesClient(api_key="sk-test", timeout=-1)

    def test_guilt_nan_timeout_raises_value_error_at_construction(self):
        with pytest.raises(ValueError):
            OpenAIResponsesClient(api_key="sk-test", timeout=float("nan"))

    def test_guilt_oversized_int_timeout_raises_value_error_not_overflow_error(self):
        """R13-1 (Kimi K3 round-13 review): `math.isfinite` does not
        return `False` on an `int` too large to convert to `float` — it
        RAISES `OverflowError`, which used to escape this constructor
        raw, outside the exception taxonomy this class's own `Raises:`
        block claims is complete. `10**400` is treated as non-finite
        (it can never be a usable timeout) and must raise `ValueError`,
        never `OverflowError`."""
        with pytest.raises(ValueError):
            OpenAIResponsesClient(api_key="sk-test", timeout=10**400)

    def test_innocence_int_timeout_constructs_normally(self):
        client = OpenAIResponsesClient(api_key="sk-test", timeout=30)
        assert client.timeout == 30

    def test_innocence_float_timeout_constructs_normally(self):
        client = OpenAIResponsesClient(api_key="sk-test", timeout=12.5)
        assert client.timeout == 12.5


class TestR12_2ApiKeyTypeValidation:
    """R12-2 (Kimi K3 round-12 review): a non-`str`, non-`None` `api_key`
    (e.g. an `int` or `bytes`) previously reached `_resolve_api_key()` and
    then `_validate_api_key_ascii()` unexamined — the ASCII/control-char
    regex match on a non-`str` raises a raw `TypeError` from `re.search`,
    outside this module's typed exception hierarchy. The existing
    empty-string-is-falsy-and-therefore-unavailable semantics are
    preserved unchanged — only the *type* is validated here."""

    def test_guilt_int_api_key_raises_value_error_at_construction(self):
        with pytest.raises(ValueError):
            OpenAIResponsesClient(api_key=123)

    def test_guilt_bytes_api_key_raises_value_error_at_construction(self):
        with pytest.raises(ValueError):
            OpenAIResponsesClient(api_key=b"sk-x")

    def test_innocence_none_api_key_constructs_normally(self):
        client = OpenAIResponsesClient(api_key=None)
        assert client._explicit_api_key is None

    def test_innocence_string_api_key_constructs_normally(self):
        client = OpenAIResponsesClient(api_key="sk-x")
        assert client._explicit_api_key == "sk-x"

    def test_innocence_empty_string_api_key_constructs_normally(self):
        """Empty string is a valid `str` — it must still construct, and
        the existing falsy-is-unavailable semantics are unchanged by this
        type check.

        R13-4 binding correction, 2026-08-15 (Kimi K3 round-13 review):
        the docstring above promises "falsy-is-unavailable semantics
        unchanged" but the body only ever asserted `_explicit_api_key`,
        never `available` itself — the property the promise is actually
        about. `_resolve_api_key` returns `self._explicit_api_key`
        whenever it is not `None` (an explicit `""` is not `None`), so
        `available` reads `bool("")` regardless of any
        `OPENAI_WA_PROVIDER_API_KEY` set in the ambient environment —
        no `monkeypatch` needed for this assertion to be meaningful."""
        client = OpenAIResponsesClient(api_key="")
        assert client._explicit_api_key == ""
        assert client.available is False


class TestR6_5CredentialFormatValidation:
    """R6-5 (Kimi K3 round-6 review): a resolved API key containing a
    non-ASCII or control character used to escape this module's typed
    exception taxonomy entirely — `httpx` encodes header VALUES as
    Latin-1, so building `Authorization: Bearer <key>` via `_headers()`'s
    f-string with a key containing e.g. 'é' raises a raw
    `UnicodeEncodeError` deep inside httpx, never one of
    `OpenAIClientUnavailableError` / `OpenAINetworkError` /
    `OpenAIAPIError` / `OpenAIResponseShapeError` — the "complete" set
    `generate()`'s own `Raises:` docstring claims. `_validate_api_key_ascii`
    is called from `generate()` BEFORE any network call and raises the
    typed `OpenAICredentialFormatError` instead."""

    @pytest.mark.asyncio
    async def test_guilt_non_ascii_key_raises_typed_error_before_any_network_call(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("no network call should happen for a malformed key")

        client = _client_with_transport(handler, api_key="sk-café-not-ascii")
        with pytest.raises(OpenAICredentialFormatError) as exc_info:
            await client.generate(input_text="hello")
        assert exc_info.value.category == "non_ascii_key"

    @pytest.mark.asyncio
    async def test_guilt_control_char_key_raises_typed_error_before_any_network_call(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("no network call should happen for a malformed key")

        # A key that is pure ASCII but embeds a CRLF — isascii() alone
        # would let this through; the dedicated control-char regex catches
        # what isascii() cannot (see _API_KEY_CONTROL_CHAR_RE).
        client = _client_with_transport(handler, api_key="sk-abc\r\ninjected-header")
        with pytest.raises(OpenAICredentialFormatError) as exc_info:
            await client.generate(input_text="hello")
        assert exc_info.value.category == "control_char_key"

    def test_guilt_exception_message_never_contains_key_content_or_length(self):
        key = "sk-café-" + "x" * 50  # distinctive content + a length nobody should be able to recover
        with pytest.raises(OpenAICredentialFormatError) as exc_info:
            _validate_api_key_ascii(key)
        message = str(exc_info.value)
        assert key not in message
        assert "café" not in message
        assert str(len(key)) not in message, "the key's length alone can fingerprint some key formats"

    def test_innocence_normal_ascii_key_passes_validation_unchanged(self):
        # Must not raise — this is the happy path every real deployment
        # hits. `_validate_api_key_ascii` has no return value on success
        # (raises on failure, returns None on success), so asserting the
        # (only) return value IS the assertion that it did not raise.
        assert _validate_api_key_ascii("sk-perfectly-normal-ascii-key-123") is None

    @pytest.mark.asyncio
    async def test_innocence_normal_key_reaches_the_network_and_generates(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_text_response_payload("hi there"))

        client = _client_with_transport(handler, api_key="sk-normal-ascii-key-123")
        result = await client.generate(input_text="hello")
        assert result.text == "hi there"
        assert result.refusal is False


class TestParsing:
    """Pure-function tests against realistic payload shapes — no I/O."""

    def test_text_response(self):
        result = _parse_responses_payload(
            _text_response_payload("Halo, PT PMA membutuhkan modal 2.5 miliar."),
            model_requested=MODEL_TERRA,
        )
        assert result.text == "Halo, PT PMA membutuhkan modal 2.5 miliar."
        assert result.refusal is False
        assert result.refusal_reason is None
        assert result.tool_calls == ()
        assert result.input_tokens == 12
        assert result.output_tokens == 7

    def test_refusal_is_not_an_error_shape(self):
        result = _parse_responses_payload(_refusal_response_payload(), model_requested=MODEL_TERRA)
        assert result.refusal is True
        assert result.refusal_reason == "I can't help with that request."
        assert result.text == ""

    def test_tool_call_parsed_when_requested(self):
        """A function_call is only accepted when its name is in
        `requested_tool_names` — see the fail-closed test right below for
        the default (empty) case."""
        result = _parse_responses_payload(
            _tool_call_response_payload(),
            model_requested=MODEL_TERRA,
            requested_tool_names=frozenset({"get_weather"}),
        )
        assert len(result.tool_calls) == 1
        call = result.tool_calls[0]
        assert call.name == "get_weather"
        assert json.loads(call.arguments) == {"city": "Bali"}

    def test_unexpected_function_call_fails_closed_by_default(self):
        """With `requested_tool_names` defaulting to empty (which is what
        happens whenever `ALLOWED_TOOL_NAMES` is empty, the current
        state), ANY function_call the server returns is unsolicited and
        must be rejected — never silently handed back as a normal tool
        call to a caller who never asked for tools."""
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(_tool_call_response_payload(), model_requested=MODEL_TERRA)

    def test_function_call_for_a_different_name_than_requested_fails_closed(self):
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(
                _tool_call_response_payload(),  # names "get_weather"
                model_requested=MODEL_TERRA,
                requested_tool_names=frozenset({"some_other_tool"}),
            )

    @pytest.mark.parametrize("status", ["failed", "incomplete", "cancelled", "queued", "in_progress", "bogus"])
    def test_non_completed_status_raises(self, status):
        payload = _text_response_payload("partial answer", status=status)
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_incomplete_details_present_raises_even_if_status_completed(self):
        """Belt-and-suspenders: a payload should never carry both
        status=completed and incomplete_details, but if the API ever does,
        this client refuses rather than trusting the more convenient
        field."""
        payload = _text_response_payload("truncated answer")
        payload["incomplete_details"] = {"reason": "max_output_tokens"}
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_unrecognised_output_item_type_raises(self):
        """`reasoning` is now a KNOWN, recognised-and-ignored type (P0,
        2026-08-15 — see TestReasoningItem below) — this test uses a
        genuinely unrecognised type so it keeps testing what it claims to."""
        payload = _text_response_payload("ok")
        payload["output"].append({"type": "some_future_item_type", "data": "..."})
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_unrecognised_message_content_part_type_raises(self):
        payload = _text_response_payload("ok")
        payload["output"][0]["content"].append({"type": "input_image", "image_url": "https://x"})
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_known_shape_does_not_raise(self):
        """Innocence companion to the four raising tests above — a
        legitimate, fully-recognised payload must not be caught by an
        over-broad guard."""
        result = _parse_responses_payload(_text_response_payload("all good"), model_requested=MODEL_TERRA)
        assert result.text == "all good"

    def test_response_body_not_a_dict_raises(self):
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(["not", "a", "dict"], model_requested=MODEL_TERRA)  # type: ignore[arg-type]

    def test_output_missing_raises(self):
        payload = _text_response_payload("ok")
        del payload["output"]
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_output_not_a_list_raises(self):
        payload = _text_response_payload("ok")
        payload["output"] = {"type": "message"}
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_output_empty_list_raises(self):
        """A 'completed' response with a genuinely empty output list is
        invalid, not a quietly successful empty answer."""
        payload = _text_response_payload("ok")
        payload["output"] = []
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_output_item_not_a_dict_raises(self):
        payload = _text_response_payload("ok")
        payload["output"].append("not-a-dict")
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_message_content_not_a_list_raises(self):
        payload = _text_response_payload("ok")
        payload["output"][0]["content"] = "not-a-list"
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_message_content_part_not_a_dict_raises(self):
        payload = _text_response_payload("ok")
        payload["output"][0]["content"].append("not-a-dict")
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_completed_with_message_but_no_text_no_refusal_raises(self):
        """A message item whose content list is present but empty yields
        no text and no refusal — this must fail closed rather than return
        a silently empty successful answer."""
        payload = {
            "id": "resp_empty",
            "model": "gpt-5.6-terra",
            "status": "completed",
            "output": [{"type": "message", "role": "assistant", "content": []}],
            "usage": {"input_tokens": 1, "output_tokens": 0},
        }
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_error_messages_never_contain_the_remote_value(self):
        """Binding correction, 2026-08-15: error text carries only local
        category literals, never the raw remote status/reason/type."""
        marker = "REMOTE_INJECTED_MARKER_XYZ"
        payload = _text_response_payload("ok", status=marker)
        with pytest.raises(OpenAIResponseShapeError) as exc_info:
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)
        assert marker not in str(exc_info.value)
        assert "category=unknown" in str(exc_info.value)

    def test_known_non_completed_status_reported_as_its_own_local_category(self):
        payload = _text_response_payload("ok", status="failed")
        with pytest.raises(OpenAIResponseShapeError) as exc_info:
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)
        assert "category=failed" in str(exc_info.value)


class TestReasoningItem:
    """P0 (2026-08-15): GPT-5.x models on the Responses API routinely emit
    a `type: "reasoning"` output item before the `message` item. Before
    this fix, EVERY real GPT-5.x response would have hit the
    "unrecognised output item type" branch and raised — this client had
    never actually accepted a live response from the model family it
    targets."""

    def _reasoning_item(self, **extra) -> dict:
        """Shape confirmed against OpenAI's migrate-to-responses guide,
        2026-08-15: `id`, `type`, `content` (list), `summary` (list), and
        optionally `encrypted_content`."""
        return {
            "id": "rs_abc123",
            "type": "reasoning",
            "content": [],
            "summary": [{"type": "summary_text", "text": "internal chain of thought — must never leak"}],
            **extra,
        }

    def test_reasoning_before_message_is_ignored_and_message_still_parses(self):
        payload = _text_response_payload("the real answer")
        payload["output"].insert(0, self._reasoning_item())
        result = _parse_responses_payload(payload, model_requested=MODEL_TERRA)
        assert result.text == "the real answer"
        assert result.refusal is False

    def test_reasoning_summary_text_never_leaks_into_result(self):
        """The reasoning item's `summary` carries a marker string that must
        never surface anywhere on the parsed result — this client ignores
        reasoning items entirely, it does not selectively redact them.

        Live-gate addendum (2026-08-15): the original second assertion
        (`(result.refusal_reason or "") == "" or marker not in
        result.refusal_reason`) was near-vacuous — in THIS payload
        `refusal_reason` is always `None` (no refusal item exists here),
        so the left side of the `or` is always `True` and Python's `or`
        short-circuits before ever evaluating `marker not in
        result.refusal_reason`: the assertion would have passed even if
        the marker somehow DID leak into a refusal reason. Rewritten with
        a second scenario that genuinely produces a non-None
        `refusal_reason` (a refusal response, not a text response) with
        the same marker planted in a leading reasoning item — the
        marker-absence check there is a standalone assert with real
        signal, not the disarmed second half of an `or`."""
        marker = "CHAIN_OF_THOUGHT_MARKER_SHOULD_NEVER_LEAK"
        payload = _text_response_payload("the real answer")
        payload["output"].insert(0, self._reasoning_item(summary=[{"type": "summary_text", "text": marker}]))
        result = _parse_responses_payload(payload, model_requested=MODEL_TERRA)
        assert marker not in result.text
        assert result.refusal_reason is None  # this payload has no refusal item at all

        refusal_payload = _refusal_response_payload()
        refusal_payload["output"].insert(0, self._reasoning_item(summary=[{"type": "summary_text", "text": marker}]))
        refusal_result = _parse_responses_payload(refusal_payload, model_requested=MODEL_TERRA)
        assert refusal_result.refusal is True
        assert refusal_result.refusal_reason is not None
        assert marker not in refusal_result.refusal_reason

    def test_reasoning_only_response_still_raises_no_text_refusal_or_tool_call(self):
        """Recognising `reasoning` is not the same as treating it as a
        satisfying answer — a reasoning-only response (no message, no
        refusal, no tool_call) must still fail closed."""
        payload = {
            "id": "resp_reasoning_only",
            "model": "gpt-5.6-terra",
            "status": "completed",
            "output": [self._reasoning_item()],
            "usage": {"input_tokens": 5, "output_tokens": 0},
        }
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_reasoning_item_that_is_not_a_dict_raises(self):
        """Malformed shape: a 'reasoning' slot in `output` that isn't
        itself a JSON object must fail the same generic non-dict-item
        guard every other item type is subject to — recognising the type
        string never bypasses the base shape check."""
        payload = _text_response_payload("ok")
        payload["output"].insert(0, "not-a-dict-reasoning-item")
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_reasoning_with_encrypted_content_field_ignored(self):
        """Confirmed-possible field (OpenAI's ZDR-compatible mode returns
        `encrypted_content`) — must never be read or surfaced either."""
        payload = _text_response_payload("the real answer")
        payload["output"].insert(0, self._reasoning_item(encrypted_content="opaque-blob-should-not-matter"))
        result = _parse_responses_payload(payload, model_requested=MODEL_TERRA)
        assert result.text == "the real answer"

    # --- A1 (2026-08-15 audit): "recognised and ignored" must still mean
    # "shape-validated, then ignored" — not "unvalidated". Every field on
    # a reasoning item is OPTIONAL, but a PRESENT field with the wrong
    # type must still fail closed like everywhere else in this parser.

    def test_reasoning_summary_not_a_list_raises(self):
        payload = _text_response_payload("ok")
        payload["output"].insert(0, self._reasoning_item(summary="not-a-list"))
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_reasoning_content_not_a_list_raises(self):
        payload = _text_response_payload("ok")
        payload["output"].insert(0, self._reasoning_item(content="not-a-list"))
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_reasoning_id_not_a_string_raises(self):
        payload = _text_response_payload("ok")
        payload["output"].insert(0, self._reasoning_item(id=12345))
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_reasoning_encrypted_content_not_a_string_raises(self):
        payload = _text_response_payload("ok")
        payload["output"].insert(0, self._reasoning_item(encrypted_content={"not": "a string"}))
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_reasoning_with_absent_optional_fields_still_succeeds(self):
        """Innocence: every reasoning field is OPTIONAL — a reasoning item
        carrying only `type` must not be rejected for missing fields that
        are legitimately allowed to be absent."""
        payload = _text_response_payload("ok")
        payload["output"].insert(0, {"type": "reasoning"})
        result = _parse_responses_payload(payload, model_requested=MODEL_TERRA)
        assert result.text == "ok"


class TestRemoteTypeValidation:
    """P1 (2026-08-15 binding correction): every remote-controlled field
    that becomes part of the envelope or a dataclass must be type-checked
    before use — a malformed shape raises `OpenAIResponseShapeError`,
    never a raw `TypeError`, and (for function_call/refusal/usage fields)
    never silently coerces into looking like a well-formed value."""

    def test_function_call_name_not_a_string_raises(self):
        payload = _tool_call_response_payload()
        payload["output"][0]["name"] = 12345
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(
                payload, model_requested=MODEL_TERRA, requested_tool_names=frozenset({"get_weather"}),
            )

    def test_function_call_call_id_not_a_string_raises(self):
        payload = _tool_call_response_payload()
        payload["output"][0]["call_id"] = {"nested": "object"}
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(
                payload, model_requested=MODEL_TERRA, requested_tool_names=frozenset({"get_weather"}),
            )

    def test_function_call_arguments_not_a_string_raises(self):
        payload = _tool_call_response_payload()
        payload["output"][0]["arguments"] = ["not", "a", "json", "string"]
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(
                payload, model_requested=MODEL_TERRA, requested_tool_names=frozenset({"get_weather"}),
            )

    def test_function_call_well_formed_strings_still_parse(self):
        """Innocence companion — a genuinely well-formed function_call must
        not be caught by the new type guards."""
        result = _parse_responses_payload(
            _tool_call_response_payload(),
            model_requested=MODEL_TERRA,
            requested_tool_names=frozenset({"get_weather"}),
        )
        assert result.tool_calls[0].call_id == "call_1"

    def test_message_refusal_reason_not_a_string_raises(self):
        payload = _refusal_response_payload()
        payload["output"][0]["content"][0]["refusal"] = {"nested": "object"}
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_top_level_refusal_reason_not_a_string_raises(self):
        payload = {
            "id": "resp_top_refuse",
            "model": "gpt-5.6-terra",
            "status": "completed",
            "output": [{"type": "refusal", "refusal": ["not", "a", "string"]}],
            "usage": {"input_tokens": 1, "output_tokens": 0},
        }
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_top_level_refusal_well_formed_string_still_parses(self):
        payload = {
            "id": "resp_top_refuse_ok",
            "model": "gpt-5.6-terra",
            "status": "completed",
            "output": [{"type": "refusal", "refusal": "a real reason"}],
            "usage": {"input_tokens": 1, "output_tokens": 0},
        }
        result = _parse_responses_payload(payload, model_requested=MODEL_TERRA)
        assert result.refusal is True
        assert result.refusal_reason == "a real reason"

    def test_usage_input_tokens_bool_raises(self):
        """`bool` is an `int` subclass in Python — must be explicitly
        rejected, not silently coerced to 0/1."""
        payload = _text_response_payload("ok")
        payload["usage"]["input_tokens"] = True
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_usage_output_tokens_negative_raises(self):
        payload = _text_response_payload("ok")
        payload["usage"]["output_tokens"] = -1
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_usage_tokens_non_int_string_raises(self):
        payload = _text_response_payload("ok")
        payload["usage"]["input_tokens"] = "12"
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_usage_tokens_missing_defaults_to_zero(self):
        """Innocence — a missing usage field must still default to 0, not
        raise (matches the pre-existing `int(... or 0)` behaviour for the
        absent case)."""
        payload = _text_response_payload("ok")
        del payload["usage"]["input_tokens"]
        result = _parse_responses_payload(payload, model_requested=MODEL_TERRA)
        assert result.input_tokens == 0

    def test_usage_tokens_zero_is_valid_not_an_error(self):
        payload = _text_response_payload("ok")
        payload["usage"] = {"input_tokens": 0, "output_tokens": 0}
        result = _parse_responses_payload(payload, model_requested=MODEL_TERRA)
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_model_not_a_string_falls_back_to_model_requested(self):
        """`model`/`id` are the two fields that degrade to a local fallback
        instead of raising — they are metadata, not safety-relevant."""
        payload = _text_response_payload("ok")
        payload["model"] = 12345
        result = _parse_responses_payload(payload, model_requested=MODEL_TERRA)
        assert result.model == MODEL_TERRA

    def test_id_not_a_string_falls_back_to_none(self):
        payload = _text_response_payload("ok")
        payload["id"] = 999
        result = _parse_responses_payload(payload, model_requested=MODEL_TERRA)
        assert result.raw_response_id is None

    def test_model_and_id_well_formed_strings_pass_through(self):
        """Innocence companion for the fallback pair."""
        payload = _text_response_payload("ok", model="gpt-5.6-luna")
        payload["id"] = "resp_real_id"
        result = _parse_responses_payload(payload, model_requested=MODEL_TERRA)
        assert result.model == "gpt-5.6-luna"
        assert result.raw_response_id == "resp_real_id"

    # --- MEDIUM/LOW (2026-08-15, Kimi K3 adversarial review of frozen
    # 6a8ab5180..1be079571 diff) -------------------------------------

    def test_status_not_hashable_raises_shape_error_not_typeerror(self):
        """MEDIUM: `status not in _ACCEPTED_STATUS` requires `status` to
        be hashable — a remote `status` that is a list would previously
        have raised a raw `TypeError: unhashable type`, not the
        fail-closed `OpenAIResponseShapeError` this module promises
        everywhere else."""
        payload = _text_response_payload("ok")
        payload["status"] = ["completed"]
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_output_item_type_not_hashable_raises_shape_error_not_typeerror(self):
        payload = _text_response_payload("ok")
        payload["output"].append({"type": {"nested": "object"}})
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_message_content_part_type_not_hashable_raises_shape_error_not_typeerror(self):
        payload = _text_response_payload("ok")
        payload["output"][0]["content"].append({"type": ["nested", "list"]})
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_output_text_missing_text_field_raises(self):
        """LOW: an absent `text` key must fail closed, not silently
        degrade to an empty string (A2 required-by-default doctrine)."""
        payload = _text_response_payload("ok")
        del payload["output"][0]["content"][0]["text"]
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_output_text_explicit_empty_string_still_parses(self):
        """Innocence companion — a genuinely present `"text": ""` is a
        legitimate (if unusual) value, distinct from the key being
        absent, and must not raise on its own (the overall
        no-text/no-refusal/no-tool-call guard is a separate check)."""
        payload = _text_response_payload("ok")
        payload["output"][0]["content"][0]["text"] = ""
        payload["output"][0]["content"].append({"type": "refusal", "refusal": "something"})
        result = _parse_responses_payload(payload, model_requested=MODEL_TERRA)
        assert result.text == ""
        assert result.refusal is True

    def test_usage_present_but_not_a_dict_raises(self):
        """LOW: `data.get("usage") or {}` collapsed a present-but-malformed
        `usage` (any falsy or non-dict value) down to the same silent `{}`
        an absent one gets — must fail closed instead."""
        payload = _text_response_payload("ok")
        payload["usage"] = "not-a-dict"
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_usage_present_but_falsy_non_dict_raises(self):
        """Guilt companion for the FALSY non-dict case specifically — the
        old `or {}` made this indistinguishable from absent."""
        payload = _text_response_payload("ok")
        payload["usage"] = 0
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_usage_explicit_none_defaults_to_zero(self):
        """Innocence — explicit `"usage": null` means "no usage data
        given", same as an absent key, and must NOT raise."""
        payload = _text_response_payload("ok")
        payload["usage"] = None
        result = _parse_responses_payload(payload, model_requested=MODEL_TERRA)
        assert result.input_tokens == 0
        assert result.output_tokens == 0

    def test_incomplete_details_falsy_non_dict_present_raises(self):
        """LOW: `if incomplete_details:` used truthiness — a
        present-but-falsy malformed value (`0`, `""`, `[]`) was treated as
        equivalent to ABSENT and silently skipped. Any of these are now a
        fail-closed shape error, never a silently-accepted 'complete'
        response."""
        payload = _text_response_payload("ok")
        payload["incomplete_details"] = 0
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_incomplete_details_empty_string_present_raises(self):
        payload = _text_response_payload("ok")
        payload["incomplete_details"] = ""
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_incomplete_details_explicit_none_does_not_raise(self):
        """Innocence — explicit `"incomplete_details": null` means "no
        incompleteness to report", same as an absent key."""
        payload = _text_response_payload("ok")
        payload["incomplete_details"] = None
        result = _parse_responses_payload(payload, model_requested=MODEL_TERRA)
        assert result.text == "ok"


class TestGetStrFieldRequiredByDefault:
    """A2 (2026-08-15 audit): `_get_str_field` defaulted MISSING
    `function_call.call_id`/`arguments` to `""` — indistinguishable from a
    server that genuinely sent an empty string. Now required by default;
    only an explicit `default=` opts out (no current call site does)."""

    def test_missing_key_with_no_default_raises(self):
        with pytest.raises(OpenAIResponseShapeError):
            _get_str_field({}, "call_id", "function_call.call_id")

    def test_missing_key_with_explicit_default_returns_default(self):
        assert _get_str_field({}, "call_id", "function_call.call_id", default="fallback") == "fallback"

    def test_missing_key_with_non_string_default_raises(self):
        """MICRO binding correction, 2026-08-15 (Kimi K3, live-gate round
        5, point F(i)): the docstring claims an explicitly-passed
        `default` is type-checked as a string, but the absent-key branch
        returned it completely unchecked — team-lead's explicit
        preference was to fix the CODE to match the docstring's claim
        (not weaken the docstring). Guilt: a non-string `default` (e.g. an
        `int`, standing in for any caller bug that passes the wrong
        type) on a missing key must raise the same category of error as
        the present-non-string-value path, not silently return the
        malformed default."""
        with pytest.raises(OpenAIResponseShapeError):
            _get_str_field({}, "call_id", "function_call.call_id", default=123)

    def test_present_string_returned_regardless_of_default(self):
        assert _get_str_field({"call_id": "call_1"}, "call_id", "function_call.call_id") == "call_1"

    def test_present_non_string_raises(self):
        with pytest.raises(OpenAIResponseShapeError):
            _get_str_field({"call_id": 123}, "call_id", "function_call.call_id")

    def test_function_call_missing_call_id_raises(self):
        payload = _tool_call_response_payload()
        del payload["output"][0]["call_id"]
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(
                payload, model_requested=MODEL_TERRA, requested_tool_names=frozenset({"get_weather"}),
            )

    def test_function_call_missing_arguments_raises(self):
        payload = _tool_call_response_payload()
        del payload["output"][0]["arguments"]
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(
                payload, model_requested=MODEL_TERRA, requested_tool_names=frozenset({"get_weather"}),
            )

    def test_function_call_missing_name_raises(self):
        payload = _tool_call_response_payload()
        del payload["output"][0]["name"]
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(
                payload, model_requested=MODEL_TERRA, requested_tool_names=frozenset({"get_weather"}),
            )


class TestExtractRefusalReasonPresenceVsFalsy:
    """A3 (2026-08-15 audit): the original `if value:` guard conflated
    "key absent" with "key present but falsy" — `{"refusal": 0}` or
    `{"refusal": {}}` would have been silently SKIPPED (treated as if
    nothing were sent) rather than rejected as malformed. Declared rule:
    ABSENT, `None`, or `""` all mean "try the next candidate" (or
    fallback); any OTHER non-string present value raises."""

    def test_present_zero_raises(self):
        with pytest.raises(OpenAIResponseShapeError):
            _extract_refusal_reason({"refusal": 0}, "refusal")

    def test_present_false_raises(self):
        with pytest.raises(OpenAIResponseShapeError):
            _extract_refusal_reason({"refusal": False}, "refusal")

    def test_present_empty_dict_raises(self):
        with pytest.raises(OpenAIResponseShapeError):
            _extract_refusal_reason({"refusal": {}}, "refusal")

    def test_present_empty_list_raises(self):
        with pytest.raises(OpenAIResponseShapeError):
            _extract_refusal_reason({"refusal": []}, "refusal")

    def test_present_none_falls_back_to_next_key(self):
        assert _extract_refusal_reason({"refusal": None, "text": "real reason"}, "refusal", "text") == "real reason"

    def test_present_none_on_last_key_falls_back_to_refused(self):
        assert _extract_refusal_reason({"refusal": None}, "refusal") == "refused"

    def test_present_empty_string_falls_back_to_next_key(self):
        """Declared choice: an empty string is syntactically a valid `str`
        but carries no actual reason — treated as equivalent to absent,
        not raised."""
        assert _extract_refusal_reason({"refusal": "", "text": "real reason"}, "refusal", "text") == "real reason"

    def test_missing_key_entirely_falls_back_to_refused(self):
        assert _extract_refusal_reason({}, "refusal", "text") == "refused"

    def test_present_valid_string_returned(self):
        assert _extract_refusal_reason({"refusal": "policy violation"}, "refusal") == "policy violation"

    def test_message_refusal_reason_zero_raises_via_full_parse(self):
        payload = _refusal_response_payload()
        payload["output"][0]["content"][0]["refusal"] = 0
        with pytest.raises(OpenAIResponseShapeError):
            _parse_responses_payload(payload, model_requested=MODEL_TERRA)

    def test_top_level_refusal_reason_none_falls_back_via_full_parse(self):
        payload = {
            "id": "resp_top_refuse_none",
            "model": "gpt-5.6-terra",
            "status": "completed",
            "output": [{"type": "refusal", "refusal": None}],
            "usage": {"input_tokens": 1, "output_tokens": 0},
        }
        result = _parse_responses_payload(payload, model_requested=MODEL_TERRA)
        assert result.refusal is True
        assert result.refusal_reason == "refused"


class TestToolAllowlist:
    def test_default_allowlist_is_empty(self):
        assert client_module.ALLOWED_TOOL_NAMES == frozenset()

    async def test_tools_argument_with_empty_allowlist_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("must never reach the network when every tool is rejected")

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIToolNotAllowedError):
            await client.generate(input_text="hi", tools=[{"name": "crm_query"}])
        await client.close()

    async def test_no_tools_argument_never_raises_allowlist_error(self):
        """Innocence: a normal call with no tools at all must not trip the
        allowlist guard."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_text_response_payload("ok"))

        client = _client_with_transport(handler)
        result = await client.generate(input_text="hi")
        await client.close()
        assert result.text == "ok"

    async def test_mixed_allowed_and_unknown_tools_rejects_entire_request(self, monkeypatch):
        """Binding correction, 2026-08-15: a mixed list (one allowed name,
        one unknown name) must refuse the WHOLE request — never silently
        drop the unknown one and forward the allowed one. This replaces a
        prior (wrong) design that partially filtered."""
        monkeypatch.setattr(client_module, "ALLOWED_TOOL_NAMES", frozenset({"get_weather"}))

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("must never reach the network on a mixed allowed/unknown tools list")

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIToolNotAllowedError):
            await client.generate(
                input_text="hi",
                tools=[{"name": "get_weather"}, {"name": "crm_query"}],
            )
        await client.close()

    async def test_all_allowed_tools_are_forwarded_verbatim(self, monkeypatch):
        monkeypatch.setattr(client_module, "ALLOWED_TOOL_NAMES", frozenset({"get_weather"}))
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "id": "resp_tool_ok",
                    "model": "gpt-5.6-terra",
                    "status": "completed",
                    "output": [
                        {
                            "type": "function_call",
                            "call_id": "call_1",
                            "name": "get_weather",
                            "arguments": "{}",
                        },
                    ],
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
            )

        client = _client_with_transport(handler)
        result = await client.generate(input_text="hi", tools=[{"name": "get_weather"}])
        await client.close()

        forwarded_names = [t["name"] for t in captured["body"]["tools"]]
        assert forwarded_names == ["get_weather"]
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "get_weather"

    async def test_tools_entry_not_a_dict_raises_typed_error_pre_network(self):
        """LOW (2026-08-15, Kimi K3 adversarial review): a `tools` entry
        that isn't a dict (e.g. a bare string) made `t.get("name")` raise
        a raw `AttributeError` — must be a typed, pre-network refusal
        instead, same as an unknown tool name."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("must never reach the network with a malformed tools entry")

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIToolNotAllowedError):
            await client.generate(input_text="hi", tools=["not-a-dict"])
        await client.close()

    async def test_tools_entry_not_a_dict_among_valid_ones_still_refuses_whole_request(self, monkeypatch):
        """Guilt companion: a malformed entry mixed with an otherwise
        allowlisted one must still refuse the WHOLE request, not just
        skip the bad entry — same all-or-nothing discipline as the
        mixed allowed/unknown-name case above."""
        monkeypatch.setattr(client_module, "ALLOWED_TOOL_NAMES", frozenset({"get_weather"}))

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("must never reach the network with a malformed tools entry")

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIToolNotAllowedError):
            await client.generate(input_text="hi", tools=[{"name": "get_weather"}, "not-a-dict"])
        await client.close()

    async def test_tools_entry_name_not_hashable_raises_typed_error_pre_network(self):
        """Same-class binding correction (2026-08-15, Kimi K3 live-gate):
        a dict entry whose `name` is itself unhashable (a list/dict) made
        `t.get("name") not in ALLOWED_TOOL_NAMES` raise a raw `TypeError:
        unhashable type` — the entry-is-a-dict guard above did not cover
        this, since the entry itself IS a well-formed dict; the problem is
        one level deeper, in the `name` value. Must be a typed pre-network
        refusal instead, zero HTTP calls."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("must never reach the network with an unhashable tool name")

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIToolNotAllowedError):
            await client.generate(input_text="hi", tools=[{"name": ["x"]}])
        await client.close()

    async def test_tools_entry_unknown_string_name_behaviour_unchanged(self):
        """Innocence: the new isinstance(name, str) guard must not change
        behaviour for the pre-existing, already-covered case — a
        well-formed string name that simply isn't on the allowlist still
        raises the ORIGINARY unknown-name refusal, not the new
        malformed-name one."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("must never reach the network when the tool name is unknown")

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIToolNotAllowedError) as exc_info:
            await client.generate(input_text="hi", tools=[{"name": "crm_query"}])
        await client.close()

        assert "malformed_tool_name" not in str(exc_info.value)


class TestGenerateHTTP:
    async def test_successful_generate(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_text_response_payload("ok"))

        client = _client_with_transport(handler)
        result = await client.generate(input_text="hi")
        assert result.text == "ok"
        assert result.attempts == 1
        await client.close()

    async def test_stateless_payload_shape(self):
        """Every request is stateless. `store` must be `false` and
        `previous_response_id` must never appear."""
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_text_response_payload("ok"))

        client = _client_with_transport(handler)
        await client.generate(input_text="hi", system_prompt="be nice")
        await client.close()

        assert captured["body"]["store"] is False
        assert "previous_response_id" not in captured["body"]

    async def test_default_model_is_terra_not_sol(self):
        """`sol` is a ceiling-only reference, and the default must be an
        approved candidate, not the most expensive tier."""
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_text_response_payload("ok"))

        client = _client_with_transport(handler)
        await client.generate(input_text="hi")
        await client.close()

        assert captured["body"]["model"] == MODEL_TERRA == DEFAULT_MODEL
        assert captured["body"]["model"] != MODEL_SOL

    async def test_explicit_model_override_honoured(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_text_response_payload("ok", model=MODEL_LUNA))

        client = _client_with_transport(handler)
        result = await client.generate(input_text="hi", model=MODEL_LUNA)
        await client.close()

        assert captured["body"]["model"] == MODEL_LUNA
        assert result.model == MODEL_LUNA

    async def test_refusal_returned_not_raised(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_refusal_response_payload())

        client = _client_with_transport(handler)
        result = await client.generate(input_text="do something unsafe")
        await client.close()

        assert result.refusal is True
        assert result.refusal_reason

    async def test_incomplete_status_raises_shape_error_not_returned_as_text(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_text_response_payload("cut off mid", status="incomplete"))

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIResponseShapeError):
            await client.generate(input_text="hi")
        await client.close()


class TestR14_2GeneratePayloadValidation:
    """R14-2 (Kimi K3 round-14 review): `input_text`/`system_prompt`/
    `max_output_tokens` used to flow straight into `payload` unvalidated
    — the FIFTH recurrence of the "wrong-type value bypasses this
    module's own typed exceptions" class, this time on the payload side.
    `generate(input_text=object())` reached `json.dumps` deep inside
    httpx's own request encoding and raised a raw `TypeError`, outside
    `httpx.RequestError`/`httpx.StreamError` (the only types the retry
    loop's `except` catches) and therefore outside `generate()`'s own
    `Raises:` block too. Every guilt case below asserts ZERO network
    calls — the validation must reject before `payload` is even built,
    matching this file's own established pattern for constructor-time
    guards (see `TestR6_5CredentialFormatValidation`)."""

    async def test_guilt_non_str_input_text_raises_value_error_before_any_network_call(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("no network call should happen for a malformed input_text")

        client = _client_with_transport(handler)
        with pytest.raises(ValueError):
            await client.generate(input_text=object())
        await client.close()

    async def test_guilt_bytes_input_text_raises_value_error_before_any_network_call(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("no network call should happen for a malformed input_text")

        client = _client_with_transport(handler)
        with pytest.raises(ValueError):
            await client.generate(input_text=b"hi")
        await client.close()

    async def test_guilt_non_str_system_prompt_raises_value_error_before_any_network_call(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("no network call should happen for a malformed system_prompt")

        client = _client_with_transport(handler)
        with pytest.raises(ValueError):
            await client.generate(input_text="hi", system_prompt=123)
        await client.close()

    async def test_guilt_bool_max_output_tokens_raises_value_error_before_any_network_call(self):
        """Same bool-exclusion trap as every other numeric guard in this
        file — `bool` is a subtype of `int`."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("no network call should happen for a malformed max_output_tokens")

        client = _client_with_transport(handler)
        with pytest.raises(ValueError):
            await client.generate(input_text="hi", max_output_tokens=True)
        await client.close()

    async def test_guilt_zero_max_output_tokens_raises_value_error_before_any_network_call(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("no network call should happen for max_output_tokens=0")

        client = _client_with_transport(handler)
        with pytest.raises(ValueError):
            await client.generate(input_text="hi", max_output_tokens=0)
        await client.close()

    async def test_guilt_negative_max_output_tokens_raises_value_error_before_any_network_call(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("no network call should happen for a negative max_output_tokens")

        client = _client_with_transport(handler)
        with pytest.raises(ValueError):
            await client.generate(input_text="hi", max_output_tokens=-1)
        await client.close()

    async def test_innocence_valid_values_reach_the_network(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_text_response_payload("ok"))

        client = _client_with_transport(handler)
        result = await client.generate(input_text="hi", system_prompt="be nice", max_output_tokens=100)
        assert result.text == "ok"
        await client.close()

    async def test_innocence_none_system_prompt_and_max_output_tokens_reach_the_network(self):
        """`system_prompt=None` and `max_output_tokens=None` are both
        explicitly permitted (not just the defaults `""`/`2048`) — the
        guard rejects the WRONG type, not absence.

        R15-4 binding correction, 2026-08-15 (Kimi K3 round-15 review,
        LOW): this test used to assert only `result.text == "ok"` —
        vacuous on the specific claim the R14-2 docstring made about
        `max_output_tokens=None` (that it is "explicitly permitted"),
        because it never inspected the actual request body. It would
        have stayed green even if `payload` sent a literal
        `"max_output_tokens": null` to the API — which, before R15-4,
        is exactly what it DID do. Now captures the serialized body and
        asserts the key's ABSENCE when `None` is passed, matching the
        real wire contract R15-4 establishes: `None` means "omit the
        key", never "explicitly request a null token limit"."""
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_text_response_payload("ok"))

        client = _client_with_transport(handler)
        result = await client.generate(input_text="hi", system_prompt=None, max_output_tokens=None)
        assert result.text == "ok"
        assert "max_output_tokens" not in captured["body"]
        await client.close()


class TestR15_2ToolsListTypeValidation:
    """R15-2 (Kimi K3 round-15 review, MEDIUM): the SIXTH recurrence of
    the out-of-taxonomy class, on `tools`. `_validate_tools_allowlisted`
    iterates its argument TWICE — a one-shot iterator passes the first
    loop (shape-checking each entry) but is already EXHAUSTED by the
    second (the `unknown` comprehension), so `unknown` comes back empty
    no matter what the names actually were and the function returns as
    if every name had cleared the allowlist. This defeats the "empty
    allowlist rejects everything" invariant this file otherwise relies
    on, and the exhausted iterator then reaches `json.dumps` unchecked.
    `tools=object()` (not iterable at all) fails even earlier with a raw
    `TypeError` inside `_validate_tools_allowlisted` itself. Fixed:
    `tools is None or isinstance(tools, list)` validated BEFORE
    `_validate_tools_allowlisted` is ever called."""

    async def test_guilt_non_iterable_tools_raises_value_error_before_any_network_call(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("no network call should happen for a malformed tools argument")

        client = _client_with_transport(handler)
        with pytest.raises(ValueError):
            await client.generate(input_text="hi", tools=object())
        await client.close()

    async def test_guilt_one_shot_iterator_tools_raises_value_error_before_any_network_call(self):
        """The confirmed bypass scenario: an iterator that WOULD look
        like a single valid, allowlisted-sounding entry to the buggy
        double-iteration must still be rejected for its TYPE before
        `_validate_tools_allowlisted` ever gets a chance to be fooled by
        it."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("no network call should happen for a malformed tools argument")

        client = _client_with_transport(handler)
        with pytest.raises(ValueError):
            await client.generate(input_text="hi", tools=iter([{"name": "crm_query"}]))
        await client.close()

    async def test_innocence_real_list_with_unknown_name_still_raises_tool_not_allowed(self):
        """A genuine `list` (this file's own established shape) must
        reach `_validate_tools_allowlisted` exactly as before — the new
        type guard must not intercept or change the behavior for the
        case it was never meant to touch."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("must never reach the network when every tool is rejected")

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIToolNotAllowedError):
            await client.generate(input_text="hi", tools=[{"name": "crm_query"}])
        await client.close()

    async def test_innocence_none_and_empty_list_tools_reach_the_network_unchanged(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_text_response_payload("ok"))

        client = _client_with_transport(handler)
        result_none = await client.generate(input_text="hi", tools=None)
        assert result_none.text == "ok"
        result_empty = await client.generate(input_text="hi", tools=[])
        assert result_empty.text == "ok"
        await client.close()


class TestModelAllowlist:
    """K2 (2026-08-15 audit): "approved candidates" / "sol is
    ceiling-only" were previously only comments — `model=` and
    `OPENAI_RESPONSES_MODEL` accepted ANY string, with zero enforcement
    before the network call. `_RUNTIME_MODEL_CANDIDATES` is the real
    spend/model control now."""

    async def test_arbitrary_model_string_rejected_before_network_call(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("must never reach the network with an unapproved model")

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIModelNotAllowedError):
            await client.generate(input_text="hi", model="gpt-5.6-nightly-experimental")
        await client.close()

    async def test_env_var_arbitrary_model_string_rejected(self, monkeypatch):
        """The same guard applies whether the model came from an explicit
        `model=` argument or from `OPENAI_RESPONSES_MODEL` — a stale/
        unreviewed slug set in the environment must not silently bypass
        the allowlist just because it wasn't passed as a kwarg."""
        monkeypatch.setenv("OPENAI_RESPONSES_MODEL", "gpt-4-turbo-preview")

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("must never reach the network with an unapproved env-configured model")

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIModelNotAllowedError):
            await client.generate(input_text="hi")
        await client.close()

    async def test_sol_accepted_when_explicitly_requested(self):
        """`MODEL_SOL` stays a MEMBER of the allowlist — the policy is
        "only these three", not "sol may never be requested". The bench
        harness (`wa_blind_bench.py`) explicitly asks for it as the
        quality-ceiling reference; that call must keep working."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_text_response_payload("ok", model=MODEL_SOL))

        client = _client_with_transport(handler)
        result = await client.generate(input_text="hi", model=MODEL_SOL)
        await client.close()
        assert result.model == MODEL_SOL

    async def test_all_three_candidates_accepted(self):
        for candidate in (MODEL_SOL, MODEL_TERRA, MODEL_LUNA):

            def handler(request: httpx.Request, *, _model=candidate) -> httpx.Response:
                return httpx.Response(200, json=_text_response_payload("ok", model=_model))

            client = _client_with_transport(handler)
            result = await client.generate(input_text="hi", model=candidate)
            await client.close()
            assert result.model == candidate

    async def test_sol_from_env_var_rejected_zero_network_calls(self, monkeypatch):
        """K2 SECOND (2026-08-15, Kimi K3 round-2 refinement): `MODEL_SOL`
        stays a member of `_RUNTIME_MODEL_CANDIDATES`, but only for an
        EXPLICIT `generate(model=...)` call. A persistent
        `OPENAI_RESPONSES_MODEL=gpt-5.6-sol` in the environment is not an
        explicit per-call request — it must be rejected BEFORE any network
        call, with zero HTTP traffic, so a shell profile / systemd unit /
        `.env` setting can never silently route every call this client
        makes onto the most expensive tier."""
        monkeypatch.setenv("OPENAI_RESPONSES_MODEL", MODEL_SOL)

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("must never reach the network when sol is resolved via env, not explicit model=")

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIModelNotAllowedError) as exc_info:
            await client.generate(input_text="hi")
        await client.close()

        assert "sol_requires_explicit_request" in str(exc_info.value)

    async def test_sol_from_default_would_be_rejected_same_as_env(self):
        """Companion innocence-adjacent check: `DEFAULT_MODEL` itself is
        `MODEL_TERRA`, never `MODEL_SOL` (see the module-level constant) —
        this pins that invariant directly, since the env/default
        restriction above only protects the sol-from-env path if the
        default itself never resolves to sol in the first place."""
        assert DEFAULT_MODEL == MODEL_TERRA
        assert DEFAULT_MODEL != MODEL_SOL

    async def test_terra_from_env_var_accepted(self, monkeypatch):
        """Innocence: the env/default-resolution path is not blanket-
        blocked — `MODEL_TERRA`/`MODEL_LUNA` resolved via
        `OPENAI_RESPONSES_MODEL` (no explicit `model=`) must still work,
        exactly as an unset env var falling back to `DEFAULT_MODEL`
        already does (`test_default_model_is_terra_not_sol`)."""
        monkeypatch.setenv("OPENAI_RESPONSES_MODEL", MODEL_TERRA)
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json=_text_response_payload("ok", model=MODEL_TERRA))

        client = _client_with_transport(handler)
        result = await client.generate(input_text="hi")
        await client.close()

        assert captured["body"]["model"] == MODEL_TERRA
        assert result.model == MODEL_TERRA

    async def test_unhashable_model_value_rejected_before_network_call(self):
        """MEDIUM binding correction, 2026-08-15 (Kimi K3, live-gate round
        5, point C): `model_name not in allowed_candidates` performs `in`
        on the raw, possibly-unhashable value — `model=[]` (or any list/
        dict) raised a bare `TypeError: unhashable type` instead of the
        typed `OpenAIModelNotAllowedError` every other malformed-model
        path in this class produces. Guilt: zero network calls, and the
        raised error is the module's own typed exception, not a raw
        `TypeError` leaking implementation detail to the caller."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("must never reach the network with an unhashable model value")

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIModelNotAllowedError) as exc_info:
            await client.generate(input_text="hi", model=[])
        await client.close()

        assert "malformed_model_type" in str(exc_info.value)
        assert "list" in str(exc_info.value), "the error names the offending TYPE"

    async def test_unhashable_model_value_never_echoes_raw_value(self):
        """The raw caller-supplied value could be large/awkward (a list
        embedding arbitrary content) — the fix cites only
        `type(model_name).__name__`, never the value itself. Plants a
        marker inside the unhashable value and confirms it never surfaces
        in the exception's message."""
        secret_marker = "MODEL_VALUE_MARKER_NEVER_ECHOED"

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("must never reach the network with an unhashable model value")

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIModelNotAllowedError) as exc_info:
            await client.generate(input_text="hi", model=[secret_marker])
        await client.close()

        assert secret_marker not in str(exc_info.value)

    async def test_unknown_string_model_still_gets_original_refusal_not_malformed_type(self):
        """Innocence for point C: the new `isinstance(model_name, str)`
        guard must not change behaviour for an unknown-but-VALID-type
        model string — it still hits the pre-existing unknown-name
        refusal path (same as
        `test_arbitrary_model_string_rejected_before_network_call`), not
        the new malformed-type branch. Asserted explicitly here so a
        future edit that widens the type guard's scope (e.g. by mistake
        matching on more than non-str) would be caught."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("must never reach the network with an unapproved model")

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIModelNotAllowedError) as exc_info:
            await client.generate(input_text="hi", model="gpt-5.6-nightly-experimental")
        await client.close()

        assert "malformed_model_type" not in str(exc_info.value), (
            "an unknown but well-typed string model must not be misreported as a type error"
        )


class TestErrorHandling:
    async def test_invalid_json_body_raises_response_shape_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=b"not json at all {{{", headers={"content-type": "application/json"})

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIResponseShapeError):
            await client.generate(input_text="hi")
        await client.close()

    async def test_non_retryable_4xx_raises_api_error_immediately(self):
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(401, json={"error": {"message": "invalid api key"}})

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIAPIError) as exc_info:
            await client.generate(input_text="hi")
        await client.close()

        assert exc_info.value.status_code == 401
        assert calls["n"] == 1, "a 401 must never be retried"

    async def test_http_100_continue_raises_api_error_never_parsed(self):
        """MEDIUM binding correction, 2026-08-15 (Kimi K3, live-gate round
        5, point E): `if response.status_code >= 400:` let ANY status
        below 400 — including a 1xx an intermediary sent through — fall
        straight into `response.json()` parsing, contradicting this
        module's own documented invariant ("HTTP 200 is necessary but not
        sufficient"). The gate is now strict on `!= 200`. The response
        body here is deliberately invalid JSON: if the fix regressed and
        this status were allowed through to the parser, the failure mode
        would be `OpenAIResponseShapeError` (a JSON-decode failure), NOT
        `OpenAIAPIError` — asserting the exact type (not just "raises")
        is what proves the parser was never reached."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                100,
                content=b"not json at all {{{",
                headers={"content-type": "application/json"},
            )

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIAPIError) as exc_info:
            await client.generate(input_text="hi")
        await client.close()

        assert exc_info.value.status_code == 100

    async def test_http_304_not_modified_raises_api_error_never_parsed(self):
        """Point E companion: a non-error, non-200 status this endpoint
        never legitimately returns (the Responses API only ever answers
        200 on success — a documented, deliberate design choice). Same
        invalid-JSON-body technique as the 100 case above: reaching
        `OpenAIAPIError` (not `OpenAIResponseShapeError`) proves the
        strict `!= 200` gate caught it before parsing."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                304,
                content=b"not json at all {{{",
                headers={"content-type": "application/json"},
            )

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIAPIError) as exc_info:
            await client.generate(input_text="hi")
        await client.close()

        assert exc_info.value.status_code == 304

    async def test_unexpected_status_category_for_sub_400_non_200(self):
        """Pins the `OpenAIAPIError` category classification for the
        newly-reachable <400 branch: neither `rate_limited` (429-only) nor
        `server_error` (>=500) nor `client_error` (400-499) applies to a
        1xx/2xx-non-200/3xx status, so it must fall into a distinct,
        descriptive category rather than silently reusing one of those or
        a generic 'unknown'."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(204)

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIAPIError) as exc_info:
            await client.generate(input_text="hi")
        await client.close()

        assert exc_info.value.status_code == 204
        assert exc_info.value.category == "unexpected_status"

    async def test_api_error_never_carries_remote_body(self):
        """The response body can echo request content back (e.g. a
        malformed-input 400) — it must never end up in the exception."""
        secret_marker = "CLIENT_PROMPT_ECHO_MARKER_1234"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                json={"error": {"message": f"bad input: {secret_marker}"}},
            )

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIAPIError) as exc_info:
            await client.generate(input_text="hi")
        await client.close()

        assert secret_marker not in str(exc_info.value)
        assert not hasattr(exc_info.value, "body")
        assert exc_info.value.category == "client_error"

    async def test_retryable_5xx_retries_then_succeeds(self):
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] < 3:
                return httpx.Response(503, text="temporarily unavailable")
            return httpx.Response(200, json=_text_response_payload("recovered"))

        client = _client_with_transport(handler)
        result = await client.generate(input_text="hi")
        await client.close()

        assert result.text == "recovered"
        assert result.attempts == 3
        assert calls["n"] == 3

    async def test_latency_ms_measures_only_the_successful_attempt_not_retry_overhead(self):
        """R7-7 binding correction, 2026-08-15 (Kimi K3 round-7 review):
        `t0` used to be set ONCE before the whole retry loop, so
        `latency_ms` on a call that needed a retry included every backoff
        sleep AND every failed round-trip before the attempt that finally
        succeeded (observed live: ~1600ms reported for a ~100ms successful
        3rd attempt) — systematically inflating the reported latency for
        any candidate that merely hit a transient network/5xx blip, which
        matters because `scripts/bot/wa_blind_bench.py` reports this value
        per candidate. `t0` is now reset at the top of EVERY retry-loop
        iteration.

        Uses REAL wall-clock timing (same pattern as
        `test_retryable_5xx_retries_then_succeeds` above, which already
        pays the real ~1.5s backoff cost unmocked) rather than mocking
        `time.perf_counter`: that function is a process-wide singleton
        shared with asyncio/httpx internals (verified empirically — an
        earlier draft of this test patched it and broke unrelated
        machinery deep in the event loop with `StopIteration`), so it
        cannot be safely faked out from underneath just this one client.
        Real backoff between attempts 1→2 (0.5s) and 2→3 (1.0s) totals
        ~1.5s of real sleep BEFORE the successful 3rd attempt even starts.
        Pre-fix, `latency_ms` would measure from `t0` set before attempt 1
        and therefore be AT LEAST that ~1500ms; with the fix it measures
        only the successful (near-instant, no sleep) 3rd attempt's own
        round-trip — well under that floor."""
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] < 3:
                return httpx.Response(503, text="temporarily unavailable")
            return httpx.Response(200, json=_text_response_payload("recovered"))

        client = _client_with_transport(handler)
        result = await client.generate(input_text="hi")
        await client.close()

        assert result.attempts == 3
        assert result.latency_ms < 500, (
            f"latency_ms={result.latency_ms} looks like it included retry backoff "
            f"(~1500ms of real sleep occurred before the successful attempt) — the fix "
            f"resets the timer per attempt, so this should be near-instant"
        )

    async def test_retries_exhausted_raises_api_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, text="rate limited")

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIAPIError) as exc_info:
            await client.generate(input_text="hi")
        await client.close()

        assert exc_info.value.status_code == 429
        assert exc_info.value.category == "rate_limited"

    async def test_network_error_raises_distinct_exception(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        client = _client_with_transport(handler)
        with pytest.raises(OpenAINetworkError):
            await client.generate(input_text="hi")
        await client.close()

    async def test_network_error_and_api_error_are_distinct_types(self):
        """Callers must be able to tell 'never reached the API' from
        'API answered with an error status' without string-matching."""
        assert not issubclass(OpenAINetworkError, OpenAIAPIError)
        assert not issubclass(OpenAIAPIError, OpenAINetworkError)
        assert not issubclass(OpenAIResponseShapeError, OpenAIAPIError)
        assert not issubclass(OpenAIResponseShapeError, OpenAINetworkError)

    async def test_decoding_error_wrapped_as_network_error(self):
        """K1 (2026-08-15 audit): `httpx.DecodingError` is an
        `httpx.RequestError` but NOT an `httpx.TransportError` — the
        original `except (httpx.TimeoutException, httpx.TransportError)`
        would have let this rise RAW past the client, uncaught, unwrapped,
        and unretried. Verified against the installed httpx==0.28.1's
        actual exception hierarchy (not assumed) before writing this
        fix/test. `httpx.RequestError` is the correct common base."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.DecodingError("could not decode response body")

        client = _client_with_transport(handler)
        with pytest.raises(OpenAINetworkError):
            await client.generate(input_text="hi")
        await client.close()

    async def test_too_many_redirects_wrapped_as_network_error(self):
        """Second `httpx.RequestError` subclass that is not a
        `TransportError` — same gap, different concrete exception."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TooManyRedirects("too many redirects")

        client = _client_with_transport(handler)
        with pytest.raises(OpenAINetworkError):
            await client.generate(input_text="hi")
        await client.close()

    async def test_network_error_cause_is_none_not_original_exception(self):
        """K4 (2026-08-15 audit): an `httpx.RequestError`'s `.request`
        attribute carries the actual outgoing request — including this
        client's own `Authorization: Bearer <key>` header. `from exc`
        would leave that reachable via `__cause__` even though the
        exception's own message never echoes it. Plants a marker as the
        (fake) API key and confirms it survives nowhere in the cause
        chain, not just in the message.

        Live-gate addendum (2026-08-15): also asserts `__context__ is
        None` — `from None` alone leaves the implicit `__context__` Python
        sets during exception chaining populated (verified empirically);
        this client closes that specific gap by deferring the `raise`
        until after the except block exits rather than relying on `from
        None` alone."""
        secret_marker = "OPENAI_KEY_SECRET_MARKER_NEVER_IN_CAUSE"

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        client = _client_with_transport(handler, api_key=secret_marker)
        with pytest.raises(OpenAINetworkError) as exc_info:
            await client.generate(input_text="hi")
        await client.close()

        assert exc_info.value.__cause__ is None
        assert exc_info.value.__context__ is None
        assert secret_marker not in str(exc_info.value)

    async def test_json_decode_error_cause_is_none_not_original_exception(self):
        """K4 companion for the JSON-parse failure path —
        `json.JSONDecodeError.doc` carries the FULL raw response body that
        failed to parse. Plants a marker inside the invalid body and
        confirms it is reachable through neither the message nor
        `__cause__`.

        Live-gate addendum (2026-08-15): also asserts `__context__ is
        None`, same reasoning as the network-error companion above."""
        secret_marker = "RESPONSE_BODY_SECRET_MARKER_NEVER_IN_CAUSE"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=f"not json at all {{{{ {secret_marker}".encode(),
                headers={"content-type": "application/json"},
            )

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIResponseShapeError) as exc_info:
            await client.generate(input_text="hi")
        await client.close()

        assert exc_info.value.__cause__ is None
        assert exc_info.value.__context__ is None
        assert secret_marker not in str(exc_info.value)

    async def test_request_not_read_wrapped_as_network_error(self):
        """K1 SECOND (2026-08-15, Kimi K3 round-2 refinement): `httpx.
        StreamError` (base of `RequestNotRead`/`ResponseNotRead`/
        `StreamClosed`/`StreamConsumed`) inherits from `RuntimeError`
        directly, NOT from `httpx.RequestError` — verified against the
        installed httpx==0.28.1's actual exception hierarchy (not assumed)
        before writing this fix/test: `isinstance(httpx.RequestNotRead(),
        httpx.RequestError)` is `False`. The original
        `except httpx.RequestError` alone would have let this rise raw,
        unwrapped and unretried, straight out of `generate()` on a
        `client.post()` that never finished sending.

        Live-gate addendum (2026-08-15): a bare `pytest.raises(TYPE)` proves
        the type is caught but not that K4's no-leak discipline extends to
        this NEW except branch. Asserts `__cause__ is None` AND
        `__context__ is None` — `from None` alone only sets `__cause__` and
        `__suppress_context__`, it does NOT clear the implicit `__context__`
        Python populates during exception chaining (verified empirically:
        raising inside this except block left `err.__context__ is exc` true
        even with `from None`). The client defers the actual `raise`
        statement until immediately after the except block exits — verified
        empirically that this leaves `__context__` genuinely `None`, not
        just display-suppressed — and this test pins that. Also asserts the
        local message is built ONLY from `type(exc).__name__` (never httpx's
        own fixed internal string, even though that string isn't
        remote-influenced content — the discipline is "local category
        literals only", not "unless the source happens to be safe this
        time"). `httpx.RequestNotRead` doesn't accept a custom message
        argument (verified: `TypeError` on `RequestNotRead("marker")`), so a
        planted-marker variant isn't possible here; the fixed-httpx-string
        absence check is the practical equivalent."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.RequestNotRead()

        client = _client_with_transport(handler)
        with pytest.raises(OpenAINetworkError) as exc_info:
            await client.generate(input_text="hi")
        await client.close()

        assert exc_info.value.__cause__ is None
        assert exc_info.value.__context__ is None
        assert str(exc_info.value) == "transport failure: RequestNotRead"
        assert "streaming request content" not in str(exc_info.value), (
            "httpx's own internal message text must never leak into the local exception"
        )

    async def test_response_json_decoding_error_wrapped_as_response_shape_error(self, monkeypatch):
        """K1 SECOND companion (2026-08-15, Kimi K3 round-2 refinement):
        `response.json()` can itself raise `httpx.DecodingError` — distinct
        from invalid JSON syntax (`json.JSONDecodeError`, a `ValueError`,
        already covered by `test_invalid_json_body_raises_response_shape_error`)
        and from a transport-level failure at `client.post()` (already
        covered above). The previous `except ValueError` around
        `response.json()` would have let a `DecodingError` raised at THIS
        call site rise raw. `httpx.Response.json` is patched directly to
        isolate this specific call site.

        Comment corrected 2026-08-15 (live-gate round 5, Kimi K3): an
        earlier version of this comment claimed a real
        encoding/content-encoding failure "is a property of the transport
        layer that a MockTransport fake does not reproduce" — that was
        FALSE, verified empirically by driving a `MockTransport` handler
        that returns a `content-encoding: gzip` header over non-gzip
        bytes: it DOES raise a genuine `httpx.DecodingError`, but it does
        so from `client.post()` itself (httpx reads/decodes the body
        eagerly for a non-streaming request, before `post()` even
        returns), which is already covered by the transport-level except
        clause above, not from `response.json()`. This test therefore
        exercises a DEFENSIVE branch that is likely UNREACHABLE via any
        real httpx failure mode in this client's non-streaming flow — the
        direct `httpx.Response.json` patch is how it's reached at all.
        The catch stays (defense in depth costs nothing here and the
        `.json()` call is a plausible future site for such an error even
        if today's httpx doesn't raise one there for this flow), but the
        justification for testing it this way is "the only way to reach
        this specific line", not "MockTransport can't produce the real
        error".

        Original rationale for why the test still matters, unchanged: the
        branch under test only cares that `generate()` catches
        `httpx.DecodingError` wherever `response.json()` raises it from.

        Live-gate addendum (2026-08-15): plants a unique marker inside the
        `DecodingError`'s own message (standing in for whatever a real
        decode failure might embed, e.g. a body excerpt) and asserts the
        marker survives in NEITHER the local exception's message NOR its
        `__cause__` NOR its `__context__` — `from None` alone leaves
        `__context__` populated (verified empirically), so this also pins
        that the client defers its `raise` until after the except block
        exits specifically to close that gap, not just suppress its
        display. This test must fail if a future edit reintroduces
        `from exc`, raises directly inside the except block, or interpolates
        the remote/original exception's text."""
        secret_marker = "LEAK-MARKER-BODY-SECRET-XYZ"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_text_response_payload("irrelevant"))

        def _raise_decoding_error(self) -> dict:
            raise httpx.DecodingError(f"could not decode response body: {secret_marker}")

        monkeypatch.setattr(httpx.Response, "json", _raise_decoding_error)

        client = _client_with_transport(handler)
        with pytest.raises(OpenAIResponseShapeError) as exc_info:
            await client.generate(input_text="hi")
        await client.close()

        assert exc_info.value.__context__ is None

        assert exc_info.value.__cause__ is None
        assert secret_marker not in str(exc_info.value)


class TestUsageAccounting:
    async def test_usage_tokens_propagated(self):
        def handler(request: httpx.Request) -> httpx.Response:
            payload = _text_response_payload("ok")
            payload["usage"] = {"input_tokens": 123, "output_tokens": 45}
            return httpx.Response(200, json=payload)

        client = _client_with_transport(handler)
        result = await client.generate(input_text="hi")
        await client.close()

        assert result.input_tokens == 123
        assert result.output_tokens == 45


class TestR9_5GetClientTrustEnvRegression:
    """R9-5 (Kimi K3 round-9 review): `trust_env=False` (R8-12) had NO
    regression pin — every other test in this file goes through
    `_client_with_transport`, which builds its own `httpx.AsyncClient` by
    hand and never calls the real `_get_client()` at all, so a future drop
    of the `trust_env=False` kwarg would pass this entire suite while
    silently letting `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` route this
    client's `Authorization: Bearer <key>` traffic through an ambient
    proxy. This test exercises the REAL `_get_client()` method — the one
    every production caller actually uses via `generate()` — by
    monkeypatching `httpx.AsyncClient` in the client module to capture the
    kwargs it was constructed with, instead of faking the transport."""

    def test_get_client_constructs_asyncclient_with_trust_env_false(self, monkeypatch):
        captured_kwargs: dict = {}
        real_async_client = httpx.AsyncClient

        def _capturing_async_client(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return real_async_client(*args, **kwargs)

        monkeypatch.setattr(client_module.httpx, "AsyncClient", _capturing_async_client)

        client = OpenAIResponsesClient(api_key="test-key")
        # R14-4 binding correction, 2026-08-15 (Kimi K3 round-14 review):
        # `underlying` used to be assigned only INSIDE the `try` block,
        # while the `finally` below used it unconditionally. If
        # `client._get_client()` itself raised — precisely the regression
        # this test exists to pin — `underlying` would never be bound,
        # and the `finally` clause would then raise its own `NameError:
        # name 'underlying' is not defined`, MASKING the real exception
        # that should have failed this test. Pre-declared `None` here so
        # the `finally` below can tell "never got far enough to construct
        # a client" apart from "constructed one, must close it" and skip
        # cleanup on the former without ever raising a second, unrelated
        # error over the first.
        underlying = None
        try:
            underlying = client._get_client()
            assert captured_kwargs.get("trust_env") is False, (
                f"httpx.AsyncClient must be constructed with trust_env=False, "
                f"got trust_env={captured_kwargs.get('trust_env')!r} — a future drop of this "
                f"kwarg must turn this test red (R8-12: an ambient HTTP_PROXY/HTTPS_PROXY/"
                f"ALL_PROXY must never be able to silently redirect this client's traffic)"
            )
            assert captured_kwargs.get("timeout") == client.timeout
            limits = captured_kwargs.get("limits")
            assert isinstance(limits, httpx.Limits)
        finally:
            import asyncio

            if underlying is not None:
                asyncio.run(underlying.aclose())
