"""Focused unit tests for check_claim_inventory / check_evidence_support /
check_citation_integrity (checks 6, 8, 9) — edge cases the B6b golden
fixtures do not individually isolate. See evidence_check.py's own module
docstring for the design rationale each assertion below is checking.

Author: Claude Opus 5 (lane B1b — client-bot engine).
"""

from __future__ import annotations

import pytest

from backend.services.client_bot.policy.evidence_check import (
    check_citation_integrity,
    check_claim_inventory,
    check_evidence_support,
)
from backend.services.client_bot.policy.types import GateReason, GateVerdict
from backend.tests.duebot.goldens.builders import (
    make_abstain_candidate,
    make_answer_candidate,
    make_claim,
    make_evidence_item,
    make_grounding_bundle,
)

# ---------------------------------------------------------------------------
# check_claim_inventory (check 6)
# ---------------------------------------------------------------------------


def test_empty_answer_passes_trivially() -> None:
    # BrainCandidate's own model_validator forbids an "answer"-disposition
    # candidate with an empty answer string (answer must be non-empty when
    # disposition="answer") — so the empty-answer case this check's early
    # return guards against is reached via a non-answer disposition
    # (abstain/handoff), which the contract does allow to carry answer="".
    candidate = make_abstain_candidate("inv")
    assert check_claim_inventory(candidate) is None


def test_currency_without_price_claim_is_uninventoried_numeric() -> None:
    candidate = make_answer_candidate("inv", answer="Biayanya sekitar Rp 5.000.000.")
    outcome = check_claim_inventory(candidate)
    assert outcome is not None
    assert outcome.verdict == GateVerdict.ABSTAIN
    assert outcome.reason == GateReason.UNINVENTORIED_NUMERIC_STATEMENT


def test_currency_with_price_claim_passes() -> None:
    claim = make_claim(suffix="p1", text="Rp 5.000.000", kind="price", price_service_key="svc_1")
    candidate = make_answer_candidate("inv", answer="Biayanya sekitar Rp 5.000.000.", claims=(claim,))
    assert check_claim_inventory(candidate) is None


def test_legal_citation_without_regulatory_claim_is_uninventoried_regulated() -> None:
    candidate = make_answer_candidate("inv", answer="Sesuai UU No. 6 Tahun 2011, Anda wajib melapor.")
    outcome = check_claim_inventory(candidate)
    assert outcome is not None
    assert outcome.verdict == GateVerdict.ABSTAIN
    assert outcome.reason == GateReason.UNINVENTORIED_REGULATED_STATEMENT


def test_legal_citation_with_regulatory_claim_passes() -> None:
    claim = make_claim(suffix="r1", text="UU No. 6 Tahun 2011", kind="regulatory")
    candidate = make_answer_candidate(
        "inv", answer="Sesuai UU No. 6 Tahun 2011, Anda wajib melapor.", claims=(claim,)
    )
    assert check_claim_inventory(candidate) is None


def test_plain_answer_with_no_claims_passes() -> None:
    candidate = make_answer_candidate("inv", answer="Tentu, saya bisa bantu proses ini.")
    assert check_claim_inventory(candidate) is None


# ---------------------------------------------------------------------------
# check_evidence_support (check 8)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kind_not_in_required_set_skips_evidence_entirely() -> None:
    claim = make_claim(suffix="p1", text="price note", kind="price", evidence_ids=(), price_service_key="svc_1")
    candidate = make_answer_candidate("sup", answer="text", claims=(claim,))
    grounding = make_grounding_bundle("sup")
    outcome = await check_evidence_support(
        candidate, grounding, citation_policy_all_factual=False, semantic_verifier=None
    )
    assert outcome is None


@pytest.mark.asyncio
async def test_all_factual_widens_to_every_claim_kind() -> None:
    claim = make_claim(suffix="p1", text="price note", kind="price", evidence_ids=(), price_service_key="svc_1")
    candidate = make_answer_candidate("sup", answer="text", claims=(claim,))
    grounding = make_grounding_bundle("sup")
    outcome = await check_evidence_support(
        candidate, grounding, citation_policy_all_factual=True, semantic_verifier=None
    )
    assert outcome is not None
    assert outcome.reason == GateReason.CLAIM_MISSING_EVIDENCE_ID


@pytest.mark.asyncio
async def test_required_kind_with_no_evidence_ids_is_missing_evidence_id() -> None:
    claim = make_claim(suffix="r1", text="claim", kind="regulatory", evidence_ids=())
    candidate = make_answer_candidate("sup", answer="text", claims=(claim,))
    grounding = make_grounding_bundle("sup")
    outcome = await check_evidence_support(
        candidate, grounding, citation_policy_all_factual=False, semantic_verifier=None
    )
    assert outcome is not None
    assert outcome.reason == GateReason.CLAIM_MISSING_EVIDENCE_ID


@pytest.mark.asyncio
async def test_evidence_id_absent_from_bundle_is_deterministic_check_failed() -> None:
    claim = make_claim(suffix="r1", text="claim", kind="regulatory", evidence_ids=("ev-ghost",))
    candidate = make_answer_candidate("sup", answer="text", claims=(claim,))
    grounding = make_grounding_bundle("sup", evidence=(make_evidence_item("sup", suffix="ev1"),))
    outcome = await check_evidence_support(
        candidate, grounding, citation_policy_all_factual=False, semantic_verifier=None
    )
    assert outcome is not None
    assert outcome.reason == GateReason.EVIDENCE_DETERMINISTIC_CHECK_FAILED


@pytest.mark.asyncio
async def test_no_verifier_wired_is_verifier_outage() -> None:
    claim = make_claim(suffix="r1", text="claim", kind="regulatory", evidence_ids=("ev-ev1",))
    candidate = make_answer_candidate("sup", answer="text", claims=(claim,))
    grounding = make_grounding_bundle("sup", evidence=(make_evidence_item("sup", suffix="ev1"),))
    outcome = await check_evidence_support(
        candidate, grounding, citation_policy_all_factual=False, semantic_verifier=None
    )
    assert outcome is not None
    assert outcome.reason == GateReason.EVIDENCE_VERIFIER_OUTAGE
    assert outcome.reason_detail == "no semantic verifier registered — fail-safe per Sol §1.6"


@pytest.mark.asyncio
async def test_verifier_returning_none_is_also_verifier_outage() -> None:
    claim = make_claim(suffix="r1", text="claim", kind="regulatory", evidence_ids=("ev-ev1",))
    candidate = make_answer_candidate("sup", answer="text", claims=(claim,))
    grounding = make_grounding_bundle("sup", evidence=(make_evidence_item("sup", suffix="ev1"),))

    async def _outage_verifier(_claim, _evidence):
        return None

    outcome = await check_evidence_support(
        candidate, grounding, citation_policy_all_factual=False, semantic_verifier=_outage_verifier
    )
    assert outcome is not None
    assert outcome.reason == GateReason.EVIDENCE_VERIFIER_OUTAGE
    assert "verifier reported outage" in outcome.reason_detail


@pytest.mark.asyncio
async def test_low_score_is_below_threshold() -> None:
    claim = make_claim(suffix="r1", text="claim", kind="regulatory", evidence_ids=("ev-ev1",))
    candidate = make_answer_candidate("sup", answer="text", claims=(claim,))
    grounding = make_grounding_bundle("sup", evidence=(make_evidence_item("sup", suffix="ev1"),))

    async def _low_score_verifier(_claim, _evidence):
        return 0.1

    outcome = await check_evidence_support(
        candidate, grounding, citation_policy_all_factual=False, semantic_verifier=_low_score_verifier
    )
    assert outcome is not None
    assert outcome.reason == GateReason.EVIDENCE_SEMANTIC_SUPPORT_BELOW_THRESHOLD


@pytest.mark.asyncio
async def test_high_score_passes() -> None:
    claim = make_claim(suffix="r1", text="claim", kind="regulatory", evidence_ids=("ev-ev1",))
    candidate = make_answer_candidate("sup", answer="text", claims=(claim,))
    grounding = make_grounding_bundle("sup", evidence=(make_evidence_item("sup", suffix="ev1"),))

    async def _high_score_verifier(_claim, _evidence):
        return 0.95

    outcome = await check_evidence_support(
        candidate, grounding, citation_policy_all_factual=False, semantic_verifier=_high_score_verifier
    )
    assert outcome is None


# ---------------------------------------------------------------------------
# check_citation_integrity (check 9)
# ---------------------------------------------------------------------------


def test_cited_id_not_in_bundle_is_citation_id_not_in_bundle() -> None:
    candidate = make_answer_candidate("cit", answer="text", cited_evidence_ids=("ev-ghost",))
    grounding = make_grounding_bundle("cit", evidence=(make_evidence_item("cit", suffix="ev1"),))
    outcome = check_citation_integrity(candidate, grounding, citation_policy_all_factual=False)
    assert outcome is not None
    assert outcome.reason == GateReason.CITATION_ID_NOT_IN_BUNDLE


def test_cited_id_backing_no_claim_is_unused_evidence() -> None:
    candidate = make_answer_candidate("cit", answer="text", cited_evidence_ids=("ev-ev1",))
    grounding = make_grounding_bundle("cit", evidence=(make_evidence_item("cit", suffix="ev1"),))
    outcome = check_citation_integrity(candidate, grounding, citation_policy_all_factual=False)
    assert outcome is not None
    assert outcome.reason == GateReason.CITATION_TO_UNUSED_EVIDENCE


def test_required_claim_evidence_not_displayed_is_missing_displayed_citation() -> None:
    claim = make_claim(suffix="r1", text="claim", kind="regulatory", evidence_ids=("ev-ev1",))
    candidate = make_answer_candidate("cit", answer="text", claims=(claim,), cited_evidence_ids=())
    grounding = make_grounding_bundle("cit", evidence=(make_evidence_item("cit", suffix="ev1"),))
    outcome = check_citation_integrity(candidate, grounding, citation_policy_all_factual=False)
    assert outcome is not None
    assert outcome.reason == GateReason.CLAIM_MISSING_DISPLAYED_CITATION


def test_required_claim_evidence_not_displayed_under_all_factual_is_kbli_specific_reason() -> None:
    claim = make_claim(suffix="r1", text="claim", kind="regulatory", evidence_ids=("ev-ev1",))
    candidate = make_answer_candidate("cit", answer="text", claims=(claim,), cited_evidence_ids=())
    grounding = make_grounding_bundle("cit", evidence=(make_evidence_item("cit", suffix="ev1"),))
    outcome = check_citation_integrity(candidate, grounding, citation_policy_all_factual=True)
    assert outcome is not None
    assert outcome.reason == GateReason.KBLI_CLASSIFICATION_MISSING_ALL_FACTUAL_CITATION


def test_properly_cited_claim_passes() -> None:
    claim = make_claim(suffix="r1", text="claim", kind="regulatory", evidence_ids=("ev-ev1",))
    candidate = make_answer_candidate("cit", answer="text", claims=(claim,), cited_evidence_ids=("ev-ev1",))
    grounding = make_grounding_bundle("cit", evidence=(make_evidence_item("cit", suffix="ev1"),))
    outcome = check_citation_integrity(candidate, grounding, citation_policy_all_factual=False)
    assert outcome is None
