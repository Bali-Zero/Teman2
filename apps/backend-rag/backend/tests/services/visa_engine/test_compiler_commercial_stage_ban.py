"""F3: commercial_only facts (commercial.service_fee_budget_idr,
commercial.wants_quote) must never influence a legal-eligibility decision —
binding decision §0.3. The existing compiler already forbade a RANKING rule
from referencing a legal (non-commercial) fact; F3 mirrors that ban in the
other direction: HARD_FILTER/ELIGIBILITY/HUMAN_REVIEW rules must never
reference a commercial_only fact.

Explicitly OUT of scope (reviewer's extra suggestion, declared skipped by
the orchestrator): rejecting "presence-only support rules" — no test here
covers that.
"""

from __future__ import annotations

import pytest

from backend.services.visa_engine.compiler import CompiledRulePack, compile_rule_pack
from backend.services.visa_engine.errors import RulePackCompilationError
from backend.services.visa_engine.fact_registry import FactRegistry
from backend.services.visa_engine.models import RulePack

from ._builders import single_rule_envelope


def _compile(*, stage: str, when: dict, required_facts: list[str]) -> CompiledRulePack:
    envelope = single_rule_envelope(when=when, stage=stage, required_facts=required_facts)
    pack = RulePack(**envelope)
    return compile_rule_pack(pack, fact_registry=FactRegistry())


class TestCommercialFactForbiddenInLegalStages:
    def test_hard_filter_referencing_commercial_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError, match="HARD_FILTER"):
            _compile(
                stage="HARD_FILTER",
                when={"op": "known", "fact": "commercial.wants_quote"},
                required_facts=["commercial.wants_quote"],
            )

    def test_eligibility_referencing_commercial_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError, match="ELIGIBILITY"):
            _compile(
                stage="ELIGIBILITY",
                when={"op": "known", "fact": "commercial.service_fee_budget_idr"},
                required_facts=["commercial.service_fee_budget_idr"],
            )

    def test_human_review_referencing_commercial_fact_rejected(self) -> None:
        with pytest.raises(RulePackCompilationError, match="HUMAN_REVIEW"):
            _compile(
                stage="HUMAN_REVIEW",
                when={"op": "known", "fact": "commercial.wants_quote"},
                required_facts=["commercial.wants_quote"],
            )


class TestLegalFactsStillAllowedInLegalStages:
    def test_hard_filter_referencing_legal_fact_accepted(self) -> None:
        compiled = _compile(
            stage="HARD_FILTER",
            when={"op": "gt", "fact": "immigration.overstay_days", "value": 60},
            required_facts=["immigration.overstay_days"],
        )
        assert len(compiled.rules) == 1
        assert compiled.rules[0].referenced_facts == frozenset({"immigration.overstay_days"})

    def test_eligibility_referencing_legal_fact_accepted(self) -> None:
        compiled = _compile(
            stage="ELIGIBILITY",
            when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
            required_facts=["intent.purposes"],
        )
        assert len(compiled.rules) == 1
        assert compiled.rules[0].referenced_facts == frozenset({"intent.purposes"})
