"""
OpenAI Responses API Client — OFFLINE, standalone provider adapter.

Council verdict this client implements (2026-08-15, cross-family panel —
see `research/operations/2026-08-15-adr-wa-runtime-openai-provider.md`):
NO-GO on using the ChatGPT Pro / Codex OAuth subscription as a WhatsApp
runtime credential; CONDITIONAL-GO on the OpenAI **API** with a
least-privilege project service account, key held server-side (or WIF),
and the **Responses API** (never Chat Completions) — Responses is the
API OpenAI is actively developing, carries first-class typed refusal /
tool-call items instead of overloading `finish_reason`, and is the
surface `wa_blind_bench.py` (`scripts/bot/`) is built against.

⚠️ THIS FILE HAS ZERO WIRING. Nothing in `backend/services/rag/agentic/`
or any other live module imports it. No config flag, no gateway branch,
no hot-path reference exists anywhere in this repo — grep it yourself
before trusting this comment. It is an offline component sitting behind
three gates (security review, Zero's business/cost GO, a real shadow-hook
design with context parity) — see the ADR §Non-goals / §Gates.

⚠️ DEDICATED CREDENTIAL, NOT THE EMBEDDINGS KEY (binding, restated
2026-08-15 by the lead orchestrator: this is non-negotiable, not a
preference). This client reads **`OPENAI_WA_PROVIDER_API_KEY`**
(`_ENV_VAR` below) — a name deliberately DISTINCT from
`Settings.openai_api_key`/`OPENAI_API_KEY`, which backs
`embedding_provider="openai"` (`text-embedding-3-small`, Golden Rule §9,
FROZEN) and is ALREADY a live Fly secret. No env var this client reads is
set anywhere today, so `available` is `False` everywhere until Zero
explicitly provisions a least-privilege project service-account key (or
WIF — see the ADR) under THIS name. Do not repoint `_ENV_VAR` at the
embeddings key to "make it work" — that reintroduces the exact identity/
billing collision an earlier draft was rejected for.

Design (Golden Rules #4/#8/#10):
    - httpx.AsyncClient persistent, created lazily, closed via `close()`
      (call from app lifespan — mirrors `OpenRouterClient`).
    - No SDK: OpenAI's Python SDK is not in this repo's dependency graph
      and CLAUDE.md §5 bans the Anthropic SDK on the same "no vendor SDK
      surprise" principle; a raw httpx client keeps the surface area (and
      the fake-at-the-HTTP-boundary testing story, W114) identical to
      every other provider in `backend/llm/providers/`.
    - `available` is a property, computed from the env key ONLY. Missing
      key -> `available=False`. The client NEVER raises on construction
      and NEVER crashes a caller that forgot to check `available` first
      (`generate()` raises `OpenAIClientUnavailableError`, a normal
      exception, not a crash).
    - **Fail-closed on response shape, not just on transport.** HTTP 200
      is necessary but not sufficient. `data["status"]` must be literally
      `"completed"` — `"failed"`, `"incomplete"`, `"cancelled"`, or any
      value this client does not recognise raises `OpenAIResponseShapeError`
      rather than being treated as a usable answer. `incomplete_details`
      (reason `max_output_tokens`, `content_filter`, or anything else) is
      the same class of error, never silently coerced into a shorter
      answer. Any `output` item whose `type`, or whose `content[].type`
      for a message item, is not one of the small set this parser
      recognises ALSO raises — an unrecognised shape is refused, not
      best-effort skipped, because a silently-dropped item is exactly how
      a real answer becomes a truncated one with nothing to say so.
    - Refusal is NOT an error. The Responses API can return HTTP 200,
      `status: "completed"`, with an output item of type "refusal" — this
      is content-level policy output, distinct from a transport failure,
      an API error status, or an incomplete/failed generation.
      `LLMResult.refusal` carries it explicitly; callers must check it,
      and this client NEVER folds refusal text into a success path — the
      same discipline CLAUDE.md §5 requires for Fable/Opus-5's own
      `stop_reason == "refusal"` gotcha.
    - **No remote body in exceptions or logs, ever.** `OpenAIAPIError`
      carries only the HTTP status code and a coarse category derived
      from it (`rate_limited` / `server_error` / `client_error` /
      `unknown`) — never `response.text`, never any parsed field from the
      body. The Responses API echoes request content back into error
      payloads on some 4xx shapes (e.g. malformed `input`), so a response
      body is not "just OpenAI's words" — it can contain a verbatim slice
      of whatever `input_text`/`instructions` this client sent, which may
      itself carry client-derived text. Logging or raising it would leak
      exactly the kind of thing this adapter exists to keep server-side.
    - **Tool policy is a positive allowlist, fail-closed on the WHOLE
      request, never a partial filter.** `generate(tools=...)` never
      forwards a caller-supplied tool list to the API verbatim. Every
      requested tool name is checked against `ALLOWED_TOOL_NAMES` (empty
      in this offline phase — nothing has been censito/reviewed for this
      adapter yet) BEFORE any network call; if even ONE requested name is
      not on the allowlist — a mixed list of some allowed, some unknown
      names included — `generate()` raises `OpenAIToolNotAllowedError` for
      the entire request. This is deliberately NOT "drop the unknown
      names, forward the rest": a caller that asked for tools and silently
      got a filtered subset back reads as success when it should read as
      a refusal (cicatrix family #3's under-match twin). With
      `ALLOWED_TOOL_NAMES` empty, this means: any `tools=` argument is a
      hard refusal today, by construction, not a runtime decision — the
      allowlist is the only thing that can ever change that, and it is
      empty on purpose.
    - Retries: max 2, exponential backoff, ONLY on transient failures
      (429, 5xx, network-level timeout/connect errors). 4xx (400/401/403/
      404) are not retried — retrying a bad request or a revoked key
      just burns quota for the same failure (cicatrix family #8 is about
      the opposite mistake — under-retrying real flaps; this is the
      other edge: retry-storm on your own mistakes is family #2's
      "green-but-broken" in a different color).

Scope boundary (explicit): this module is a pure provider — it turns
(prompt in) into (LLMResult out). It does not touch retrieval, abstention,
provenance, PricingTool/auth, PII handling, cache, routing, rate-limiting,
audit, or human handoff. It has no caller in this PR.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Single source for the env var this client reads — a DEDICATED credential,
# never the embeddings `OPENAI_API_KEY` (see module docstring). Renaming
# this must not silently repoint at that key.
_ENV_VAR = "OPENAI_WA_PROVIDER_API_KEY"

_RESPONSES_URL = "https://api.openai.com/v1/responses"

# Transient HTTP statuses worth a retry. 429 = rate limit, 5xx = server-side.
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

# Approved model candidates (CLAUDE.md §5 GPT-5.6 family, same slugs the
# Codex CLI cascade uses elsewhere in this repo). `MODEL_SOL` is the
# quality-CEILING reference for `wa_blind_bench.py` ONLY — it must never
# become a runtime/shadow default; doing so would silently spend the most
# expensive tier on every call this client makes. `MODEL_TERRA` (balanced)
# is the default; `MODEL_LUNA` (grunt/cheap) is available for cost-sensitive
# callers. None of these three has been benchmarked against this specific
# WA-bot task yet — that is `wa_blind_bench.py`'s job, not an assertion
# this module makes.
MODEL_SOL = "gpt-5.6-sol"
MODEL_TERRA = "gpt-5.6-terra"
MODEL_LUNA = "gpt-5.6-luna"
DEFAULT_MODEL = MODEL_TERRA

# K2 binding correction, 2026-08-15: "approved model candidates" and
# "sol is ceiling-only, never a runtime default" were, until this fix,
# ONLY comments — `generate()`'s `model` argument and the
# `OPENAI_RESPONSES_MODEL` env var both accepted any string at all. A
# typo'd model slug, a stale/deprecated model ID, or an env var pointed at
# an unreviewed/unbudgeted model would all have gone straight onto the
# wire with zero enforcement. This frozenset is the actual spend/model
# control: `generate()` rejects any `model_name` not in it BEFORE the
# network call. `MODEL_SOL`
# stays IN this set on purpose — the policy is "only these three may ever
# be requested", not "sol may never be requested"; `wa_blind_bench.py`
# explicitly asks for it as the bench's quality-ceiling reference. What
# this allowlist does NOT do (declared, not silently deferred): choosing
# WHICH of the three is appropriate for a given runtime call is future
# wiring's job (there is no live caller of `generate()` in this PR) — this
# is a coarse "one of the three reviewed candidates, nothing else" gate,
# not a per-call policy engine.
_RUNTIME_MODEL_CANDIDATES: frozenset[str] = frozenset({MODEL_SOL, MODEL_TERRA, MODEL_LUNA})

# K2 SECOND binding correction, 2026-08-15 (Kimi K3 round-2 refinement): the
# first K2 fix (above) treated `_RUNTIME_MODEL_CANDIDATES` as one flat
# allowlist regardless of HOW `model_name` was resolved — but that left
# "sol is ceiling-only, never a runtime/shadow default" (see the comment on
# `MODEL_SOL` above) enforced only for slugs OUTSIDE the three-candidate
# set, not for the specific case of `MODEL_SOL` itself reaching this client
# via `OPENAI_RESPONSES_MODEL` or `DEFAULT_MODEL`. An env var is not an
# explicit per-call request — a value set once (shell profile, systemd
# unit, `.env`) would silently route EVERY call this client makes onto the
# priciest tier with nobody having asked for that on any given call. This
# narrower set is what `generate()` checks `model_name` against when the
# model was resolved from the env var or `DEFAULT_MODEL` rather than passed
# explicitly; `MODEL_SOL` stays reachable, just only via an explicit
# `generate(model=MODEL_SOL)` call — see `generate()`'s model-resolution
# block below.
_ENV_OR_DEFAULT_MODEL_CANDIDATES: frozenset[str] = frozenset({MODEL_TERRA, MODEL_LUNA})

# Positive tool allowlist — refuse-all by default (see module docstring).
# Empty today: nothing has been reviewed/censito for this offline adapter.
# Adding a name here is a deliberate, reviewed act, never a side effect of
# a caller wanting a tool to work.
#
# SENTINEL (R16-4, 2026-08-15, DECLARE-NOT-FIX — precedent ADR §20): only
# a tool entry's `name` field is ever validated, by `_validate_tools_
# allowlisted` in `generate()` below — a dict entry's OTHER fields (e.g.
# `"parameters"`) are never checked for JSON-serializability. Today this
# is DORMANT: with this frozenset empty, `_validate_tools_allowlisted`
# rejects the entire request the moment `tools` is non-empty, regardless
# of what any other field contains — an entry never survives long enough
# for its non-`name` fields to matter. The moment a name is added HERE,
# that dormancy ends: `generate(tools=[{"name": "<allowed-name>",
# "parameters": object()}])` would pass the name check and reach
# `json.dumps` with an unvalidated `"parameters"` value — the same "a
# caller-supplied value of the wrong type/shape bypasses this module's own
# typed exception taxonomy" class as R14-2/R15-2, one level deeper into
# the entry. WHOEVER POPULATES THIS ALLOWLIST MUST ALSO ADD entry-field
# serializability validation (e.g. a `json.dumps`-round-trip check, or an
# explicit per-field schema) in `_validate_tools_allowlisted` or
# `generate()` BEFORE relying on a non-empty value here in production —
# this is a required companion change, not an optional hardening.
ALLOWED_TOOL_NAMES: frozenset[str] = frozenset()

# `status` values this client accepts as a genuinely finished, usable
# generation. Anything else — `failed`, `incomplete`, `cancelled`, or a
# value not in this set at all — is a typed error, never a best-effort
# read of whatever text happened to be present.
_ACCEPTED_STATUS = frozenset({"completed"})

# Every OTHER status/reason/type value this parser can classify into a
# fixed LOCAL literal for error messages/logs — used ONLY via
# `_local_category()` below, which returns one of these exact strings (or
# "unknown"), NEVER the remote value it compared against. This is the
# single mechanism enforcing "no remote value ever reaches an error
# message or a log line" for status/reason/item_type/part_type — see
# module docstring.
_KNOWN_NON_COMPLETED_STATUSES = frozenset({"failed", "incomplete", "cancelled", "queued", "in_progress"})
_KNOWN_INCOMPLETE_REASONS = frozenset({"max_output_tokens", "content_filter"})

# Output item / content-part types this parser recognises. Anything else
# raises `OpenAIResponseShapeError` rather than being silently skipped —
# a dropped item is exactly how a real answer goes missing without saying
# so.
#
# `reasoning` (P0, 2026-08-15): GPT-5.x models on the Responses API
# routinely emit a `type: "reasoning"` output item BEFORE the `message`
# item — confirmed against OpenAI's own migrate-to-responses guide, which
# shows a reasoning item (fields: `id`, `type`, `content`, `summary`, and
# optionally `encrypted_content`) preceding the message item in the typed
# `output` array. Before this fix, EVERY real GPT-5.x response would have
# hit the "unrecognised output item type" branch and raised — this parser
# had never actually accepted a live response from the model family this
# whole adapter targets. `reasoning` is recognised and then IGNORED for
# RESULT purposes (see the parsing loop below): its fields — `summary`,
# `content`, `encrypted_content` — ARE read, but ONLY for an
# isinstance()-only type check (micro-correction, 2026-08-15: an earlier
# draft of this comment claimed they are "never read", which was false —
# they are read into local variables to be type-checked; what never
# happens is a VALUE reaching `LLMResult`, an exception message, or a log
# line). No chain-of-thought text can escape this module through any
# observable channel. A
# response consisting of `reasoning` alone (no message/refusal/tool_call)
# still falls through to the existing "completed response produced no
# text, refusal, or tool call" error — recognising the item type is not
# the same as treating it as a satisfying answer.
_KNOWN_OUTPUT_ITEM_TYPES = frozenset({"message", "function_call", "refusal", "reasoning"})
_KNOWN_MESSAGE_CONTENT_TYPES = frozenset({"output_text", "refusal"})


def _local_category(value: Any, known: frozenset[str]) -> str:
    """Classify a REMOTE-controlled value against a fixed LOCAL set of
    literals, for use in error messages and logs only.

    Returns one of `known`'s own string members when `value` matches it
    exactly, or the literal `"unknown"` otherwise — never `value` handed
    back verbatim as an object, and never anything for a non-match. This
    is deliberately conservative: even a value that superficially "is"
    one of the known strings only ever surfaces here as our own constant,
    so nothing OpenAI wrote (arbitrary length, encoding, or content) can
    ride along into a log line or exception message under the guise of a
    status/reason/type. Binding correction, 2026-08-15: an earlier draft
    interpolated the raw remote value directly (`{status!r}` etc.) — this
    function is the fix, not a wrapper around the old behaviour.
    """
    if isinstance(value, str):
        for k in known:
            if k == value:
                return k
    return "unknown"


class OpenAIClientUnavailableError(RuntimeError):
    """Raised by `generate()` when no API key is configured.

    Callers must check `.available` before calling `generate()` in any
    hot path; this exception exists so a caller that skips the check
    fails loudly instead of the client crashing with an AttributeError
    or sending an unauthenticated request.
    """


class OpenAINetworkError(RuntimeError):
    """Transport-level failure: DNS, connect, TLS, timeout — never reached
    OpenAI's API. Distinct from `OpenAIAPIError` per the fail-closed
    contract above.
    """


class OpenAIAPIError(RuntimeError):
    """OpenAI's API answered with anything other than the one status this
    client treats as success (HTTP 200 exactly — binding correction,
    2026-08-15, live-gate round 5: the Responses API never uses 201/204/
    3xx for this endpoint, so `generate()` gates on `!= 200`, not `>= 400`;
    this class's job is naming what kind of "not 200" it was).

    Carries ONLY the status code and a coarse category — NEVER the
    response body (see module docstring "No remote body in exceptions or
    logs, ever"). A category string is derived purely from the numeric
    code, so nothing OpenAI wrote can end up in this exception's message.
    """

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        if status_code == 429:
            self.category = "rate_limited"
        elif status_code >= 500:
            self.category = "server_error"
        elif status_code >= 400:
            self.category = "client_error"
        else:
            # 1xx, a non-200 2xx (201/204/...), or a 3xx — none of these
            # are ever a genuine Responses-API success, but they also
            # aren't a 4xx/5xx error status either; "unexpected_status" is
            # more precise than a bare "unknown" fallback would be (binding
            # correction, 2026-08-15: this branch was unreachable before
            # `generate()` gated on `>= 400`, so it had never actually
            # needed to name this class of code).
            self.category = "unexpected_status"
        super().__init__(f"OpenAI API error: status={status_code} category={self.category}")


class OpenAIResponseShapeError(RuntimeError):
    """The API returned HTTP 200 but the body was not a usable, finished
    generation: invalid JSON, `status` not `"completed"`,
    `incomplete_details` present, `output` missing/not-a-list/empty, an
    output item or message content part that isn't a JSON object, an
    output item/content-part type this parser doesn't recognise, a
    `function_call` for a tool the request never offered, or a
    `"completed"` response with no text/refusal/tool_call at all. Every
    message is built ONLY from local category literals (`_local_category`)
    — never the remote status/reason/type value itself.
    """


class OpenAIModelNotAllowedError(RuntimeError):
    """`generate()` was called (explicitly, or via `OPENAI_RESPONSES_MODEL`)
    with a model slug not in `_RUNTIME_MODEL_CANDIDATES` (K2 binding
    correction, 2026-08-15). Mirrors `OpenAIToolNotAllowedError`'s
    positive-allowlist shape: this is a spend/scope control on CALLER
    input, not a remote-value guard, so the rejected model name is safe to
    include in the message (it originates from this process's own code or
    its own environment, never from OpenAI's response)."""


class OpenAIToolNotAllowedError(RuntimeError):
    """`generate(tools=...)` was called with at least one tool name not in
    `ALLOWED_TOOL_NAMES`. FAIL-CLOSED ON THE WHOLE REQUEST: a mixed list
    (some names allowed, some not) is refused in full — this client never
    silently filters a tools list down to the allowed subset and forwards
    the rest, because that reads as success to the caller when it should
    read as a refusal (cicatrix family #3, guard-over-match's under-match
    twin). With the allowlist empty (default), ANY non-empty `tools`
    argument raises this.
    """


class OpenAICredentialFormatError(RuntimeError):
    """R6-5 binding correction (Kimi K3 round-6 review): a resolved API
    key containing non-ASCII characters or control characters used to
    escape this module's own typed-exception taxonomy entirely. `httpx`
    encodes header VALUES as latin-1 (per RFC 7230); building the
    `Authorization: Bearer <key>` header via `_headers()`'s f-string with
    a key containing e.g. 'é' raises a raw `UnicodeEncodeError` deep
    inside httpx's header-construction path — never caught by any of
    `OpenAIClientUnavailableError` / `OpenAINetworkError` /
    `OpenAIAPIError` / `OpenAIResponseShapeError`, all of which this
    module's docstring and `generate()`'s own `Raises:` section present as
    the COMPLETE set of ways this client can fail. A caller written
    against that list (reasonably — it is documented as exhaustive) would
    have an uncaught, undocumented exception type reach it.

    `generate()` now validates the resolved key BEFORE any network call
    (see `_validate_api_key_ascii`) and raises this typed error instead —
    zero HTTP calls are made, and the message states ONLY the fact and a
    coarse category, NEVER any byte of the key itself (not even its
    length, which alone can fingerprint some key formats) — the same
    "no remote/sensitive content in exceptions or logs" discipline this
    module already applies to API response bodies (see module docstring,
    "No remote body in exceptions or logs, ever").
    """

    def __init__(self, category: str) -> None:
        self.category = category
        super().__init__(
            f"resolved API key failed a pre-network format check "
            f"(category={category}) — refusing before any network call. "
            f"No key content, including length, is included in this message.",
        )


@dataclass(frozen=True)
class ToolCall:
    """One function/tool call the model asked to make."""

    call_id: str
    name: str
    arguments: str  # raw JSON string, as returned by the API — callers parse


@dataclass(frozen=True)
class LLMResult:
    """Provider-neutral envelope. Deliberately NOT importing/extending
    `backend.llm.base.LLMResponse` here — that dataclass has no refusal or
    tool_calls fields and is Gemini/OpenRouter-shaped; reshaping it is a
    separate, cross-provider change out of scope for an unwired adapter.
    """

    text: str
    refusal: bool
    refusal_reason: str | None
    tool_calls: tuple[ToolCall, ...]
    input_tokens: int
    output_tokens: int
    model: str
    # Round-trip time of the SINGLE attempt that produced this result only
    # (R7-7 binding correction, 2026-08-15, Kimi K3 round-7 review) — never
    # includes retry backoff sleeps or earlier failed attempts' round-trip
    # time. `generate()` resets its timer at the top of every retry-loop
    # iteration for exactly this reason; see that loop for the measurement
    # site. Before this fix the timer started once before the whole retry
    # loop, so a call that succeeded on e.g. its 3rd attempt reported the
    # sum of both backoff sleeps plus both failed round-trips plus the
    # successful one — inflating this field for any candidate that merely
    # hit a transient network/5xx blip.
    #
    # R8-3 binding correction, 2026-08-15 (Kimi K3 round-8 review): the
    # line above used to claim "scripts/bot/wa_blind_bench.py reports this
    # value per candidate" — FALSE at the time it was written (zero
    # occurrences of `latency_ms` in that file). Since R8-3,
    # `wa_blind_bench.py::_run_one_fixture` records this field per
    # response in the KEY FILE's `key_row` (`label_key.local.jsonl`) —
    # deliberately NEVER in the blind transcript, where a distinctive
    # per-model latency profile could itself de-blind a response.
    latency_ms: float
    # Number of attempts actually sent to the API (1 = no retry needed).
    attempts: int = 1
    finish_reason: str | None = None
    raw_response_id: str | None = None


# R6-5: control characters (0x00-0x1F, 0x7F) can break HTTP header parsing
# or enable header injection even on an otherwise-ASCII key — a check for
# `str.isascii()` alone would let e.g. an embedded `\r\n` through, which
# is a distinct (and worse) failure mode than the `UnicodeEncodeError`
# this whole guard exists to convert into a typed error.
_API_KEY_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")


def _validate_api_key_ascii(api_key: str) -> None:
    """Pre-network format check on the RESOLVED API key (R6-5 binding
    correction, Kimi K3 round-6 review). `_headers()` builds the
    `Authorization: Bearer <key>` header via an f-string, and `httpx`
    encodes header VALUES as Latin-1 per RFC 7230 — a key containing any
    non-ASCII character (Latin-1 is a superset of ASCII, but a resolved
    credential should never legitimately need anything past ASCII, and
    treating "not ASCII" as the refusal boundary is simpler and stricter
    than "not Latin-1 encodable") raises a raw `UnicodeEncodeError`
    from deep inside httpx's header-construction code — a failure mode
    this module's exception taxonomy (`OpenAIClientUnavailableError` /
    `OpenAINetworkError` / `OpenAIAPIError` / `OpenAIResponseShapeError`)
    never named and `generate()`'s own `Raises:` docstring never promised.

    Called from `generate()` BEFORE any network call, so a malformed key
    is refused with ZERO HTTP traffic — no wasted request, no partial
    connection attempt. Raises `OpenAICredentialFormatError` with a coarse
    category only; the key's content — including its length, which alone
    can fingerprint some key formats — never appears in the exception
    message, the same "no sensitive content in exceptions or logs"
    discipline this module already applies to remote response bodies."""
    if not api_key.isascii():
        raise OpenAICredentialFormatError("non_ascii_key")
    if _API_KEY_CONTROL_CHAR_RE.search(api_key):
        raise OpenAICredentialFormatError("control_char_key")


def _validate_tools_allowlisted(tools: list[dict[str, Any]]) -> None:
    """Fail closed on the WHOLE request if ANY requested tool name is not
    in `ALLOWED_TOOL_NAMES` — a mixed list (some allowed, some not) is
    refused in full, never silently filtered down to the allowed subset.
    Partial filtering was this function's first (wrong) shape: it dropped
    disallowed tools and forwarded the rest, which is indistinguishable
    from success to the caller when the correct behaviour is an explicit
    refusal (binding correction, 2026-08-15).

    Raises `OpenAIToolNotAllowedError` if `tools` is non-empty and at
    least one name is not allowlisted. Tool names here are CALLER-supplied
    (this process's own code calling `generate(tools=...)`), not remote
    API response content, so including them in the exception message does
    not violate the no-remote-value rule that governs status/reason/
    item_type/part_type.

    LOW binding correction, 2026-08-15 (Kimi K3): a `tools` entry that
    isn't a dict at all (e.g. a bare string) made `t.get("name")` raise a
    raw `AttributeError` instead of a typed, pre-network refusal — this
    function's own contract ("fail closed on the WHOLE request") was
    itself unguarded against a malformed LIST shape, not just malformed
    NAMES within it. Raises `OpenAIToolNotAllowedError` here too (not a
    new/separate exception class) — a non-dict entry means this `tools=`
    call cannot be honored at all, the same practical outcome as an
    unknown name, so it is refused through the same type rather than
    inventing a second category for what the caller experiences
    identically (`generate()` never sends the request either way).

    Same-class binding correction, 2026-08-15 (Kimi K3, live-gate on the
    frozen diff): the non-dict-ENTRY guard above did not cover a dict
    entry whose `name` value is itself unhashable (a list or dict) — the
    `unknown = sorted({... for t in tools if t.get("name") not in
    ALLOWED_TOOL_NAMES})` comprehension performs `in` against
    `ALLOWED_TOOL_NAMES` (a frozenset) on the RAW `t.get("name")` value
    BEFORE the `str()` wrapping that only happens on the emitted set
    element, not on the membership test itself — the same "unhashable
    value reaches `in` on a frozenset" class this module's `_parse_
    responses_payload` gates were just hardened against, here on the
    CALLER side. Every entry's `name` is now validated `isinstance(...,
    str)` in the same loop that already checks the entry itself is a
    dict — an absent `name` key (`t.get("name")` returning `None`) is
    caught by the same check, since a tool entry without a name can never
    be validated against the allowlist either way. `name` is
    CALLER-supplied like the entry itself, so a well-formed string name
    is still safe to echo; a malformed (non-string) one is described only
    by its Python type, never its value.
    """
    for t in tools:
        if not isinstance(t, dict):
            raise OpenAIToolNotAllowedError(
                "tools entry is not a JSON object — ENTIRE request refused, "
                "no partial forwarding (category=malformed_tool_entry)",
            )
        name = t.get("name")
        if not isinstance(name, str):
            raise OpenAIToolNotAllowedError(
                f"tools entry 'name' is not a string (got {type(name).__name__}) — "
                f"ENTIRE request refused, no partial forwarding "
                f"(category=malformed_tool_name)",
            )
    # Every `t["name"]` is now guaranteed a `str` by the loop above, so the
    # `in` check here is membership-safe (never reaches a raw unhashable
    # value) and `t["name"]` (not `.get`) is safe too — every entry was
    # already confirmed to have a string name.
    unknown = sorted({t["name"] for t in tools if t["name"] not in ALLOWED_TOOL_NAMES})
    if unknown:
        raise OpenAIToolNotAllowedError(
            f"tool(s) not on ALLOWED_TOOL_NAMES — ENTIRE request refused, no partial "
            f"forwarding: {unknown}. This adapter is offline-phase with an empty "
            f"allowlist by design — see module docstring.",
        )


# Sentinel distinguishing "no default was passed" from "the caller
# explicitly wants `None`/some other falsy default" — a plain `default:
# str | None = None` couldn't tell those apart. `_get_str_field` is
# REQUIRED by default (A2 binding correction, 2026-08-15): the first draft
# defaulted every field to `""` when the key was absent, which meant a
# `function_call` missing `call_id`/`arguments` entirely silently passed
# through as a valid-looking-but-empty string rather than failing closed
# on the missing field — indistinguishable from a server that genuinely
# sent an empty string. Only a caller that explicitly passes `default=`
# opts out of that.
_REQUIRED_STR_FIELD = object()


def _get_str_field(
    item: dict[str, Any],
    key: str,
    field_label: str,
    *,
    default: Any = _REQUIRED_STR_FIELD,
) -> str:
    """Read `item[key]`. Raises `OpenAIResponseShapeError` if the key is
    ABSENT and no `default` was passed (REQUIRED by default — see
    `_REQUIRED_STR_FIELD` above), or if the value that ends up being used
    (present, or an explicitly-passed `default`) is not a `str` — never
    silently coerces (`str(123)` would hide a malformed remote shape from
    every caller downstream) and never echoes the value itself, only the
    local `field_label` literal, into the exception message (P1 binding
    correction, 2026-08-15: a `function_call`'s `name`/`call_id`/
    `arguments` must be validated as strings BEFORE a membership check or
    dataclass construction sees them). None of this module's current call
    sites pass an explicit `default` — all three `function_call` fields
    are required per the second binding correction (A2, 2026-08-15); the
    parameter exists for a future caller with a genuinely optional string
    field, not for these three.

    Micro binding correction, 2026-08-15 (Kimi K3, live-gate round 5): the
    "(present, or an explicitly-passed `default`)" claim above was true in
    WORDS but not in CODE — the absent-key branch returned `default`
    unchecked, so a future caller passing a non-`str` `default` (or a
    typo'd `None`) would have silently broken this function's own `-> str`
    return-type promise, with no error until something downstream choked
    on the wrong type. Made the docstring true rather than weakened: the
    absent-key-with-explicit-default branch now runs the SAME isinstance
    check as the present-value branch below."""
    if key not in item:
        if default is _REQUIRED_STR_FIELD:
            raise OpenAIResponseShapeError(f"{field_label} is missing (category=malformed_field)")
        if not isinstance(default, str):
            raise OpenAIResponseShapeError(f"{field_label} default is not a string (category=malformed_field)")
        return default
    value = item[key]
    if not isinstance(value, str):
        raise OpenAIResponseShapeError(f"{field_label} is not a string (category=malformed_field)")
    return value


def _extract_refusal_reason(source: dict[str, Any], *keys: str) -> str:
    """Pick the first candidate field for a refusal reason from `source`,
    checked in `keys` order.

    A3 binding correction, 2026-08-15: the first draft used `if value:`
    (truthiness) to decide whether a candidate counted, which conflated
    "key absent" with "key present but falsy" — a present-but-malformed
    `{"refusal": 0}` or `{"refusal": {}}` would have been silently
    SKIPPED rather than rejected, falling through to the next key or the
    "refused" fallback as if nothing had been sent at all. The rule this
    function actually enforces now: a key that is ABSENT, or explicitly
    `None`, or an empty string, means "no reason given via this key" and
    the next candidate (or the fallback) is tried — but a key that is
    PRESENT with any other non-string value is a malformed shape and
    raises `OpenAIResponseShapeError`, regardless of whether that value
    happens to be falsy in Python (`0`, `False`, `[]`, `{}` all raise).
    Only `None` and `""` are treated as "equivalent to absent" — both
    are declared choices, not omissions: `None` is the natural
    "explicitly nothing" JSON value, and an empty string is syntactically
    a valid `str` but carries no actual reason to report.

    Falls back to the local literal `"refused"` only when no candidate key
    held a usable (non-None, non-empty-string) value at all — mirrors the
    original chain's final `or "refused"` for the true "nothing was ever
    sent" case."""
    for key in keys:
        if key not in source:
            continue
        value = source[key]
        if value is None:
            continue
        if not isinstance(value, str):
            raise OpenAIResponseShapeError(
                "refusal reason field is not a string (category=malformed_field)",
            )
        if value == "":
            continue
        return value
    return "refused"


def _require_nonneg_int_or_zero(value: Any, field_label: str) -> int:
    """Validate a `usage` token count. Missing (`None`) defaults to `0` —
    matching the prior `int(usage.get(..., 0) or 0)` behaviour for an
    absent field. A present value raises `OpenAIResponseShapeError` unless
    it is a genuine non-negative `int` — `bool` is EXPLICITLY excluded
    even though `isinstance(True, int)` is `True` in Python (bool is an
    int subclass), because a remote `true`/`false` where a token count was
    expected is a malformed shape, not a value worth silently coercing to
    `0`/`1` (P1 binding correction, 2026-08-15)."""
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OpenAIResponseShapeError(f"{field_label} is not a non-negative integer (category=malformed_field)")
    return value


def _parse_responses_payload(
    data: dict[str, Any],
    *,
    model_requested: str,
    requested_tool_names: frozenset[str] = frozenset(),
) -> LLMResult:
    """Parse a Responses API JSON body into an `LLMResult`.

    Pure function (no I/O) so the parsing logic is unit-testable against
    fixture payloads without a network round-trip. FAIL-CLOSED on every
    axis: a non-dict body, a `status` other than `"completed"`, a present
    `incomplete_details`, a missing/non-list/empty `output`, a non-dict
    output item or content part, an unrecognised output-item/content-part
    type, a `function_call` whose `name`/`call_id`/`arguments` is not a
    string or for a tool name outside `requested_tool_names` (with
    `ALLOWED_TOOL_NAMES` empty by default, this means EVERY function_call
    is rejected today), a refusal reason field that is present but not a
    string, a `usage` token count that is present but not a non-negative
    `int` (a `bool` is explicitly rejected here — see
    `_require_nonneg_int_or_zero`), or a `"completed"` response that
    yields no text, no refusal, and no tool call at all. A `reasoning`
    output item (GPT-5.x models routinely emit one before the `message`
    item) is recognised and IGNORED for RESULT purposes (R19-5
    micro-correction, 2026-08-15: this docstring previously claimed "none
    of its fields are ever read", which was stale against the two prior
    corrections at `_KNOWN_OUTPUT_ITEM_TYPES`'s own comment and the
    parsing loop below — its fields ARE read into local variables, but
    ONLY for an isinstance()-only type check; no value ever reaches
    `LLMResult`, an exception message, or a log line) — so a
    `reasoning`-only response with no message/refusal/tool_call still
    raises the same "no text/refusal/tool call" error, it is not treated
    as a satisfying answer. `model`/`id` are the two
    exceptions to fail-closed: a present-but-wrong-typed value degrades to
    a local fallback (`model_requested`/`None`) rather than raising, since
    neither is safety-relevant the way a tool call or token count is.
    Every raised message carries only local category literals — see
    `_local_category` — never the remote value that triggered it.
    """
    if not isinstance(data, dict):
        raise OpenAIResponseShapeError("response body is not a JSON object")

    status = data.get("status")
    # MEDIUM binding correction, 2026-08-15 (Kimi K3 adversarial review on
    # the frozen 6a8ab5180..1be079571 diff): `x not in <frozenset>` requires
    # `x` to be HASHABLE — a remote `status` that is a list or dict (not
    # just "the wrong string") would have raised a raw, uncaught `TypeError:
    # unhashable type`, not the fail-closed `OpenAIResponseShapeError` this
    # module promises everywhere else. The `isinstance(status, str)` guard
    # short-circuits the `or` before Python ever evaluates the `in` check,
    # so a non-hashable value never reaches it. `_local_category` was
    # already isinstance-safe internally (it loops with `==`, never `in` on
    # a frozenset) — this fixes the CALLER's guard, not `_local_category`
    # itself.
    if not isinstance(status, str) or status not in _ACCEPTED_STATUS:
        category = _local_category(status, _KNOWN_NON_COMPLETED_STATUSES)
        raise OpenAIResponseShapeError(f"unusable response status (category={category})")

    incomplete_details = data.get("incomplete_details")
    # LOW binding correction, 2026-08-15 (Kimi K3): `if incomplete_details:`
    # used Python TRUTHINESS, which treats a present-but-malformed falsy
    # value (`incomplete_details: 0`, `""`, `[]`, `False`) as equivalent to
    # ABSENT — the whole branch was silently skipped, and a response OpenAI
    # explicitly flagged as incomplete (however oddly) would have been
    # accepted as a normal completed answer. A3's rule applies here too:
    # absent or explicit `None` means "nothing to report" (skip, unchanged);
    # ANY other present value — dict or not, truthy or not — is a shape
    # that must be processed/rejected, never silently waved through.
    if incomplete_details is not None:
        if isinstance(incomplete_details, dict):
            reason = incomplete_details.get("reason")
            reason_category = _local_category(reason, _KNOWN_INCOMPLETE_REASONS)
        else:
            reason_category = "malformed_incomplete_details"
        raise OpenAIResponseShapeError(f"response marked incomplete (reason_category={reason_category})")

    output_items = data.get("output")
    if not isinstance(output_items, list) or not output_items:
        raise OpenAIResponseShapeError("output field missing, not a list, or empty")

    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    refusal = False
    refusal_reason: str | None = None

    for item in output_items:
        if not isinstance(item, dict):
            raise OpenAIResponseShapeError("output item is not a JSON object")
        item_type = item.get("type")
        # MEDIUM binding correction, 2026-08-15 (Kimi K3, same class as the
        # `status` guard above): a remote `type` that is a list/dict is
        # unhashable — guard before the `in` check, never after.
        if not isinstance(item_type, str) or item_type not in _KNOWN_OUTPUT_ITEM_TYPES:
            raise OpenAIResponseShapeError("unrecognised output item type (category=unknown)")

        if item_type == "message":
            content_parts = item.get("content")
            if not isinstance(content_parts, list):
                raise OpenAIResponseShapeError("message item content is not a list")
            for part in content_parts:
                if not isinstance(part, dict):
                    raise OpenAIResponseShapeError("message content part is not a JSON object")
                part_type = part.get("type")
                # MEDIUM binding correction, 2026-08-15 (Kimi K3, same class
                # as the two guards above): a remote `type` that is a
                # list/dict is unhashable — guard before the `in` check.
                if not isinstance(part_type, str) or part_type not in _KNOWN_MESSAGE_CONTENT_TYPES:
                    raise OpenAIResponseShapeError(
                        "unrecognised message content part type (category=unknown)",
                    )
                if part_type == "output_text":
                    # LOW binding correction, 2026-08-15 (Kimi K3): `part.
                    # get("text", "")` degraded a genuinely ABSENT `text`
                    # key to an empty string — indistinguishable from a
                    # server that sent `"text": ""` on purpose, and
                    # inconsistent with this module's A2 doctrine
                    # (`_get_str_field`'s REQUIRED-by-default rule) applied
                    # everywhere else a string field is read from remote
                    # JSON. `"text" not in part` now fails closed exactly
                    # like a missing `function_call.name` already does;
                    # present-but-wrong-typed still raises as before.
                    if "text" not in part:
                        raise OpenAIResponseShapeError("output_text part is missing its text field")
                    text = part["text"]
                    if not isinstance(text, str):
                        raise OpenAIResponseShapeError("output_text part's text field is not a string")
                    text_parts.append(text)
                elif part_type == "refusal":
                    refusal = True
                    refusal_reason = _extract_refusal_reason(part, "refusal", "text")
        elif item_type == "function_call":
            # Fail closed on an UNEXPECTED tool call: with
            # ALLOWED_TOOL_NAMES empty (default) and therefore
            # requested_tool_names empty too, the server returning a
            # function_call for ANY name is unsolicited and rejected —
            # never silently handed to a caller who never offered a tool.
            # Type-validate name/call_id/arguments as strings BEFORE the
            # membership check and BEFORE constructing the dataclass (P1
            # binding correction, 2026-08-15) — a non-string value here
            # (int, dict, None-with-key-present) must never reach
            # `requested_tool_names` membership logic or a `ToolCall`
            # field typed as `str`.
            call_name = _get_str_field(item, "name", "function_call.name")
            if call_name not in requested_tool_names:
                raise OpenAIResponseShapeError(
                    "server returned a function_call the request never offered "
                    "(category=unexpected_tool_call)",
                )
            call_id = _get_str_field(item, "call_id", "function_call.call_id")
            arguments = _get_str_field(item, "arguments", "function_call.arguments")
            tool_calls.append(
                ToolCall(
                    call_id=call_id,
                    name=call_name,
                    arguments=arguments,
                ),
            )
        elif item_type == "refusal":
            # Some Responses payloads surface a top-level refusal item
            # rather than nesting it inside a message's content parts.
            refusal = True
            refusal_reason = _extract_refusal_reason(item, "refusal", "content")
        elif item_type == "reasoning":
            # Recognised-and-ignored by design (see _KNOWN_OUTPUT_ITEM_TYPES
            # comment above) — but "ignored" is not "unvalidated" (A1
            # binding correction, 2026-08-15). The mandate was to validate
            # the MINIMAL shape and then ignore it, not to skip validation
            # entirely: any dict with `type: "reasoning"`, however
            # malformed otherwise, was passing through silently before this
            # fix. Every check below is ISINSTANCE-only — a field's value IS
            # read into a local variable (micro-correction, 2026-08-15: this
            # comment previously claimed it is "never read", which was
            # inaccurate), but ONLY to type-check it; that local variable is
            # never interpolated into an error message or a log line, so
            # this still cannot leak
            # chain-of-thought content; it only confirms the shape looks
            # like a genuine reasoning item (per OpenAI's
            # migrate-to-responses guide: `id` str, `summary`/`content`
            # lists, optional `encrypted_content` str) before moving on.
            # Every field is OPTIONAL (a present-but-wrong-typed field
            # fails closed; an absent field does not) — the guide's example
            # shows `content`/`summary` as empty lists, not as guaranteed-
            # present keys.
            reasoning_id = item.get("id")
            if reasoning_id is not None and not isinstance(reasoning_id, str):
                raise OpenAIResponseShapeError(
                    "reasoning item id is not a string (category=malformed_reasoning_item)",
                )
            reasoning_summary = item.get("summary")
            if reasoning_summary is not None and not isinstance(reasoning_summary, list):
                raise OpenAIResponseShapeError(
                    "reasoning item summary is not a list (category=malformed_reasoning_item)",
                )
            reasoning_content = item.get("content")
            if reasoning_content is not None and not isinstance(reasoning_content, list):
                raise OpenAIResponseShapeError(
                    "reasoning item content is not a list (category=malformed_reasoning_item)",
                )
            reasoning_encrypted = item.get("encrypted_content")
            if reasoning_encrypted is not None and not isinstance(reasoning_encrypted, str):
                raise OpenAIResponseShapeError(
                    "reasoning item encrypted_content is not a string (category=malformed_reasoning_item)",
                )

    if not refusal and not tool_calls and not "".join(text_parts).strip():
        # A "completed" response with nothing to show for it — no text,
        # no refusal, no tool call — is an invalid/empty shape, not a
        # quietly successful empty answer.
        raise OpenAIResponseShapeError("completed response produced no text, refusal, or tool call")

    # LOW binding correction, 2026-08-15 (Kimi K3): `data.get("usage") or
    # {}` collapsed EVERY falsy value — a present-but-malformed `0`, `""`,
    # `[]`, or `False` — down to the same silent `{}` an absent/`None`
    # usage already gets, then a second `isinstance` check caught the
    # remaining non-dict-and-truthy cases (a non-empty list, a string) the
    # same way. Both branches hid a malformed `usage` behind the SAME
    # zero-token result a genuinely absent one produces. Absent/`None`
    # still means "no usage data given" (0-default, unchanged) — but
    # present-and-not-a-dict is now a fail-closed shape error, matching
    # the `incomplete_details` doctrine below (A3: absent/None is fine,
    # present-with-anything-else is not silently ignored).
    usage = data.get("usage")
    if usage is None:
        usage = {}
    elif not isinstance(usage, dict):
        raise OpenAIResponseShapeError("usage is present but not a JSON object (category=malformed_field)")

    # `model`/`id` get a LOCAL FALLBACK rather than raising on a malformed
    # shape (P1 binding correction, 2026-08-15) — unlike function_call
    # fields, refusal reason, and usage counts, these two are metadata
    # (logging/telemetry), not fields whose wrong type changes what a
    # caller does with the result, so a present-but-wrong-typed value
    # degrades to the same local default a MISSING value would already
    # get, instead of failing the whole response.
    model_value = data.get("model")
    model_out = model_value if isinstance(model_value, str) else model_requested
    id_value = data.get("id")
    id_out = id_value if isinstance(id_value, str) else None

    return LLMResult(
        text="".join(text_parts),
        refusal=refusal,
        refusal_reason=refusal_reason,
        tool_calls=tuple(tool_calls),
        input_tokens=_require_nonneg_int_or_zero(usage.get("input_tokens"), "usage.input_tokens"),
        output_tokens=_require_nonneg_int_or_zero(usage.get("output_tokens"), "usage.output_tokens"),
        model=model_out,
        latency_ms=0.0,  # filled in by the caller (generate()) after timing
        finish_reason=status,
        raw_response_id=id_out,
    )


class OpenAIResponsesClient:
    """Thin async wrapper over the OpenAI Responses API.

    Never instantiate more than one per process for real traffic — the
    persistent `httpx.AsyncClient` is the point, same as every other
    provider in this package. There is no live caller of this class in
    this repo today.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        """
        Raises:
            ValueError: `max_retries` is not a non-negative `int` (`bool`
                excluded, since `bool` is a subtype of `int` in Python
                and `True`/`False` silently coerce to `1`/`0` — a real
                but nonsensical caller mistake this validation also
                catches). R11-4 binding correction, 2026-08-15 (Kimi K3
                round-11 review): `max_retries` was never validated —
                the THIRD recidivism of the "a caller-supplied value of
                the wrong type bypasses this file's own error taxonomy"
                class in this same file (see R8-6-shaped `isinstance(...,
                int) and not isinstance(..., bool)` guards elsewhere in
                this repo's `wa_blind_bench.py` for the sibling pattern).
                Two concrete failure modes this closes: `max_retries=2.5`
                reached `range(1, self.max_retries + 2)` inside
                `generate()` and raised a raw `TypeError`
                (`'float' object cannot be interpreted as an integer`)
                that is NOT one of this module's own typed exceptions —
                a caller catching this client's documented exception
                hierarchy would not catch it. `max_retries=-1` produced
                `range(1, 1)`, an EMPTY range — the retry loop's body
                never executes at all, zero network calls are ever made,
                and execution falls through to the loop's own
                "Unreachable in practice" trailing `raise
                OpenAINetworkError(...)` — a transport-flavored exception
                for a call the transport never touched, misleading about
                what actually happened. Both are now caught here, at
                construction time, before either bad value can reach
                `generate()` at all.
            ValueError: `timeout` is not a finite positive `int`/`float`
                (`bool` excluded, same subtype trap as `max_retries` above).
                R12-1, 2026-08-15 (Kimi K3 round-12 review): `timeout` was
                never validated and is handed to `httpx.AsyncClient(timeout=
                ...)` unexamined in `_get_client()`. `timeout="abc"` or
                `timeout=True` would not fail here — they would fail deep
                inside httpx's own timeout-config parsing, as an exception
                that is not one of this module's typed exceptions, on the
                FIRST real network call rather than at construction.
                `timeout=float("nan")` is worse: httpx does not reject NaN,
                so every per-attempt deadline comparison against a NaN
                timeout is silently always-false, and a hung connection
                would never time out at all. `timeout=-1` is rejected for
                the same reason as any non-positive deadline: a timeout
                that has already elapsed before the first request is sent.
            ValueError: `api_key` is neither `None` nor `str`. R12-2, 2026-
                08-15 (Kimi K3 round-12 review): a non-string, non-`None`
                `api_key` (e.g. `123` or `b"sk-x"`) previously reached
                `_resolve_api_key()` and then `_validate_api_key_ascii()`
                unexamined — the ASCII/control-char regex match on a
                non-`str` raises a raw `TypeError` from `re.search`, again
                outside this module's typed exception hierarchy. The
                existing empty-string-is-falsy-and-therefore-unavailable
                semantics (`api_key=""` behaves as "no key provided", not
                as an error) are preserved unchanged by this check — only
                the *type* is validated here, not the value.
        """
        if not isinstance(max_retries, int) or isinstance(max_retries, bool) or max_retries < 0:
            raise ValueError(
                f"max_retries must be a non-negative int, got {type(max_retries).__name__}",
            )
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
            raise ValueError(
                f"timeout must be a finite positive number, got {type(timeout).__name__}",
            )
        try:
            # R13-1 binding correction, 2026-08-15 (Kimi K3 round-13
            # review): `math.isfinite` does not merely return `False` on
            # an oversized `int` — it RAISES `OverflowError: int too large
            # to convert to float`, reproduced empirically by the gate
            # against this project's own venv with `timeout=10**400`. A
            # bare `not math.isfinite(timeout)` therefore let a raw
            # `OverflowError` escape past this constructor, outside the
            # exception taxonomy the `Raises:` block above just declared
            # complete — the same "wrong-type/shape value bypasses this
            # module's typed exceptions" class as R12-1/R12-2 above, just
            # one call deeper. An `int` too large to convert to `float`
            # IS non-finite for the purposes of this guard (it can never
            # be a usable timeout), so the conversion failure is treated
            # as `timeout_is_finite = False` rather than re-raised.
            timeout_is_finite = math.isfinite(timeout)
        except OverflowError:
            timeout_is_finite = False
        if not timeout_is_finite or timeout <= 0:
            raise ValueError(
                f"timeout must be a finite positive number, got {type(timeout).__name__}",
            )
        if api_key is not None and not isinstance(api_key, str):
            raise ValueError(
                f"api_key must be a str or None, got {type(api_key).__name__}",
            )
        # `_explicit_api_key` is set ONLY when a caller passes `api_key=`
        # directly (tests do this). In every other case — including every
        # real deployment — no key is cached at construction time; both
        # `available` and `generate()` re-read the environment on each
        # access, genuinely live, never a docstring claim over a cached
        # field.
        self._explicit_api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None

        if not self._resolve_api_key():
            logger.info(
                "OpenAIResponsesClient: %s not set — client disabled (available=False). "
                "This is expected: no dedicated WA-provider key exists in any "
                "environment yet (see the ADR).",
                _ENV_VAR,
            )

    def _resolve_api_key(self) -> str | None:
        """The single place that decides the API key value. Called fresh
        on every `available` read and every `generate()` call — genuinely
        live, not a docstring claim over a cached field."""
        if self._explicit_api_key is not None:
            return self._explicit_api_key
        return os.getenv(_ENV_VAR)

    @property
    def available(self) -> bool:
        """True only when an API key is configured, re-checked on every
        access (see `_resolve_api_key`) — mirrors `OpenRouterProvider.
        is_available` reading `settings.openrouter_enabled` at call time
        (COS-LAW-013), not once at import/construction."""
        return bool(self._resolve_api_key())

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
                # R8-12 binding correction, 2026-08-15 (Kimi K3 round-8
                # review): httpx defaults `trust_env=True`, which reads
                # `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` from the process
                # environment and routes every request — this client's
                # `Authorization: Bearer <key>` header included — through
                # whatever proxy is ambiently set. Inconsistent with the
                # same allowlist-env discipline this diff already applies
                # elsewhere (`build_deid_corpus.py`'s K3 Ollama subprocess
                # allowlist): an ambient env var should not be able to
                # silently redirect this client's traffic, key included,
                # through a third-party proxy. Explicit `trust_env=False`.
                trust_env=False,
            )
        return self._client

    async def close(self) -> None:
        """Shut down the persistent client. Call from app lifespan
        (Golden Rule #10) — never per-request."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.info("OpenAIResponsesClient: HTTP client closed")

    def _headers(self, api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def generate(
        self,
        *,
        input_text: str,
        system_prompt: str | None = "",
        model: str | None = None,
        max_output_tokens: int | None = 2048,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResult:
        """Generate one response via the Responses API.

        STATELESS ONLY for this phase: every request sends `"store": false`
        and there is no `previous_response_id` parameter — this client
        never threads a prior response into a new one, and OpenAI does not
        persist the call as retrievable application state (no conversation
        history, no `previous_response_id` continuity to resume later).
        **This is NOT a zero-retention claim.** Per OpenAI's platform data
        usage policy, API content may still be retained for up to 30 days
        for abuse and safety monitoring even under `store: false`, unless
        a Zero Data Retention agreement has been separately negotiated —
        this client makes no claim that one exists. Anyone reasoning about
        PII exposure from this adapter must reason about that 30-day
        abuse-log window, not about "nothing is stored" (see the ADR §4.6
        for the corrected framing — an earlier draft overclaimed "OpenAI
        never persists this call server-side"). Multi-turn/provider-side
        conversation state is explicitly deferred; see the ADR
        §Non-goals. Turn-to-turn context, if ever needed, must be
        assembled by the CALLER into `input_text` — this client does not
        accumulate state of its own.

        Raises:
            OpenAIClientUnavailableError: no API key configured.
            OpenAICredentialFormatError: the resolved API key is not valid
                ASCII, or contains a control character (a header-injection
                shape `isascii()` alone would miss) — checked via
                `_validate_api_key_ascii` before any network call. R8-2
                binding correction, 2026-08-15 (Kimi K3 round-8 review):
                this docstring's own `Raises:` list presented itself as
                exhaustive (see `OpenAIResponseShapeError`'s entry below,
                "the full list") while omitting this exception, which
                `generate()` has been able to raise since R6-5 (§13) — a
                recurrence of that same class: a list that claims
                completeness without actually being complete.
            OpenAINetworkError: transport-level failure after retries.
            OpenAIAPIError: non-2xx from the API after retries (or on a
                non-retryable 4xx immediately). Never carries the remote
                body — status code + category only.
            OpenAIResponseShapeError: HTTP 200 but the body was not valid
                JSON, or was not a usable, finished, fully-recognised
                generation (see that class's docstring for the full list).
            OpenAIToolNotAllowedError: `tools` was non-empty and at least
                one requested name is not on `ALLOWED_TOOL_NAMES` — the
                ENTIRE request is refused, never partially forwarded.
            OpenAIModelNotAllowedError: the resolved model is not allowed
                for how it was resolved. An explicit `model=` argument may
                be any of the three reviewed `_RUNTIME_MODEL_CANDIDATES`
                (`MODEL_SOL` included). A model resolved from
                `OPENAI_RESPONSES_MODEL` or `DEFAULT_MODEL` (no explicit
                `model=`) is restricted to `_ENV_OR_DEFAULT_MODEL_CANDIDATES`
                (`MODEL_TERRA`/`MODEL_LUNA` only) — `MODEL_SOL` reaching
                this point via env/default is rejected
                (category=sol_requires_explicit_request): `MODEL_SOL` is
                ceiling-only and must be requested explicitly, never
                inherited from a persistent env var or the default.
            ValueError: `input_text` is not a `str`; `system_prompt` is
                neither `None` nor a `str`; `max_output_tokens` is
                neither `None` nor a positive `int` (`bool` excluded,
                same subtype trap as every other guard in this file); or
                `tools` is neither `None` nor a `list`.
                R14-2, 2026-08-15 (Kimi K3 round-14 review): the FIFTH
                recurrence of the "a caller-supplied value of the wrong
                type/shape bypasses this module's own typed exceptions"
                class — this time on the payload side. An unvalidated
                `input_text=object()` reached `json.dumps` deep inside
                httpx's own request encoding and raised a raw `TypeError`
                there, outside `httpx.RequestError`/`httpx.StreamError`
                (the only types the retry loop's `except` catches) and
                therefore outside this very `Raises:` block too. Checked
                BEFORE `payload` is built, so a malformed value never
                reaches the network.
                R15-2, 2026-08-15 (Kimi K3 round-15 review, MEDIUM): the
                SIXTH recurrence of the same class, on `tools` — a
                one-shot iterator (`generate(tools=iter([...]))`) defeats
                `_validate_tools_allowlisted`'s allowlist check entirely
                (that function iterates its argument TWICE; an exhausted
                iterator on the second pass silently looks like "zero
                unknown names") and then reaches `json.dumps` unchecked.
                Checked here too, before `_validate_tools_allowlisted` is
                ever called.

        A refusal is NOT raised — it comes back as
        `LLMResult(refusal=True, ...)`. Callers that only want the answer
        text must check `.refusal` before using `.text`.
        """
        api_key = self._resolve_api_key()
        if not api_key:
            raise OpenAIClientUnavailableError(
                f"OpenAIResponsesClient.generate() called with no {_ENV_VAR} configured",
            )

        # R6-5 SECOND binding correction (live-gate, 2026-08-15): the guard
        # above (`_validate_api_key_ascii`, see its own docstring and
        # `OpenAICredentialFormatError`'s) was fully implemented — and
        # extensively documented as THE fix for the raw UnicodeEncodeError
        # httpx raises on a non-ASCII/control-char header value — but was
        # never actually CALLED from this method. A resolved key containing
        # e.g. 'é' therefore still reached `client.post()` and still raised
        # the very UnicodeEncodeError this whole guard exists to convert
        # into a typed, documented exception. Caught by this file's own
        # first real guilt test for the class (a fake transport asserting
        # zero network calls for a malformed key) — the test failed with
        # the raw UnicodeEncodeError, not the expected typed error, proving
        # the wiring gap rather than assuming the docstrings above were
        # accurate. Called BEFORE any model/tool validation too, so a
        # malformed key is refused as early as possible.
        _validate_api_key_ascii(api_key)

        # K2 SECOND binding correction, 2026-08-15 (Kimi K3 round-2
        # refinement): which allowlist applies depends on WHETHER `model`
        # was passed explicitly by the caller, not just on the resolved
        # string value — see `_ENV_OR_DEFAULT_MODEL_CANDIDATES` above. An
        # explicit `generate(model=...)` call may request any of the three
        # reviewed candidates, `MODEL_SOL` included; a model resolved from
        # `OPENAI_RESPONSES_MODEL` or `DEFAULT_MODEL` may only resolve to
        # `MODEL_TERRA`/`MODEL_LUNA` — `MODEL_SOL` reaching this point via
        # that path is rejected with its own category so a persistent env
        # var can never silently become "sol on every call".
        model_explicitly_requested = model is not None
        model_name = model if model_explicitly_requested else os.getenv("OPENAI_RESPONSES_MODEL", DEFAULT_MODEL)

        if model_explicitly_requested:
            allowed_candidates = _RUNTIME_MODEL_CANDIDATES
        else:
            allowed_candidates = _ENV_OR_DEFAULT_MODEL_CANDIDATES

        # Same-class binding correction, 2026-08-15 (Kimi K3, live-gate
        # round 5): `model_name not in allowed_candidates` below performs
        # `in` against a frozenset, which requires `model_name` to be
        # HASHABLE — a caller passing `generate(model=[...])` or
        # `generate(model={...})` would raise a raw `TypeError: unhashable
        # type` instead of a typed `OpenAIModelNotAllowedError`. The env/
        # default resolution path can never produce this (`os.getenv`
        # always returns a `str` or the `str` `DEFAULT_MODEL`), so this is
        # reachable only via an explicit `model=` kwarg — still
        # CALLER-supplied, like a malformed tool name, but described only
        # by its Python type here rather than echoed verbatim: an
        # arbitrary object handed to `model=` might be large or otherwise
        # awkward to render, and the type name alone is all a caller needs
        # to fix their own call.
        if not isinstance(model_name, str):
            raise OpenAIModelNotAllowedError(
                f"model resolved to a non-string value (got {type(model_name).__name__}) — "
                f"only a string model slug may be requested "
                f"(category=malformed_model_type)",
            )

        if model_name not in allowed_candidates:
            if not model_explicitly_requested and model_name == MODEL_SOL:
                raise OpenAIModelNotAllowedError(
                    f"model {model_name!r} was resolved via OPENAI_RESPONSES_MODEL or "
                    f"DEFAULT_MODEL, not an explicit generate(model=...) call — "
                    f"MODEL_SOL is ceiling-only and may only be requested explicitly "
                    f"(category=sol_requires_explicit_request)",
                )
            # K2 binding correction, 2026-08-15 — real enforcement, not a
            # comment: an arbitrary string (typo, stale model ID, an
            # unreviewed slug someone set in OPENAI_RESPONSES_MODEL) must
            # never reach the network. `MODEL_SOL` is a MEMBER of
            # `_RUNTIME_MODEL_CANDIDATES` (it stays requestable, e.g. by
            # wa_blind_bench.py's explicit ceiling-reference call) — this
            # branch only excludes slugs outside the allowlist that applies
            # to THIS resolution path, it does not by itself pick which
            # candidate a given caller "should" use.
            raise OpenAIModelNotAllowedError(
                f"model {model_name!r} is not on the allowed candidate set for this "
                f"call ({sorted(allowed_candidates)}) — only reviewed gpt-5.6 "
                f"candidates may be requested",
            )

        # R15-2 binding correction, 2026-08-15 (Kimi K3 round-15 review,
        # MEDIUM): `tools` was never validated as actually being a `list`
        # before reaching `_validate_tools_allowlisted`, which itself
        # iterates its argument TWICE (the dict/name-shape loop, then a
        # SEPARATE comprehension building `unknown`). A one-shot iterator
        # (`generate(tools=iter([{"name": "crm_query"}]))`) passes the
        # FIRST loop (each entry looks like a valid dict-with-str-name),
        # but the second iteration then sees an ALREADY-EXHAUSTED
        # iterator — the `unknown` comprehension yields zero items no
        # matter what the tool names actually were, `if unknown:` is
        # False, and the function returns as if every name had been
        # checked against the allowlist and found fine. This defeats the
        # very invariant `_validate_tools_allowlisted`'s own docstring
        # states ("Fail closed on the WHOLE request if ANY requested tool
        # name is not in ALLOWED_TOOL_NAMES") — with an empty allowlist by
        # design, EVERY name should be rejected, and this bug makes none
        # of them reach that check at all. The same exhausted iterator
        # then reaches `requested_tool_names`/`payload["tools"]` below and
        # is handed to `json.dumps` un-checked — a raw `TypeError`
        # ("Object of type list_iterator is not JSON serializable"),
        # outside this method's documented taxonomy, the same class as
        # R14-2. `tools=object()` (non-iterable entirely) fails even
        # earlier, at the first iteration attempt inside
        # `_validate_tools_allowlisted` itself, with a raw
        # `TypeError: 'object' object is not iterable`. Fixed: validated
        # HERE, before `_validate_tools_allowlisted` is ever called —
        # `tools is None or isinstance(tools, list)`, `ValueError` naming
        # only the offending type, same guard style as every other
        # constructor/payload check in this file. This CORRECTS the R14-2
        # comment two paragraphs below, which reasoned `tools=`'s twin
        # exposure was "unreachable today" purely because the empty
        # allowlist would reject any non-empty `tools` — that reasoning
        # assumed `_validate_tools_allowlisted` always actually performs
        # the rejection it promises, which this finding shows is false
        # for non-`list` iterables specifically; a `list` (however
        # malformed its entries) was never at risk, only this narrower
        # iterator/iterable case was.
        if tools is not None and not isinstance(tools, list):
            raise ValueError(
                f"tools must be a list or None, got {type(tools).__name__}",
            )
        if tools:
            _validate_tools_allowlisted(tools)  # raises on ANY unknown name — all-or-nothing
        # `str(t.get("name")) for t in tools` here is SAFE, not merely
        # convenient: `_validate_tools_allowlisted` above already raised on
        # any entry that isn't a dict OR whose `name` isn't a string
        # (live-gate binding correction, 2026-08-15) — this line only
        # executes once every entry is confirmed dict-with-str-name, so the
        # `str()` call is a type-narrowing no-op by this point, not a
        # safety mechanism reached before that guard ran.
        requested_tool_names: frozenset[str] = (
            frozenset(str(t.get("name")) for t in tools) if tools else frozenset()
        )

        # R14-2 binding correction, 2026-08-15 (Kimi K3 round-14 review):
        # `input_text`/`system_prompt`/`max_output_tokens` used to flow
        # straight into `payload` below with no type/range check — the
        # FIFTH recurrence of the "a caller-supplied value of the wrong
        # type/shape bypasses this module's own typed exception taxonomy"
        # class (siblings: R8-6, R9-4/R10-2, R11-4, R12-1, R12-2), this
        # time on the payload side rather than the constructor side.
        # `generate(input_text=object())` reached `json.dumps` deep
        # inside httpx's request-body encoding and raised a raw
        # `TypeError` there — NOT `httpx.RequestError`/`httpx.StreamError`
        # (the only exception types the retry loop's `except` clause
        # catches), so it escaped the retry loop entirely and left this
        # method's own `Raises:` block, which presents itself as
        # exhaustive, incomplete. Fixed: validated here, BEFORE `payload`
        # is built, consistent with `__init__`'s own guard style —
        # `ValueError` naming only the offending type, never a raw value.
        # `tools=` has the identical shape of exposure in principle (an
        # unhashable/malformed entry could in theory reach `json.dumps`
        # unvalidated) but is UNREACHABLE today: `_validate_tools_allowlisted`
        # above already rejects the entire request the moment `tools` is
        # non-empty and the allowlist (`ALLOWED_TOOL_NAMES`) is itself
        # empty by default — every `tools=` call is refused before this
        # point is ever reached, so no parallel guard is added here for
        # it (see ADR §21 for the same note, dated). NOT permanent: this
        # dormancy is scoped to "allowlist empty" — see `ALLOWED_TOOL_NAMES`'s
        # own R16-4 sentinel comment, DECLARE-NOT-FIX, for the required
        # companion validation once any name is added there.
        if not isinstance(input_text, str):
            raise ValueError(
                f"input_text must be a str, got {type(input_text).__name__}",
            )
        if system_prompt is not None and not isinstance(system_prompt, str):
            raise ValueError(
                f"system_prompt must be a str or None, got {type(system_prompt).__name__}",
            )
        if (
            max_output_tokens is not None
            and (
                not isinstance(max_output_tokens, int)
                or isinstance(max_output_tokens, bool)
                or max_output_tokens <= 0
            )
        ):
            raise ValueError(
                f"max_output_tokens must be a positive int or None, "
                f"got {type(max_output_tokens).__name__}",
            )

        payload: dict[str, Any] = {
            "model": model_name,
            "input": input_text,
            # Stateless by construction — see the STATELESS note above.
            "store": False,
        }
        # R15-4 binding correction, 2026-08-15 (Kimi K3 round-15 review,
        # LOW): the signature said `max_output_tokens: int = 2048` while
        # R14-2's own validation (and its `Raises:` entry) explicitly
        # accepts `None` — and the payload used to emit
        # `"max_output_tokens": null` UNCONDITIONALLY whenever `None` was
        # passed, a contract mismatch between what the type hint claimed
        # was accepted and what the code actually did. Fixed on both
        # sides: the hint above now reads `int | None = 2048`, and the
        # key is included in `payload` only when a value was actually
        # given — `None` means "let the API apply its own default",
        # never "explicitly request a null token limit".
        if max_output_tokens is not None:
            payload["max_output_tokens"] = max_output_tokens
        if system_prompt:
            payload["instructions"] = system_prompt
        if tools:
            # Every entry's `name` already passed `_validate_tools_allowlisted`
            # above (which raises on any miss) — nothing to FILTER here (no
            # partial forwarding, all-or-nothing). This does NOT mean every
            # entry is fully validated: only `name` is checked anywhere in
            # this module — other fields (e.g. `"parameters"`) are forwarded
            # unvalidated. See `ALLOWED_TOOL_NAMES`'s own R16-4 sentinel
            # comment above for why that gap is dormant today (empty
            # allowlist) and what must be added before it is populated.
            payload["tools"] = tools

        client = self._get_client()
        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 2):  # e.g. max_retries=2 -> attempts 1,2,3
            # R7-7 binding correction, 2026-08-15 (Kimi K3 round-7 review):
            # `t0` used to be set ONCE, before this loop — so `latency_ms`
            # on a call that needed a retry included every backoff sleep
            # AND every failed round-trip before the one that finally
            # succeeded (observed: ~1600ms reported for a ~100ms successful
            # attempt on retry 3). That systematically penalized, once
            # recorded per-candidate in the blind bench's key file (R8-3,
            # `wa_blind_bench.py::_run_one_fixture` — NOT the round-7
            # state, which didn't record this field anywhere yet),
            # whichever candidate happened to hit a transient network/5xx
            # blip — a latency measurement of the RETRY MACHINERY, not of
            # the model. `t0` is now reset at the top of
            # EVERY attempt, so `latency_ms` (computed below at line ~1233,
            # still `time.perf_counter() - t0`) always measures only the
            # single attempt that actually returned the response used to
            # build the result — backoff sleeps and prior failed attempts
            # are excluded entirely, matching `LLMResult.latency_ms`'s
            # intended meaning (see that field's docstring).
            t0 = time.perf_counter()
            pending_network_error: OpenAINetworkError | None = None
            try:
                response = await client.post(
                    _RESPONSES_URL,
                    headers=self._headers(api_key),
                    json=payload,
                )
            except (httpx.RequestError, httpx.StreamError) as exc:
                # K1 binding correction, 2026-08-15: `httpx.TimeoutException`
                # and `httpx.TransportError` do NOT cover every pre-response
                # httpx failure — `httpx.DecodingError` (RequestError, not
                # TransportError) and `httpx.TooManyRedirects` would have
                # risen raw past this except clause, uncaught. `RequestError`
                # is httpx's actual base for "never got a usable response"
                # (verified against the installed httpx==0.28.1's exception
                # hierarchy in this venv: TimeoutException and
                # TransportError are both already RequestError subclasses),
                # so this widens the catch to the correct base instead of
                # two of its subclasses.
                #
                # K1 SECOND binding correction, 2026-08-15 (Kimi K3 round-2
                # refinement): `RequestError` is NOT httpx's complete
                # pre-response failure surface either. `httpx.StreamError`
                # (base of `RequestNotRead`/`ResponseNotRead`/
                # `StreamClosed`/`StreamConsumed`) inherits from `RuntimeError`
                # directly, NOT from `RequestError` — verified against the
                # same installed httpx==0.28.1 hierarchy — so
                # `except httpx.RequestError` alone let `RequestNotRead` rise
                # raw out of this method on a request `client.post()` never
                # finished sending. Added as a second exception type in this
                # clause rather than a second `except` block: both classes
                # get IDENTICAL treatment below (retry then wrap), matching
                # the existing "every RequestError treated identically"
                # discipline this file already applies — this file never
                # distinguished retryability WITHIN transport-level
                # failures, only between transport-level failures (always
                # retried) and API 4xx/5xx status codes (retryable only if
                # in _RETRYABLE_STATUS_CODES, handled separately below).
                last_exc = exc
                if attempt <= self.max_retries:
                    backoff = 0.5 * (2 ** (attempt - 1))
                    logger.warning(
                        "OpenAIResponsesClient: network error attempt %d/%d, retrying in %.1fs: %s",
                        attempt,
                        self.max_retries + 1,
                        backoff,
                        type(exc).__name__,
                    )
                    await asyncio.sleep(backoff)
                    continue
                # Exception TYPE only, never the exception's string content —
                # same discipline as everywhere else in this module. `from
                # None`, not `from exc` (K4 binding correction, 2026-08-15):
                # an `httpx.RequestError`'s `.request` attribute carries the
                # actual outgoing request, headers included — this client's
                # own `Authorization: Bearer <key>` header among them. A
                # future serializer that walks `__cause__` (traceback
                # formatting, an error-reporting integration, a debugger)
                # would otherwise have a path to the API key via this
                # exception's cause chain even though the message itself
                # never echoes it.
                #
                # Live-gate addendum, 2026-08-15: `from None` alone leaves a
                # gap `__cause__` doesn't cover — Python's implicit exception
                # chaining sets `__context__` to `exc` at raise time
                # regardless of `from None` (verified empirically: `err.
                # __cause__` is `None` but `err.__context__ is exc` remains
                # true when raised HERE, inside this except block; only
                # `__suppress_context__` becomes `True`, which affects the
                # STANDARD traceback formatter's printed output, not
                # attribute access — a tool that walks `__context__`
                # directly, e.g. some error-reporting SDK integrations,
                # would still reach `exc.request`'s headers). The exception
                # is therefore built HERE but the `raise` itself is deferred
                # to immediately after this except block exits — verified
                # empirically that raising once no exception is "currently
                # being handled" leaves BOTH `__cause__` and `__context__`
                # `None`, closing the gap outright rather than only
                # suppressing its display.
                pending_network_error = OpenAINetworkError(f"transport failure: {type(exc).__name__}")

            if pending_network_error is not None:
                raise pending_network_error

            # MEDIUM binding correction, 2026-08-15 (Kimi K3, live-gate round
            # 5): `if response.status_code >= 400:` let ANY status < 400 —
            # 1xx (e.g. a 100 Continue an intermediary sent through), a
            # non-200 2xx (201/204/...), or a 3xx redirect httpx followed —
            # fall straight into `response.json()` parsing below, contrary
            # to this module's own docstring ("HTTP 200 is necessary but
            # not sufficient"). The OpenAI Responses API only ever answers
            # `200` on a genuine success (confirmed against its docs — it
            # does not use 201/204/3xx for this endpoint), so the gate is
            # now the STRICT positive case, not merely "not obviously an
            # error": anything other than exactly 200 is treated as an API
            # error (retried if in `_RETRYABLE_STATUS_CODES`, same as
            # before — every code currently in that set is already >= 400,
            # so retry behaviour for the previously-handled cases is
            # unchanged).
            if response.status_code != 200:
                if response.status_code in _RETRYABLE_STATUS_CODES and attempt <= self.max_retries:
                    backoff = 0.5 * (2 ** (attempt - 1))
                    logger.warning(
                        "OpenAIResponsesClient: HTTP %d attempt %d/%d, retrying in %.1fs",
                        response.status_code,
                        attempt,
                        self.max_retries + 1,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue
                # Non-retryable (any non-200 we don't retry) or retries
                # exhausted. Deliberately NOT response.text — same no-remote-
                # body rule as everywhere else in this module.
                raise OpenAIAPIError(response.status_code)

            latency_ms = (time.perf_counter() - t0) * 1000
            pending_shape_error: OpenAIResponseShapeError | None = None
            try:
                data = response.json()
            except (ValueError, httpx.DecodingError):
                # httpx raises json.JSONDecodeError (a ValueError subclass)
                # on invalid JSON. Never embed response.text here — same
                # no-remote-body rule as OpenAIAPIError. `from None`, not
                # `from exc` (K4 binding correction, 2026-08-15):
                # `JSONDecodeError.doc` carries the FULL raw response body
                # text that failed to parse — exactly the remote-body
                # content this module's docstring says must never reach an
                # exception or log line, and `__cause__` is a path to it
                # that bypasses the message-only discipline everywhere else
                # in this file.
                #
                # K1 SECOND binding correction, 2026-08-15 (Kimi K3 round-2
                # refinement): `Response.json()` doesn't only raise
                # `ValueError` — before decoding as JSON it must decode the
                # raw bytes to text using the response's detected/declared
                # encoding, and a body whose bytes don't match that encoding
                # raises `httpx.DecodingError` (an `httpx.RequestError`
                # subclass, not a `ValueError`), which the previous
                # `except ValueError` let rise raw. Same fail-closed
                # destination either way: this is still an unusable response
                # body, mapped to the same `OpenAIResponseShapeError`.
                #
                # Live-gate addendum, 2026-08-15: same `__context__`-survives-
                # `from None` gap as the transport-error site above (see that
                # site's comment for the empirical verification) — the
                # `JSONDecodeError`/`DecodingError` object, body-excerpt
                # attribute included, would still be reachable via
                # `err.__context__` if raised HERE. Deferred past the except
                # block for the same reason: raising once nothing is
                # "currently being handled" leaves `__context__` genuinely
                # `None`, not just display-suppressed.
                pending_shape_error = OpenAIResponseShapeError("response body was not valid JSON")

            if pending_shape_error is not None:
                raise pending_shape_error
            result = _parse_responses_payload(
                data,
                model_requested=model_name,
                requested_tool_names=requested_tool_names,
            )
            # Replace the placeholder latency_ms/attempts from the pure parser
            # with the real measurement — dataclass is frozen, so rebuild.
            return LLMResult(
                text=result.text,
                refusal=result.refusal,
                refusal_reason=result.refusal_reason,
                tool_calls=result.tool_calls,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                model=result.model,
                latency_ms=round(latency_ms, 1),
                attempts=attempt,
                finish_reason=result.finish_reason,
                raw_response_id=result.raw_response_id,
            )

        # Unreachable in practice (the loop always returns or raises), but
        # keeps the type-checker honest and fails loudly rather than
        # returning None if the retry accounting above is ever changed.
        raise OpenAINetworkError(
            f"exhausted retries with no response and no captured exception: "
            f"{type(last_exc).__name__ if last_exc else 'none'}",
        )
