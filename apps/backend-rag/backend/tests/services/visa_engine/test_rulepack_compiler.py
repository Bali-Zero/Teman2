"""Tests for ``backend.services.visa_engine.compiler``.

One guilt test per ``CompilationError`` code the compiler can emit, plus one
innocence test (a minimal valid pack compiles with zero errors) — per the
PR1 task brief. Every guilt fixture is built by taking the shared
``minimal_valid_pack`` fixture (already innocent) and mutating exactly the
one thing under test, so a failing assertion localizes to a single cause.
"""

from __future__ import annotations

import uuid

from backend.services.visa_engine import compiler as C
from backend.services.visa_engine import models as M
from backend.tests.services.visa_engine.conftest import (
    GOLD_EFFECTIVE_AT,
    make_product,
    make_rule_pack,
    make_rule_pack_payload,
    make_source_record,
    make_support_rule,
)

_OPEN_PERIOD = {"from": GOLD_EFFECTIVE_AT, "to": None}


class TestInnocence:
    def test_minimal_valid_pack_compiles_clean(self, minimal_valid_pack: M.RulePack) -> None:
        report = C.compile_rule_pack(minimal_valid_pack)
        assert report.ok, report.errors
        assert report.errors == ()
        assert report.sequence == 1

    def test_report_carries_rule_pack_id(self, minimal_valid_pack: M.RulePack) -> None:
        report = C.compile_rule_pack(minimal_valid_pack)
        assert report.rule_pack_id == str(minimal_valid_pack.payload.rule_pack_id)


class TestAstLimitExceeded:
    def test_oversized_condition_reported(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        deep_condition: dict = {"op": "known", "fact": "person.birth_date"}
        for _ in range(13):  # depth 14, over the 12-deep limit
            deep_condition = {"op": "not", "arg": deep_condition}
        rule = M.Rule(
            rule_id="rule.too_deep",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            priority=100,
            valid_period=_OPEN_PERIOD,
            when=deep_condition,
            effect={"type": "SUPPORT", "reason_code": "X", "covered_purposes": ["TOURISM"]},
            on_unknown="NEEDS_INPUT",
            required_facts=["person.birth_date"],
            source_refs=[source_record.source_record_id],
            explanation_key="explain.deep",
            safety_critical=False,
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "AST_LIMIT_EXCEEDED" for e in report.errors)


class TestRequiredFactsMismatch:
    def test_missing_declared_fact_reported(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.mismatch.missing",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            required_facts=(),  # `when` references intent.purposes but required_facts is empty
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "REQUIRED_FACTS_MISMATCH" for e in report.errors)

    def test_extra_declared_fact_reported(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.mismatch.extra",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            required_facts=("intent.purposes", "study.level"),  # study.level never referenced
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "REQUIRED_FACTS_MISMATCH" for e in report.errors)


class TestNoCommercialFactInLegalStage:
    def test_hard_filter_rule_using_commercial_fact_reported(
        self, minimal_valid_pack: M.RulePack, source_record: M.SourceRecord
    ) -> None:
        hf_rule = M.Rule(
            rule_id="rule.hf.commercial",
            stage="HARD_FILTER",
            scope="GLOBAL",
            product_version_ids=None,
            priority=10,
            valid_period=_OPEN_PERIOD,
            when={"op": "gt", "fact": "commercial.service_fee_budget_idr", "value": 100},
            effect={"type": "EXCLUDE", "reason_code": "TOO_CHEAP"},
            on_unknown="NO_EFFECT",
            required_facts=["commercial.service_fee_budget_idr"],
            source_refs=[source_record.source_record_id],
            explanation_key="explain.hf",
            safety_critical=True,
        )
        rules = [*minimal_valid_pack.payload.rules, hf_rule]
        payload = make_rule_pack_payload(
            rules=rules,
            products=minimal_valid_pack.payload.products,
            source_records=minimal_valid_pack.payload.source_records,
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "COMMERCIAL_FACT_IN_LEGAL_STAGE" for e in report.errors)


class TestRankingRuleUsesLegalFact:
    def test_ranking_rule_referencing_legal_fact_reported(
        self, minimal_valid_pack: M.RulePack, source_record: M.SourceRecord
    ) -> None:
        rank_rule = M.Rule(
            rule_id="rule.ranking.legal",
            stage="RANKING",
            scope="GLOBAL",
            product_version_ids=None,
            priority=10,
            valid_period=_OPEN_PERIOD,
            when={"op": "known", "fact": "person.birth_date"},
            effect={"type": "ADD_SCORE", "reason_code": "PREFERRED", "points": 5},
            on_unknown="NO_EFFECT",
            required_facts=["person.birth_date"],
            source_refs=[source_record.source_record_id],
            explanation_key="explain.rank",
            safety_critical=False,
        )
        rules = [*minimal_valid_pack.payload.rules, rank_rule]
        payload = make_rule_pack_payload(
            rules=rules,
            products=minimal_valid_pack.payload.products,
            source_records=minimal_valid_pack.payload.source_records,
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "RANKING_RULE_USES_LEGAL_FACT" for e in report.errors)

    def test_ranking_rule_using_commercial_fact_is_innocent(
        self, minimal_valid_pack: M.RulePack, source_record: M.SourceRecord
    ) -> None:
        rank_rule = M.Rule(
            rule_id="rule.ranking.commercial",
            stage="RANKING",
            scope="GLOBAL",
            product_version_ids=None,
            priority=10,
            valid_period=_OPEN_PERIOD,
            when={"op": "gt", "fact": "commercial.service_fee_budget_idr", "value": 0},
            effect={"type": "ADD_SCORE", "reason_code": "PREFERRED", "points": 5},
            on_unknown="NO_EFFECT",
            required_facts=["commercial.service_fee_budget_idr"],
            source_refs=[source_record.source_record_id],
            explanation_key="explain.rank2",
            safety_critical=False,
        )
        rules = [*minimal_valid_pack.payload.rules, rank_rule]
        payload = make_rule_pack_payload(
            rules=rules,
            products=minimal_valid_pack.payload.products,
            source_records=minimal_valid_pack.payload.source_records,
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert not any(e.code == "RANKING_RULE_USES_LEGAL_FACT" for e in report.errors)


class TestEligibilityPresenceOnly:
    def test_presence_only_eligibility_rule_reported(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.presence.only",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "known", "fact": "intent.purposes"},
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "ELIGIBILITY_RULE_PRESENCE_ONLY" for e in report.errors)

    def test_comparison_based_eligibility_rule_is_innocent(
        self, minimal_valid_pack: M.RulePack
    ) -> None:
        report = C.compile_rule_pack(minimal_valid_pack)
        assert not any(e.code == "ELIGIBILITY_RULE_PRESENCE_ONLY" for e in report.errors)


class TestFactLiteralKindMismatch:
    def test_eq_against_set_valued_fact_reported(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.kind.mismatch",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "eq", "fact": "intent.purposes", "value": "TOURISM"},
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "FACT_LITERAL_KIND_MISMATCH" for e in report.errors)

    def test_ordering_against_boolean_fact_reported(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = M.Rule(
            rule_id="rule.bool.ordering",
            stage="HARD_FILTER",
            scope="GLOBAL",
            product_version_ids=None,
            priority=10,
            valid_period=_OPEN_PERIOD,
            when={"op": "gt", "fact": "immigration.currently_in_indonesia", "value": 1},
            effect={"type": "EXCLUDE", "reason_code": "X"},
            on_unknown="NO_EFFECT",
            required_facts=["immigration.currently_in_indonesia"],
            source_refs=[source_record.source_record_id],
            explanation_key="explain.bool",
            safety_critical=True,
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "FACT_LITERAL_KIND_MISMATCH" for e in report.errors)


class TestUnknownProductReference:
    def test_rule_referencing_unknown_product_reported(
        self, minimal_valid_pack: M.RulePack, source_record: M.SourceRecord
    ) -> None:
        rogue_rule = make_support_rule(
            rule_id="rule.rogue.product",
            product_version_ids=[uuid.uuid4()],  # not in payload.products
            source_refs=[source_record.source_record_id],
        )
        rules = [*minimal_valid_pack.payload.rules, rogue_rule]
        payload = make_rule_pack_payload(
            rules=rules,
            products=minimal_valid_pack.payload.products,
            source_records=minimal_valid_pack.payload.source_records,
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "UNKNOWN_PRODUCT_REFERENCE" for e in report.errors)


class TestUnknownSourceReference:
    def test_rule_referencing_unknown_source_reported(
        self, minimal_valid_pack: M.RulePack, source_record: M.SourceRecord
    ) -> None:
        product_id = minimal_valid_pack.payload.products[0].product_version_id
        rogue_rule = make_support_rule(
            rule_id="rule.rogue.source",
            product_version_ids=[product_id],
            source_refs=[uuid.uuid4()],  # not in payload.source_records
        )
        rules = [*minimal_valid_pack.payload.rules, rogue_rule]
        payload = make_rule_pack_payload(
            rules=rules,
            products=minimal_valid_pack.payload.products,
            source_records=minimal_valid_pack.payload.source_records,
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "UNKNOWN_SOURCE_REFERENCE" for e in report.errors)

    def test_product_referencing_unknown_source_reported(
        self, source_record: M.SourceRecord
    ) -> None:
        product_id = uuid.uuid4()
        rogue_product = make_product(
            product_version_id=product_id,
            source_refs=[uuid.uuid4()],  # not in source_records
        )
        rule = make_support_rule(
            rule_id="rule.for.rogue.product",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[rogue_product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(
            e.code == "UNKNOWN_SOURCE_REFERENCE" and e.product_code == "C1" for e in report.errors
        )


class TestSupportRulePurposeNotOnProduct:
    def test_support_rule_claiming_uncovered_purpose_reported(
        self, source_record: M.SourceRecord
    ) -> None:
        product_id = uuid.uuid4()
        # product only covers TOURISM
        product = make_product(
            product_version_id=product_id,
            source_refs=[source_record.source_record_id],
            covered_purposes=["TOURISM"],
        )
        rule = make_support_rule(
            rule_id="rule.claims.employment",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            covered_purposes=["EMPLOYMENT"],  # not on the product
            when={"op": "intersects", "fact": "intent.purposes", "values": ["EMPLOYMENT"]},
            required_facts=("intent.purposes",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "SUPPORT_RULE_PURPOSE_NOT_ON_PRODUCT" for e in report.errors)


class TestEnvironmentMismatch:
    def test_header_environment_mismatch_reported(self, minimal_valid_pack: M.RulePack) -> None:
        # protected.environment=STAGING while payload.environment stays TEST
        # would already fail Pydantic's own RulePack validator, so exercise
        # the compiler's independent re-check directly via model_construct
        # (bypassing validation), matching the defense-in-depth rationale
        # documented in compiler.py.
        tampered_protected = minimal_valid_pack.protected.model_copy(
            update={"environment": "STAGING"}
        )
        tampered_pack = M.RulePack.model_construct(
            canonicalization=minimal_valid_pack.canonicalization,
            protected=tampered_protected,
            payload=minimal_valid_pack.payload,
            payload_sha256=minimal_valid_pack.payload_sha256,
            signature=minimal_valid_pack.signature,
        )
        report = C.compile_rule_pack(tampered_pack)
        assert any(e.code == "ENVIRONMENT_MISMATCH" for e in report.errors)


class TestRequiredFactNotInRegistry:
    def test_unknown_registry_fact_reported(self) -> None:
        from backend.services.visa_engine.enums import FactPath, FactValueKind
        from backend.services.visa_engine.fact_registry import FactRegistry, FactSpec

        narrow_registry = FactRegistry(
            [
                FactSpec(
                    path=FactPath.INTENT_PURPOSES,
                    kind=FactValueKind.STRING_SET,
                    value_type="visa_purpose_set",
                    derived=False,
                )
            ]
        )
        source_record = make_source_record()
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        # required_facts references study.level, which the narrow registry does not know
        rule = M.Rule(
            rule_id="rule.unknown.registry.fact",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_version_ids=[product_id],
            priority=100,
            valid_period=_OPEN_PERIOD,
            when={
                "op": "all",
                "args": [
                    {"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
                    {"op": "known", "fact": "study.level"},
                ],
            },
            effect={"type": "SUPPORT", "reason_code": "X", "covered_purposes": ["TOURISM"]},
            on_unknown="NEEDS_INPUT",
            required_facts=["intent.purposes", "study.level"],
            source_refs=[source_record.source_record_id],
            explanation_key="explain.narrow",
            safety_critical=False,
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload), fact_registry=narrow_registry)
        assert any(e.code == "REQUIRED_FACT_NOT_IN_REGISTRY" for e in report.errors)
