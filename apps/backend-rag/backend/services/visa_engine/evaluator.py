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

# Divergences from the spec text (recorded here + in the PR body)

1. **Signature/return type.** Spec §1's ``evaluator.py`` snippet has
   ``evaluate(pack, facts, *, context: EvaluationContext) -> DecisionDraft``.
   Neither ``EvaluationContext`` nor ``DecisionDraft`` exists anywhere in this
   package (both are explicitly "not started, deferred" per
   ``visa_engine/__init__.py``'s PR-scope map) — the PR5 task brief instead
   specifies ``evaluate(facts, compiled_pack, *, effective_at, observed_at,
   fingerprint_hmac_key, fingerprint_key_id) -> Decision`` directly,
   skipping the draft/context indirection while keeping key ownership at the
   caller boundary.
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
3. **GLOBAL ``HUMAN_REVIEW`` rules use the spec §4.3 pre-pass.** They are
   evaluated before purpose completeness and product selection so an
   independently true global safety trigger cannot be masked by a product's
   earlier ``HARD_FILTER`` stage, an unknown ``intent.purposes`` fact, or a
   pack with no active products. ``rules_for()`` still includes GLOBAL rules
   in each product for UNKNOWN propagation, but a definitely TRUE global
   review trigger always short-circuits at the global precedence boundary.
4. **``TEMPORARILY_UNAVAILABLE`` is never produced by this function.** Its
   two triggers per spec §4.3 ("absent/unverifiable pack, compilation
   failure" and "persistence-required dependency failure") are both
   *upstream* of this pure function's precondition: it only ever runs
   against an already-``build_compiled_pack``-validated
   ``CompiledRulePack`` (compilation already succeeded by construction) and
   never calls out to persistence/pricing (``repository.py``/``pricing.py``
   are undone, PR4+/later scope) — ``quotes`` is always ``()``. Resolving
   "no active pack" is the caller's (repository/service layer) job, done
   *before* ``evaluate()`` is ever invoked.
5. **The caller supplies the HMAC key and key id.** The evaluator stays pure
   and deterministic, but it never invents or embeds a repository-visible
   signing key. ``decision_id``/``public_id`` are derived (UUIDv5 / truncated
   SHA-256 hex) from the assessment identity plus the rule-pack/facts inputs;
   distinct assessments with identical answers therefore cannot collide.
6. **"minimal_missing_fact_set" (spec §4.3) is implemented as the UNION of
   every ``BLOCKED_UNKNOWN`` proof's ``missing_facts``, not an
   intersection.** An intersection could legitimately be empty when two
   blocked products are blocked by disjoint fact sets, which would violate
   ``Decision``'s own invariant ("state=NEEDS_INPUT requires at least one
   missing fact") — asking for one extra fact is never a wrong legal
   answer, so the union is the only choice that is safe in general.
7. **A synthetic, clearly-labeled fallback ``Reason`` is emitted for
   ``NO_SUPPORTED_PATH`` when no product carried a named ``EXCLUDE``
   reason** (e.g. an empty pack, or every product merely ``UNSUPPORTED``
   with no named disqualifying rule) — ``Decision`` requires
   ``no_path_reasons`` to be non-empty for this state, and every real
   disqualifying/legal claim in this engine's design is expressed as a
   named ``HARD_FILTER`` rule (see the gold rule-pack fixtures), so this
   fallback only ever fires on a pack-authoring/data gap, never as a
   silent legal claim. It carries empty ``rule_ids``/``source_refs``
   (nothing to cite — the gap itself is the finding) and a code
   (``NO_PRODUCT_SUPPORTS_DECLARED_PURPOSES``) namespaced so a caller can
   tell it apart from a real, cited legal reason at a glance.

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
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from backend.services.visa_engine import ast as ast_module
from backend.services.visa_engine.ast import ConditionResult, FactSnapshot, UnknownFact
from backend.services.visa_engine.compiler import CompiledProduct, CompiledRule, CompiledRulePack
from backend.services.visa_engine.enums import (
    DecisionState,
    FactPath,
    OnUnknownAction,
    RuleScope,
    RuleStage,
    TruthValue,
    VisaProductStatus,
)
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
    #: Populated for EXCLUDED (exclusion reasons) and REVIEW (review reasons).
    reasons: tuple[Reason, ...] = ()
    #: Populated for BLOCKED_UNKNOWN — applicant-collected paths only (derived
    #: paths already resolved to their dependency per ``_underlying_applicant_facts``).
    missing_facts: frozenset[FactPath] = frozenset()
    #: Populated for SUPPORTED — every TRUE ELIGIBILITY (SUPPORT-effect) rule.
    support_rules: tuple[CompiledRule, ...] = ()
    #: Populated for SUPPORTED — union of ``support_rules``' covered purposes.
    covered_purposes: frozenset[str] = frozenset()
    #: Populated for UNSUPPORTED — the declared purposes no TRUE rule covered.
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
    the rule author says *could* still change the outcome once resolved.
    """
    return tuple(
        (rule, result)
        for rule, result in entries
        if result.truth is TruthValue.UNKNOWN and rule.on_unknown is not OnUnknownAction.NO_EFFECT
    )


def _sorted_uuids(values: Iterable[uuid.UUID]) -> tuple[uuid.UUID, ...]:
    return tuple(sorted(set(values), key=str))


def _reason_from_rule(rule: CompiledRule) -> Reason:
    """Build one ``Reason`` from a rule whose effect fired (EXCLUDE or
    REQUIRE_REVIEW) — citations propagated verbatim from the rule that fired.
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
    """
    by_stage = _rules_by_stage(rules)

    hard_results = _evaluate_stage(by_stage.get(RuleStage.HARD_FILTER, ()), facts)
    if any(result.truth is TruthValue.TRUE for _, result in hard_results):
        return ProductProof(
            product=product,
            status=ProductProofStatus.EXCLUDED,
            reasons=_true_reasons(hard_results),
        )
    hard_unknowns = _safety_unknowns(hard_results)

    review_results = _evaluate_stage(by_stage.get(RuleStage.HUMAN_REVIEW, ()), facts)
    if any(result.truth is TruthValue.TRUE for _, result in review_results):
        return ProductProof(
            product=product,
            status=ProductProofStatus.REVIEW,
            reasons=_true_reasons(review_results),
        )
    review_unknowns = _safety_unknowns(review_results)

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
    support_unknowns = _safety_unknowns(support_results)

    if hard_unknowns or review_unknowns:
        missing = _underlying_applicant_facts(hard_unknowns + review_unknowns, fact_registry)
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
    unknown_coverage = (
        frozenset[str]().union(
            *(frozenset(rule.effect.covered_purposes) for rule, _ in support_unknowns)  # type: ignore[union-attr]
        )
        if support_unknowns
        else frozenset()
    )
    if missing_purposes <= unknown_coverage:
        missing = _underlying_applicant_facts(support_unknowns, fact_registry)
        return ProductProof(
            product=product,
            status=ProductProofStatus.BLOCKED_UNKNOWN,
            missing_facts=missing,
        )

    return ProductProof(
        product=product,
        status=ProductProofStatus.UNSUPPORTED,
        missing_purposes=missing_purposes,
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
# Deterministic identity + facts fingerprint (divergence #5 — see module docstring)
# ---------------------------------------------------------------------------

#: Fixed, arbitrary namespace UUID for deriving a deterministic ``decision_id``
#: via UUIDv5 — never treat as a secret; its only job is to keep the derived
#: UUID out of the random (v4) namespace so it is visibly "derived, not random".
_DECISION_ID_NAMESPACE = uuid.UUID("2f6a8b2e-6a3b-4b8e-9b0a-6f1a8b2e6a3b")


def _facts_fingerprint(facts: ApplicantFacts, *, hmac_key: bytes, key_id: str) -> Fingerprint:
    if len(hmac_key) < 32:
        raise ValueError("facts fingerprint HMAC key must be at least 32 bytes")
    canonical = canonical_fact_payload(facts)
    payload_bytes = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(hmac_key, payload_bytes, hashlib.sha256).hexdigest()
    return Fingerprint(algorithm="HMAC-SHA256", key_id=key_id, digest=digest)


def _deterministic_ids(
    *,
    assessment_id: uuid.UUID,
    rule_pack_id: uuid.UUID,
    sequence: int,
    facts_digest: str,
    effective_at: datetime,
) -> tuple[uuid.UUID, str]:
    seed = f"{assessment_id}:{rule_pack_id}:{sequence}:{facts_digest}:{effective_at.isoformat()}"
    decision_id = uuid.uuid5(_DECISION_ID_NAMESPACE, seed)
    public_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:20]
    return decision_id, public_id


def _product_is_effective(period: TimeRange, moment: datetime) -> bool:
    """Half-open ``[from_, to)`` containment — same semantics as
    ``compiler.py``'s private ``_valid_period_contains`` (rules), applied
    here to a product's own ``valid_period``. Deliberately a tiny local copy
    rather than importing a private cross-module helper for a one-line
    check (see module docstring's divergence notes for the reuse policy this
    package otherwise follows).
    """
    return period.from_ <= moment and (period.to is None or moment < period.to)


def _global_review_reasons(
    compiled_pack: CompiledRulePack,
    facts: FactSnapshot,
    *,
    effective_at: datetime,
) -> tuple[Reason, ...]:
    """Evaluate in-force GLOBAL review rules before any product stage loop."""
    rules = tuple(
        sorted(
            (
                rule
                for rule in compiled_pack.rules
                if rule.scope is RuleScope.GLOBAL
                and rule.stage is RuleStage.HUMAN_REVIEW
                and _product_is_effective(rule.source_rule.valid_period, effective_at)
            ),
            key=lambda rule: (rule.priority, rule.rule_id),
        )
    )
    return _dedupe_reasons(_true_reasons(_evaluate_stage(rules, facts)))


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
    (divergence #5/purity note — this function reads no independent
    wall-clock; see module docstring). Every ``Decision`` model validator
    still runs — a bug in this assembly surfaces as a ``ValidationError`` in
    tests, per the task's "treat a validator error as your own bug" rule.
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


#: Fallback reason (divergence #7 — see module docstring) when NO_SUPPORTED_PATH
#: is reached with zero named EXCLUDE reasons collected (empty pack / a pack
#: with products but none of them ever excluded by name).
_NO_PRODUCT_SUPPORTS_DECLARED_PURPOSES = Reason(
    code="NO_PRODUCT_SUPPORTS_DECLARED_PURPOSES",
    rule_ids=(),
    source_refs=(),
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
    fingerprint_hmac_key: bytes,
    fingerprint_key_id: str,
    fact_registry: FactRegistry = DEFAULT_FACT_REGISTRY,
) -> Decision:
    """Assemble one ``Decision`` for ``facts`` against ``compiled_pack``.

    PURE: no I/O, no DB, no clock reads beyond ``effective_at``/``observed_at``.
    Same inputs always produce a byte-identical ``Decision`` (see module
    docstring divergence #5 for how ``decision_id``/``public_id``/
    ``facts_fingerprint`` stay deterministic).

    Global precedence (spec §4.3, highest first) — this function never
    produces ``TEMPORARILY_UNAVAILABLE`` (divergence #4):

    1. ``HUMAN_REVIEW_REQUIRED`` — at least one product's proof is REVIEW.
    2. ``SUPPORTED_CANDIDATES`` — at least one product's proof is SUPPORTED.
    3. ``NEEDS_INPUT`` — at least one product's proof is BLOCKED_UNKNOWN
       (or ``intent.purposes`` itself is UNKNOWN, checked upfront below).
    4. ``NO_SUPPORTED_PATH`` — every applicable product is EXCLUDED or
       UNSUPPORTED.

    The prose precedence table is the safety contract when it conflicts with
    the pseudocode ordering: any independently true applicable review trigger
    wins over a supported proof from another product.
    """
    rule_pack_ref = RulePackRef(
        rule_pack_id=compiled_pack.rule_pack_id,
        sequence=compiled_pack.sequence,
        version=compiled_pack.version,
        payload_sha256=compiled_pack.source_pack.payload_sha256,
    )
    facts_fingerprint = _facts_fingerprint(
        facts,
        hmac_key=fingerprint_hmac_key,
        key_id=fingerprint_key_id,
    )
    decision_id, public_id = _deterministic_ids(
        assessment_id=facts.assessment_id,
        rule_pack_id=compiled_pack.rule_pack_id,
        sequence=compiled_pack.sequence,
        facts_digest=facts_fingerprint.digest,
        effective_at=effective_at,
    )

    snapshot = fact_registry.derive(facts, effective_at=effective_at)
    notices = _build_notices(snapshot, compiled_pack)

    def assemble(**kwargs: object) -> Decision:
        return _assemble(
            decision_id=decision_id,
            public_id=public_id,
            rule_pack_ref=rule_pack_ref,
            facts_fingerprint=facts_fingerprint,
            effective_at=effective_at,
            observed_at=observed_at,
            notices=notices,
            **kwargs,  # type: ignore[arg-type]
        )

    global_review_reasons = _global_review_reasons(
        compiled_pack,
        snapshot,
        effective_at=effective_at,
    )
    if global_review_reasons:
        return assemble(
            state=DecisionState.HUMAN_REVIEW_REQUIRED,
            review_reasons=global_review_reasons,
        )

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
            and _product_is_effective(compiled_product.product.valid_period, effective_at)
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
        # Divergence #6 — union, not intersection (see module docstring).
        missing = frozenset[FactPath]().union(*(proof.missing_facts for proof in blocked))
        return assemble(
            state=DecisionState.NEEDS_INPUT,
            missing_facts=tuple(sorted(missing, key=lambda path: path.value)),
        )

    excluded = [proof for proof in proofs if proof.status is ProductProofStatus.EXCLUDED]
    no_path_reasons = _dedupe_reasons(reason for proof in excluded for reason in proof.reasons)
    if not no_path_reasons:
        # Divergence #7 — see module docstring.
        no_path_reasons = (_NO_PRODUCT_SUPPORTS_DECLARED_PURPOSES,)
    return assemble(state=DecisionState.NO_SUPPORTED_PATH, no_path_reasons=no_path_reasons)
