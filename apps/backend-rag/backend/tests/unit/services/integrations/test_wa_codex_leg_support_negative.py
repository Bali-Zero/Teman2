"""B2.1 Terminal route — the support-negative branch in `wa_codex_leg.py`.

research/operations/2026-09-11-bot-staff-room/B2-engine.md §4 B2.1 "Terminal
route": stopping package construction is NOT the right disposition for an
unsupported sealed package — an unbuildable package returns a fall-off
reason (`wa_codex_leg.py:580-581`) that the worker raises as
`codex_leg_fell_off` (`wa_outbox_worker.py:1026-1027`) into its retry/failure
ladder, so the client would wait through five attempts for a question that
can never become answerable. This module proves the branch added BEFORE the
broker offer instead: when the sealed package's `evidence_inputs
["support_verdict"]` is anything other than SUPPORTED, the leg generates
NOTHING and hands the sealed decision straight to the UNCHANGED finalizer's
safe-abstention path, returning a TERMINAL served-text result through the
existing worker fence — never a generation-failure classification.

Self-contained fixtures (deliberately NOT imported from the sibling
`backend/tests/unit/services/test_wa_codex_leg.py`, which predates this
branch and is owned by other chaos-table rows): a minimal pool/conn double
and a `_wire_stubs`-shaped monkeypatch helper, trimmed to exactly what this
branch touches. No client PII anywhere in these fixtures — every string is
a synthetic, non-real-looking placeholder.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.integrations import wa_codex_leg
from backend.services.integrations.wa_broker import (
    OfferOutcome,
    OfferResult,
    WaitOutcome,
    WaitResult,
)
from backend.services.integrations.wa_finalize import FinalizeOutcome, FinalizeResult
from backend.services.integrations.wa_outbox_worker import _CODEX_LEG_STANDING_REASONS


class _ScriptedConn:
    """Answers the post-completion drift re-read with a no-drift row
    (`human_handling=False`, `handling_version` matching `_thread()`'s
    default `3`) so the SUPPORTED/absent-verdict positive-control paths —
    which run all the way past the broker consume in these tests — do not
    spuriously stand down. The support-negative branch itself never reaches
    this read at all (it returns before the offer), so this shape is inert
    for those tests."""

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        return {"human_handling": False, "handling_version": 3}

    async def execute(self, sql: str, *args: Any) -> str:
        return "UPDATE 1"

    def transaction(self) -> Any:
        class _Tx:
            async def __aenter__(self) -> None:
                return None

            async def __aexit__(self, *exc: Any) -> bool:
                return False

        return _Tx()


class _FakePool:
    def __init__(self, conn: _ScriptedConn | None = None) -> None:
        self._conn = conn or _ScriptedConn()

    def acquire(self) -> Any:
        conn = self._conn

        class _CM:
            async def __aenter__(self) -> _ScriptedConn:
                return conn

            async def __aexit__(self, *exc: Any) -> bool:
                return False

        return _CM()


def _thread() -> dict[str, Any]:
    return {
        "thread_id": 7,
        "counterpart_phone": "628111",
        "human_handling": False,
        "last_customer_at": datetime.now(timezone.utc) - timedelta(minutes=5),
        "handling_version": 3,
    }


def _build_response(payload: dict[str, Any]) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=payload)
    return resp


def _wire(support_verdict: str | None, *, evidence_score: float = 0.85) -> str:
    """A sealed-wire JSON string carrying the additive B2.1 support keys.

    `support_verdict=None` OMITS the key entirely (models a pre-B2.1 /
    dlp=False package — "not consulted"), matching
    `wa_package_builder.build_context_package`'s own `None` convention.
    """
    evidence_inputs: dict[str, Any] = {
        "abstain": False,
        "context_length": 2,
        "evidence_score": evidence_score,
        "domain": "visa",
    }
    if support_verdict is not None:
        evidence_inputs["support_verdict"] = support_verdict
        evidence_inputs["support_votes"] = [support_verdict, support_verdict, "UNKNOWN"]
        evidence_inputs["support_judge"] = "codex:gpt-5.6-terra"
        evidence_inputs["support_fallback_used"] = False

    return json.dumps(
        {
            "history": [],
            "chunks": [{"text": "Synthetic retrieved chunk about a KITAS.", "score": 0.9}],
            "pricing_block": None,
            "persona_digest": "pd",
            "evidence_inputs": evidence_inputs,
            "thread_epoch": 3,
        }
    )


def _wire_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    support_verdict: str | None,
    finalize_result: FinalizeResult | None = None,
    consume_text: str = "the broker completion text",
    evidence_score: float = 0.85,
) -> SimpleNamespace:
    monkeypatch.setenv("WA_GENERATION_PROVIDER", "codex")
    monkeypatch.setenv("WA_INBOX_BOT_AUTOREPLY", "true")

    load = AsyncMock(return_value=("what is a KITAS?", [{"role": "user", "content": "hi"}]))
    monkeypatch.setattr(wa_codex_leg, "_load_thread_context", load)

    client = MagicMock()
    build = {
        "package_wire": _wire(support_verdict, evidence_score=evidence_score),
        "package_hash": "abc123",
        "unbuildable": None,
    }
    client.post = AsyncMock(return_value=_build_response(build))
    monkeypatch.setattr(wa_codex_leg, "_get_rag_client", AsyncMock(return_value=client))

    fin_calls: list[dict[str, Any]] = []

    async def _fake_finalize(*, data: dict[str, Any], **kwargs: Any) -> FinalizeResult:
        fin_calls.append(data)
        if finalize_result is not None:
            return finalize_result
        return FinalizeResult(outcome=FinalizeOutcome.SEND, text=consume_text)

    fin = AsyncMock(side_effect=_fake_finalize)
    monkeypatch.setattr(wa_codex_leg, "finalize_wa_answer", fin)

    tell = AsyncMock(return_value=True)
    monkeypatch.setattr(wa_codex_leg, "_tell_a_human", tell)

    stub = SimpleNamespace(
        OfferOutcome=OfferOutcome,
        OfferResult=OfferResult,
        WaitOutcome=WaitOutcome,
        WaitResult=WaitResult,
        deadline_seconds=lambda: 15,
        offer_job=AsyncMock(
            return_value=OfferResult(OfferOutcome.OFFERED, job_id=uuid.uuid4(), thread_epoch=3)
        ),
        wait_for_job=AsyncMock(return_value=WaitResult(WaitOutcome.COMPLETED)),
        consume_result=AsyncMock(return_value=consume_text),
        discard_completion=AsyncMock(return_value=None),
        record_breaker_result=AsyncMock(return_value=None),
    )
    monkeypatch.setattr(wa_codex_leg, "wa_broker", stub)
    stub.rag_client = client
    stub.finalize = fin
    stub.finalize_calls = fin_calls
    stub.tell = tell
    return stub


async def _run() -> wa_codex_leg.CodexLegResult:
    return await wa_codex_leg.attempt(
        _FakePool(),  # type: ignore[arg-type]
        outbox_id=42,
        thread_id=7,
        message_id=4200,
        claim_token=uuid.uuid4(),
        outbox_expected_status="generating",
        thread=_thread(),
    )


# ── the support-negative branch ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_unsupported_verdict_never_offers_to_the_broker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stubs = _wire_stubs(monkeypatch, support_verdict="NOT_SUPPORTED")
    await _run()
    stubs.offer_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_unsupported_verdict_generates_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stubs = _wire_stubs(monkeypatch, support_verdict="UNKNOWN")
    await _run()
    stubs.wait_for_job.assert_not_awaited()
    stubs.consume_result.assert_not_awaited()


@pytest.mark.asyncio
async def test_unsupported_verdict_is_not_a_generation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`leg.fail` empty and `leg.reason` is not one the worker turns into
    `codex_leg_fell_off` — the worker's own elif-chain
    (`wa_outbox_worker.py:1009-1027`) classifies ANY `leg.text is not None`
    result as a served completion before it ever inspects `leg.reason`
    against `_CODEX_LEG_STANDING_REASONS` or falls through to
    `codex_leg_fell_off`; both properties are asserted directly."""
    _wire_stubs(monkeypatch, support_verdict="UNAVAILABLE")
    result = await _run()
    assert result.fail == ""
    assert not result.stand_down
    assert result.text is not None
    assert result.reason not in _CODEX_LEG_STANDING_REASONS
    assert result.reason != ""


@pytest.mark.asyncio
async def test_unsupported_verdict_preserves_d6_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D6: the branch generates nothing, so a later `abstained_at` (B2.3b's
    DB write, not this leg's job) stays NULL while `evidence_score` carries
    the SEALED package's frozen score — asserted here as the shape the
    finalizer call carries, never a DB row. `answer=""` (nothing was
    generated) and `abstain=True` is FORCED regardless of the sealed
    package's own `abstain` flag (the wire above sets `abstain: False`),
    because this branch exists precisely to guarantee the safe-abstention
    disposition independent of whether the scorer's own fail-closed
    relevance-zeroing already produced the same label by a different path."""
    stubs = _wire_stubs(monkeypatch, support_verdict="NOT_SUPPORTED", evidence_score=0.85)
    await _run()

    assert len(stubs.finalize_calls) == 1
    data = stubs.finalize_calls[0]
    assert data["answer"] == ""
    assert data["abstain"] is True
    assert data["context_length"] == 2
    assert data["evidence_score"] == 0.85


@pytest.mark.asyncio
async def test_supported_verdict_positive_control_still_reaches_the_offer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The supported path is UNCHANGED: a SUPPORTED verdict still runs the
    full broker offer -> wait -> consume -> finalize sequence and serves the
    generated completion, exactly as before this branch existed."""
    stubs = _wire_stubs(monkeypatch, support_verdict="SUPPORTED", consume_text="the real answer")
    result = await _run()

    stubs.offer_job.assert_awaited_once()
    stubs.wait_for_job.assert_awaited_once()
    stubs.consume_result.assert_awaited_once()
    assert result.text == "the real answer"
    assert result.fail == ""
    assert not result.stand_down


@pytest.mark.asyncio
async def test_missing_support_verdict_does_not_enter_the_unsupported_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`support_verdict` absent (`None`, e.g. a dlp=False / pre-B2.1 sealed
    package) means "not consulted" — matches
    `calculate_evidence_score`'s own "not consulted, no change" contract —
    and must NOT be treated as unsupported: the leg falls through to the
    unchanged offer path."""
    stubs = _wire_stubs(monkeypatch, support_verdict=None, consume_text="the real answer")
    result = await _run()

    stubs.offer_job.assert_awaited_once()
    assert result.text == "the real answer"
