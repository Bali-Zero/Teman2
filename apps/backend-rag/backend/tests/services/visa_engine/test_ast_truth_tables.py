"""Truth-table tests for every AST operator x KNOWN/UNKNOWN fact, plus the
full Kleene tables for ``all``/``any``/``not`` (including mixed children) and
the ``known``/``unknown`` presence operator (API A: one ``PresenceCondition``
class dispatching on its ``op`` string, not two separate node types).

Spec: research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
concretization.md §4.1 (lines 2341-2359).
"""

from __future__ import annotations

import pytest

from backend.services.visa_engine.ast import (
    AllCondition,
    AnyCondition,
    BetweenCondition,
    ContainsAllCondition,
    EqCondition,
    FactSnapshot,
    GtCondition,
    GteCondition,
    InCondition,
    IntersectsCondition,
    KnownFact,
    LtCondition,
    LteCondition,
    NeqCondition,
    NotCondition,
    NotInCondition,
    PresenceCondition,
    UnknownFact,
    evaluate_condition,
)
from backend.services.visa_engine.enums import FactPath, TruthValue, UnknownReason

KNOWN_INT_SNAPSHOT = FactSnapshot(
    values={
        FactPath.INTENT_STAY_DAYS: KnownFact(value=30),
        FactPath.INTENT_PURPOSES: KnownFact(value=frozenset({"TOURISM", "BUSINESS_MEETINGS"})),
    }
)
UNKNOWN_SNAPSHOT = FactSnapshot(
    values={
        FactPath.INTENT_STAY_DAYS: UnknownFact(reason=UnknownReason.NOT_ASKED),
        FactPath.INTENT_PURPOSES: UnknownFact(reason=UnknownReason.NOT_PROVIDED),
    }
)


class TestPresenceOperator:
    def test_known_op_true_on_known_fact(self) -> None:
        cond = PresenceCondition(op="known", fact="intent.stay_days")
        assert evaluate_condition(cond, KNOWN_INT_SNAPSHOT).truth is TruthValue.TRUE

    def test_known_op_false_on_unknown_fact(self) -> None:
        cond = PresenceCondition(op="known", fact="intent.stay_days")
        assert evaluate_condition(cond, UNKNOWN_SNAPSHOT).truth is TruthValue.FALSE

    def test_unknown_op_false_on_known_fact(self) -> None:
        cond = PresenceCondition(op="unknown", fact="intent.stay_days")
        assert evaluate_condition(cond, KNOWN_INT_SNAPSHOT).truth is TruthValue.FALSE

    def test_unknown_op_true_on_unknown_fact(self) -> None:
        cond = PresenceCondition(op="unknown", fact="intent.stay_days")
        assert evaluate_condition(cond, UNKNOWN_SNAPSHOT).truth is TruthValue.TRUE


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        (EqCondition(op="eq", fact="intent.stay_days", value=30), TruthValue.TRUE),
        (EqCondition(op="eq", fact="intent.stay_days", value=31), TruthValue.FALSE),
        (NeqCondition(op="neq", fact="intent.stay_days", value=31), TruthValue.TRUE),
        (NeqCondition(op="neq", fact="intent.stay_days", value=30), TruthValue.FALSE),
        (LtCondition(op="lt", fact="intent.stay_days", value=31), TruthValue.TRUE),
        (LtCondition(op="lt", fact="intent.stay_days", value=30), TruthValue.FALSE),
        (LteCondition(op="lte", fact="intent.stay_days", value=30), TruthValue.TRUE),
        (LteCondition(op="lte", fact="intent.stay_days", value=29), TruthValue.FALSE),
        (GtCondition(op="gt", fact="intent.stay_days", value=29), TruthValue.TRUE),
        (GtCondition(op="gt", fact="intent.stay_days", value=30), TruthValue.FALSE),
        (GteCondition(op="gte", fact="intent.stay_days", value=30), TruthValue.TRUE),
        (GteCondition(op="gte", fact="intent.stay_days", value=31), TruthValue.FALSE),
        (InCondition(op="in", fact="intent.stay_days", values=[10, 30, 60]), TruthValue.TRUE),
        (InCondition(op="in", fact="intent.stay_days", values=[10, 60]), TruthValue.FALSE),
        (NotInCondition(op="not_in", fact="intent.stay_days", values=[10, 60]), TruthValue.TRUE),
        (
            NotInCondition(op="not_in", fact="intent.stay_days", values=[10, 30, 60]),
            TruthValue.FALSE,
        ),
        (
            BetweenCondition(op="between", fact="intent.stay_days", lower=1, upper=30),
            TruthValue.TRUE,
        ),
        (
            BetweenCondition(op="between", fact="intent.stay_days", lower=31, upper=60),
            TruthValue.FALSE,
        ),
        (
            BetweenCondition(op="between", fact="intent.stay_days", lower=30, upper=30),
            TruthValue.TRUE,
        ),
        (
            IntersectsCondition(op="intersects", fact="intent.purposes", values=["TOURISM"]),
            TruthValue.TRUE,
        ),
        (
            IntersectsCondition(op="intersects", fact="intent.purposes", values=["STUDY"]),
            TruthValue.FALSE,
        ),
        (
            ContainsAllCondition(op="contains_all", fact="intent.purposes", values=["TOURISM"]),
            TruthValue.TRUE,
        ),
        (
            ContainsAllCondition(
                op="contains_all",
                fact="intent.purposes",
                values=["TOURISM", "BUSINESS_MEETINGS", "STUDY"],
            ),
            TruthValue.FALSE,
        ),
    ],
)
def test_comparison_operators_on_known_fact(condition: object, expected: TruthValue) -> None:
    assert evaluate_condition(condition, KNOWN_INT_SNAPSHOT).truth is expected


@pytest.mark.parametrize(
    "condition",
    [
        EqCondition(op="eq", fact="intent.stay_days", value=30),
        NeqCondition(op="neq", fact="intent.stay_days", value=30),
        LtCondition(op="lt", fact="intent.stay_days", value=30),
        LteCondition(op="lte", fact="intent.stay_days", value=30),
        GtCondition(op="gt", fact="intent.stay_days", value=30),
        GteCondition(op="gte", fact="intent.stay_days", value=30),
        InCondition(op="in", fact="intent.stay_days", values=[30]),
        NotInCondition(op="not_in", fact="intent.stay_days", values=[30]),
        BetweenCondition(op="between", fact="intent.stay_days", lower=1, upper=30),
        IntersectsCondition(op="intersects", fact="intent.purposes", values=["TOURISM"]),
        ContainsAllCondition(op="contains_all", fact="intent.purposes", values=["TOURISM"]),
    ],
)
def test_comparison_operators_on_unknown_fact_always_unknown(condition: object) -> None:
    """§4.1: every comparison operator on an UNKNOWN fact returns UNKNOWN,
    regardless of the operator or the comparison value."""

    result = evaluate_condition(condition, UNKNOWN_SNAPSHOT)
    assert result.truth is TruthValue.UNKNOWN
    assert (
        FactPath.INTENT_STAY_DAYS in result.unknown_facts
        or FactPath.INTENT_PURPOSES in result.unknown_facts
    )


class TestNotKleeneTable:
    def test_not_true_is_false(self) -> None:
        cond = NotCondition(op="not", arg=EqCondition(op="eq", fact="intent.stay_days", value=30))
        assert evaluate_condition(cond, KNOWN_INT_SNAPSHOT).truth is TruthValue.FALSE

    def test_not_false_is_true(self) -> None:
        cond = NotCondition(op="not", arg=EqCondition(op="eq", fact="intent.stay_days", value=99))
        assert evaluate_condition(cond, KNOWN_INT_SNAPSHOT).truth is TruthValue.TRUE

    def test_not_unknown_stays_unknown(self) -> None:
        cond = NotCondition(op="not", arg=EqCondition(op="eq", fact="intent.stay_days", value=30))
        assert evaluate_condition(cond, UNKNOWN_SNAPSHOT).truth is TruthValue.UNKNOWN


def _leaf(truth: str) -> object:
    """Build a leaf condition against ``MIXED_SNAPSHOT`` engineered to make
    the leaf evaluate to TRUE/FALSE/UNKNOWN."""

    if truth == "TRUE":
        return EqCondition(op="eq", fact="intent.stay_days", value=30)
    if truth == "FALSE":
        return EqCondition(op="eq", fact="intent.stay_days", value=999)
    if truth == "UNKNOWN":
        return EqCondition(op="eq", fact="intent.desired_entry_date", value="x")
    raise ValueError(truth)


MIXED_SNAPSHOT = FactSnapshot(
    values={
        FactPath.INTENT_STAY_DAYS: KnownFact(value=30),
        FactPath.INTENT_DESIRED_ENTRY_DATE: UnknownFact(reason=UnknownReason.NOT_ASKED),
    }
)


@pytest.mark.parametrize(
    ("children", "expected"),
    [
        (["TRUE", "TRUE"], TruthValue.TRUE),
        (["TRUE", "FALSE"], TruthValue.FALSE),
        (["TRUE", "UNKNOWN"], TruthValue.UNKNOWN),
        (["FALSE", "FALSE"], TruthValue.FALSE),
        (["FALSE", "UNKNOWN"], TruthValue.FALSE),
        (["UNKNOWN", "UNKNOWN"], TruthValue.UNKNOWN),
        (["FALSE", "TRUE", "UNKNOWN"], TruthValue.FALSE),
    ],
)
def test_all_kleene_table(children: list[str], expected: TruthValue) -> None:
    cond = AllCondition(op="all", args=[_leaf(c) for c in children])
    assert evaluate_condition(cond, MIXED_SNAPSHOT).truth is expected


@pytest.mark.parametrize(
    ("children", "expected"),
    [
        (["TRUE", "TRUE"], TruthValue.TRUE),
        (["TRUE", "FALSE"], TruthValue.TRUE),
        (["TRUE", "UNKNOWN"], TruthValue.TRUE),
        (["FALSE", "FALSE"], TruthValue.FALSE),
        (["FALSE", "UNKNOWN"], TruthValue.UNKNOWN),
        (["UNKNOWN", "UNKNOWN"], TruthValue.UNKNOWN),
        (["TRUE", "FALSE", "UNKNOWN"], TruthValue.TRUE),
    ],
)
def test_any_kleene_table(children: list[str], expected: TruthValue) -> None:
    cond = AnyCondition(op="any", args=[_leaf(c) for c in children])
    assert evaluate_condition(cond, MIXED_SNAPSHOT).truth is expected


class TestUnreachableSetTypeMismatch:
    """ast.py's own module docstring: intersects/contains_all against a
    non-set fact value must raise, never silently degrade — unreachable for
    a compiler-validated pack, but evaluate_condition itself must still fail
    loud if ever handed a mis-derived FactSnapshot."""

    def test_intersects_on_scalar_value_raises(self) -> None:
        cond = IntersectsCondition(op="intersects", fact="intent.stay_days", values=["TOURISM"])
        snapshot = FactSnapshot(values={FactPath.INTENT_STAY_DAYS: KnownFact(value=30)})
        with pytest.raises(TypeError, match="intersects requires a set-typed fact value"):
            evaluate_condition(cond, snapshot)

    def test_contains_all_on_scalar_value_raises(self) -> None:
        cond = ContainsAllCondition(
            op="contains_all", fact="intent.stay_days", values=["TOURISM"]
        )
        snapshot = FactSnapshot(values={FactPath.INTENT_STAY_DAYS: KnownFact(value=30)})
        with pytest.raises(TypeError, match="contains_all requires a set-typed fact value"):
            evaluate_condition(cond, snapshot)


class TestMissingFactTreatedAsUnknown:
    def test_leaf_on_fact_absent_from_snapshot_is_unknown(self) -> None:
        cond = EqCondition(op="eq", fact="intent.stay_days", value=30)
        empty_snapshot = FactSnapshot(values={})
        result = evaluate_condition(cond, empty_snapshot)
        assert result.truth is TruthValue.UNKNOWN
        assert result.unknown_facts == frozenset({FactPath.INTENT_STAY_DAYS})
