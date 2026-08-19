"""Tests for the WA outbox worker's codex broker leg (BOT-V4 S2 PR-5).

Chaos-table ownership (design s2-pr5 §7): rows 2 (ALREADY_SPENT -> Gemini),
3-adjacent (fall-off semantics), 7 (typed failure -> fall-off), 9 (broker
dark -> Gemini-only) live here; rows 1/4 are pinned by PR-2's broker suite,
rows 5/6/8 by PR-6's daemon tests.

Fake discipline: the real ``wa_broker`` enums travel through a stub
namespace, so every ``is not OfferOutcome.OFFERED`` identity check in the
module under test runs against the same objects production uses — a fake
enum would make the comparisons vacuously true (W114: a fake speaking a
vocabulary the code never emits proves nothing).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.integrations import wa_broker, wa_codex_leg
from backend.services.integrations.wa_broker import (
    OfferOutcome,
    OfferResult,
    WaitOutcome,
    WaitResult,
)


class ScriptedConn:
    """Minimal fetchrow-scripted conn for the drift re-read."""

    def __init__(self, fetchrow_results: list[Any] | None = None) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self._fetchrow = list(fetchrow_results or [])

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        self.executed.append((sql, args))
        return self._fetchrow.pop(0) if self._fetchrow else None


def _thread(
    *,
    last_customer_at: Any = "fresh",
    handling_version: int = 3,
) -> dict[str, Any]:
    if last_customer_at == "fresh":
        last_customer_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    return {
        "thread_id": 7,
        "counterpart_phone": "628111",
        "human_handling": False,
        "last_customer_at": last_customer_at,
        "handling_version": handling_version,
    }


def _build_response(payload: dict[str, Any]) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=payload)
    return resp


_GOOD_BUILD = {
    "package_wire": '{"query":"q","thread_epoch":3}',
    "package_hash": "abc123",
    "evidence_inputs": {"chunks": 2},
    "unbuildable": None,
}


def _wire_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    build: dict[str, Any] | None = None,
    build_exc: Exception | None = None,
    offer: OfferResult | None = None,
    wait: WaitResult | None = None,
    consume: str | None = "the broker reply",
    query: str = "what is a KITAS?",
) -> SimpleNamespace:
    """Install fakes; return the namespace of spies."""
    monkeypatch.setenv("WA_GENERATION_PROVIDER", "codex")

    load = AsyncMock(return_value=(query, [{"role": "user", "content": "hi"}]))
    monkeypatch.setattr(wa_codex_leg, "_load_thread_context", load)

    client = MagicMock()
    if build_exc is not None:
        client.post = AsyncMock(side_effect=build_exc)
    else:
        client.post = AsyncMock(return_value=_build_response(build or _GOOD_BUILD))
    monkeypatch.setattr(wa_codex_leg, "_get_rag_client", AsyncMock(return_value=client))

    stub = SimpleNamespace(
        # Real enums/dataclasses so identity comparisons are meaningful.
        OfferOutcome=OfferOutcome,
        OfferResult=OfferResult,
        WaitOutcome=WaitOutcome,
        WaitResult=WaitResult,
        deadline_seconds=lambda: 15,
        offer_job=AsyncMock(
            return_value=offer
            if offer is not None
            else OfferResult(OfferOutcome.OFFERED, job_id=uuid.uuid4())
        ),
        wait_for_job=AsyncMock(
            return_value=wait if wait is not None else WaitResult(WaitOutcome.COMPLETED)
        ),
        consume_result=AsyncMock(return_value=consume),
        discard_completion=AsyncMock(return_value=None),
        record_breaker_result=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(wa_codex_leg, "wa_broker", stub)
    stub.rag_client = client
    stub.load_thread_context = load
    return stub


async def _run(
    conn: ScriptedConn | None = None,
    thread: dict[str, Any] | None = None,
) -> wa_codex_leg.CodexLegResult:
    return await wa_codex_leg.attempt(
        MagicMock(),  # pool — consumed only by fakes here
        conn or ScriptedConn(),
        outbox_id=42,
        thread_id=7,
        claim_token=uuid.uuid4(),
        outbox_expected_status="generating",
        thread=thread or _thread(),
    )


# ── gate 1: the env provider switch ─────────────────────────────────────────


def test_provider_gate_reads_env_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WA_GENERATION_PROVIDER", raising=False)
    assert wa_codex_leg.provider_is_codex() is False
    monkeypatch.setenv("WA_GENERATION_PROVIDER", "codex")
    assert wa_codex_leg.provider_is_codex() is True
    monkeypatch.setenv("WA_GENERATION_PROVIDER", "  CODEX  ")
    assert wa_codex_leg.provider_is_codex() is True
    monkeypatch.setenv("WA_GENERATION_PROVIDER", "gemini")
    assert wa_codex_leg.provider_is_codex() is False


# ── gate 2: 24h-window margin ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_window_margin_too_thin_falls_off_before_any_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A row about to lose its send window never waits on a broker: with
    2 x T_exec = 30s required and ~20s left, the leg steps aside before
    the loader or the HTTP client is ever touched."""
    stubs = _wire_stubs(monkeypatch)
    nearly_closed = datetime.now(timezone.utc) - (
        timedelta(hours=24) - timedelta(seconds=20)
    )
    result = await _run(thread=_thread(last_customer_at=nearly_closed))
    assert result.text is None and not result.stand_down
    assert result.reason == "window_margin"
    stubs.load_thread_context.assert_not_awaited()
    stubs.rag_client.post.assert_not_awaited()
    stubs.offer_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_window_never_opened_falls_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stubs = _wire_stubs(monkeypatch)
    result = await _run(thread=_thread(last_customer_at=None))
    assert result.reason == "window_margin"
    stubs.offer_job.assert_not_awaited()


# ── gate 3: the package build ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_customer_message_falls_off_before_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stubs = _wire_stubs(monkeypatch, query="")
    result = await _run()
    assert result.reason == "no_customer_message"
    stubs.rag_client.post.assert_not_awaited()


@pytest.mark.asyncio
async def test_unbuildable_falls_off_offer_never_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stubs = _wire_stubs(
        monkeypatch,
        build={"package_wire": None, "package_hash": None, "unbuildable": "greeting"},
    )
    result = await _run()
    assert result.reason == "unbuildable:greeting"
    stubs.offer_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_build_http_error_falls_off(monkeypatch: pytest.MonkeyPatch) -> None:
    stubs = _wire_stubs(monkeypatch, build_exc=RuntimeError("conn refused"))
    result = await _run()
    assert result.reason == "package_build_error"
    stubs.offer_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_build_contract_break_missing_wire_falls_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """200 with neither the wire nor an unbuildable reason is a contract
    break — never offered."""
    stubs = _wire_stubs(
        monkeypatch,
        build={"package_wire": None, "package_hash": None, "unbuildable": None},
    )
    result = await _run()
    assert result.reason == "build_contract_break"
    stubs.offer_job.assert_not_awaited()


# ── gate 4: the offer ───────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome",
    [
        OfferOutcome.BROKER_ABSENT,
        OfferOutcome.BREAKER_OPEN,
        OfferOutcome.QUEUE_FULL,
        OfferOutcome.ALREADY_SPENT,
        OfferOutcome.FENCE_LOST,
    ],
)
async def test_every_non_offered_outcome_falls_off_without_waiting(
    monkeypatch: pytest.MonkeyPatch, outcome: OfferOutcome
) -> None:
    """Chaos rows 2/9: every admission refusal is a route decision, not an
    error — straight to Gemini, no wait, no consume, no fold."""
    stubs = _wire_stubs(monkeypatch, offer=OfferResult(outcome))
    result = await _run()
    assert result.text is None and not result.stand_down
    assert result.reason == f"offer:{outcome.value}"
    stubs.wait_for_job.assert_not_awaited()
    stubs.consume_result.assert_not_awaited()
    stubs.record_breaker_result.assert_not_awaited()


@pytest.mark.asyncio
async def test_offer_passes_wire_hash_and_epoch_verbatim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The sealed envelope crosses untouched: offer_job receives EXACTLY the
    builder's wire string and hash — any re-serialization here would break
    the byte-fidelity contract PR-2 r4/r5 established."""
    stubs = _wire_stubs(monkeypatch)
    await _run()
    kwargs = stubs.offer_job.await_args.kwargs
    assert kwargs["package"] == _GOOD_BUILD["package_wire"]
    assert kwargs["package_hash"] == _GOOD_BUILD["package_hash"]
    assert kwargs["thread_epoch"] == 3
    assert '"chunks": 2' in kwargs["evidence_inputs"]


# ── wait / consume ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("wait_result", "expected_prefix"),
    [
        (WaitResult(WaitOutcome.FAILED, error_class="exec_timeout"), "wait:failed"),
        (WaitResult(WaitOutcome.DEADLINE), "wait:deadline"),
    ],
)
async def test_wait_failed_and_deadline_fall_off_without_consume_or_fold(
    monkeypatch: pytest.MonkeyPatch,
    wait_result: WaitResult,
    expected_prefix: str,
) -> None:
    """Chaos row 7 + breaker doctrine: FAILED/DEADLINE were folded by their
    transition owners — the worker adds NO second fold and simply falls off."""
    stubs = _wire_stubs(monkeypatch, wait=wait_result)
    result = await _run()
    assert result.text is None and not result.stand_down
    assert result.reason.startswith(expected_prefix)
    stubs.consume_result.assert_not_awaited()
    stubs.discard_completion.assert_not_awaited()
    stubs.record_breaker_result.assert_not_awaited()


@pytest.mark.asyncio
async def test_completed_with_takeover_drift_discards_and_stands_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec 2.3: a takeover during exec means the completion must never be
    sent AND must never trigger a fresh generation."""
    stubs = _wire_stubs(monkeypatch)
    conn = ScriptedConn(
        fetchrow_results=[{"human_handling": True, "handling_version": 3}]
    )
    result = await _run(conn=conn)
    assert result.stand_down is True
    assert result.text is None
    stubs.discard_completion.assert_awaited_once()
    assert stubs.discard_completion.await_args.kwargs["reason"] == "takeover"
    stubs.consume_result.assert_not_awaited()


@pytest.mark.asyncio
async def test_completed_with_epoch_drift_discards_and_stands_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A takeover+RELEASE during exec leaves human_handling false but moves
    handling_version — the epoch comparison catches what the boolean
    cannot."""
    stubs = _wire_stubs(monkeypatch)
    conn = ScriptedConn(
        fetchrow_results=[{"human_handling": False, "handling_version": 4}]
    )
    result = await _run(conn=conn)
    assert result.stand_down is True
    stubs.discard_completion.assert_awaited_once()
    stubs.consume_result.assert_not_awaited()


@pytest.mark.asyncio
async def test_completed_fresh_consumes_and_returns_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stubs = _wire_stubs(monkeypatch)
    conn = ScriptedConn(
        fetchrow_results=[{"human_handling": False, "handling_version": 3}]
    )
    result = await _run(conn=conn)
    assert result.text == "the broker reply"
    assert result.stand_down is False
    stubs.discard_completion.assert_not_awaited()


@pytest.mark.asyncio
async def test_consume_lost_falls_off_without_second_fold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Losing the reaper's dead-consumer race is a fall-off, not a fold —
    the job's fold already happened at its transition."""
    stubs = _wire_stubs(monkeypatch, consume=None)
    conn = ScriptedConn(
        fetchrow_results=[{"human_handling": False, "handling_version": 3}]
    )
    result = await _run(conn=conn)
    assert result.text is None and not result.stand_down
    assert result.reason == "consume_lost"
    stubs.record_breaker_result.assert_not_awaited()


# ── the never-raises contract ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_attempt_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """An escape from the leg must never enter the worker's retry ladder:
    broker outcomes consume zero attempts by design."""
    stubs = _wire_stubs(monkeypatch)
    stubs.offer_job.side_effect = RuntimeError("boom")
    result = await _run()
    assert result.text is None and not result.stand_down
    assert result.reason == "internal_error:RuntimeError"


def test_stub_namespace_mirrors_the_real_module() -> None:
    """The stub in _wire_stubs must name only attributes the real wa_broker
    exports — a fake speaking an invented vocabulary proves nothing (W114)."""
    for name in (
        "OfferOutcome",
        "OfferResult",
        "WaitOutcome",
        "WaitResult",
        "deadline_seconds",
        "offer_job",
        "wait_for_job",
        "consume_result",
        "discard_completion",
        "record_breaker_result",
    ):
        assert hasattr(wa_broker, name), f"stub names {name}, real module does not"
