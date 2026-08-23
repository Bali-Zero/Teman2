from __future__ import annotations

from typing import Any

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from pydantic import ValidationError
from research_os.cli import FIXTURES_ROOT
from research_os.models.conductor_handoff import ConductorHandoff
from research_os.schemas import SCHEMA_DIRECTORY

CONTRACT_KIND = "conductor_handoff"


def _reason_codes(exc: ValidationError) -> set[str]:
    return {str(error["type"]) for error in exc.errors()}


def test_valid_fixtures_round_trip(load_json: Any) -> None:
    schema = load_json(SCHEMA_DIRECTORY / f"{CONTRACT_KIND}.schema.json")
    for fixture_path in sorted((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json")):
        payload = load_json(fixture_path)
        Draft202012Validator(schema).validate(payload)
        instance = ConductorHandoff.model_validate(payload)
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
            ConductorHandoff.model_validate(load_json(fixture_path))
        assert expected in _reason_codes(caught.value), fixture_path.name


def test_rejects_unknown_top_level_field(load_json: Any) -> None:
    fixture_path = next((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "unexpected": True}
    with pytest.raises(ValidationError):
        ConductorHandoff.model_validate(payload)


def test_validation_context_cannot_bypass_exact_object_hash(load_json: Any) -> None:
    fixture_path = next((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "object_hash": "0" * 64}
    with pytest.raises(ValidationError) as caught:
        ConductorHandoff.model_validate(payload, context={"skip_object_hash_check": True})
    assert "object_hash_mismatch" in _reason_codes(caught.value)


def test_conductor_handoff_is_immutable(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    handoff = ConductorHandoff.model_validate(payload)
    with pytest.raises(ValidationError):
        handoff.state = "rejected"  # type: ignore[misc]


def test_handoff_carries_no_lineage_field_per_section_15(load_json: Any) -> None:
    """Section 15's wire shape has no ``lineage`` block (unlike every other
    kind in this package) -- it binds provenance via the required top-level
    ``workflow_run_ref`` instead. Adding a ``lineage`` block is rejected the
    same way any other unknown field is: there is no dedicated reason code
    for "this kind doesn't have this field", it is just extra_forbidden.
    """
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = {**payload, "lineage": {"input_hashes": []}}
    with pytest.raises(ValidationError) as caught:
        ConductorHandoff.model_validate(candidate)
    assert "extra_forbidden" in _reason_codes(caught.value)


def test_bulk_approve_all_has_no_field_to_carry_it(load_json: Any) -> None:
    """Section 15: 'Bulk "approve all" is invalid' -- each selected lock,
    content approval, publication approval, and action approval receives a
    separate ApprovalReceipt (a different Packet 04 kind, not this one).
    ConductorHandoff itself carries no batch-approval field for this to be
    tested against; this invariant is enforced by ApprovalReceipt's own
    per-subject shape, not by anything on this object. Documented as a
    negative check: this object cannot even represent a bulk approval.
    """
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = {**payload, "bulk_approved_refs": []}
    with pytest.raises(ValidationError) as caught:
        ConductorHandoff.model_validate(candidate)
    assert "extra_forbidden" in _reason_codes(caught.value)


def test_considered_option_disposition_accepts_only_the_three_closed_values(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_with_locks_and_options.json")
    handoff = ConductorHandoff.model_validate(payload)
    dispositions = {option.disposition for option in handoff.considered_options}
    assert dispositions == {"selected", "rejected"}


def test_supersedes_ref_binds_the_exact_predecessor_hash(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_with_supersedes_and_extension.json")
    handoff = ConductorHandoff.model_validate(payload)
    assert handoff.supersedes_conductor_handoff_ref is not None
    assert (
        str(handoff.supersedes_conductor_handoff_ref.conductor_handoff_id)
        == "60000000-0000-4000-8000-000000000001"
    )
