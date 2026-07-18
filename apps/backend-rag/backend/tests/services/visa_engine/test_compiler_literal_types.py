"""F1: the compiler must recursively validate every condition literal's
Python type against the referenced fact's FactSpec.value_type — a bool
literal only on a bool fact, an int literal only on an int fact, a str
literal only on a str fact, and a date-typed fact's literal must be a
valid ISO date string. lt/lte/gt/gte/between are additionally FORBIDDEN on
bool facts regardless of the literal's type. No cross-type comparison may
ever reach evaluate_condition.
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


class TestBoolLiteralOnlyOnBoolFact:
    def test_int_literal_on_bool_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": "eq", "fact": "commercial.wants_quote", "value": 1},
                required_facts=["commercial.wants_quote"],
            )

    def test_str_literal_on_bool_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": "eq", "fact": "immigration.currently_in_indonesia", "value": "true"},
                required_facts=["immigration.currently_in_indonesia"],
            )

    def test_bool_literal_on_bool_fact_accepted(self) -> None:
        compiled = _compile(
            {"op": "eq", "fact": "immigration.currently_in_indonesia", "value": True},
            required_facts=["immigration.currently_in_indonesia"],
        )
        assert compiled.rules[0].when.value is True


class TestIntLiteralOnlyOnIntFact:
    def test_bool_literal_on_int_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": "eq", "fact": "intent.stay_days", "value": True},
                required_facts=["intent.stay_days"],
            )

    def test_str_literal_on_int_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": "eq", "fact": "intent.stay_days", "value": "30"},
                required_facts=["intent.stay_days"],
            )

    def test_int_literal_on_int_fact_accepted(self) -> None:
        compiled = _compile(
            {"op": "gt", "fact": "intent.stay_days", "value": 30},
            required_facts=["intent.stay_days"],
        )
        assert compiled.rules[0].when.value == 30


class TestStrLiteralOnlyOnStrFact:
    def test_int_literal_on_str_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": "eq", "fact": "person.marital_status", "value": 1},
                required_facts=["person.marital_status"],
            )

    def test_str_literal_on_str_fact_accepted(self) -> None:
        compiled = _compile(
            {"op": "eq", "fact": "person.marital_status", "value": "MARRIED"},
            required_facts=["person.marital_status"],
        )
        assert compiled.rules[0].when.value == "MARRIED"


class TestDateTypedFactLiteralMustBeIsoString:
    def test_non_iso_string_on_date_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": "gt", "fact": "immigration.current_status_expiry", "value": "not-a-date"},
                required_facts=["immigration.current_status_expiry"],
            )

    def test_valid_iso_string_on_date_fact_accepted(self) -> None:
        compiled = _compile(
            {"op": "gt", "fact": "immigration.current_status_expiry", "value": "2027-01-01"},
            required_facts=["immigration.current_status_expiry"],
        )
        assert compiled.rules[0].when.value == "2027-01-01"


class TestOrderingOpsForbiddenOnBoolFacts:
    @pytest.mark.parametrize("op", ["lt", "lte", "gt", "gte"])
    def test_ordering_op_on_bool_fact_rejected(self, op: str) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": op, "fact": "commercial.wants_quote", "value": True},
                required_facts=["commercial.wants_quote"],
            )

    def test_between_on_bool_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {
                    "op": "between",
                    "fact": "commercial.wants_quote",
                    "lower": False,
                    "upper": True,
                },
                required_facts=["commercial.wants_quote"],
            )

    def test_eq_on_bool_fact_still_allowed(self) -> None:
        """eq/neq are NOT ordering ops — only lt/lte/gt/gte/between are
        forbidden on bool facts. Uses a non-commercial bool fact (F3 bans
        commercial-only facts in HARD_FILTER, which is orthogonal to this
        F1 ordering-ban check)."""

        compiled = _compile(
            {"op": "eq", "fact": "immigration.currently_in_indonesia", "value": True},
            required_facts=["immigration.currently_in_indonesia"],
        )
        assert compiled.rules[0].when.op == "eq"


class TestInNotInBetweenLiteralLists:
    def test_in_condition_with_all_matching_int_literals_accepted(self) -> None:
        compiled = _compile(
            {"op": "in", "fact": "intent.stay_days", "values": [10, 20, 30]},
            required_facts=["intent.stay_days"],
        )
        assert compiled.rules[0].when.values == (10, 20, 30)

    def test_in_condition_with_a_mismatched_literal_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": "in", "fact": "intent.stay_days", "values": ["10"]},
                required_facts=["intent.stay_days"],
            )

    def test_between_literal_type_checked_on_both_bounds(self) -> None:
        with pytest.raises(RulePackCompilationError):
            _compile(
                {"op": "between", "fact": "intent.stay_days", "lower": 1, "upper": "30"},
                required_facts=["intent.stay_days"],
            )

    def test_between_valid_int_bounds_accepted(self) -> None:
        compiled = _compile(
            {"op": "between", "fact": "intent.stay_days", "lower": 1, "upper": 30},
            required_facts=["intent.stay_days"],
        )
        assert (compiled.rules[0].when.lower, compiled.rules[0].when.upper) == (1, 30)
