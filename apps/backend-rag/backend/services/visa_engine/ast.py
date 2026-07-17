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
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.services.visa_engine.enums import FactPath
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

    op: Literal["all"] = "all"
    args: tuple[Condition, ...] = Field(..., min_length=1, max_length=64)


class AnyCondition(_ConditionBase):
    """Kleene disjunction: TRUE if any child TRUE; else UNKNOWN if any child
    UNKNOWN; else FALSE (spec §4.1).
    """

    op: Literal["any"] = "any"
    args: tuple[Condition, ...] = Field(..., min_length=1, max_length=64)


class NotCondition(_ConditionBase):
    """Negation: TRUE<->FALSE swap; UNKNOWN remains UNKNOWN (spec §4.1)."""

    op: Literal["not"] = "not"
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

    @field_validator("value")
    @classmethod
    def _validate_value(cls, v: Scalar) -> Scalar:
        return _check_scalar(v)


class EqCondition(_ScalarLeafCondition):
    op: Literal["eq"] = "eq"


class NeqCondition(_ScalarLeafCondition):
    op: Literal["neq"] = "neq"


class LtCondition(_ScalarLeafCondition):
    op: Literal["lt"] = "lt"


class LteCondition(_ScalarLeafCondition):
    op: Literal["lte"] = "lte"


class GtCondition(_ScalarLeafCondition):
    op: Literal["gt"] = "gt"


class GteCondition(_ScalarLeafCondition):
    op: Literal["gte"] = "gte"


class BetweenCondition(_ConditionBase):
    """Inclusive ``[lower, upper]`` range (spec §4.1)."""

    op: Literal["between"] = "between"
    fact: FactPath
    lower: Scalar
    upper: Scalar

    @field_validator("lower", "upper")
    @classmethod
    def _validate_bound(cls, v: Scalar) -> Scalar:
        return _check_scalar(v)


# ---------------------------------------------------------------------------
# Scalar-set comparisons
# ---------------------------------------------------------------------------


class _ScalarSetCondition(_ConditionBase):
    fact: FactPath
    values: tuple[Scalar, ...] = Field(..., min_length=1, max_length=256)

    @field_validator("values")
    @classmethod
    def _validate_values(cls, v: tuple[Scalar, ...]) -> tuple[Scalar, ...]:
        return _check_unique(tuple(_check_scalar(item) for item in v))


class InCondition(_ScalarSetCondition):
    op: Literal["in"] = "in"


class NotInCondition(_ScalarSetCondition):
    op: Literal["not_in"] = "not_in"


class IntersectsCondition(_ScalarSetCondition):
    """True iff the fact's set-value and ``values`` share at least one element."""

    op: Literal["intersects"] = "intersects"


class ContainsAllCondition(_ScalarSetCondition):
    """True iff the fact's set-value is a superset of ``values``."""

    op: Literal["contains_all"] = "contains_all"


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


def _walk(condition: object) -> Iterator[object]:
    """Pre-order traversal of every node in the tree, combinator or leaf."""
    yield condition
    for child in _children(condition):
        yield from _walk(child)


def iter_nodes(condition: object) -> Iterator[object]:
    """Public pre-order traversal of every node in the tree (combinator or
    leaf). ``compiler.py`` uses this rather than the private ``_walk`` to
    build its per-node checks (e.g. fact-literal-kind compatibility).
    """
    yield from _walk(condition)


def compute_depth(condition: object) -> int:
    """Depth of the tree rooted at ``condition``; a bare leaf has depth 1."""
    children = _children(condition)
    if not children:
        return 1
    return 1 + max(compute_depth(child) for child in children)


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
