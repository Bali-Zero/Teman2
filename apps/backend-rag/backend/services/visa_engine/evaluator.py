"""The pure per-product/global Decision evaluator orchestrator.

Source: ``research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
concretization.md`` §4 (Evaluator algorithm — §4.1 tri-state condition
semantics already lives in ``ast.evaluate_condition``; this module implements
§4.2 ``evaluate_product`` and §4.3 ``evaluate``'s global state assembly, §4.4
ranking, and the state-precedence table cited there and echoed in
``enums.DecisionState``'s own docstring).

PR5 scope (this module, per the task brief that authorized it): the
top-level PURE function that assembles a ``models.Decision`` from an
``ApplicantFacts`` + an already-compiled ``compiler.CompiledRulePack``. No
I/O, no DB, no wall-clock reads beyond the two instants the caller passes in
(``effective_at``/``observed_at``) — determinism is the point (same inputs
must produce a byte-identical ``Decision`` on every call).

# Gate round 1 (2026-07-19) — GATE: FIX-FIRST, two independent cross-family
# seats (Codex GPT-5.6-sol xhigh + Kimi K3), convergent on the load-bearing
# finding

Both seats independently found the same defect (P0-C below) from different
angles and both required fixes below; every "divergence" paragraph that
follows has been re-audited against that review and updated to say what
actually ships now, not what an earlier draft of this module claimed.

1. **P0-A — purpose-coverage UNKNOWN handling was backwards.** The original
   ``evaluate_product`` asked "does ANY unknown SUPPORT rule's
   ``covered_purposes`` intersect ANY missing purpose" and returned
   ``BLOCKED_UNKNOWN`` if so. That is wrong whenever a product has one
   missing purpose no rule anywhere could ever cover (permanently
   unsupportable) *and* another missing purpose an unknown rule could
   resolve — the old check let the permanently-unsupportable purpose ride
   along and reported ``BLOCKED_UNKNOWN`` (``NEEDS_INPUT`` globally) instead
   of the correct ``UNSUPPORTED`` (``NO_SUPPORTED_PATH`` globally) — an
   UNKNOWN was silently producing a *better*-ranked global state than a
   definite FALSE would have, backwards from the "UNKNOWN never increases
   eligibility" invariant this module enforces everywhere else. Fixed: see
   ``evaluate_product``'s ``potential_coverage`` computation below —
   ``BLOCKED_UNKNOWN`` only when resolving *every* unknown SUPPORT rule
   favorably would fully cover every declared purpose; otherwise
   ``UNSUPPORTED`` right now, because no future fact could ever change that.
2. **P0-B — the global state-assembly order was inverted relative to the
   frozen precedence table.** ``enums.DecisionState``'s own docstring is
   unambiguous: ``HUMAN_REVIEW_REQUIRED`` outranks ``SUPPORTED_CANDIDATES``
   unconditionally. An earlier draft of this module checked ``supported``
   before ``review`` in the outer loop (copied verbatim from the spec's own
   ``evaluate()`` pseudocode ordering) on the theory that a PRODUCTS-scoped
   review trigger could never coexist with an unrelated SUPPORTED product in
   a way that mattered — the gate round showed that claim false (a
   PRODUCTS-scoped, not GLOBAL, review trigger on one product *can* coexist
   with a different product being genuinely SUPPORTED, and the frozen table
   requires REVIEW to win regardless). Fixed: ``evaluate()`` now checks
   ``review`` before ``supported`` — see that function.
3. **P0-C — the "folded GLOBAL review pre-pass" equivalence claim was
   refuted with three concrete counterexamples.** An earlier draft argued
   that folding the spec's separate ``evaluate_global_review_rules`` pre-pass
   into the existing per-product ``HUMAN_REVIEW`` stage was "provably
   equivalent" to a real pre-pass, since ``CompiledRulePack.rules_for()``
   already includes every GLOBAL rule in every product's own rule list. That
   argument silently assumed the per-product loop always runs and always
   reaches its own ``HUMAN_REVIEW`` stage for every product — false in three
   reachable cases: (a) ``intent.purposes`` itself UNKNOWN — the per-product
   loop never even starts, short-circuited before it by the purposes check;
   (b) zero products ACTIVE/effective at ``effective_at`` — the loop
   produces an empty ``proofs`` list; (c) a GLOBAL ``HARD_FILTER`` also fires
   TRUE for every product — each product's own stage loop returns
   ``EXCLUDED`` before it ever reaches its ``HUMAN_REVIEW`` stage, silently
   suppressing the GLOBAL review concern. Fixed: ``evaluate()`` now evaluates
   every in-force GLOBAL ``HUMAN_REVIEW`` rule ONCE, before purpose
   extraction and before the per-product loop, and returns
   ``HUMAN_REVIEW_REQUIRED`` immediately on any TRUE result — see
   ``evaluate()``'s pre-pass block. This does not replace or deduplicate the
   per-product ``HUMAN_REVIEW`` stage: PRODUCTS-scoped review rules (and a
   GLOBAL rule that resolves UNKNOWN rather than TRUE here) still flow
   through ``evaluate_product()`` exactly as before.
4. **P1 — ``on_unknown=HUMAN_REVIEW`` was a dead option**, silently treated
   identically to ``on_unknown=NEEDS_INPUT``. Fixed: an UNKNOWN result from a
   rule declaring ``on_unknown=HUMAN_REVIEW`` now escalates to ``REVIEW``
   (contributing a review reason built from that rule) instead of
   contributing a missing fact — see ``_partition_unknowns_by_policy``.
5. **P1 — the identity/fingerprint placeholder had no runtime guard.**
   Fixed: the default provider now raises ``PlaceholderIdentityNotAllowedError``
   outside ``environment=TEST``, and ``evaluate()`` accepts an injectable
   ``identity_provider`` — see the "Deterministic identity" section below.
6. **P1 — the global ``missing_facts`` union asked for more than necessary.**
   Fixed: ``evaluate()`` now selects the single ``BLOCKED_UNKNOWN`` proof
   with the fewest ``missing_facts`` (deterministic tie-break by product
   order) rather than the union across every blocked product — see
   ``evaluate()``'s ``blocked`` branch.
7. **P1 — the ``NO_SUPPORTED_PATH`` fallback ``Reason`` was uncited.** Fixed:
   see ``_fallback_no_path_reason`` below — citations are now derived from
   the evaluated products' own catalog sources (or the pack's own
   ``source_records`` when zero products were evaluated at all). Framing
   correction (Kimi gate round 1): reaching this fallback is **not**
   necessarily evidence of a pack-authoring gap — an applicant whose
   declared purposes genuinely no product covers is a normal, legitimate
   evaluation outcome; the fallback exists purely because ``Decision``
   requires a non-empty ``no_path_reasons`` for this state and this engine's
   design otherwise expresses every real disqualifying claim as a named
   rule.

# Gate round 2 (2026-07-20) — GATE: FIX-FIRST on the round-1 fix commit
# itself, Codex GPT-5.6-sol xhigh, two EXECUTED counterexamples (not theory)

1. **P0-R1 — the GLOBAL HUMAN_REVIEW pre-pass dropped UNKNOWN.** Round 1's
   pre-pass only reacted to a definite TRUE result from a GLOBAL review
   rule. A GLOBAL review rule whose condition evaluates UNKNOWN with
   ``rule.on_unknown == HUMAN_REVIEW`` must ALSO contribute a review
   reason — that is the entire meaning of ``on_unknown=HUMAN_REVIEW``
   ("if we can't tell, a human must look"), and item 4 above already
   established that policy for the per-product stages; the pre-pass had
   silently not been given the same treatment. Executed counterexamples
   (purposes UNKNOWN / zero active products / a GLOBAL hard-filter
   excluding everything, each paired with an UNKNOWN-not-TRUE GLOBAL
   review condition) wrongly fell through to ``NEEDS_INPUT`` or
   ``NO_SUPPORTED_PATH`` instead of the correct ``HUMAN_REVIEW_REQUIRED``.
   Fixed: the pre-pass now also collects UNKNOWN entries whose rule opts
   into ``HUMAN_REVIEW``, mirroring ``_partition_unknowns_by_policy`` —
   see ``evaluate()``'s pre-pass block.
2. **P0-R2 — ``potential_coverage`` (round 1's own P0-A fix) unioned
   jointly-unsatisfiable rules.** A flat union of every unknown SUPPORT
   rule's ``covered_purposes`` is itself a Strong-Kleene violation
   whenever two of those rules can never both be TRUE at once. Executed
   counterexample: purposes ``{TOURISM, STUDY}``; rule A covers TOURISM
   iff ``marital_status == MARRIED``; rule B covers STUDY iff
   ``marital_status == SINGLE``; ``marital_status`` UNKNOWN. The union
   claimed both purposes jointly coverable (→ ``BLOCKED_UNKNOWN``), but
   EVERY concrete resolution of ``marital_status`` (either value) can
   only ever satisfy one of the two rules — the true answer is
   ``UNSUPPORTED`` right now. Fixed: ``_has_consistent_covering_subset``
   requires at least one subset of the unknown rules that is BOTH a
   covering set AND jointly consistent (no two rules in the subset
   necessarily requiring the same fact path to equal two different
   constants) — see that function and ``_jointly_consistent`` below.
   Direction constraint (do not invert): satisfiability is
   OVER-approximated, never under-approximated — an unanalyzable
   condition shape, or a rule count too large to brute-force, defaults to
   "assume consistent"/"assume coverable", because an extra
   ``BLOCKED_UNKNOWN`` is recoverable and a wrong ``UNSUPPORTED`` is not.

# Divergences from the spec text still standing (recorded here + in the PR
# body)

1. **Signature/return type.** Spec §1's ``evaluator.py`` snippet has
   ``evaluate(pack, facts, *, context: EvaluationContext) -> DecisionDraft``.
   Neither ``EvaluationContext`` nor ``DecisionDraft`` exists anywhere in this
   package (both are explicitly "not started, deferred" per
   ``visa_engine/__init__.py``'s PR-scope map) — the PR5 task brief instead
   specifies ``evaluate(facts, compiled_pack, *, effective_at, observed_at)
   -> Decision`` directly, skipping the draft/context indirection entirely.
   This module follows the task brief (a real, already-frozen target type)
   over the spec's scaffolding names for two never-implemented types.
2. **``facts`` is the wire ``models.ApplicantFacts``, not a pre-derived
   ``ast.FactSnapshot``.** The spec's ``evaluate_product``/``evaluate``
   pseudocode takes a ``FactSnapshot`` directly; this module's public
   ``evaluate()`` takes the raw ``ApplicantFacts`` and calls
   ``fact_registry.FactRegistry.derive()`` itself (still pure — derivation
   reads only ``effective_at``, already an explicit parameter). This keeps
   the "one call assembles one Decision" contract self-contained for
   callers, and matches the task brief's "FactSnapshot-or-ApplicantFacts per
   the models' shape" phrasing by picking the actual ``models.py`` type.
3. **``TEMPORARILY_UNAVAILABLE`` is never produced by this function.** Its
   two triggers per spec §4.3 ("absent/unverifiable pack, compilation
   failure" and "persistence-required dependency failure") are both
   *upstream* of this pure function's precondition: it only ever runs
   against an already-``build_compiled_pack``-validated
   ``CompiledRulePack`` (compilation already succeeded by construction) and
   never calls out to persistence/pricing (``repository.py``/``pricing.py``
   are undone, PR4+/later scope) — ``quotes`` is always ``()``. Resolving
   "no active pack" is the caller's (repository/service layer) job, done
   *before* ``evaluate()`` is ever invoked.
4. **``facts_fingerprint``/``decision_id``/``public_id`` use a documented
   PLACEHOLDER, not real HMAC secret management** — now runtime-guarded (see
   gate-round-1 item 5 above) and injectable so STEP-6+ can swap in real
   crypto without touching this module's control flow. ``crypto.py`` (secret/
   key management) is undone (PR4+/later, per ``__init__.py``'s PR-scope
   map), so this module cannot pull a real HMAC key from anywhere without
   inventing one out of scope; it instead derives a deterministic (same
   inputs -> same output, required for the determinism test) fingerprint
   using a fixed, clearly-named, NON-SECRET placeholder key
   (``_FACTS_FINGERPRINT_PLACEHOLDER_KEY``) — mirroring ``bundle.py``'s own
   "UNSIGNED-DEV firebreak, never silently treated as real security"
   posture. ``decision_id``/``public_id`` are derived (UUIDv5 / truncated
   SHA-256 hex) from the same inputs for the same determinism reason. **Do
   not treat any of these three as a real integrity guarantee until
   crypto.py lands the genuine secret**, and see ``_deterministic_ids``'s
   docstring for why ``public_id`` specifically must never be treated as an
   access-control capability either, even once it is real.

Everything else (per-product stage loop order, UNKNOWN-never-increases-
eligibility, purpose-coverage hit policy, ranking, state precedence) follows
spec §4.2/§4.3/§4.4 exactly — see each function's docstring for the specific
paragraph it implements.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from backend.services.visa_engine import ast as ast_module
from backend.services.visa_engine.ast import ConditionResult, FactSnapshot, UnknownFact
from backend.services.visa_engine.compiler import CompiledProduct, CompiledRule, CompiledRulePack
from backend.services.visa_engine.enums import (
    DecisionState,
    Environment,
    FactPath,
    OnUnknownAction,
    RuleScope,
    RuleStage,
    TruthValue,
    VisaProductStatus,
)
from backend.services.visa_engine.errors import PlaceholderIdentityNotAllowedError
from backend.services.visa_engine.fact_registry import (
    DEFAULT_FACT_REGISTRY,
    FactRegistry,
    canonical_fact_payload,
)
from backend.services.visa_engine.models import (
    ApplicantFacts,
    Candidate,
    Decision,
    Fingerprint,
    Outage,
    PriceQuote,
    Reason,
    RulePackRef,
    TimeRange,
)

# ---------------------------------------------------------------------------
# ProductProofStatus / ProductProof (spec §1 evaluator.py, §4.2)
# ---------------------------------------------------------------------------


class ProductProofStatus(str, Enum):
    """The five per-product proof outcomes (spec §1 ``evaluator.py``, §4.2)."""

    EXCLUDED = "EXCLUDED"
    REVIEW = "REVIEW"
    BLOCKED_UNKNOWN = "BLOCKED_UNKNOWN"
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True, slots=True)
class ProductProof:
    """One product's proof outcome (spec §4.2 ``evaluate_product``).

    Only the fields relevant to ``status`` are populated; the rest keep
    their empty default — never a signal in themselves, always read
    conditionally on ``status`` by the caller (mirrors ``models.Decision``'s
    own state-conditional field discipline).
    """

    product: CompiledProduct
    status: ProductProofStatus
    #: Populated for EXCLUDED (exclusion reasons) and REVIEW (review
    #: reasons — either a definite TRUE trigger, or an on_unknown=
    #: HUMAN_REVIEW escalation, see ``_unknown_reasons``).
    reasons: tuple[Reason, ...] = ()
    #: Populated for BLOCKED_UNKNOWN — applicant-collected paths only (derived
    #: paths already resolved to their dependency per ``_underlying_applicant_facts``).
    missing_facts: frozenset[FactPath] = frozenset()
    #: Populated for SUPPORTED — every TRUE ELIGIBILITY (SUPPORT-effect) rule.
    support_rules: tuple[CompiledRule, ...] = ()
    #: Populated for SUPPORTED — union of ``support_rules``' covered purposes.
    covered_purposes: frozenset[str] = frozenset()
    #: Populated for UNSUPPORTED — the declared purposes no TRUE (or
    #: potentially-TRUE-via-an-unresolved-unknown) rule could ever cover.
    missing_purposes: frozenset[str] = frozenset()


# ---------------------------------------------------------------------------
# Stage-evaluation plumbing
# ---------------------------------------------------------------------------

_StageResult = tuple[CompiledRule, ConditionResult]


def _rules_by_stage(rules: Sequence[CompiledRule]) -> Mapping[RuleStage, tuple[CompiledRule, ...]]:
    """Partition an already ``rules_for()``-selected/sorted rule sequence by stage.

    Order within each stage is preserved (``rules_for`` already sorted by
    ``(stage.order, priority, rule_id)``), so iterating a bucket stays
    deterministic.
    """
    buckets: dict[RuleStage, list[CompiledRule]] = {stage: [] for stage in RuleStage}
    for rule in rules:
        buckets[rule.stage].append(rule)
    return {stage: tuple(bucket) for stage, bucket in buckets.items()}


def _evaluate_stage(rules: Sequence[CompiledRule], facts: FactSnapshot) -> tuple[_StageResult, ...]:
    """Evaluate every rule in one stage against ``facts``. Never short-circuits
    across rules (each rule's own ``evaluate_condition`` already never
    short-circuits within itself — spec §4.1)."""
    return tuple((rule, ast_module.evaluate_condition(rule.when, facts)) for rule in rules)


def _safety_unknowns(entries: Sequence[_StageResult]) -> tuple[_StageResult, ...]:
    """The subset of ``entries`` whose condition is UNKNOWN and whose rule
    does not declare ``on_unknown=NO_EFFECT`` — i.e. an UNKNOWN result that
    the rule author says *could* still change the outcome once resolved
    (whether by asking the applicant, per ``NEEDS_INPUT``, or by escalating
    to a human reviewer, per ``HUMAN_REVIEW`` — see
    ``_partition_unknowns_by_policy`` for that split).
    """
    return tuple(
        (rule, result)
        for rule, result in entries
        if result.truth is TruthValue.UNKNOWN and rule.on_unknown is not OnUnknownAction.NO_EFFECT
    )


def _partition_unknowns_by_policy(
    entries: Sequence[_StageResult],
) -> tuple[tuple[_StageResult, ...], tuple[_StageResult, ...]]:
    """Split an already-``_safety_unknowns``-filtered sequence into
    ``(review_unknowns, input_unknowns)`` by each rule's own ``on_unknown``
    policy (gate round 1 item 4, 2026-07-19 — ``on_unknown=HUMAN_REVIEW`` was
    previously a dead option, silently treated identically to
    ``NEEDS_INPUT``).

    A ``HUMAN_REVIEW``-tagged UNKNOWN contributes a review reason: the rule
    author is saying "if we cannot determine this, put it in front of a
    human — do not just ask the applicant for more facts". A
    ``NEEDS_INPUT``-tagged UNKNOWN contributes a missing fact, exactly as
    before.
    """
    review = tuple(
        entry for entry in entries if entry[0].on_unknown is OnUnknownAction.HUMAN_REVIEW
    )
    needs_input = tuple(
        entry for entry in entries if entry[0].on_unknown is OnUnknownAction.NEEDS_INPUT
    )
    return review, needs_input


def _sorted_uuids(values: Iterable[uuid.UUID]) -> tuple[uuid.UUID, ...]:
    return tuple(sorted(set(values), key=str))


def _reason_from_rule(rule: CompiledRule) -> Reason:
    """Build one ``Reason`` from a rule whose effect fired (EXCLUDE or
    REQUIRE_REVIEW), or whose UNKNOWN result escalated to review under
    ``on_unknown=HUMAN_REVIEW`` — citations propagated verbatim from the
    rule either way.
    """
    return Reason(
        code=rule.effect.reason_code,  # type: ignore[union-attr]
        rule_ids=(rule.rule_id,),
        source_refs=_sorted_uuids(rule.source_refs),
    )


def _true_reasons(entries: Sequence[_StageResult]) -> tuple[Reason, ...]:
    """One ``Reason`` per rule whose condition evaluated definitely TRUE."""
    return tuple(
        _reason_from_rule(rule) for rule, result in entries if result.truth is TruthValue.TRUE
    )


def _unknown_reasons(entries: Sequence[_StageResult]) -> tuple[Reason, ...]:
    """One ``Reason`` per rule in an UNKNOWN-but-escalated-to-review bucket
    (``on_unknown=HUMAN_REVIEW``, see ``_partition_unknowns_by_policy``) —
    reuses the rule's own ``reason_code``/citations exactly like
    ``_true_reasons`` does for a definite TRUE, since the rule author
    declared this particular UNKNOWN itself review-worthy.
    """
    return tuple(_reason_from_rule(rule) for rule, _ in entries)


def _dedupe_reasons(reasons: Iterable[Reason]) -> tuple[Reason, ...]:
    """Collapse duplicate ``Reason``s (same code/rule_ids/source_refs) that
    arise when the same GLOBAL rule fires identically across several
    products — first-seen order preserved for determinism.
    """
    seen: dict[tuple[str, tuple[str, ...], tuple[str, ...]], Reason] = {}
    for reason in reasons:
        key = (
            reason.code,
            tuple(reason.rule_ids),
            tuple(str(ref) for ref in reason.source_refs),
        )
        seen.setdefault(key, reason)
    return tuple(seen.values())


#: Gate round 2 (2026-07-20) P0-R2: cap on the number of UNKNOWN support
#: rules `_has_consistent_covering_subset` will brute-force (2**N subsets).
#: A rule pack with more UNKNOWN ELIGIBILITY rules than this on a SINGLE
#: product is already pathological. Beyond the cap we fall back to
#: assuming a consistent covering subset exists (the pre-round-2 union
#: behavior) — per the direction constraint below, an extra
#: BLOCKED_UNKNOWN is always the safe failure mode, a wrong UNSUPPORTED
#: never is, so an unaffordable proof must default to the favorable side.
_MAX_SUBSET_SEARCH_RULES = 20


def _required_equalities(
    condition: ast_module.Condition,
) -> tuple[tuple[FactPath, ast_module.Scalar], ...]:
    """Conservative, purely-structural extraction of the equality
    constraints a condition NECESSARILY requires to hold TRUE — used only
    to detect DEFINITE cross-rule inconsistency (gate round 2 P0-R2, see
    module docstring). Descends only through ``AllCondition`` (conjunction
    — every child must hold, so every child's own necessary equalities are
    also necessary for the whole) and a bare ``EqCondition`` leaf. Any
    other node shape (``any``/``not``/every other leaf op) is NOT descended
    into and contributes nothing: per the over-approximate-satisfiability
    direction, an unanalyzable shape must never manufacture a false
    inconsistency — under-reporting constraints here can only make two
    rules look MORE compatible than they really are, never less, which is
    exactly the safe-side error to make.
    """
    if isinstance(condition, ast_module.EqCondition):
        return ((condition.fact, condition.value),)
    if isinstance(condition, ast_module.AllCondition):
        out: list[tuple[FactPath, ast_module.Scalar]] = []
        for child in condition.args:
            out.extend(_required_equalities(child))
        return tuple(out)
    return ()


def _jointly_consistent(rules: Sequence[CompiledRule]) -> bool:
    """Conservative joint-consistency check (gate round 2 P0-R2): FALSE
    only when two rules in ``rules`` both necessarily require the SAME
    fact path to equal two DIFFERENT constants — a definite,
    structurally-provable contradiction (e.g. one rule requires
    ``marital_status == MARRIED``, another requires ``marital_status ==
    SINGLE``: no single fact resolution can ever satisfy both). Anything
    else — including every condition shape ``_required_equalities`` cannot
    analyze — is presumed consistent.
    """
    seen: dict[FactPath, ast_module.Scalar] = {}
    for rule in rules:
        for fact, value in _required_equalities(rule.when):
            if fact in seen and seen[fact] != value:
                return False
            seen[fact] = value
    return True


def _has_consistent_covering_subset(
    missing_purposes: frozenset[str], unknown_entries: Sequence[_StageResult]
) -> bool:
    """Gate round 2 (2026-07-20) P0-R2: does there exist a jointly
    consistent subset of the given UNKNOWN support rules whose
    ``covered_purposes`` union fully covers ``missing_purposes``?

    The round-1 fix (see module docstring, P0-A) unioned EVERY unknown
    support rule's ``covered_purposes`` unconditionally — wrong whenever
    two of those rules can never both be true at once (a direct
    Strong-Kleene violation: UNKNOWN would then be strictly MORE
    favorable than every one of its own possible concrete resolutions).
    This enumerates subsets rather than unioning everything, so a
    jointly-unsatisfiable pair can no longer manufacture false coverage.

    Direction constraint (do not invert): satisfiability is
    OVER-approximated, never under-approximated. An extra
    ``BLOCKED_UNKNOWN`` is recoverable (ask the fact, resolve correctly
    next round); a wrong ``UNSUPPORTED`` is a definitive wrong legal
    answer. So beyond ``_MAX_SUBSET_SEARCH_RULES`` (an unaffordable brute
    force) this returns ``True`` — the safe, favorable default — rather
    than attempting a proof it cannot complete.
    """
    if not missing_purposes:
        return True
    rules = tuple(rule for rule, _ in unknown_entries)
    if len(rules) > _MAX_SUBSET_SEARCH_RULES:
        return True
    for mask in range(1, 1 << len(rules)):
        subset = tuple(rule for i, rule in enumerate(rules) if mask & (1 << i))
        subset_coverage: frozenset[str] = frozenset[str]().union(
            *(frozenset(rule.effect.covered_purposes) for rule in subset)  # type: ignore[union-attr]
        )
        if missing_purposes <= subset_coverage and _jointly_consistent(subset):
            return True
    return False


def _underlying_applicant_facts(
    entries: Sequence[_StageResult], fact_registry: FactRegistry
) -> frozenset[FactPath]:
    """Every fact path referenced as UNKNOWN across ``entries``, with any
    ``derived.*`` path resolved back to its applicant-collected
    dependency/dependencies (``fact_registry.FactSpec.dependencies``).

    Required because ``Decision.missing_facts`` rejects derived paths
    outright (a derived fact is never something the applicant can "answer" —
    only its dependency can be collected) and because a condition can
    reference a derived path directly (e.g. ``derived.has_indonesian_
    citizenship``) whose own UNKNOWN-ness always traces back to exactly one
    applicant path per the current registry (1 level deep in practice, but
    walked iteratively/generically here rather than assuming that depth).
    """
    if not entries:
        return frozenset()
    raw = frozenset[FactPath]().union(*(result.unknown_facts for _, result in entries))
    resolved: set[FactPath] = set()
    stack: list[FactPath] = list(raw)
    seen: set[FactPath] = set()
    while stack:
        path = stack.pop()
        if path in seen:
            continue
        seen.add(path)
        spec = fact_registry.spec(path)
        if spec.derived:
            stack.extend(spec.dependencies)
        else:
            resolved.add(path)
    return frozenset(resolved)


# ---------------------------------------------------------------------------
# Per-product proof (spec §4.2 ``evaluate_product``)
# ---------------------------------------------------------------------------


def evaluate_product(
    *,
    product: CompiledProduct,
    rules: Sequence[CompiledRule],
    facts: FactSnapshot,
    purposes: frozenset[str],
    fact_registry: FactRegistry = DEFAULT_FACT_REGISTRY,
) -> ProductProof:
    """Evaluate one product's HARD_FILTER -> HUMAN_REVIEW -> ELIGIBILITY
    stage loop (spec §4.2, verbatim algorithm — the docstring order matches
    ``enums.STAGE_ORDER``, not ``RuleStage``'s declaration order).

    ``rules`` must already be the product-specific, in-force, sorted rule
    sequence (``CompiledRulePack.rules_for(product, effective_at=...)``).

    Escalation precedence within one product (gate round 1 item 4, see
    module docstring): a stage's own definite TRUE always wins first
    (EXCLUDED / REVIEW); next, any ``on_unknown=HUMAN_REVIEW`` UNKNOWN from
    HARD_FILTER or HUMAN_REVIEW escalates straight to REVIEW — a rule author
    asking for human judgment on an uncertain exclusion/review trigger
    outranks merely asking the applicant for more facts; only then do
    ``on_unknown=NEEDS_INPUT`` UNKNOWNs from those two stages block via
    BLOCKED_UNKNOWN. ELIGIBILITY runs last and applies the same
    review-before-input precedence to whichever unknown SUPPORT rules are
    actually relevant to the remaining purpose gap (see the
    ``potential_coverage`` computation below, gate round 1 item 1 / P0-A).
    """
    by_stage = _rules_by_stage(rules)

    hard_results = _evaluate_stage(by_stage.get(RuleStage.HARD_FILTER, ()), facts)
    if any(result.truth is TruthValue.TRUE for _, result in hard_results):
        return ProductProof(
            product=product,
            status=ProductProofStatus.EXCLUDED,
            reasons=_true_reasons(hard_results),
        )
    hard_safety = _safety_unknowns(hard_results)
    hard_review_unknowns, hard_input_unknowns = _partition_unknowns_by_policy(hard_safety)

    review_results = _evaluate_stage(by_stage.get(RuleStage.HUMAN_REVIEW, ()), facts)
    if any(result.truth is TruthValue.TRUE for _, result in review_results):
        return ProductProof(
            product=product,
            status=ProductProofStatus.REVIEW,
            reasons=_true_reasons(review_results),
        )
    review_safety = _safety_unknowns(review_results)
    review_review_unknowns, review_input_unknowns = _partition_unknowns_by_policy(review_safety)

    if hard_review_unknowns or review_review_unknowns:
        return ProductProof(
            product=product,
            status=ProductProofStatus.REVIEW,
            reasons=_unknown_reasons(hard_review_unknowns + review_review_unknowns),
        )

    support_results = _evaluate_stage(by_stage.get(RuleStage.ELIGIBILITY, ()), facts)
    true_support = tuple(
        (rule, result) for rule, result in support_results if result.truth is TruthValue.TRUE
    )
    covered: frozenset[str] = (
        frozenset[str]().union(
            *(frozenset(rule.effect.covered_purposes) for rule, _ in true_support)  # type: ignore[union-attr]
        )
        if true_support
        else frozenset()
    )
    support_safety = _safety_unknowns(support_results)
    support_review_unknowns, support_input_unknowns = _partition_unknowns_by_policy(support_safety)

    if hard_input_unknowns or review_input_unknowns:
        missing = _underlying_applicant_facts(
            hard_input_unknowns + review_input_unknowns, fact_registry
        )
        return ProductProof(
            product=product,
            status=ProductProofStatus.BLOCKED_UNKNOWN,
            missing_facts=missing,
        )

    if purposes <= covered:
        return ProductProof(
            product=product,
            status=ProductProofStatus.SUPPORTED,
            support_rules=tuple(rule for rule, _ in true_support),
            covered_purposes=covered,
        )

    missing_purposes = purposes - covered

    # P0-A fix (gate round 1 item 1, see module docstring): the previous
    # check asked "does ANY unknown SUPPORT rule's covered_purposes
    # intersect ANY missing purpose" — wrong whenever one missing purpose is
    # permanently uncoverable by anything in this product while ANOTHER is
    # potentially coverable via an unknown rule. `naive_potential_coverage`
    # below (the optimistic union, ignoring joint consistency) still answers
    # exactly that question: any purpose it can't reach is permanently
    # uncoverable by ANYTHING in this product, full stop, regardless of how
    # any fact resolves — reported verbatim as `missing_purposes` here,
    # unchanged from round 1.
    naive_potential_coverage: frozenset[str] = covered | (
        frozenset[str]().union(
            *(frozenset(rule.effect.covered_purposes) for rule, _ in support_safety)  # type: ignore[union-attr]
        )
        if support_safety
        else frozenset()
    )
    if not (purposes <= naive_potential_coverage):
        return ProductProof(
            product=product,
            status=ProductProofStatus.UNSUPPORTED,
            missing_purposes=purposes - naive_potential_coverage,
        )

    # Gate round 2 (2026-07-20) P0-R2: the optimistic union above says every
    # purpose is INDIVIDUALLY reachable by some unknown rule — but it never
    # asked whether those rules can all be TRUE at the same time. That is
    # itself a Strong-Kleene violation whenever two of them can never both
    # hold at once (e.g. one requires `marital_status == MARRIED` to cover
    # TOURISM, another requires `marital_status == SINGLE` to cover STUDY:
    # no resolution of `marital_status` ever covers both, yet the union
    # claimed it did, making the UNKNOWN case strictly MORE favorable than
    # every one of its own possible concrete resolutions).
    # `_has_consistent_covering_subset` requires at least one JOINTLY
    # CONSISTENT covering subset of the unknown rules, not just a bare
    # union. If none exists, the product is definitively UNSUPPORTED right
    # now — no single future resolution could ever realize the coverage the
    # naive union promised.
    if not _has_consistent_covering_subset(missing_purposes, support_safety):
        return ProductProof(
            product=product,
            status=ProductProofStatus.UNSUPPORTED,
            missing_purposes=missing_purposes,
        )

    # Every declared purpose IS potentially coverable by some jointly
    # consistent combination of unknown SUPPORT rules — scope the decision
    # to the unknown SUPPORT rules that actually touch the remaining gap (an
    # unknown rule covering a purpose the applicant never declared must not
    # drive either bucket). Review-tagged relevance wins over input-tagged,
    # consistent with the review-before-input precedence used above.
    relevant_review = tuple(
        entry
        for entry in support_review_unknowns
        if frozenset(entry[0].effect.covered_purposes) & missing_purposes  # type: ignore[union-attr]
    )
    relevant_input = tuple(
        entry
        for entry in support_input_unknowns
        if frozenset(entry[0].effect.covered_purposes) & missing_purposes  # type: ignore[union-attr]
    )
    if relevant_review:
        return ProductProof(
            product=product,
            status=ProductProofStatus.REVIEW,
            reasons=_unknown_reasons(relevant_review),
        )
    missing = _underlying_applicant_facts(relevant_input, fact_registry)
    return ProductProof(
        product=product,
        status=ProductProofStatus.BLOCKED_UNKNOWN,
        missing_facts=missing,
    )


# ---------------------------------------------------------------------------
# Ranking (spec §4.4)
# ---------------------------------------------------------------------------


def _rank_supported(
    proofs: Sequence[ProductProof],
    facts: FactSnapshot,
    compiled_pack: CompiledRulePack,
    *,
    effective_at: datetime,
) -> tuple[Candidate, ...]:
    """Rank already-SUPPORTED proofs only (spec §4.4). Ranking rules add
    integer points; UNKNOWN ranking facts add zero (never re-derive
    eligibility, never add/remove a candidate). Stable order
    ``(-score, product_code, str(product_version_id))``.
    """
    scored: list[tuple[ProductProof, int]] = []
    for proof in proofs:
        rules = compiled_pack.rules_for(proof.product, effective_at=effective_at)
        score = 0
        for rule in rules:
            if rule.stage is not RuleStage.RANKING:
                continue
            result = ast_module.evaluate_condition(rule.when, facts)
            if result.truth is TruthValue.TRUE:
                score += rule.effect.points  # type: ignore[union-attr]
        scored.append((proof, score))

    scored.sort(
        key=lambda item: (
            -item[1],
            item[0].product.product_code,
            str(item[0].product.product_version_id),
        )
    )

    candidates: list[Candidate] = []
    for rank, (proof, score) in enumerate(scored, start=1):
        support_rule_ids = tuple(rule.rule_id for rule in proof.support_rules)
        source_refs = _sorted_uuids(ref for rule in proof.support_rules for ref in rule.source_refs)
        reason_codes = tuple(
            dict.fromkeys(rule.effect.reason_code for rule in proof.support_rules)  # type: ignore[union-attr]
        )
        candidates.append(
            Candidate(
                rank=rank,
                product_version_id=proof.product.product_version_id,
                product_code=proof.product.product_code,
                score=score,
                covered_purposes=tuple(sorted(proof.covered_purposes)),
                support_rule_ids=support_rule_ids,
                source_refs=source_refs,
                reason_codes=reason_codes,
            )
        )
    return tuple(candidates)


# ---------------------------------------------------------------------------
# Notices — requested legacy product code (VisaProductVersion.legacy_codes)
# ---------------------------------------------------------------------------


def _build_notices(facts: FactSnapshot, compiled_pack: CompiledRulePack) -> tuple[Reason, ...]:
    """If the applicant's ``intent.requested_product_code`` matches a
    product's ``legacy_codes`` (a code retired by a regulatory reclassification
    but still requested by name), emit a non-blocking ``OBSOLETE_PRODUCT_CODE``
    notice citing the canonical product's own sources. Not part of spec
    §4.2/§4.3's pseudocode verbatim — ``Decision.notices`` exists precisely
    for this kind of informational, non-legal-state-changing signal, and
    ``VisaProductVersion.legacy_codes`` exists precisely to make this lookup
    possible (see gold persona 18/19).
    """
    requested = facts.values.get(FactPath.INTENT_REQUESTED_PRODUCT_CODE)
    if requested is None or isinstance(requested, UnknownFact):
        return ()
    requested_code = str(requested.value)
    notices: list[Reason] = []
    for compiled_product in compiled_pack.products:
        if requested_code in compiled_product.product.legacy_codes:
            notices.append(
                Reason(
                    code="OBSOLETE_PRODUCT_CODE",
                    rule_ids=(),
                    source_refs=_sorted_uuids(compiled_product.product.source_refs),
                )
            )
    return tuple(notices)


# ---------------------------------------------------------------------------
# Deterministic identity + facts fingerprint (see module docstring)
# ---------------------------------------------------------------------------

#: NOT a secret. A fixed, non-secret placeholder standing in for the real
#: HMAC key ``crypto.py`` (PR4+/later, undone) will eventually manage. Never
#: treat a ``Fingerprint`` built with this key as a real integrity guarantee.
_FACTS_FINGERPRINT_PLACEHOLDER_KEY = b"visa-engine-pr5-unsigned-dev-placeholder-key"
_FACTS_FINGERPRINT_KEY_ID = "pr5-unsigned-dev-placeholder-v1"

#: Fixed, arbitrary namespace UUID for deriving a deterministic ``decision_id``
#: via UUIDv5 — never treat as a secret; its only job is to keep the derived
#: UUID out of the random (v4) namespace so it is visibly "derived, not random".
_DECISION_ID_NAMESPACE = uuid.UUID("2f6a8b2e-6a3b-4b8e-9b0a-6f1a8b2e6a3b")


def _facts_fingerprint(facts: ApplicantFacts) -> Fingerprint:
    canonical = canonical_fact_payload(facts)
    payload_bytes = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(_FACTS_FINGERPRINT_PLACEHOLDER_KEY, payload_bytes, hashlib.sha256).hexdigest()
    return Fingerprint(algorithm="HMAC-SHA256", key_id=_FACTS_FINGERPRINT_KEY_ID, digest=digest)


def _deterministic_ids(
    *,
    rule_pack_id: uuid.UUID,
    sequence: int,
    facts_digest: str,
    effective_at: datetime,
) -> tuple[uuid.UUID, str]:
    """``public_id`` NOTE (Kimi gate round 1, 2026-07-19): this is a
    deterministic SHA-256 of otherwise-guessable inputs
    (``rule_pack_id``/``sequence``/``facts_digest``/``effective_at``) — it is
    NEVER, itself, an access-control capability or secret, even once the
    surrounding fingerprint stops being a placeholder. Whatever consumes
    ``public_id`` downstream (STEP-6c) must gate access via the
    session-exchange mechanism (spec §6.3), never via ``public_id`` secrecy.
    """
    seed = f"{rule_pack_id}:{sequence}:{facts_digest}:{effective_at.isoformat()}"
    decision_id = uuid.uuid5(_DECISION_ID_NAMESPACE, seed)
    public_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]
    return decision_id, public_id


@dataclass(frozen=True, slots=True)
class DecisionIdentity:
    """The three PURE, DERIVED identity values one ``Decision`` needs
    (``decision_id``, ``public_id``, ``facts_fingerprint``) — bundled so a
    real crypto-backed provider (STEP-6+, once ``crypto.py`` lands) can be
    injected into ``evaluate()`` as a single callable without this module
    needing to know its internals.
    """

    decision_id: uuid.UUID
    public_id: str
    facts_fingerprint: Fingerprint


#: ``evaluate()``'s injectable identity/fingerprint provider shape (gate
#: round 1 item 5, see module docstring). Default is
#: ``_placeholder_identity_provider`` below.
IdentityProvider = Callable[[ApplicantFacts, RulePackRef, datetime, Environment], DecisionIdentity]


def _placeholder_identity_provider(
    facts: ApplicantFacts,
    rule_pack_ref: RulePackRef,
    effective_at: datetime,
    environment: Environment,
) -> DecisionIdentity:
    """The DEFAULT ``IdentityProvider`` — NOT real crypto (see module
    docstring). Fail-closed guard (gate round 1 item 5, 2026-07-19): legal
    ONLY for ``environment=TEST`` rule packs. A STAGING/PRODUCTION pack must
    never receive a ``Decision`` whose identity/fingerprint came from this
    non-secret placeholder — raise loudly rather than silently producing a
    finished-looking, unsigned ``Decision``. Inject a real crypto-backed
    ``IdentityProvider`` via ``evaluate(..., identity_provider=...)`` for any
    non-TEST environment once ``crypto.py`` lands (STEP-6+).
    """
    if environment is not Environment.TEST:
        raise PlaceholderIdentityNotAllowedError(
            "the placeholder facts_fingerprint/decision_id/public_id provider "
            "is only legal for environment=TEST rule packs (fail-closed) — got "
            f"environment={environment.value!r}. Inject a real crypto-backed "
            "identity_provider (evaluate(..., identity_provider=...)) for "
            "STAGING/PRODUCTION."
        )
    facts_fingerprint = _facts_fingerprint(facts)
    decision_id, public_id = _deterministic_ids(
        rule_pack_id=rule_pack_ref.rule_pack_id,
        sequence=rule_pack_ref.sequence,
        facts_digest=facts_fingerprint.digest,
        effective_at=effective_at,
    )
    return DecisionIdentity(
        decision_id=decision_id, public_id=public_id, facts_fingerprint=facts_fingerprint
    )


def _period_contains(period: TimeRange, moment: datetime) -> bool:
    """Half-open ``[from_, to)`` containment — same semantics as
    ``compiler.py``'s private ``_valid_period_contains``. Used both for a
    product's own ``valid_period`` (product selection) and for a GLOBAL
    rule's ``source_rule.valid_period`` (the GLOBAL HUMAN_REVIEW pre-pass,
    gate round 1 item 3 / P0-C). Deliberately a tiny local copy rather than
    importing a private cross-module helper for a one-line check (see module
    docstring's divergence notes for the reuse policy this package otherwise
    follows).
    """
    return period.from_ <= moment and (period.to is None or moment < period.to)


def _assemble(
    *,
    state: DecisionState,
    decision_id: uuid.UUID,
    public_id: str,
    rule_pack_ref: RulePackRef,
    facts_fingerprint: Fingerprint,
    effective_at: datetime,
    observed_at: datetime,
    candidates: tuple[Candidate, ...] = (),
    missing_facts: tuple[FactPath, ...] = (),
    review_reasons: tuple[Reason, ...] = (),
    no_path_reasons: tuple[Reason, ...] = (),
    quotes: tuple[PriceQuote, ...] = (),
    notices: tuple[Reason, ...] = (),
    outage: Outage | None = None,
) -> Decision:
    """Build the final ``Decision``. ``evaluated_at`` is set to ``observed_at``
    (purity note — this function reads no independent wall-clock; see
    module docstring). Every ``Decision`` model validator still runs — a bug
    in this assembly surfaces as a ``ValidationError`` in tests, per the
    task's "treat a validator error as your own bug" rule.
    """
    return Decision(
        schema_version="1.0.0",
        decision_id=decision_id,
        public_id=public_id,
        state=state,
        effective_at=effective_at,
        observed_at=observed_at,
        evaluated_at=observed_at,
        rule_pack=rule_pack_ref,
        facts_fingerprint=facts_fingerprint,
        candidates=candidates,
        missing_facts=missing_facts,
        review_reasons=review_reasons,
        no_path_reasons=no_path_reasons,
        outage=outage,
        quotes=quotes,
        notices=notices,
        trace_sha256=None,
        decision_integrity=None,
    )


def _fallback_no_path_reason(
    products: Sequence[CompiledProduct], compiled_pack: CompiledRulePack
) -> Reason:
    """A genuinely NON-LEGAL, OPERATIONAL diagnostic reason — never a legal
    conclusion — emitted only when ``NO_SUPPORTED_PATH`` is reached with zero
    named EXCLUDE reasons collected (gate round 1 item 7, see module
    docstring).

    Framing (Kimi gate round 1 correction, 2026-07-19): reaching this
    fallback is **not** necessarily evidence of a pack-authoring/data gap —
    an applicant whose declared purposes genuinely no product covers is a
    perfectly normal, legitimate evaluation outcome. The fallback exists
    purely because ``Decision`` requires ``no_path_reasons`` non-empty for
    this state, and every REAL disqualifying/legal claim in this engine's
    design is instead expressed as a named ``HARD_FILTER`` rule (see the gold
    rule-pack fixtures) — this is what fires when there simply isn't one.

    Citations are still mandatory (task bar: zero uncited outputs) — derived
    from the evaluated products' own catalog ``source_refs`` when at least
    one product was evaluated, else the pack's own ``source_records``
    (``RulePackPayload.source_records`` has ``min_length=1``, so this is
    never itself empty).
    """
    if products:
        refs = _sorted_uuids(ref for p in products for ref in p.product.source_refs)
    else:
        refs = _sorted_uuids(
            record.source_record_id for record in compiled_pack.source_pack.payload.source_records
        )
    return Reason(
        code="OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES",
        rule_ids=(),
        source_refs=refs,
    )


# ---------------------------------------------------------------------------
# Global assembly (spec §4.3 ``evaluate`` + precedence table)
# ---------------------------------------------------------------------------


def evaluate(
    facts: ApplicantFacts,
    compiled_pack: CompiledRulePack,
    *,
    effective_at: datetime,
    observed_at: datetime,
    fact_registry: FactRegistry = DEFAULT_FACT_REGISTRY,
    identity_provider: IdentityProvider = _placeholder_identity_provider,
) -> Decision:
    """Assemble one ``Decision`` for ``facts`` against ``compiled_pack``.

    PURE: no I/O, no DB, no clock reads beyond ``effective_at``/``observed_at``.
    Same inputs always produce a byte-identical ``Decision`` (see module
    docstring for how ``decision_id``/``public_id``/``facts_fingerprint``
    stay deterministic via ``identity_provider``).

    Global precedence (frozen, ``enums.DecisionState``'s own docstring,
    highest first) — this function never produces
    ``TEMPORARILY_UNAVAILABLE`` (see module docstring):

    1. ``HUMAN_REVIEW_REQUIRED`` — a GLOBAL HUMAN_REVIEW rule is TRUE (the
       pre-pass below), or at least one product's proof is REVIEW.
    2. ``SUPPORTED_CANDIDATES`` — at least one product's proof is SUPPORTED.
    3. ``NEEDS_INPUT`` — ``intent.purposes`` itself is UNKNOWN (checked
       upfront below), or at least one product's proof is BLOCKED_UNKNOWN.
    4. ``NO_SUPPORTED_PATH`` — every applicable product is EXCLUDED or
       UNSUPPORTED (the floor).

    This function checks ``review`` before ``supported`` in the per-product
    outer assembly (gate round 1 item 2 / P0-B — an earlier draft had this
    inverted, matching the spec's own pseudocode literally but violating the
    frozen precedence table whenever a PRODUCTS-scoped review trigger
    coexisted with a different, genuinely SUPPORTED product).
    """
    rule_pack_ref = RulePackRef(
        rule_pack_id=compiled_pack.rule_pack_id,
        sequence=compiled_pack.sequence,
        version=compiled_pack.version,
        payload_sha256=compiled_pack.source_pack.payload_sha256,
    )
    identity = identity_provider(facts, rule_pack_ref, effective_at, compiled_pack.environment)

    snapshot = fact_registry.derive(facts, effective_at=effective_at)
    notices = _build_notices(snapshot, compiled_pack)

    def assemble(**kwargs: object) -> Decision:
        return _assemble(
            decision_id=identity.decision_id,
            public_id=identity.public_id,
            rule_pack_ref=rule_pack_ref,
            facts_fingerprint=identity.facts_fingerprint,
            effective_at=effective_at,
            observed_at=observed_at,
            notices=notices,
            **kwargs,  # type: ignore[arg-type]
        )

    # --- GLOBAL HUMAN_REVIEW pre-pass (gate round 1 item 3 / P0-C, see
    # module docstring) — evaluated ONCE, here, before purpose extraction
    # and before the per-product loop. `rules_for()` only ever surfaces a
    # GLOBAL rule when called FOR a specific product, so this cannot be
    # expressed as "just call rules_for" without a product to loop over —
    # the three reachable counterexamples this fixes (unknown purposes,
    # zero active products, a GLOBAL hard-filter excluding every product
    # first) are covered by `test_evaluator_gate_round1.py`. A TRUE result
    # here wins immediately and unconditionally (frozen precedence:
    # HUMAN_REVIEW_REQUIRED ranks above every other state this function
    # produces). This does not replace the per-product HUMAN_REVIEW stage —
    # PRODUCTS-scoped review rules, and a GLOBAL rule that resolves UNKNOWN
    # under `on_unknown` policies other than HUMAN_REVIEW, still flow
    # through `evaluate_product()` below exactly as before.
    #
    # Gate round 2 (2026-07-20) — P0-R1: an UNKNOWN result here used to be
    # silently dropped, so a GLOBAL review rule tagged `on_unknown=
    # HUMAN_REVIEW` never escalated when its own condition could not be
    # determined — precisely the case `on_unknown=HUMAN_REVIEW` exists to
    # cover ("if we can't tell, a human must look"). Fixed by ALSO
    # collecting UNKNOWN entries whose rule opts into HUMAN_REVIEW, exactly
    # mirroring the per-product `_partition_unknowns_by_policy` split.
    global_review_rules = sorted(
        (
            rule
            for rule in compiled_pack.rules
            if rule.scope is RuleScope.GLOBAL
            and rule.stage is RuleStage.HUMAN_REVIEW
            and _period_contains(rule.source_rule.valid_period, effective_at)
        ),
        key=lambda rule: (rule.priority, rule.rule_id),
    )
    global_review_results = _evaluate_stage(global_review_rules, snapshot)
    global_true_entries = tuple(
        (rule, result) for rule, result in global_review_results if result.truth is TruthValue.TRUE
    )
    global_unknown_review_entries = tuple(
        (rule, result)
        for rule, result in global_review_results
        if result.truth is TruthValue.UNKNOWN and rule.on_unknown is OnUnknownAction.HUMAN_REVIEW
    )
    if global_true_entries or global_unknown_review_entries:
        review_reasons = _dedupe_reasons(
            _true_reasons(global_true_entries) + _unknown_reasons(global_unknown_review_entries)
        )
        return assemble(state=DecisionState.HUMAN_REVIEW_REQUIRED, review_reasons=review_reasons)

    purposes_fact = snapshot.values.get(FactPath.INTENT_PURPOSES)
    if purposes_fact is None or isinstance(purposes_fact, UnknownFact):
        # `evaluate_product` needs a concrete `purposes` set (spec §4.3:
        # `purposes=facts.require_known_set("intent.purposes")`) — with no
        # declared purpose at all, no per-product coverage test is even
        # meaningful, so we short-circuit here rather than run every
        # product's stage loop against an undefined purpose set.
        return assemble(
            state=DecisionState.NEEDS_INPUT,
            missing_facts=(FactPath.INTENT_PURPOSES,),
        )
    purposes: frozenset[str] = frozenset(purposes_fact.value)  # type: ignore[union-attr]

    products = sorted(
        (
            compiled_product
            for compiled_product in compiled_pack.products
            if compiled_product.product.status is VisaProductStatus.ACTIVE
            and _period_contains(compiled_product.product.valid_period, effective_at)
        ),
        key=lambda compiled_product: (
            compiled_product.product_code,
            str(compiled_product.product_version_id),
        ),
    )

    proofs = [
        evaluate_product(
            product=compiled_product,
            rules=compiled_pack.rules_for(compiled_product, effective_at=effective_at),
            facts=snapshot,
            purposes=purposes,
            fact_registry=fact_registry,
        )
        for compiled_product in products
    ]

    # P0-B fix (gate round 1 item 2, see module docstring): REVIEW checked
    # before SUPPORTED — frozen precedence ranks HUMAN_REVIEW_REQUIRED above
    # SUPPORTED_CANDIDATES unconditionally, not only when the review trigger
    # happens to be GLOBAL (GLOBAL review triggers are already handled above
    # and never reach this point when TRUE).
    review = [proof for proof in proofs if proof.status is ProductProofStatus.REVIEW]
    if review:
        review_reasons = _dedupe_reasons(reason for proof in review for reason in proof.reasons)
        return assemble(state=DecisionState.HUMAN_REVIEW_REQUIRED, review_reasons=review_reasons)

    supported = [proof for proof in proofs if proof.status is ProductProofStatus.SUPPORTED]
    if supported:
        candidates = _rank_supported(supported, snapshot, compiled_pack, effective_at=effective_at)
        return assemble(state=DecisionState.SUPPORTED_CANDIDATES, candidates=candidates)

    blocked = [proof for proof in proofs if proof.status is ProductProofStatus.BLOCKED_UNKNOWN]
    if blocked:
        # P1 fix (gate round 1 item 6, see module docstring): the
        # deterministic MINIMAL viable set — the single BLOCKED_UNKNOWN
        # proof with the fewest missing_facts — rather than the union
        # across every blocked product. `min` ties break on first-seen
        # order, which is already the deterministic
        # (product_code, product_version_id) order `products`/`proofs` were
        # built in. Each blocked proof's own missing_facts is always
        # non-empty by construction (it derives from >=1 UNKNOWN rule), so
        # this can never produce an empty set.
        smallest = min(blocked, key=lambda proof: len(proof.missing_facts))
        missing = tuple(sorted(smallest.missing_facts, key=lambda path: path.value))
        return assemble(state=DecisionState.NEEDS_INPUT, missing_facts=missing)

    excluded = [proof for proof in proofs if proof.status is ProductProofStatus.EXCLUDED]
    no_path_reasons = _dedupe_reasons(reason for proof in excluded for reason in proof.reasons)
    if not no_path_reasons:
        no_path_reasons = (_fallback_no_path_reason(products, compiled_pack),)
    return assemble(state=DecisionState.NO_SUPPORTED_PATH, no_path_reasons=no_path_reasons)
