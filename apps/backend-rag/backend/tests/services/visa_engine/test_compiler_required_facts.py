"""F8: when a Rule declares `required_facts`, the compiler must enforce
`frozenset(rule.required_facts) == collect_fact_paths(rule.when)` exactly —
never silently substitute the AST's real fact set for a mismatched
declaration (a subset OR a superset are both rejected).
"""

from __future__ import annotations

import pytest

from backend.services.visa_engine.compiler import CompiledRulePack, compile_rule_pack
from backend.services.visa_engine.errors import RulePackCompilationError
from backend.services.visa_engine.fact_registry import FactRegistry
from backend.services.visa_engine.models import RulePack

from ._builders import single_rule_envelope

_WHEN = {"op": "gt", "fact": "immigration.overstay_days", "value": 60}


def _compile(required_facts: list[str]) -> CompiledRulePack:
    envelope = single_rule_envelope(when=_WHEN, required_facts=required_facts)
    pack = RulePack(**envelope)
    return compile_rule_pack(pack, fact_registry=FactRegistry())


def test_exact_match_compiles() -> None:
    compiled = _compile(["immigration.overstay_days"])
    assert compiled.rules[0].referenced_facts == frozenset({"immigration.overstay_days"})


def test_superset_required_facts_rejected() -> None:
    with pytest.raises(RulePackCompilationError, match="required_facts"):
        _compile(["immigration.overstay_days", "intent.stay_days"])


def test_subset_required_facts_rejected() -> None:
    """An empty declaration is the degenerate subset case."""

    with pytest.raises(RulePackCompilationError, match="required_facts"):
        _compile([])


def test_disjoint_required_facts_rejected() -> None:
    with pytest.raises(RulePackCompilationError, match="required_facts"):
        _compile(["intent.stay_days"])


def test_composite_condition_required_facts_must_cover_every_leaf() -> None:
    envelope = single_rule_envelope(
        when={
            "op": "all",
            "args": [
                {"op": "gt", "fact": "immigration.overstay_days", "value": 60},
                {"op": "known", "fact": "intent.stay_days"},
            ],
        },
        required_facts=["immigration.overstay_days"],  # missing intent.stay_days
    )
    pack = RulePack(**envelope)
    with pytest.raises(RulePackCompilationError, match="required_facts"):
        compile_rule_pack(pack, fact_registry=FactRegistry())
