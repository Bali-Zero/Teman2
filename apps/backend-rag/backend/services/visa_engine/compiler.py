"""Compiles a schema-valid ``RulePack`` into an evaluator-ready structure.

**PR1 signature deviation (approved by orchestrator):** the spec's
``compile_rule_pack(verified: VerifiedRulePack, ...)`` takes a
``VerifiedRulePack`` produced by ``bundle.py``'s Ed25519 signature
verification. ``bundle.py`` is out of PR1 scope (no crypto in this PR), so
PR1's ``compile_rule_pack`` takes the schema-validated ``RulePack`` model
directly. PR2 will re-introduce the ``VerifiedRulePack`` seam in front of
this same compiler.

Enforces (PR1 baseline + fix-round F1-F5/F8):

* max AST depth 12, max condition nodes 256 (per rule's ``when`` tree)
* max 4096 rules, max 256 products (redundant with the Pydantic
  ``max_length`` on ``RulePackPayload.rules``/``products`` — kept here too
  as a defense-in-depth re-check independent of how ``pack`` was built)
* every fact path referenced by a rule's ``when`` must be registered in the
  supplied ``fact_registry`` — a registry is an injected parameter, not a
  hardcoded singleton (see ``fact_registry.py``), so tests can construct a
  deliberately incomplete registry to exercise this path
* a ``RANKING``-stage rule may reference only commercial-only facts
  (``FactSpec.commercial_only``); referencing a legal fact is rejected
* **F3**: mirrored the other way — a ``HARD_FILTER``/``ELIGIBILITY``/
  ``HUMAN_REVIEW`` rule may never reference a commercial-only fact (a
  commercial budget must never influence a legal-eligibility decision,
  binding decision Sec 0.3)
* **F1**: every condition literal's Python type must match the referenced
  fact's ``FactSpec.value_type`` exactly (``bool`` only on a bool fact,
  ``int`` only on an int fact, ``str`` only on a str fact; a ``date``-typed
  fact's literal must be a valid ISO-8601 date string). ``lt``/``lte``/
  ``gt``/``gte``/``between`` are additionally forbidden on bool facts.
* **F2**: ``intersects``/``contains_all`` may reference only a set-typed
  (``frozenset``) fact; every scalar comparison op may reference only a
  scalar-typed fact — no cross-shape condition may ever reach
  ``evaluate_condition``.
* **F4**: pack integrity — no duplicate ``rule_id``/``product_version_id``/
  ``product_code``/``source_record_id`` within the payload, no
  ``Rule.product_version_ids`` or ``*.source_refs`` UUID that fails to
  resolve to a real product/source record in the same payload.
* **F5**: the protected header's ``environment`` must equal the payload's
  own ``environment``.
* **F8**: when a rule declares ``required_facts``, it must equal
  ``collect_fact_paths(when)`` exactly (no silent substitution).

Still intentionally deferred beyond this fix round: UTF/NFC normalization,
``requested_purposes ⊆ covered_purposes`` — see the PR1/fix-round implementer
reports.

Pure module: no I/O.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from backend.services.visa_engine.ast import (
    AllCondition,
    AnyCondition,
    BetweenCondition,
    Condition,
    ContainsAllCondition,
    EqCondition,
    GtCondition,
    GteCondition,
    InCondition,
    IntersectsCondition,
    KnownCondition,
    LtCondition,
    LteCondition,
    NeqCondition,
    NotCondition,
    NotInCondition,
    UnknownCondition,
    collect_fact_paths,
)
from backend.services.visa_engine.enums import RuleStage
from backend.services.visa_engine.errors import FactValidationError, RulePackCompilationError
from backend.services.visa_engine.fact_registry import FactRegistry, FactSpec
from backend.services.visa_engine.models import Rule, RuleEffect, RulePack, VisaProductVersion

if TYPE_CHECKING:  # pragma: no cover - typing only
    from backend.services.visa_engine.models import RulePackPayload

MAX_AST_DEPTH = 12
MAX_CONDITION_NODES = 256
MAX_RULES = 4096
MAX_PRODUCTS = 256

# F2's operator/fact-shape matrix.
_SET_CONDITIONS = (IntersectsCondition, ContainsAllCondition)
_ORDERING_CONDITIONS = (LtCondition, LteCondition, GtCondition, GteCondition, BetweenCondition)
_SCALAR_LEAF_CONDITIONS = (
    EqCondition,
    NeqCondition,
    LtCondition,
    LteCondition,
    GtCondition,
    GteCondition,
    InCondition,
    NotInCondition,
    BetweenCondition,
)

# F3: legal-eligibility stages that must never reference a commercial-only
# fact — the mirror image of "RANKING may reference only commercial facts".
_LEGAL_STAGES_FORBIDDING_COMMERCIAL = (
    RuleStage.HARD_FILTER,
    RuleStage.ELIGIBILITY,
    RuleStage.HUMAN_REVIEW,
)


def _condition_depth(condition: Condition) -> int:
    if isinstance(condition, (AllCondition, AnyCondition)):
        return 1 + max((_condition_depth(child) for child in condition.args), default=0)
    if isinstance(condition, NotCondition):
        return 1 + _condition_depth(condition.arg)
    return 1


def _condition_node_count(condition: Condition) -> int:
    if isinstance(condition, (AllCondition, AnyCondition)):
        return 1 + sum(_condition_node_count(child) for child in condition.args)
    if isinstance(condition, NotCondition):
        return 1 + _condition_node_count(condition.arg)
    return 1


@dataclass(frozen=True)
class CompiledRule:
    """A ``Rule`` pre-analyzed for the evaluator (PR2+): AST depth/node-count
    precomputed once, ``required_facts`` resolved to the AST's *actual*
    referenced fact paths (``collect_fact_paths(when)``)."""

    rule_id: str
    stage: RuleStage
    scope: str
    product_version_ids: frozenset[UUID]
    priority: int
    when: Condition
    effect: RuleEffect
    on_unknown: str
    referenced_facts: frozenset[str]
    source_refs: frozenset[UUID]
    explanation_key: str
    safety_critical: bool
    ast_depth: int
    ast_node_count: int
    source_rule: Rule


@dataclass(frozen=True)
class CompiledProduct:
    """A ``VisaProductVersion`` alongside its identity for evaluator lookups."""

    product_version_id: UUID
    product_code: str
    product: VisaProductVersion


@dataclass(frozen=True)
class CompiledRulePack:
    """The evaluator-ready compiled form of a signed ``RulePack``."""

    rule_pack_id: UUID
    sequence: int
    version: str
    environment: str
    products: tuple[CompiledProduct, ...]
    rules: tuple[CompiledRule, ...]
    source_pack: RulePack

    def rules_for(self, product: CompiledProduct) -> tuple[CompiledRule, ...]:
        """``GLOBAL`` rules + ``PRODUCTS``-scoped rules naming this product,
        ordered by ``(stage.order, priority, rule_id)`` for deterministic
        evaluation (matches the evaluator's ``pack.rules_for(product)``
        usage, §4.2). ``stage.order`` (F13) is the SEMANTIC processing
        order (``HARD_FILTER`` -> ``HUMAN_REVIEW`` -> ``ELIGIBILITY`` ->
        ``RANKING``), not the alphabetical order of ``stage.value``."""

        selected = [
            rule
            for rule in self.rules
            if rule.scope == "GLOBAL" or product.product_version_id in rule.product_version_ids
        ]
        return tuple(
            sorted(selected, key=lambda rule: (rule.stage.order, rule.priority, rule.rule_id))
        )


def compile_rule_pack(pack: RulePack, *, fact_registry: FactRegistry) -> CompiledRulePack:
    """Compile a schema-valid ``RulePack`` into a ``CompiledRulePack``.

    Always raises :class:`RulePackCompilationError` (never a bare
    :class:`~backend.services.visa_engine.errors.FactValidationError` or other
    exception) with a precise, rule-scoped message on any invariant
    violation.
    """

    payload = pack.payload

    if pack.protected.environment != payload.environment:
        # F5: header/payload environment must agree before this pack is
        # trusted to compile at all.
        raise RulePackCompilationError(
            f"protected header environment {pack.protected.environment!r} does not "
            f"match payload environment {payload.environment!r}"
        )

    if len(payload.products) > MAX_PRODUCTS:
        raise RulePackCompilationError(
            f"rule pack has {len(payload.products)} products, exceeding the "
            f"maximum of {MAX_PRODUCTS}"
        )
    if len(payload.rules) > MAX_RULES:
        raise RulePackCompilationError(
            f"rule pack has {len(payload.rules)} rules, exceeding the maximum of {MAX_RULES}"
        )

    _check_pack_integrity(payload)

    compiled_rules = tuple(
        _compile_rule(rule, fact_registry=fact_registry) for rule in payload.rules
    )
    compiled_products = tuple(
        CompiledProduct(
            product_version_id=product.product_version_id,
            product_code=product.product_code,
            product=product,
        )
        for product in payload.products
    )

    return CompiledRulePack(
        rule_pack_id=payload.rule_pack_id,
        sequence=payload.sequence,
        version=payload.version,
        environment=payload.environment,
        products=compiled_products,
        rules=compiled_rules,
        source_pack=pack,
    )


def _reject_duplicates(values: list[object], *, kind: str) -> None:
    """F4: raise if ``values`` contains any repeated element."""

    seen: set[object] = set()
    dupes: set[object] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    if dupes:
        rendered = sorted(str(d) for d in dupes)
        raise RulePackCompilationError(f"rule pack has duplicate {kind} value(s): {rendered!r}")


def _check_pack_integrity(payload: RulePackPayload) -> None:
    """F4: dedup rule_id/product_version_id/product_code/source_record_id,
    and reject any Rule/VisaProductVersion reference that doesn't resolve to
    a real product/source record within this same payload."""

    _reject_duplicates([r.rule_id for r in payload.rules], kind="rule_id")

    product_version_ids = [p.product_version_id for p in payload.products]
    _reject_duplicates(list(product_version_ids), kind="product_version_id")

    product_codes = [p.product_code for p in payload.products]
    _reject_duplicates(list(product_codes), kind="product_code")

    source_record_ids = [s.source_record_id for s in payload.source_records]
    _reject_duplicates(list(source_record_ids), kind="source_record_id")

    known_product_ids = frozenset(product_version_ids)
    known_source_ids = frozenset(source_record_ids)

    for rule in payload.rules:
        if rule.product_version_ids:
            dangling_products = [
                pid for pid in rule.product_version_ids if pid not in known_product_ids
            ]
            if dangling_products:
                raise RulePackCompilationError(
                    f"rule {rule.rule_id!r}: product_version_ids references unknown "
                    f"product(s) {sorted(str(p) for p in dangling_products)!r}"
                )

        dangling_rule_sources = [sid for sid in rule.source_refs if sid not in known_source_ids]
        if dangling_rule_sources:
            raise RulePackCompilationError(
                f"rule {rule.rule_id!r}: source_refs references unknown source "
                f"record(s) {sorted(str(s) for s in dangling_rule_sources)!r}"
            )

    for product in payload.products:
        dangling_product_sources = [
            sid for sid in product.source_refs if sid not in known_source_ids
        ]
        if dangling_product_sources:
            raise RulePackCompilationError(
                f"product {product.product_version_id}: source_refs references "
                f"unknown source record(s) "
                f"{sorted(str(s) for s in dangling_product_sources)!r}"
            )


def _resolve_spec(path: str, *, fact_registry: FactRegistry, rule_id: str) -> FactSpec:
    try:
        return fact_registry.spec(path)
    except FactValidationError as exc:
        raise RulePackCompilationError(
            f"rule {rule_id!r}: references unregistered fact path {path!r}"
        ) from exc


def _condition_literals(condition: Condition) -> tuple[object, ...]:
    """The literal(s) a scalar-leaf condition compares its fact against."""

    if isinstance(
        condition, (EqCondition, NeqCondition, LtCondition, LteCondition, GtCondition, GteCondition)
    ):
        return (condition.value,)
    if isinstance(condition, (InCondition, NotInCondition)):
        return tuple(condition.values)
    if isinstance(condition, BetweenCondition):
        return (condition.lower, condition.upper)
    raise TypeError(f"unhandled scalar condition type: {type(condition)!r}")  # pragma: no cover


_CANONICAL_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
"""R2: ``date.fromisoformat`` (Python 3.11) also accepts non-canonical forms
— compact ``YYYYMMDD`` and ISO week-dates ``YYYY-Www-D`` — that then compare
LEXICOGRAPHICALLY WRONG against the canonical ``YYYY-MM-DD`` strings stored
in ``FactSnapshot``. Every date-typed-fact literal must match this pattern
in addition to parsing successfully."""

# R1: every currently-registered set-typed (frozenset) fact stores
# frozenset[str] elements (country codes, purpose/violation enum values —
# see fact_registry.py's module docstring). `intersects`/`contains_all`
# `values` members must be validated against that element type too, not
# just the container shape.
_SET_FACT_ELEMENT_TYPE = str


def _check_literal_type(literal: object, spec: FactSpec, *, path: str, rule_id: str) -> None:
    """F1/R2: the literal's exact Python type must match ``spec.value_type``.

    Uses ``type(x) is T`` rather than ``isinstance`` throughout — ``bool`` is
    an ``int`` subclass in Python, so ``isinstance(True, int)`` is ``True``
    and would silently let a boolean literal slip through an int-fact check.
    """

    value_type = spec.value_type

    if value_type is date:
        if type(literal) is not str or not _CANONICAL_ISO_DATE_RE.match(literal):
            raise RulePackCompilationError(
                f"rule {rule_id!r}: fact {path!r} is date-typed; literal {literal!r} "
                "must be a canonical ISO-8601 date string (YYYY-MM-DD) — compact "
                "(YYYYMMDD) and week-date (YYYY-Www-D) forms are rejected even "
                "though `date.fromisoformat` accepts them, because they compare "
                "lexicographically wrong against canonical snapshot values"
            )
        try:
            date.fromisoformat(literal)
        except ValueError as exc:
            raise RulePackCompilationError(
                f"rule {rule_id!r}: fact {path!r} literal {literal!r} is not a valid "
                "ISO-8601 date string"
            ) from exc
        return

    if type(literal) is not value_type:
        raise RulePackCompilationError(
            f"rule {rule_id!r}: fact {path!r} has value_type={value_type.__name__!r}, "
            f"but literal {literal!r} is of type {type(literal).__name__!r}"
        )


def _check_set_member_types(
    values: tuple[object, ...], *, path: str, rule_id: str, op: str
) -> None:
    """R1: every member of an ``intersects``/``contains_all`` ``values``
    tuple must match the set fact's element type (``str`` for every
    currently-registered frozenset fact) — the container-shape check alone
    (F2) never inspected individual members."""

    for member in values:
        if type(member) is not _SET_FACT_ELEMENT_TYPE:
            raise RulePackCompilationError(
                f"rule {rule_id!r}: {op!r} on fact {path!r} has member "
                f"{member!r} of type {type(member).__name__!r}, expected "
                f"{_SET_FACT_ELEMENT_TYPE.__name__!r}"
            )


def _fact_path_str(fact: object) -> str:
    return str(fact.value) if hasattr(fact, "value") else str(fact)


def _validate_condition_tree(
    condition: Condition, *, fact_registry: FactRegistry, rule: Rule
) -> None:
    """Recursively enforce F1 (literal types), F2 (operator/fact-shape
    matrix), and the RANKING/legal-stage commercial-fact bans (existing +
    F3) over every leaf of ``condition``."""

    if isinstance(condition, (AllCondition, AnyCondition)):
        for child in condition.args:
            _validate_condition_tree(child, fact_registry=fact_registry, rule=rule)
        return
    if isinstance(condition, NotCondition):
        _validate_condition_tree(condition.arg, fact_registry=fact_registry, rule=rule)
        return

    path = _fact_path_str(condition.fact)
    spec = _resolve_spec(path, fact_registry=fact_registry, rule_id=rule.rule_id)

    if rule.stage == RuleStage.RANKING and not spec.commercial_only:
        raise RulePackCompilationError(
            f"rule {rule.rule_id!r}: RANKING-stage rule references legal "
            f"fact {path!r} (commercial_only=False); RANKING rules may "
            f"reference only commercial/preference facts"
        )
    if rule.stage in _LEGAL_STAGES_FORBIDDING_COMMERCIAL and spec.commercial_only:
        raise RulePackCompilationError(
            f"rule {rule.rule_id!r}: {rule.stage.value}-stage rule references "
            f"commercial-only fact {path!r}; legal-eligibility stages "
            "(HARD_FILTER/ELIGIBILITY/HUMAN_REVIEW) may never reference a "
            "commercial fact (binding decision Sec 0.3)"
        )

    if isinstance(condition, (KnownCondition, UnknownCondition)):
        # Presence checks are valid against any fact shape.
        return

    if isinstance(condition, _SET_CONDITIONS):
        if spec.value_type is not frozenset:
            raise RulePackCompilationError(
                f"rule {rule.rule_id!r}: {condition.op!r} requires a set-typed fact, "
                f"but {path!r} has value_type={spec.value_type.__name__!r}"
            )
        _check_set_member_types(condition.values, path=path, rule_id=rule.rule_id, op=condition.op)
        return

    if not isinstance(condition, _SCALAR_LEAF_CONDITIONS):  # pragma: no cover - exhaustive
        raise TypeError(f"unhandled condition type in compiler walk: {type(condition)!r}")

    if spec.value_type is frozenset:
        raise RulePackCompilationError(
            f"rule {rule.rule_id!r}: {condition.op!r} requires a scalar-typed fact, "
            f"but {path!r} is set-typed (frozenset)"
        )

    if isinstance(condition, _ORDERING_CONDITIONS) and spec.value_type is bool:
        raise RulePackCompilationError(
            f"rule {rule.rule_id!r}: {condition.op!r} is forbidden on the boolean "
            f"fact {path!r} — ordering has no meaning for booleans"
        )

    for literal in _condition_literals(condition):
        _check_literal_type(literal, spec, path=path, rule_id=rule.rule_id)


def _compile_rule(rule: Rule, *, fact_registry: FactRegistry) -> CompiledRule:
    depth = _condition_depth(rule.when)
    if depth > MAX_AST_DEPTH:
        raise RulePackCompilationError(
            f"rule {rule.rule_id!r}: condition AST depth {depth} exceeds the "
            f"maximum of {MAX_AST_DEPTH}"
        )

    node_count = _condition_node_count(rule.when)
    if node_count > MAX_CONDITION_NODES:
        raise RulePackCompilationError(
            f"rule {rule.rule_id!r}: condition AST has {node_count} nodes, "
            f"exceeding the maximum of {MAX_CONDITION_NODES}"
        )

    referenced_facts = collect_fact_paths(rule.when)

    declared_required = frozenset(rule.required_facts)
    if declared_required != referenced_facts:
        raise RulePackCompilationError(
            f"rule {rule.rule_id!r}: required_facts "
            f"{sorted(declared_required)!r} does not match the fact paths "
            f"actually referenced by `when` {sorted(referenced_facts)!r}"
        )

    _validate_condition_tree(rule.when, fact_registry=fact_registry, rule=rule)

    product_version_ids = (
        frozenset(rule.product_version_ids) if rule.product_version_ids else frozenset()
    )

    return CompiledRule(
        rule_id=rule.rule_id,
        stage=rule.stage,
        scope=rule.scope,
        product_version_ids=product_version_ids,
        priority=rule.priority,
        when=rule.when,
        effect=rule.effect,
        on_unknown=rule.on_unknown,
        referenced_facts=referenced_facts,
        source_refs=frozenset(rule.source_refs),
        explanation_key=rule.explanation_key,
        safety_critical=rule.safety_critical,
        ast_depth=depth,
        ast_node_count=node_count,
        source_rule=rule,
    )
