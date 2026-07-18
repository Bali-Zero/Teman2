"""F2: ast.py must not silently coerce a scalar fact value into a singleton
set for intersects/contains_all — that fallback is removed; a mismatched
fact shape reaching evaluate_condition (which should be unreachable for a
compiler-validated pack) must raise an internal error instead of silently
"working" on the wrong shape.
"""

from __future__ import annotations

import pytest

from backend.services.visa_engine.ast import (
    ContainsAllCondition,
    IntersectsCondition,
    evaluate_condition,
)
from backend.services.visa_engine.fact_registry import FactSnapshot, KnownFact

SCALAR_SNAPSHOT = FactSnapshot(values={"intent.stay_days": KnownFact(value=30)})
SET_SNAPSHOT = FactSnapshot(values={"intent.purposes": KnownFact(value=frozenset({"TOURISM"}))})


def test_intersects_on_scalar_fact_raises_internal_error() -> None:
    """No scalar->singleton fallback: a scalar fact value reaching
    `intersects` (which should never happen for a compiler-validated pack)
    must raise, not silently wrap the scalar in a set."""

    cond = IntersectsCondition(op="intersects", fact="intent.stay_days", values=["TOURISM"])
    with pytest.raises(TypeError):
        evaluate_condition(cond, SCALAR_SNAPSHOT)


def test_contains_all_on_scalar_fact_raises_internal_error() -> None:
    cond = ContainsAllCondition(op="contains_all", fact="intent.stay_days", values=["TOURISM"])
    with pytest.raises(TypeError):
        evaluate_condition(cond, SCALAR_SNAPSHOT)


def test_intersects_on_set_fact_still_works() -> None:
    cond = IntersectsCondition(op="intersects", fact="intent.purposes", values=["TOURISM"])
    result = evaluate_condition(cond, SET_SNAPSHOT)
    assert result.truth.value == "TRUE"


def test_contains_all_on_set_fact_still_works() -> None:
    cond = ContainsAllCondition(op="contains_all", fact="intent.purposes", values=["TOURISM"])
    result = evaluate_condition(cond, SET_SNAPSHOT)
    assert result.truth.value == "TRUE"
