"""Condition AST: node types, the closed operator vocabulary, structural limits.

Source: ``research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
concretization.md`` §1 (module layout, ``ast.py``) and §2 (JSON Schema 2020-12
``Condition`` ``$defs``).

PR1 scope note (deliberate deferral): this module defines node *shapes* and
*pure structural* helpers only. It does **not** implement ``evaluate_condition``
or ``ConditionResult`` — computing a Kleene ``TruthValue`` against a
``FactSnapshot`` needs the evaluator's fact-resolution machinery (spec §4.1,
§4.2), which is PR3 scope (spec §9 delivery table: PR3 = "Pure evaluator,
deterministic trace"). Every node model here already carries everything that
future evaluation will need (operator, fact path, operands, children) per
the PR1 mandate, so PR3 adds a function over these same frozen models rather
than reshaping them.

``collect_fact_paths`` *is* implemented here (it is pure tree traversal, no
truth-value semantics) because ``compiler.py`` needs it for the
``required_facts == collect_fact_paths(when)`` invariant (spec §2
compiler-only invariants).

PR3 addition: ``ConditionResult``, ``evaluate_condition()`` — the strong-
Kleene tri-state evaluator this module's own docstring above named as
deferred. Also ``FactSnapshot``/``KnownFact``/``UnknownFact``, the runtime
fact-value wrappers ``evaluate_condition`` reads (``fact_registry.py``'s
``FactRegistry.derive()`` is what *produces* a ``FactSnapshot`` from a wire
``ApplicantFacts`` — see that module's docstring). These three small
dataclasses live HERE, not in ``fact_registry.py`` (where the original spec
snippet places them), for an import-cycle reason specific to this package's
actual module graph: ``models.py`` imports ``Condition`` from this module,
and (post PR3 fix) ``fact_registry.py`` imports ``ApplicantFacts`` from
``models.py`` — so if ``FactSnapshot`` lived in ``fact_registry.py`` and
this module needed it, the edge would be ``ast -> fact_registry -> models
-> ast``, a real cycle. Keeping them here instead gives ``fact_registry.py
-> ast.py`` (for these three types) and ``fact_registry.py -> models.py``
(for ``ApplicantFacts``) as two one-way edges into a module (``ast.py``)
that itself depends on nothing but ``enums.py``/``errors.py`` — no cycle.
See ``fact_registry.py``'s module docstring for the companion note on the
``models.py`` import-cycle redirect this relies on.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.services.visa_engine.enums import FactPath, TruthValue, UnknownReason
from backend.services.visa_engine.errors import ConditionStructureError

#: Spec §2 compiler-only invariant: "Maximum AST depth 12, condition nodes 256".
MAX_CONDITION_DEPTH = 12
MAX_CONDITION_NODES = 256

#: Spec §2 ``$defs/Scalar``: boolean | JS-safe integer | non-empty <=128-char string.
Scalar = bool | int | str
_SCALAR_INT_MIN = -9_007_199_254_740_991
_SCALAR_INT_MAX = 9_007_199_254_740_991
_SCALAR_STR_MIN_LEN = 1
_SCALAR_STR_MAX_LEN = 128


def _check_scalar(value: object) -> Scalar:
    """Validate one raw value against ``$defs/Scalar`` — spec §2, and the
    compiler-only invariant "all numbers are integers ... floats are
    rejected" (line 2285 of the concretization doc).

    ``bool`` is checked before ``int`` because ``bool`` is an ``int``
    subclass in Python — a bare ``isinstance(value, int)`` check would
    silently accept/misclassify booleans.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        raise ValueError(f"scalar must be boolean/integer/string, got float {value!r}")
    if isinstance(value, int):
        if not (_SCALAR_INT_MIN <= value <= _SCALAR_INT_MAX):
            raise ValueError(
                f"integer scalar {value!r} outside JS-safe range "
                f"[{_SCALAR_INT_MIN}, {_SCALAR_INT_MAX}]"
            )
        return value
    if isinstance(value, str):
        if not (_SCALAR_STR_MIN_LEN <= len(value) <= _SCALAR_STR_MAX_LEN):
            raise ValueError(
                f"string scalar must be {_SCALAR_STR_MIN_LEN}..{_SCALAR_STR_MAX_LEN} chars, "
                f"got {len(value)}"
            )
        return value
    raise TypeError(f"unsupported scalar type: {type(value)!r}")


def _check_unique(values: tuple[Scalar, ...]) -> tuple[Scalar, ...]:
    """Spec §2 ``uniqueItems: true`` on every ``values`` array."""
    seen: list[Scalar] = []
    for v in values:
        if v in seen:
            raise ValueError(f"duplicate value in set condition: {v!r}")
        seen.append(v)
    return values


class _ConditionBase(BaseModel):
    """Shared config for every condition node: frozen, no unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


# ---------------------------------------------------------------------------
# Logical combinators
# ---------------------------------------------------------------------------


class AllCondition(_ConditionBase):
    """Kleene conjunction: FALSE if any child FALSE; else UNKNOWN if any
    child UNKNOWN; else TRUE (spec §4.1). No short-circuit at evaluation
    time — every child is evaluated so the trace stays complete.
    """

    # No default (Codex finding 2/FX-1): `op` is the discriminator for the
    # `Condition` union AND, for a signed RulePack payload, a silently
    # defaulted field is a field a canonical-payload consumer can omit
    # entirely while still round-tripping — that omission must be a
    # validation error, not an implicit "all".
    op: Literal["all"]
    args: tuple[Condition, ...] = Field(..., min_length=1, max_length=64)


class AnyCondition(_ConditionBase):
    """Kleene disjunction: TRUE if any child TRUE; else UNKNOWN if any child
    UNKNOWN; else FALSE (spec §4.1).
    """

    op: Literal["any"]
    args: tuple[Condition, ...] = Field(..., min_length=1, max_length=64)


class NotCondition(_ConditionBase):
    """Negation: TRUE<->FALSE swap; UNKNOWN remains UNKNOWN (spec §4.1)."""

    op: Literal["not"]
    arg: Condition


# ---------------------------------------------------------------------------
# Presence (spec §2 ``PresenceCondition`` merges ``known``/``unknown`` into
# one node type — see ``enums.ConditionOperator``'s docstring for why)
# ---------------------------------------------------------------------------


class PresenceCondition(_ConditionBase):
    """``known``: TRUE iff the fact is KNOWN, else FALSE.
    ``unknown``: TRUE iff the fact is UNKNOWN, else FALSE (spec §4.1).
    """

    op: Literal["known", "unknown"]
    fact: FactPath


# ---------------------------------------------------------------------------
# Scalar comparisons — UNKNOWN fact -> condition UNKNOWN (spec §4.1)
# ---------------------------------------------------------------------------


class _ScalarLeafCondition(_ConditionBase):
    fact: FactPath
    value: Scalar

    @field_validator("value", mode="before")
    @classmethod
    def _validate_value(cls, v: object) -> Scalar:
        # mode="before" is load-bearing (Codex finding 4): Scalar = bool |
        # int | str is a *lax* union, and Pydantic's own union coercion runs
        # before an "after" validator ever sees the value — a raw float like
        # 2.0 would already have been silently coerced into the int member
        # (Python's int(2.0) == 2.0) by the time an "after" validator ran,
        # so `isinstance(value, float)` below would never fire. "before"
        # intercepts the *original* wire value first.
        return _check_scalar(v)


class EqCondition(_ScalarLeafCondition):
    op: Literal["eq"]


class NeqCondition(_ScalarLeafCondition):
    op: Literal["neq"]


class LtCondition(_ScalarLeafCondition):
    op: Literal["lt"]


class LteCondition(_ScalarLeafCondition):
    op: Literal["lte"]


class GtCondition(_ScalarLeafCondition):
    op: Literal["gt"]


class GteCondition(_ScalarLeafCondition):
    op: Literal["gte"]


class BetweenCondition(_ConditionBase):
    """Inclusive ``[lower, upper]`` range (spec §4.1)."""

    op: Literal["between"]
    fact: FactPath
    lower: Scalar
    upper: Scalar

    @field_validator("lower", "upper", mode="before")
    @classmethod
    def _validate_bound(cls, v: object) -> Scalar:
        # See `_ScalarLeafCondition._validate_value` — same before-mode
        # rationale: a float bound (e.g. `upper=10.0`) must be rejected as a
        # float, not silently truncated into the int member.
        return _check_scalar(v)


# ---------------------------------------------------------------------------
# Scalar-set comparisons
# ---------------------------------------------------------------------------


class _ScalarSetCondition(_ConditionBase):
    fact: FactPath
    values: tuple[Scalar, ...] = Field(..., min_length=1, max_length=256)

    @field_validator("values", mode="before")
    @classmethod
    def _validate_values(cls, v: object) -> tuple[Scalar, ...]:
        # mode="before" for the same reason as the two validators above: each
        # raw element must be scalar-checked (float rejected, bool-vs-int
        # disambiguated) before Pydantic's own tuple/union coercion touches it.
        if not isinstance(v, (list, tuple)):
            raise TypeError(f"expected a list/tuple of scalars, got {type(v)!r}")
        return _check_unique(tuple(_check_scalar(item) for item in v))


class InCondition(_ScalarSetCondition):
    op: Literal["in"]


class NotInCondition(_ScalarSetCondition):
    op: Literal["not_in"]


class IntersectsCondition(_ScalarSetCondition):
    """True iff the fact's set-value and ``values`` share at least one element."""

    op: Literal["intersects"]


class ContainsAllCondition(_ScalarSetCondition):
    """True iff the fact's set-value is a superset of ``values``."""

    op: Literal["contains_all"]


Condition = Annotated[
    AllCondition
    | AnyCondition
    | NotCondition
    | PresenceCondition
    | EqCondition
    | NeqCondition
    | LtCondition
    | LteCondition
    | GtCondition
    | GteCondition
    | InCondition
    | NotInCondition
    | BetweenCondition
    | IntersectsCondition
    | ContainsAllCondition,
    Field(discriminator="op"),
]

# Resolve the forward references in AllCondition.args / AnyCondition.args / NotCondition.arg.
AllCondition.model_rebuild()
AnyCondition.model_rebuild()
NotCondition.model_rebuild()

#: Every leaf (non-combinator) condition class — used by ``_walk``/``collect_fact_paths``.
_LEAF_CONDITION_TYPES = (
    PresenceCondition,
    EqCondition,
    NeqCondition,
    LtCondition,
    LteCondition,
    GtCondition,
    GteCondition,
    BetweenCondition,
    InCondition,
    NotInCondition,
    IntersectsCondition,
    ContainsAllCondition,
)


def _children(node: object) -> tuple[object, ...]:
    if isinstance(node, (AllCondition, AnyCondition)):
        return tuple(node.args)
    if isinstance(node, NotCondition):
        return (node.arg,)
    return ()


#: Hard iteration cap for tree traversal, independent of and much larger
#: than ``MAX_CONDITION_NODES`` (256). A `model_construct`-built condition
#: can bypass every frozen-model write guard (Codex findings 6+8) and smuggle
#: in a self-referential/cyclic structure; walking such a tree with naive
#: Python recursion would raise ``RecursionError`` (an unrelated,
#: uninformative crash) rather than the intended, reportable
#: ``ConditionStructureError``. Both traversal primitives below are
#: iterative (no Python call-stack recursion) with this explicit budget for
#: exactly that reason — a true cycle exhausts the budget deterministically
#: instead of exhausting the interpreter's C stack.
_MAX_WALK_ITERATIONS = 100_000


def _walk(condition: object) -> Iterator[object]:
    """Pre-order traversal of every node in the tree, combinator or leaf.

    Iterative (explicit stack), not recursive — see ``_MAX_WALK_ITERATIONS``.
    """
    stack: list[object] = [condition]
    visited = 0
    while stack:
        node = stack.pop()
        visited += 1
        if visited > _MAX_WALK_ITERATIONS:
            raise ConditionStructureError(
                f"condition tree traversal exceeded {_MAX_WALK_ITERATIONS} nodes "
                "without terminating — likely a cyclic or pathological structure "
                "built outside normal validation"
            )
        yield node
        # Reversed so `stack.pop()` still yields children left-to-right.
        stack.extend(reversed(_children(node)))


def iter_nodes(condition: object) -> Iterator[object]:
    """Public pre-order traversal of every node in the tree (combinator or
    leaf). ``compiler.py`` uses this rather than the private ``_walk`` to
    build its per-node checks (e.g. fact-literal-kind compatibility).
    """
    yield from _walk(condition)


def compute_depth(condition: object) -> int:
    """Depth of the tree rooted at ``condition``; a bare leaf has depth 1.

    Iterative (explicit stack of ``(node, depth)`` pairs), not recursive —
    see ``_walk``'s ``_MAX_WALK_ITERATIONS`` docstring for why.
    """
    stack: list[tuple[object, int]] = [(condition, 1)]
    max_depth_seen = 0
    visited = 0
    while stack:
        node, depth = stack.pop()
        visited += 1
        if visited > _MAX_WALK_ITERATIONS:
            raise ConditionStructureError(
                f"condition tree traversal exceeded {_MAX_WALK_ITERATIONS} nodes "
                "without terminating — likely a cyclic or pathological structure "
                "built outside normal validation"
            )
        max_depth_seen = max(max_depth_seen, depth)
        for child in _children(node):
            stack.append((child, depth + 1))
    return max_depth_seen


def count_nodes(condition: object) -> int:
    """Total node count (combinators + leaves) in the tree rooted at ``condition``."""
    return sum(1 for _ in _walk(condition))


def validate_ast_limits(
    condition: object,
    *,
    max_depth: int = MAX_CONDITION_DEPTH,
    max_nodes: int = MAX_CONDITION_NODES,
) -> None:
    """Raise ``ConditionStructureError`` if ``condition`` exceeds the spec's
    structural limits (depth <=12, nodes <=256 — spec §2 compiler-only
    invariants). Deliberately *not* wired into any Pydantic model_validator
    (see ``models.py`` module docstring): the spec buckets this under
    "compiler-only invariants, because JSON Schema cannot express them
    safely", so ``compiler.py`` is the only caller that treats a violation as
    a (non-raising, collected) ``CompilationReport`` entry; this function is
    the raise-based primitive it wraps, and is independently unit-tested
    (``test_condition_ast.py``: depth 13 fails, depth 12 passes).
    """
    depth = compute_depth(condition)
    if depth > max_depth:
        raise ConditionStructureError(f"condition AST depth {depth} exceeds maximum {max_depth}")
    nodes = count_nodes(condition)
    if nodes > max_nodes:
        raise ConditionStructureError(
            f"condition AST node count {nodes} exceeds maximum {max_nodes}"
        )


def collect_fact_paths(condition: object) -> frozenset[str]:
    """Every distinct ``fact`` path referenced anywhere in the tree (spec §1
    ``ast.py``: ``def collect_fact_paths(condition: Condition) ->
    frozenset[str]``). Used by ``compiler.py`` to enforce
    ``required_facts == collect_fact_paths(when)``.
    """
    paths: set[str] = set()
    for node in _walk(condition):
        fact = getattr(node, "fact", None)
        if fact is not None:
            paths.add(str(fact.value if isinstance(fact, FactPath) else fact))
    return frozenset(paths)


def collect_leaf_operators(condition: object) -> frozenset[str]:
    """Every distinct leaf-level operator string used in the tree (combinators
    ``all``/``any``/``not`` excluded). Used by ``compiler.py``'s "eligibility
    rules cannot derive positive support solely from known/unknown/absence
    tests" invariant (spec §2 compiler-only invariants).
    """
    ops: set[str] = set()
    for node in _walk(condition):
        if isinstance(node, _LEAF_CONDITION_TYPES):
            ops.add(node.op)
    return frozenset(ops)


class _RootConditionHolder(BaseModel):
    """Parses a raw JSON condition tree (e.g. from a test fixture or an
    already-decoded RulePack payload dict) into the discriminated ``Condition``
    union. Not part of the spec's public API — a thin helper so callers don't
    need to hand-import ``pydantic.TypeAdapter`` boilerplate everywhere.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    root: Condition


def parse_condition(raw: object) -> Condition:
    """Parse a raw ``dict`` (or already-built node) into a validated ``Condition``."""
    if isinstance(
        raw,
        (
            AllCondition,
            AnyCondition,
            NotCondition,
            PresenceCondition,
            EqCondition,
            NeqCondition,
            LtCondition,
            LteCondition,
            GtCondition,
            GteCondition,
            InCondition,
            NotInCondition,
            BetweenCondition,
            IntersectsCondition,
            ContainsAllCondition,
        ),
    ):
        return raw
    holder = _RootConditionHolder.model_validate({"root": raw})
    return holder.root


# ---------------------------------------------------------------------------
# PR3: the strong-Kleene tri-state evaluator + its runtime fact types.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KnownFact:
    """Runtime representation of a fact whose value is known.

    ``value`` is already canonicalized by ``fact_registry.FactRegistry.
    derive()``: dates are ISO-8601 strings (so ``lt``/``lte``/``gt``/``gte``
    work as plain string comparison), ``STRING_SET``-kind facts are
    ``frozenset[str]``, everything else is the bare ``bool``/``int``/``str``.
    """

    value: object


@dataclass(frozen=True)
class UnknownFact:
    """Runtime representation of a fact whose value is unknown."""

    reason: UnknownReason


@dataclass(frozen=True)
class FactSnapshot:
    """The full set of facts (applicant-supplied + derived) for one
    evaluation, keyed by :class:`~backend.services.visa_engine.enums.FactPath`
    (a ``str`` subclass — a plain dotted string key also matches, since
    ``FactPath`` members compare/hash equal to their own string value).
    """

    values: Mapping[FactPath, KnownFact | UnknownFact]


@dataclass(frozen=True)
class ConditionResult:
    """The outcome of evaluating one condition node.

    ``referenced_facts``/``unknown_facts`` are the union across the *entire*
    evaluated subtree (every child, always — no short-circuit, see
    ``evaluate_condition``'s docstring), so a trace built from these stays
    complete even when an early child already decided the aggregate truth
    value.
    """

    truth: TruthValue
    referenced_facts: frozenset[FactPath]
    unknown_facts: frozenset[FactPath]


def _leaf_lookup(
    fact: FactPath, facts: FactSnapshot
) -> tuple[frozenset[FactPath], frozenset[FactPath], bool, object]:
    """Shared bookkeeping for every fact-referencing leaf condition.

    Returns ``(referenced_facts, unknown_facts, is_unknown, value_or_none)``.
    A fact path absent from the snapshot (should not happen for a snapshot
    built by ``FactRegistry.derive()``, which always populates all 38 paths)
    is treated as UNKNOWN rather than raising — the same fail-safe posture
    as an explicit ``UnknownFact`` entry.
    """

    snapshot_value = facts.values.get(fact)
    is_unknown = snapshot_value is None or isinstance(snapshot_value, UnknownFact)
    referenced = frozenset({fact})
    unknown = frozenset({fact}) if is_unknown else frozenset()
    value = None if is_unknown else snapshot_value.value  # type: ignore[union-attr]
    return referenced, unknown, is_unknown, value


def evaluate_condition(condition: Condition, facts: FactSnapshot) -> ConditionResult:
    """Evaluate ``condition`` against ``facts`` per the spec §4.1 strong-
    Kleene truth tables.

    Never short-circuits: ``all``/``any`` always evaluate every child (a
    Python list comprehension over ``condition.args`` forces every element
    unconditionally), and the returned ``referenced_facts``/``unknown_facts``
    are always the union over the whole subtree — a later child's fact
    reference is recorded even when an earlier child already decided the
    aggregate truth value.

    Kleene tables (spec §4.1):

    * ``all``: FALSE if any child FALSE; elif any child UNKNOWN -> UNKNOWN;
      else TRUE.
    * ``any``: TRUE if any child TRUE; elif any child UNKNOWN -> UNKNOWN;
      else FALSE.
    * ``not``: UNKNOWN -> UNKNOWN; TRUE -> FALSE; FALSE -> TRUE.
    * ``known``/``unknown`` (``PresenceCondition``): decide on the fact's
      presence, never on its own value's truthiness.
    * every scalar/scalar-set comparison: the referenced fact UNKNOWN ->
      condition UNKNOWN, regardless of operator or literal.

    ``intersects``/``contains_all`` against a fact whose known value is not
    itself a ``set``/``frozenset`` raises ``TypeError`` — unreachable for a
    ``compiler.py``-validated RulePack (its ``FACT_LITERAL_KIND_MISMATCH``
    check rejects that shape at compile time), so this is an internal
    consistency check, never a silent degrade.
    """

    if isinstance(condition, AllCondition):
        children = [evaluate_condition(child, facts) for child in condition.args]
        referenced = frozenset[FactPath]().union(*(c.referenced_facts for c in children))
        unknown = frozenset[FactPath]().union(*(c.unknown_facts for c in children))
        if any(c.truth is TruthValue.FALSE for c in children):
            truth = TruthValue.FALSE
        elif any(c.truth is TruthValue.UNKNOWN for c in children):
            truth = TruthValue.UNKNOWN
        else:
            truth = TruthValue.TRUE
        return ConditionResult(truth, referenced, unknown)

    if isinstance(condition, AnyCondition):
        children = [evaluate_condition(child, facts) for child in condition.args]
        referenced = frozenset[FactPath]().union(*(c.referenced_facts for c in children))
        unknown = frozenset[FactPath]().union(*(c.unknown_facts for c in children))
        if any(c.truth is TruthValue.TRUE for c in children):
            truth = TruthValue.TRUE
        elif any(c.truth is TruthValue.UNKNOWN for c in children):
            truth = TruthValue.UNKNOWN
        else:
            truth = TruthValue.FALSE
        return ConditionResult(truth, referenced, unknown)

    if isinstance(condition, NotCondition):
        child = evaluate_condition(condition.arg, facts)
        if child.truth is TruthValue.UNKNOWN:
            truth = TruthValue.UNKNOWN
        elif child.truth is TruthValue.TRUE:
            truth = TruthValue.FALSE
        else:
            truth = TruthValue.TRUE
        return ConditionResult(truth, child.referenced_facts, child.unknown_facts)

    if isinstance(condition, PresenceCondition):
        referenced, unknown, is_unknown, _value = _leaf_lookup(condition.fact, facts)
        if condition.op == "known":
            truth = TruthValue.FALSE if is_unknown else TruthValue.TRUE
        else:  # "unknown"
            truth = TruthValue.TRUE if is_unknown else TruthValue.FALSE
        return ConditionResult(truth, referenced, unknown)

    # Every remaining node type is a scalar/scalar-set leaf carrying `.fact`.
    referenced, unknown, is_unknown, value = _leaf_lookup(condition.fact, facts)

    if is_unknown:
        return ConditionResult(TruthValue.UNKNOWN, referenced, unknown)

    if isinstance(condition, EqCondition):
        truth = TruthValue.TRUE if value == condition.value else TruthValue.FALSE
    elif isinstance(condition, NeqCondition):
        truth = TruthValue.TRUE if value != condition.value else TruthValue.FALSE
    elif isinstance(condition, LtCondition):
        truth = TruthValue.TRUE if value < condition.value else TruthValue.FALSE
    elif isinstance(condition, LteCondition):
        truth = TruthValue.TRUE if value <= condition.value else TruthValue.FALSE
    elif isinstance(condition, GtCondition):
        truth = TruthValue.TRUE if value > condition.value else TruthValue.FALSE
    elif isinstance(condition, GteCondition):
        truth = TruthValue.TRUE if value >= condition.value else TruthValue.FALSE
    elif isinstance(condition, InCondition):
        truth = TruthValue.TRUE if value in condition.values else TruthValue.FALSE
    elif isinstance(condition, NotInCondition):
        truth = TruthValue.TRUE if value not in condition.values else TruthValue.FALSE
    elif isinstance(condition, BetweenCondition):
        truth = (
            TruthValue.TRUE if condition.lower <= value <= condition.upper else TruthValue.FALSE
        )
    elif isinstance(condition, IntersectsCondition):
        if not isinstance(value, (set, frozenset)):
            raise TypeError(
                f"intersects requires a set-typed fact value, got "
                f"{type(value).__name__} for fact {condition.fact.value!r} — "
                "unreachable for a compiler-validated RulePack (compiler.py's "
                "FACT_LITERAL_KIND_MISMATCH check rejects this at compile time)"
            )
        truth = TruthValue.TRUE if value & set(condition.values) else TruthValue.FALSE
    elif isinstance(condition, ContainsAllCondition):
        if not isinstance(value, (set, frozenset)):
            raise TypeError(
                f"contains_all requires a set-typed fact value, got "
                f"{type(value).__name__} for fact {condition.fact.value!r} — "
                "unreachable for a compiler-validated RulePack (compiler.py's "
                "FACT_LITERAL_KIND_MISMATCH check rejects this at compile time)"
            )
        truth = TruthValue.TRUE if set(condition.values) <= value else TruthValue.FALSE
    else:  # pragma: no cover - exhaustive over the closed Condition union
        raise TypeError(f"unhandled condition type: {type(condition)!r}")

    return ConditionResult(truth, referenced, unknown)
