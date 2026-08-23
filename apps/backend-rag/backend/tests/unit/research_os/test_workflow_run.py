from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from pydantic import ValidationError
from research_os.cli import FIXTURES_ROOT
from research_os.hashing import object_hash
from research_os.models.workflow_run import WorkflowRun
from research_os.schemas import SCHEMA_DIRECTORY

CONTRACT_KIND = "workflow_run"


def _reason_codes(exc: ValidationError) -> set[str]:
    return {str(error["type"]) for error in exc.errors()}


def test_valid_fixtures_round_trip(load_json: Any) -> None:
    schema = load_json(SCHEMA_DIRECTORY / f"{CONTRACT_KIND}.schema.json")
    for fixture_path in sorted((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json")):
        payload = load_json(fixture_path)
        Draft202012Validator(schema).validate(payload)
        instance = WorkflowRun.model_validate(payload)
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
            WorkflowRun.model_validate(load_json(fixture_path))
        assert expected in _reason_codes(caught.value), fixture_path.name


def test_rejects_unknown_top_level_field(load_json: Any) -> None:
    fixture_path = next((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "unexpected": True}
    with pytest.raises(ValidationError):
        WorkflowRun.model_validate(payload)


def test_validation_context_cannot_bypass_exact_object_hash(load_json: Any) -> None:
    fixture_path = next((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "object_hash": "0" * 64}
    with pytest.raises(ValidationError) as caught:
        WorkflowRun.model_validate(payload, context={"skip_object_hash_check": True})
    assert "object_hash_mismatch" in _reason_codes(caught.value)


def test_workflow_run_is_immutable(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    run = WorkflowRun.model_validate(payload)
    with pytest.raises(ValidationError):
        run.state = "failed"  # type: ignore[misc]


def _revalidated(payload: dict[str, Any], **updates: Any) -> dict[str, Any]:
    candidate = deepcopy(payload)
    candidate.update(updates)
    candidate.pop("object_hash", None)
    candidate["object_hash"] = object_hash(candidate)
    return candidate


def test_run_revision_one_rejects_a_predecessor_ref(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = _revalidated(
        payload,
        supersedes_workflow_run_ref={
            "workflow_run_id": "30000000-0000-4000-8000-000000000099",
            "object_hash": "9" * 64,
        },
    )
    with pytest.raises(ValidationError) as caught:
        WorkflowRun.model_validate(candidate)
    assert "first_revision_has_predecessor" in _reason_codes(caught.value)


def test_later_revision_requires_a_predecessor_ref(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_with_supersedes.json")
    candidate = deepcopy(payload)
    del candidate["supersedes_workflow_run_ref"]
    candidate["object_hash"] = object_hash(candidate)
    with pytest.raises(ValidationError) as caught:
        WorkflowRun.model_validate(candidate)
    assert "later_revision_missing_predecessor" in _reason_codes(caught.value)


def test_run_revision_two_with_matching_predecessor_is_valid(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_with_supersedes.json")
    run = WorkflowRun.model_validate(payload)
    assert run.run_revision == 2
    assert run.supersedes_workflow_run_ref is not None


def test_ended_at_must_be_later_than_started_at(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_completed_with_extension.json")
    candidate = _revalidated(payload, ended_at="2026-01-01T00:00:00Z")
    with pytest.raises(ValidationError) as caught:
        WorkflowRun.model_validate(candidate)
    assert "run_ended_at_not_later" in _reason_codes(caught.value)


def test_step_ended_at_must_be_later_than_step_started_at(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_completed_with_extension.json")
    candidate = deepcopy(payload)
    candidate["steps"][0]["ended_at"] = "2026-01-01T00:00:00Z"
    candidate["object_hash"] = object_hash(candidate)
    with pytest.raises(ValidationError) as caught:
        WorkflowRun.model_validate(candidate)
    assert "step_ended_at_not_later" in _reason_codes(caught.value)
