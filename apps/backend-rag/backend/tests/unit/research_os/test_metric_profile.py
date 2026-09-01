from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from pydantic import ValidationError
from research_os.cli import FIXTURES_ROOT
from research_os.hashing import object_hash
from research_os.models.metric_profile import MetricProfile
from research_os.schemas import SCHEMA_DIRECTORY

CONTRACT_KIND = "metric_profile"


def _reason_codes(exc: ValidationError) -> set[str]:
    return {str(error["type"]) for error in exc.errors()}


def _rehash(payload: dict[str, Any]) -> dict[str, Any]:
    payload["object_hash"] = "0" * 64
    payload["object_hash"] = object_hash(payload)
    return payload


def test_valid_fixtures_round_trip(load_json: Any) -> None:
    schema = load_json(SCHEMA_DIRECTORY / f"{CONTRACT_KIND}.schema.json")
    fixture_paths = sorted((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json"))
    # Lower bound, not merely non-empty: a silently emptied/renamed fixture
    # directory would otherwise make this loop pass having asserted nothing.
    assert len(fixture_paths) >= 3, "expected at least the 3 known valid metric_profile fixtures"
    for fixture_path in fixture_paths:
        payload = load_json(fixture_path)
        Draft202012Validator(schema).validate(payload)
        instance = MetricProfile.model_validate(payload)
        assert instance.model_dump(mode="json", exclude_none=True) == payload, fixture_path.name


def test_invalid_fixtures_reject_with_exact_expected_reason(load_json: Any) -> None:
    fixture_paths = sorted(
        path
        for path in (FIXTURES_ROOT / CONTRACT_KIND).glob("invalid_*.json")
        if not path.name.endswith(".expect.json")
    )
    # Lower bound, not merely non-empty -- see test_valid_fixtures_round_trip above.
    assert len(fixture_paths) >= 5, "expected at least the 5 known invalid metric_profile fixtures"
    for fixture_path in fixture_paths:
        expected = load_json(fixture_path.with_suffix(".expect.json"))["reason_code"]
        with pytest.raises(ValidationError) as caught:
            MetricProfile.model_validate(load_json(fixture_path))
        assert expected in _reason_codes(caught.value), fixture_path.name


def test_fixing_the_declared_defect_makes_invalid_fixtures_valid(load_json: Any) -> None:
    """Rule 5: fixing ONLY the declared defect must make the document fully
    valid -- guards against a second, undeclared reason hiding in the same
    fixture (e.g. a stale object_hash left over from mutation)."""
    fixes: dict[str, Any] = {
        "invalid_object_hash_mismatch.json": lambda p: p,  # object_hash itself is the fix target
        "invalid_unknown_top_level_field.json": lambda p: {
            k: v for k, v in p.items() if k != "unexpected_field"
        },
        "invalid_missing_data_policy_not_closed.json": lambda p: {
            **p,
            "missing_data_policy": "exclude",
        },
        "invalid_validity_expires_at_not_later.json": lambda p: {
            **p,
            "validity": {**p["validity"], "expires_at": "2026-04-01T00:00:00Z"},
        },
        "invalid_numerator_missing.json": lambda p: {**p, "numerator": None},
    }
    for filename, fix in fixes.items():
        payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / filename)
        fixed = fix(deepcopy(payload))
        fixed = _rehash(fixed)
        instance = MetricProfile.model_validate(fixed)
        assert instance.object_hash == fixed["object_hash"], filename


def test_rejects_unknown_top_level_field(load_json: Any) -> None:
    fixture_path = next((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "unexpected": True}
    with pytest.raises(ValidationError):
        MetricProfile.model_validate(payload)


def test_validation_context_cannot_bypass_exact_object_hash(load_json: Any) -> None:
    fixture_path = next((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "object_hash": "0" * 64}
    with pytest.raises(ValidationError) as caught:
        MetricProfile.model_validate(payload, context={"skip_object_hash_check": True})
    assert "object_hash_mismatch" in _reason_codes(caught.value)


def test_metric_profile_is_immutable(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    profile = MetricProfile.model_validate(payload)
    with pytest.raises(ValidationError):
        profile.metric_name = "com.example.other"


def test_numerator_and_denominator_are_required_keys(load_json: Any) -> None:
    """No `?` on either field in section 19 -- the key must be present even
    though its value type (Any) would otherwise accept an absent default."""
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    for field in ("numerator", "denominator"):
        candidate = deepcopy(payload)
        del candidate[field]
        candidate = _rehash(candidate)
        with pytest.raises(ValidationError) as caught:
            MetricProfile.model_validate(candidate)
        assert "missing" in _reason_codes(caught.value), field


def test_numerator_and_denominator_accept_explicit_null(load_json: Any) -> None:
    """The spec's "exact definition or null" -- proven directly against the model
    rather than via a checked-in valid_*.json fixture: `model_dump(...,
    exclude_none=True)` (used by the round-trip test above, matching every
    sibling kind's test convention) drops any None-valued field from the
    dump, so a fixture that set these fields to null could never satisfy
    that round-trip equality. This test targets the nullability contract
    directly instead."""
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = deepcopy(payload)
    candidate["numerator"] = None
    candidate["denominator"] = None
    candidate = _rehash(candidate)
    profile = MetricProfile.model_validate(candidate)
    assert profile.numerator is None
    assert profile.denominator is None


def test_baseline_window_accepts_explicit_null(load_json: Any) -> None:
    """baseline.window is given no field names at all in the spec prose --
    typed Any and required; proving null acceptance the same way as
    numerator/denominator above, for the same round-trip-dump reason."""
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = deepcopy(payload)
    candidate["baseline"] = {**candidate["baseline"], "window": None}
    candidate = _rehash(candidate)
    profile = MetricProfile.model_validate(candidate)
    assert profile.baseline.window is None


def test_missing_data_policy_rejects_a_value_outside_the_closed_three(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    for closed_value in ("exclude", "impute_registered", "insufficient_evidence"):
        candidate = deepcopy(payload)
        candidate["missing_data_policy"] = closed_value
        candidate = _rehash(candidate)
        MetricProfile.model_validate(candidate)  # innocence: every permitted value passes

    candidate = deepcopy(payload)
    candidate["missing_data_policy"] = "com.example.unregistered_policy"
    candidate = _rehash(candidate)
    with pytest.raises(ValidationError) as caught:
        MetricProfile.model_validate(candidate)
    assert "literal_error" in _reason_codes(caught.value)  # guilt


def test_validity_expires_at_must_be_strictly_later_than_valid_from(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")

    # innocence: a real gap passes
    candidate = deepcopy(payload)
    candidate["validity"] = {
        "valid_from": "2026-03-01T00:00:00Z",
        "expires_at": "2026-03-02T00:00:00Z",
    }
    MetricProfile.model_validate(_rehash(candidate))

    # guilt: equal timestamps are rejected
    candidate = deepcopy(payload)
    candidate["validity"] = {
        "valid_from": "2026-03-01T00:00:00Z",
        "expires_at": "2026-03-01T00:00:00Z",
    }
    with pytest.raises(ValidationError) as caught:
        MetricProfile.model_validate(_rehash(candidate))
    assert "expires_at_not_later" in _reason_codes(caught.value)

    # guilt: an earlier expires_at is rejected too
    candidate = deepcopy(payload)
    candidate["validity"] = {
        "valid_from": "2026-03-01T00:00:00Z",
        "expires_at": "2026-02-01T00:00:00Z",
    }
    with pytest.raises(ValidationError) as caught:
        MetricProfile.model_validate(_rehash(candidate))
    assert "expires_at_not_later" in _reason_codes(caught.value)


def test_minimum_sample_overall_cannot_be_negative(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")

    candidate = deepcopy(payload)
    candidate["minimum_sample"] = {"overall": 0}
    MetricProfile.model_validate(_rehash(candidate))  # innocence: 0 is a legitimate floor

    candidate = deepcopy(payload)
    candidate["minimum_sample"] = {"overall": -1}
    with pytest.raises(ValidationError) as caught:
        MetricProfile.model_validate(_rehash(candidate))
    assert "greater_than_equal" in _reason_codes(caught.value)


def test_extensions_reject_a_shadowed_core_field(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = deepcopy(payload)
    candidate["extensions"] = {
        "com.balizero.example": {
            "extension_version": "1.0.0",
            "payload": {"object_hash": "should not be allowed to shadow the core field"},
        }
    }
    candidate = _rehash(candidate)
    with pytest.raises(ValueError):
        MetricProfile.model_validate(candidate)
