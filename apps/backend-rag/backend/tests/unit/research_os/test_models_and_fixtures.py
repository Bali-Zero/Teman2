from __future__ import annotations

from typing import Any

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from pydantic import BaseModel, ValidationError
from research_os.cli import FIXTURES_ROOT
from research_os.models.revocation_receipt import RevocationReceipt
from research_os.models.successor_edge import ObjectSuccessorEdge
from research_os.schemas import SCHEMA_DIRECTORY

CONTRACT_MODELS: dict[str, type[BaseModel]] = {
    "object_successor_edge": ObjectSuccessorEdge,
    "revocation_receipt": RevocationReceipt,
}


def _reason_codes(exc: ValidationError) -> set[str]:
    return {str(error["type"]) for error in exc.errors()}


@pytest.mark.parametrize("contract_kind", sorted(CONTRACT_MODELS))
def test_valid_fixtures_round_trip(contract_kind: str, load_json: Any) -> None:
    model = CONTRACT_MODELS[contract_kind]
    for fixture_path in sorted((FIXTURES_ROOT / contract_kind).glob("valid_*.json")):
        payload = load_json(fixture_path)
        schema = load_json(SCHEMA_DIRECTORY / f"{contract_kind}.schema.json")
        Draft202012Validator(schema).validate(payload)
        instance = model.model_validate(payload)
        assert instance.model_dump(mode="json", exclude_none=True) == payload


@pytest.mark.parametrize("contract_kind", sorted(CONTRACT_MODELS))
def test_invalid_fixtures_reject_with_exact_expected_reason(
    contract_kind: str, load_json: Any
) -> None:
    model = CONTRACT_MODELS[contract_kind]
    fixture_paths = (
        path
        for path in (FIXTURES_ROOT / contract_kind).glob("invalid_*.json")
        if not path.name.endswith(".expect.json")
    )
    for fixture_path in sorted(fixture_paths):
        expected = load_json(fixture_path.with_suffix(".expect.json"))["reason_code"]
        with pytest.raises(ValidationError) as caught:
            model.model_validate(load_json(fixture_path))
        assert expected in _reason_codes(caught.value), fixture_path.name


@pytest.mark.parametrize("model", CONTRACT_MODELS.values())
def test_contract_models_reject_unknown_top_level_fields(
    model: type[BaseModel], load_json: Any
) -> None:
    contract_kind = next(kind for kind, candidate in CONTRACT_MODELS.items() if candidate is model)
    fixture_path = next((FIXTURES_ROOT / contract_kind).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "unexpected": True}
    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("model", CONTRACT_MODELS.values())
def test_validation_context_cannot_bypass_exact_object_hash(
    model: type[BaseModel], load_json: Any
) -> None:
    contract_kind = next(kind for kind, candidate in CONTRACT_MODELS.items() if candidate is model)
    fixture_path = next((FIXTURES_ROOT / contract_kind).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "object_hash": "0" * 64}

    with pytest.raises(ValidationError) as caught:
        model.model_validate(
            payload,
            context={"skip_object_hash_check": True},
        )

    assert "object_hash_mismatch" in _reason_codes(caught.value)
