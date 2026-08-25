"""Focused unit tests for check_pricing (check 7) — Golden Rule 11
enforcement. See its own module docstring for why this is stricter than
wa_finalize.py's veto and why HANDOFF (not POLICY_BLOCKED) is this
module's terminal verdict.

Author: Claude Opus 5 (lane B1b — client-bot engine).
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
