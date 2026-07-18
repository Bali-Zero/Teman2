"""F2 (compiler side): intersects/contains_all may reference ONLY a
set-typed (frozenset) fact; eq/neq/lt/lte/gt/gte/between/in/not_in may
reference ONLY a scalar-typed (bool/int/str/date) fact. A shape mismatch
must be rejected at compile time — never left for ast.py's runtime
TypeError (F2's ast.py side) to catch.
"""

from __future__ import annotations

import pytest

from backend.services.visa_engine.compiler import CompiledRulePack, compile_rule_pack
from backend.services.visa_engine.errors import RulePackCompilationError
from backend.services.visa_engine.fact_registry import FactRegistry
from backend.services.visa_engine.models import RulePack

from ._builders import single_rule_envelope


def _compile(when: dict, *, required_facts: list[str]) -> CompiledRulePack:
    envelope = single_rule_envelope(when=when, required_facts=required_facts)
    pack = RulePack(**envelope)
    return compile_rule_pack(pack, fact_registry=FactRegistry())


class TestSetOpsForbiddenOnScalarFacts:
    def test_intersects_on_int_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": "intersects", "fact": "intent.stay_days", "values": ["30"]},
                required_facts=["intent.stay_days"],
            )

    def test_contains_all_on_bool_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": "contains_all", "fact": "commercial.wants_quote", "values": ["x"]},
                required_facts=["commercial.wants_quote"],
            )

    def test_intersects_on_set_fact_accepted(self) -> None:
        compiled = _compile(
            {"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
            required_facts=["intent.purposes"],
        )
        assert compiled.rules[0].when.values == ("TOURISM",)


class TestScalarOpsForbiddenOnSetFacts:
    @pytest.mark.parametrize("op", ["eq", "neq", "lt", "lte", "gt", "gte"])
    def test_scalar_comparison_on_set_fact_rejected(self, op: str) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": op, "fact": "intent.purposes", "value": "TOURISM"},
                required_facts=["intent.purposes"],
            )

    def test_in_on_set_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": "in", "fact": "intent.purposes", "values": ["TOURISM"]},
                required_facts=["intent.purposes"],
            )

    def test_between_on_set_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {
                    "op": "between",
                    "fact": "intent.purposes",
                    "lower": "A",
                    "upper": "Z",
                },
                required_facts=["intent.purposes"],
            )
