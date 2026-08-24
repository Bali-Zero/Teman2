"""Unit tests for `backend.services.integrations.wa_codex_daemon`.

Fakes sit at the boundaries the daemon actually crosses (W114 discipline):
HTTP via `httpx.MockTransport` — so the daemon's OWN client construction,
header attachment and JSON encoding all run for real — and the codex CLI
via a stub with `generate()`'s exact signature. No network, no subprocess,
no broker required.
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
    CodexExecAuthError,
    CodexExecCommunicationError,
    CodexExecOutputShapeError,
    CodexExecProcessError,
    CodexExecTimeoutError,
    CodexExecUnavailableError,
    MatchConfidence,
    OutputShapeReason,
)
from backend.services.integrations import wa_codex_daemon as daemon_module
from backend.services.integrations.wa_codex_daemon import (
    DaemonConfig,
    WaCodexDaemon,
    compute_budget_s,
)

_PIN = "0.147.0"
_PACKAGE_WIRE = json.dumps({"question": "SYNTHETIC-CLIENT-TEXT-a8f3", "chunks": []})
_RESULT_TEXT = "SYNTHETIC-MODEL-ANSWER-c71e"

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
    """`CodexExecClient.generate`-shaped stub; records calls."""

    def __init__(self, *, text: str = _RESULT_TEXT, raises: BaseException | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._text = text
        self._raises = raises

    async def generate(
        self, prompt: str, *, model: str | None = None, timeout_s: float | None = None
    ) -> Any:
        self.calls.append({"prompt": prompt, "model": model, "timeout_s": timeout_s})
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
        broker = _Broker(claim_results=[_claim_payload()])
        codex = _StubCodex()
        daemon = _daemon(broker, codex)
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        [call] = codex.calls
        assert call["timeout_s"] == 14.0  # (15s window) - (1s margin)
        assert call["prompt"] == _PACKAGE_WIRE  # wire passed verbatim as prompt


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
        assert body["result_text"] == _RESULT_TEXT
        assert body["error_class"] is None
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
            # B2b (2026-08-25): `CodexExecOutputShapeError`/`CodexExecAuthError`
            # now require `reason=`/`confidence=` — this daemon predates that
            # split (PR #4377) and, per its own `except` clauses just above,
            # folds BOTH into "cli_failure" regardless of sub-cause/confidence,
            # so a neutral value here changes nothing about what this test
            # asserts.
            (CodexExecOutputShapeError("o", reason=OutputShapeReason.EMPTY), "cli_failure"),
            (CodexExecAuthError("a", confidence=MatchConfidence.LOW), "cli_failure"),
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
        broker = _Broker(claim_results=[_claim_payload()])
        daemon = _daemon(broker, _StubCodex(text="x" * 65536))
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        [body] = _complete_bodies(broker)
        assert body["error_class"] is None
        assert len(body["result_text"]) == 65536

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
        """50k 3-byte chars pass the 65,536-CHAR cap but encode to ~150KB —
        over the router's 128KiB stream cap. Posting would 413 and the
        4xx-never-retry branch would abandon the job untyped (Kimi round-1
        F1, verified by execution); the byte pre-check must fail it TYPED."""
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
        """40k 3-byte chars ≈ 120,018 encoded bytes — under _RESULT_BYTES_MAX,
        so it must be SENT. And the wire bytes must equal `_encode_body` of
        the parsed body: the measuring stick and the wire share one encoder,
        so the byte pre-check can never drift from what actually ships."""
        text = "€" * 40_000
        broker = _Broker(claim_results=[_claim_payload()])
        daemon = _daemon(broker, _StubCodex(text=text))
        daemon._version_ok = True

        claim = await daemon._claim()
        await daemon._execute_and_complete(claim)

        [request] = broker.complete_requests
        body = json.loads(request.content)
        assert body["error_class"] is None
        assert body["result_text"] == text
        assert request.headers["Content-Type"] == "application/json"
        assert request.content == daemon_module._encode_body(body)


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
