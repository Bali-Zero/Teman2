"""V1/E28 (2026-08-24, mandate docs/plans/2026-08-24-visa-oracle-live/
MANDATE.md, lane V1 unit 1) — E28B/C/D/F reachability, against the REAL
ACTIVE signed pack (``rulepack-prod-013.source.json``, seq-13), never a
hand-authored fixture pack.

THE DISEASE (measured, not re-derived — see the mandate + LIVE STATE
2026-08-24 entry in ``.claude/skills/visaoracle/SKILL.md``): each of
E28B/E28C/E28D/E28F carries exactly ONE ``PRODUCTS``-scope rule
(``review.e28{b,c,d,f}.*-manual``, stage ``HUMAN_REVIEW``, effect
``REQUIRE_REVIEW``), keyed on ``intent.requested_product_code ==
"<code>"``, with ``on_unknown: NEEDS_INPUT`` — not ``HUMAN_REVIEW``. No
ELIGIBILITY/SUPPORT rule exists for any of the four at all.
``evaluator._partition_unknowns_by_policy`` routes an UNKNOWN fact by the
rule's OWN ``on_unknown``: only ``HUMAN_REVIEW`` escalates to a review
reason; ``NEEDS_INPUT`` makes the product's own proof ``BLOCKED_UNKNOWN``.
Before this mandate's fix, ``apps/mouth/.../_lib/fact-mapper.ts`` hard-coded
``"intent.requested_product_code": unknownFact(NOT_ASKED)`` UNCONDITIONALLY
— the interview had no question that could ever populate it — so these four
products were BLOCKED_UNKNOWN for every real applicant, always. Per
``evaluate()``'s frozen precedence (module docstring,
``evaluator.evaluate_with_trace``), a real investor with good E28A facts
reaches ``SUPPORTED_CANDIDATES`` regardless, which always beats a
per-product ``BLOCKED_UNKNOWN`` at the top-level ``Decision`` — so the four
products were not merely unreachable, they were INVISIBLE: absent from
candidates, review reasons, missing_facts, everything.

THE FIX (frontend-only, this mandate's scope): ``apps/mouth`` ships a new
``investment_product_code`` interview question (tree.ts/flow.ts), asked for
every "invest" category applicant right after ``investment_vehicle``
(unconditional across every vehicle sub-branch — E28C is a pure
capital-market portfolio investor, no PT PMA, so gating this on
``investment_vehicle === "pt_pma"`` would leave E28C unreachable through
this question). ``fact-mapper.ts`` now maps a named answer to a real KNOWN
``intent.requested_product_code`` via ``enumFact``. This module proves the
BACKEND side of that claim: the rule pack ALREADY handles a KNOWN value
correctly (per-product REVIEW, never masking a sibling) and the
BLOCKED_UNKNOWN-when-unnamed mechanism is exactly as diagnosed — nothing
here changes the pack. What changes is which fact value production can now
actually supply, which is proven at the TS layer by
``fact-mapper.test.ts``'s "V1/E28" describe block and
``flow.test.ts``'s "investment_product_code is askable" describe block
(the real path a user walks — acceptance item 1).

Guilt+innocence pattern per product (house style,
``test_seq9_new_rule_witnesses.py``'s E23U/E23V section — SAME disease
class, this module is its E28 sibling against the CURRENT active pack
rather than the historical seq-9 one): naming a code fires REVIEW for THAT
product only, never a sibling; the UNKNOWN baseline (what production served
before this mandate, and what it still serves for any applicant who
explicitly declines to name a product) is BLOCKED_UNKNOWN, never a
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

# Any instant on/after every E28B/C/D/F rule's valid_period.from
# (2026-07-24T00:00:00Z) and inside every other inherited rule's window —
# same value already used by this same pack's own gate suite
# (test_seq13_rules_pack.py).
AT = datetime(2026, 8, 23, 12, 0, 0, tzinfo=timezone.utc)

# The 4 (product_code -> reason_code) pairs, read live off the signed
# active pack in the investigation for this mandate — pinned here as
# witnesses, not re-derived, so a future pack edit that silently renames a
# reason_code is caught by this suite rather than by a client-facing report.
_PRODUCT_REASON_CODES = {
    "E28B": "E28B_USD_THRESHOLD_MANUAL_CHECK",
    "E28C": "E28C_USD_THRESHOLD_AND_INSTRUMENT_CHECK",
    "E28D": "E28D_USD_THRESHOLD_AND_TURNOVER_CHECK",
    "E28F": "E28F_IKN_THRESHOLD_MANUAL_CHECK",
}

# A plausible Golden Visa investor by E28A's own SUPPORT rule
# (el.e28a.investment) — every fact that rule requires, comfortably above
# threshold. This is the applicant the mandate's disease actually hides
# E28B/C/D/F from: without this fix, THIS SAME PERSON reaches
# SUPPORTED_CANDIDATES via E28A alone and never sees E28B/C/D/F even exist.
_PLAUSIBLE_INVESTOR_OVERRIDES: dict[str, Any] = {
    "intent.purposes": {"status": "KNOWN", "value": ["INVESTMENT"]},
    "investment.pt_pma_committed": {"status": "KNOWN", "value": True},
    "investment.proposed_role": {"status": "KNOWN", "value": "SHAREHOLDER_DIRECTOR"},
    "investment.paid_up_capital_idr": {"status": "KNOWN", "value": 3_000_000_000},
    "investment.investment_capital_idr": {"status": "KNOWN", "value": 12_000_000_000},
}


def _known(value: Any) -> dict[str, Any]:
    return {"status": "KNOWN", "value": value}


def _identity(facts, rule_pack_ref, effective_at, _environment):
    """Test-safe, non-secret identity provider — house pattern (``test_seq6_
    refuter_witnesses.py``/``test_seq9_new_rule_witnesses.py``). Required
    because ``rulepack-prod-013.source.json``'s ``environment`` is
    ``PRODUCTION``: ``evaluate()``'s default ``_placeholder_identity_
    provider`` fail-closes (raises ``PlaceholderIdentityNotAllowedError``)
    for any non-``TEST``-environment pack, so an aggregate-level test against
    the real active pack must inject its own deterministic, non-secret HMAC
    key rather than rely on the default.
    """
    return build_decision_identity(
        facts,
        rule_pack_ref,
        effective_at,
        fingerprint_key=b"e28-v1-witness-non-secret-test-key",
        fingerprint_key_id="e28-v1-witness-test",
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
    the aggregated multi-product ``Decision`` — a REVIEW-gated sibling
    product elsewhere in the pack could otherwise mask a defect on the
    product actually under test (house pattern, ``test_seq7_sponsor_
    witnesses.py`` / ``test_seq9_new_rule_witnesses.py``).
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
# Per-product proof: guilt (named -> REVIEW, cited, this product only) +
# innocence (siblings unaffected).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("product_code", ["E28B", "E28C", "E28D", "E28F"])
def test_named_product_code_fires_review_for_that_product_only(
    active_pack: compiler.CompiledRulePack, product_code: str
) -> None:
    overrides = {
        "intent.purposes": _known(["INVESTMENT"]),
        "intent.requested_product_code": _known(product_code),
    }
    named_proof = _proof(active_pack, product_code, overrides)
    assert named_proof.status is ProductProofStatus.REVIEW
    assert _PRODUCT_REASON_CODES[product_code] in _reason_codes(named_proof)

    for sibling in ("E28B", "E28C", "E28D", "E28F"):
        if sibling == product_code:
            continue
        sibling_proof = _proof(active_pack, sibling, overrides)
        assert sibling_proof.status is not ProductProofStatus.REVIEW, (
            f"naming {product_code} must never fire {sibling}'s review rule"
        )


@pytest.mark.parametrize("product_code", ["E28B", "E28C", "E28D", "E28F"])
def test_unknown_requested_product_code_is_blocked_unknown_never_review(
    active_pack: compiler.CompiledRulePack, product_code: str
) -> None:
    """The baseline this mandate's fix moves applicants OFF: an applicant
    for whom ``intent.requested_product_code`` was never populated (exactly
    what fact-mapper.ts's old unconditional ``unknownFact(NOT_ASKED)``
    produced for every real request) leaves the rule's own condition
    UNKNOWN. ``on_unknown: NEEDS_INPUT`` (not ``HUMAN_REVIEW``) means this
    must resolve to BLOCKED_UNKNOWN, never a manufactured REVIEW and never
    SUPPORTED — pinning that the pack's mechanism is unchanged by this
    mandate; only whether production can ever supply the KNOWN branch is.
    """
    proof = _proof(active_pack, product_code, {"intent.purposes": _known(["INVESTMENT"])})
    assert proof.status is ProductProofStatus.BLOCKED_UNKNOWN
    assert proof.status is not ProductProofStatus.REVIEW


# ---------------------------------------------------------------------------
# Aggregate Decision-level: the actual acceptance claim — "a synthetic
# applicant who is a plausible investor and names one of them reaches it"
# (mandate acceptance item 2). Proven against evaluator.evaluate(), the
# same aggregation a live /visa-oracle/evaluate call drives, using the
# REAL active pack — never evaluate_product alone, since the mandate's
# disease is specifically about top-level VISIBILITY, not just per-product
# proof correctness.
# ---------------------------------------------------------------------------


def test_before_the_fix_a_plausible_investor_who_names_e28b_was_invisible(
    active_pack: compiler.CompiledRulePack,
) -> None:
    """Negative control, pinning the exact disease: the SAME plausible
    investor as the guilt test below, but with
    ``intent.requested_product_code`` at its old, unconditional NOT_ASKED
    baseline (what every real applicant got before this mandate's fix).
    E28A alone carries the decision to SUPPORTED_CANDIDATES; E28B never
    appears anywhere in the Decision — this is "invisible", not merely
    "not chosen".
    """
    facts = gf.applicant_facts(overrides=_PLAUSIBLE_INVESTOR_OVERRIDES)
    decision = evaluator.evaluate(
        facts, active_pack, effective_at=AT, observed_at=AT, identity_provider=_identity
    )

    assert decision.state is DecisionState.SUPPORTED_CANDIDATES
    codes = {c.product_code for c in decision.candidates}
    assert "E28A" in codes
    assert "E28B" not in codes
    assert not any("E28B" in r.code for r in decision.review_reasons)
    assert not any("E28B" in r.code for r in decision.no_path_reasons)


@pytest.mark.parametrize("product_code", ["E28B", "E28C", "E28D", "E28F"])
def test_after_the_fix_a_plausible_investor_who_names_the_code_reaches_it(
    active_pack: compiler.CompiledRulePack, product_code: str
) -> None:
    """The acceptance claim itself: the exact same plausible-investor facts
    as the negative control above, PLUS the one fact this mandate's
    interview question now makes askable — ``intent.requested_product_code``
    KNOWN, naming the product. ``HUMAN_REVIEW_REQUIRED`` beats
    ``SUPPORTED_CANDIDATES`` in the frozen precedence
    (``evaluate_with_trace``'s own docstring), so the applicant's overall
    decision flips from "quietly SUPPORTED via E28A, E28B never mentioned"
    to "HUMAN_REVIEW_REQUIRED, citing E28B by name" — which IS the doctrine
    card's designed disposition for these four Golden Visa tiers (§7,
    `research/visa/doctrine-factory/cards/E28B.md`: the always-REVIEW rule
    is a deliberate high-value/high-fraud-risk manual-verification gate,
    not a defect to route around).
    """
    facts = gf.applicant_facts(
        overrides={
            **_PLAUSIBLE_INVESTOR_OVERRIDES,
            "intent.requested_product_code": _known(product_code),
        }
    )
    decision = evaluator.evaluate(
        facts, active_pack, effective_at=AT, observed_at=AT, identity_provider=_identity
    )

    assert decision.state is DecisionState.HUMAN_REVIEW_REQUIRED
    assert _PRODUCT_REASON_CODES[product_code] in {r.code for r in decision.review_reasons}
    for reason in decision.review_reasons:
        if reason.code == _PRODUCT_REASON_CODES[product_code]:
            assert reason.source_refs, f"{product_code}'s review reason must carry a citation"
