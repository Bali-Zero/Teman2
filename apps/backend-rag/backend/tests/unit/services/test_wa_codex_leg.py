"""Tests for the WA outbox worker's codex broker leg (BOT-V4 S2 PR-5).

Chaos-table ownership (design s2-pr5 §7): rows 2 (ALREADY_SPENT -> Gemini),
3-adjacent (fall-off semantics), 7 (typed failure -> fall-off), 9 (broker
dark -> Gemini-only) live here; rows 1/4 are pinned by PR-2's broker suite,
rows 5/6/8 by PR-6's daemon tests. Retry-budget update (spec gradino 2/5,
migration 296): row 2's ALREADY_SPENT still falls off (now a defensive
race fallback, not the normal retry path), but a retry offer on a row
with a STILL-ALIVE prior leg now returns REATTACHED — this leg proceeds
to wait/consume the SAME job rather than falling off, and a terminal
prior leg with budget left gets a fresh OFFERED leg instead of falling
off at all. See test_offer_job_retry_* in test_wa_broker.py for the
offer_job-side coverage; this file covers only wa_codex_leg.py's
consumption of the new outcomes.

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
from backend.services.integrations.wa_finalize import (
    FinalizeOutcome,
    FinalizeResult,
)


class ScriptedConn:
    """Minimal scripted conn for the drift re-read + atomic stand-down."""

    def __init__(
        self,
        fetchrow_results: list[Any] | None = None,
        *,
        fetchrow_exc: Exception | None = None,
    ) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self._fetchrow = list(fetchrow_results or [])
        self._fetchrow_exc = fetchrow_exc

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        self.executed.append((sql, args))
        if self._fetchrow_exc is not None:
            raise self._fetchrow_exc
        return self._fetchrow.pop(0) if self._fetchrow else None

    async def execute(self, sql: str, *args: Any) -> str:
        self.executed.append((sql, args))
        return "UPDATE 1"

    def transaction(self) -> Any:
        class _Tx:
            async def __aenter__(self) -> None:
                return None

            async def __aexit__(self, *exc: Any) -> bool:
                return False

        return _Tx()

    def sql_contains(self, needle: str) -> bool:
        return any(needle in sql for sql, _ in self.executed)


class _FakePool:
    """The leg is pool-only by contract (the worker's claim connection
    carries a concurrent heartbeat — Codex r1 finding 4): every acquire()
    hands out the one scripted conn so the drift-re-read script drives it.

    ``release_exc_on_acquire`` (1-based) makes THAT acquire's __aexit__
    raise on a CLEAN exit — the connection-release-after-commit shape from
    Codex r3. ``enter_exc_on_acquire`` makes THAT acquire's __aenter__
    raise — the certain nothing-ran-yet shape from Codex r4.
    ``release_exc_on_error_exit`` makes THAT acquire's __aexit__ raise
    while an exception is ALREADY propagating — the release-replaces-
    cancellation shape from Codex r6."""

    def __init__(
        self,
        conn: ScriptedConn,
        *,
        release_exc_on_acquire: int | None = None,
        enter_exc_on_acquire: int | None = None,
        release_exc_on_error_exit: int | None = None,
    ) -> None:
        self._conn = conn
        self.acquired = 0
        self.released = 0
        self._release_exc_on = release_exc_on_acquire
        self._enter_exc_on = enter_exc_on_acquire
        self._release_exc_on_error = release_exc_on_error_exit

    def acquire(self) -> Any:
        pool = self

        class _CM:
            async def __aenter__(self) -> ScriptedConn:
                pool.acquired += 1
                self._n = pool.acquired
                if pool._enter_exc_on == self._n:
                    raise RuntimeError("acquire failed")
                return pool._conn

            async def __aexit__(self, *exc: Any) -> bool:
                pool.released += 1
                if pool._release_exc_on == self._n and exc[0] is None:
                    raise RuntimeError("release failed")
                if pool._release_exc_on_error == self._n and exc[0] is not None:
                    raise RuntimeError("release failed during unwind")
                return False

        return _CM()


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


_GOOD_WIRE = (
    '{"history":[],"chunks":[{"text":"KITAS costs Rp 12.000.000","score":0.9}],'
    '"pricing_block":null,"persona_digest":"pd",'
    '"evidence_inputs":{"abstain":false,"context_length":2,'
    '"evidence_score":0.85},"thread_epoch":3}'
)

# NOTE the build response carries NO evidence_inputs copy: the S2 gate's
# round 2 struck the unsealed top-level field from the contract — every
# consumer read comes from the sealed wire.
_GOOD_BUILD = {
    "package_wire": _GOOD_WIRE,
    "package_hash": "abc123",
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
    finalize: FinalizeResult | None = None,
) -> SimpleNamespace:
    """Install fakes; return the namespace of spies."""
    monkeypatch.setenv("WA_GENERATION_PROVIDER", "codex")
    # The autoreply kill switch gates the leg BEFORE the provider switch
    # (Codex r1 finding 2) — armed here so every test past gate 0 runs.
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")

    load = AsyncMock(return_value=(query, [{"role": "user", "content": "hi"}]))
    monkeypatch.setattr(wa_codex_leg, "_load_thread_context", load)

    client = MagicMock()
    if build_exc is not None:
        client.post = AsyncMock(side_effect=build_exc)
    else:
        client.post = AsyncMock(return_value=_build_response(build or _GOOD_BUILD))
    monkeypatch.setattr(wa_codex_leg, "_get_rag_client", AsyncMock(return_value=client))

    # Default finalize: SEND with the consumed text unchanged, so the
    # fall-off/stand-down tests stay focused on their own gate. The tests
    # that pin the FINALIZATION contract override this.
    fin = AsyncMock(
        return_value=finalize
        if finalize is not None
        else FinalizeResult(outcome=FinalizeOutcome.SEND, text=consume or "")
    )
    monkeypatch.setattr(wa_codex_leg, "finalize_wa_answer", fin)

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
            else OfferResult(
                OfferOutcome.OFFERED,
                job_id=uuid.uuid4(),
                # matches _thread()'s default handling_version=3 — most
                # tests never touch the epoch and just need the drift
                # check's `serving_epoch` to equal what `_thread()` hands
                # back as `fresh["handling_version"]`.
                thread_epoch=3,
            )
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
    stub.finalize = fin
    return stub


async def _run(
    conn: ScriptedConn | None = None,
    thread: dict[str, Any] | None = None,
    pool: _FakePool | None = None,
) -> wa_codex_leg.CodexLegResult:
    return await wa_codex_leg.attempt(
        pool or _FakePool(conn or ScriptedConn()),  # type: ignore[arg-type]
        outbox_id=42,
        thread_id=7,
        message_id=4200,
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


# ── gate 2b: the scripted greeting turn ─────────────────────────────────────


@pytest.mark.asyncio
async def test_a_bare_greeting_is_served_from_the_script_before_any_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cycle 359, measured on real delivery: a bare "halo" reached the package
    builder, was refused as `greeting_domain` (GREETING maps to zero
    collections by design), and — with the Gemini leg cut — took the full
    five-attempt retry ladder, ~7m45s, to arrive at an English error stub.

    The cure returns the scripted turn here, and the assertions that matter
    are the NEGATIVE ones: no build request, no broker offer, nothing
    generated. If the short-circuit is removed, `rag_client.post` is awaited
    and this test fails."""
    stubs = _wire_stubs(monkeypatch, query="halo")
    result = await _run()

    assert result.text is not None
    assert "Zantara" in result.text
    assert result.reason == "" and not result.stand_down and not result.fail
    stubs.rag_client.post.assert_not_awaited()
    stubs.offer_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_question_that_merely_opens_with_a_greeting_takes_the_normal_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Innocence, and the expensive half: "halo, berapa harga PT PMA?" is a
    pricing question wearing a polite hat. It must reach the package build
    exactly as before — a greeting guard that eats real questions is a worse
    defect than the one it cures (scar family #3)."""
    stubs = _wire_stubs(monkeypatch, query="halo, berapa harga PT PMA?")
    await _run()

    stubs.rag_client.post.assert_awaited()


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
async def test_no_customer_message_records_a_durable_fall_off_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Migration 290 — the exact shape measured live 2026-08-27 (outbox row
    346: generation_route stayed NULL, no broker_jobs row was ever created,
    because the fall-off happened at one of the PRE-OFFER conditions). This
    pins that a pre-offer fall-off writes a normalized, bounded reason to
    wa_outbox — not just an in-memory CodexLegResult that a log line loses
    a minute later. Without the write in attempt()'s wrapper this test
    fails: no execute() call ever mentions the column."""
    conn = ScriptedConn()
    stubs = _wire_stubs(monkeypatch, query="")
    result = await _run(conn=conn)
    assert result.reason == "no_customer_message"
    assert conn.sql_contains("generation_fall_off_reason")
    [written] = [
        args
        for sql, args in conn.executed
        if "generation_fall_off_reason" in sql
    ]
    assert written == (42, "standing_no_customer_message")
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
@pytest.mark.parametrize(
    ("unbuildable_reason", "expected_stored"),
    [
        ("greeting_domain", "package_unbuildable_greeting_domain"),
        ("no_collections", "package_unbuildable_no_collections"),
        ("dlp_error", "package_unbuildable_dlp_error"),
    ],
)
async def test_unbuildable_sub_reason_recorded_distinctly(
    monkeypatch: pytest.MonkeyPatch,
    unbuildable_reason: str,
    expected_stored: str,
) -> None:
    """Migration 291: the codex leg's three PackageUnbuildable sub-reasons
    must each land in their own DB value, not collapse into the single
    "package_unbuildable" bucket the way they did before this migration
    (2026-08-27, measured live: wa_outbox row 348 fell off
    "package_unbuildable" and the sub-reason — WHICH of greeting_domain /
    no_collections / dlp_error fired — was already gone from Fly's ~60s
    log retention by the time anyone looked, twice)."""
    conn = ScriptedConn()
    _wire_stubs(
        monkeypatch,
        build={
            "package_wire": None,
            "package_hash": None,
            "unbuildable": unbuildable_reason,
        },
    )
    result = await _run(conn=conn)
    assert result.reason == f"unbuildable:{unbuildable_reason}"
    [written] = [
        args for sql, args in conn.executed if "generation_fall_off_reason" in sql
    ]
    assert written == (42, expected_stored)


@pytest.mark.asyncio
async def test_unbuildable_unrecognized_sub_reason_falls_back_to_generic_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A PackageUnbuildable reason not yet in `_UNBUILDABLE_SUB_REASON_MAP`
    (a future sub-reason nobody has taught this module yet) must still
    land somewhere DISTINCTLY LABELED as "an unbuildable package", not in
    the module-wide "unknown" bucket a genuinely uncatalogued reason HEAD
    gets — the head here ("unbuildable") is perfectly well known, only the
    sub-reason is new."""
    conn = ScriptedConn()
    _wire_stubs(
        monkeypatch,
        build={
            "package_wire": None,
            "package_hash": None,
            "unbuildable": "some_future_reason",
        },
    )
    result = await _run(conn=conn)
    assert result.reason == "unbuildable:some_future_reason"
    [written] = [
        args for sql, args in conn.executed if "generation_fall_off_reason" in sql
    ]
    assert written == (42, "package_unbuildable")


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
        OfferOutcome.LEGS_EXHAUSTED,
    ],
)
async def test_every_non_offered_outcome_falls_off_without_waiting(
    monkeypatch: pytest.MonkeyPatch, outcome: OfferOutcome
) -> None:
    """Chaos rows 2/9: every admission refusal is a route decision, not an
    error — straight to Gemini, no wait, no consume, no fold. LEGS_EXHAUSTED
    (spec gradino 2/5) joins this set: named distinctly from ALREADY_SPENT
    in the reason string, but the same fall-off shape until Gemini itself
    is retired from this channel."""
    stubs = _wire_stubs(monkeypatch, offer=OfferResult(outcome))
    result = await _run()
    assert result.text is None and not result.stand_down
    assert result.reason == f"offer:{outcome.value}"
    stubs.wait_for_job.assert_not_awaited()
    stubs.consume_result.assert_not_awaited()
    stubs.record_breaker_result.assert_not_awaited()


@pytest.mark.asyncio
async def test_legs_exhausted_offer_refusal_records_a_durable_fall_off_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Migration 290, offer-refusal half of the mandate (as opposed to the
    pre-offer half pinned above): LEGS_EXHAUSTED is named distinctly in the
    log/CodexLegResult.reason (spec gradino 2/5) but normalizes to the same
    bounded 'offer_refused' category as every other non-OFFERED/REATTACHED
    outcome — the DB column is a small closed vocabulary, not a mirror of
    every offer outcome string. Without the write this test fails: no
    execute() call ever mentions the column."""
    conn = ScriptedConn()
    stubs = _wire_stubs(monkeypatch, offer=OfferResult(OfferOutcome.LEGS_EXHAUSTED))
    result = await _run(conn=conn)
    assert result.reason == "offer:legs_exhausted"
    [written] = [
        args
        for sql, args in conn.executed
        if "generation_fall_off_reason" in sql
    ]
    assert written == (42, "offer_refused")
    stubs.wait_for_job.assert_not_awaited()


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
    assert '"context_length": 2' in kwargs["evidence_inputs"]


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
    sent AND must never trigger a fresh generation. The verdict is ATOMIC
    (Codex r2 finding 3): fenced outbox abort + discard + ledger sentinel
    in one transaction, owned by the leg."""
    stubs = _wire_stubs(monkeypatch)
    conn = ScriptedConn(
        fetchrow_results=[
            {"human_handling": True, "handling_version": 3},
            {"id": 42},  # atomic stand-down abort: fenced RETURNING
        ]
    )
    result = await _run(conn=conn)
    assert result.stand_down is True
    assert result.text is None
    stubs.discard_completion.assert_awaited_once()
    assert stubs.discard_completion.await_args.kwargs["reason"] == "takeover"
    stubs.consume_result.assert_not_awaited()
    assert conn.sql_contains("UPDATE wa_outbox SET status = 'failed'")
    assert conn.sql_contains("aborted_human_takeover_codex_drift")


@pytest.mark.asyncio
async def test_completed_with_epoch_drift_discards_and_stands_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A takeover+RELEASE during exec leaves human_handling false but moves
    handling_version — the epoch comparison catches what the boolean
    cannot."""
    stubs = _wire_stubs(monkeypatch)
    conn = ScriptedConn(
        fetchrow_results=[
            {"human_handling": False, "handling_version": 4},
            {"id": 42},  # atomic stand-down abort: fenced RETURNING
        ]
    )
    result = await _run(conn=conn)
    assert result.stand_down is True
    stubs.discard_completion.assert_awaited_once()
    stubs.consume_result.assert_not_awaited()
    assert conn.sql_contains("aborted_human_takeover_codex_drift")


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
    """A PRE-OFFER escape from the leg is a fall-off, never an exception
    into the worker's retry ladder — before the offer nothing durable
    exists, so Gemini in the same claim is safe."""
    stubs = _wire_stubs(monkeypatch)
    stubs.load_thread_context.side_effect = RuntimeError("boom")
    result = await _run()
    assert result.text is None and not result.stand_down and not result.fail
    assert result.reason == "internal_error:RuntimeError"


@pytest.mark.asyncio
async def test_fall_off_reason_recording_failure_never_blocks_the_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mandate constraint 4: writing the durable reason must never be able
    to fail the send. A DB acquire that raises on the record-write's own
    connection must not surface — attempt() still returns the SAME
    fall-off result it would have returned had the write succeeded."""
    stubs = _wire_stubs(monkeypatch, query="")
    # window_margin/no_customer_message do zero pool.acquire() calls of
    # their own before returning — the record write is the FIRST and ONLY
    # acquire on this path, so `enter_exc_on_acquire=1` targets exactly it.
    pool = _FakePool(ScriptedConn(), enter_exc_on_acquire=1)
    result = await _run(pool=pool)
    assert result.text is None and not result.stand_down and not result.fail
    assert result.reason == "no_customer_message"
    stubs.rag_client.post.assert_not_awaited()


def test_fall_off_reason_map_covers_every_reason_the_module_can_emit() -> None:
    """The map must not be able to rot in silence — which is exactly what
    this PR exists to prevent. `_normalize_fall_off_reason` maps anything
    it does not recognise to "unknown" (correct runtime behaviour: it must
    never raise), which means a NEW ``CodexLegResult(fail="something_new:...")``
    added later, with nobody teaching `_FALL_OFF_REASON_PREFIX_MAP` its
    head, goes red NOWHERE at import or unit-test time — the column just
    quietly fills with "unknown", and "why didn't ChatGPT answer this one?"
    is unanswered again, this time disguised as a populated column.

    So this test extracts, from the SOURCE (not a hand-copied list, which
    would itself be a proof that cannot fail when it drifts from the code),
    every reason head the module's ``CodexLegResult(...)`` call sites can
    actually produce, plus the one literal `raw_reason=` the worker passes
    directly (the sole condition the leg itself never sees), and asserts
    each one is a real key in the map.
    """
    import ast
    from pathlib import Path

    from backend.services.integrations import wa_outbox_worker

    def _head_of(value: ast.expr) -> str:
        """The exact head `_normalize_fall_off_reason` would compute at
        runtime for the literal (or literal-prefixed f-string) this AST
        node represents — mirroring `raw.split(":", 1)[0]` on the STATIC
        leading text, since every interpolation in this module's reason
        strings comes after the first literal segment (never inside it)."""
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value.split(":", 1)[0]
        if isinstance(value, ast.JoinedStr) and value.values:
            first = value.values[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                return first.value.split(":", 1)[0]
        raise AssertionError(
            f"cannot statically extract a reason head from {ast.dump(value)} "
            "— teach this helper the new shape before trusting the coverage "
            "assertion below"
        )

    assert wa_codex_leg.__file__ is not None
    tree = ast.parse(Path(wa_codex_leg.__file__).read_text(encoding="utf-8"))

    heads: set[str] = set()
    result_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "CodexLegResult"
    ]
    assert result_calls, "the module no longer constructs CodexLegResult — retarget this guard"
    for call in result_calls:
        by_kw = {kw.arg: kw.value for kw in call.keywords if kw.arg is not None}
        if "text" in by_kw:
            # The ONE success shape (`text=result.text, reason="completed"`)
            # — never written to the DB (attempt() only records when
            # result.text is None), so "completed" is deliberately excluded
            # from the coverage requirement below.
            continue
        for kw_name in ("reason", "fail"):
            if kw_name in by_kw:
                heads.add(_head_of(by_kw[kw_name]))

    assert wa_outbox_worker.__file__ is not None
    worker_tree = ast.parse(Path(wa_outbox_worker.__file__).read_text(encoding="utf-8"))
    worker_calls = [
        node
        for node in ast.walk(worker_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "record_fall_off_reason"
    ]
    assert worker_calls, (
        "the worker no longer calls record_fall_off_reason directly — "
        "retarget this guard (condition 2, provider_not_codex, is the ONE "
        "reason the leg itself never emits)"
    )
    for call in worker_calls:
        by_kw = {kw.arg: kw.value for kw in call.keywords if kw.arg is not None}
        if "raw_reason" in by_kw and isinstance(by_kw["raw_reason"], ast.Constant):
            heads.add(_head_of(by_kw["raw_reason"]))
        # A non-literal raw_reason (the wrapper's own `result.fail or
        # result.reason` call inside wa_codex_leg.py) contributes nothing
        # NEW here — its possible values are already the CodexLegResult
        # heads collected above.

    assert heads, "extraction found nothing — the AST walk is broken, not the coverage"
    missing = {h for h in heads if h not in wa_codex_leg._FALL_OFF_REASON_PREFIX_MAP}
    assert not missing, (
        f"these reason heads are emitted by the module but have no entry in "
        f"_FALL_OFF_REASON_PREFIX_MAP — they would silently normalize to "
        f"'unknown': {sorted(missing)}"
    )


def test_normalize_fall_off_reason_unrecognized_head_defaults_to_unknown() -> None:
    """The coverage guard above proves every head the module CAN emit today
    has a map entry — it says nothing about what happens the day a NEW,
    not-yet-catalogued head shows up (a genuinely new failure mode, or a
    caller that got the string wrong). That path is this function's
    `.get(head, "unknown")` fallback, and nothing else in this file drives
    it: `_normalize_fall_off_reason` itself is never called directly
    anywhere in the suite. Left uncovered, a mutation of that literal
    default (e.g. to some other bounded-looking string) would leave all
    138 tests in this file's suite green while the DB CHECK constraint on
    ``generation_fall_off_reason`` (exactly 20 allowed values, see the
    module docstring) started rejecting every genuinely-new reason instead
    of gracefully bucketing it under "unknown" — silently reintroducing
    the blindness this column exists to end.
    """
    # A colon-delimited head that is not a key in the map.
    assert wa_codex_leg._normalize_fall_off_reason("totally_unheard_of_reason:detail") == "unknown"
    # No colon at all — the whole string is the head, still unrecognized.
    assert wa_codex_leg._normalize_fall_off_reason("totally_unheard_of_reason") == "unknown"
    # Falsy input takes the function's earlier explicit `if not raw` branch
    # rather than reaching the map lookup at all — cover it too so the
    # function's full return contract (never raises, always "unknown" for
    # anything it cannot place) is proven, not just the map-lookup tail.
    assert wa_codex_leg._normalize_fall_off_reason("") == "unknown"


# ── the offer boundary is fail-closed (Codex r3) ────────────────────────────


@pytest.mark.asyncio
async def test_offer_exception_is_uncertain_never_a_fall_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Once offer_job has begun, an exception's transactional outcome is
    uncertain — the job may be committed. Falling off would run Gemini in
    this claim beside a durable job, skipping the drift protocol; the
    retry ladder resolves it (ALREADY_SPENT or a fresh offer)."""
    stubs = _wire_stubs(monkeypatch)
    stubs.offer_job.side_effect = RuntimeError("boom")
    result = await _run()
    assert result.fail == "offer_uncertain:RuntimeError"
    assert result.text is None and not result.stand_down
    stubs.wait_for_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_connection_release_failure_after_offered_is_uncertain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Codex r3 shape verbatim: offer_job returns OFFERED, then the
    pool-acquire block's EXIT raises during connection release. The offer
    is durable — this must take the retry ladder, never Gemini."""
    stubs = _wire_stubs(monkeypatch)
    pool = _FakePool(ScriptedConn(), release_exc_on_acquire=1)
    result = await _run(pool=pool)
    assert result.fail == "offer_uncertain:RuntimeError"
    stubs.offer_job.assert_awaited_once()
    stubs.wait_for_job.assert_not_awaited()
    stubs.consume_result.assert_not_awaited()


@pytest.mark.asyncio
async def test_offer_acquire_entry_failure_is_a_certain_fall_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex r4 finding 2: failing to ENTER the acquire means offer_job
    never ran — nothing durable exists, so burning a retry attempt would
    be wrong. Certain outcome: fall off to Gemini in the same claim."""
    stubs = _wire_stubs(monkeypatch)
    pool = _FakePool(ScriptedConn(), enter_exc_on_acquire=1)
    result = await _run(pool=pool)
    assert result.reason == "offer_acquire_error:RuntimeError"
    assert not result.fail and not result.stand_down
    stubs.offer_job.assert_not_awaited()
    stubs.wait_for_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_release_failure_after_certain_non_offered_keeps_the_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex r4 finding 2: a known non-OFFERED admission verdict is
    CERTAIN — a release failure after it must not launder it into
    offer_uncertain and burn a retry attempt."""
    stubs = _wire_stubs(
        monkeypatch, offer=OfferResult(OfferOutcome.BROKER_ABSENT)
    )
    pool = _FakePool(ScriptedConn(), release_exc_on_acquire=1)
    result = await _run(pool=pool)
    assert result.reason == "offer:broker_absent"
    assert not result.fail
    stubs.wait_for_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancellation_during_offer_releases_the_connection_and_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex r5: CancelledError is a BaseException — a manual __aexit__
    call outside a finally would be SKIPPED by cancellation during
    offer_job, leaving the connection checked out and hanging
    pool.close() at shutdown. The real async-with must release exactly
    once, and the cancellation must PROPAGATE (never be swallowed into a
    fall-off or fail)."""
    import asyncio

    stubs = _wire_stubs(monkeypatch)
    stubs.offer_job.side_effect = asyncio.CancelledError()
    pool = _FakePool(ScriptedConn())
    with pytest.raises(asyncio.CancelledError):
        await _run(pool=pool)
    assert pool.acquired == 1
    assert pool.released == 1
    stubs.wait_for_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_release_failure_cannot_replace_a_propagating_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex r6: when the release raises a plain Exception WHILE a
    CancelledError is propagating out of offer_job, PEP 3134 chaining
    makes the release error replace the cancellation — an outer
    except-Exception would swallow it into a fail and the worker would
    retry instead of stopping. The leg must restore and re-raise the
    cancellation."""
    import asyncio

    stubs = _wire_stubs(monkeypatch)
    stubs.offer_job.side_effect = asyncio.CancelledError()
    pool = _FakePool(ScriptedConn(), release_exc_on_error_exit=1)
    with pytest.raises(asyncio.CancelledError):
        await _run(pool=pool)
    assert pool.released == 1
    stubs.wait_for_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_offered_without_job_id_is_a_contract_break_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Codex r4 finding 1: OFFERED with no id is a broken transport
    contract over a possibly-durable job — Gemini beside it could never
    be waited on, consumed or discarded. Retry ladder, never fall-off."""
    stubs = _wire_stubs(monkeypatch, offer=OfferResult(OfferOutcome.OFFERED))
    result = await _run()
    assert result.fail == "offer_contract_break:missing_job_id"
    assert result.text is None and not result.stand_down
    stubs.wait_for_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_offered_without_thread_epoch_is_a_contract_break_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same contract-break class as a missing job_id (Codex r4 finding 1):
    without thread_epoch the post-completion drift check has nothing safe
    to fence against, so this must fail closed before ever waiting."""
    stubs = _wire_stubs(
        monkeypatch,
        offer=OfferResult(OfferOutcome.OFFERED, job_id=uuid.uuid4(), thread_epoch=None),
    )
    result = await _run()
    assert result.fail == "offer_contract_break:missing_thread_epoch"
    assert result.text is None and not result.stand_down
    stubs.wait_for_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_reattached_proceeds_to_wait_like_offered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REATTACHED is the fix for the historical bug: a retry offer on a
    row whose prior codex leg is still alive gets that job's id back and
    must wait/consume/finalize it exactly like a fresh OFFERED — never
    fall off and lose it to Gemini."""
    job_id = uuid.uuid4()
    stubs = _wire_stubs(
        monkeypatch,
        offer=OfferResult(OfferOutcome.REATTACHED, job_id=job_id, thread_epoch=3),
    )
    conn = ScriptedConn(
        fetchrow_results=[{"human_handling": False, "handling_version": 3}]
    )
    result = await _run(conn=conn)
    assert result.text == "the broker reply"
    assert result.stand_down is False
    stubs.wait_for_job.assert_awaited_once()
    assert stubs.wait_for_job.await_args.args[1] == job_id
    stubs.consume_result.assert_awaited_once()


@pytest.mark.asyncio
async def test_reattach_drift_check_fences_on_the_jobs_own_epoch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The critical correctness case: a REATTACHED job's post-completion
    drift check must compare against the PRIOR leg's own frozen
    thread_epoch (offer.thread_epoch), never this claim's freshly-read
    local epoch. Here the CURRENT claim's thread reads handling_version=5
    (it started later than the original leg), the reattached job was
    actually offered under epoch=3, and the thread's live handling_version
    is STILL 3 (nothing moved since the original offer) — using the local
    epoch (5) would wrongly declare drift and discard a perfectly valid
    completion; using the job's own epoch (3) correctly finds none."""
    job_id = uuid.uuid4()
    stubs = _wire_stubs(
        monkeypatch,
        offer=OfferResult(OfferOutcome.REATTACHED, job_id=job_id, thread_epoch=3),
    )
    conn = ScriptedConn(
        fetchrow_results=[{"human_handling": False, "handling_version": 3}]
    )
    result = await _run(conn=conn, thread=_thread(handling_version=5))
    assert result.text == "the broker reply"
    assert result.stand_down is False
    stubs.discard_completion.assert_not_awaited()


@pytest.mark.asyncio
async def test_reattach_drift_check_still_catches_real_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """INNOCENCE for the above: if the thread's live handling_version has
    actually moved PAST the reattached job's own frozen epoch, the drift
    check must still fire — the fix narrows WHICH epoch is authoritative,
    it does not disable the protocol."""
    job_id = uuid.uuid4()
    stubs = _wire_stubs(
        monkeypatch,
        offer=OfferResult(OfferOutcome.REATTACHED, job_id=job_id, thread_epoch=3),
    )
    conn = ScriptedConn(
        fetchrow_results=[
            {"human_handling": False, "handling_version": 4},  # moved past 3
            {"id": 42},  # atomic stand-down abort: fenced RETURNING
        ]
    )
    result = await _run(conn=conn, thread=_thread(handling_version=5))
    assert result.stand_down is True
    assert result.text is None
    stubs.discard_completion.assert_awaited_once()
    stubs.consume_result.assert_not_awaited()


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


# ── gate 0: the autoreply kill switch (Codex r1 finding 2) ──────────────────


@pytest.mark.asyncio
async def test_autoreply_off_falls_off_before_any_io(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WA_INBOX_BOT_AUTOREPLY off must silence the codex route exactly as it
    silences the Gemini one: the leg steps aside with zero IO, the worker
    proceeds to bot_generate_fn, and ITS first statement raises the
    BotStandingCondition that owns this switch. Innocence is every other
    test in this file (the harness arms the flag)."""
    stubs = _wire_stubs(monkeypatch)
    monkeypatch.delenv("WA_INBOX_BOT_AUTOREPLY")
    result = await _run()
    assert result.text is None and not result.stand_down and not result.fail
    assert result.reason == "autoreply_disabled"
    stubs.load_thread_context.assert_not_awaited()
    stubs.rag_client.post.assert_not_awaited()
    stubs.offer_job.assert_not_awaited()


# ── finalization (Codex r1 finding 1) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_served_text_is_the_finalized_text_not_the_raw_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The consumed completion is NEVER returned raw — what the worker sends
    is finalize_wa_answer's output (mutation pin: deleting the finalize call
    would return 'the broker reply' here and go red)."""
    stubs = _wire_stubs(
        monkeypatch,
        finalize=FinalizeResult(outcome=FinalizeOutcome.SEND, text="FINALIZED"),
    )
    conn = ScriptedConn(
        fetchrow_results=[{"human_handling": False, "handling_version": 3}]
    )
    result = await _run(conn=conn)
    assert result.text == "FINALIZED"
    stubs.finalize.assert_awaited_once()


@pytest.mark.asyncio
async def test_finalize_receives_codex_provider_and_the_frozen_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pipeline runs in its fail-closed codex configuration: provider
    'codex', secret_scan armed, price sources from the SAME wire the
    executor answered from, and the abstain verdict inputs from the FROZEN
    evidence — never recomputed."""
    stubs = _wire_stubs(monkeypatch)
    conn = ScriptedConn(
        fetchrow_results=[{"human_handling": False, "handling_version": 3}]
    )
    await _run(conn=conn)
    kwargs = stubs.finalize.await_args.kwargs
    assert kwargs["provider"] == "codex"
    assert kwargs["secret_scan"] is True
    assert "KITAS costs Rp 12.000.000" in kwargs["price_sources"]
    assert callable(kwargs["tell_a_human"])
    assert kwargs["query"] == "what is a KITAS?"
    assert kwargs["data"]["answer"] == "the broker reply"
    assert kwargs["data"]["abstain"] is False
    assert kwargs["data"]["context_length"] == 2
    assert kwargs["data"]["evidence_score"] == 0.85


@pytest.mark.asyncio
async def test_finalize_receives_env_derived_canary_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PR-6 canary wiring (spec 4.3): the values planted in the
    zantara-codex sandbox arrive as the WA_CODEX_CANARY_TOKENS Fly secret
    and MUST reach finalize's canary scan — an empty tuple here means the
    canary half of the tripwire is silently disarmed."""
    monkeypatch.setenv("WA_CODEX_CANARY_TOKENS", "canary-alpha-1, canary-beta-2 ,")
    stubs = _wire_stubs(monkeypatch)
    conn = ScriptedConn(
        fetchrow_results=[{"human_handling": False, "handling_version": 3}]
    )
    await _run(conn=conn)
    kwargs = stubs.finalize.await_args.kwargs
    assert kwargs["canary_tokens"] == ("canary-alpha-1", "canary-beta-2")


@pytest.mark.asyncio
async def test_no_canary_env_passes_an_empty_tuple_scan_still_armed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Innocence: unset env is a legal state (pre-provisioning) — empty
    canaries, but secret_scan stays True (the pattern half never disarms)."""
    monkeypatch.delenv("WA_CODEX_CANARY_TOKENS", raising=False)
    stubs = _wire_stubs(monkeypatch)
    conn = ScriptedConn(
        fetchrow_results=[{"human_handling": False, "handling_version": 3}]
    )
    await _run(conn=conn)
    kwargs = stubs.finalize.await_args.kwargs
    assert kwargs["canary_tokens"] == ()
    assert kwargs["secret_scan"] is True


@pytest.mark.asyncio
async def test_finalize_defect_falls_off_to_gemini(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec 2.3 TEXT_DEFECT: a defective codex text fails off so the Gemini
    leg regenerates and re-enters the same pipeline — never sent, never a
    stand-down, never the retry ladder."""
    stubs = _wire_stubs(
        monkeypatch,
        finalize=FinalizeResult(
            outcome=FinalizeOutcome.DEFECT,
            defect_reason="oversized_output",
            defect_message="too long",
        ),
    )
    conn = ScriptedConn(
        fetchrow_results=[{"human_handling": False, "handling_version": 3}]
    )
    result = await _run(conn=conn)
    assert result.text is None and not result.stand_down and not result.fail
    assert result.reason == "finalize:oversized_output"
    stubs.record_breaker_result.assert_not_awaited()


@pytest.mark.asyncio
async def test_finalize_blank_send_text_falls_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defensive: SEND promises non-empty text; a blank slipping through
    would otherwise read falsy in the worker and cascade into a Gemini
    generation AFTER a consumed completion."""
    stubs = _wire_stubs(
        monkeypatch,
        finalize=FinalizeResult(outcome=FinalizeOutcome.SEND, text="   "),
    )
    conn = ScriptedConn(
        fetchrow_results=[{"human_handling": False, "handling_version": 3}]
    )
    result = await _run(conn=conn)
    assert result.text is None and not result.stand_down
    assert result.reason == "finalize:blank_send_text"
    assert stubs.finalize.await_count == 1


# ── post-completion verification is fail-closed (Codex r1 finding 3) ────────


@pytest.mark.asyncio
async def test_drift_reread_failure_fails_closed_not_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A completion exists and drift can no longer be ruled out: a broken
    drift re-read must take the worker's retry ladder (fail), NEVER an
    in-claim fall-off that would let Gemini answer from the pre-drift
    thread snapshot with the drift check silently skipped."""
    stubs = _wire_stubs(monkeypatch)
    conn = ScriptedConn(fetchrow_exc=RuntimeError("pg gone"))
    result = await _run(conn=conn)
    assert result.fail == "post_completion:RuntimeError"
    assert result.text is None and not result.stand_down
    assert result.reason == ""
    stubs.consume_result.assert_not_awaited()
    stubs.record_breaker_result.assert_not_awaited()


@pytest.mark.asyncio
async def test_discard_failure_after_detected_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drift WAS detected but the discard broke: neither a stand-down (the
    completion is still pending-consume) nor a fall-off (fail-open) — the
    retry ladder re-claims with a fresh thread read. The transaction rolls
    the fenced abort back with it, so the row is still claimable."""
    stubs = _wire_stubs(monkeypatch)
    stubs.discard_completion.side_effect = RuntimeError("pg gone")
    conn = ScriptedConn(
        fetchrow_results=[
            {"human_handling": True, "handling_version": 3},
            {"id": 42},  # abort fence holds; the discard after it breaks
        ]
    )
    result = await _run(conn=conn)
    assert result.fail == "post_completion:RuntimeError"
    assert not result.stand_down
    stubs.consume_result.assert_not_awaited()


@pytest.mark.asyncio
async def test_stand_down_fence_lost_rolls_back_and_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fence goes FIRST inside the atomic abort: when the claim is
    gone, the raise rolls the whole transaction back — the discard never
    runs, the still-pending completion is left for the new owner's own
    drift protocol."""
    stubs = _wire_stubs(monkeypatch)
    conn = ScriptedConn(
        fetchrow_results=[
            {"human_handling": True, "handling_version": 3},
            None,  # abort fence returns no row: claim reclaimed elsewhere
        ]
    )
    result = await _run(conn=conn)
    assert result.fail == "stand_down_fence_lost"
    assert not result.stand_down
    stubs.discard_completion.assert_not_awaited()
    stubs.consume_result.assert_not_awaited()


# ── post-offer uncertainty is fail-closed (Codex r2 finding 2) ──────────────


@pytest.mark.asyncio
async def test_wait_exception_after_durable_offer_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After OFFERED the job is durable: an UNTYPED wait failure means the
    daemon may have completed and the thread may have drifted while we
    could not see it — falling off to Gemini in this claim would skip the
    drift protocol entirely. The typed FAILED/DEADLINE outcomes keep
    falling off (their transitions leave no pending completion)."""
    stubs = _wire_stubs(monkeypatch)
    stubs.wait_for_job.side_effect = RuntimeError("pg gone")
    result = await _run()
    assert result.fail == "wait_error:RuntimeError"
    assert result.text is None and not result.stand_down
    stubs.consume_result.assert_not_awaited()
    stubs.discard_completion.assert_not_awaited()


# ── evidence comes ONLY from the sealed wire (Codex r2 finding 1) ───────────


@pytest.mark.asyncio
async def test_evidence_is_read_from_the_sealed_wire_never_a_response_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guilt: a build response smuggling a DIVERGENT top-level
    evidence_inputs (abstain=false) alongside a wire whose SEALED copy says
    abstain=true must not steer the finalize verdict — the leg parses
    evidence out of the bytes the hash covers, and the stray key is
    ignored."""
    divergent_wire = (
        '{"history":[],"chunks":[{"text":"c","score":0.1}],'
        '"pricing_block":null,"persona_digest":"pd",'
        '"evidence_inputs":{"abstain":true,"context_length":0,'
        '"evidence_score":0.0},"thread_epoch":3}'
    )
    stubs = _wire_stubs(
        monkeypatch,
        build={
            "package_wire": divergent_wire,
            "package_hash": "abc123",
            "unbuildable": None,
            # The stray unsealed copy a divergent/hostile response could carry:
            "evidence_inputs": {
                "abstain": False,
                "context_length": 2,
                "evidence_score": 0.85,
            },
        },
    )
    conn = ScriptedConn(
        fetchrow_results=[{"human_handling": False, "handling_version": 3}]
    )
    await _run(conn=conn)
    data = stubs.finalize.await_args.kwargs["data"]
    assert data["abstain"] is True
    assert data["context_length"] == 0
    assert data["evidence_score"] == 0.0
    # The offer row's evidence_inputs is the SEALED copy too.
    assert '"abstain": true' in stubs.offer_job.await_args.kwargs["evidence_inputs"]


@pytest.mark.asyncio
async def test_consume_failure_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stubs = _wire_stubs(monkeypatch)
    stubs.consume_result.side_effect = RuntimeError("pg gone")
    conn = ScriptedConn(
        fetchrow_results=[{"human_handling": False, "handling_version": 3}]
    )
    result = await _run(conn=conn)
    assert result.fail == "post_completion:RuntimeError"
    assert result.text is None
    stubs.record_breaker_result.assert_not_awaited()


# ── G-P3 DLP wiring: the two load-bearing wires nothing else exercises ─────
#
# Final-gate finding (2026-08-20): 153 DLP tests existed, none through THIS
# module — a correct wa_dlp.py protects nothing if the leg that calls it
# never restores placeholders or never asks for redaction (scar family #2,
# "a correct function nothing exercises protects nothing"). These three
# tests pin BOTH wires through the real `_attempt` code path, using the
# harness above (no parallel harness).
#
# The default `_wire_stubs` finalize fake returns a FIXED FinalizeResult
# built from the `consume` kwarg at setup time — it never looks at what the
# leg actually passed as `data["answer"]`, so it cannot prove restore_text
# ran. These tests instead install an ECHO fake (`side_effect` reading
# `kwargs["data"]["answer"]`) so `result.text` reflects the REAL text the
# leg computed after restore_text — the closest thing to "prefer the real
# path" the mocked finalize boundary allows.


def _echo_finalize() -> AsyncMock:
    """Fake finalize that returns exactly what the leg passed as the
    answer — unlike `_wire_stubs`'s fixed-value default, this proves
    `restore_text`'s OUTPUT (not the harness's canned text) reaches
    `CodexLegResult.text`."""
    return AsyncMock(
        side_effect=lambda **kwargs: FinalizeResult(
            outcome=FinalizeOutcome.SEND, text=kwargs["data"]["answer"]
        )
    )


@pytest.mark.asyncio
async def test_leg_restores_placeholders_before_the_customer_sees_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guilt (restore): the build response carries a reversal_map and the
    consumed completion echoes a placeholder the generator saw in its
    redacted prompt — the leg must substitute it back BEFORE finalize/send.
    Mutation pin: deleting `text = restore_text(text, reversal_map)` in
    `wa_codex_leg._attempt` leaves the literal `[PII-PHONE-1]` token in
    `CodexLegResult.text` and this test goes red.

    The placeholder is embedded in an otherwise-normal sentence (not a bare
    token) so a real finalize's text-defect checks would not eat it —
    matching the coordinator's harness note.

    G-P3 r2 F6 (ORDER pin): asserting on `result.text` alone only proves
    restore happened SOMEWHERE in the pipeline — it cannot tell "restore
    before finalize" apart from "finalize first, then restore the
    RETURNED text", because `_echo_finalize` simply forwards whatever it
    is given straight back out, and either ordering would still leave
    `result.text` fully restored. The assertion on
    `echo_finalize.await_args.kwargs["data"]["answer"]` below closes that
    gap: it inspects the value the finalize call ITSELF received, which
    can only be the restored text if `restore_text` ran BEFORE that call.
    Mutation pin: moving the `restore_text` call to run on `result.text`
    AFTER `finalize_wa_answer` returns would leave this kwarg holding the
    raw `[PII-PHONE-1]` placeholder and this assertion goes red, even
    though the old `result.text`-only assertions below would still pass."""
    build = {**_GOOD_BUILD, "reversal_map": {"[PII-PHONE-1]": "+628111234567"}}
    stubs = _wire_stubs(
        monkeypatch,
        build=build,
        consume="Please call [PII-PHONE-1] to confirm your appointment.",
    )
    echo_finalize = _echo_finalize()
    monkeypatch.setattr(wa_codex_leg, "finalize_wa_answer", echo_finalize)
    conn = ScriptedConn(
        fetchrow_results=[{"human_handling": False, "handling_version": 3}]
    )
    result = await _run(conn=conn)
    assert result.text is not None
    assert "+628111234567" in result.text
    assert "[PII-" not in result.text
    stubs.rag_client.post.assert_awaited_once()  # sanity: build actually ran

    received_answer = echo_finalize.await_args.kwargs["data"]["answer"]
    assert "+628111234567" in received_answer
    assert "[PII-" not in received_answer


@pytest.mark.asyncio
async def test_build_request_always_carries_dlp_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guilt (flag): the leg is the ONLY caller of /api/wa-package/build
    that hands customer text to an external generator (module docstring,
    wa_codex_leg.py:240-243) — every build request must ask for redaction.
    Mutation pin: dropping `"dlp": True` from the POST body ships the
    UNREDACTED package to codex and this test goes red."""
    stubs = _wire_stubs(monkeypatch)
    await _run()
    kwargs = stubs.rag_client.post.await_args.kwargs
    captured = kwargs["json"]
    assert captured["dlp"] is True


@pytest.mark.asyncio
async def test_absent_reversal_map_passes_completion_through_byte_identical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Innocence: a build response with NO reversal_map (a dlp=False build,
    or a redaction that found nothing to redact) must leave the consumed
    completion untouched — no strip, no crash, no placeholder-shaped noise
    introduced. `_GOOD_BUILD` carries no `reversal_map` key, so
    `built.get("reversal_map") or {}` resolves to `{}` here — the ordinary
    default every other test in this file already relies on implicitly;
    this test makes it an explicit, named guarantee."""
    original = "The office is open Monday to Friday, 9am-5pm."
    _wire_stubs(monkeypatch, consume=original)
    monkeypatch.setattr(wa_codex_leg, "finalize_wa_answer", _echo_finalize())
    conn = ScriptedConn(
        fetchrow_results=[{"human_handling": False, "handling_version": 3}]
    )
    result = await _run(conn=conn)
    assert result.text == original


# --- migration 297: finalize sub-reasons ---------------------------------
#
# Same shape of blindness migration 291 cured one row up in the map, and
# the same shape of proof. Measured cost: outbox row 363
# (2026-08-28T21:43:52Z) had THREE successful codex generations
# (`consumed_ok`, 9711/10137/8521 ms) discarded by the finalize stage, and
# every one recorded the same "finalize_defect" — the STAGE, never the
# CAUSE.


@pytest.mark.parametrize(
    ("defect_reason", "expected_stored"),
    [
        ("internal_monologue_leak", "finalize_internal_monologue_leak"),
        ("pricing_outside_package", "finalize_pricing_outside_package"),
        ("empty_rag_answer", "finalize_empty_rag_answer"),
        ("persona_escalate_marker", "finalize_persona_escalate_marker"),
        ("empty_after_escalate_strip", "finalize_empty_after_escalate_strip"),
        ("workflow_only_output", "finalize_workflow_only_output"),
        ("empty_after_channel_format", "finalize_empty_after_channel_format"),
        ("oversized_output", "finalize_oversized_output"),
        ("rag_abstain", "finalize_rag_abstain"),
        ("blank_send_text", "finalize_blank_send_text"),
    ],
)
def test_finalize_sub_reason_normalizes_distinctly(
    defect_reason: str, expected_stored: str
) -> None:
    """Every finalize DEFECT branch must land in its OWN DB value.

    Guilt, not innocence: each of these returned "finalize_defect" before
    migration 297, so this parametrization goes red on the pre-297 code.
    """
    assert (
        wa_codex_leg._normalize_fall_off_reason(f"finalize:{defect_reason}")
        == expected_stored
    )


def test_finalize_unrecognized_sub_reason_falls_back_to_generic_bucket() -> None:
    """A future defect_reason nobody has taught this module yet must still
    land in a value that says "the finalize stage refused" — never in the
    module-wide "unknown" bucket a genuinely uncatalogued HEAD gets. The
    head here is perfectly well known; only the sub-reason is new."""
    assert (
        wa_codex_leg._normalize_fall_off_reason("finalize:some_future_defect")
        == "finalize_defect"
    )


def test_finalize_secret_egress_never_stores_the_pattern_name() -> None:
    """`secret_egress:<pattern-name>` is the ONE finalize reason with a
    variable suffix. The stored value must be the bare bucket: the suffix
    names which scanner pattern hit — this column is read by dashboards and
    pasted into reports, and an unbounded suffix would also defeat the
    CHECK constraint that exists to keep this vocabulary closed."""
    for pattern in ("anthropic_key", "canary_token", "some_future_pattern"):
        stored = wa_codex_leg._normalize_fall_off_reason(
            f"finalize:secret_egress:{pattern}"
        )
        assert stored == "finalize_secret_egress"
        assert pattern not in stored


def test_finalize_sub_reason_map_covers_every_defect_reason_wa_finalize_can_emit() -> None:
    """The map must not be able to rot in silence.

    Read the SOURCE of ``wa_finalize.py`` — never a hand-copied list, which
    would be a proof that cannot fail once it drifts from the code — and
    assert every ``defect_reason`` that module can actually produce is a
    key here. A new DEFECT branch added later with nobody teaching this map
    would otherwise fill the column with the generic bucket again, and
    "why was this answer discarded?" would be unanswerable a third time.

    A ``defect_reason=`` whose value this helper cannot resolve statically
    is a FAILURE, never a skip: an un-analysable node is exactly where a
    new shape would hide.
    """
    import ast
    from pathlib import Path

    from backend.services.integrations import wa_finalize

    assert wa_finalize.__file__ is not None
    tree = ast.parse(Path(wa_finalize.__file__).read_text(encoding="utf-8"))

    def _literal(node: ast.expr) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr) and node.values:
            first = node.values[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                # e.g. f"secret_egress:{hit}" -> the static leading segment
                return first.value
        return None

    # (a) every literal bound to a name the DEFECT sites forward verbatim,
    #     plus (b) the veto function's own returned tuples.
    #
    # An assignment to one of those names that this helper cannot resolve to
    # a literal is a FAILURE, not a skip. Waving it through was a real hole
    # (found by the adversarial review of this PR): a future dict-dispatch
    # refactor writing `human_reason = _LOOKUP["x"]` would forward a value
    # this scan never sees, `missing` would stay empty, and the guard would
    # pass while the map rotted — precisely what it exists to prevent.
    forwarded = {"reason", "veto", "human_reason"}
    indirect: set[str] = set()

    def _collect(node: ast.expr, where: str) -> None:
        lit = _literal(node)
        if lit is not None:
            indirect.add(lit)
            return
        if isinstance(node, ast.BoolOp):
            for operand in node.values:
                _collect(operand, where)
            return
        # `reason = "x" if cond else None` — a real shape in this module
        # (the strict resolver above found it; the permissive first draft
        # of this test walked straight past it). Both arms count.
        if isinstance(node, ast.IfExp):
            _collect(node.body, where)
            _collect(node.orelse, where)
            return
        # An explicit `None` is "no reason yet", not an unresolved shape.
        if isinstance(node, ast.Constant) and node.value is None:
            return
        # `reason = human_reason or "..."` legitimately references a name
        # whose own literal sources this same scan collects elsewhere.
        if isinstance(node, ast.Name) and node.id in forwarded:
            return
        # `veto = _codex_egress_veto(...)` binds the veto helper's return
        # value, and that helper's own returned tuples are collected by the
        # ast.Return branch below — so the call itself needs no resolving.
        # Any OTHER call bound to these names does, hence the name check.
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_codex_egress_veto"
        ):
            return
        raise AssertionError(
            f"cannot statically resolve {where} = {ast.dump(node)} — teach "
            "this helper the new shape before trusting the coverage "
            "assertion below"
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in forwarded:
                    _collect(node.value, target.id)
        elif isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple):
            if node.value.elts:
                lit = _literal(node.value.elts[0])
                if lit is not None:
                    indirect.add(lit)

    # (c) the direct `defect_reason=` keywords.
    #
    # KEYWORD-ONLY BY CONVENTION, enforced here (second hole found by the
    # adversarial review): `FinalizeResult` is a plain frozen dataclass, so
    # `FinalizeResult(FinalizeOutcome.DEFECT, "", None, "new_defect", ...)`
    # is legal Python and completely invisible to a scan that reads only
    # `node.keywords`. Rather than teach the scan to count positions — which
    # silently breaks the day a field is inserted — require the call site to
    # keep naming its arguments.
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "FinalizeResult"
            and node.args
        ):
            raise AssertionError(
                "FinalizeResult(...) is constructed with positional "
                f"argument(s) at line {node.lineno} of wa_finalize.py — a "
                "positional defect_reason is invisible to the coverage scan "
                "below. Pass every field by keyword."
            )

    direct: set[str] = set()
    defect_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for kw in node.keywords
        if kw.arg == "defect_reason"
    ]
    assert defect_calls, (
        "wa_finalize no longer passes defect_reason= — retarget this guard"
    )
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg != "defect_reason":
                continue
            lit = _literal(kw.value)
            if lit is not None:
                direct.add(lit)
                continue
            # Not a literal: it must be one of the names whose literal
            # sources (a)/(b) above already collected. Anything else is a
            # shape this helper has not been taught — fail loudly.
            if isinstance(kw.value, ast.Name) and kw.value.id in forwarded:
                continue
            if (
                isinstance(kw.value, ast.Subscript)
                and isinstance(kw.value.value, ast.Name)
                and kw.value.value.id in forwarded
            ):
                continue
            raise AssertionError(
                "cannot statically resolve defect_reason="
                f"{ast.dump(kw.value)} — teach this helper the new shape "
                "before trusting the coverage assertion below"
            )

    emitted = direct | indirect
    # The leg's own defensive fallback, which wa_finalize never emits.
    emitted.add("blank_send_text")

    known = set(wa_codex_leg._FINALIZE_SUB_REASON_MAP) | {
        wa_codex_leg._FINALIZE_EGRESS_SCAN_HEAD
    }
    missing = {
        reason
        for reason in emitted
        if reason.partition(":")[0] not in known
    }
    assert not missing, (
        f"wa_finalize can emit defect_reason(s) {sorted(missing)} that "
        "_FINALIZE_SUB_REASON_MAP does not know — they would silently "
        "collapse into the generic 'finalize_defect' bucket again"
    )


def test_every_stored_fall_off_value_is_allowed_by_the_live_check_constraint() -> None:
    """Code and DB must agree on the closed vocabulary.

    A value this module can WRITE that the CHECK constraint REJECTS is not
    a mislabel — it is an exception on the write path, i.e. a second reason
    nothing was recorded. Parse the newest migration that (re-)defines the
    constraint and assert it admits every value the maps can produce.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[4]
    migrations = root / "backend" / "db" / "migrations_v2"
    assert migrations.is_dir(), f"migrations dir not found at {migrations}"
    # Sort by the leading INTEGER, never by filename: lexicographically
    # "1000_..." sorts BEFORE "999_...", so a filename sort silently starts
    # validating against a stale constraint the day this repo passes
    # migration 999 (third finding of this PR's adversarial review; same
    # "a proxy is not the content" class as superscar #9).
    defining = sorted(
        (
            p
            for p in migrations.glob("*.sql")
            if "wa_outbox_generation_fall_off_reason_check"
            in p.read_text(encoding="utf-8")
        ),
        key=lambda p: int(p.name.split("_", 1)[0]),
    )
    assert defining, "no migration defines the fall-off-reason CHECK constraint"
    newest = defining[-1]
    # The UP block only — the file's ROLLBACK section restores the older,
    # narrower vocabulary on purpose.
    up = newest.read_text(encoding="utf-8").split("=== ROLLBACK ===")[0]
    allowed = set(re.findall(r"'([a-z_]+)'", up))

    produced = (
        set(wa_codex_leg._FALL_OFF_REASON_PREFIX_MAP.values())
        | set(wa_codex_leg._UNBUILDABLE_SUB_REASON_MAP.values())
        | set(wa_codex_leg._FINALIZE_SUB_REASON_MAP.values())
        | {"finalize_secret_egress", "unknown"}
    )
    assert produced <= allowed, (
        f"{sorted(produced - allowed)} can be written by the code but is "
        f"rejected by the CHECK constraint in {newest.name}"
    )
