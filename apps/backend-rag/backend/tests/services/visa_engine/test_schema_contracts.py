"""Tests for ``backend.services.visa_engine.models`` + ``schema_export``.

Covers: RulePack/Rule/SourceRecord round-trip through ``model_dump()`` ->
``model_validate()``; ``extra="forbid"`` rejection on every top-level model;
the two Rule ``allOf`` conditionals (scope<->product_version_ids,
stage<->effect) with guilt+innocence pairs; the RulePackPayload sequence<->
previous_payload_sha256 conditional; UtcDateTime non-UTC rejection; the
exported JSON Schema's key invariants (5 DecisionState values, 16
ConditionOperator values, 5 UnknownReason values) per the PR1 task brief.

PR1 hardening round (Codex findings 1/2/4/10) additions: the FX-1
scope-expansion models (``ApplicantFacts``/``Decision``/``PriceQuote``/
``Candidate``) with their round-trip + ``allOf``-conditional coverage; every
now-required (no-silent-default) field from finding 2, one guilt test each;
strict-int rejection (finding 4) on the models-layer integer fields; and —
replacing the old enum-length/string-search "invariant" tests Codex
criticized in finding 10 — real ``jsonschema.Draft202012Validator`` +
``FormatChecker`` validation of golden instances against the *exported*
schema documents (generator != grader: this uses a JSON Schema engine that
has never seen Pydantic's internals, not the models that produced the data).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from referencing import Registry, Resource

from backend.services.visa_engine import models as M
from backend.services.visa_engine import schema_export as SE
from backend.services.visa_engine.enums import ConditionOperator, DecisionState, UnknownReason
from backend.tests.services.visa_engine.conftest import (
    _HIT_POLICY,
    GOLD_EFFECTIVE_AT,
    make_applicant_facts,
    make_candidate,
    make_fingerprint,
    make_price_quote,
    make_product,
    make_rule_pack_ref,
    make_support_rule,
    make_supported_candidates_decision,
)

_OPEN_PERIOD = {"from": GOLD_EFFECTIVE_AT, "to": None}


def _jsonschema_validator_for(schemas: dict, entrypoint_filename: str) -> Draft202012Validator:
    """Build a real ``jsonschema`` validator for one exported entrypoint,
    resolving its ``$ref`` into ``contract.schema.json`` via a two-resource
    ``referencing.Registry`` — the same two-file shape ``schema_export.py``
    writes to disk. Independent of Pydantic: this is the generator != grader
    check Codex's finding 10 asked for.
    """
    contract = schemas["contract.schema.json"]
    entrypoint = schemas[entrypoint_filename]
    registry = Registry().with_resources(
        [
            (contract["$id"], Resource.from_contents(contract)),
            (entrypoint["$id"], Resource.from_contents(entrypoint)),
        ]
    )
    return Draft202012Validator(
        entrypoint, registry=registry, format_checker=Draft202012Validator.FORMAT_CHECKER
    )


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
                jurisdiction="ID",
                decision_domain="IMMIGRATION_VISA",
                engine_contract_version="1.0.0",
                engine_min_version="1.0.0",
                engine_max_version="1.0.0",
                valid_period=_OPEN_PERIOD,
                created_at=GOLD_EFFECTIVE_AT,
                created_by="pipeline.compiler",
                previous_payload_sha256="e" * 64,  # illegal for sequence 1
                rollback_of_payload_sha256=None,
                hit_policy=_HIT_POLICY,
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
                jurisdiction="ID",
                decision_domain="IMMIGRATION_VISA",
                engine_contract_version="1.0.0",
                engine_min_version="1.0.0",
                engine_max_version="1.0.0",
                valid_period=_OPEN_PERIOD,
                created_at=GOLD_EFFECTIVE_AT,
                created_by="pipeline.compiler",
                previous_payload_sha256=None,  # illegal for sequence > 1
                rollback_of_payload_sha256=None,
                hit_policy=_HIT_POLICY,
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
                canonicalization=minimal_valid_pack.canonicalization,
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

    def test_all_seven_spec_entrypoints_exported(self) -> None:
        # Codex finding 1: the original PR1 draft exported only 4 of the 7
        # spec §2 "Equivalent entrypoints" — this asserts all seven, plus
        # the shared `contract.schema.json` they `$ref` into.
        schemas = SE.build_schemas()
        for filename in (
            "contract.schema.json",
            "rule-pack.schema.json",
            "rule.schema.json",
            "visa-product-version.schema.json",
            "applicant-facts.schema.json",
            "decision.schema.json",
            "price-quote.schema.json",
            "source-record.schema.json",
        ):
            assert filename in schemas, f"{filename} missing from exported schema set"

    def test_decision_state_present_in_contract(self) -> None:
        schemas = SE.build_schemas()
        rendered = str(schemas["contract.schema.json"])
        for state in DecisionState:
            assert state.value in rendered

    def test_unknown_reason_present_in_contract(self) -> None:
        schemas = SE.build_schemas()
        rendered = str(schemas["contract.schema.json"])
        for reason in UnknownReason:
            assert reason.value in rendered


class TestJsonSchemaGoldenInstanceValidation:
    """Generator != grader (Codex finding 10): validate real model instances
    against the *exported* schema documents using ``jsonschema``, a JSON
    Schema engine wholly independent of Pydantic — this catches an exported
    schema that Pydantic itself would happily round-trip against but that
    diverges from what an external consumer (a non-Python service, a CI
    contract-check) would actually accept.
    """

    def test_rule_pack_instance_validates_against_exported_schema(
        self, minimal_valid_pack: M.RulePack
    ) -> None:
        schemas = SE.build_schemas()
        validator = _jsonschema_validator_for(schemas, "rule-pack.schema.json")
        instance = minimal_valid_pack.model_dump(mode="json", by_alias=True)
        errors = list(validator.iter_errors(instance))
        assert errors == [], [str(e) for e in errors]

    def test_source_record_instance_validates_against_exported_schema(
        self, source_record: M.SourceRecord
    ) -> None:
        schemas = SE.build_schemas()
        validator = _jsonschema_validator_for(schemas, "source-record.schema.json")
        instance = source_record.model_dump(mode="json", by_alias=True)
        errors = list(validator.iter_errors(instance))
        assert errors == [], [str(e) for e in errors]

    def test_applicant_facts_instance_validates_against_exported_schema(self) -> None:
        schemas = SE.build_schemas()
        validator = _jsonschema_validator_for(schemas, "applicant-facts.schema.json")
        instance = make_applicant_facts().model_dump(mode="json", by_alias=True)
        errors = list(validator.iter_errors(instance))
        assert errors == [], [str(e) for e in errors]

    def test_decision_instance_validates_against_exported_schema(self) -> None:
        product_id = uuid.uuid4()
        decision = make_supported_candidates_decision(product_version_id=product_id)
        schemas = SE.build_schemas()
        validator = _jsonschema_validator_for(schemas, "decision.schema.json")
        instance = decision.model_dump(mode="json", by_alias=True)
        errors = list(validator.iter_errors(instance))
        assert errors == [], [str(e) for e in errors]

    def test_price_quote_instance_validates_against_exported_schema(self) -> None:
        quote = make_price_quote(product_version_id=uuid.uuid4())
        schemas = SE.build_schemas()
        validator = _jsonschema_validator_for(schemas, "price-quote.schema.json")
        instance = quote.model_dump(mode="json", by_alias=True)
        errors = list(validator.iter_errors(instance))
        assert errors == [], [str(e) for e in errors]

    def test_visa_product_version_instance_validates_against_exported_schema(self) -> None:
        product = make_product(product_version_id=uuid.uuid4(), source_refs=[uuid.uuid4()])
        schemas = SE.build_schemas()
        validator = _jsonschema_validator_for(schemas, "visa-product-version.schema.json")
        instance = product.model_dump(mode="json", by_alias=True)
        errors = list(validator.iter_errors(instance))
        assert errors == [], [str(e) for e in errors]

    def test_broken_instance_is_actually_caught(self, source_record: M.SourceRecord) -> None:
        # Innocence-of-the-grader-itself check: a deliberately-invalid
        # instance (bad content_sha256 pattern) must be REJECTED — proves
        # the validator above is not vacuously passing everything.
        schemas = SE.build_schemas()
        validator = _jsonschema_validator_for(schemas, "source-record.schema.json")
        instance = source_record.model_dump(mode="json", by_alias=True)
        instance["content_sha256"] = "not-a-valid-sha256"
        errors = list(validator.iter_errors(instance))
        assert errors != []


class TestApplicantFactsContract:
    def test_round_trips(self) -> None:
        facts = make_applicant_facts()
        dumped = facts.model_dump(mode="json", by_alias=True)
        rebuilt = M.ApplicantFacts.model_validate(dumped)
        assert rebuilt == facts

    def test_rejects_extra_top_level_field(self) -> None:
        dumped = make_applicant_facts().model_dump(mode="json", by_alias=True)
        dumped["unexpected"] = True
        with pytest.raises(ValidationError):
            M.ApplicantFacts.model_validate(dumped)

    def test_facts_object_missing_one_of_35_keys_rejected(self) -> None:
        dumped = make_applicant_facts().model_dump(mode="json", by_alias=True)
        del dumped["facts"]["person.birth_date"]
        with pytest.raises(ValidationError):
            M.ApplicantFacts.model_validate(dumped)

    def test_facts_object_rejects_unrecognized_key(self) -> None:
        dumped = make_applicant_facts().model_dump(mode="json", by_alias=True)
        dumped["facts"]["not.a.real.path"] = {"status": "UNKNOWN", "reason": "NOT_ASKED"}
        with pytest.raises(ValidationError):
            M.ApplicantFacts.model_validate(dumped)

    def test_known_marital_status_parses(self) -> None:
        dumped = make_applicant_facts().model_dump(mode="json", by_alias=True)
        dumped["facts"]["person.marital_status"] = {"status": "KNOWN", "value": "MARRIED"}
        rebuilt = M.ApplicantFacts.model_validate(dumped)
        assert rebuilt.facts.person_marital_status.value == "MARRIED"  # type: ignore[union-attr]

    def test_known_marital_status_rejects_value_outside_enum(self) -> None:
        dumped = make_applicant_facts().model_dump(mode="json", by_alias=True)
        dumped["facts"]["person.marital_status"] = {"status": "KNOWN", "value": "NOT_A_STATUS"}
        with pytest.raises(ValidationError):
            M.ApplicantFacts.model_validate(dumped)


class TestPriceQuoteStatusConditional:
    def test_available_requires_non_null_amount(self) -> None:
        with pytest.raises(ValidationError, match="AVAILABLE requires non-null"):
            M.PriceQuote(
                quote_id=uuid.uuid4(),
                product_version_id=uuid.uuid4(),
                product_code="C1",
                status="AVAILABLE",
                currency="IDR",
                amount=None,
                pricing_key={"category": "visa", "item_key": "c1"},
                catalog_version=None,
                catalog_sha256=None,
                row_sha256=None,
                quoted_at=GOLD_EFFECTIVE_AT,
                valid_until=None,
                reason_code="X",
            )

    def test_unavailable_requires_null_amount(self) -> None:
        with pytest.raises(ValidationError, match="requires amount=null"):
            M.PriceQuote(
                quote_id=uuid.uuid4(),
                product_version_id=uuid.uuid4(),
                product_code="C1",
                status="UNAVAILABLE",
                currency="IDR",
                amount=100,
                pricing_key={"category": "visa", "item_key": "c1"},
                catalog_version=None,
                catalog_sha256=None,
                row_sha256=None,
                quoted_at=GOLD_EFFECTIVE_AT,
                valid_until=None,
                reason_code="X",
            )

    def test_available_with_all_fields_is_innocent(self) -> None:
        quote = make_price_quote(product_version_id=uuid.uuid4(), status="AVAILABLE")
        assert quote.status == "AVAILABLE"

    def test_contact_required_with_null_amount_is_innocent(self) -> None:
        quote = make_price_quote(product_version_id=uuid.uuid4(), status="CONTACT_REQUIRED")
        assert quote.status == "CONTACT_REQUIRED"


class TestDecisionStateConditionals:
    def _base_kwargs(self) -> dict:
        return {
            "schema_version": "1.0.0",
            "effective_at": GOLD_EFFECTIVE_AT,
            "observed_at": GOLD_EFFECTIVE_AT,
            "evaluated_at": GOLD_EFFECTIVE_AT,
            "facts_fingerprint": make_fingerprint(),
            "trace_sha256": "e" * 64,
        }

    def test_supported_candidates_requires_at_least_one_candidate(self) -> None:
        with pytest.raises(ValidationError, match="at least one candidate"):
            M.Decision(
                decision_id=uuid.uuid4(),
                public_id="a" * 16,
                state="SUPPORTED_CANDIDATES",
                rule_pack=make_rule_pack_ref(),
                candidates=[],
                missing_facts=[],
                review_reasons=[],
                no_path_reasons=[],
                outage=None,
                quotes=[],
                notices=[],
                decision_integrity=None,
                **self._base_kwargs(),
            )

    def test_supported_candidates_forbids_null_identity(self) -> None:
        with pytest.raises(ValidationError, match="requires non-null"):
            M.Decision(
                decision_id=None,
                public_id=None,
                state="SUPPORTED_CANDIDATES",
                rule_pack=make_rule_pack_ref(),
                candidates=[make_candidate(product_version_id=uuid.uuid4())],
                missing_facts=[],
                review_reasons=[],
                no_path_reasons=[],
                outage=None,
                quotes=[],
                notices=[],
                decision_integrity=None,
                **self._base_kwargs(),
            )

    def test_supported_candidates_valid_is_innocent(self) -> None:
        decision = make_supported_candidates_decision(product_version_id=uuid.uuid4())
        assert decision.state.value == "SUPPORTED_CANDIDATES"

    def test_needs_input_requires_at_least_one_missing_fact(self) -> None:
        with pytest.raises(ValidationError, match="at least one missing fact"):
            M.Decision(
                decision_id=uuid.uuid4(),
                public_id="a" * 16,
                state="NEEDS_INPUT",
                rule_pack=make_rule_pack_ref(),
                candidates=[],
                missing_facts=[],
                review_reasons=[],
                no_path_reasons=[],
                outage=None,
                quotes=[],
                notices=[],
                decision_integrity=None,
                **self._base_kwargs(),
            )

    def test_needs_input_valid_is_innocent(self) -> None:
        decision = M.Decision(
            decision_id=uuid.uuid4(),
            public_id="a" * 16,
            state="NEEDS_INPUT",
            rule_pack=make_rule_pack_ref(),
            candidates=[],
            missing_facts=["person.birth_date"],
            review_reasons=[],
            no_path_reasons=[],
            outage=None,
            quotes=[],
            notices=[],
            decision_integrity=None,
            **self._base_kwargs(),
        )
        assert decision.state.value == "NEEDS_INPUT"

    def test_human_review_required_requires_at_least_one_review_reason(self) -> None:
        with pytest.raises(ValidationError, match="at least one review reason"):
            M.Decision(
                decision_id=uuid.uuid4(),
                public_id="a" * 16,
                state="HUMAN_REVIEW_REQUIRED",
                rule_pack=make_rule_pack_ref(),
                candidates=[],
                missing_facts=[],
                review_reasons=[],
                no_path_reasons=[],
                outage=None,
                quotes=[],
                notices=[],
                decision_integrity=None,
                **self._base_kwargs(),
            )

    def test_no_supported_path_requires_at_least_one_no_path_reason(self) -> None:
        with pytest.raises(ValidationError, match="at least one no_path reason"):
            M.Decision(
                decision_id=uuid.uuid4(),
                public_id="a" * 16,
                state="NO_SUPPORTED_PATH",
                rule_pack=make_rule_pack_ref(),
                candidates=[],
                missing_facts=[],
                review_reasons=[],
                no_path_reasons=[],
                outage=None,
                quotes=[],
                notices=[],
                decision_integrity=None,
                **self._base_kwargs(),
            )

    def test_temporarily_unavailable_requires_non_null_outage(self) -> None:
        with pytest.raises(ValidationError, match="requires a non-null outage"):
            M.Decision(
                decision_id=None,
                public_id=None,
                state="TEMPORARILY_UNAVAILABLE",
                rule_pack=None,
                candidates=[],
                missing_facts=[],
                review_reasons=[],
                no_path_reasons=[],
                outage=None,
                quotes=[],
                notices=[],
                decision_integrity=None,
                **self._base_kwargs(),
            )

    def test_temporarily_unavailable_with_outage_is_innocent(self) -> None:
        decision = M.Decision(
            decision_id=None,
            public_id=None,
            state="TEMPORARILY_UNAVAILABLE",
            rule_pack=None,
            candidates=[],
            missing_facts=[],
            review_reasons=[],
            no_path_reasons=[],
            outage={"code": "RULE_PACK_UNAVAILABLE", "retryable": True},
            quotes=[],
            notices=[],
            decision_integrity=None,
            **self._base_kwargs(),
        )
        assert decision.state.value == "TEMPORARILY_UNAVAILABLE"

    def test_non_supported_candidates_state_forbids_nonempty_candidates(self) -> None:
        with pytest.raises(ValidationError, match="forbids non-empty candidates"):
            M.Decision(
                decision_id=uuid.uuid4(),
                public_id="a" * 16,
                state="NEEDS_INPUT",
                rule_pack=make_rule_pack_ref(),
                candidates=[make_candidate(product_version_id=uuid.uuid4())],
                missing_facts=["person.birth_date"],
                review_reasons=[],
                no_path_reasons=[],
                outage=None,
                quotes=[],
                notices=[],
                decision_integrity=None,
                **self._base_kwargs(),
            )


class TestCandidateDecisionAlias:
    def test_candidate_decision_is_candidate(self) -> None:
        # Spec §1's module-layout snippet names this class `CandidateDecision`;
        # spec §2's JSON Schema $def is `Candidate` — see models.py's
        # module docstring for the resolution.
        assert M.CandidateDecision is M.Candidate


class TestNoSilentDefaults:
    """One guilt test per Codex finding-2 counterexample: a field that used
    to have a Python default (letting the key be silently omitted) is now
    required — omitting it must raise, never fall back to the old default.
    """

    def test_time_range_missing_to_key_rejected(self) -> None:
        with pytest.raises(ValidationError):
            M.TimeRange.model_validate({"from": GOLD_EFFECTIVE_AT})

    def test_rule_missing_required_facts_key_rejected(self) -> None:
        dumped = make_support_rule(
            rule_id="rule.no.required.facts",
            product_version_ids=[uuid.uuid4()],
            source_refs=[uuid.uuid4()],
        ).model_dump(mode="json", by_alias=True)
        del dumped["required_facts"]
        with pytest.raises(ValidationError):
            M.Rule.model_validate(dumped)

    def test_hit_policy_declaration_zero_args_rejected(self) -> None:
        # Codex's exact counterexample: `HitPolicyDeclaration()` used to be
        # wrongly accepted.
        with pytest.raises(ValidationError):
            M.HitPolicyDeclaration()

    def test_protected_header_missing_domain_alg_schema_version_rejected(self) -> None:
        with pytest.raises(ValidationError):
            M.ProtectedHeader.model_validate(
                {
                    "kid": "key-1",
                    "signed_at": GOLD_EFFECTIVE_AT,
                    "environment": "TEST",
                }
            )

    def test_rule_pack_missing_canonicalization_rejected(
        self, minimal_valid_pack: M.RulePack
    ) -> None:
        dumped = minimal_valid_pack.model_dump(mode="json", by_alias=True)
        del dumped["canonicalization"]
        with pytest.raises(ValidationError):
            M.RulePack.model_validate(dumped)

    def test_source_record_missing_jurisdiction_rejected(
        self, source_record: M.SourceRecord
    ) -> None:
        dumped = source_record.model_dump(mode="json", by_alias=True)
        del dumped["jurisdiction"]
        with pytest.raises(ValidationError):
            M.SourceRecord.model_validate(dumped)

    def test_source_record_missing_document_number_key_rejected(
        self, source_record: M.SourceRecord
    ) -> None:
        dumped = source_record.model_dump(mode="json", by_alias=True)
        del dumped["document_number"]
        with pytest.raises(ValidationError):
            M.SourceRecord.model_validate(dumped)

    def test_source_record_missing_locators_key_rejected(
        self, source_record: M.SourceRecord
    ) -> None:
        dumped = source_record.model_dump(mode="json", by_alias=True)
        del dumped["locators"]
        with pytest.raises(ValidationError):
            M.SourceRecord.model_validate(dumped)

    def test_source_record_missing_supersedes_key_rejected(
        self, source_record: M.SourceRecord
    ) -> None:
        dumped = source_record.model_dump(mode="json", by_alias=True)
        del dumped["supersedes_source_record_id"]
        with pytest.raises(ValidationError):
            M.SourceRecord.model_validate(dumped)


class TestStrictIntFields:
    """Codex finding 4, extended per the orchestrator's "do the same for
    integer fields in models" instruction: a float with no fractional part
    (e.g. ``1.0``) must never silently coerce into an ``int`` field.
    """

    def test_source_record_version_rejects_float(self, source_record: M.SourceRecord) -> None:
        dumped = source_record.model_dump(mode="json", by_alias=True)
        dumped["version"] = 1.0
        with pytest.raises(ValidationError):
            M.SourceRecord.model_validate(dumped)

    def test_rule_pack_payload_sequence_rejects_float(self, minimal_valid_pack: M.RulePack) -> None:
        dumped = minimal_valid_pack.payload.model_dump(mode="json", by_alias=True)
        dumped["sequence"] = 1.0
        with pytest.raises(ValidationError):
            M.RulePackPayload.model_validate(dumped)

    def test_rule_priority_rejects_float(self, minimal_valid_pack: M.RulePack) -> None:
        dumped = minimal_valid_pack.payload.rules[0].model_dump(mode="json", by_alias=True)
        dumped["priority"] = 100.0
        with pytest.raises(ValidationError):
            M.Rule.model_validate(dumped)

    def test_effect_add_score_points_rejects_float(self) -> None:
        with pytest.raises(ValidationError):
            M.EffectAddScore(type="ADD_SCORE", reason_code="X", points=1.0)  # type: ignore[arg-type]


class TestStageEffectTypeImmutable:
    def test_stage_effect_type_cannot_be_cleared(self) -> None:
        # Codex finding 9: `models.py`'s module-level mapping must be a
        # true `MappingProxyType`, not a plain `dict` a caller could mutate.
        with pytest.raises(AttributeError):
            M.STAGE_EFFECT_TYPE.clear()  # type: ignore[attr-defined]
        assert len(M.STAGE_EFFECT_TYPE) == 4
