"""Tests for ``backend.services.visa_engine.compiler``.

One guilt test per ``CompilationError`` code the compiler can emit, plus one
innocence test (a minimal valid pack compiles with zero errors) — per the
PR1 task brief. Every guilt fixture is built by taking the shared
``minimal_valid_pack`` fixture (already innocent) and mutating exactly the
one thing under test, so a failing assertion localizes to a single cause.

PR1 hardening round (Codex findings 5/6/7/8/9) additions at the bottom of
this file: the rewritten fact-literal-kind semantics (finding 5), the
bypass-proof re-validation/cycle-safety/uniqueness/UTC/NFC checks
(findings 6+8+9), and the SUPPORT-purpose vacuous-truth + GLOBAL-rule gaps
(finding 7) — every one exercised via ``model_construct``/``object.
__setattr__`` where the defect can only be reached by bypassing normal
Pydantic construction, matching the "bypass-proof by design" rationale
documented in ``compiler.py``.
"""

from __future__ import annotations

import uuid

from backend.services.visa_engine import ast as A
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


# ---------------------------------------------------------------------------
# Codex finding 5 — corrected fact-literal-kind semantics
# ---------------------------------------------------------------------------


class TestFactLiteralKindCorrectedSemantics:
    def test_in_valid_scalar_membership_is_innocent(self, source_record: M.SourceRecord) -> None:
        # Exact orchestrator example: `marital_status in [SINGLE, MARRIED]`
        # is a SCALAR membership test over a STRING-kind fact — valid.
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.in.scalar.valid",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={
                "op": "in",
                "fact": "person.marital_status",
                "values": ["SINGLE", "MARRIED"],
            },
            required_facts=("person.marital_status",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert not any(e.code.startswith("FACT_LITERAL") for e in report.errors)

    def test_in_against_set_valued_fact_now_guilty(self, source_record: M.SourceRecord) -> None:
        # Reversed semantics (finding 5): `in`/`not_in` against a
        # STRING_SET-kind fact (intent.purposes) is now the WRONG operator
        # (use `intersects`/`contains_all` instead) — the old PR1 code had
        # this backwards.
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.in.set.invalid",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "in", "fact": "intent.purposes", "values": ["TOURISM"]},
            required_facts=("intent.purposes",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "FACT_LITERAL_KIND_MISMATCH" for e in report.errors)

    def test_intersects_valid_against_set_fact_is_innocent(
        self, minimal_valid_pack: M.RulePack
    ) -> None:
        # minimal_valid_pack's own rule uses `intersects` against
        # `intent.purposes` — this is the innocence half of the reversed
        # semantics above.
        report = C.compile_rule_pack(minimal_valid_pack)
        assert not any(e.code.startswith("FACT_LITERAL") for e in report.errors)

    def test_string_literal_against_integer_fact_guilty(
        self, source_record: M.SourceRecord
    ) -> None:
        # Exact orchestrator example: `age == "30"` — a STRING literal
        # against an INTEGER-kind fact.
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.literal.kind.mismatch",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "eq", "fact": "immigration.overstay_days", "value": "30"},
            required_facts=("immigration.overstay_days",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "FACT_LITERAL_KIND_MISMATCH" for e in report.errors)

    def test_allowed_value_violation_guilty(self, source_record: M.SourceRecord) -> None:
        # Exact orchestrator example: `marital_status == "NOT_A_STATUS"`.
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.allowed.values.violation",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "eq", "fact": "person.marital_status", "value": "NOT_A_STATUS"},
            required_facts=("person.marital_status",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "FACT_LITERAL_NOT_ALLOWED" for e in report.errors)

    def test_allowed_value_valid_is_innocent(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.allowed.values.valid",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "eq", "fact": "person.marital_status", "value": "MARRIED"},
            required_facts=("person.marital_status",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert not any(e.code.startswith("FACT_LITERAL") for e in report.errors)

    def test_between_bounds_kind_mismatch_guilty(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.between.kind.mismatch",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={
                "op": "between",
                "fact": "immigration.overstay_days",
                "lower": "0",
                "upper": 10,
            },
            required_facts=("immigration.overstay_days",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "FACT_LITERAL_KIND_MISMATCH" for e in report.errors)

    def test_between_bounds_inverted_guilty(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.between.inverted",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={
                "op": "between",
                "fact": "immigration.overstay_days",
                "lower": 90,
                "upper": 10,
            },
            required_facts=("immigration.overstay_days",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "BETWEEN_BOUNDS_INVERTED" for e in report.errors)

    def test_between_valid_is_innocent(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.between.valid",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={
                "op": "between",
                "fact": "immigration.overstay_days",
                "lower": 0,
                "upper": 30,
            },
            required_facts=("immigration.overstay_days",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert not any(e.code.startswith(("FACT_LITERAL", "BETWEEN")) for e in report.errors)


# ---------------------------------------------------------------------------
# Codex findings 6+8 — structural safety net / bypass-proofing
# ---------------------------------------------------------------------------


class TestStructuralRevalidationAndCycleSafety:
    def test_model_construct_bad_environment_type_never_crashes(
        self, minimal_valid_pack: M.RulePack
    ) -> None:
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
        report = C.compile_rule_pack(tampered_pack)  # must not raise
        assert any(e.code == "ENVIRONMENT_MISMATCH" for e in report.errors)

    def test_cyclic_condition_tree_reported_not_crashed(
        self, source_record: M.SourceRecord
    ) -> None:
        # Codex's exact counterexample class: a self-referential AST node
        # built via `object.__setattr__` (bypassing the frozen-model write
        # guard) must be reported as a `CompilationError`, never raise
        # `RecursionError` out of `compile_rule_pack`.
        leaf = A.parse_condition({"op": "known", "fact": "person.birth_date"})
        cyclic = A.NotCondition(op="not", arg=leaf)
        object.__setattr__(cyclic, "arg", cyclic)

        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.cyclic",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when=cyclic,
            required_facts=(),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        pack = make_rule_pack(payload)

        report = C.compile_rule_pack(pack)  # must not raise RecursionError
        assert not report.ok
        assert any(
            e.code
            in (
                "PACK_FAILS_STRUCTURAL_REVALIDATION",
                "AST_LIMIT_EXCEEDED",
                "MALFORMED_CONDITION_TREE",
            )
            for e in report.errors
        )

    def test_degenerate_all_args_empty_via_bypass_never_crashes(
        self, source_record: M.SourceRecord
    ) -> None:
        # `AllCondition(args=())` bypasses `Field(..., min_length=1)` only
        # via `model_construct`.
        degenerate = A.AllCondition.model_construct(op="all", args=())
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.degenerate.all",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when=degenerate,
            required_facts=(),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))  # must not raise
        assert not report.ok


class TestBypassProofRedundantChecks:
    def test_duplicate_rule_id_bypass_reported(self, minimal_valid_pack: M.RulePack) -> None:
        rule = minimal_valid_pack.payload.rules[0]
        payload = minimal_valid_pack.payload.model_construct(
            **{**minimal_valid_pack.payload.__dict__, "rules": (rule, rule)}
        )
        pack = minimal_valid_pack.model_construct(
            **{**minimal_valid_pack.__dict__, "payload": payload}
        )
        report = C.compile_rule_pack(pack)
        assert any(e.code == "DUPLICATE_RULE_ID" for e in report.errors)

    def test_non_utc_datetime_bypass_reported(self, minimal_valid_pack: M.RulePack) -> None:
        import datetime as dt

        naive_payload = minimal_valid_pack.payload.model_construct(
            **{**minimal_valid_pack.payload.__dict__, "created_at": dt.datetime(2026, 7, 17)}
        )
        pack = minimal_valid_pack.model_construct(
            **{**minimal_valid_pack.__dict__, "payload": naive_payload}
        )
        report = C.compile_rule_pack(pack)
        assert any(e.code == "NON_UTC_DATETIME" for e in report.errors)

    def test_non_nfc_string_bypass_reported(self, minimal_valid_pack: M.RulePack) -> None:
        import unicodedata

        # "é" as NFD (e + combining acute accent) vs NFC (single codepoint)
        # — visually identical, byte-distinct.
        nfd_name = unicodedata.normalize("NFD", "café")
        assert nfd_name != unicodedata.normalize("NFC", nfd_name)

        naive_payload = minimal_valid_pack.payload.model_construct(
            **{**minimal_valid_pack.payload.__dict__, "created_by": nfd_name}
        )
        pack = minimal_valid_pack.model_construct(
            **{**minimal_valid_pack.__dict__, "payload": naive_payload}
        )
        report = C.compile_rule_pack(pack)
        assert any(e.code == "NON_NFC_STRING" for e in report.errors)

    def test_pack_size_limit_rules_exceeded_reported(
        self, minimal_valid_pack: M.RulePack, monkeypatch
    ) -> None:
        monkeypatch.setattr(C, "_MAX_RULES", 0)
        report = C.compile_rule_pack(minimal_valid_pack)
        assert any(e.code == "TOO_MANY_RULES" for e in report.errors)

    def test_pack_size_limit_products_exceeded_reported(
        self, minimal_valid_pack: M.RulePack, monkeypatch
    ) -> None:
        monkeypatch.setattr(C, "_MAX_PRODUCTS", 0)
        report = C.compile_rule_pack(minimal_valid_pack)
        assert any(e.code == "TOO_MANY_PRODUCTS" for e in report.errors)


# ---------------------------------------------------------------------------
# Codex finding 7 — SUPPORT-purpose vacuous-truth + GLOBAL-rule gaps
# ---------------------------------------------------------------------------


class TestSupportPurposeCoverageFixed:
    def test_empty_covered_purposes_bypass_reported(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        empty_effect = M.EffectSupport.model_construct(
            type="SUPPORT", reason_code="X", covered_purposes=()
        )
        rule = make_support_rule(
            rule_id="rule.empty.covered.purposes",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
        )
        rule = rule.model_construct(**{**rule.__dict__, "effect": empty_effect})
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "SUPPORT_RULE_EMPTY_COVERED_PURPOSES" for e in report.errors)

    def test_global_support_rule_claiming_unsupported_purpose_reported(
        self, source_record: M.SourceRecord
    ) -> None:
        # Codex's exact counterexample: a GLOBAL-scope SUPPORT rule (no
        # product_version_ids) used to be skipped entirely by `continue`.
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id,
            source_refs=[source_record.source_record_id],
            covered_purposes=["TOURISM"],
        )
        global_rule = M.Rule(
            rule_id="rule.global.support.invalid",
            stage="ELIGIBILITY",
            scope="GLOBAL",
            product_version_ids=None,
            priority=100,
            valid_period=_OPEN_PERIOD,
            when={"op": "intersects", "fact": "intent.purposes", "values": ["EMPLOYMENT"]},
            effect={
                "type": "SUPPORT",
                "reason_code": "X",
                "covered_purposes": ["EMPLOYMENT"],
            },
            on_unknown="NEEDS_INPUT",
            required_facts=["intent.purposes"],
            source_refs=[source_record.source_record_id],
            explanation_key="explain.global",
            safety_critical=False,
        )
        payload = make_rule_pack_payload(
            rules=[global_rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "SUPPORT_RULE_PURPOSE_NOT_ON_ANY_PRODUCT" for e in report.errors)

    def test_global_support_rule_claiming_covered_purpose_is_innocent(
        self, source_record: M.SourceRecord
    ) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id,
            source_refs=[source_record.source_record_id],
            covered_purposes=["TOURISM"],
        )
        global_rule = M.Rule(
            rule_id="rule.global.support.valid",
            stage="ELIGIBILITY",
            scope="GLOBAL",
            product_version_ids=None,
            priority=100,
            valid_period=_OPEN_PERIOD,
            when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
            effect={
                "type": "SUPPORT",
                "reason_code": "X",
                "covered_purposes": ["TOURISM"],
            },
            on_unknown="NEEDS_INPUT",
            required_facts=["intent.purposes"],
            source_refs=[source_record.source_record_id],
            explanation_key="explain.global.valid",
            safety_critical=False,
        )
        payload = make_rule_pack_payload(
            rules=[global_rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert not any(e.code.startswith("SUPPORT_RULE") for e in report.errors)
