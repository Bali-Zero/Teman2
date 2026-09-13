"""Unit tests for `backend.services.integrations.wa_codex_daemon`.

Fakes sit at the boundaries the daemon actually crosses (W114 discipline):
HTTP via `httpx.MockTransport` — so the daemon's OWN client construction,
header attachment and JSON encoding all run for real — and the codex CLI
via a stub with `generate()`'s exact signature. No network, no subprocess,
no broker required.

B2.4: the daemon now judges support on the claimed package BEFORE
generating, reusing its OWN codex client for both the judge's 3 votes and
the eventual generation — `_StubCodex` therefore answers BOTH kinds of call
through the same object, telling them apart by the PROMPT shape (a judge
call is always `RUBRIC`-formatted; the generation call always carries the
raw package verbatim, per `wa-codex-daemon`'s own PII-boundary comment). A
`SUPPORTED` judge_text default keeps every PRE-B2.4 test's generation path
reachable unchanged; tests that need a different verdict pass their own
`judge_text`/`judge_raises`.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from backend.llm.codex_exec_client import (
    MODEL_LUNA,
    MODEL_TERRA,
    CodexExecAuthError,
    CodexExecCommunicationError,
    CodexExecOutputShapeError,
    CodexExecProcessError,
    CodexExecQuotaError,
    CodexExecTimeoutError,
    CodexExecUnavailableError,
)
from backend.services.integrations import wa_codex_daemon as daemon_module
from backend.services.integrations.wa_codex_daemon import (
    DaemonConfig,
    WaCodexDaemon,
    compute_budget_s,
)
from backend.services.integrations.wa_completion_envelope import (
    decode_completion,
    encode_completion,
)
from backend.services.rag.agentic._support_signal import RUBRIC, SupportVerdict

_PIN = "0.147.0"
# A readable wire (design B2-4-design.md §1.1 step 3): 'history'/'chunks'
# are exactly what `support_inputs_from_wire` parses. The markers stay
# distinctive so TestPiiBoundary can prove neither ever reaches a log line.
_SYNTHETIC_QUERY = "SYNTHETIC-CLIENT-TEXT-a8f3"
_SYNTHETIC_CONTEXT = "SYNTHETIC-CONTEXT-CHUNK-9c21"
_PACKAGE_WIRE = json.dumps(
    {
        "history": [{"role": "user", "content": _SYNTHETIC_QUERY}],
        "chunks": [{"collection": "c", "text": _SYNTHETIC_CONTEXT, "score": 0.9}],
        "pricing_block": None,
        "persona_digest": "digest",
        "evidence_inputs": {},
        "thread_epoch": 0,
    }
)
_MALFORMED_PACKAGE_WIRE = json.dumps({"nothing": "readable here"})
_RESULT_TEXT = "SYNTHETIC-MODEL-ANSWER-c71e"
_JUDGE_PROMPT = RUBRIC.format(query=_SYNTHETIC_QUERY, context=_SYNTHETIC_CONTEXT)

# Sentinel for _Broker.claim_results: answer this claim with a 200 whose body
# is NOT JSON (an LB error page under a misconfigured proxy).
_NON_JSON_200 = "NON_JSON_200"


def _config(**overrides: Any) -> DaemonConfig:
    defaults: dict[str, Any] = {
        "base_url": "http://broker.test",
        "broker_key": "test-broker-key-abcdef",
        "version_pin": _PIN,
        "poll_s": 0.01,
        "net_margin_s": 1.0,
    }
    defaults.update(overrides)
    return DaemonConfig(**defaults)


def _claim_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "job_id": str(uuid.uuid4()),
        "fence_token": str(uuid.uuid4()),
        "package": _PACKAGE_WIRE,
        "package_hash": "deadbeef" * 8,
        # Server-truth timestamps deliberately in the DISTANT PAST relative
        # to any real wall clock running these tests: a budget derived from
        # anything but these two fields cannot come out right (chaos row 6).
        "server_now": "2020-01-01T00:00:00+00:00",
        "deadline_at": "2020-01-01T00:00:15+00:00",
    }
    payload.update(overrides)
    return payload


class _StubCodex:
    """`CodexExecClient.generate`-shaped stub; records ALL calls.

    B2.4: the daemon hands this SAME object to `CodexSupportJudge` (3 votes)
    AND uses it directly for the final generation, exactly like the real
    daemon reusing its own `self._codex`. A call is a judge vote iff its
    prompt is `RUBRIC`-formatted (`_vote_once` always builds it that way);
    the generation call always carries the raw package verbatim — the two
    shapes never collide because the package wire is JSON, never English
    prose starting with the rubric's fixed sentence.

    `judge_text` is either a single verdict word (every vote answers it) or
    a list consumed one-per-call (in call order — safe here because none of
    these stub calls actually suspend on real I/O, so `asyncio.gather`
    runs them start-to-finish in scheduling order) for split-vote tests.
    """

    def __init__(
        self,
        *,
        text: str = _RESULT_TEXT,
        raises: BaseException | None = None,
        judge_text: str | list[str] = "SUPPORTED",
        judge_raises: BaseException | None = None,
        judge_delay_s: float = 0.0,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._text = text
        self._raises = raises
        self._judge_text = judge_text
        self._judge_raises = judge_raises
        self._judge_delay_s = judge_delay_s

    async def generate(
        self, prompt: str, *, model: str | None = None, timeout_s: float | None = None
    ) -> Any:
        self.calls.append({"prompt": prompt, "model": model, "timeout_s": timeout_s})
        if prompt.startswith("You judge evidence sufficiency."):
            if self._judge_delay_s:
                await asyncio.sleep(self._judge_delay_s)
            if self._judge_raises is not None:
                raise self._judge_raises
            verdict_word = (
                self._judge_text.pop(0) if isinstance(self._judge_text, list) else self._judge_text
            )

            class _JudgeResult:
                text = verdict_word

            return _JudgeResult()

        if self._raises is not None:
            raise self._raises

        class _Result:
            text = self._text
            model = "gpt-5.6-terra"
            latency_ms = 1.0

        return _Result()


@dataclass
class _Broker:
    """Scripted broker behind an `httpx.MockTransport`.

    `claim_results` is consumed one per /claim POST (a dict payload, None
    for "no job", or the `_NON_JSON_200` sentinel for a 200 with a non-JSON
    body). `complete_script` is consumed one per /complete POST: an int HTTP
    status, or an exception instance to raise at the transport. When a
    script runs dry, claims answer "no job" and completes answer 200.
    """

    claim_results: list[dict[str, Any] | str | None] = field(default_factory=list)
    complete_script: list[int | str | Exception] = field(default_factory=list)
    claim_requests: list[httpx.Request] = field(default_factory=list)
    complete_requests: list[httpx.Request] = field(default_factory=list)

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/wa-broker/claim":
            self.claim_requests.append(request)
            result = self.claim_results.pop(0) if self.claim_results else None
            if result is None:
                return httpx.Response(200, json={"job_id": None})
            if result == _NON_JSON_200:
                return httpx.Response(
                    200,
                    content=b"<html>upstream gateway error</html>",
                    headers={"Content-Type": "text/html"},
                )
            return httpx.Response(200, json=result)
        if request.url.path == "/api/wa-broker/complete":
            self.complete_requests.append(request)
            action = self.complete_script.pop(0) if self.complete_script else 200
            if isinstance(action, Exception):
                raise action
            if action == _NON_JSON_200:
                return httpx.Response(
                    200,
                    content=b"<html>upstream gateway error</html>",
                    headers={"Content-Type": "text/html"},
                )
            body = {"status": "accepted"} if action == 200 else {"detail": "scripted"}
            return httpx.Response(action, json=body)
        raise AssertionError(f"unexpected path: {request.url.path}")

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


def _daemon(
    broker: _Broker,
    codex: _StubCodex | None = None,
    config: DaemonConfig | None = None,
) -> WaCodexDaemon:
    return WaCodexDaemon(
        config or _config(),
        codex_client=codex or _StubCodex(),  # type: ignore[arg-type]
        transport=broker.transport(),
    )


def _complete_bodies(broker: _Broker) -> list[dict[str, Any]]:
    return [json.loads(r.content) for r in broker.complete_requests]


# ---------------------------------------------------------------------------
# DaemonConfig.from_env — fail-fast validation
# ---------------------------------------------------------------------------


class TestConfig:
    _FULL_ENV = {
        "WA_BROKER_BASE_URL": "http://broker.test/",
        "WA_BROKER_KEY": "k-1234567890",
        "WA_CODEX_CLI_VERSION_PIN": _PIN,
        "WA_CODEX_MODEL": "gpt-5.6-terra",
        "WA_BROKER_POLL_S": "3.5",
        "WA_BROKER_NET_MARGIN_S": "0.5",
    }

    def _set_env(self, monkeypatch: pytest.MonkeyPatch, **overrides: str | None) -> None:
        env = {**self._FULL_ENV, **overrides}
        for key in self._FULL_ENV:
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            if value is not None:
                monkeypatch.setenv(key, value)

    def test_innocence_full_env_parses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._set_env(monkeypatch)
        config = DaemonConfig.from_env()
        assert config.base_url == "http://broker.test"  # trailing slash stripped
        assert config.version_pin == _PIN
        assert config.poll_s == 3.5
        assert config.net_margin_s == 0.5

    @pytest.mark.parametrize(
        "missing", ["WA_BROKER_BASE_URL", "WA_BROKER_KEY", "WA_CODEX_CLI_VERSION_PIN"]
    )
    def test_guilt_missing_required_refuses(
        self, monkeypatch: pytest.MonkeyPatch, missing: str
    ) -> None:
        self._set_env(monkeypatch, **{missing: None})
        with pytest.raises(ValueError):
            DaemonConfig.from_env()

    def test_guilt_empty_pin_refuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An EMPTY pin is not 'unpinned allowed' — it is a refusal to start."""
        self._set_env(monkeypatch, WA_CODEX_CLI_VERSION_PIN="   ")
        with pytest.raises(ValueError, match="WA_CODEX_CLI_VERSION_PIN"):
            DaemonConfig.from_env()

    def test_guilt_unknown_model_refuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._set_env(monkeypatch, WA_CODEX_MODEL="gpt-9.9-imaginary")
        with pytest.raises(ValueError, match="WA_CODEX_MODEL"):
            DaemonConfig.from_env()

    def test_guilt_nonpositive_poll_refuses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._set_env(monkeypatch, WA_BROKER_POLL_S="0")
        with pytest.raises(ValueError):
            DaemonConfig.from_env()


# ---------------------------------------------------------------------------
# Budget — chaos row 6 (server fields only, local wall clock never consulted)
# ---------------------------------------------------------------------------


class TestBudget:
    def test_budget_is_a_pure_function_of_server_fields(self) -> None:
        """Timestamps from 2020 — six years before any wall clock running
        this test. If the local clock were an input, the result could not
        be exactly (deadline - server_now) - margin."""
        budget = compute_budget_s(
            "2020-01-01T00:00:15+00:00", "2020-01-01T00:00:00+00:00", 1.0
        )
        assert budget == 14.0

    def test_guilt_unparseable_timestamp_raises(self) -> None:
        with pytest.raises(ValueError):
            compute_budget_s("not-a-timestamp", "2020-01-01T00:00:00+00:00", 1.0)

    @pytest.mark.asyncio
    async def test_guilt_aware_naive_timestamp_mix_completes_cli_failure(self) -> None:
        """An aware/naive mix raises TypeError, not ValueError (Kimi
        round-2 L3) — the contract-break catch must cover BOTH so the job
        fails typed instead of dying in the loop's generic handler."""
        broker = _Broker(
            claim_results=[_claim_payload(server_now="2020-01-01T00:00:00")]  # naive
        )
        codex = _StubCodex()
        daemon = _daemon(broker, codex)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        assert codex.calls == []  # contract break — never spawned
        [body] = _complete_bodies(broker)
        assert body["error_class"] == "cli_failure"

    @pytest.mark.asyncio
    async def test_exec_timeout_reported_without_spawning_when_budget_spent(self) -> None:
        """deadline_at == server_now → margin eats the whole budget →
        complete(error_class=exec_timeout) with the CLI NEVER invoked."""
        broker = _Broker(
            claim_results=[_claim_payload(deadline_at="2020-01-01T00:00:00+00:00")]
        )
        codex = _StubCodex()
        daemon = _daemon(broker, codex)
        daemon._version_ok = True

        claim = await daemon._claim()
        assert claim is not None
        await daemon._execute_and_complete(claim)

        assert codex.calls == []
        [body] = _complete_bodies(broker)
        assert body["error_class"] == "exec_timeout"
        assert body["result_text"] is None

    @pytest.mark.asyncio
    async def test_generate_receives_the_server_derived_budget(self) -> None:
        """B2.4: the judge stage runs first (3 votes) inside the SAME
        client, so the generation call's timeout is the REMAINING budget —
        strictly less than the full (15s window) - (1s margin) = 14.0s, but
        still positive."""
        broker = _Broker(claim_results=[_claim_payload()])
        codex = _StubCodex()
        daemon = _daemon(broker, codex)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        assert len(codex.calls) == 4  # 3 judge votes + 1 generation
        generate_call = codex.calls[-1]
        assert 0 < generate_call["timeout_s"] <= 14.0
        assert generate_call["prompt"] == _PACKAGE_WIRE  # wire passed verbatim as prompt


# ---------------------------------------------------------------------------
# Happy path + auth header
# ---------------------------------------------------------------------------


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_claim_exec_complete_round_trip(self) -> None:
        broker = _Broker(claim_results=[_claim_payload()])
        daemon = _daemon(broker)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        [body] = _complete_bodies(broker)
        assert body["error_class"] is None
        # B2.4: result_text is the HMAC-sealed envelope, not the raw text —
        # decode it exactly as the routing leg would.
        decoded = decode_completion(
            body["result_text"], key=daemon._config.broker_key, package_hash=claim.package_hash
        )
        assert decoded is not None
        assert decoded.verdict == SupportVerdict.SUPPORTED
        assert decoded.answer == _RESULT_TEXT
        assert body["job_id"] == claim.job_id
        assert body["fence_token"] == claim.fence_token
        assert 8 <= len(body["completion_key"]) <= 128
        assert isinstance(body["exec_ms"], int) and body["exec_ms"] >= 0

    @pytest.mark.asyncio
    async def test_every_request_carries_the_broker_key_header(self) -> None:
        """Exercises the daemon's OWN client construction (transport
        injection) — the header must ride on claim AND complete."""
        broker = _Broker(claim_results=[_claim_payload()])
        daemon = _daemon(broker)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        for request in [*broker.claim_requests, *broker.complete_requests]:
            assert request.headers.get("X-API-Key") == "test-broker-key-abcdef"

    @pytest.mark.asyncio
    async def test_claim_with_missing_sibling_fields_is_a_contract_break(self) -> None:
        payload = _claim_payload()
        del payload["fence_token"]
        broker = _Broker(claim_results=[payload])
        daemon = _daemon(broker)

        assert await daemon._claim() is None


# ---------------------------------------------------------------------------
# Claim robustness — a 200 that is not JSON is a blip, not a loop crash
# ---------------------------------------------------------------------------


class TestClaimRobustness:
    @pytest.mark.asyncio
    async def test_guilt_non_json_200_claim_is_a_failed_claim_not_a_crash(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A 200 whose body is an LB error page (Kimi round-1 named gap):
        must degrade to "no job" — and must not poison the next claim."""
        broker = _Broker(claim_results=[_NON_JSON_200, _claim_payload()])
        daemon = _daemon(broker)
        daemon._version_ok = True

        with caplog.at_level("WARNING"):
            assert await daemon._claim() is None
        assert any("non-JSON" in record.getMessage() for record in caplog.records)

        assert await daemon._claim() is not None  # loop not poisoned


# ---------------------------------------------------------------------------
# Completion idempotency — chaos row 3
# ---------------------------------------------------------------------------


class TestCompletionRetry:
    @pytest.mark.asyncio
    async def test_lost_response_retried_with_the_same_completion_key(self) -> None:
        broker = _Broker(
            claim_results=[_claim_payload()],
            complete_script=[httpx.ConnectError("scripted drop"), 200],
        )
        daemon = _daemon(broker)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        bodies = _complete_bodies(broker)
        assert len(bodies) == 2
        assert bodies[0]["completion_key"] == bodies[1]["completion_key"]

    @pytest.mark.asyncio
    async def test_5xx_retried_then_accepted(self) -> None:
        broker = _Broker(
            claim_results=[_claim_payload()],
            complete_script=[503, 200],
        )
        daemon = _daemon(broker)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        bodies = _complete_bodies(broker)
        assert len(bodies) == 2
        assert bodies[0]["completion_key"] == bodies[1]["completion_key"]

    @pytest.mark.asyncio
    async def test_409_conflict_is_never_retried(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        broker = _Broker(claim_results=[_claim_payload()], complete_script=[409])
        daemon = _daemon(broker)
        daemon._version_ok = True

        claim = await daemon._claim()
        with caplog.at_level("ERROR"):
            await daemon._execute_and_complete(claim)

        assert len(broker.complete_requests) == 1
        assert any("409" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_410_gone_is_never_retried(self) -> None:
        broker = _Broker(claim_results=[_claim_payload()], complete_script=[410])
        daemon = _daemon(broker)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        assert len(broker.complete_requests) == 1

    @pytest.mark.asyncio
    async def test_422_deterministic_rejection_is_never_retried(self) -> None:
        broker = _Broker(claim_results=[_claim_payload()], complete_script=[422])
        daemon = _daemon(broker)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        assert len(broker.complete_requests) == 1

    @pytest.mark.asyncio
    async def test_guilt_non_json_200_complete_does_not_escape(self) -> None:
        """A 200 /complete answer whose body is an LB error page (Kimi
        round-2 L1): the same guard as the claim side — `_complete` must
        absorb it, not let ValueError escape to the loop's generic catch."""
        broker = _Broker(claim_results=[_claim_payload()], complete_script=[_NON_JSON_200])
        daemon = _daemon(broker)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)  # must not raise

        assert len(broker.complete_requests) == 1  # a 200 is final — no retry


# ---------------------------------------------------------------------------
# Error mapping — closed vocabulary
# ---------------------------------------------------------------------------


class TestErrorMapping:
    @pytest.mark.parametrize(
        ("raised", "expected"),
        [
            (CodexExecTimeoutError("t"), "exec_timeout"),
            (CodexExecUnavailableError("u"), "spawn_failure"),
            (CodexExecProcessError(1), "cli_failure"),
            (CodexExecCommunicationError("c"), "cli_failure"),
            (CodexExecOutputShapeError("o"), "cli_failure"),
            (CodexExecAuthError("a"), "cli_failure"),
            (CodexExecQuotaError("q"), "quota_exhausted"),
            (RuntimeError("anything unexpected"), "cli_failure"),
        ],
    )
    @pytest.mark.asyncio
    async def test_guilt_exec_failures_map_to_the_vocabulary(
        self, raised: BaseException, expected: str
    ) -> None:
        broker = _Broker(claim_results=[_claim_payload()])
        daemon = _daemon(broker, _StubCodex(raises=raised))
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        [body] = _complete_bodies(broker)
        assert body["error_class"] == expected
        assert body["result_text"] is None

    @pytest.mark.asyncio
    async def test_guilt_oversized_output_is_reported_never_truncated(self) -> None:
        broker = _Broker(claim_results=[_claim_payload()])
        daemon = _daemon(broker, _StubCodex(text="x" * 65537))
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        [body] = _complete_bodies(broker)
        assert body["error_class"] == "oversized_output"
        assert body["result_text"] is None  # never a truncated answer

    @pytest.mark.asyncio
    async def test_guilt_blank_output_is_empty_output(self) -> None:
        broker = _Broker(claim_results=[_claim_payload()])
        daemon = _daemon(broker, _StubCodex(text="   \n"))
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        [body] = _complete_bodies(broker)
        assert body["error_class"] == "empty_output"

    @pytest.mark.asyncio
    async def test_innocence_result_at_exactly_the_cap_is_sent(self) -> None:
        """B2.4: the cap binds the ENVELOPE (bytes actually sent), not the
        raw model text — compute the exact answer length that puts the
        envelope AT `_RESULT_TEXT_MAX`, rather than assuming raw text length
        equals envelope length (the envelope's fixed fields add overhead)."""
        claim_payload = _claim_payload()
        probe_envelope = encode_completion(
            key=_config().broker_key,
            package_hash=claim_payload["package_hash"],
            verdict=SupportVerdict.SUPPORTED,
            votes=(SupportVerdict.SUPPORTED,) * 3,
            judge=f"codex:{MODEL_TERRA}",
            answer="A",
        )
        overhead = len(probe_envelope) - 1
        text = "x" * (daemon_module._RESULT_TEXT_MAX - overhead)  # noqa: SLF001

        broker = _Broker(claim_results=[claim_payload])
        daemon = _daemon(broker, _StubCodex(text=text))
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        [body] = _complete_bodies(broker)
        assert body["error_class"] is None
        assert len(body["result_text"]) == daemon_module._RESULT_TEXT_MAX  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_guilt_nul_in_result_is_cli_failure(self) -> None:
        """PostgreSQL TEXT cannot hold U+0000: the router 422s it and the
        daemon's 4xx branch never retries — so the daemon pre-scans and
        fails the job TYPED instead of losing it untyped (Kimi round-1 F2)."""
        broker = _Broker(claim_results=[_claim_payload()])
        daemon = _daemon(broker, _StubCodex(text="answer\x00tail"))
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        [body] = _complete_bodies(broker)
        assert body["error_class"] == "cli_failure"
        assert body["result_text"] is None

    @pytest.mark.asyncio
    async def test_guilt_multibyte_result_under_char_cap_over_byte_cap(self) -> None:
        """50k 3-byte chars pass the raw 65,536-CHAR cap, and B2.4's ENVELOPE
        wrapping (the bytes actually measured/sent) only adds to that — it
        still encodes to well over the router's 128KiB stream cap. Posting
        would 413 and the 4xx-never-retry branch would abandon the job
        untyped (Kimi round-1 F1, verified by execution); the byte pre-check
        must fail it TYPED — this test doubles as the ENVELOPE-exceeds-the-
        byte-cap case (B2.4 build spec §Tests)."""
        text = "€" * 50_000  # € = 3 bytes in UTF-8
        assert len(text) <= daemon_module._RESULT_TEXT_MAX  # passes the char cap
        broker = _Broker(claim_results=[_claim_payload()])
        daemon = _daemon(broker, _StubCodex(text=text))
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        [body] = _complete_bodies(broker)
        assert body["error_class"] == "oversized_output"
        assert body["result_text"] is None

    @pytest.mark.asyncio
    async def test_innocence_multibyte_under_both_caps_is_sent_and_measured_as_wired(
        self,
    ) -> None:
        """40k 3-byte chars, once sealed in the envelope, still measure
        ~120,320 encoded bytes (measured) — under _RESULT_BYTES_MAX, so it
        must be SENT. And the wire bytes must equal `_encode_body` of the
        parsed body: the measuring stick and the wire share one encoder, so
        the byte pre-check can never drift from what actually ships."""
        text = "€" * 40_000
        broker = _Broker(claim_results=[_claim_payload()])
        daemon = _daemon(broker, _StubCodex(text=text))
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        [request] = broker.complete_requests
        body = json.loads(request.content)
        assert body["error_class"] is None
        decoded = decode_completion(
            body["result_text"], key=daemon._config.broker_key, package_hash=claim.package_hash
        )
        assert decoded is not None
        assert decoded.answer == text
        assert request.headers["Content-Type"] == "application/json"
        assert request.content == daemon_module._encode_body(body)


# ---------------------------------------------------------------------------
# B2.4 — the support-judge stage inserted before generation
# ---------------------------------------------------------------------------


class TestSupportJudgeStage:
    @pytest.mark.asyncio
    async def test_supported_majority_runs_exactly_three_judge_calls_then_one_generate(
        self,
    ) -> None:
        broker = _Broker(claim_results=[_claim_payload()])
        codex = _StubCodex()  # judge_text="SUPPORTED" default
        daemon = _daemon(broker, codex)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        judge_calls = [c for c in codex.calls if c["prompt"] == _JUDGE_PROMPT]
        generate_calls = [c for c in codex.calls if c["prompt"] == _PACKAGE_WIRE]
        assert len(judge_calls) == 3
        assert len(generate_calls) == 1
        assert 0 < generate_calls[0]["timeout_s"] <= 14.0

        [body] = _complete_bodies(broker)
        decoded = decode_completion(
            body["result_text"], key=daemon._config.broker_key, package_hash=claim.package_hash
        )
        assert decoded is not None
        assert decoded.verdict == SupportVerdict.SUPPORTED
        assert decoded.answer == _RESULT_TEXT

    @pytest.mark.asyncio
    async def test_judge_prompt_equals_rubric_format_of_the_wire(self) -> None:
        broker = _Broker(claim_results=[_claim_payload()])
        codex = _StubCodex()
        daemon = _daemon(broker, codex)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        judge_calls = [c for c in codex.calls if c["model"] == MODEL_TERRA]
        assert len(judge_calls) == 3
        for call in judge_calls:
            assert call["prompt"] == _JUDGE_PROMPT

    @pytest.mark.asyncio
    async def test_judge_model_is_pinned_to_terra_even_when_config_model_differs(self) -> None:
        broker = _Broker(claim_results=[_claim_payload()])
        codex = _StubCodex()
        config = _config(model=MODEL_LUNA)  # any allowed model other than MODEL_TERRA
        daemon = _daemon(broker, codex, config=config)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        judge_calls = [c for c in codex.calls if c["prompt"] == _JUDGE_PROMPT]
        assert len(judge_calls) == 3
        assert all(call["model"] == MODEL_TERRA for call in judge_calls)

    @pytest.mark.asyncio
    async def test_not_supported_majority_skips_generation(self) -> None:
        broker = _Broker(claim_results=[_claim_payload()])
        codex = _StubCodex(judge_text="NOT_SUPPORTED")
        daemon = _daemon(broker, codex)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        assert len(codex.calls) == 3  # judge only — generate never called
        [body] = _complete_bodies(broker)
        assert body["error_class"] is None
        decoded = decode_completion(
            body["result_text"], key=daemon._config.broker_key, package_hash=claim.package_hash
        )
        assert decoded is not None
        assert decoded.verdict == SupportVerdict.NOT_SUPPORTED
        assert decoded.answer is None

    @pytest.mark.asyncio
    async def test_unknown_majority_skips_generation(self) -> None:
        broker = _Broker(claim_results=[_claim_payload()])
        codex = _StubCodex(judge_text="UNKNOWN")
        daemon = _daemon(broker, codex)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        assert len(codex.calls) == 3
        [body] = _complete_bodies(broker)
        assert body["error_class"] is None
        decoded = decode_completion(
            body["result_text"], key=daemon._config.broker_key, package_hash=claim.package_hash
        )
        assert decoded is not None
        assert decoded.verdict == SupportVerdict.UNKNOWN
        assert decoded.answer is None

    @pytest.mark.asyncio
    async def test_split_vote_fails_closed_to_not_supported_without_generating(self) -> None:
        broker = _Broker(claim_results=[_claim_payload()])
        codex = _StubCodex(judge_text=["SUPPORTED", "NOT_SUPPORTED", "UNKNOWN"])
        daemon = _daemon(broker, codex)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        assert len(codex.calls) == 3
        [body] = _complete_bodies(broker)
        assert body["error_class"] is None
        decoded = decode_completion(
            body["result_text"], key=daemon._config.broker_key, package_hash=claim.package_hash
        )
        assert decoded is not None
        assert decoded.verdict == SupportVerdict.NOT_SUPPORTED
        assert decoded.answer is None

    @pytest.mark.asyncio
    async def test_unavailable_majority_reports_support_judge_unavailable(self) -> None:
        broker = _Broker(claim_results=[_claim_payload()])
        codex = _StubCodex(judge_raises=CodexExecUnavailableError("dead seat"))
        daemon = _daemon(broker, codex)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        assert len(codex.calls) == 3  # 3 judge attempts, all raised; generate never called
        [body] = _complete_bodies(broker)
        assert body["error_class"] == "support_judge_unavailable"
        assert body["result_text"] is None

    @pytest.mark.asyncio
    async def test_malformed_package_reports_support_judge_unavailable(self) -> None:
        payload = _claim_payload(package=_MALFORMED_PACKAGE_WIRE)
        broker = _Broker(claim_results=[payload])
        codex = _StubCodex()
        daemon = _daemon(broker, codex)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        assert codex.calls == []  # never reaches the judge or the generation
        [body] = _complete_bodies(broker)
        assert body["error_class"] == "support_judge_unavailable"
        assert body["result_text"] is None

    @pytest.mark.asyncio
    async def test_judge_consuming_the_whole_budget_reports_exec_timeout_without_generating(
        self,
    ) -> None:
        payload = _claim_payload(
            server_now="2020-01-01T00:00:00+00:00",
            deadline_at="2020-01-01T00:00:00.050000+00:00",  # 50ms budget window
        )
        broker = _Broker(claim_results=[payload])
        codex = _StubCodex(judge_delay_s=0.2)  # outlasts the 50ms budget
        config = _config(net_margin_s=0.0)
        daemon = _daemon(broker, codex, config=config)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        generate_calls = [c for c in codex.calls if c["prompt"] == _PACKAGE_WIRE]
        assert generate_calls == []
        [body] = _complete_bodies(broker)
        assert body["error_class"] == "exec_timeout"
        assert body["result_text"] is None


# ---------------------------------------------------------------------------
# Version pin — chaos row 8
# ---------------------------------------------------------------------------


class TestVersionPin:
    @pytest.mark.asyncio
    async def test_guilt_startup_mismatch_refuses_to_run(self) -> None:
        broker = _Broker()
        daemon = _daemon(broker)

        async def _wrong_version() -> str | None:
            return "9.9.9"

        daemon._read_cli_version = _wrong_version  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="version"):
            await daemon.run_forever()
        assert broker.claim_requests == []

    @pytest.mark.asyncio
    async def test_guilt_midrun_mismatch_stops_claiming(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Startup sees the pin; every re-check after sees drift. With the
        re-check forced due on every iteration, the loop must never claim
        after the flip — the stale heartbeat gauge is the designed signal."""
        monkeypatch.setattr(daemon_module, "_VERSION_RECHECK_S", 0.0)
        broker = _Broker()
        daemon = _daemon(broker)
        versions = iter([_PIN])  # startup only; every later read drifts

        async def _version_sequence() -> str | None:
            return next(versions, "9.9.9")

        daemon._read_cli_version = _version_sequence  # type: ignore[method-assign]

        task = asyncio.ensure_future(daemon.run_forever())
        await asyncio.sleep(0.15)
        daemon.request_stop()
        await task

        assert broker.claim_requests == []

    @pytest.mark.asyncio
    async def test_innocence_matching_pin_keeps_claiming(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(daemon_module, "_VERSION_RECHECK_S", 0.0)
        broker = _Broker()
        daemon = _daemon(broker)

        async def _pinned_version() -> str | None:
            return _PIN

        daemon._read_cli_version = _pinned_version  # type: ignore[method-assign]

        task = asyncio.ensure_future(daemon.run_forever())
        await asyncio.sleep(0.15)
        daemon.request_stop()
        await task

        assert len(broker.claim_requests) >= 2  # polled repeatedly

    @pytest.mark.asyncio
    async def test_guilt_version_flip_between_claim_and_exec_completes_mismatch(
        self,
    ) -> None:
        """The pre-exec guard: a claimed job must NEVER run on a drifted
        binary, whatever future reordering produces that state."""
        broker = _Broker(claim_results=[_claim_payload()])
        codex = _StubCodex()
        daemon = _daemon(broker, codex)
        daemon._version_ok = True
        claim = await daemon._claim()
        daemon._version_ok = False  # the flip

        await daemon._execute_and_complete(claim)

        assert codex.calls == []
        [body] = _complete_bodies(broker)
        assert body["error_class"] == "cli_version_mismatch"


# ---------------------------------------------------------------------------
# PII boundary — job ids and outcomes only, never text
# ---------------------------------------------------------------------------


class TestPiiBoundary:
    @pytest.mark.asyncio
    async def test_no_package_or_result_text_in_any_log_record(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        broker = _Broker(
            claim_results=[_claim_payload(), _claim_payload()],
            complete_script=[httpx.ConnectError("drop"), 200, 409],
        )
        daemon = _daemon(broker)
        daemon._version_ok = True

        with caplog.at_level("DEBUG"):
            for _ in range(2):
                claim = await daemon._claim()
                await daemon._execute_and_complete(claim)

        logged = " ".join(record.getMessage() for record in caplog.records)
        assert "SYNTHETIC-CLIENT-TEXT-a8f3" not in logged
        assert "SYNTHETIC-MODEL-ANSWER-c71e" not in logged
