"""FinalPolicyGate.evaluate() — the 11 ordered checks, verified two ways:

1. Direct unit tests for check 1 (delivery fence) and the collaborator
   wiring (idempotency probe, canary tokens) that only ``final_gate.py``
   itself owns.
2. A GOLDEN-FIXTURE COMPLIANCE test: every B6b ``client.*`` golden fixture
   that carries a real ``candidate``/``grounding`` pair (16 of 19 — the
   other 3 model states that never reach generation, or an engine-level
   provider-exhaustion path with no candidate to evaluate at all) is run
   through the REAL ``evaluate()`` and its ``(verdict, reason)`` is
   asserted against the fixture's own ``expected_decision`` — the fixtures
   were authored (B6b lane) BEFORE this gate existed
   ("There is no FinalPolicyGate.evaluate() yet to run these against" —
   ``fixtures.py``'s own module docstring), so this is the first time they
   are actually exercised end-to-end, not merely constructed.

The compliance test needs two test-only doubles because two collaborators
this lane deliberately did not wire a real implementation for
(``semantic_verifier``, ``handoff_service``'s repository) are exactly what
several fixtures need exercised:

- ``_word_overlap_semantic_verifier``: a crude, deliberately simple stand-in
  for a real embedding/LLM verifier. It exists ONLY to drive these 16
  fixtures to the same verdict a real verifier would reach on them — it is
  NOT a claim that this heuristic is production-grade (see
  ``evidence_check.py``'s own docstring on why no real verifier is wired
  yet). Its one real judgment: a claim naming a number/date not present in
  its cited evidence text scores low (this is what makes
  "client.deadline-date-mismatch" correctly abstain); anything else scores
  full support.
- ``_FixtureHandoffService``: reports a fixed ``HandoffOutcome`` per call —
  the two ``client.handoff-insert-succeeds-and-fails`` variants use an
  IDENTICAL candidate/request shape and differ only in what the (out of
  scope) durable store would have reported, so the test drives that
  outcome directly rather than faking a repository.

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

import re

import pytest

from backend.channels.profiles import CLIENT_WA_V1
from backend.services.client_bot.contracts import BrainCandidate
from backend.services.client_bot.policy.final_gate import DeliveryFence, FinalPolicyGate
from backend.services.client_bot.policy.handoff import ClientHandoffService, HandoffOutcome
from backend.services.client_bot.policy.types import GateReason, GateVerdict
from backend.tests.duebot.goldens import fixtures as F
from backend.tests.duebot.goldens.builders import (
    make_answer_candidate,
    make_brain_request,
    make_canonical_message,
    make_grounding_bundle,
)

_OK_FENCE = DeliveryFence(
    thread_owned=True,
    thread_epoch_current=True,
    human_taken_over=False,
    terminal_response_already_sent=False,
    service_window_expired=False,
)


def _request(case_id: str = "gate-case"):
    message = make_canonical_message(case_id)
    grounding = make_grounding_bundle(case_id)
    return make_brain_request(case_id, message=message, profile=CLIENT_WA_V1, grounding=grounding)


# ---------------------------------------------------------------------------
# Check 1 — delivery and thread fence. Runs before the candidate is even
# inspected, so a trivial answer candidate is enough to prove the fence
# alone decides the outcome.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fence_kwargs", "expected_reason"),
    [
        ({"thread_owned": False}, GateReason.THREAD_OWNERSHIP_LOST),
        ({"thread_epoch_current": False}, GateReason.THREAD_EPOCH_STALE),
        ({"human_taken_over": True}, GateReason.HUMAN_TAKEOVER_ACTIVE),
        ({"terminal_response_already_sent": True}, GateReason.DUPLICATE_TERMINAL_RESPONSE),
        ({"service_window_expired": True}, GateReason.SERVICE_WINDOW_EXPIRED),
    ],
    ids=["ownership-lost", "epoch-stale", "human-takeover", "duplicate", "window-expired"],
)
async def test_delivery_fence_drops_before_touching_the_candidate(fence_kwargs, expected_reason) -> None:
    base = {
        "thread_owned": True,
        "thread_epoch_current": True,
        "human_taken_over": False,
        "terminal_response_already_sent": False,
        "service_window_expired": False,
    }
    fence = DeliveryFence(**{**base, **fence_kwargs})
    gate = FinalPolicyGate()
    req = _request()
    candidate = make_answer_candidate("gate-case", answer="anything at all")
    decision = await gate.evaluate(candidate, req, fence)
    assert decision.verdict == GateVerdict.DROP
    assert decision.reason == expected_reason
    assert decision.rendered_text is None


@pytest.mark.asyncio
async def test_fence_check_order_reports_the_first_failing_reason() -> None:
    """Multiple fence fields failing at once — the check order (thread
    ownership before epoch before takeover before duplicate before window)
    must report the FIRST one, deterministically.
    """
    fence = DeliveryFence(
        thread_owned=False,
        thread_epoch_current=False,
        human_taken_over=True,
        terminal_response_already_sent=True,
        service_window_expired=True,
    )
    gate = FinalPolicyGate()
    decision = await gate.evaluate(make_answer_candidate("gate-case"), _request(), fence)
    assert decision.reason == GateReason.THREAD_OWNERSHIP_LOST


# ---------------------------------------------------------------------------
# Check 2 — package hash / control-byte scanning.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_package_hash_mismatch_is_text_defect() -> None:
    req = _request()
    candidate = make_answer_candidate("gate-case", answer="fine")
    # deliberately NOT matching req.grounding.package_sha256
    assert candidate.package_sha256 != req.grounding.package_sha256
    gate = FinalPolicyGate()
    decision = await gate.evaluate(candidate, req, _OK_FENCE)
    assert decision.verdict == GateVerdict.TEXT_DEFECT
    assert decision.reason == GateReason.PACKAGE_HASH_MISMATCH
    assert decision.is_retryable is True


@pytest.mark.asyncio
async def test_control_byte_in_answer_is_invalid_encoding() -> None:
    req = _request()
    candidate = BrainCandidate(
        **{
            **make_answer_candidate("gate-case", answer="fine\x07text").model_dump(),
            "package_sha256": req.grounding.package_sha256,
        }
    )
    gate = FinalPolicyGate()
    decision = await gate.evaluate(candidate, req, _OK_FENCE)
    assert decision.verdict == GateVerdict.TEXT_DEFECT
    assert decision.reason == GateReason.INVALID_ENCODING


# ---------------------------------------------------------------------------
# Collaborator wiring only final_gate.py owns.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotency_probe_conflict_is_text_defect() -> None:
    req = _request()
    candidate = BrainCandidate(
        **{
            **make_answer_candidate("gate-case", answer="A short clean answer.").model_dump(),
            "package_sha256": req.grounding.package_sha256,
        }
    )
    gate = FinalPolicyGate(idempotency_probe=lambda: False)
    decision = await gate.evaluate(candidate, req, _OK_FENCE)
    assert decision.verdict == GateVerdict.TEXT_DEFECT
    assert decision.reason == GateReason.IDEMPOTENCY_CONFLICT_AT_INSERT


@pytest.mark.asyncio
async def test_idempotency_probe_none_defers_to_outbox_constraint() -> None:
    """No probe wired at all — the gate must ALLOW (not fail closed on a
    missing collaborator here; the outbox table's own UNIQUE constraint is
    the real authority, per the module docstring).
    """
    req = _request()
    candidate = BrainCandidate(
        **{
            **make_answer_candidate("gate-case", answer="A short clean answer.").model_dump(),
            "package_sha256": req.grounding.package_sha256,
        }
    )
    gate = FinalPolicyGate()
    decision = await gate.evaluate(candidate, req, _OK_FENCE)
    assert decision.verdict == GateVerdict.ALLOW
    assert decision.reason == GateReason.PASSED_ALL_CHECKS
    assert decision.rendered_text is not None


@pytest.mark.asyncio
async def test_zero_wiring_gate_never_false_allows_a_regulatory_claim() -> None:
    """A FinalPolicyGate built with NO collaborators (the constructor's own
    defaults) must still fail safe on a claim that needs semantic backing
    — this is the "safer, not broken" contract the class docstring makes.
    """
    req = _request()
    from backend.tests.duebot.goldens.builders import make_claim, make_evidence_item

    grounding = make_grounding_bundle(
        "zero-wire", evidence=(make_evidence_item("zero-wire", suffix="ev1"),)
    )
    req = make_brain_request(
        "zero-wire", message=make_canonical_message("zero-wire"), profile=CLIENT_WA_V1, grounding=grounding
    )
    claim = make_claim(suffix="c1", text="A regulated claim.", kind="regulatory", evidence_ids=("ev-ev1",))
    candidate = BrainCandidate(
        **{
            **make_answer_candidate(
                "zero-wire", answer="A regulated claim in the answer.", claims=(claim,)
            ).model_dump(),
            "package_sha256": req.grounding.package_sha256,
        }
    )
    gate = FinalPolicyGate()  # zero wiring
    decision = await gate.evaluate(candidate, req, _OK_FENCE)
    assert decision.verdict != GateVerdict.ALLOW
    assert decision.reason == GateReason.EVIDENCE_VERIFIER_OUTAGE


# ---------------------------------------------------------------------------
# Golden-fixture compliance — see module docstring.
# ---------------------------------------------------------------------------


def _word_overlap_semantic_verifier(claim, evidence_items):
    async def _inner() -> float:
        combined = " ".join(e.text for e in evidence_items)
        claim_numbers = set(re.findall(r"\d+", claim.text))
        evidence_numbers = set(re.findall(r"\d+", combined))
        if claim_numbers and not claim_numbers.issubset(evidence_numbers):
            return 0.2
        return 1.0

    return _inner()


class _FixtureHandoffService(ClientHandoffService):
    def __init__(self, outcome: HandoffOutcome) -> None:
        super().__init__(None)
        self._outcome = outcome

    async def create_handoff(self, candidate, request) -> HandoffOutcome:  # noqa: ANN001
        return self._outcome


# The one fixture whose defect (a planted sandbox canary token) requires a
# per-request secret the FinalPolicyGate constructor takes as a static
# list — every other fixture uses the default empty tuple.
_CANARY_TOKENS_BY_CASE: dict[str, tuple[str, ...]] = {
    "client-secret-canary-output-001": ("CANARY-4F91A2C7",),
}

_RUNNABLE_GOLDENS = tuple(fx for fx in F.CLIENT_GOLDENS if fx.candidate is not None and fx.grounding is not None)
_SKIPPED_GOLDENS = tuple(fx for fx in F.CLIENT_GOLDENS if fx.candidate is None or fx.grounding is None)


def test_every_client_golden_is_accounted_for_by_this_suite() -> None:
    """Pins the 16/3 split so a future fixture addition cannot silently
    fall through neither this compliance test nor a documented skip.
    """
    assert len(_RUNNABLE_GOLDENS) == 16
    assert {fx.case_id for fx in _SKIPPED_GOLDENS} == {
        "client-human-takeover-thread-epoch-race-001",  # covered above, by fence, not fixture
        "client-duplicate-meta-delivery-001",  # covered above, by fence, not fixture
        "client-both-providers-unavailable-001",  # engine-level, no candidate — engine.py's tests
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("fx", _RUNNABLE_GOLDENS, ids=[fx.case_id for fx in _RUNNABLE_GOLDENS])
async def test_final_policy_gate_matches_every_client_golden(fx) -> None:  # noqa: ANN001
    # The builder module computes BrainCandidate.package_sha256 and
    # GroundingBundle.package_sha256 independently (by design — see
    # builders.py) so they do not match by construction; a real provider
    # is required to echo the SAME hash it received (check 2's whole
    # point), so fixtures need this one field corrected before check 2
    # would otherwise reject every fixture on a hash mismatch that isn't
    # the scenario under test. Normal construction (not model_copy/
    # model_construct — CLAUDE.md/test_contracts_freeze.py's own rule).
    candidate = BrainCandidate(**{**fx.candidate.model_dump(), "package_sha256": fx.grounding.package_sha256})
    request = make_brain_request(fx.case_id, message=fx.message, profile=fx.profile, grounding=fx.grounding)
    outcome = HandoffOutcome.ROW_INSERTED if "succeeds" in fx.case_id else HandoffOutcome.ROW_INSERT_FAILED
    gate = FinalPolicyGate(
        semantic_verifier=_word_overlap_semantic_verifier,
        handoff_service=_FixtureHandoffService(outcome),
        canary_tokens=_CANARY_TOKENS_BY_CASE.get(fx.case_id, ()),
    )
    decision = await gate.evaluate(candidate, request, _OK_FENCE)
    assert decision.verdict == fx.expected_decision.verdict, (
        f"{fx.case_id}: verdict {decision.verdict.value!r} != expected "
        f"{fx.expected_decision.verdict.value!r} (reason={decision.reason.value!r}, "
        f"detail={decision.reason_detail!r})"
    )
    assert decision.reason == fx.expected_decision.reason, (
        f"{fx.case_id}: reason {decision.reason.value!r} != expected {fx.expected_decision.reason.value!r}"
    )
    # rendered_text: only pinned where the golden's own is_retryable/ALLOW
    # shape requires SOMETHING non-None — the exact rendered bytes are not
    # asserted (no renderer algorithm is frozen by any contract; see
    # surface_check.py's own module docstring on RENDERER_ADDED_CONTENT).
    if fx.expected_decision.verdict == GateVerdict.ALLOW:
        assert decision.rendered_text is not None
    else:
        assert decision.rendered_text is None
