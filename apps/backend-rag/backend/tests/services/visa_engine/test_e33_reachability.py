"""V1/E33 (2026-08-25, mandate docs/plans/2026-08-24-visa-oracle-live/
MANDATE.md, lane V1 unit 1, team-lead ruling) — E33A/E33B/E33C reachability,
against the REAL ACTIVE signed pack (``rulepack-prod-013.source.json``,
seq-13), never a hand-authored fixture pack. Sibling of
``test_e28_investor_golden_visa_reachability.py`` — SAME disease class, same
house pattern — with one addition unique to this trio: an explicit proof of
the sponsor.type GATING mechanism the design decision below rests on.

THE DISEASE (measured, not re-derived — see the corrected E33 comment in
``apps/mouth/.../_lib/fact-mapper.ts``): each of E33A/E33B/E33C carries
exactly ONE ``PRODUCTS``-scope rule (``review.e33{a,b,c}.*``, stage
``HUMAN_REVIEW``, effect ``REQUIRE_REVIEW``), keyed on
``intent.requested_product_code == "<code>"``, with ``on_unknown:
NEEDS_INPUT`` — not ``HUMAN_REVIEW``. No ELIGIBILITY/SUPPORT rule exists for
any of the three at all — this trio can NEVER auto-approve, only ever
BLOCKED_UNKNOWN (unnamed) or REVIEW (named). Before this fix, the mandate's
E28 fix left ``intent.requested_product_code`` populated ONLY by the
"invest" category's ``investment_product_code`` question — E33A/B (purposes
EMPLOYMENT, "work" category) had NO path to KNOWN at all, and E33C
(purposes INVESTMENT, "invest" category) shared E28's question but was
DELIBERATELY excluded from its option list on a since-corrected "not
groundable" premise (conflated AUTOMATABILITY with REACHABILITY — see
fact-mapper.ts's comment history). All three were therefore INVISIBLE by
the same top-level mechanism as E28B/C/D/F: a real applicant who could
otherwise reach ``SUPPORTED_CANDIDATES`` via a sibling product (E23 for
EMPLOYMENT, E28A for INVESTMENT) never saw E33A/B/C mentioned anywhere.

THE FIX (frontend-only, this follow-up's scope) is NARROWER than E28's:
``employment_product_code_govt``/``employment_product_code_none``/
``investment_product_code_govt`` (tree.ts/flow.ts) are inserted into the
interview ONLY when ``sponsor_category`` matches the exact value(s) each
product's own INDEPENDENT ``sponsor.type`` HARD_FILTER requires —
GOVERNMENT-only for E33A (``hf.e33a.sponsor-not-government``),
GOVERNMENT-or-NONE for E33B/E33C (``hf.e33{b,c}.sponsor-not-government-or-
none``) — never the whole EMPLOYMENT/INVESTMENT purpose slice. This module
proves TWO claims: (1) the E28-style reachability claim (naming a code
fires REVIEW, citing that product), and (2) the mechanism the narrower gate
was designed around — that a HARD_FILTER-excluded product proof never
escalates to a top-level ``HUMAN_REVIEW_REQUIRED`` (``evaluator.py``'s
``evaluate_product``: a HARD_FILTER TRUE returns ``EXCLUDED`` immediately,
before the REVIEW stage is ever consulted; ``evaluate()``'s aggregation only
promotes ``ProductProofStatus.REVIEW`` proofs to
``DecisionState.HUMAN_REVIEW_REQUIRED``, never ``EXCLUDED`` ones, which sink
to the lowest-precedence ``NO_SUPPORTED_PATH`` bucket instead) — so even a
hypothetically over-broad gate could not have suppressed a genuine
``SUPPORTED_CANDIDATES`` outcome the way a REVIEW-stage rule would. The
narrower per-product gate is still correct UX (never offer a choice a
sponsor type structurally cannot pass) and is what team-lead's ruling
ordered; this module documents that the stricter design was a deliberate
choice, not the only thing standing between production and a suppressed
outcome.

Guilt+innocence pattern per product (house style, shared with the E28
sibling module): naming a code with a MATCHING sponsor type fires REVIEW for
THAT product only; naming a code with a MISMATCHED sponsor type is EXCLUDED,
never REVIEW; the UNKNOWN baseline (unnamed) is BLOCKED_UNKNOWN, never a
manufactured REVIEW and never SUPPORTED.
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
from backend.services.visa_engine.enums import DecisionState, FactPath
from backend.services.visa_engine.evaluator import (
    ProductProof,
    ProductProofStatus,
    build_decision_identity,
)
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.tests.services.visa_engine import _gold_fixtures as gf

_PACKS_DIR = (
    Path(__file__).resolve().parents[3] / "services" / "visa_engine" / "contracts" / "packs"
)
_ACTIVE_PACK_NAME = "rulepack-prod-013.source.json"

# Same instant already used by test_e28_investor_golden_visa_reachability.py
# and test_seq13_rules_pack.py — on/after every relevant rule's
# valid_period.from, inside every other inherited rule's window.
AT = datetime(2026, 8, 23, 12, 0, 0, tzinfo=timezone.utc)

_PURPOSE = {"E33A": "EMPLOYMENT", "E33B": "EMPLOYMENT", "E33C": "INVESTMENT"}

# The sponsor.type value(s) each product's OWN independent HARD_FILTER
# accepts (read live off the signed active pack, pinned as witnesses — see
# module docstring). This is the exact set flow.ts's sponsor_category gate
# now mirrors.
_VALID_SPONSOR_TYPES: dict[str, tuple[str, ...]] = {
    "E33A": ("GOVERNMENT",),
    "E33B": ("GOVERNMENT", "NONE"),
    "E33C": ("GOVERNMENT", "NONE"),
}

# review.e33{a,b,c}.*'s reason_code, read live off the signed active pack.
# NOTE: E33A and E33C's review rules share the IDENTICAL reason_code
# GOVT_INVITATION_REQUIRED (verified, not a typo) — the two rules are
# text-identical apart from their `purposes`/`requested_product_code`
# operands, so a proof-level check must distinguish them by PRODUCT
# (evaluate_product is already per-product) rather than by reason_code
# alone.
_REVIEW_REASON_CODES = {
    "E33A": "GOVT_INVITATION_REQUIRED",
    "E33B": "E33B_EXPERTISE_QUALIFICATION_CHECK",
    "E33C": "GOVT_INVITATION_REQUIRED",
}

# hf.e33{a,b,c}.sponsor-not-government[-or-none]'s reason_code.
_HARD_FILTER_REASON_CODES = {
    "E33A": "E33A_SPONSOR_NOT_GOVERNMENT",
    "E33B": "E33B_SPONSOR_NOT_GOVERNMENT_OR_NONE",
    "E33C": "E33C_SPONSOR_NOT_GOVERNMENT_OR_NONE",
}

# A plausible ordinary work-KITAS applicant (el.e23-employment-support's own
# SUPPORT condition) — the EMPLOYMENT-purpose sibling of E28's plausible
# investor. This is the person the disease hides E33A/E33B from: without
# this fix, THIS SAME PERSON reaches SUPPORTED_CANDIDATES via E23 alone and
# never sees E33A/E33B even exist.
_PLAUSIBLE_EMPLOYMENT_OVERRIDES: dict[str, Any] = {
    "intent.purposes": {"status": "KNOWN", "value": ["EMPLOYMENT"]},
    "work.employer_is_indonesian_entity": {"status": "KNOWN", "value": True},
    "work.indonesian_work_sponsor_confirmed": {"status": "KNOWN", "value": True},
}

# The INVESTMENT-purpose sibling, identical to
# test_e28_investor_golden_visa_reachability.py's own
# _PLAUSIBLE_INVESTOR_OVERRIDES (duplicated rather than imported — house
# convention, each test module is self-contained) — the person E33C's
# disease hides behind a plausible E28A SUPPORTED outcome.
_PLAUSIBLE_INVESTOR_OVERRIDES: dict[str, Any] = {
    "intent.purposes": {"status": "KNOWN", "value": ["INVESTMENT"]},
    "investment.pt_pma_committed": {"status": "KNOWN", "value": True},
    "investment.proposed_role": {"status": "KNOWN", "value": "SHAREHOLDER_DIRECTOR"},
    "investment.paid_up_capital_idr": {"status": "KNOWN", "value": 3_000_000_000},
    "investment.investment_capital_idr": {"status": "KNOWN", "value": 12_000_000_000},
}


def _known(value: Any) -> dict[str, Any]:
    return {"status": "KNOWN", "value": value}


def _plausible_overrides(product_code: str) -> dict[str, Any]:
    return dict(
        _PLAUSIBLE_EMPLOYMENT_OVERRIDES
        if _PURPOSE[product_code] == "EMPLOYMENT"
        else _PLAUSIBLE_INVESTOR_OVERRIDES
    )


def _identity(facts, rule_pack_ref, effective_at, _environment):
    """Test-safe, non-secret identity provider — house pattern, same as
    ``test_e28_investor_golden_visa_reachability.py``. Required because
    ``rulepack-prod-013.source.json``'s ``environment`` is ``PRODUCTION``:
    ``evaluate()``'s default ``_placeholder_identity_provider`` fail-closes
    for any non-``TEST``-environment pack.
    """
    return build_decision_identity(
        facts,
        rule_pack_ref,
        effective_at,
        fingerprint_key=b"e33-v1-witness-non-secret-test-key",
        fingerprint_key_id="e33-v1-witness-test",
    )


@pytest.fixture(scope="module")
def active_pack() -> compiler.CompiledRulePack:
    payload = load_rule_pack_payload(_PACKS_DIR / _ACTIVE_PACK_NAME)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


def _proof(
    compiled: compiler.CompiledRulePack, product_code: str, overrides: dict[str, Any]
) -> ProductProof:
    """Evaluate ONE product's proof directly (``evaluate_product``), never
    the aggregated multi-product ``Decision`` — house pattern, same as the
    E28 sibling module.
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
# Per-product proof: guilt (named + matching sponsor -> REVIEW, cited, this
# product only) + the sponsor-mismatch mechanism proof (named + WRONG
# sponsor -> EXCLUDED, never REVIEW) + innocence (unnamed -> BLOCKED_UNKNOWN).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "product_code,sponsor_type",
    [
        ("E33A", "GOVERNMENT"),
        ("E33B", "GOVERNMENT"),
        ("E33B", "NONE"),
        ("E33C", "GOVERNMENT"),
        ("E33C", "NONE"),
    ],
)
def test_named_product_code_with_matching_sponsor_fires_review_for_that_product_only(
    active_pack: compiler.CompiledRulePack, product_code: str, sponsor_type: str
) -> None:
    overrides = {
        "intent.purposes": _known([_PURPOSE[product_code]]),
        "intent.requested_product_code": _known(product_code),
        "sponsor.type": _known(sponsor_type),
    }
    named_proof = _proof(active_pack, product_code, overrides)
    assert named_proof.status is ProductProofStatus.REVIEW
    assert _REVIEW_REASON_CODES[product_code] in _reason_codes(named_proof)

    for sibling in ("E33A", "E33B", "E33C"):
        if sibling == product_code:
            continue
        sibling_proof = _proof(active_pack, sibling, overrides)
        assert sibling_proof.status is not ProductProofStatus.REVIEW, (
            f"naming {product_code} must never fire {sibling}'s review rule"
        )


@pytest.mark.parametrize(
    "product_code,wrong_sponsor_type",
    [
        ("E33A", "NONE"),
        ("E33A", "INDIVIDUAL"),
        ("E33B", "INDIVIDUAL"),
        ("E33C", "EMPLOYER"),
    ],
)
def test_named_product_code_with_mismatched_sponsor_is_excluded_never_review(
    active_pack: compiler.CompiledRulePack, product_code: str, wrong_sponsor_type: str
) -> None:
    """THE mechanism this follow-up's sponsor.type gating design decision
    rests on: naming a product whose ``sponsor.type`` HARD_FILTER the
    applicant cannot pass never reaches REVIEW at all —
    ``evaluate_product``'s HARD_FILTER-TRUE branch returns ``EXCLUDED``
    immediately, before the HUMAN_REVIEW stage is even consulted (see module
    docstring). This is what makes the narrower per-sponsor-type gate a
    UX/precision choice rather than the only thing standing between
    production and a suppressed outcome — see the aggregate-level sibling
    test below for the top-level consequence.
    """
    assert wrong_sponsor_type not in _VALID_SPONSOR_TYPES[product_code]
    overrides = {
        "intent.purposes": _known([_PURPOSE[product_code]]),
        "intent.requested_product_code": _known(product_code),
        "sponsor.type": _known(wrong_sponsor_type),
    }
    proof = _proof(active_pack, product_code, overrides)
    assert proof.status is ProductProofStatus.EXCLUDED
    assert proof.status is not ProductProofStatus.REVIEW
    assert _HARD_FILTER_REASON_CODES[product_code] in _reason_codes(proof)


@pytest.mark.parametrize("product_code", ["E33A", "E33B", "E33C"])
def test_unknown_requested_product_code_is_blocked_unknown_never_review(
    active_pack: compiler.CompiledRulePack, product_code: str
) -> None:
    """The baseline this follow-up's fix moves applicants OFF: an applicant
    for whom ``intent.requested_product_code`` was never populated leaves
    the rule's own condition UNKNOWN. ``on_unknown: NEEDS_INPUT`` means this
    must resolve to BLOCKED_UNKNOWN, never a manufactured REVIEW and never
    SUPPORTED — even with a VALID sponsor.type, so this isolates the
    fact-not-asked case from the sponsor-mismatch case tested above.
    """
    overrides = {
        "intent.purposes": _known([_PURPOSE[product_code]]),
        "sponsor.type": _known(_VALID_SPONSOR_TYPES[product_code][0]),
    }
    proof = _proof(active_pack, product_code, overrides)
    assert proof.status is ProductProofStatus.BLOCKED_UNKNOWN
    assert proof.status is not ProductProofStatus.REVIEW


# ---------------------------------------------------------------------------
# Aggregate Decision-level: the actual acceptance claim, plus the
# sponsor-mismatch-at-aggregate-level proof unique to this trio.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("product_code", ["E33A", "E33B", "E33C"])
def test_before_the_fix_a_plausible_applicant_who_names_the_code_was_invisible(
    active_pack: compiler.CompiledRulePack, product_code: str
) -> None:
    """Negative control, pinning the exact disease: the SAME plausible
    applicant as the guilt test below (E23-eligible for EMPLOYMENT purpose,
    E28A-eligible for INVESTMENT purpose), a VALID sponsor.type for this
    product, but ``intent.requested_product_code`` left at its unconditional
    NOT_ASKED baseline (what every real applicant got before this
    follow-up's fix, and what any applicant with an invalid sponsor.type
    still gets today, structurally, since the question is never shown to
    them). The sibling SUPPORT product carries the decision to
    SUPPORTED_CANDIDATES; this product never appears anywhere.
    """
    overrides = {
        **_plausible_overrides(product_code),
        "sponsor.type": _known(_VALID_SPONSOR_TYPES[product_code][0]),
    }
    facts = gf.applicant_facts(overrides=overrides)
    decision = evaluator.evaluate(
        facts, active_pack, effective_at=AT, observed_at=AT, identity_provider=_identity
    )

    assert decision.state is DecisionState.SUPPORTED_CANDIDATES
    codes = {c.product_code for c in decision.candidates}
    assert ("E23" in codes) or ("E28A" in codes)
    assert product_code not in codes
    assert not any(product_code in r.code for r in decision.review_reasons)
    assert not any(product_code in r.code for r in decision.no_path_reasons)


@pytest.mark.parametrize("product_code", ["E33A", "E33B", "E33C"])
def test_after_the_fix_a_plausible_applicant_who_names_the_code_reaches_it(
    active_pack: compiler.CompiledRulePack, product_code: str
) -> None:
    """The acceptance claim itself: the exact same plausible-applicant facts
    as the negative control above, PLUS the one fact this follow-up's
    interview questions now make askable — ``intent.requested_product_code``
    KNOWN, naming the product, with a VALID matching ``sponsor.type``.
    ``HUMAN_REVIEW_REQUIRED`` beats ``SUPPORTED_CANDIDATES`` in the frozen
    precedence, so the decision flips from "quietly SUPPORTED via the
    sibling product, this product never mentioned" to
    "HUMAN_REVIEW_REQUIRED, citing this product by name" — which IS this
    trio's designed T3 disposition (routed to a human, not silently hidden).
    """
    overrides = {
        **_plausible_overrides(product_code),
        "sponsor.type": _known(_VALID_SPONSOR_TYPES[product_code][0]),
        "intent.requested_product_code": _known(product_code),
    }
    facts = gf.applicant_facts(overrides=overrides)
    decision = evaluator.evaluate(
        facts, active_pack, effective_at=AT, observed_at=AT, identity_provider=_identity
    )

    assert decision.state is DecisionState.HUMAN_REVIEW_REQUIRED
    assert _REVIEW_REASON_CODES[product_code] in {r.code for r in decision.review_reasons}
    for reason in decision.review_reasons:
        if reason.code == _REVIEW_REASON_CODES[product_code] and reason.source_refs:
            break
    else:
        pytest.fail(f"{product_code}'s review reason must carry a citation")


@pytest.mark.parametrize(
    "product_code,wrong_sponsor_type",
    [("E33A", "NONE"), ("E33B", "INDIVIDUAL"), ("E33C", "EMPLOYER")],
)
def test_naming_the_code_with_wrong_sponsor_never_forces_human_review_at_aggregate_level(
    active_pack: compiler.CompiledRulePack, product_code: str, wrong_sponsor_type: str
) -> None:
    """THE empirical proof behind team-lead's sponsor.type-gating ruling's
    stated worry ("every extra person shown the option is a person who
    could name it and get routed to HUMAN_REVIEW_REQUIRED, suppressing a
    correct outcome") does NOT actually materialize at the AGGREGATE level
    for a HARD_FILTER-excluded product, even in this adversarial case where
    the applicant is given the sponsor.type this exact product's own gate
    was designed to prevent them from seeing: naming ``product_code`` while
    holding a ``sponsor.type`` that fails ITS OWN HARD_FILTER still leaves
    the plausible sibling SUPPORT product's outcome intact —
    ``SUPPORTED_CANDIDATES``, never demoted to ``HUMAN_REVIEW_REQUIRED`` by
    the excluded product. This does not make the sponsor.type gate
    pointless — production never actually offers this combination to a real
    applicant, and the gate is still correct, precise UX per team-lead's
    ruling — it documents that the gate is a precision choice on top of an
    already-safe mechanism, not the only thing standing between production
    and a suppressed outcome.
    """
    assert wrong_sponsor_type not in _VALID_SPONSOR_TYPES[product_code]
    overrides = {
        **_plausible_overrides(product_code),
        "sponsor.type": _known(wrong_sponsor_type),
        "intent.requested_product_code": _known(product_code),
    }
    facts = gf.applicant_facts(overrides=overrides)
    decision = evaluator.evaluate(
        facts, active_pack, effective_at=AT, observed_at=AT, identity_provider=_identity
    )

    assert decision.state is DecisionState.SUPPORTED_CANDIDATES
    assert not any(product_code in r.code for r in decision.review_reasons)
