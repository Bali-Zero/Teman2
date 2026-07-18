"""The condition AST: 16 operators, three-valued (strong Kleene) semantics.

A closed, audited vocabulary by design (product-design.md §5.2) — no
arbitrary Python/JS/regex/LLM predicate can ever live inside a RulePack.
Every condition node is a frozen, ``extra="forbid"`` Pydantic model
discriminated on its ``op`` literal, matching ``$defs.Condition`` in the
JSON Schema contract member-for-member.

Evaluation never short-circuits: every child of ``all``/``any`` is always
evaluated, and every fact path referenced anywhere in the subtree is always
recorded — the trace (built in later PRs from :class:`ConditionResult`) must
stay complete regardless of which child happened to decide the outcome.

Pure module: no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator

from backend.services.visa_engine.enums import TruthValue
from backend.services.visa_engine.fact_registry import (
    FactPath,
    FactSnapshot,
    UnknownFact,
)

_INT_MIN = -9_007_199_254_740_991
_INT_MAX = 9_007_199_254_740_991

ScalarInt = Annotated[StrictInt, Field(ge=_INT_MIN, le=_INT_MAX)]
ScalarStr = Annotated[StrictStr, Field(min_length=1, max_length=128)]
Scalar = StrictBool | ScalarInt | ScalarStr
"""Matches ``$defs.Scalar``: boolean, JS-safe integer, or a 1..128 char string.

F7: every member is a Pydantic Strict type — a JSON float (``2.0``) must
never silently collapse into ``ScalarInt`` (2), and a JSON int must never
silently collapse into ``StrictBool``. The legitimate str member (any
enum-like literal for a str-typed fact) is untouched by this — a *real*
string always validates as ``ScalarStr`` regardless of its contents (e.g.
the literal text ``"true"`` is a perfectly valid Scalar string; whether
it's the *correct* type for whatever fact it's compared against is the
compiler's job, per F1 — not this union's)."""


def _require_unique(values: tuple[Scalar, ...]) -> tuple[Scalar, ...]:
    if len(values) != len(set(values)):
        raise ValueError("items must be unique")
    return values


class _ConditionBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --- Logical connectives (recursive) ---------------------------------------


class AllCondition(_ConditionBase):
    """``TRUE`` only if every child is ``TRUE``; see §4.1 truth table."""

    op: Literal["all"]
    args: tuple[Condition, ...] = Field(min_length=1, max_length=64)


class AnyCondition(_ConditionBase):
    """``TRUE`` if any child is ``TRUE``; see §4.1 truth table."""

    op: Literal["any"]
    args: tuple[Condition, ...] = Field(min_length=1, max_length=64)


class NotCondition(_ConditionBase):
    """Negation. ``UNKNOWN`` stays ``UNKNOWN`` (never resolves to a boolean)."""

    op: Literal["not"]
    arg: Condition


# --- Presence -----------------------------------------------------------


class KnownCondition(_ConditionBase):
    """``TRUE`` iff ``fact`` is ``KNOWN``."""

    op: Literal["known"]
    fact: FactPath


class UnknownCondition(_ConditionBase):
    """``TRUE`` iff ``fact`` is ``UNKNOWN``."""

    op: Literal["unknown"]
    fact: FactPath


# --- Scalar comparisons ---------------------------------------------------


class EqCondition(_ConditionBase):
    op: Literal["eq"]
    fact: FactPath
    value: Scalar


class NeqCondition(_ConditionBase):
    op: Literal["neq"]
    fact: FactPath
    value: Scalar


class LtCondition(_ConditionBase):
    op: Literal["lt"]
    fact: FactPath
    value: Scalar


class LteCondition(_ConditionBase):
    op: Literal["lte"]
    fact: FactPath
    value: Scalar


class GtCondition(_ConditionBase):
    op: Literal["gt"]
    fact: FactPath
    value: Scalar


class GteCondition(_ConditionBase):
    op: Literal["gte"]
    fact: FactPath
    value: Scalar


# --- Membership / range / set operators -----------------------------------


class InCondition(_ConditionBase):
    op: Literal["in"]
    fact: FactPath
    values: tuple[Scalar, ...] = Field(min_length=1, max_length=256)

    _unique = field_validator("values")(_require_unique)


class NotInCondition(_ConditionBase):
    op: Literal["not_in"]
    fact: FactPath
    values: tuple[Scalar, ...] = Field(min_length=1, max_length=256)

    _unique = field_validator("values")(_require_unique)


class BetweenCondition(_ConditionBase):
    op: Literal["between"]
    fact: FactPath
    lower: Scalar
    upper: Scalar


class IntersectsCondition(_ConditionBase):
    op: Literal["intersects"]
    fact: FactPath
    values: tuple[Scalar, ...] = Field(min_length=1, max_length=256)

    _unique = field_validator("values")(_require_unique)


class ContainsAllCondition(_ConditionBase):
    op: Literal["contains_all"]
    fact: FactPath
    values: tuple[Scalar, ...] = Field(min_length=1, max_length=256)

    _unique = field_validator("values")(_require_unique)


Condition = Annotated[
    AllCondition
    | AnyCondition
    | NotCondition
    | KnownCondition
    | UnknownCondition
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
"""Matches ``$defs.Condition`` — a ``oneOf`` of the 16 operator shapes,
discriminated in Python by the (always-present, always-literal) ``op`` field."""

# Resolve the "Condition" forward reference used by the 3 recursive nodes.
AllCondition.model_rebuild()
AnyCondition.model_rebuild()
NotCondition.model_rebuild()


@dataclass(frozen=True)
class ConditionResult:
    """The outcome of evaluating one condition node.

    ``referenced_facts``/``unknown_facts`` are the UNION across the *entire*
    evaluated subtree (every child, always — no short-circuit), so a trace
    built from these stays complete even when an early child already decided
    the aggregate truth value.
    """

    truth: TruthValue
    referenced_facts: frozenset[str]
    unknown_facts: frozenset[str]


def _leaf_lookup(
    fact: FactPath, facts: FactSnapshot
) -> tuple[frozenset[str], frozenset[str], bool, object]:
    """Shared bookkeeping for every fact-referencing leaf condition.

    Returns ``(referenced_facts, unknown_facts, is_unknown, value_or_none)``.
    """

    path = str(fact.value) if hasattr(fact, "value") else str(fact)
    snapshot_value = facts.values.get(path)
    is_unknown = snapshot_value is None or isinstance(snapshot_value, UnknownFact)
    referenced = frozenset({path})
    unknown = frozenset({path}) if is_unknown else frozenset()
    value = None if is_unknown else snapshot_value.value  # type: ignore[union-attr]
    return referenced, unknown, is_unknown, value


def evaluate_condition(condition: Condition, facts: FactSnapshot) -> ConditionResult:
    """Evaluate ``condition`` against ``facts`` per the §4.1 truth table.

    Never short-circuits: ``all``/``any`` always evaluate every child, and
    the returned ``referenced_facts``/``unknown_facts`` are always the union
    over the whole subtree.
    """

    if isinstance(condition, AllCondition):
        children = [evaluate_condition(c, facts) for c in condition.args]
        referenced = frozenset().union(*(c.referenced_facts for c in children))
        unknown = frozenset().union(*(c.unknown_facts for c in children))
        if any(c.truth is TruthValue.FALSE for c in children):
            truth = TruthValue.FALSE
        elif any(c.truth is TruthValue.UNKNOWN for c in children):
            truth = TruthValue.UNKNOWN
        else:
            truth = TruthValue.TRUE
        return ConditionResult(truth, referenced, unknown)

    if isinstance(condition, AnyCondition):
        children = [evaluate_condition(c, facts) for c in condition.args]
        referenced = frozenset().union(*(c.referenced_facts for c in children))
        unknown = frozenset().union(*(c.unknown_facts for c in children))
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

    referenced, unknown, is_unknown, value = _leaf_lookup(condition.fact, facts)

    if isinstance(condition, KnownCondition):
        truth = TruthValue.FALSE if is_unknown else TruthValue.TRUE
        return ConditionResult(truth, referenced, unknown)

    if isinstance(condition, UnknownCondition):
        truth = TruthValue.TRUE if is_unknown else TruthValue.FALSE
        return ConditionResult(truth, referenced, unknown)

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
        truth = TruthValue.TRUE if condition.lower <= value <= condition.upper else TruthValue.FALSE
    elif isinstance(condition, IntersectsCondition):
        if not isinstance(value, (set, frozenset)):
            # Unreachable for a compiler-validated pack: compiler.py's
            # operator/fact-shape check (F2) rejects `intersects` on any
            # fact whose FactSpec.value_type isn't frozenset before this
            # code can ever run. No scalar->singleton fallback — that
            # silently "worked" on the wrong shape instead of surfacing the
            # authoring bug.
            raise TypeError(
                f"intersects requires a set-typed fact value, got "
                f"{type(value).__name__} for fact {condition.fact!r} — "
                "this is unreachable for a compiler-validated RulePack"
            )
        truth = TruthValue.TRUE if value & set(condition.values) else TruthValue.FALSE
    elif isinstance(condition, ContainsAllCondition):
        if not isinstance(value, (set, frozenset)):
            # See IntersectsCondition above: unreachable post-compilation.
            raise TypeError(
                f"contains_all requires a set-typed fact value, got "
                f"{type(value).__name__} for fact {condition.fact!r} — "
                "this is unreachable for a compiler-validated RulePack"
            )
        truth = TruthValue.TRUE if set(condition.values) <= value else TruthValue.FALSE
    else:  # pragma: no cover - exhaustive over the closed Condition union
        raise TypeError(f"unhandled condition type: {type(condition)!r}")

    return ConditionResult(truth, referenced, unknown)


def collect_fact_paths(condition: Condition) -> frozenset[str]:
    """Every fact path referenced anywhere in ``condition``'s subtree.

    A pure, evaluation-independent AST walk (unlike
    :func:`evaluate_condition`'s ``referenced_facts``, which is scoped to one
    evaluation run) — used by the compiler to validate a rule's
    ``required_facts`` and fact-path registration before any facts exist.
    """

    if isinstance(condition, (AllCondition, AnyCondition)):
        result: frozenset[str] = frozenset()
        for child in condition.args:
            result |= collect_fact_paths(child)
        return result

    if isinstance(condition, NotCondition):
        return collect_fact_paths(condition.arg)

    fact = condition.fact
    path = str(fact.value) if hasattr(fact, "value") else str(fact)
    return frozenset({path})
