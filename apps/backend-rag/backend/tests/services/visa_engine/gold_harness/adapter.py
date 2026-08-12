"""Gold-harness proof adapter: a thin, Decision-agnostic per-product / global
tri-state evaluator built ONLY on top of what is merged to main today.

History (context for the reviewer): as of this harness's ORIGINAL authoring
date, ``backend.services.visa_engine`` shipped the condition-level evaluator
(``ast.evaluate_condition``), the compiler (``compiler.compile_rule_pack`` /
``compiler.build_compiled_pack``), and the fact-resolution step
(``fact_registry.FactRegistry.derive``) -- but the PER-PRODUCT / GLOBAL
evaluator (spec's ``evaluator.py``: ``ProductProofStatus``, ``ProductProof``,
``DecisionDraft``, ``evaluate()``) was explicitly deferred (see
``backend/services/visa_engine/__init__.py``'s PR-scope map: "evaluator.py,
trace.py -- not started"). This module was written as a stand-in, built
EXCLUSIVELY on real, merged primitives:

- ``ast.evaluate_condition`` for every condition truth value (never
  reimplemented -- this module never inspects a ``Condition`` tree directly).
- ``compiler.build_compiled_pack`` / ``CompiledRulePack.rules_for`` for stage
  ordering and bitemporal/scope selection (never reimplemented).
- ``fact_registry.FactRegistry.derive`` for the wire-to-runtime fact
  translation (never reimplemented).

**PR5 has since merged** as ``backend.services.visa_engine.evaluator``
(``evaluate_with_trace`` / ``evaluate``, imported by production's
``evaluate_path.py``). This module remains the harness's own
DECISION-AGNOSTIC proof layer (it returns plain dataclasses, never
``backend.services.visa_engine.models.Decision``) rather than a thin call
into the real ``evaluate()`` -- but it is no longer free to diverge from
``evaluator.py``'s semantics now that a real implementation exists to diverge
FROM. A 2026-08-12 prod-replay audit (23 gold personas evaluated offline
against the real production rule pack and diffed against live
``POST /api/visa-oracle/evaluate`` responses) found and fixed two concrete
divergences between this module and ``evaluator.py`` (see each function's
docstring for the specific fix):

1. **No GLOBAL ``HUMAN_REVIEW`` pre-pass.** ``evaluator.py::evaluate_with_
   trace`` evaluates every ``scope=GLOBAL, stage=HUMAN_REVIEW`` rule ONCE,
   before the per-product loop, and a TRUE (or an UNKNOWN escalated via
   ``on_unknown=HUMAN_REVIEW``) result there wins UNCONDITIONALLY over every
   other global state -- including a product's own EXCLUDED verdict from an
   unrelated GLOBAL ``HARD_FILTER`` rule that would otherwise short-circuit
   every product before its own review stage ever runs. This module used to
   only ever see a GLOBAL review rule if it happened to survive a specific
   product's own stage loop -- fixed in ``evaluate_all`` below.
2. **``_safety_unknowns`` gated on the wrong field.** It used to filter on
   ``rule.safety_critical``; ``evaluator.py::_safety_unknowns`` filters on
   ``rule.on_unknown is not OnUnknownAction.NO_EFFECT``. These are two
   DIFFERENT fields on a compiled rule -- a rule can be
   ``safety_critical=False`` yet still declare ``on_unknown=NEEDS_INPUT``
   (a real production rule does exactly this), and the old gate silently
   dropped its UNKNOWN result as if it were inconsequential. Fixed below.

Known REMAINING divergence, NOT fixed by this pass (out of the audited
scope, never observed to affect any of the 23 gold personas against either
rule pack): the ELIGIBILITY-stage "could an UNKNOWN SUPPORT rule still cover
a missing purpose" check below still unions every UNKNOWN support rule's
``covered_purposes`` naively, whereas ``evaluator.py``'s
``_has_consistent_covering_subset`` (gate round 2 P0-R2) additionally
requires the covering rules to be jointly satisfiable. A future pass should
close this gap if a persona ever exercises it.

Deliberate simplifications still standing (so a reviewer does not read them
as bugs):

1. ``missing_facts`` on a ``ProductProof``/``GlobalDecision`` is the raw
   ``ConditionResult.unknown_facts`` set, NOT translated from a
   ``derived.*`` fact back to its applicant-collected dependency (spec's
   ``underlying_applicant_facts`` helper). None of this harness's 23 gold
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
3. PRODUCTS-scoped ``HUMAN_REVIEW``/``BLOCKED_UNKNOWN`` reason/missing-fact
   aggregation (the E33E/E33F-scoped ``hr-e33e-e33f-age-band-55-59``
   BERSYARAT band rule being the one example in this pack, fires TRUE only
   for RETIREMENT-purpose applicants aged 55-59, persona 21) still unions
   across every product in that bucket, deduplicated and sorted for
   determinism, exactly as before -- only GLOBAL-scope review rules moved to
   the new dedicated pre-pass (fix 1 above); a PRODUCTS-scoped trigger has no
   pre-pass equivalent in ``evaluator.py`` either, it still flows through
   each product's own stage loop.
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
from backend.services.visa_engine.enums import (
    FactPath,
    OnUnknownAction,
    RuleScope,
    RuleStage,
    TruthValue,
)


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

    Gates on ``rule.on_unknown is not OnUnknownAction.NO_EFFECT`` -- matches
    ``evaluator.py::_safety_unknowns`` exactly (fixed 2026-08-12: this used
    to gate on ``rule.safety_critical`` instead, a DIFFERENT field. A rule
    can be ``safety_critical=False`` yet still declare
    ``on_unknown=NEEDS_INPUT``/``HUMAN_REVIEW`` -- the ``safety_critical``
    gate silently treated that UNKNOWN as inconsequential, which is exactly
    backwards: ``on_unknown`` is the rule author's own declaration of
    whether an UNKNOWN result *could* still change the outcome, independent
    of ``safety_critical``'s narrower "gates a HARD_FILTER/HUMAN_REVIEW
    exclusion or review trigger" meaning).
    """
    return [
        r
        for r in results
        if r.truth is TruthValue.UNKNOWN and r.rule.on_unknown is not OnUnknownAction.NO_EFFECT
    ]


def _partition_unknowns_by_policy(
    results: list[_RuleEvalResult],
) -> tuple[list[_RuleEvalResult], list[_RuleEvalResult]]:
    """Split an already-``_safety_unknowns``-filtered list into
    ``(review_unknowns, input_unknowns)`` by each rule's own ``on_unknown``
    policy -- mirrors ``evaluator.py::_partition_unknowns_by_policy``
    exactly (added 2026-08-12, see module docstring fix 1/2). A
    ``HUMAN_REVIEW``-tagged UNKNOWN means "if we cannot determine this, put
    it in front of a human" and escalates straight to ``REVIEW``; a
    ``NEEDS_INPUT``-tagged UNKNOWN means "ask the applicant" and blocks via
    ``BLOCKED_UNKNOWN`` exactly as before this fix.
    """
    review = [r for r in results if r.rule.on_unknown is OnUnknownAction.HUMAN_REVIEW]
    needs_input = [r for r in results if r.rule.on_unknown is OnUnknownAction.NEEDS_INPUT]
    return review, needs_input


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

    Escalation precedence within one product (matches
    ``evaluator.py::evaluate_product``'s docstring exactly, fixed
    2026-08-12, see module docstring fix 2): a stage's own definite TRUE
    always wins first (EXCLUDED / REVIEW); next, any
    ``on_unknown=HUMAN_REVIEW`` UNKNOWN from HARD_FILTER or HUMAN_REVIEW
    escalates straight to REVIEW -- a rule author asking for human judgment
    on an uncertain exclusion/review trigger outranks merely asking the
    applicant for more facts; only THEN do ``on_unknown=NEEDS_INPUT``
    UNKNOWNs from those two stages block via BLOCKED_UNKNOWN. Before this
    fix, every safety-relevant UNKNOWN from either stage fell straight to
    BLOCKED_UNKNOWN regardless of its own rule's ``on_unknown`` policy.
    """

    hard_results = _evaluate_stage(rules, RuleStage.HARD_FILTER, facts)
    true_hard = [r for r in hard_results if r.truth is TruthValue.TRUE]
    if true_hard:
        return ProductProof(
            product.product_code, ProofState.EXCLUDED, reason_codes=_reason_codes(true_hard)
        )

    hard_review_unknowns, hard_input_unknowns = _partition_unknowns_by_policy(
        _safety_unknowns(hard_results)
    )

    review_results = _evaluate_stage(rules, RuleStage.HUMAN_REVIEW, facts)
    true_review = [r for r in review_results if r.truth is TruthValue.TRUE]
    if true_review:
        return ProductProof(
            product.product_code, ProofState.REVIEW, reason_codes=_reason_codes(true_review)
        )

    review_review_unknowns, review_input_unknowns = _partition_unknowns_by_policy(
        _safety_unknowns(review_results)
    )

    if hard_review_unknowns or review_review_unknowns:
        return ProductProof(
            product.product_code,
            ProofState.REVIEW,
            reason_codes=_reason_codes(hard_review_unknowns + review_review_unknowns),
        )

    if hard_input_unknowns or review_input_unknowns:
        missing = _underlying_facts(hard_input_unknowns) | _underlying_facts(review_input_unknowns)
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
    Sec 4.3's FROZEN precedence -- HUMAN_REVIEW_REQUIRED outranks
    SUPPORTED_CANDIDATES unconditionally, which outranks NEEDS_INPUT, which
    outranks NO_SUPPORTED_PATH (the floor); TEMPORARILY_UNAVAILABLE is out
    of scope, see module docstring. Matches ``evaluator.py::evaluate_with_
    trace``'s own precedence exactly: review is checked before supported
    (gate round 1 item 2 / P0-B there) -- fixed 2026-08-12, this used to
    check supported first, which is the exact anti-pattern PR5's own gate
    round 1 caught and fixed ("copied verbatim from the spec's own
    ``evaluate()`` pseudocode ordering... wrong whenever a PRODUCTS-scoped
    review trigger can coexist with a different, genuinely SUPPORTED
    product").
    """

    proofs: dict[str, ProductProof] = {}
    for product in sorted(pack.products, key=lambda p: (p.product_code, str(p.product_version_id))):
        rules = pack.rules_for(product, effective_at=effective_at)
        proofs[product.product_code] = evaluate_product(product, rules, facts)

    # GLOBAL HUMAN_REVIEW pre-pass (spec Sec 4.3; evaluator.py gate round 1
    # item 3 / P0-C, gate round 2 item 1 / P0-R1 -- see module docstring fix
    # 1). Evaluated ONCE, independent of any per-product outcome: a TRUE
    # result, OR an UNKNOWN whose own rule opts into
    # ``on_unknown=HUMAN_REVIEW``, wins UNCONDITIONALLY over every other
    # global state below -- including a product's own EXCLUDED verdict from
    # an unrelated GLOBAL HARD_FILTER rule that would otherwise
    # short-circuit every product before its own review stage ever runs
    # (e.g. an active overstay that also happens to exceed the hard overstay
    # limit: every product proof is EXCLUDED via the hard limit, but the
    # applicant still needs a human to look at the active-overstay concern
    # first). This does NOT replace the per-product ``review`` aggregation
    # below -- a PRODUCTS-scoped review trigger (this pack's
    # ``hr-e33e-e33f-age-band-55-59``) has no pre-pass equivalent and still
    # flows through each product's own stage loop exactly as before.
    global_review_rules = tuple(
        rule
        for rule in pack.active_rules(effective_at=effective_at)
        if rule.scope is RuleScope.GLOBAL and rule.stage is RuleStage.HUMAN_REVIEW
    )
    global_review_results = _evaluate_stage(global_review_rules, RuleStage.HUMAN_REVIEW, facts)
    global_true = [r for r in global_review_results if r.truth is TruthValue.TRUE]
    global_review_unknowns, _global_input_unknowns = _partition_unknowns_by_policy(
        _safety_unknowns(global_review_results)
    )
    if global_true or global_review_unknowns:
        reasons = _reason_codes(global_true + global_review_unknowns)
        return proofs, GlobalDecision(GlobalState.HUMAN_REVIEW_REQUIRED, reason_codes=reasons)

    review = [p for p in proofs.values() if p.state is ProofState.REVIEW]
    if review:
        reasons = tuple(sorted({code for p in review for code in p.reason_codes}))
        return proofs, GlobalDecision(GlobalState.HUMAN_REVIEW_REQUIRED, reason_codes=reasons)

    supported = [p for p in proofs.values() if p.state is ProofState.SUPPORTED]
    if supported:
        ranked = sorted(supported, key=lambda p: (-p.score, p.product_code))
        return proofs, GlobalDecision(
            GlobalState.SUPPORTED_CANDIDATES,
            supported_product_codes=tuple(p.product_code for p in ranked),
        )

    blocked = [p for p in proofs.values() if p.state is ProofState.BLOCKED_UNKNOWN]
    if blocked:
        missing: frozenset[FactPath] = frozenset()
        for p in blocked:
            missing |= p.missing_facts
        return proofs, GlobalDecision(GlobalState.NEEDS_INPUT, missing_facts=missing)

    excluded = [p for p in proofs.values() if p.state is ProofState.EXCLUDED]
    reasons = tuple(sorted({code for p in excluded for code in p.reason_codes})) if excluded else ()
    return proofs, GlobalDecision(GlobalState.NO_SUPPORTED_PATH, reason_codes=reasons)
