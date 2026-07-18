"""JSON Schema 2020-12 validation tests.

Loads the packaged schema files with `Draft202012Validator(...,
format_checker=FormatChecker())`. Verifies: a valid example RulePack passes;
malformed variants (bad op, bad pattern, extra property) fail; the example
that passes JSON Schema also parses via the Pydantic models and vice-versa a
model-built pack serializes back to schema-valid JSON (schema/model
coherence).
"""

from __future__ import annotations

import copy
import json

import pytest
from jsonschema import Draft202012Validator
from jsonschema import ValidationError as JsonSchemaValidationError
from pydantic import ValidationError as PydanticValidationError

from backend.services.visa_engine.models import ApplicantFacts, RulePack

from ._builders import applicant_facts_envelope, minimal_valid_envelope
from .conftest import validate_or_fail


def test_valid_rule_pack_passes_json_schema(rule_pack_validator: Draft202012Validator) -> None:
    envelope = minimal_valid_envelope()
    # `validator.validate(...)` returns None on success — asserting on it
    # would be a tautology. `iter_errors` gives a real, inspectable result:
    # the innocence case must produce ZERO schema violations.
    errors = list(rule_pack_validator.iter_errors(envelope))
    assert errors == []


def test_valid_applicant_facts_passes_json_schema(
    applicant_facts_validator: Draft202012Validator,
) -> None:
    payload = applicant_facts_envelope(
        **{"person.birth_date": {"status": "KNOWN", "value": "1990-05-12"}}
    )
    errors = list(applicant_facts_validator.iter_errors(payload))
    assert errors == []


def test_bad_op_rejected_by_json_schema(rule_pack_validator: Draft202012Validator) -> None:
    envelope = minimal_valid_envelope()
    envelope["payload"]["rules"][0]["when"] = {"op": "not_a_real_operator", "fact": "x", "value": 1}
    with pytest.raises(JsonSchemaValidationError):
        rule_pack_validator.validate(envelope)


def test_bad_pattern_rejected_by_json_schema(rule_pack_validator: Draft202012Validator) -> None:
    envelope = minimal_valid_envelope()
    envelope["protected"]["kid"] = "1-starts-with-a-digit-violates-Identifier-pattern"
    with pytest.raises(JsonSchemaValidationError):
        rule_pack_validator.validate(envelope)


def test_extra_property_rejected_by_json_schema(rule_pack_validator: Draft202012Validator) -> None:
    envelope = minimal_valid_envelope()
    envelope["totally_unexpected_top_level_key"] = True
    with pytest.raises(JsonSchemaValidationError):
        rule_pack_validator.validate(envelope)


def test_bad_sha256_length_rejected(rule_pack_validator: Draft202012Validator) -> None:
    envelope = minimal_valid_envelope()
    envelope["payload_sha256"] = "not-64-hex-chars"
    with pytest.raises(JsonSchemaValidationError):
        rule_pack_validator.validate(envelope)


def test_missing_required_key_rejected(rule_pack_validator: Draft202012Validator) -> None:
    envelope = minimal_valid_envelope()
    del envelope["payload"]["hit_policy"]
    with pytest.raises(JsonSchemaValidationError):
        rule_pack_validator.validate(envelope)


def test_bad_uuid_format_rejected(rule_pack_validator: Draft202012Validator) -> None:
    envelope = minimal_valid_envelope()
    envelope["payload"]["rule_pack_id"] = "not-a-uuid"
    with pytest.raises(JsonSchemaValidationError):
        rule_pack_validator.validate(envelope)


class TestSchemaModelCoherence:
    """The SAME dict must be valid (or invalid) under both JSON Schema and
    the Pydantic models — the wire contract and the runtime model must
    agree, not merely each "look correct" in isolation."""

    def test_valid_pack_parses_via_pydantic_after_passing_json_schema(
        self, rule_pack_validator: Draft202012Validator
    ) -> None:
        envelope = minimal_valid_envelope()
        validate_or_fail(rule_pack_validator, envelope)

        pack = RulePack(**envelope)
        assert str(pack.payload.rule_pack_id) == envelope["payload"]["rule_pack_id"]

    def test_model_built_pack_serializes_to_schema_valid_json(
        self, rule_pack_validator: Draft202012Validator
    ) -> None:
        envelope = minimal_valid_envelope()
        pack = RulePack(**envelope)

        # Round-trip through JSON (mode="json" + by_alias to match the wire shape).
        dumped = json.loads(json.dumps(pack.model_dump(mode="json", by_alias=True)))
        errors = list(rule_pack_validator.iter_errors(dumped))
        assert errors == []

    def test_valid_applicant_facts_round_trips(
        self, applicant_facts_validator: Draft202012Validator
    ) -> None:
        payload = applicant_facts_envelope(
            **{
                "person.birth_date": {"status": "KNOWN", "value": "1990-05-12"},
                "person.nationalities": {"status": "KNOWN", "value": ["US", "GB"]},
            }
        )
        validate_or_fail(applicant_facts_validator, payload)

        model = ApplicantFacts(**payload)
        dumped = json.loads(json.dumps(model.model_dump(mode="json", by_alias=True)))
        validate_or_fail(applicant_facts_validator, dumped)
        assert dumped["facts"]["person.nationalities"]["value"] == ["US", "GB"]

    def test_sequence_previous_hash_mismatch_rejected_by_both_layers(
        self, rule_pack_validator: Draft202012Validator
    ) -> None:
        """`sequence > 1` requires a non-null `previous_payload_sha256` — the
        schema's own `allOf` conditional (lines 1790-1804) encodes this, and
        `RulePackPayload._check_sequence_previous_hash` re-enforces the same
        rule at the Pydantic layer. Both must reject the same broken pack
        (schema/model coherence in the other direction: agreeing on what's
        INVALID, not just on what's valid)."""

        envelope = minimal_valid_envelope()
        broken = copy.deepcopy(envelope)
        broken["payload"]["sequence"] = 2  # previous_payload_sha256 stays null -> invalid

        assert not rule_pack_validator.is_valid(broken)
        with pytest.raises(PydanticValidationError):
            RulePack(**broken)
