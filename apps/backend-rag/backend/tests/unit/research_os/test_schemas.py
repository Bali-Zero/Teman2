from __future__ import annotations

import json

import pytest
from jsonschema import (  # type: ignore[import-untyped]
    Draft202012Validator,
    ValidationError,
)
from research_os.schemas import (
    SCHEMA_DIRECTORY,
    checked_in_schemas_match,
    validate_schema_artifacts,
)


def test_checked_in_schemas_are_byte_identical_to_fresh_regeneration() -> None:
    assert checked_in_schemas_match() == ()


def test_generated_schemas_are_valid_draft_2020_12() -> None:
    assert validate_schema_artifacts() == ()


@pytest.mark.parametrize(
    "invalid_timestamp",
    ("2026-02-01T08:01:00+08:00", "2026-02-01T00:01:00"),
    ids=("non_utc", "naive"),
)
def test_shipped_schema_asserts_utc_timestamp_offset(invalid_timestamp: str) -> None:
    schema_path = SCHEMA_DIRECTORY / "revocation_receipt.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    fixture_path = (
        SCHEMA_DIRECTORY.parents[1] / "fixtures" / "revocation_receipt" / "valid_minimal.json"
    )
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["issued_at"] = invalid_timestamp

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(payload)
