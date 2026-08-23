from __future__ import annotations

from research_os.schemas import checked_in_schemas_match, validate_schema_artifacts


def test_checked_in_schemas_are_byte_identical_to_fresh_regeneration() -> None:
    assert checked_in_schemas_match() == ()


def test_generated_schemas_are_valid_draft_2020_12() -> None:
    assert validate_schema_artifacts() == ()
