"""Focused unit tests for check_pricing (check 7) — Golden Rule 11
enforcement. See its own module docstring for why this is stricter than
wa_finalize.py's veto and why HANDOFF (not POLICY_BLOCKED) is this
module's terminal verdict.

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

import pytest

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
    claim = make_claim(suffix="p1", text="Rp 790.000", kind="price")
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
    claim = make_claim(suffix="p1", text="setengah dari harga standar", kind="price")
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
# RED — team-lead gate finding, 2026-08-25 (SPEC-price-service-binding.md).
#
# "verbatim match against the snapshot" is weaker than it sounds:
# _snapshot_values() flattens EVERY numeric token from EVERY entry in the
# WHOLE catalogue into one flat set[int], so check_pricing() can only ask
# "is this amount A real Bali Zero price anywhere", never "is this amount
# THE price of the service actually under discussion". A real price for
# service B, quoted in an answer about service A, is a real number and
# passes. This is the same shape as `branching-verdict-single-price-key`
# (memory, 2026-08-23/24) — a system with zero hallucinated digits that is
# still wrong on every priced answer, because "real" and "correct for this
# question" are not the same property.
#
# xfail(strict=True), not a plain skip or a silent pass: the failure stays
# ON THE RECORD in every CI run rather than reading as noise, and `strict`
# means the day SPEC-price-service-binding.md is implemented, this xpasses
# and CI goes red until the marker is removed — nobody lands that fix
# without this test having been red first. Do NOT widen check_pricing's
# regex/floor logic to make this pass; the fix is service-identity binding
# (the spec), not tighter numeric matching.
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "ACCEPTED GAP (SPEC-price-service-binding.md): check_pricing has no "
        "way to bind a quoted amount to the service a claim is about — "
        "PricingSnapshot carries no per-item service identity and Claim has "
        "no field to reference one. A real price for the WRONG service "
        "passes because _snapshot_values() only tests catalogue-wide "
        "membership. Fix is a contract change (PricingSnapshot item "
        "identity + Claim.price_service_key), team-lead go-ahead required, "
        "precondition for arming real client sends — not a shadow-mode "
        "blocker, not tonight's work."
    ),
)
def test_check_pricing_catches_a_real_price_for_the_wrong_service() -> None:
    """E33G KITAS is Rp 12.000.000; Working KITAS is Rp 25.000.000 — both
    real, both in the snapshot. The candidate is answering an E33G KITAS
    question but states the Working KITAS price. Today's check_pricing
    extracts 25000000, finds it in the flattened snapshot value set (it
    IS a real Bali Zero price, just for the wrong service), and returns
    None — ALLOW-eligible. This assertion states the CORRECT behavior
    (the check should catch this) and fails against today's
    implementation, which is the point.
    """
    snapshot = make_pricing_snapshot(
        "wrong-svc",
        items=(
            {
                "services": {
                    "kitas": {
                        "e33g_kitas": {"name": "E33G KITAS", "price": "Rp 12.000.000"},
                        "working_kitas": {"name": "Working KITAS", "price": "Rp 25.000.000"},
                    }
                }
            },
        ),
    )
    claim = make_claim(suffix="p1", text="Rp 25.000.000", kind="price")
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
