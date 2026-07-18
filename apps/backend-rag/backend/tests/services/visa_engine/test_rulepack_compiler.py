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
        # would already fail Pydantic's own RulePack validator
        # (RulePack._check_header_environment, models.py), so the only way to
        # get a mismatched pack at all is model_construct (bypassing
        # validation). Round 3 (fail-stop): compile_rule_pack's structural
        # revalidation gate round-trips the WHOLE pack through
        # model_dump(mode="json") -> RulePack.model_validate(...), which
        # re-runs that exact model_validator — so the mismatch is now caught
        # at the revalidation gate, and compile_rule_pack stops there. The
        # compiler's own `_check_header_environment` never gets a chance to
        # run (and, per its updated docstring, never will for ANY
        # successfully-revalidated pack — it stays only as documented
        # defense-in-depth for a hypothetical relaxed model validator).
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
        assert not report.ok
        assert any(e.code == "PACK_FAILS_STRUCTURAL_REVALIDATION" for e in report.errors)


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
        # Round 3 (fail-stop): caught at the revalidation gate, not by the
        # compiler's own header/environment re-check — see
        # TestEnvironmentMismatch's updated comment for the full rationale.
        assert any(e.code == "PACK_FAILS_STRUCTURAL_REVALIDATION" for e in report.errors)

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
    """Round 3 note: with ``compile_rule_pack``'s fail-stop revalidation gate
    (see that function's docstring), every bypass technique below that also
    violates a ``models.py``-level invariant is now caught AT the
    revalidation gate — ``PACK_FAILS_STRUCTURAL_REVALIDATION`` alone, never
    the compiler's own more-specific code — because
    ``_revalidate_structurally`` round-trips the ENTIRE pack through
    ``model_dump(mode="json") -> RulePack.model_validate(...)``, which
    re-parses every nested model from a plain dict (no model-instance
    identity survives) and therefore re-runs every field/model validator the
    bypass skipped. The ``NON_NFC_STRING``/NFC case moved to
    ``TestNfcUtcGenericWalker`` below: NFC-normalization is NOT enforced by
    any ``models.py`` validator, so it remains genuinely reachable post-
    fail-stop for a NORMALLY-constructed (non-bypass) pack.
    """

    def test_duplicate_rule_id_bypass_reported(self, minimal_valid_pack: M.RulePack) -> None:
        # RulePackPayload._check_unique_rule_ids (models.py field_validator)
        # enforces this — the bypass is only reachable via model_construct,
        # and the revalidation gate re-runs that exact validator on re-parse.
        rule = minimal_valid_pack.payload.rules[0]
        payload = minimal_valid_pack.payload.model_construct(
            **{**minimal_valid_pack.payload.__dict__, "rules": (rule, rule)}
        )
        pack = minimal_valid_pack.model_construct(
            **{**minimal_valid_pack.__dict__, "payload": payload}
        )
        report = C.compile_rule_pack(pack)  # must not raise
        assert any(e.code == "PACK_FAILS_STRUCTURAL_REVALIDATION" for e in report.errors)

    def test_non_utc_datetime_bypass_reported(self, minimal_valid_pack: M.RulePack) -> None:
        # RulePackPayload._check_utc / _validate_utc (models.py
        # field_validator on created_at) enforces this — same fail-stop
        # rationale as the duplicate-rule-id case above.
        import datetime as dt

        naive_payload = minimal_valid_pack.payload.model_construct(
            **{**minimal_valid_pack.payload.__dict__, "created_at": dt.datetime(2026, 7, 17)}
        )
        pack = minimal_valid_pack.model_construct(
            **{**minimal_valid_pack.__dict__, "payload": naive_payload}
        )
        report = C.compile_rule_pack(pack)  # must not raise
        assert any(e.code == "PACK_FAILS_STRUCTURAL_REVALIDATION" for e in report.errors)

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
        # EffectSupport.covered_purposes carries Field(..., min_length=1)
        # (models.py) — the bypass is only reachable via model_construct, and
        # round 3's fail-stop revalidation gate re-runs that exact
        # constraint on re-parse, so the report now carries
        # PACK_FAILS_STRUCTURAL_REVALIDATION alone (never
        # SUPPORT_RULE_EMPTY_COVERED_PURPOSES — the compiler's own check
        # never gets a chance to run against an unproven pack).
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
        report = C.compile_rule_pack(make_rule_pack(payload))  # must not raise
        assert any(e.code == "PACK_FAILS_STRUCTURAL_REVALIDATION" for e in report.errors)

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


# ---------------------------------------------------------------------------
# Round 3 (Codex round-2 re-review HIGH finding) — GLOBAL SUPPORT rule
# purpose coverage must use the INTERSECTION of every product's
# covered_purposes, not their union: a GLOBAL rule structurally applies to
# EVERY product, so its claim must hold for ALL of them, not just one.
# ---------------------------------------------------------------------------


class TestGlobalSupportPurposeIntersectionSemantics:
    def test_global_support_purpose_not_common_to_all_products_reported(
        self, source_record: M.SourceRecord
    ) -> None:
        # Exact orchestrator/Codex counterexample: products {C1: TOURISM,
        # E23: EMPLOYMENT} + a GLOBAL SUPPORT rule claiming {TOURISM}. Round
        # 2's union test wrongly let this pass (TOURISM is in the union) —
        # but the rule structurally also applies to E23, which does not
        # cover TOURISM, so this must be a compile error under intersection
        # semantics.
        c1_id = uuid.uuid4()
        e23_id = uuid.uuid4()
        c1 = make_product(
            product_version_id=c1_id,
            product_code="C1",
            source_refs=[source_record.source_record_id],
            covered_purposes=["TOURISM"],
        )
        e23 = make_product(
            product_version_id=e23_id,
            product_code="E23",
            source_refs=[source_record.source_record_id],
            covered_purposes=["EMPLOYMENT"],
        )
        global_rule = M.Rule(
            rule_id="rule.global.intersection.guilty",
            stage="ELIGIBILITY",
            scope="GLOBAL",
            product_version_ids=None,
            priority=100,
            valid_period=_OPEN_PERIOD,
            when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
            effect={"type": "SUPPORT", "reason_code": "X", "covered_purposes": ["TOURISM"]},
            on_unknown="NEEDS_INPUT",
            required_facts=["intent.purposes"],
            source_refs=[source_record.source_record_id],
            explanation_key="explain.global.intersection.guilty",
            safety_critical=False,
        )
        payload = make_rule_pack_payload(
            rules=[global_rule], products=[c1, e23], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "SUPPORT_RULE_PURPOSE_NOT_ON_ANY_PRODUCT" for e in report.errors)

    def test_global_support_purpose_common_to_all_products_is_innocent(
        self, source_record: M.SourceRecord
    ) -> None:
        # Innocence half: every product shares TOURISM, and the GLOBAL rule
        # claims only TOURISM — valid under both union AND intersection
        # semantics.
        c1_id = uuid.uuid4()
        e23_id = uuid.uuid4()
        c1 = make_product(
            product_version_id=c1_id,
            product_code="C1",
            source_refs=[source_record.source_record_id],
            covered_purposes=["TOURISM"],
        )
        e23 = make_product(
            product_version_id=e23_id,
            product_code="E23",
            source_refs=[source_record.source_record_id],
            covered_purposes=["TOURISM", "EMPLOYMENT"],
        )
        global_rule = M.Rule(
            rule_id="rule.global.intersection.innocent",
            stage="ELIGIBILITY",
            scope="GLOBAL",
            product_version_ids=None,
            priority=100,
            valid_period=_OPEN_PERIOD,
            when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
            effect={"type": "SUPPORT", "reason_code": "X", "covered_purposes": ["TOURISM"]},
            on_unknown="NEEDS_INPUT",
            required_facts=["intent.purposes"],
            source_refs=[source_record.source_record_id],
            explanation_key="explain.global.intersection.innocent",
            safety_critical=False,
        )
        payload = make_rule_pack_payload(
            rules=[global_rule], products=[c1, e23], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert not any(e.code.startswith("SUPPORT_RULE") for e in report.errors)

    def test_global_support_zero_products_guard_unit_level(
        self, source_record: M.SourceRecord
    ) -> None:
        # RulePackPayload.products carries Field(..., min_length=1) — a
        # normally-constructed payload can never have zero products, and
        # even a model_construct-bypassed one would be caught by
        # compile_rule_pack's fail-stop revalidation gate before reaching
        # this check at all (min_length=1 is re-enforced on re-parse). The
        # `if payload.products else frozenset()` guard in
        # _check_support_purposes_on_product (avoiding a TypeError from
        # frozenset.intersection(*()) on empty args) is therefore only
        # reachable by calling the check function directly — exercised here
        # at the unit level so the guard itself stays covered.
        global_rule = M.Rule(
            rule_id="rule.global.zero.products",
            stage="ELIGIBILITY",
            scope="GLOBAL",
            product_version_ids=None,
            priority=100,
            valid_period=_OPEN_PERIOD,
            when={"op": "intersects", "fact": "intent.purposes", "values": ["TOURISM"]},
            effect={"type": "SUPPORT", "reason_code": "X", "covered_purposes": ["TOURISM"]},
            on_unknown="NEEDS_INPUT",
            required_facts=["intent.purposes"],
            source_refs=[source_record.source_record_id],
            explanation_key="explain.global.zero.products",
            safety_critical=False,
        )
        empty_products_payload = M.RulePackPayload.model_construct(
            rule_pack_id=uuid.uuid4(),
            sequence=1,
            version="1.0.0",
            environment="TEST",
            jurisdiction="ID",
            decision_domain="IMMIGRATION_VISA",
            engine_contract_version="1.0.0",
            engine_min_version="1.0.0",
            engine_max_version="1.0.0",
            valid_period=_OPEN_PERIOD,
            created_at=GOLD_EFFECTIVE_AT,
            created_by="pipeline.compiler",
            previous_payload_sha256=None,
            rollback_of_payload_sha256=None,
            hit_policy=M.HitPolicyDeclaration(
                hard_filter="COLLECT_ALL",
                eligibility="COVER_ALL_DECLARED_PURPOSES",
                human_review="COLLECT_ALL",
                ranking="SUM_TRUE_INTEGER_WEIGHTS",
            ),
            source_records=(source_record,),
            products=(),  # only reachable via model_construct — see docstring above
            rules=(global_rule,),
        )
        errors: list[C.CompilationError] = []
        C._check_support_purposes_on_product(empty_products_payload, errors)  # must not raise
        assert any(e.code == "SUPPORT_RULE_PURPOSE_NOT_ON_ANY_PRODUCT" for e in errors)


# ---------------------------------------------------------------------------
# Round 3 (Codex round-2 re-review NEW HIGH finding) — fail-stop
# revalidation: compile_rule_pack must never raise, even when a
# `model_copy(update=...)`-tampered structural field (here: `rule.stage`)
# would otherwise reach a dict lookup keyed by the real enum.
# ---------------------------------------------------------------------------


class TestFailStopRevalidation:
    def test_bogus_stage_model_copy_never_crashes_reports_clean_error(
        self, minimal_valid_pack: M.RulePack
    ) -> None:
        # Codex's exact counterexample: rule.model_copy(update={"stage":
        # "BOGUS"}) bypasses validation (model_copy does not re-validate),
        # producing a Rule whose `.stage` is the raw string "BOGUS" instead
        # of a RuleStage member. Round 2's non-short-circuit design let this
        # reach `_check_stage_effect_compatibility`'s
        # `STAGE_EFFECT_TYPE[rule.stage]` dict lookup and crash with an
        # uncaught KeyError. Round 3's fail-stop gate catches it at
        # revalidation instead (RuleStage enum coercion fails on "BOGUS"
        # during RulePack.model_validate) and stops before any semantic
        # check runs.
        original_rule = minimal_valid_pack.payload.rules[0]
        bogus_rule = original_rule.model_copy(update={"stage": "BOGUS"})
        tampered_payload = minimal_valid_pack.payload.model_construct(
            **{**minimal_valid_pack.payload.__dict__, "rules": (bogus_rule,)}
        )
        tampered_pack = minimal_valid_pack.model_construct(
            **{**minimal_valid_pack.__dict__, "payload": tampered_payload}
        )
        report = C.compile_rule_pack(tampered_pack)  # must not raise KeyError
        assert not report.ok
        assert any(e.code == "PACK_FAILS_STRUCTURAL_REVALIDATION" for e in report.errors)

    def test_payload_corrupted_to_empty_dict_never_crashes_reports_defensive_header(
        self, minimal_valid_pack: M.RulePack
    ) -> None:
        # Round 4 (Codex round-3 verify HIGH residual): compile_rule_pack's
        # fail-stop branch used to dereference `pack.payload.rule_pack_id`
        # directly — crashing with AttributeError when `payload` itself
        # (not just a field inside it) is corrupted, e.g. replaced wholesale
        # with `{}` via model_copy. A structurally-dead pack must ALWAYS
        # yield a clean report, never a second exception on the way to
        # reporting the first one.
        corrupted_pack = minimal_valid_pack.model_copy(update={"payload": {}})
        report = C.compile_rule_pack(corrupted_pack)  # must not raise AttributeError
        assert not report.ok
        assert report.rule_pack_id == "UNKNOWN"
        assert report.sequence == -1
        assert any(e.code == "PACK_FAILS_STRUCTURAL_REVALIDATION" for e in report.errors)


# ---------------------------------------------------------------------------
# Round 3 (Codex round-2 re-review finding 6 residue) — the NFC/UTC check
# now walks the ENTIRE signed payload (payload.model_dump(mode="json")), not
# a curated field list. NFC-normalization is NOT enforced by any models.py
# validator (unlike UTC-ness, ID-uniqueness, and covered_purposes
# non-emptiness — all bypass-proof-redundant per TestBypassProofRedundantChecks
# above), so a NORMALLY-constructed (non-bypass) pack with an NFD string can
# genuinely reach this check post-fail-stop.
# ---------------------------------------------------------------------------


class TestNfcUtcGenericWalker:
    def test_source_record_document_number_nfd_reported(
        self, source_record: M.SourceRecord
    ) -> None:
        # document_number has no Identifier pattern constraint (unlike
        # created_by/explanation_key/verified_by, which are ASCII-only
        # Identifier fields a non-ASCII string could never pass even via
        # bypass+revalidation) — this is the genuine target the orchestrator
        # specified, and needs no bypass trick at all: a normally-
        # constructed SourceRecord with an NFD document_number sails through
        # full Pydantic validation cleanly.
        import unicodedata

        nfd_number = unicodedata.normalize("NFD", "Café-2026/A")
        assert nfd_number != unicodedata.normalize("NFC", nfd_number)

        tampered_source = source_record.model_copy(update={"document_number": nfd_number})
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[tampered_source.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.nfc.document.number",
            product_version_ids=[product_id],
            source_refs=[tampered_source.source_record_id],
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[tampered_source]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "NON_NFC_STRING" for e in report.errors)

    def test_source_record_document_number_nfc_is_innocent(
        self, source_record: M.SourceRecord
    ) -> None:
        import unicodedata

        nfc_number = unicodedata.normalize("NFC", "Café-2026/A")
        tampered_source = source_record.model_copy(update={"document_number": nfc_number})
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[tampered_source.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.nfc.document.number.valid",
            product_version_ids=[product_id],
            source_refs=[tampered_source.source_record_id],
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[tampered_source]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert not any(e.code == "NON_NFC_STRING" for e in report.errors)

    def test_source_locator_value_nfd_reported(self, source_record: M.SourceRecord) -> None:
        # Locator values were entirely excluded from round 2's curated field
        # list (Codex round-2 re-review finding 6 residue, explicit
        # counterexample). SourceLocator.value has no pattern constraint.
        import unicodedata

        nfd_locator = unicodedata.normalize("NFD", "Pasal 5 ayat é")
        tampered_source = source_record.model_copy(
            update={"locators": (M.SourceLocator(kind="ARTICLE", value=nfd_locator),)}
        )
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[tampered_source.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.nfc.locator.value",
            product_version_ids=[product_id],
            source_refs=[tampered_source.source_record_id],
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[tampered_source]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "NON_NFC_STRING" for e in report.errors)

    def test_condition_string_literal_nfd_reported(self, source_record: M.SourceRecord) -> None:
        # Condition string literals (inside `when`) were also excluded from
        # round 2's curated field list — this is the "string literals of
        # conditions" gap Codex called out explicitly. intent.requested_
        # product_code is a STRING-kind fact with no allowed_values
        # restriction, so an `eq` literal against it is a clean vehicle: no
        # FACT_LITERAL_NOT_ALLOWED noise to disambiguate from NON_NFC_STRING.
        import unicodedata

        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        nfd_code = unicodedata.normalize("NFD", "É2")
        rule = make_support_rule(
            rule_id="rule.nfc.condition.literal",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "eq", "fact": "intent.requested_product_code", "value": nfd_code},
            required_facts=("intent.requested_product_code",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "NON_NFC_STRING" for e in report.errors)


# ---------------------------------------------------------------------------
# Round 4 (Codex round-3 verify residual) — the UTC-detection half of the
# walker matched a datetime-shaped PREFIX, not the WHOLE string, producing a
# false positive on any ordinary field that merely happens to start with a
# date-shaped substring.
# ---------------------------------------------------------------------------


class TestUtcDetectionAnchoredFullMatch:
    def test_datetime_prefix_with_trailing_garbage_is_innocent(
        self, source_record: M.SourceRecord
    ) -> None:
        # Codex's exact counterexample: document_number is an ordinary
        # identifier that happens to START with a date-shaped substring but
        # is NOT itself a datetime — the round-3 prefix-only regex
        # false-positived this as NON_UTC_DATETIME.
        tampered_source = source_record.model_copy(
            update={"document_number": "2026-07-17T00:00:00/REG-A"}
        )
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[tampered_source.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.utc.prefix.false.positive",
            product_version_ids=[product_id],
            source_refs=[tampered_source.source_record_id],
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[tampered_source]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert not any(e.code == "NON_UTC_DATETIME" for e in report.errors)

    def test_true_non_utc_offset_datetime_still_reported(
        self, source_record: M.SourceRecord
    ) -> None:
        # Innocence-of-the-fix-itself check: a GENUINE non-UTC datetime
        # string (a real +08:00 offset, no trailing garbage) must still be
        # caught — proves the fullmatch anchor didn't over-correct into
        # blindness.
        tampered_source = source_record.model_copy(
            update={"document_number": "2026-07-17T00:00:00+08:00"}
        )
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[tampered_source.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.utc.true.non.utc",
            product_version_ids=[product_id],
            source_refs=[tampered_source.source_record_id],
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[tampered_source]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "NON_UTC_DATETIME" for e in report.errors)


# ---------------------------------------------------------------------------
# Hotfix round (2026-07-18) — correctness gaps found by a comparative
# analysis against the concretization spec.
# ---------------------------------------------------------------------------


class TestFactLiteralDateShape:
    """Gap A: date-valued facts (``value_format="date"``) had no shape check
    on their literals — ``person.birth_date eq "20260101"`` or
    ``"2026-1-1"`` compiled clean, and a regex-shape-valid but
    calendar-invalid date (``"2026-02-30"``) did too.
    """

    def test_no_dashes_shape_guilty(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.date.no_dashes",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "eq", "fact": "person.birth_date", "value": "20260101"},
            required_facts=("person.birth_date",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "FACT_LITERAL_INVALID_DATE" for e in report.errors)

    def test_single_digit_month_day_shape_guilty(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.date.single_digit",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "eq", "fact": "person.birth_date", "value": "2026-1-1"},
            required_facts=("person.birth_date",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "FACT_LITERAL_INVALID_DATE" for e in report.errors)

    def test_invalid_calendar_date_guilty(self, source_record: M.SourceRecord) -> None:
        # Shape-valid (matches YYYY-MM-DD) but not a real calendar date —
        # only caught by a `datetime.date.fromisoformat` round-trip.
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.date.feb30",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "eq", "fact": "person.birth_date", "value": "2026-02-30"},
            required_facts=("person.birth_date",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "FACT_LITERAL_INVALID_DATE" for e in report.errors)

    def test_valid_date_is_innocent(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.date.valid",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "eq", "fact": "person.birth_date", "value": "2026-07-17"},
            required_facts=("person.birth_date",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert not any(e.code.startswith("FACT_LITERAL") for e in report.errors)

    def test_between_bounds_invalid_date_guilty(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.date.between.invalid",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={
                "op": "between",
                "fact": "person.birth_date",
                "lower": "2026-02-30",
                "upper": "2026-12-31",
            },
            required_facts=("person.birth_date",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "FACT_LITERAL_INVALID_DATE" for e in report.errors)

    def test_between_bounds_valid_date_is_innocent(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.date.between.valid",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={
                "op": "between",
                "fact": "person.birth_date",
                "lower": "2026-01-01",
                "upper": "2026-12-31",
            },
            required_facts=("person.birth_date",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert not any(e.code.startswith(("FACT_LITERAL", "BETWEEN")) for e in report.errors)


class TestBetweenBoundsInvertedSuppressedOnInvalidDate:
    """PR1b item 6 (Codex nit on hotfix #2739): a ``between`` bound that
    already fails date validation is not a meaningful basis for the
    lower>upper ordering comparison — comparing an invalid string
    lexicographically produced a SECOND, confusing ``BETWEEN_BOUNDS_INVERTED``
    error on top of the real ``FACT_LITERAL_INVALID_DATE`` one, for what is
    really a single defect. The task brief's exact counterexample:
    ``["2026-99-99", "2026-01-01"]`` — the invalid lower bound sorts
    lexicographically greater than the valid upper bound.
    """

    def test_invalid_lower_bound_suppresses_inverted_error(
        self, source_record: M.SourceRecord
    ) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.date.between.invalid_lower_suppresses_inverted",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={
                "op": "between",
                "fact": "person.birth_date",
                "lower": "2026-99-99",
                "upper": "2026-01-01",
            },
            required_facts=("person.birth_date",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        codes = [e.code for e in report.errors]
        assert "FACT_LITERAL_INVALID_DATE" in codes
        assert "BETWEEN_BOUNDS_INVERTED" not in codes

    def test_valid_bounds_still_report_inverted_when_actually_inverted(
        self, source_record: M.SourceRecord
    ) -> None:
        # Innocence-of-the-suppression: two SHAPE/CALENDAR-valid bounds that
        # are genuinely inverted must still be caught — the fix only
        # suppresses the ordering check when a bound is invalid, it must
        # never suppress a real BETWEEN_BOUNDS_INVERTED defect.
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.date.between.genuinely_inverted",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={
                "op": "between",
                "fact": "person.birth_date",
                "lower": "2026-12-31",
                "upper": "2026-01-01",
            },
            required_facts=("person.birth_date",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        codes = [e.code for e in report.errors]
        assert "BETWEEN_BOUNDS_INVERTED" in codes
        assert "FACT_LITERAL_INVALID_DATE" not in codes


class TestOrderingOpsRestrictedToNumericOrDate:
    """Gap B: ``lt``/``lte``/``gt``/``gte``/``between`` were rejected only
    against BOOLEAN-kind facts — a plain enum-ish STRING fact (e.g.
    ``marital_status``) compiled clean under lexicographic ordering, which
    is not a legally meaningful comparison.
    """

    def test_ordering_against_plain_string_enum_fact_guilty(
        self, source_record: M.SourceRecord
    ) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.ordering.enum.string",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "lt", "fact": "person.marital_status", "value": "MARRIED"},
            required_facts=("person.marital_status",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "FACT_LITERAL_KIND_MISMATCH" for e in report.errors)

    def test_ordering_against_integer_fact_is_innocent(
        self, source_record: M.SourceRecord
    ) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.ordering.integer.valid",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "lt", "fact": "immigration.overstay_days", "value": 10},
            required_facts=("immigration.overstay_days",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert not any(e.code.startswith("FACT_LITERAL") for e in report.errors)

    def test_ordering_against_date_fact_is_innocent(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.ordering.date.valid",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "gte", "fact": "person.birth_date", "value": "2000-01-01"},
            required_facts=("person.birth_date",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert not any(e.code.startswith("FACT_LITERAL") for e in report.errors)


class TestCountryCodeShape:
    """Gap D: facts marked ``value_format="country_code"`` had no shape
    check — a 3-letter code (``"USA"``) or a lowercase code (``"us"``)
    compiled clean, on both the scalar fact (``work.employer_country_code``)
    and set-valued facts' members (``person.nationalities``).
    """

    def test_three_letter_code_guilty(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.country.three_letter",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "eq", "fact": "work.employer_country_code", "value": "USA"},
            required_facts=("work.employer_country_code",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "FACT_LITERAL_INVALID_COUNTRY_CODE" for e in report.errors)

    def test_lowercase_code_guilty(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.country.lowercase",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "eq", "fact": "work.employer_country_code", "value": "us"},
            required_facts=("work.employer_country_code",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "FACT_LITERAL_INVALID_COUNTRY_CODE" for e in report.errors)

    def test_set_member_invalid_code_guilty(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.country.set.invalid",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "intersects", "fact": "person.nationalities", "values": ["USA"]},
            required_facts=("person.nationalities",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert any(e.code == "FACT_LITERAL_INVALID_COUNTRY_CODE" for e in report.errors)

    def test_scalar_code_valid_is_innocent(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.country.valid",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "eq", "fact": "work.employer_country_code", "value": "US"},
            required_facts=("work.employer_country_code",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert not any(e.code.startswith("FACT_LITERAL") for e in report.errors)

    def test_set_member_valid_codes_is_innocent(self, source_record: M.SourceRecord) -> None:
        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.country.set.valid",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
            when={"op": "intersects", "fact": "person.nationalities", "values": ["US", "GB"]},
            required_facts=("person.nationalities",),
        )
        payload = make_rule_pack_payload(
            rules=[rule], products=[product], source_records=[source_record]
        )
        report = C.compile_rule_pack(make_rule_pack(payload))
        assert not any(e.code.startswith("FACT_LITERAL") for e in report.errors)
