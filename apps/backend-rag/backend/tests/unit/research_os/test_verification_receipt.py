from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from pydantic import ValidationError
from research_os.cli import FIXTURES_ROOT
from research_os.hashing import object_hash
from research_os.models.verification_receipt import VerificationReceipt
from research_os.schemas import SCHEMA_DIRECTORY

CONTRACT_KIND = "verification_receipt"


def _reason_codes(exc: ValidationError) -> set[str]:
    return {str(error["type"]) for error in exc.errors()}


def test_valid_fixtures_round_trip(load_json: Any) -> None:
    schema = load_json(SCHEMA_DIRECTORY / f"{CONTRACT_KIND}.schema.json")
    for fixture_path in sorted((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json")):
        payload = load_json(fixture_path)
        Draft202012Validator(schema).validate(payload)
        instance = VerificationReceipt.model_validate(payload)
        assert instance.model_dump(mode="json", exclude_none=True) == payload, fixture_path.name


def test_invalid_fixtures_reject_with_exact_expected_reason(load_json: Any) -> None:
    fixture_paths = (
        path
        for path in (FIXTURES_ROOT / CONTRACT_KIND).glob("invalid_*.json")
        if not path.name.endswith(".expect.json")
    )
    for fixture_path in sorted(fixture_paths):
        expected = load_json(fixture_path.with_suffix(".expect.json"))["reason_code"]
        with pytest.raises(ValidationError) as caught:
            VerificationReceipt.model_validate(load_json(fixture_path))
        assert expected in _reason_codes(caught.value), fixture_path.name


def test_rejects_unknown_top_level_field(load_json: Any) -> None:
    fixture_path = next((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "unexpected": True}
    with pytest.raises(ValidationError):
        VerificationReceipt.model_validate(payload)


def test_validation_context_cannot_bypass_exact_object_hash(load_json: Any) -> None:
    fixture_path = next((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "object_hash": "0" * 64}
    with pytest.raises(ValidationError) as caught:
        VerificationReceipt.model_validate(payload, context={"skip_object_hash_check": True})
    assert "object_hash_mismatch" in _reason_codes(caught.value)


def test_verification_receipt_is_immutable(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    receipt = VerificationReceipt.model_validate(payload)
    with pytest.raises(ValidationError):
        receipt.verdict = "fail"  # type: ignore[assignment]


def test_domain_findings_cannot_redefine_the_canonical_verdict(load_json: Any) -> None:
    """Section 14: domain findings live in extensions, never as a core field.

    ``extra="forbid"`` makes this a structural guarantee: any attempt to add
    a sibling top-level field (e.g. a bespoke ``contradiction`` flag) instead
    of using ``extensions`` is rejected the same way any other unknown field
    is rejected -- there is nothing verdict-specific to test beyond that.
    """
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = {**payload, "contradiction": True}
    with pytest.raises(ValidationError) as caught:
        VerificationReceipt.model_validate(candidate)
    assert "extra_forbidden" in _reason_codes(caught.value)


def test_verdict_pass_with_limits_round_trips_with_limits_populated(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_pass_with_limits.json")
    receipt = VerificationReceipt.model_validate(payload)
    assert receipt.verdict.value == "pass_with_limits"
    assert receipt.limits == ("reduced_sample_size",)


def test_check_result_uses_gate_disposition_not_verification_verdict(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = deepcopy(payload)
    candidate["checks"][0]["result"] = "pass_with_limits"  # valid verdict, not a gate_disposition
    candidate["object_hash"] = object_hash(candidate)
    with pytest.raises(ValidationError) as caught:
        VerificationReceipt.model_validate(candidate)
    assert "enum" in _reason_codes(caught.value)
