"""seq-9's 8 newly-inserted rules, pinned as witnesses against the REAL
evaluator (house pattern: ``test_seq7_sponsor_witnesses.py``).

Each test below isolates ONE product's per-product proof
(``evaluator.evaluate_product``, called directly — not the aggregated
multi-product ``evaluate()``/``Decision``) so a review-gated sibling
product elsewhere in the pack can never mask the rule under test. This is
the exact "masking" disease class ``test_seq7_sponsor_witnesses.py``'s
module docstring documents at length for E33A/E33C (a global ``Decision``
returns HUMAN_REVIEW_REQUIRED the instant ANY product is REVIEW, which
would hide a HARD_FILTER regression on a completely different product),
and the same shape as the D1/D2/D12 production masking bug
``HANDOFF-2026-08-08-voa-conclusive-rate.md`` diagnosed.

Guilt+innocence pairs pinned here (E5 increment 3 refuter fix list,
FIX-5b — Codex F1/F3/F6, Kimi F1):

- E33A (``hf.e33a.sponsor-not-government``): sponsor GOVERNMENT is never
  excluded by this HARD_FILTER; sponsor EMPLOYER is excluded.
- E33B/E33C (``hf.e33b/c.sponsor-not-government-or-none``): sponsor in
  {GOVERNMENT, NONE} is never excluded; sponsor EMPLOYER is excluded.
- E30F (``el.e30f-student-support``, pins FIX-1): sponsor EDUCATION with
  admission+sponsor confirmed reaches SUPPORTED; sponsor NONE does not —
  before the cure this exact fact pattern (a generic boolean treated as
  equivalent to the sponsor-type gate) reached SUPPORTED with ANY
  sponsor.type, including NONE (Codex refuter finding 1).
- E30E (``el.e30e-student-support``): sponsor EDUCATION and sponsor
  INDIVIDUAL both reach SUPPORTED (CL-E30E-05's two-pathway reading —
  E30E, unlike E30F, allows a WNI individual guarantor); sponsor NONE
  does not.
- E33G (``review.e33g.income-evidence``): a clean remote-work
  configuration (the SAME 4 facts that also satisfy the healthy sibling
  ``el.e33g.remote-work``, SUPPORT) resolves to REVIEW, not SUPPORTED —
  the OD-1 narrowing this rule exists for (spec Step 3b / Assembly
  decision #2).
- E23U/E23V (``review.e23u/v.requested-product``): an explicit
  ``intent.requested_product_code`` fires review for THAT product only,
  never its sibling; an UNKNOWN requested-product-code never manufactures
  a REVIEW (``on_unknown=NEEDS_INPUT``, not ``HUMAN_REVIEW``) — this is the
  path production actually exercises today, since ``fact-mapper.ts:469``
  hard-codes this fact ``NOT_ASKED`` (Kimi refuter finding 2).
- UNKNOWN ``sponsor.type`` on E33A/E33B/E33C: never EXCLUDED — a
  HARD_FILTER may not assume exclusion from missing sponsor data.

Two of those witnesses had their incidental PROOF SHAPE revised on
2026-09-06 (``BLOCKED_UNKNOWN`` → ``UNSUPPORTED``) by the decisiveness
reorder — ``evaluate_product`` now tests purpose-feasibility before it
blocks on an input-tagged gate unknown, and all five products named above
carry zero SUPPORT rules, so no fact resolution could ever have made them
candidates. Each test's own stated SAFETY assertion (``is not EXCLUDED`` /
``is not REVIEW``) is untouched and still the first line of the test; the
mechanism the shape used to stand for is pinned directly, on a product that
CAN be recommended, in ``test_evaluator_purpose_feasibility_precedence.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.compile_pack import (
    load_rule_pack_payload,
    wrap_as_unsigned_pack,
)
from backend.services.visa_engine import compiler, evaluator
from backend.services.visa_engine.enums import FactPath
from backend.services.visa_engine.evaluator import ProductProof, ProductProofStatus
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.tests.services.visa_engine import _gold_fixtures as gf

PACKS = Path(__file__).resolve().parents[3] / "services/visa_engine/contracts/packs"

# Any instant on/after every inserted rule's valid_period.from
# (2026-08-19T00:00:00Z, normalized by fold_pack.py — FIX-3b) and inside
# every byte-inherited seq-7 rule's window (2026-07-25T00:00:00Z onward).
AT = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)


def _known(value: Any) -> dict[str, Any]:
    return {"status": "KNOWN", "value": value}


def _load(name: str) -> compiler.CompiledRulePack:
    payload = load_rule_pack_payload(PACKS / name)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


@pytest.fixture(scope="module")
def seq9() -> compiler.CompiledRulePack:
    return _load("rulepack-prod-009.source.json")


def _proof(
    compiled: compiler.CompiledRulePack, product_code: str, overrides: dict[str, Any]
) -> ProductProof:
    """Evaluate ONE product's proof directly (``evaluate_product``), never
    the aggregated multi-product ``Decision`` — see module docstring.
    """

    facts = gf.applicant_facts(overrides=overrides)
    snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=AT)
    product = next(p for p in compiled.products if p.product_code == product_code)
    rules = compiled.rules_for(product, effective_at=AT)
    purposes = frozenset(snapshot.values[FactPath.INTENT_PURPOSES].value)
    return evaluator.evaluate_product(
        product=product,
        rules=rules,
        facts=snapshot,
        purposes=purposes,
        fact_registry=DEFAULT_FACT_REGISTRY,
    )


def _reason_codes(proof: ProductProof) -> set[str]:
    return {r.code for r in proof.reasons}


# ---------------------------------------------------------------------------
# E33A / E33B / E33C — hf.*.sponsor-not-government[-or-none]
# ---------------------------------------------------------------------------


def test_e33a_government_sponsor_is_not_excluded(seq9: compiler.CompiledRulePack) -> None:
    proof = _proof(
        seq9,
        "E33A",
        {"intent.purposes": _known(["TOURISM"]), "sponsor.type": _known("GOVERNMENT")},
    )
    assert proof.status is not ProductProofStatus.EXCLUDED


def test_e33a_employer_sponsor_is_excluded(seq9: compiler.CompiledRulePack) -> None:
    proof = _proof(
        seq9,
        "E33A",
        {"intent.purposes": _known(["TOURISM"]), "sponsor.type": _known("EMPLOYER")},
    )
    assert proof.status is ProductProofStatus.EXCLUDED
    assert "E33A_SPONSOR_NOT_GOVERNMENT" in _reason_codes(proof)


@pytest.mark.parametrize("product_code", ["E33B", "E33C"])
@pytest.mark.parametrize("sponsor", ["GOVERNMENT", "NONE"])
def test_e33bc_government_or_none_sponsor_is_not_excluded(
    seq9: compiler.CompiledRulePack, product_code: str, sponsor: str
) -> None:
    proof = _proof(
        seq9,
        product_code,
        {"intent.purposes": _known(["TOURISM"]), "sponsor.type": _known(sponsor)},
    )
    assert proof.status is not ProductProofStatus.EXCLUDED


@pytest.mark.parametrize("product_code", ["E33B", "E33C"])
def test_e33bc_employer_sponsor_is_excluded(
    seq9: compiler.CompiledRulePack, product_code: str
) -> None:
    proof = _proof(
        seq9,
        product_code,
        {"intent.purposes": _known(["TOURISM"]), "sponsor.type": _known("EMPLOYER")},
    )
    assert proof.status is ProductProofStatus.EXCLUDED
    assert f"{product_code}_SPONSOR_NOT_GOVERNMENT_OR_NONE" in _reason_codes(proof)


@pytest.mark.parametrize("product_code", ["E33A", "E33B", "E33C"])
def test_unknown_sponsor_type_is_never_excluded(
    seq9: compiler.CompiledRulePack, product_code: str
) -> None:
    """An applicant who was never asked ``sponsor.type`` (the fact stays at
    its baseline UNKNOWN) must never be silently EXCLUDED — that is this
    witness's SAFETY assertion and it is unchanged.

    The proof SHAPE moved from ``BLOCKED_UNKNOWN`` to ``UNSUPPORTED`` with
    the decisiveness reorder (2026-09-06, ``evaluate_product`` now tests
    purpose-feasibility before blocking on an input-tagged gate unknown —
    see ``test_evaluator_purpose_feasibility_precedence.py``). E33A/E33B/
    E33C carry ZERO SUPPORT rules in this pack, so a TOURISM applicant can
    never be a candidate for them under ANY ``sponsor.type`` value: asking
    the question was never a step towards an answer, and the honest proof
    is "this product cannot cover TOURISM", not "tell me your sponsor".
    The rule's ``on_unknown=NEEDS_INPUT`` still asks wherever the product
    COULD be recommended — pinned in the sibling file's
    ``test_a_purpose_feasible_product_still_blocks_on_its_gate_unknown``."""
    proof = _proof(seq9, product_code, {"intent.purposes": _known(["TOURISM"])})
    assert proof.status is not ProductProofStatus.EXCLUDED
    assert not _reason_codes(proof), "no exclusion reason may be manufactured from an UNKNOWN"
    assert proof.status is ProductProofStatus.UNSUPPORTED
    assert proof.missing_purposes == frozenset({"TOURISM"})
    assert proof.missing_facts == frozenset(), "a product that cannot cover TOURISM asks nothing"


# ---------------------------------------------------------------------------
# E30F — el.e30f-student-support (pins FIX-1: the missing sponsor gate)
# ---------------------------------------------------------------------------


def test_e30f_education_sponsor_with_confirmed_admission_is_supported(
    seq9: compiler.CompiledRulePack,
) -> None:
    proof = _proof(
        seq9,
        "E30F",
        {
            "intent.purposes": _known(["STUDY"]),
            "study.admission_confirmed": _known(True),
            "study.sponsor_confirmed": _known(True),
            "sponsor.type": _known("EDUCATION"),
        },
    )
    assert proof.status is ProductProofStatus.SUPPORTED


def test_e30f_none_sponsor_is_not_supported(seq9: compiler.CompiledRulePack) -> None:
    """FIX-1 regression pin: before the cure, this exact fact pattern
    (sponsor.type=NONE, everything else identical) reached SUPPORTED —
    Codex refuter finding 1, live-evaluator-verified against seq-9 before
    the sponsor.type conjunct was added."""
    proof = _proof(
        seq9,
        "E30F",
        {
            "intent.purposes": _known(["STUDY"]),
            "study.admission_confirmed": _known(True),
            "study.sponsor_confirmed": _known(True),
            "sponsor.type": _known("NONE"),
        },
    )
    assert proof.status is not ProductProofStatus.SUPPORTED


# ---------------------------------------------------------------------------
# E30E — el.e30e-student-support (EDUCATION or INDIVIDUAL, per CL-E30E-05)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sponsor", ["EDUCATION", "INDIVIDUAL"])
def test_e30e_education_or_individual_sponsor_is_supported(
    seq9: compiler.CompiledRulePack, sponsor: str
) -> None:
    proof = _proof(
        seq9,
        "E30E",
        {
            "intent.purposes": _known(["STUDY"]),
            "study.admission_confirmed": _known(True),
            "study.sponsor_confirmed": _known(True),
            "sponsor.type": _known(sponsor),
        },
    )
    assert proof.status is ProductProofStatus.SUPPORTED


def test_e30e_none_sponsor_is_not_supported(seq9: compiler.CompiledRulePack) -> None:
    proof = _proof(
        seq9,
        "E30E",
        {
            "intent.purposes": _known(["STUDY"]),
            "study.admission_confirmed": _known(True),
            "study.sponsor_confirmed": _known(True),
            "sponsor.type": _known("NONE"),
        },
    )
    assert proof.status is not ProductProofStatus.SUPPORTED


# ---------------------------------------------------------------------------
# E33G — review.e33g.income-evidence (OD-1 narrowing over el.e33g.remote-work)
# ---------------------------------------------------------------------------


def test_e33g_clean_remote_work_configuration_fires_human_review(
    seq9: compiler.CompiledRulePack,
) -> None:
    """The SAME 4 facts that satisfy the healthy sibling
    ``el.e33g.remote-work`` (SUPPORT) must resolve to REVIEW, not
    SUPPORTED — this rule exists specifically to intercept that
    unconditional SUPPORT (spec Step 3b / Assembly decision #2)."""
    proof = _proof(
        seq9,
        "E33G",
        {
            "intent.purposes": _known(["REMOTE_WORK"]),
            "work.employer_is_indonesian_entity": _known(False),
            "work.serves_indonesian_clients": _known(False),
            "work.indonesia_source_compensation": _known(False),
        },
    )
    assert proof.status is ProductProofStatus.REVIEW
    assert "E33G_INCOME_EVIDENCE_REVIEW" in _reason_codes(proof)


# ---------------------------------------------------------------------------
# E23U / E23V — review.e23u/v.requested-product
# ---------------------------------------------------------------------------


def test_e23u_requested_product_code_fires_review_for_e23u_only(
    seq9: compiler.CompiledRulePack,
) -> None:
    overrides = {
        "intent.purposes": _known(["EMPLOYMENT"]),
        "intent.requested_product_code": _known("E23U"),
    }
    e23u_proof = _proof(seq9, "E23U", overrides)
    assert e23u_proof.status is ProductProofStatus.REVIEW
    assert "E23U_DIPLOMATIC_HOUSEHOLD_STAFF_REVIEW" in _reason_codes(e23u_proof)

    e23v_proof = _proof(seq9, "E23V", overrides)
    assert e23v_proof.status is not ProductProofStatus.REVIEW


def test_e23v_requested_product_code_fires_review_for_e23v_only(
    seq9: compiler.CompiledRulePack,
) -> None:
    overrides = {
        "intent.purposes": _known(["EMPLOYMENT"]),
        "intent.requested_product_code": _known("E23V"),
    }
    e23v_proof = _proof(seq9, "E23V", overrides)
    assert e23v_proof.status is ProductProofStatus.REVIEW
    assert "E23V_TRADE_OFFICE_STAFF_REVIEW" in _reason_codes(e23v_proof)

    e23u_proof = _proof(seq9, "E23U", overrides)
    assert e23u_proof.status is not ProductProofStatus.REVIEW


@pytest.mark.parametrize("product_code", ["E23U", "E23V"])
def test_unknown_requested_product_code_never_manufactures_a_review(
    seq9: compiler.CompiledRulePack, product_code: str
) -> None:
    """``intent.requested_product_code`` stays at its baseline UNKNOWN
    (never asked) — the rule's ``on_unknown=NEEDS_INPUT`` must never
    manufacture a REVIEW verdict. That SAFETY assertion is unchanged. This
    is the path production actually exercises today: ``fact-mapper.ts:469``
    hard-codes this fact NOT_ASKED unconditionally (Kimi refuter finding 2)
    — these two rules are production-inert until that fact is collected.

    The proof SHAPE moved from ``BLOCKED_UNKNOWN`` to ``UNSUPPORTED`` with
    the decisiveness reorder (see the E33A/B/C witness above and
    ``test_evaluator_purpose_feasibility_precedence.py``): E23U/E23V carry
    zero SUPPORT rules, so "production-inert" is now what the proof itself
    says, instead of the product asking every EMPLOYMENT applicant for a
    product code the browser can never supply."""
    proof = _proof(seq9, product_code, {"intent.purposes": _known(["EMPLOYMENT"])})
    assert proof.status is not ProductProofStatus.REVIEW
    assert not _reason_codes(proof), "no review reason may be manufactured from an UNKNOWN"
    assert proof.status is ProductProofStatus.UNSUPPORTED
    assert proof.missing_purposes == frozenset({"EMPLOYMENT"})
    assert proof.missing_facts == frozenset()
