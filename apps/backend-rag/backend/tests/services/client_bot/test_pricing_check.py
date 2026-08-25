"""Focused unit tests for check_pricing (check 7) — Golden Rule 11
enforcement. See its own module docstring for why this is stricter than
wa_finalize.py's veto and why HANDOFF (not POLICY_BLOCKED) is this
module's terminal verdict.

Author: Claude Opus 5 (lane B1b — client-bot engine; lane B1c —
service-identity binding, 2026-08-25).
"""

from __future__ import annotations

from backend.services.client_bot.policy.pricing_check import check_pricing
from backend.services.client_bot.policy.types import GateReason, GateVerdict
from backend.tests.duebot.goldens.builders import (
    make_answer_candidate,
    make_claim,
    make_pricing_snapshot,
)


def test_no_snapshot_no_price_content_passes() -> None:
    candidate = make_answer_candidate("price", answer="Prosesnya memakan waktu beberapa hari.")
    assert check_pricing(candidate, None) is None


def test_no_snapshot_with_price_claim_is_handoff() -> None:
    claim = make_claim(suffix="p1", text="Rp 790.000", kind="price", price_service_key="svc_1")
    candidate = make_answer_candidate("price", answer="Biayanya Rp 790.000.", claims=(claim,))
    outcome = check_pricing(candidate, None)
    assert outcome is not None
    assert outcome.verdict == GateVerdict.HANDOFF
    assert outcome.reason == GateReason.NO_PRICING_SNAPSHOT_AVAILABLE


def test_no_snapshot_with_bare_currency_in_answer_is_handoff() -> None:
    candidate = make_answer_candidate("price", answer="Biayanya sekitar Rp 790.000.")
    outcome = check_pricing(candidate, None)
    assert outcome is not None
    assert outcome.reason == GateReason.NO_PRICING_SNAPSHOT_AVAILABLE


def test_amount_matching_snapshot_passes() -> None:
    snapshot = make_pricing_snapshot("price", items=({"price": "Rp 790.000"},))
    candidate = make_answer_candidate("price", answer="Biayanya sekitar Rp 790.000 saja.")
    assert check_pricing(candidate, snapshot) is None


def test_amount_not_in_snapshot_is_price_not_in_snapshot() -> None:
    snapshot = make_pricing_snapshot("price", items=({"price": "Rp 790.000"},))
    candidate = make_answer_candidate("price", answer="Biayanya Rp 999.000.")
    outcome = check_pricing(candidate, snapshot)
    assert outcome is not None
    assert outcome.verdict == GateVerdict.HANDOFF
    assert outcome.reason == GateReason.PRICE_NOT_IN_SNAPSHOT


def test_amount_below_idr_floor_is_ignored_even_if_absent_from_snapshot() -> None:
    snapshot = make_pricing_snapshot("price", items=({"price": "Rp 790.000"},))
    candidate = make_answer_candidate("price", answer="Ada biaya materai sekitar Rp 10.")
    assert check_pricing(candidate, snapshot) is None


def test_price_claim_with_no_detectable_amount_is_recomputed() -> None:
    snapshot = make_pricing_snapshot("price", items=({"price": "Rp 790.000"},))
    claim = make_claim(
        suffix="p1", text="setengah dari harga standar", kind="price", price_service_key="svc_1"
    )
    candidate = make_answer_candidate(
        "price", answer="Biayanya setengah dari harga standar kami.", claims=(claim,)
    )
    outcome = check_pricing(candidate, snapshot)
    assert outcome is not None
    assert outcome.verdict == GateVerdict.HANDOFF
    assert outcome.reason == GateReason.PRICE_RECOMPUTED_BY_MODEL


def test_juta_multiplier_canonicalizes_to_the_same_value_as_full_digits() -> None:
    snapshot = make_pricing_snapshot("price", items=({"price": "Rp 99.000.000"},))
    candidate = make_answer_candidate("price", answer="Biayanya sekitar Rp 99 juta.")
    assert check_pricing(candidate, snapshot) is None


def test_usd_amount_matching_snapshot_passes() -> None:
    snapshot = make_pricing_snapshot("price", items=({"price": "$500"},))
    candidate = make_answer_candidate("price", answer="Biayanya sekitar $500.")
    assert check_pricing(candidate, snapshot) is None


def test_usd_amount_below_floor_is_ignored() -> None:
    snapshot = make_pricing_snapshot("price", items=({"price": "$500"},))
    candidate = make_answer_candidate("price", answer="Biaya admin kecil sekitar $5.")
    assert check_pricing(candidate, snapshot) is None


# ---------------------------------------------------------------------------
# Service-identity binding (SPEC-price-service-binding.md, 2026-08-25).
#
# "verbatim match against the snapshot" is weaker than it sounds:
# _snapshot_values() flattens EVERY numeric token from EVERY entry in the
# WHOLE catalogue into one flat set[int], so check_pricing() could only ask
# "is this amount A real Bali Zero price anywhere", never "is this amount
# THE price of the service actually under discussion". A real price for
# service B, quoted in an answer about service A, is a real number and used
# to pass. This is the same shape as `branching-verdict-single-price-key`
# (memory, 2026-08-23/24) — a system with zero hallucinated digits that is
# still wrong on every priced answer, because "real" and "correct for this
# question" are not the same property.
#
# Was xfail(strict=True) here — the RED companion test the team lead's gate
# finding required before implementation. Now that
# _snapshot_index_by_key()/Claim.price_service_key (P1/P2/P3) are wired,
# this is a normal green test, not an accepted gap: the guilt case below
# (test_check_pricing_catches_a_real_price_for_the_wrong_service) proves the
# defect is closed, and the innocence cases (P5) prove the fix did not turn
# into a check so strict it rejects correct answers.
# ---------------------------------------------------------------------------

# Two per-service items, "key" as the first-class identity field — this is
# the shape GroundingBundleBuilder._build_pricing_snapshot() now actually
# produces (P1: one item per service, never the whole nested catalogue
# folded into one opaque blob).
_WRONG_SVC_ITEMS = (
    {"key": "e33g_kitas", "name": "E33G KITAS", "price": "Rp 12.000.000"},
    {"key": "working_kitas", "name": "Working KITAS", "price": "Rp 25.000.000"},
)


def test_check_pricing_catches_a_real_price_for_the_wrong_service() -> None:
    """E33G KITAS is Rp 12.000.000; Working KITAS is Rp 25.000.000 — both
    real, both in the snapshot. The candidate's claim is bound to E33G
    KITAS (``price_service_key="e33g_kitas"``) but states the Working
    KITAS price. Layer 1 (catalogue-wide) alone would let 25.000.000
    through — it IS a real Bali Zero price, just for the wrong service.
    Layer 2 (P1-P3, the fix) catches it: the claim's own text (25.000.000)
    does not match the price bound to ITS OWN ``price_service_key``
    (12.000.000 for ``e33g_kitas``).
    """
    snapshot = make_pricing_snapshot("wrong-svc", items=_WRONG_SVC_ITEMS)
    claim = make_claim(
        suffix="p1", text="Rp 25.000.000", kind="price", price_service_key="e33g_kitas"
    )
    candidate = make_answer_candidate(
        "wrong-svc",
        answer="Untuk E33G KITAS, biayanya adalah Rp 25.000.000.",
        claims=(claim,),
    )
    outcome = check_pricing(candidate, snapshot)
    assert outcome is not None, (
        "a real price for the WRONG service passed check_pricing — the "
        "amount is genuine (it prices Working KITAS) but the claim/answer "
        "is about E33G KITAS, and nothing here checked that the two match"
    )
    assert outcome.verdict == GateVerdict.HANDOFF
    assert outcome.reason == GateReason.PRICE_NOT_IN_SNAPSHOT


# ---------------------------------------------------------------------------
# P5 — innocence counterparts. Per the orchestrator's 2026-08-25 ruling:
# "the ones that decide whether this is landable are: the right price for
# the right service still passes; a service mentioned without a price
# claim does not trip it; and a price for a service the client asked about
# in a PREVIOUS turn behaves the way the implementer decides — that
# decision must be stated, not left for the implementation to settle by
# accident."
# ---------------------------------------------------------------------------


def test_correct_price_for_its_own_service_still_passes() -> None:
    """The SAME two-item snapshot as the guilt case above — proves P1-P3
    do not turn into a check so strict it rejects a correct answer. E33G
    KITAS's own price (12.000.000) bound to its own key must pass even
    though a DIFFERENT real price (25.000.000, Working KITAS) sits right
    next to it in the same snapshot.
    """
    snapshot = make_pricing_snapshot("wrong-svc", items=_WRONG_SVC_ITEMS)
    claim = make_claim(
        suffix="p1", text="Rp 12.000.000", kind="price", price_service_key="e33g_kitas"
    )
    candidate = make_answer_candidate(
        "wrong-svc",
        answer="Untuk E33G KITAS, biayanya adalah Rp 12.000.000.",
        claims=(claim,),
    )
    assert check_pricing(candidate, snapshot) is None


def test_service_mentioned_without_a_price_claim_does_not_trip_the_binding() -> None:
    """A regulatory (non-"price") claim that happens to name a service, with
    no currency amount anywhere in the answer, must not engage the P1-P3
    binding at all — there is no price claim to bind, and check_pricing's
    ``price_claims`` list is empty for a purely regulatory answer.
    """
    snapshot = make_pricing_snapshot("wrong-svc", items=_WRONG_SVC_ITEMS)
    claim = make_claim(
        suffix="r1",
        text="E33G KITAS requires a company sponsor.",
        kind="regulatory",
    )
    candidate = make_answer_candidate(
        "wrong-svc",
        answer="E33G KITAS requires a company sponsor.",
        claims=(claim,),
    )
    assert check_pricing(candidate, snapshot) is None


def test_price_service_key_absent_from_snapshot_is_handoff() -> None:
    """A price claim bound to a service key the snapshot does not carry at
    all (e.g. scoped out by domain, per P4, or simply a key that does not
    exist) has no price to compare against — treated the same as "amount
    not in snapshot", never as a silent pass.
    """
    snapshot = make_pricing_snapshot("wrong-svc", items=_WRONG_SVC_ITEMS)
    claim = make_claim(
        suffix="p1", text="Rp 12.000.000", kind="price", price_service_key="not_a_real_service"
    )
    candidate = make_answer_candidate(
        "wrong-svc",
        answer="Biayanya adalah Rp 12.000.000.",
        claims=(claim,),
    )
    outcome = check_pricing(candidate, snapshot)
    assert outcome is not None
    assert outcome.verdict == GateVerdict.HANDOFF
    assert outcome.reason == GateReason.PRICE_NOT_IN_SNAPSHOT


def test_cross_turn_service_context_is_not_check_pricings_job() -> None:
    """Decision stated per the orchestrator's ruling: check_pricing has NO
    visibility into ``GroundingBundle.history`` (it receives only
    ``candidate`` and ``pricing``) and does not attempt to re-derive a
    claim's service binding from a prior conversation turn. A price
    mentioned because the client asked about it in an EARLIER turn must
    still carry its own correct ``price_service_key`` on THIS turn's
    claim — supplying that binding correctly (including from prior-turn
    context) is the generating provider's responsibility, upstream of
    this check. This test pins that division of responsibility: the same
    claim/answer pair is judged identically regardless of what
    conversation history produced it, because this function never
    receives history at all.
    """
    snapshot = make_pricing_snapshot("wrong-svc", items=_WRONG_SVC_ITEMS)
    claim = make_claim(
        suffix="p1", text="Rp 12.000.000", kind="price", price_service_key="e33g_kitas"
    )
    candidate = make_answer_candidate(
        "wrong-svc",
        answer="Seperti yang kita bahas, biaya E33G KITAS adalah Rp 12.000.000.",
        claims=(claim,),
    )
    # check_pricing's signature has no `history` parameter at all — this
    # call is the proof: the function cannot special-case "the client asked
    # in a previous turn" even if it wanted to.
    assert check_pricing(candidate, snapshot) is None
