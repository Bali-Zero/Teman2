"""Gold-harness proof adapter: a thin, Decision-agnostic per-product / global
tri-state evaluator built ONLY on top of what is merged to main today.

Why this exists (context for the reviewer): as of this harness's authoring
date, ``backend.services.visa_engine`` ships the condition-level evaluator
(``ast.evaluate_condition``), the compiler (``compiler.compile_rule_pack`` /
``compiler.build_compiled_pack``), and the fact-resolution step
(``fact_registry.FactRegistry.derive``) -- but the PER-PRODUCT / GLOBAL
evaluator (spec's ``evaluator.py``: ``ProductProofStatus``, ``ProductProof``,
``DecisionDraft``, ``evaluate()``) is explicitly deferred (see
``backend/services/visa_engine/__init__.py``'s PR-scope map: "evaluator.py,
trace.py -- not started"). A separate PR ("PR5 -- Decision evaluator (pure
tri-state orchestrator)") is open, NOT merged, at time of writing.

This module is a self-contained, minimal implementation of the algorithm
documented in ``research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
concretization.md`` Sec 4.2 (``evaluate_product``) / Sec 4.3 (``evaluate``),
built EXCLUSIVELY on real, merged primitives:

- ``ast.evaluate_condition`` for every condition truth value (never
  reimplemented -- this module never inspects a ``Condition`` tree directly).
- ``compiler.build_compiled_pack`` / ``CompiledRulePack.rules_for`` for stage
  ordering and bitemporal/scope selection (never reimplemented).
- ``fact_registry.FactRegistry.derive`` for the wire-to-runtime fact
  translation (never reimplemented).

It exists ONLY in the test tree (not ``backend/services/visa_engine/``) by
design: it is not a runtime module, it is the replay harness's own proof
layer, deliberately kept DECISION-AGNOSTIC (it returns plain dataclasses,
never ``backend.services.visa_engine.models.Decision``) so that once PR5
lands, the persona replay tests in this package can be repointed at the real
``evaluate()`` by swapping this module's two entry points
(``evaluate_product`` / ``evaluate_all``) for thin calls into PR5's API --
the 20 persona fixtures and their expectations do not change.

Deliberate simplifications documented up front (so a reviewer does not read
them as bugs):

1. ``missing_facts`` on a ``ProductProof``/``GlobalDecision`` is the raw
   ``ConditionResult.unknown_facts`` set, NOT translated from a
   ``derived.*`` fact back to its applicant-collected dependency (spec's
   ``underlying_applicant_facts`` helper). None of this harness's 20 gold
   personas ever produces an UNKNOWN ``derived.*`` fact as the safety-critical
   culprit (every persona supplies a definite ``person.birth_date``, so
   ``derived.is_minor``/``derived.age_years`` always resolve to a known
   value) -- adding the translation table here would be untested code.
2. Ranking (Sec 4.4) is implemented (RANKING-stage rules run only for
   proofs that are already SUPPORTED, unknown/false ranking facts add zero
   points, stable sort by ``(-score, product_code, product_version_id)``)
   but this harness does not assert exact scores for every persona -- only
   proof state + reason codes are the gate's contract; score is exposed on
   ``ProductProof`` for personas that want to assert it.
3. Global HUMAN_REVIEW/NEEDS_INPUT reason/missing-fact aggregation unions
   across every product in that bucket, deduplicated and sorted for
   determinism -- there is no dedicated "global-only" rule stage in this
   pack (every review/hard-filter trigger in the designed pack is GLOBAL
   scope except the E33E-scoped ``hr-e33e-age-band-55-59`` BERSYARAT band
   rule, which for the current personas never fires TRUE, so the union is
   always a singleton set in this harness's personas, but the aggregation
   code does not assume that).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from backend.services.visa_engine.ast import (
    FactSnapshot,
    KnownFact,
    evaluate_condition,
)
from backend.services.visa_engine.compiler import CompiledProduct, CompiledRule, CompiledRulePack
from backend.services.visa_engine.enums import FactPath, OnUnknownAction, RuleStage, TruthValue


class ProofState(str, Enum):
    """Per-product tri-state-plus-safety proof outcome (spec Sec 4.2).

    Five states, never a sixth: ``SUPPORTED`` (every declared purpose is
    covered by a TRUE SUPPORT rule), ``EXCLUDED`` (a HARD_FILTER rule fired
    TRUE), ``REVIEW`` (a HUMAN_REVIEW rule fired TRUE), ``BLOCKED_UNKNOWN``
    (a safety-critical HARD_FILTER/HUMAN_REVIEW rule -- or the only ELIGIBLE
    path for a still-missing purpose -- is UNKNOWN rather than decided),
    ``UNSUPPORTED`` (every stage resolved definitely and no path covers the
    declared purposes).
    """

    SUPPORTED = "SUPPORTED"
    EXCLUDED = "EXCLUDED"
    REVIEW = "REVIEW"
    BLOCKED_UNKNOWN = "BLOCKED_UNKNOWN"
    UNSUPPORTED = "UNSUPPORTED"


class GlobalState(str, Enum):
    """Global decision precedence (spec Sec 4.3), minus TEMPORARILY_UNAVAILABLE
    (an outage-only state this pure, in-memory harness never produces --
    there is no pricing/persistence dependency to fail)."""

    SUPPORTED_CANDIDATES = "SUPPORTED_CANDIDATES"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    NEEDS_INPUT = "NEEDS_INPUT"
    NO_SUPPORTED_PATH = "NO_SUPPORTED_PATH"


@dataclass(frozen=True, slots=True)
class _RuleEvalResult:
    rule: CompiledRule
    truth: TruthValue
    unknown_facts: frozenset[FactPath]


@dataclass(frozen=True, slots=True)
class ProductProof:
    product_code: str
    state: ProofState
    reason_codes: tuple[str, ...] = ()
    covered_purposes: frozenset[str] = field(default_factory=frozenset)
    missing_purposes: frozenset[str] = field(default_factory=frozenset)
    missing_facts: frozenset[FactPath] = field(default_factory=frozenset)
    score: int = 0


@dataclass(frozen=True, slots=True)
class GlobalDecision:
    state: GlobalState
    reason_codes: tuple[str, ...] = ()
    missing_facts: frozenset[FactPath] = field(default_factory=frozenset)
    #: Product codes in ranked order, populated only for SUPPORTED_CANDIDATES.
    supported_product_codes: tuple[str, ...] = ()


def _evaluate_stage(
    rules: tuple[CompiledRule, ...], stage: RuleStage, facts: FactSnapshot
) -> list[_RuleEvalResult]:
    results: list[_RuleEvalResult] = []
    for rule in rules:
        if rule.stage is not stage:
            continue
        outcome = evaluate_condition(rule.when, facts)
        results.append(
            _RuleEvalResult(rule=rule, truth=outcome.truth, unknown_facts=outcome.unknown_facts)
        )
    return results


def _safety_unknowns(results: list[_RuleEvalResult]) -> list[_RuleEvalResult]:
    """Spec's ``safety_unknowns()`` helper -- gates on ``truth is UNKNOWN``,
    NEVER on ``bool(unknown_facts)`` (``ast.ConditionResult``'s own
    "ABSTENTION CONTRACT" docstring warns exactly against that mistake: a
    ``PresenceCondition`` can carry a fact in ``unknown_facts`` while still
    resolving to a DEFINITE truth value).
    """
    return [r for r in results if r.truth is TruthValue.UNKNOWN and r.rule.safety_critical]


def _underlying_facts(results: list[_RuleEvalResult]) -> frozenset[FactPath]:
    out: set[FactPath] = set()
    for r in results:
        out |= r.unknown_facts
    return frozenset(out)


def _reason_codes(results: list[_RuleEvalResult]) -> tuple[str, ...]:
    return tuple(sorted({r.rule.effect.reason_code for r in results}))  # type: ignore[attr-defined]


def evaluate_product(
    product: CompiledProduct,
    rules: tuple[CompiledRule, ...],
    facts: FactSnapshot,
) -> ProductProof:
    """One product's proof, per spec Sec 4.2's ``evaluate_product`` pseudocode.

    ``rules`` is expected to already be the output of
    ``CompiledRulePack.rules_for(product, effective_at=...)`` -- GLOBAL +
    matching PRODUCTS-scope rules, in-force at the evaluation instant,
    stage-ordered. This function never re-derives selection/ordering itself.
    """

    hard_results = _evaluate_stage(rules, RuleStage.HARD_FILTER, facts)
    true_hard = [r for r in hard_results if r.truth is TruthValue.TRUE]
    if true_hard:
        return ProductProof(
            product.product_code, ProofState.EXCLUDED, reason_codes=_reason_codes(true_hard)
        )

    hard_unknowns = _safety_unknowns(hard_results)

    review_results = _evaluate_stage(rules, RuleStage.HUMAN_REVIEW, facts)
    true_review = [r for r in review_results if r.truth is TruthValue.TRUE]
    if true_review:
        return ProductProof(
            product.product_code, ProofState.REVIEW, reason_codes=_reason_codes(true_review)
        )

    review_unknowns = _safety_unknowns(review_results)

    if hard_unknowns or review_unknowns:
        missing = _underlying_facts(hard_unknowns) | _underlying_facts(review_unknowns)
        return ProductProof(product.product_code, ProofState.BLOCKED_UNKNOWN, missing_facts=missing)

    purposes_fact = facts.values.get(FactPath.INTENT_PURPOSES)
    if not isinstance(purposes_fact, KnownFact):
        return ProductProof(
            product.product_code,
            ProofState.BLOCKED_UNKNOWN,
            missing_facts=frozenset({FactPath.INTENT_PURPOSES}),
        )
    purposes: frozenset[str] = frozenset(purposes_fact.value)

    support_results = _evaluate_stage(rules, RuleStage.ELIGIBILITY, facts)
    true_support = [r for r in support_results if r.truth is TruthValue.TRUE]
    covered: set[str] = set()
    for r in true_support:
        covered |= set(r.rule.effect.covered_purposes)  # type: ignore[attr-defined]

    support_unknowns = [
        r
        for r in support_results
        if r.truth is TruthValue.UNKNOWN and r.rule.on_unknown is not OnUnknownAction.NO_EFFECT
    ]

    if purposes.issubset(covered):
        score = _ranking_score(rules, facts)
        return ProductProof(
            product.product_code,
            ProofState.SUPPORTED,
            reason_codes=_reason_codes(true_support),
            covered_purposes=frozenset(covered),
            score=score,
        )

    missing_purposes = purposes - covered
    could_cover = any(
        set(r.rule.effect.covered_purposes) & missing_purposes  # type: ignore[attr-defined]
        for r in support_unknowns
    )
    if could_cover:
        missing = _underlying_facts(support_unknowns)
        return ProductProof(product.product_code, ProofState.BLOCKED_UNKNOWN, missing_facts=missing)

    return ProductProof(
        product.product_code, ProofState.UNSUPPORTED, missing_purposes=frozenset(missing_purposes)
    )


def _ranking_score(rules: tuple[CompiledRule, ...], facts: FactSnapshot) -> int:
    """Spec Sec 4.4: integer points only, unknown/false ranking facts add
    zero. Only ever called for an already-SUPPORTED proof."""
    ranking_results = _evaluate_stage(rules, RuleStage.RANKING, facts)
    return sum(
        r.rule.effect.points  # type: ignore[attr-defined]
        for r in ranking_results
        if r.truth is TruthValue.TRUE
    )


def evaluate_all(
    pack: CompiledRulePack, facts: FactSnapshot, *, effective_at: datetime
) -> tuple[dict[str, ProductProof], GlobalDecision]:
    """Every product's proof plus the aggregated global decision, per spec
    Sec 4.3's precedence (SUPPORTED_CANDIDATES > HUMAN_REVIEW_REQUIRED >
    NEEDS_INPUT > NO_SUPPORTED_PATH -- TEMPORARILY_UNAVAILABLE is out of
    scope, see module docstring).
    """

    proofs: dict[str, ProductProof] = {}
    for product in sorted(pack.products, key=lambda p: (p.product_code, str(p.product_version_id))):
        rules = pack.rules_for(product, effective_at=effective_at)
        proofs[product.product_code] = evaluate_product(product, rules, facts)

    supported = [p for p in proofs.values() if p.state is ProofState.SUPPORTED]
    if supported:
        ranked = sorted(supported, key=lambda p: (-p.score, p.product_code))
        return proofs, GlobalDecision(
            GlobalState.SUPPORTED_CANDIDATES,
            supported_product_codes=tuple(p.product_code for p in ranked),
        )

    review = [p for p in proofs.values() if p.state is ProofState.REVIEW]
    if review:
        reasons = tuple(sorted({code for p in review for code in p.reason_codes}))
        return proofs, GlobalDecision(GlobalState.HUMAN_REVIEW_REQUIRED, reason_codes=reasons)

    blocked = [p for p in proofs.values() if p.state is ProofState.BLOCKED_UNKNOWN]
    if blocked:
        missing: frozenset[FactPath] = frozenset()
        for p in blocked:
            missing |= p.missing_facts
        return proofs, GlobalDecision(GlobalState.NEEDS_INPUT, missing_facts=missing)

    excluded = [p for p in proofs.values() if p.state is ProofState.EXCLUDED]
    reasons = tuple(sorted({code for p in excluded for code in p.reason_codes})) if excluded else ()
    return proofs, GlobalDecision(GlobalState.NO_SUPPORTED_PATH, reason_codes=reasons)
