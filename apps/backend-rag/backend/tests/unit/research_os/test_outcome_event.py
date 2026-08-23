from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from pydantic import ValidationError
from research_os.cli import FIXTURES_ROOT
from research_os.hashing import object_hash
from research_os.models.outcome_event import OutcomeEvent
from research_os.schemas import SCHEMA_DIRECTORY

CONTRACT_KIND = "outcome_event"


def _reason_codes(exc: ValidationError) -> set[str]:
    return {str(error["type"]) for error in exc.errors()}


def test_valid_fixtures_round_trip(load_json: Any) -> None:
    schema = load_json(SCHEMA_DIRECTORY / f"{CONTRACT_KIND}.schema.json")
    for fixture_path in sorted((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json")):
        payload = load_json(fixture_path)
        Draft202012Validator(schema).validate(payload)
        instance = OutcomeEvent.model_validate(payload)
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
            OutcomeEvent.model_validate(load_json(fixture_path))
        assert expected in _reason_codes(caught.value), fixture_path.name


def test_rejects_unknown_top_level_field(load_json: Any) -> None:
    fixture_path = next((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "unexpected": True}
    with pytest.raises(ValidationError):
        OutcomeEvent.model_validate(payload)


def test_validation_context_cannot_bypass_exact_object_hash(load_json: Any) -> None:
    fixture_path = next((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "object_hash": "0" * 64}
    with pytest.raises(ValidationError) as caught:
        OutcomeEvent.model_validate(payload, context={"skip_object_hash_check": True})
    assert "object_hash_mismatch" in _reason_codes(caught.value)


def test_outcome_event_is_immutable(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    event = OutcomeEvent.model_validate(payload)
    with pytest.raises(ValidationError):
        event.outcome_type = "com.example.other"  # type: ignore[misc]


def test_metric_profile_and_result_are_jointly_absent_in_minimal_fixture(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    event = OutcomeEvent.model_validate(payload)
    assert event.metric_profile_ref is None
    assert event.metric_result_ref is None


def test_metric_result_ref_without_profile_ref_is_rejected(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = deepcopy(payload)
    candidate["metric_result_ref"] = {
        "metric_result_id": "d0000000-0000-4000-8000-000000000001",
        "object_hash": "2" * 64,
    }
    candidate["object_hash"] = object_hash(candidate)
    with pytest.raises(ValidationError) as caught:
        OutcomeEvent.model_validate(candidate)
    assert "metric_profile_and_result_not_jointly_present" in _reason_codes(caught.value)


def test_metric_profile_and_result_jointly_present_is_valid(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_with_metrics.json")
    event = OutcomeEvent.model_validate(payload)
    assert event.metric_profile_ref is not None
    assert event.metric_result_ref is not None


def test_subject_refs_has_no_revocation_receipt_ref_field(load_json: Any) -> None:
    """Documents the section-16-vs-3.2 divergence reported in the P04-D1
    handoff: an OutcomeEvent reporting ``revocation.propagation`` cannot
    bind the exact RevocationReceipt hash it propagates, because
    ``subject_refs`` was never given that field. This is not a bug in this
    model -- it encodes section 16 exactly as written -- but the absence is
    load-bearing enough to pin with a test so a future edit that quietly
    "fixes" it (by inventing the field) is a visible, deliberate diff.
    """
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = deepcopy(payload)
    candidate["subject_refs"]["revocation_receipt_ref"] = {
        "revocation_receipt_id": "20000000-0000-4000-8000-000000000001",
        "object_hash": "7" * 64,
    }
    candidate["object_hash"] = object_hash(candidate)
    with pytest.raises(ValidationError) as caught:
        OutcomeEvent.model_validate(candidate)
    assert "extra_forbidden" in _reason_codes(caught.value)


def test_window_ended_at_equal_to_started_at_is_rejected(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = deepcopy(payload)
    candidate["window"]["ended_at"] = candidate["window"]["started_at"]
    candidate["object_hash"] = object_hash(candidate)
    with pytest.raises(ValidationError) as caught:
        OutcomeEvent.model_validate(candidate)
    assert "window_ended_at_not_later" in _reason_codes(caught.value)


def test_cohort_size_cannot_be_negative(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = deepcopy(payload)
    candidate["cohort"] = {"size": -1, "suppressed": False}
    candidate["object_hash"] = object_hash(candidate)
    with pytest.raises(ValidationError) as caught:
        OutcomeEvent.model_validate(candidate)
    assert "greater_than_equal" in _reason_codes(caught.value)
