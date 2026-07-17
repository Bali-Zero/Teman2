"""Tests for ``backend.services.visa_engine.models`` + ``schema_export``.

Covers: RulePack/Rule/SourceRecord round-trip through ``model_dump()`` ->
``model_validate()``; ``extra="forbid"`` rejection on every top-level model;
the two Rule ``allOf`` conditionals (scope<->product_version_ids,
stage<->effect) with guilt+innocence pairs; the RulePackPayload sequence<->
previous_payload_sha256 conditional; UtcDateTime non-UTC rejection; the
exported JSON Schema's key invariants (5 DecisionState values, 16
ConditionOperator values, 5 UnknownReason values) per the PR1 task brief.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.services.visa_engine import models as M
from backend.services.visa_engine import schema_export as SE
from backend.services.visa_engine.enums import ConditionOperator, DecisionState, UnknownReason
from backend.tests.services.visa_engine.conftest import GOLD_EFFECTIVE_AT

_OPEN_PERIOD = {"from": GOLD_EFFECTIVE_AT, "to": None}


class TestRoundTrip:
    def test_rule_pack_round_trips_through_dump_and_validate(
        self, minimal_valid_pack: M.RulePack
    ) -> None:
        dumped = minimal_valid_pack.model_dump(mode="json")
        rebuilt = M.RulePack.model_validate(dumped)
        assert rebuilt == minimal_valid_pack

    def test_source_record_round_trips(self, source_record: M.SourceRecord) -> None:
        dumped = source_record.model_dump(mode="json")
        rebuilt = M.SourceRecord.model_validate(dumped)
        assert rebuilt == source_record

    def test_rule_round_trips(self, minimal_valid_pack: M.RulePack) -> None:
        rule = minimal_valid_pack.payload.rules[0]
        dumped = rule.model_dump(mode="json")
        rebuilt = M.Rule.model_validate(dumped)
        assert rebuilt == rule


class TestExtraForbidRejection:
    def test_rule_pack_rejects_extra_field(self, minimal_valid_pack: M.RulePack) -> None:
        dumped = minimal_valid_pack.model_dump(mode="json")
        dumped["unexpected_top_level_field"] = True
        with pytest.raises(ValidationError):
            M.RulePack.model_validate(dumped)

    def test_rule_rejects_extra_field(self, minimal_valid_pack: M.RulePack) -> None:
        dumped = minimal_valid_pack.payload.rules[0].model_dump(mode="json")
        dumped["unexpected"] = "nope"
        with pytest.raises(ValidationError):
            M.Rule.model_validate(dumped)

    def test_source_record_rejects_extra_field(self, source_record: M.SourceRecord) -> None:
        dumped = source_record.model_dump(mode="json")
        dumped["unexpected"] = "nope"
        with pytest.raises(ValidationError):
            M.SourceRecord.model_validate(dumped)

    def test_time_range_rejects_extra_field(self) -> None:
        with pytest.raises(ValidationError):
            M.TimeRange.model_validate({"from": GOLD_EFFECTIVE_AT, "to": None, "unexpected": 1})


class TestFrozenModels:
    def test_rule_pack_is_frozen(self, minimal_valid_pack: M.RulePack) -> None:
        with pytest.raises(ValidationError):
            minimal_valid_pack.payload_sha256 = "z" * 64  # type: ignore[misc]


class TestRuleScopeProductVersionIdsConditional:
    def _base_kwargs(self) -> dict:
        return {
            "rule_id": "rule.scope.test",
            "priority": 100,
            "valid_period": _OPEN_PERIOD,
            "when": {"op": "known", "fact": "person.birth_date"},
            "on_unknown": "NO_EFFECT",
            "required_facts": ["person.birth_date"],
            "source_refs": [uuid.uuid4()],
            "explanation_key": "explain.scope",
            "safety_critical": False,
        }

    def test_global_scope_with_product_version_ids_rejected(self) -> None:
        with pytest.raises(ValidationError, match="GLOBAL"):
            M.Rule(
                stage="HARD_FILTER",
                scope="GLOBAL",
                product_version_ids=[uuid.uuid4()],
                effect={"type": "EXCLUDE", "reason_code": "X"},
                **self._base_kwargs(),
            )

    def test_global_scope_without_product_version_ids_accepted(self) -> None:
        rule = M.Rule(
            stage="HARD_FILTER",
            scope="GLOBAL",
            product_version_ids=None,
            effect={"type": "EXCLUDE", "reason_code": "X"},
            **self._base_kwargs(),
        )
        assert rule.scope.value == "GLOBAL"

    def test_products_scope_without_product_version_ids_rejected(self) -> None:
        with pytest.raises(ValidationError, match="PRODUCTS"):
            M.Rule(
                stage="HARD_FILTER",
                scope="PRODUCTS",
                product_version_ids=None,
                effect={"type": "EXCLUDE", "reason_code": "X"},
                **self._base_kwargs(),
            )

    def test_products_scope_with_product_version_ids_accepted(self) -> None:
        rule = M.Rule(
            stage="HARD_FILTER",
            scope="PRODUCTS",
            product_version_ids=[uuid.uuid4()],
            effect={"type": "EXCLUDE", "reason_code": "X"},
            **self._base_kwargs(),
        )
        assert rule.scope.value == "PRODUCTS"


class TestRuleStageEffectConditional:
    def _base_kwargs(self) -> dict:
        return {
            "rule_id": "rule.stage.test",
            "scope": "GLOBAL",
            "product_version_ids": None,
            "priority": 100,
            "valid_period": _OPEN_PERIOD,
            "when": {"op": "known", "fact": "person.birth_date"},
            "required_facts": ["person.birth_date"],
            "source_refs": [uuid.uuid4()],
            "explanation_key": "explain.stage",
            "safety_critical": False,
        }

    @pytest.mark.parametrize(
        ("stage", "effect"),
        [
            ("HARD_FILTER", {"type": "EXCLUDE", "reason_code": "X"}),
            (
                "ELIGIBILITY",
                {"type": "SUPPORT", "reason_code": "X", "covered_purposes": ["TOURISM"]},
            ),
            ("HUMAN_REVIEW", {"type": "REQUIRE_REVIEW", "reason_code": "X"}),
            ("RANKING", {"type": "ADD_SCORE", "reason_code": "X", "points": 1}),
        ],
    )
    def test_matching_stage_effect_accepted(self, stage: str, effect: dict) -> None:
        rule = M.Rule(stage=stage, on_unknown="NO_EFFECT", effect=effect, **self._base_kwargs())
        assert rule.stage.value == stage

    def test_hard_filter_with_support_effect_rejected(self) -> None:
        with pytest.raises(ValidationError, match="requires effect type"):
            M.Rule(
                stage="HARD_FILTER",
                on_unknown="NO_EFFECT",
                effect={"type": "SUPPORT", "reason_code": "X", "covered_purposes": ["TOURISM"]},
                **self._base_kwargs(),
            )

    def test_ranking_with_exclude_effect_rejected(self) -> None:
        with pytest.raises(ValidationError, match="requires effect type"):
            M.Rule(
                stage="RANKING",
                on_unknown="NO_EFFECT",
                effect={"type": "EXCLUDE", "reason_code": "X"},
                **self._base_kwargs(),
            )


class TestSequenceChainConditional:
    def test_sequence_one_with_previous_hash_rejected(self, source_record: M.SourceRecord) -> None:
        from backend.tests.services.visa_engine.conftest import (
            make_product,
            make_support_rule,
        )

        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.seq",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
        )
        with pytest.raises(ValidationError, match="sequence 1"):
            M.RulePackPayload(
                rule_pack_id=uuid.uuid4(),
                sequence=1,
                version="1.0.0",
                environment="TEST",
                engine_min_version="1.0.0",
                engine_max_version="1.0.0",
                valid_period=_OPEN_PERIOD,
                created_at=GOLD_EFFECTIVE_AT,
                created_by="pipeline.compiler",
                previous_payload_sha256="e" * 64,  # illegal for sequence 1
                rollback_of_payload_sha256=None,
                hit_policy={},
                source_records=[source_record],
                products=[product],
                rules=[rule],
            )

    def test_sequence_two_without_previous_hash_rejected(
        self, source_record: M.SourceRecord
    ) -> None:
        from backend.tests.services.visa_engine.conftest import (
            make_product,
            make_support_rule,
        )

        product_id = uuid.uuid4()
        product = make_product(
            product_version_id=product_id, source_refs=[source_record.source_record_id]
        )
        rule = make_support_rule(
            rule_id="rule.seq2",
            product_version_ids=[product_id],
            source_refs=[source_record.source_record_id],
        )
        with pytest.raises(ValidationError, match="sequence > 1"):
            M.RulePackPayload(
                rule_pack_id=uuid.uuid4(),
                sequence=2,
                version="1.0.0",
                environment="TEST",
                engine_min_version="1.0.0",
                engine_max_version="1.0.0",
                valid_period=_OPEN_PERIOD,
                created_at=GOLD_EFFECTIVE_AT,
                created_by="pipeline.compiler",
                previous_payload_sha256=None,  # illegal for sequence > 1
                rollback_of_payload_sha256=None,
                hit_policy={},
                source_records=[source_record],
                products=[product],
                rules=[rule],
            )


class TestUtcDateTimeValidation:
    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(ValidationError):
            M.TimeRange(**{"from": datetime(2026, 7, 17), "to": None})

    def test_non_utc_offset_rejected(self) -> None:
        wita = timezone(timedelta(hours=8))
        with pytest.raises(ValidationError):
            M.TimeRange(**{"from": datetime(2026, 7, 17, tzinfo=wita), "to": None})

    def test_utc_datetime_accepted(self) -> None:
        tr = M.TimeRange(**{"from": GOLD_EFFECTIVE_AT, "to": None})
        assert tr.from_ == GOLD_EFFECTIVE_AT

    def test_utc_isoformat_renders_z_suffix(self) -> None:
        assert M.utc_isoformat(GOLD_EFFECTIVE_AT).endswith("Z")
        assert "+00:00" not in M.utc_isoformat(GOLD_EFFECTIVE_AT)


class TestHeaderEnvironmentConditional:
    def test_mismatched_environment_rejected_at_construction(
        self, minimal_valid_pack: M.RulePack
    ) -> None:
        protected = minimal_valid_pack.protected.model_dump(mode="json")
        protected["environment"] = "STAGING"
        with pytest.raises(ValidationError, match="must equal"):
            M.RulePack(
                protected=protected,
                payload=minimal_valid_pack.payload,
                payload_sha256=minimal_valid_pack.payload_sha256,
                signature=minimal_valid_pack.signature,
            )


class TestSchemaExportInvariants:
    def test_decision_state_has_5_values(self) -> None:
        assert len(list(DecisionState)) == 5

    def test_condition_operator_has_16_values(self) -> None:
        assert len(list(ConditionOperator)) == 16

    def test_unknown_reason_has_5_values(self) -> None:
        assert len(list(UnknownReason)) == 5

    def test_exported_condition_schema_carries_every_operator(self) -> None:
        schemas = SE.build_schemas()
        condition_schema = schemas["condition.schema.json"]
        rendered = str(condition_schema)
        for op in ConditionOperator:
            assert op.value in rendered, f"operator {op.value!r} missing from exported schema"

    def test_export_schemas_writes_files_to_disk(self, tmp_path: Path) -> None:
        SE.export_schemas(tmp_path)
        for filename in ["rule-pack.schema.json", "rule.schema.json", "source-record.schema.json"]:
            assert (tmp_path / filename).exists()

    def test_exported_rule_pack_schema_has_2020_12_dialect(self) -> None:
        schemas = SE.build_schemas()
        assert (
            schemas["rule-pack.schema.json"]["$schema"]
            == "https://json-schema.org/draft/2020-12/schema"
        )
