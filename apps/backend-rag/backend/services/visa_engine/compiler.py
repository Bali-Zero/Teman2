"""RulePack static validation: aggregate every defect into one report.

Source: ``research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
concretization.md`` §1 (module layout, ``compiler.py``) and §2's
"Compiler-only invariants, because JSON Schema cannot express them safely"
list (lines 2270-2286 of that document).

Design principle (task brief, verbatim): "Returns typed CompilationReport
(errors list, never raises-on-first)." A malformed ``RulePack`` should show
every problem in one pass, not fail on the first ``ValueError`` an author
happens to trip. Every check function below therefore *appends* to a shared
error list rather than raising; the handful of things that genuinely cannot
be represented as "well-typed but semantically wrong" (basic JSON-Schema
conformance: required fields, patterns, enums, `extra=forbid`, the two
single-object ``allOf`` conditionals) are enforced earlier, at
``models.RulePack`` construction time via Pydantic — see that module's
docstring for the split rationale. ``compile_rule_pack`` takes an
already-parsed ``models.RulePack`` for exactly that reason: a pack that
fails basic schema conformance never reaches this function at all.

PR1 scope note: the spec's own ``compiler.py`` signature takes a
``bundle.VerifiedRulePack`` (a signed-and-verified pack — PR2 scope). PR1 has
no ``bundle.py``, so ``compile_rule_pack`` takes a plain ``models.RulePack``
instead; PR2 can either wrap this function or add a thin adapter once
``VerifiedRulePack`` exists. ``CompiledRulePack``/``CompiledRule``/
``CompiledProduct`` (spec §1 — the evaluator-ready compiled form) are *not*
built here: PR1's job is to validate and report, not to compile into the
evaluator's runtime representation, which needs the evaluator itself (PR3)
to define what "compiled" means operationally.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.services.visa_engine import ast as ast_module
from backend.services.visa_engine.enums import FactValueKind, RuleEffectType, RuleStage
from backend.services.visa_engine.errors import ConditionStructureError
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY, FactRegistry
from backend.services.visa_engine.models import (
    STAGE_EFFECT_TYPE,
    Rule,
    RulePack,
    RulePackPayload,
)

#: Legal stages: a rule here may never reference a `commercial.*` fact
#: (spec §2 compiler-only invariant "No commercial.* fact in hard-filter,
#: eligibility, or review rules").
_LEGAL_STAGES = frozenset({RuleStage.HARD_FILTER, RuleStage.ELIGIBILITY, RuleStage.HUMAN_REVIEW})

#: Leaf operators that carry no comparison semantics — a rule whose `when`
#: uses only these (plus `all`/`any`/`not` combinators) cannot manufacture
#: positive eligibility from mere presence/absence (spec §2 compiler-only
#: invariant "Eligibility rules cannot derive positive support solely from
#: known, unknown, or absence tests").
_PRESENCE_ONLY_OPERATORS = frozenset({"known", "unknown"})


@dataclass(frozen=True, slots=True)
class CompilationError:
    """One reportable defect. ``rule_id``/``product_code`` are set when the
    defect is localized to a specific rule/product; both ``None`` means the
    defect is pack-wide (e.g. header/environment mismatch).
    """

    code: str
    message: str
    rule_id: str | None = None
    product_code: str | None = None


@dataclass(frozen=True, slots=True)
class CompilationReport:
    """The full result of ``compile_rule_pack`` — never partial, always
    complete: every check below runs regardless of whether an earlier one
    found a defect.
    """

    rule_pack_id: str
    sequence: int
    errors: tuple[CompilationError, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def compile_rule_pack(
    pack: RulePack,
    *,
    fact_registry: FactRegistry = DEFAULT_FACT_REGISTRY,
) -> CompilationReport:
    """Run every static validation pass over ``pack`` and return one report.

    Never raises for an ordinary defect in the pack's content — see module
    docstring. The only exceptions that propagate are programmer errors
    (e.g. passing something that is not a ``RulePack``, which is a type
    contract violation, not a "compilation defect").
    """
    errors: list[CompilationError] = []
    payload = pack.payload

    _check_header_environment(pack, errors)
    _check_ast_limits(payload.rules, errors)
    _check_required_facts_match_condition(payload.rules, errors)
    _check_required_facts_in_registry(payload.rules, fact_registry, errors)
    _check_no_commercial_facts_in_legal_stages(payload.rules, fact_registry, errors)
    _check_ranking_facts_commercial_only(payload.rules, fact_registry, errors)
    _check_eligibility_not_presence_only(payload.rules, errors)
    _check_stage_effect_compatibility(payload.rules, errors)
    _check_fact_literal_kind(payload.rules, fact_registry, errors)
    _check_product_reference_integrity(payload, errors)
    _check_source_reference_integrity(payload, errors)
    _check_support_purposes_on_product(payload, errors)

    return CompilationReport(
        rule_pack_id=str(payload.rule_pack_id),
        sequence=payload.sequence,
        errors=tuple(errors),
    )


# ---------------------------------------------------------------------------
# Individual checks — each appends to `errors`, never raises for pack content
# ---------------------------------------------------------------------------


def _check_header_environment(pack: RulePack, errors: list[CompilationError]) -> None:
    """Spec §2 compiler-only invariant: "Header environment equals payload environment".

    Compares by value, not identity/attribute access — a pack assembled via
    ``model_construct``/``model_copy(update=...)`` (bypassing Pydantic
    validation, e.g. a test simulating a tampered envelope) can carry a raw
    ``str`` instead of an ``Environment`` enum member; this must still be
    reported as a defect rather than crash the whole compile pass.
    """
    protected_env = getattr(pack.protected.environment, "value", pack.protected.environment)
    payload_env = getattr(pack.payload.environment, "value", pack.payload.environment)
    if protected_env != payload_env:
        errors.append(
            CompilationError(
                code="ENVIRONMENT_MISMATCH",
                message=f"protected.environment={protected_env!r} != payload.environment={payload_env!r}",
            )
        )


def _check_ast_limits(rules: tuple[Rule, ...], errors: list[CompilationError]) -> None:
    """Spec §2 compiler-only invariant: "Maximum AST depth 12, condition nodes 256"."""
    for rule in rules:
        try:
            ast_module.validate_ast_limits(rule.when)
        except ConditionStructureError as exc:
            errors.append(
                CompilationError(
                    code="AST_LIMIT_EXCEEDED",
                    message=str(exc),
                    rule_id=rule.rule_id,
                )
            )


def _check_required_facts_match_condition(
    rules: tuple[Rule, ...], errors: list[CompilationError]
) -> None:
    """Spec §2 compiler-only invariant: "required_facts == collect_fact_paths(when)"."""
    for rule in rules:
        declared = frozenset(path.value for path in rule.required_facts)
        referenced = ast_module.collect_fact_paths(rule.when)
        if declared != referenced:
            missing = referenced - declared
            extra = declared - referenced
            details = []
            if missing:
                details.append(f"missing from required_facts: {sorted(missing)}")
            if extra:
                details.append(f"declared but not referenced: {sorted(extra)}")
            errors.append(
                CompilationError(
                    code="REQUIRED_FACTS_MISMATCH",
                    message="; ".join(details),
                    rule_id=rule.rule_id,
                )
            )


def _check_required_facts_in_registry(
    rules: tuple[Rule, ...],
    fact_registry: FactRegistry,
    errors: list[CompilationError],
) -> None:
    """PR1 brief: "validation that a RulePack's required_facts subset-of registry"."""
    for rule in rules:
        missing = fact_registry.missing_paths(rule.required_facts)
        if missing:
            errors.append(
                CompilationError(
                    code="REQUIRED_FACT_NOT_IN_REGISTRY",
                    message=f"unknown fact path(s): {sorted(missing)}",
                    rule_id=rule.rule_id,
                )
            )


def _check_no_commercial_facts_in_legal_stages(
    rules: tuple[Rule, ...],
    fact_registry: FactRegistry,
    errors: list[CompilationError],
) -> None:
    """Spec §2 compiler-only invariant: "No commercial.* fact in hard-filter,
    eligibility, or review rules".
    """
    for rule in rules:
        if rule.stage not in _LEGAL_STAGES:
            continue
        referenced = ast_module.collect_fact_paths(rule.when)
        commercial = {path for path in referenced if _is_commercial(path, fact_registry)}
        if commercial:
            errors.append(
                CompilationError(
                    code="COMMERCIAL_FACT_IN_LEGAL_STAGE",
                    message=f"commercial fact(s) {sorted(commercial)} used in {rule.stage.value} rule",
                    rule_id=rule.rule_id,
                )
            )


def _check_ranking_facts_commercial_only(
    rules: tuple[Rule, ...],
    fact_registry: FactRegistry,
    errors: list[CompilationError],
) -> None:
    """Spec §2 compiler-only invariant: "ADD_SCORE may use only commercial/
    preference facts" (spec §4.4: "Ranking rules may use only commercial.*
    or other explicitly registered preference facts" — PR1 has no other
    registered preference facts yet, so this reduces to commercial-only;
    see module docstring for the scope note).
    """
    for rule in rules:
        if rule.stage is not RuleStage.RANKING:
            continue
        referenced = ast_module.collect_fact_paths(rule.when)
        non_commercial = {path for path in referenced if not _is_commercial(path, fact_registry)}
        if non_commercial:
            errors.append(
                CompilationError(
                    code="RANKING_RULE_USES_LEGAL_FACT",
                    message=f"non-commercial fact(s) {sorted(non_commercial)} used in RANKING rule",
                    rule_id=rule.rule_id,
                )
            )


def _check_eligibility_not_presence_only(
    rules: tuple[Rule, ...], errors: list[CompilationError]
) -> None:
    """Spec §2 compiler-only invariant: "Eligibility rules cannot derive
    positive support solely from known, unknown, or absence tests".
    """
    for rule in rules:
        if rule.stage is not RuleStage.ELIGIBILITY:
            continue
        leaf_ops = ast_module.collect_leaf_operators(rule.when)
        if leaf_ops and leaf_ops.issubset(_PRESENCE_ONLY_OPERATORS):
            errors.append(
                CompilationError(
                    code="ELIGIBILITY_RULE_PRESENCE_ONLY",
                    message=(
                        "ELIGIBILITY rule's `when` uses only known/unknown presence "
                        "tests — cannot derive positive support"
                    ),
                    rule_id=rule.rule_id,
                )
            )


def _check_stage_effect_compatibility(
    rules: tuple[Rule, ...], errors: list[CompilationError]
) -> None:
    """Redundant, defense-in-depth re-check of ``models.Rule``'s own
    ``model_validator`` (spec §2 compiler-only invariant "Stage/effect
    compatibility"). A well-formed ``Rule`` can never actually fail this —
    Pydantic already rejected it at construction — but this keeps the
    compiler's report self-sufficient if a future caller ever constructs a
    ``Rule`` via ``model_construct`` (bypassing validation) or a future PR
    relaxes the model-level check.
    """
    for rule in rules:
        expected = STAGE_EFFECT_TYPE[rule.stage]
        actual = RuleEffectType(rule.effect.type)
        if actual is not expected:
            errors.append(
                CompilationError(
                    code="STAGE_EFFECT_MISMATCH",
                    message=f"stage {rule.stage.value} requires effect {expected.value}, got {actual.value}",
                    rule_id=rule.rule_id,
                )
            )


def _check_fact_literal_kind(
    rules: tuple[Rule, ...],
    fact_registry: FactRegistry,
    errors: list[CompilationError],
) -> None:
    """Spec §2 compiler-only invariant: "Fact-path-specific literal types".

    Walks every leaf condition and checks that comparison operators are used
    against a fact whose ``FactValueKind`` supports them (e.g. ``lt``/``gt``
    against a ``STRING_SET`` fact, or ``intersects`` against a scalar
    ``BOOLEAN`` fact, is rejected).
    """
    scalar_ops = {"eq", "neq", "lt", "lte", "gt", "gte", "between"}
    set_ops = {"in", "not_in", "intersects", "contains_all"}

    for rule in rules:
        for node in ast_module.iter_nodes(rule.when):
            op = getattr(node, "op", None)
            fact = getattr(node, "fact", None)
            if op is None or fact is None or op in ("known", "unknown"):
                continue
            try:
                spec = fact_registry.spec(fact)
            except Exception:  # broad: unknown path, reported separately by another check
                continue
            if op in scalar_ops and spec.kind is FactValueKind.STRING_SET:
                errors.append(
                    CompilationError(
                        code="FACT_LITERAL_KIND_MISMATCH",
                        message=f"operator {op!r} not valid against set-valued fact {fact.value!r}",
                        rule_id=rule.rule_id,
                    )
                )
            elif op in set_ops and spec.kind is not FactValueKind.STRING_SET:
                errors.append(
                    CompilationError(
                        code="FACT_LITERAL_KIND_MISMATCH",
                        message=f"operator {op!r} requires a set-valued fact, {fact.value!r} is {spec.kind.value}",
                        rule_id=rule.rule_id,
                    )
                )
            elif op in ("lt", "lte", "gt", "gte") and spec.kind is FactValueKind.BOOLEAN:
                errors.append(
                    CompilationError(
                        code="FACT_LITERAL_KIND_MISMATCH",
                        message=f"ordering operator {op!r} not valid against boolean fact {fact.value!r}",
                        rule_id=rule.rule_id,
                    )
                )


def _known_product_ids(payload: RulePackPayload) -> frozenset:
    """The set of declared product_version_ids (helper for the check below)."""
    return frozenset(product.product_version_id for product in payload.products)


def _check_product_reference_integrity(
    payload: RulePackPayload, errors: list[CompilationError]
) -> None:
    """Spec §2 compiler-only invariant: "Source-reference and product-reference
    integrity" (product half) — a PRODUCTS-scope rule may only reference
    ``product_version_id``s that exist in ``payload.products``.
    """
    known_products = _known_product_ids(payload)
    for rule in payload.rules:
        if rule.product_version_ids is None:
            continue
        unknown = frozenset(rule.product_version_ids) - known_products
        if unknown:
            errors.append(
                CompilationError(
                    code="UNKNOWN_PRODUCT_REFERENCE",
                    message=f"references unknown product_version_id(s): {sorted(str(u) for u in unknown)}",
                    rule_id=rule.rule_id,
                )
            )


def _check_source_reference_integrity(
    payload: RulePackPayload, errors: list[CompilationError]
) -> None:
    """Spec §2 compiler-only invariant: "Source-reference and product-reference
    integrity" (source half) — every rule/product ``source_refs`` entry must
    exist in ``payload.source_records``.
    """
    known_sources = frozenset(record.source_record_id for record in payload.source_records)
    for rule in payload.rules:
        unknown = frozenset(rule.source_refs) - known_sources
        if unknown:
            errors.append(
                CompilationError(
                    code="UNKNOWN_SOURCE_REFERENCE",
                    message=f"references unknown source_record_id(s): {sorted(str(u) for u in unknown)}",
                    rule_id=rule.rule_id,
                )
            )
    for product in payload.products:
        unknown = frozenset(product.source_refs) - known_sources
        if unknown:
            errors.append(
                CompilationError(
                    code="UNKNOWN_SOURCE_REFERENCE",
                    message=f"references unknown source_record_id(s): {sorted(str(u) for u in unknown)}",
                    product_code=product.product_code,
                )
            )


def _check_support_purposes_on_product(
    payload: RulePackPayload, errors: list[CompilationError]
) -> None:
    """Spec §2 compiler-only invariant: "requested_purposes subset-of
    covered_purposes" — resolved here (documented in the PR1 report) as: a
    PRODUCTS-scope SUPPORT rule's ``effect.covered_purposes`` must be a
    subset of every referenced product's own ``covered_purposes``. A rule
    cannot claim to support a purpose its target product never declares.
    """
    products_by_id: dict = {p.product_version_id: p for p in payload.products}
    for rule in payload.rules:
        if rule.effect.type != "SUPPORT" or rule.product_version_ids is None:
            continue
        claimed = frozenset(rule.effect.covered_purposes)
        for product_id in rule.product_version_ids:
            product = products_by_id.get(product_id)
            if product is None:
                continue  # reported by _check_product_reference_integrity_errors
            allowed = frozenset(product.covered_purposes)
            extra = claimed - allowed
            if extra:
                errors.append(
                    CompilationError(
                        code="SUPPORT_RULE_PURPOSE_NOT_ON_PRODUCT",
                        message=(
                            f"claims purpose(s) {sorted(p.value for p in extra)} not in "
                            f"product {product.product_code}'s covered_purposes"
                        ),
                        rule_id=rule.rule_id,
                        product_code=product.product_code,
                    )
                )


def _is_commercial(fact_path: str, fact_registry: FactRegistry) -> bool:
    try:
        return fact_registry.is_commercial(fact_path)
    except Exception:  # broad: unknown path, reported separately by another check
        return False
