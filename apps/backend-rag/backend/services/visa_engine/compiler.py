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

PR1 hardening round 2 (Codex correctness findings 4/6/7/8/9, see git log for
the full fix-round commit message): this module now (a) re-validates the
whole pack from its serialized form before running any check, so a
``model_construct``-smuggled structure never crashes compilation with an
unrelated exception (findings 6+8); (b) wraps every call into ``ast.py``'s
tree-traversal helpers so a malformed/cyclic condition tree is reported as a
``CompilationError`` instead of propagating; (c) rewrites the fact/literal
kind-matching check with corrected operator semantics (finding 5); (d) fixes
the SUPPORT-purpose check's vacuous-truth and GLOBAL-rule gaps (finding 7);
(e) adds compiler-side ID-uniqueness/UTC/NFC/size-limit checks that are
*intentionally redundant* with ``models.py``'s own validators — every one of
those is bypass-proof against ``model_construct`` by design.

PR1 hardening round 3 (Codex round-2 re-review — 3 new defects the round-2
fix itself introduced): (a) **fail-stop revalidation** — round 2's
non-short-circuit design (report the revalidation failure, then keep
checking the *original*, unrevalidated pack "for its own more specific
diagnosis") let a ``model_copy(update={"stage": "BOGUS"})``-tampered rule
reach ``_check_stage_effect_compatibility``'s ``STAGE_EFFECT_TYPE[rule.stage]``
dict lookup with a non-enum value and crash with an uncaught ``KeyError`` —
exactly the "never raises" violation this module promises. ``compile_rule_pack``
now stops immediately when ``_revalidate_structurally`` fails: the report
carries that one structural error and nothing else, since a pack that fails
full-model round-trip validation cannot be assumed to satisfy ANY of the
Pydantic-level invariants several checks below depend on (dict lookups keyed
by enum, ``RuleEffectType(...)`` coercion, ...). When revalidation succeeds,
every check runs against the REVALIDATED pack, never the original — this
also means several of this module's own "bypass-proof redundant" checks
(``_check_header_environment``, ``_check_stage_effect_compatibility``,
``_check_unique_ids``) are now *provably unreachable* for any pack that
reaches them: a successfully round-tripped pack, by construction, already
satisfies every ``models.py`` invariant those checks duplicate (the
serialize-then-reparse in ``_revalidate_structurally`` rebuilds every nested
model from a plain dict, so no pre-existing model-instance identity survives
to skip a nested ``model_validator``). They stay as documented
defense-in-depth (see each check's own docstring), not because they can
still fire today. (b) **GLOBAL-rule SUPPORT semantics corrected from union to
intersection** — a GLOBAL-scope rule structurally applies to *every* product
in the pack, so claiming a purpose that only *some* products cover is still a
defect even though the union-of-all-products test from round 2 let it pass;
see ``_check_support_purposes_on_product``. (c) **UTC/NFC coverage widened
from a curated field list to a generic walker over the entire signed
payload** (``payload.model_dump(mode="json")``) — round 2's field-by-field
version missed ``source_records[].document_number``, locator values, and
condition string literals entirely; see ``_check_utc_and_nfc``.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date

from backend.services.visa_engine import ast as ast_module
from backend.services.visa_engine.enums import FactValueKind, RuleEffectType, RuleStage
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY, FactRegistry, FactSpec
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

#: Spec §2 compiler-only invariant: "Maximum ... rules 4096, products 256".
#: Redundant with `RulePackPayload.rules`/`.products`'s own `max_length`
#: `Field` constraint (bypass-proof re-check, see module docstring).
_MAX_RULES = 4096
_MAX_PRODUCTS = 256


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

    Sentinel values (round 4, Codex round-3 verify residual): when the pack
    fails structural revalidation SO severely that even ``rule_pack_id``/
    ``sequence`` themselves cannot be safely read (e.g. ``payload`` itself
    replaced with ``{}`` via ``model_copy``/``model_construct`` — not just a
    field inside it), ``rule_pack_id`` is ``"UNKNOWN"`` and ``sequence`` is
    ``-1``. A real ``RulePackPayload.sequence`` is always >= 1
    (``Field(ge=1, ...)``, ``models.py``), so ``-1`` is unambiguous: no
    genuine pack can ever produce it, and a caller checking ``report.ok``
    first (as every caller should) never needs to special-case it.
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

    revalidated = _revalidate_structurally(pack, errors)
    if revalidated is None:
        # Fail-stop (round 3, Codex round-2 re-review HIGH finding): a pack
        # that does not round-trip through full Pydantic validation cannot
        # be assumed to satisfy ANY of the model-level invariants the checks
        # below depend on — e.g. `_check_stage_effect_compatibility`'s
        # `STAGE_EFFECT_TYPE[rule.stage]` dict lookup assumes `rule.stage` is
        # one of the four real `RuleStage` members, which a
        # `model_construct`/`model_copy(update=...)`-tampered rule is not
        # guaranteed to be (Codex counterexample:
        # `rule.model_copy(update={"stage": "BOGUS"})` crashed this exact
        # lookup with an uncaught `KeyError` under round 2's non-short-circuit
        # design). Stop here: the report carries the one structural error and
        # nothing else — no semantic check ever runs against an unproven pack.
        #
        # Round 4 (Codex round-3 verify HIGH residual): the header fields
        # below must be harvested DEFENSIVELY, not dereferenced directly —
        # `pack.payload` itself, not just a field inside it, can be corrupted
        # (e.g. `pack.model_copy(update={"payload": {}})`), and a direct
        # `pack.payload.rule_pack_id` access would crash on THAT, one
        # exception away from the very report meant to say "no exception".
        rule_pack_id, sequence = _safe_report_header(pack)
        return CompilationReport(
            rule_pack_id=rule_pack_id,
            sequence=sequence,
            errors=tuple(errors),
        )
    # Revalidation succeeded: operate on the freshly-revalidated pack for
    # every subsequent check, never the original — guarantees no downstream
    # check can be handed a `model_construct`-smuggled structure.
    pack = revalidated
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
    _check_unique_ids(payload, errors)
    _check_utc_and_nfc(payload, errors)
    _check_pack_size_limits(payload, errors)

    return CompilationReport(
        rule_pack_id=str(payload.rule_pack_id),
        sequence=payload.sequence,
        errors=tuple(errors),
    )


# ---------------------------------------------------------------------------
# Structural safety net (Codex findings 6+8)
# ---------------------------------------------------------------------------


def _safe_report_header(pack: RulePack) -> tuple[str, int]:
    """Best-effort extraction of the two ``CompilationReport`` header fields
    for a pack that has ALREADY failed structural revalidation (round 4,
    Codex round-3 verify HIGH residual). ``pack.payload`` itself — not just
    a field inside it — may be corrupted (``model_copy``/``model_construct``
    can replace it wholesale, e.g. with ``{}``), so this walks the chain via
    ``getattr(..., default=None)`` at every step rather than direct
    attribute access: a ``dict`` (or ``None``) in place of the expected
    ``RulePackPayload`` raises ``AttributeError`` on ``.rule_pack_id``, and
    ``getattr``'s default silently absorbs exactly that — never anything
    broader, since ``getattr`` only catches the lookup failure itself.

    Returns the sentinel pair ``("UNKNOWN", -1)`` (documented on
    ``CompilationReport``) for whichever field could not be read.
    """
    payload = getattr(pack, "payload", None)
    raw_id = getattr(payload, "rule_pack_id", None)
    raw_sequence = getattr(payload, "sequence", None)
    rule_pack_id = str(raw_id) if raw_id is not None else "UNKNOWN"
    sequence = raw_sequence if isinstance(raw_sequence, int) else -1
    return rule_pack_id, sequence


def _revalidate_structurally(pack: RulePack, errors: list[CompilationError]) -> RulePack | None:
    """Re-parse ``pack`` from its own serialized form before any check runs.

    A ``model_construct``-smuggled structure (raw-dict AST children, an
    ``AllCondition(args=())``, a self-referential/cyclic tree, a naive or
    non-UTC datetime, ...) bypasses every ``model_validator``/
    ``field_validator`` this package defines. Round-tripping through
    ``model_dump(mode="json", by_alias=True)`` -> ``RulePack.model_validate(...)``
    forces it back through full validation, so a malformed pack surfaces as
    one ordinary ``CompilationError`` instead of crashing ``compile_rule_pack``
    (or, worse, a caller three layers up) with an unrelated exception.

    ``by_alias=True`` is load-bearing (PR1b item 4 follow-on): ``model_dump``
    defaults to Python field names, not aliases (e.g. ``TimeRange.from_``,
    never the wire name ``"from"``). That was harmless while
    ``TimeRange``/``ApplicantFactsData`` had ``populate_by_name=True``
    (``model_validate`` happily accepted the Python-named dump right back)
    but is a hard failure now that both are alias-only — every pack contains
    a ``TimeRange`` somewhere, so an unaliased dump made this round-trip fail
    for literally every pack, valid or not. Dumping by alias is also the more
    correct contract regardless: this function's whole job is proving the
    pack round-trips through its *wire* representation, which is
    alias-keyed by definition.

    Returns the freshly-validated pack on success. On failure (round 3:
    fail-stop, see ``compile_rule_pack``), returns ``None`` and appends one
    error — the caller then STOPS, returning a report with only this one
    error. No check below ever runs against a pack that failed this
    round-trip: several of them (dict lookups keyed by enum, discriminated-
    union coercion, ...) assume Pydantic-level invariants that only a
    successfully-revalidated pack is guaranteed to hold.
    """
    try:
        serialized = pack.model_dump(mode="json", by_alias=True)
        return RulePack.model_validate(serialized)
    except Exception as exc:
        errors.append(
            CompilationError(
                code="PACK_FAILS_STRUCTURAL_REVALIDATION",
                message=(
                    "pack does not round-trip through "
                    "model_dump(mode='json', by_alias=True) -> model_validate(): "
                    f"{exc}"
                ),
            )
        )
        return None


def _safe_ast_call(
    rule: Rule,
    fn: Callable[[object], object],
    *,
    errors: list[CompilationError],
) -> object | None:
    """Run an *eager* ``ast_module`` traversal helper (``collect_fact_paths``/
    ``collect_leaf_operators`` — both fully consume the tree internally and
    return a concrete ``frozenset``) against ``rule.when``, converting any
    exception (including a would-be ``RecursionError`` on a cyclic tree —
    see ``ast.py``'s ``_MAX_WALK_ITERATIONS``) into a ``CompilationError``
    instead of letting it propagate out of ``compile_rule_pack`` (Codex
    findings 6+8).

    Not for ``ast_module.iter_nodes`` — that one is a *generator function*,
    so calling it only creates the generator object without executing any of
    its body; an exception from a malformed tree would only surface during
    iteration, which happens *outside* this function's try/except. Use
    ``_safe_ast_nodes`` for that call site instead.
    """
    try:
        return fn(rule.when)
    except Exception as exc:
        errors.append(
            CompilationError(
                code="MALFORMED_CONDITION_TREE",
                message=str(exc),
                rule_id=rule.rule_id,
            )
        )
        return None


def _safe_ast_nodes(rule: Rule, errors: list[CompilationError]) -> list[object] | None:
    """Same protection as ``_safe_ast_call``, specialized for
    ``ast_module.iter_nodes`` (a generator function): the malformed-tree
    exception only surfaces during iteration, so it must be eagerly
    materialized into a ``list`` *inside* the try/except, not merely called.
    """
    try:
        return list(ast_module.iter_nodes(rule.when))
    except Exception as exc:
        errors.append(
            CompilationError(
                code="MALFORMED_CONDITION_TREE",
                message=str(exc),
                rule_id=rule.rule_id,
            )
        )
        return None


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
        except ast_module.ConditionStructureError as exc:
            errors.append(
                CompilationError(
                    code="AST_LIMIT_EXCEEDED",
                    message=str(exc),
                    rule_id=rule.rule_id,
                )
            )
        except Exception as exc:
            errors.append(
                CompilationError(
                    code="MALFORMED_CONDITION_TREE",
                    message=str(exc),
                    rule_id=rule.rule_id,
                )
            )


def _check_required_facts_match_condition(
    rules: tuple[Rule, ...], errors: list[CompilationError]
) -> None:
    """Spec §2 compiler-only invariant: "required_facts == collect_fact_paths(when)"."""
    for rule in rules:
        referenced = _safe_ast_call(rule, ast_module.collect_fact_paths, errors=errors)
        if referenced is None:
            continue
        declared = frozenset(path.value for path in rule.required_facts)
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
        referenced = _safe_ast_call(rule, ast_module.collect_fact_paths, errors=errors)
        if referenced is None:
            continue
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
        referenced = _safe_ast_call(rule, ast_module.collect_fact_paths, errors=errors)
        if referenced is None:
            continue
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
        leaf_ops = _safe_ast_call(rule, ast_module.collect_leaf_operators, errors=errors)
        if leaf_ops is None:
            continue
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


# ---------------------------------------------------------------------------
# Fact/literal-kind matching (Codex finding 5 — full rewrite)
# ---------------------------------------------------------------------------

#: `in`/`not_in`: SCALAR membership — the literal list is checked against
#: the fact's OWN kind (a marital_status fact is STRING-kind; `in [SINGLE,
#: MARRIED]` is a list of STRING literals over a STRING-kind fact — valid).
#: The *old* PR1 code wrongly required STRING_SET here; that was backwards
#: (STRING_SET is the *fact*, not the *operator*, being set-valued).
_MEMBERSHIP_OPS = frozenset({"in", "not_in"})

#: `intersects`/`contains_all`: true set operators — only valid against a
#: STRING_SET-kind fact (e.g. `intent.purposes`), whose individual list
#: literals are each checked as STRING (a set of strings, not a "STRING_SET
#: literal" — there is no such scalar).
_SET_OPS = frozenset({"intersects", "contains_all"})

_EQUALITY_OPS = frozenset({"eq", "neq"})
_ORDERING_OPS = frozenset({"lt", "lte", "gt", "gte"})

#: Kinds a bare scalar literal can legally take (STRING_SET is a *fact*
#: shape, never a single literal's shape).
_SCALAR_FACT_KINDS = frozenset({FactValueKind.BOOLEAN, FactValueKind.INTEGER, FactValueKind.STRING})

#: Hotfix (2026-07-18, Gap A): a fact marked ``value_format="date"`` carries
#: a STRING-kind value that must ALSO be a real ISO-8601 calendar date, not
#: merely kind-compatible — ``kind`` alone accepted ``"20260101"`` or
#: ``"2026-1-1"`` (wrong shape) and ``"2026-02-30"`` (right shape, no such
#: calendar day). The regex catches shape; ``date.fromisoformat`` catches
#: calendar validity (leap years, day-of-month bounds, month range).
#:
#: PR1b item 8 (nit Codex): ``[0-9]``, never bare ``\d`` — Python's ``re``
#: module makes ``\d`` Unicode-aware by default, so it matches any Unicode
#: decimal digit (e.g. Arabic-Indic ٠-٩), not just ASCII 0-9. A literal like
#: ``"٢٠٢٦-٠٧-١٧"`` passed this shape check under ``\d`` and only failed
#: later at ``date.fromisoformat`` — a real defect, but mis-classified: the
#: reported message said "is not a valid calendar date" when the actual
#: problem is "wrong digit script/shape" entirely. ``[0-9]`` is
#: ASCII-only (matching ECMA-262/JSON-Schema's own ``\d`` semantics,
#: which — unlike Python's — IS ASCII-only), so this now fails at the
#: shape check with the correct message.
_DATE_LITERAL_SHAPE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def _check_date_literal_shape(
    value: str, spec: FactSpec, op: str, rule: Rule, errors: list[CompilationError]
) -> bool:
    """Returns ``True`` iff ``value`` is a valid ISO-8601 calendar-date
    literal (shape AND calendar validity), ``False`` otherwise — in the
    ``False`` case, one ``FACT_LITERAL_INVALID_DATE`` has already been
    appended to ``errors``. PR1b item 6: the caller (``_check_between_bounds``)
    uses this return value to skip its own ``lower > upper`` ordering check
    when a bound already failed here, so one invalid-date defect is never
    reported twice under two different, confusing codes.
    """
    if not _DATE_LITERAL_SHAPE.fullmatch(value):
        errors.append(
            CompilationError(
                code="FACT_LITERAL_INVALID_DATE",
                message=(
                    f"operator {op!r} literal {value!r} for date fact {spec.path.value!r} "
                    "must match YYYY-MM-DD"
                ),
                rule_id=rule.rule_id,
            )
        )
        return False
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        errors.append(
            CompilationError(
                code="FACT_LITERAL_INVALID_DATE",
                message=(
                    f"operator {op!r} literal {value!r} for date fact {spec.path.value!r} "
                    f"is not a valid calendar date: {exc}"
                ),
                rule_id=rule.rule_id,
            )
        )
        return False
    return True


#: Hotfix (2026-07-18, Gap D): a fact marked ``value_format="country_code"``
#: must be a 2-letter uppercase ISO 3166-1 alpha-2 *shape* — ``kind`` alone
#: accepted ``"USA"`` (3 letters) or ``"us"`` (lowercase). Deliberately just
#: a shape check, not the full ISO country list (that list changes; this
#: package does not own it).
_COUNTRY_CODE_LITERAL_SHAPE = re.compile(r"^[A-Z]{2}$")


def _check_country_code_literal_shape(
    value: str, spec: FactSpec, op: str, rule: Rule, errors: list[CompilationError]
) -> None:
    if not _COUNTRY_CODE_LITERAL_SHAPE.fullmatch(value):
        errors.append(
            CompilationError(
                code="FACT_LITERAL_INVALID_COUNTRY_CODE",
                message=(
                    f"operator {op!r} literal {value!r} for fact {spec.path.value!r} must be "
                    "a 2-letter uppercase ISO 3166-1 alpha-2 code"
                ),
                rule_id=rule.rule_id,
            )
        )


def _literal_kind(value: bool | int | str) -> FactValueKind:
    # `bool` before `int` — `bool` is an `int` subclass in Python.
    if isinstance(value, bool):
        return FactValueKind.BOOLEAN
    if isinstance(value, int):
        return FactValueKind.INTEGER
    return FactValueKind.STRING


def _check_single_literal_against_kind(
    value: bool | int | str,
    expected_kind: FactValueKind,
    spec: FactSpec,
    op: str,
    rule: Rule,
    errors: list[CompilationError],
) -> None:
    """Codex finding 5, two of the missing checks: (1) the literal's own
    Python-level kind must match ``expected_kind`` (catches ``age == "30"``
    — a STRING literal against an INTEGER fact); (2) if the fact declares a
    closed ``allowed_values`` set, the literal must be a member of it
    (catches ``marital_status == "NOT_A_STATUS"``).
    """
    literal_kind = _literal_kind(value)
    if literal_kind is not expected_kind:
        errors.append(
            CompilationError(
                code="FACT_LITERAL_KIND_MISMATCH",
                message=(
                    f"operator {op!r} literal {value!r} is {literal_kind.value}, "
                    f"fact {spec.path.value!r} expects {expected_kind.value}"
                ),
                rule_id=rule.rule_id,
            )
        )
        return
    if spec.allowed_values is not None and value not in spec.allowed_values:
        errors.append(
            CompilationError(
                code="FACT_LITERAL_NOT_ALLOWED",
                message=(
                    f"operator {op!r} literal {value!r} is not in fact "
                    f"{spec.path.value!r}'s allowed_values {sorted(spec.allowed_values)}"
                ),
                rule_id=rule.rule_id,
            )
        )
        return
    # Hotfix (2026-07-18, Gap A/D): `kind` alone cannot distinguish a
    # free-form STRING from a date- or country-code-shaped one —
    # `value_format` is the extra axis for that. Only reachable for a `str`
    # literal (both formats are STRING-kind facts per fact_registry.py).
    if spec.value_format == "date" and isinstance(value, str):
        _check_date_literal_shape(value, spec, op, rule, errors)
    elif spec.value_format == "country_code" and isinstance(value, str):
        _check_country_code_literal_shape(value, spec, op, rule, errors)


def _check_literal_list(
    values: Iterable[bool | int | str],
    spec: FactSpec,
    op: str,
    rule: Rule,
    errors: list[CompilationError],
) -> None:
    # A STRING_SET-kind fact's own literal *items* are each STRING (a set of
    # strings) — the container kind and the per-item kind are different
    # things, and conflating them was the root cause of finding 5.
    expected_item_kind = (
        FactValueKind.STRING if spec.kind is FactValueKind.STRING_SET else spec.kind
    )
    for value in values:
        _check_single_literal_against_kind(value, expected_item_kind, spec, op, rule, errors)


def _check_between_bounds(
    node: object, spec: FactSpec, rule: Rule, errors: list[CompilationError]
) -> None:
    lower = node.lower  # type: ignore[attr-defined]
    upper = node.upper  # type: ignore[attr-defined]
    lower_kind = _literal_kind(lower)
    upper_kind = _literal_kind(upper)
    if lower_kind is not spec.kind or upper_kind is not spec.kind:
        errors.append(
            CompilationError(
                code="FACT_LITERAL_KIND_MISMATCH",
                message=(
                    f"between bounds must both match fact {spec.path.value!r}'s kind "
                    f"{spec.kind.value} (got lower={lower_kind.value}, upper={upper_kind.value})"
                ),
                rule_id=rule.rule_id,
            )
        )
        return
    # Hotfix (2026-07-18, Gap A): same date-shape/calendar check as the
    # single-literal path — `between` bounds bypass
    # `_check_single_literal_against_kind` entirely, so without this a
    # `between` on a date fact with e.g. lower="2026-02-30" compiled clean.
    if spec.value_format == "date" and isinstance(lower, str) and isinstance(upper, str):
        lower_is_valid_date = _check_date_literal_shape(lower, spec, "between", rule, errors)
        upper_is_valid_date = _check_date_literal_shape(upper, spec, "between", rule, errors)
        if not (lower_is_valid_date and upper_is_valid_date):
            # PR1b item 6 (Codex nit on hotfix #2739): a bound that already
            # failed date validation is not a meaningful basis for an
            # ordering comparison — e.g. `["2026-99-99", "2026-01-01"]`
            # would otherwise ALSO report BETWEEN_BOUNDS_INVERTED (the
            # invalid string sorts lexicographically greater than the valid
            # one) on top of FACT_LITERAL_INVALID_DATE, two codes for what
            # is really one defect. Skip the lower>upper check entirely once
            # either bound is already reported invalid.
            return
    if lower > upper:
        errors.append(
            CompilationError(
                code="BETWEEN_BOUNDS_INVERTED",
                message=f"between lower={lower!r} exceeds upper={upper!r}",
                rule_id=rule.rule_id,
            )
        )


def _check_fact_literal_kind(
    rules: tuple[Rule, ...],
    fact_registry: FactRegistry,
    errors: list[CompilationError],
) -> None:
    """Spec §2 compiler-only invariant: "Fact-path-specific literal types"
    (Codex finding 5 — full rewrite, see the ``_MEMBERSHIP_OPS``/``_SET_OPS``
    docstrings above for the corrected operator-to-kind mapping this
    replaces).
    """
    for rule in rules:
        nodes = _safe_ast_nodes(rule, errors)
        if nodes is None:
            continue
        for node in nodes:
            op = getattr(node, "op", None)
            fact = getattr(node, "fact", None)
            if op is None or fact is None or op in ("known", "unknown"):
                continue
            try:
                spec = fact_registry.spec(fact)
            except Exception:  # broad: unknown path, reported separately by another check
                continue

            if op in _SET_OPS:
                if spec.kind is not FactValueKind.STRING_SET:
                    errors.append(
                        CompilationError(
                            code="FACT_LITERAL_KIND_MISMATCH",
                            message=(
                                f"operator {op!r} requires a set-valued fact, "
                                f"{fact.value!r} is {spec.kind.value}"
                            ),
                            rule_id=rule.rule_id,
                        )
                    )
                    continue
                _check_literal_list(node.values, spec, op, rule, errors)
                continue

            if op in _MEMBERSHIP_OPS:
                if spec.kind not in _SCALAR_FACT_KINDS:
                    errors.append(
                        CompilationError(
                            code="FACT_LITERAL_KIND_MISMATCH",
                            message=(
                                f"operator {op!r} requires a scalar-valued fact, "
                                f"{fact.value!r} is {spec.kind.value}"
                            ),
                            rule_id=rule.rule_id,
                        )
                    )
                    continue
                _check_literal_list(node.values, spec, op, rule, errors)
                continue

            if op in _EQUALITY_OPS:
                _check_single_literal_against_kind(node.value, spec.kind, spec, op, rule, errors)
                continue

            if op in _ORDERING_OPS or op == "between":
                # Hotfix (2026-07-18, Gap B): ordering (`lt`/`lte`/`gt`/
                # `gte`/`between`) is only legally meaningful against a
                # numeric fact (INTEGER) or a fact with a well-defined total
                # order encoded as ISO-8601 (`value_format="date"`, sorts
                # correctly lexicographically). It used to be rejected only
                # against BOOLEAN — a plain enum-ish STRING fact (e.g.
                # `marital_status`) compiled clean under lexicographic
                # ordering, which is not a legally meaningful comparison for
                # a closed, unordered vocabulary. Fail-closed by design: a
                # free-text STRING fact without `value_format="date"` is
                # rejected too, even though lexicographic ordering on it is
                # not inherently unsafe — a legal decision engine defaults
                # to rejecting semantically ambiguous comparisons and can
                # relax this later if a real use case needs it.
                ordering_allowed = spec.kind is FactValueKind.INTEGER or (
                    spec.kind is FactValueKind.STRING and spec.value_format == "date"
                )
                if not ordering_allowed:
                    # PR1b item 7 (nit Codex on hotfix #2739): this is NOT a
                    # literal/fact kind mismatch — the literal's own Python
                    # kind is correct (e.g. `marital_status < "MARRIED"` is a
                    # STRING literal against a genuinely STRING-kind fact).
                    # The defect is the OPERATOR: ordering has no legally
                    # meaningful semantics for this fact's kind/value_format.
                    # Dedicated code so a rule author isn't misled into
                    # "fixing" the literal's type when the literal was never
                    # wrong. Pre-SHADOW (no external consumer of error codes
                    # yet), so renaming/splitting a code here is safe.
                    errors.append(
                        CompilationError(
                            code="FACT_ORDERING_UNSUPPORTED",
                            message=(
                                f"ordering operator {op!r} not valid against fact "
                                f"{fact.value!r} of kind {spec.kind.value}"
                                + (
                                    f" (value_format={spec.value_format!r})"
                                    if spec.value_format is not None
                                    else ""
                                )
                            ),
                            rule_id=rule.rule_id,
                        )
                    )
                    continue
                if op == "between":
                    _check_between_bounds(node, spec, rule, errors)
                else:
                    _check_single_literal_against_kind(
                        node.value, spec.kind, spec, op, rule, errors
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


# ---------------------------------------------------------------------------
# SUPPORT-purpose coverage (Codex finding 7 — vacuous-truth + GLOBAL gaps)
# ---------------------------------------------------------------------------


def _check_support_purposes_on_product(
    payload: RulePackPayload, errors: list[CompilationError]
) -> None:
    """Spec §2 compiler-only invariant: "requested_purposes subset-of
    covered_purposes" — this is the STATIC, structural half PR1 can actually
    check; the full runtime invariant (an accepted applicant's
    ``requested_purposes`` must be a subset of the union of every TRUE
    SUPPORT rule's ``covered_purposes`` for the winning candidate) needs the
    evaluator (PR3) and is *not* claimed here.

    What this function guarantees, structurally, at compile time:

    1. A SUPPORT rule's ``effect.covered_purposes`` must be non-empty
       (Codex finding 7's vacuous-truth hole: ``models.EffectSupport``
       already enforces ``min_length=1`` at construction, but a
       ``model_construct``-bypassed rule could carry an empty tuple — this
       is the same bypass-proofing rationale as every other compiler-side
       redundant check in this module).
    2. A PRODUCTS-scope SUPPORT rule's ``effect.covered_purposes`` must be a
       subset of *every* referenced product's own ``covered_purposes`` — a
       rule cannot claim to support a purpose its target product never
       declares.
    3. A GLOBAL-scope SUPPORT rule (``product_version_ids is None`` — Codex's
       exact counterexample: this branch used to be skipped entirely via
       ``continue``) is checked against the *intersection* of every declared
       product's ``covered_purposes`` in the pack, not their union (round 3,
       Codex round-2 re-review HIGH finding). A GLOBAL rule structurally
       applies to EVERY product, so its claim must be valid for EVERY
       product it touches — the union test from round 2 wrongly validated
       against ANY single product rather than ALL of them: products
       {C1: TOURISM, E23: EMPLOYMENT} + a GLOBAL SUPPORT rule claiming
       {TOURISM} passed round 2's union check (TOURISM ∈ union) even though
       the rule also structurally applies to E23, which does not cover
       TOURISM — a real defect the union test could not see.
    """
    products_by_id: dict = {p.product_version_id: p for p in payload.products}
    common_product_purposes: frozenset = (
        frozenset.intersection(*(frozenset(p.covered_purposes) for p in payload.products))
        if payload.products
        else frozenset()
    )

    for rule in payload.rules:
        if rule.effect.type != "SUPPORT":
            continue
        claimed = frozenset(rule.effect.covered_purposes)
        if not claimed:
            errors.append(
                CompilationError(
                    code="SUPPORT_RULE_EMPTY_COVERED_PURPOSES",
                    message="SUPPORT rule effect.covered_purposes must be non-empty",
                    rule_id=rule.rule_id,
                )
            )
            continue

        if rule.product_version_ids is None:
            extra = claimed - common_product_purposes
            if extra:
                errors.append(
                    CompilationError(
                        code="SUPPORT_RULE_PURPOSE_NOT_ON_ANY_PRODUCT",
                        message=(
                            f"GLOBAL SUPPORT rule claims purpose(s) "
                            f"{sorted(p.value for p in extra)} not covered by every "
                            "product in the pack (a GLOBAL rule applies to all of "
                            "them, so its claim must hold for all of them)"
                        ),
                        rule_id=rule.rule_id,
                    )
                )
            continue

        for product_id in rule.product_version_ids:
            product = products_by_id.get(product_id)
            if product is None:
                continue  # reported by _check_product_reference_integrity
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


# ---------------------------------------------------------------------------
# Bypass-proof redundant checks (Codex findings 6+8+9) — ID uniqueness,
# UTC/NFC normalization, pack-size limits. Every one of these is *already*
# enforced at the `models.py` layer for a normally-constructed pack; they
# are re-implemented here, independently, because `model_construct` skips
# every model-level validator — "duplicated from model validators BY
# DESIGN" (orchestrator triage, verbatim).
# ---------------------------------------------------------------------------


def _check_unique_ids(payload: RulePackPayload, errors: list[CompilationError]) -> None:
    rule_ids = [rule.rule_id for rule in payload.rules]
    if len(set(rule_ids)) != len(rule_ids):
        errors.append(
            CompilationError(code="DUPLICATE_RULE_ID", message="rules must have unique rule_id")
        )

    product_ids = [p.product_version_id for p in payload.products]
    if len(set(product_ids)) != len(product_ids):
        errors.append(
            CompilationError(
                code="DUPLICATE_PRODUCT_ID",
                message="products must have unique product_version_id",
            )
        )

    source_ids = [r.source_record_id for r in payload.source_records]
    if len(set(source_ids)) != len(source_ids):
        errors.append(
            CompilationError(
                code="DUPLICATE_SOURCE_RECORD_ID",
                message="source_records must have unique source_record_id",
            )
        )


def _is_nfc(text: str) -> bool:
    return text == unicodedata.normalize("NFC", text)


#: Matches the ISO-8601 *shape* Pydantic's `model_dump(mode="json")` renders
#: for any ``UtcDateTime`` field — a UTC datetime as literal ``Z``
#: (``"2026-07-17T00:00:00Z"``), a non-UTC-offset one as ``±HH:MM``
#: (``"2026-07-17T00:00:00+08:00"``, only reachable via a
#: ``model_construct`` bypass — see ``_check_utc_and_nfc``'s docstring), and
#: optional fractional seconds before either suffix (verified empirically:
#: ``datetime(..., microsecond=456789).isoformat()``-equivalent renders
#: ``".456789Z"``). Anchored at BOTH ends (round 4, Codex round-3 verify
#: residual): a PREFIX-only anchor (the round-3 version of this pattern) let
#: `document_number="2026-07-17T00:00:00/REG-A"` — an ordinary, valid,
#: non-datetime identifier that merely *starts with* a date-shaped substring
#: — false-positive as NON_UTC_DATETIME, since ``re.match`` only pins the
#: start, not the end. Requiring the WHOLE string to match the datetime
#: shape (via ``fullmatch``) fixes this without narrowing true-positive
#: detection: no real datetime field's serialized value ever has trailing
#: characters after its offset suffix.
_DATETIME_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")


def _looks_like_datetime(value: str) -> bool:
    return bool(_DATETIME_SHAPE.fullmatch(value))


def _iter_json_strings(node: object, path: str) -> Iterable[tuple[str, str]]:
    """Recurse over a ``model_dump(mode="json")`` tree (dicts/lists/scalars
    only) and yield ``(dotted_path, value)`` for every ``str`` leaf, at any
    nesting depth — the generic replacement for a curated field list (round
    3, Codex round-2 re-review finding 6 residue: the previous scoped-fields
    version missed ``source_records[].document_number``, locator values, and
    condition string literals entirely). RFC 8785 canonicalization/signing
    doesn't care *which* field carries a non-normalized string, so neither
    should this check.
    """
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _iter_json_strings(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _iter_json_strings(value, f"{path}[{index}]")


def _check_utc_and_nfc(payload: RulePackPayload, errors: list[CompilationError]) -> None:
    """Spec §2 compiler-only invariant: "UTC normalization and Unicode NFC" —
    swept over the ENTIRE signed payload (round 3, Codex round-2 re-review
    finding 6 residue), not a curated field list.

    NFC matters because two visually-identical strings in different Unicode
    normalization forms (NFC vs NFD) are different byte sequences — and a
    RulePack's payload is what gets canonicalized (RFC 8785) and signed in
    PR2's ``bundle.py``. A human-authored field that silently carries NFD
    would produce a canonical payload whose bytes diverge from what the
    author actually typed, without any visible symptom — and canonicalization
    doesn't care which field it happens to land in, so this walker checks
    every ``str`` leaf anywhere in ``payload.model_dump(mode="json")``:
    ``created_by``, source-record titles AND ``document_number`` AND locator
    values, product names, rule ``explanation_key``, and every string literal
    inside a rule's ``when`` condition tree — none of these are special-cased
    or excluded.

    UTC matters for the same signing reason. In practice, ``models.py``'s own
    field validators already force every ``datetime`` field to be UTC-aware
    at construction time (``_validate_utc``), so — for a pack that reached
    this point, i.e. survived ``compile_rule_pack``'s fail-stop revalidation
    gate — this half of the walker is reachable only in a hypothetical future
    where a model-level validator is relaxed without this compiler-side check
    being updated too. Kept anyway: "duplicated from model validators BY
    DESIGN" (orchestrator triage, verbatim), same rationale as every other
    check in this section.
    """
    for path, text in _iter_json_strings(payload.model_dump(mode="json"), ""):
        if not _is_nfc(text):
            errors.append(
                CompilationError(
                    code="NON_NFC_STRING", message=f"payload.{path} is not NFC-normalized"
                )
            )
        if _looks_like_datetime(text) and not text.endswith("Z"):
            errors.append(
                CompilationError(
                    code="NON_UTC_DATETIME",
                    message=f"payload.{path} is not UTC (missing 'Z' suffix): {text!r}",
                )
            )


def _check_pack_size_limits(payload: RulePackPayload, errors: list[CompilationError]) -> None:
    """Spec §2 compiler-only invariant: "Maximum ... rules 4096, products 256"."""
    if len(payload.rules) > _MAX_RULES:
        errors.append(
            CompilationError(
                code="TOO_MANY_RULES",
                message=f"{len(payload.rules)} rules exceeds maximum {_MAX_RULES}",
            )
        )
    if len(payload.products) > _MAX_PRODUCTS:
        errors.append(
            CompilationError(
                code="TOO_MANY_PRODUCTS",
                message=f"{len(payload.products)} products exceeds maximum {_MAX_PRODUCTS}",
            )
        )


def _is_commercial(fact_path: str, fact_registry: FactRegistry) -> bool:
    try:
        return fact_registry.is_commercial(fact_path)
    except Exception:  # broad: unknown path, reported separately by another check
        return False
