from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from pydantic import ValidationError
from research_os.cli import FIXTURES_ROOT
from research_os.hashing import object_hash
from research_os.models.metric_result import MetricResult
from research_os.schemas import SCHEMA_DIRECTORY

CONTRACT_KIND = "metric_result"


def _reason_codes(exc: ValidationError) -> set[str]:
    return {str(error["type"]) for error in exc.errors()}


def _rehash(payload: dict[str, Any]) -> dict[str, Any]:
    payload["object_hash"] = "0" * 64
    payload["object_hash"] = object_hash(payload)
    return payload


def test_valid_fixtures_round_trip(load_json: Any) -> None:
    schema = load_json(SCHEMA_DIRECTORY / f"{CONTRACT_KIND}.schema.json")
    for fixture_path in sorted((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json")):
        payload = load_json(fixture_path)
        Draft202012Validator(schema).validate(payload)
        instance = MetricResult.model_validate(payload)
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
            MetricResult.model_validate(load_json(fixture_path))
        assert expected in _reason_codes(caught.value), fixture_path.name


def test_fixing_the_declared_defect_makes_invalid_fixtures_valid(load_json: Any) -> None:
    """Rule 5: fixing ONLY the declared defect must make the document fully
    valid."""
    fixes: dict[str, Any] = {
        "invalid_object_hash_mismatch.json": lambda p: p,
        "invalid_unknown_top_level_field.json": lambda p: {
            k: v for k, v in p.items() if k != "unexpected_field"
        },
        "invalid_result_state_not_closed_enum.json": lambda p: {
            **p,
            "result_state": "insufficient_evidence",
        },
        "invalid_window_ended_at_not_later.json": lambda p: {
            **p,
            "window": {**p["window"], "ended_at": "2026-03-29T00:00:00Z"},
        },
        "invalid_sample_overall_negative.json": lambda p: {
            **p,
            "sample": {**p["sample"], "overall": 0},
        },
    }
    for filename, fix in fixes.items():
        payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / filename)
        fixed = fix(deepcopy(payload))
        fixed = _rehash(fixed)
        instance = MetricResult.model_validate(fixed)
        assert instance.object_hash == fixed["object_hash"], filename


def test_rejects_unknown_top_level_field(load_json: Any) -> None:
    fixture_path = next((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "unexpected": True}
    with pytest.raises(ValidationError):
        MetricResult.model_validate(payload)


def test_validation_context_cannot_bypass_exact_object_hash(load_json: Any) -> None:
    fixture_path = next((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "object_hash": "0" * 64}
    with pytest.raises(ValidationError) as caught:
        MetricResult.model_validate(payload, context={"skip_object_hash_check": True})
    assert "object_hash_mismatch" in _reason_codes(caught.value)


def test_metric_result_is_immutable(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    result = MetricResult.model_validate(payload)
    with pytest.raises(ValidationError):
        result.result_state = "measured"  # type: ignore[assignment]


def test_insufficient_evidence_result_omits_measurement_value(load_json: Any) -> None:
    """THE EXPENSIVE ONE, verified directly: a MetricResult reporting
    insufficient_evidence carries a measurement block with no value at all
    -- rule 9 ("insufficient_evidence is a valid outcome") made
    representable by NOT requiring measurement.value. The fixture omits the
    key entirely (never sets it to null) precisely so this fixture also
    satisfies the round-trip dump-equality test above."""
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    assert "value" not in payload["measurement"]
    result = MetricResult.model_validate(payload)
    assert result.result_state.value == "insufficient_evidence"
    assert result.measurement.value is None


def test_measurement_value_field_is_not_required(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_measured_with_extension.json")
    candidate = deepcopy(payload)
    del candidate["measurement"]["value"]
    candidate = _rehash(candidate)
    result = MetricResult.model_validate(candidate)  # must not raise "missing"
    assert result.measurement.value is None


def test_measurement_value_accepts_explicit_null_too(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_measured_with_extension.json")
    candidate = deepcopy(payload)
    candidate["measurement"] = {**candidate["measurement"], "value": None}
    candidate = _rehash(candidate)
    result = MetricResult.model_validate(candidate)
    assert result.measurement.value is None


def test_measured_pass_with_no_value_is_currently_accepted(load_json: Any) -> None:
    """OPEN RATIFICATION ITEM for the conductor -- pins the cost of the
    `value: Any = None` widening, not just its benefit.

    `insufficient_evidence` + no `value` is the case this widening exists
    for (see test_insufficient_evidence_result_omits_measurement_value
    above) and section 20 supports it directly via rule 9. But the same
    widening also accepts a `result_state == "measured"` +
    `gate_disposition == "pass"` document with NO `value` at all -- a
    result claiming to be a completed, passing measurement while reporting
    nothing measured. That is NOT separately named as invalid anywhere:
    section 20's enumerated invariant ("Unmet sample floors, unavailable
    denominators, failed mandatory guardrails, expired profiles, or
    invalidated inputs cannot be encoded as a passing measurement") lists
    five specific things that block a passing measurement and does not
    name a missing `value` as a sixth -- which is why this model does not
    extend that list on its own authority. Deliberate, not an oversight:
    inventing that sixth item would be exactly the "REJECT a document the
    spec's text permits" failure mode the P04-D1 mandate warns against,
    and getting it wrong in the strict direction is the unrecoverable one
    across a packet boundary (P05/P06 producers integrate against this
    kind) -- so the model errs wide here and this test exists so a future
    narrowing has to turn this specific case red on purpose, not land as
    a silent green-to-green cleanup.
    """
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_measured_with_extension.json")
    candidate = deepcopy(payload)
    del candidate["measurement"]["value"]
    candidate["result_state"] = "measured"
    candidate["gate_disposition"] = "pass"
    candidate = _rehash(candidate)
    result = MetricResult.model_validate(candidate)  # currently ACCEPTED -- see docstring
    assert result.result_state.value == "measured"
    assert result.gate_disposition.value == "pass"
    assert result.measurement.value is None


def test_measurement_unit_stays_required(load_json: Any) -> None:
    """Only `value` is relaxed by rule 9 -- `unit` keeps its literal
    required reading; nothing in section 20 or contract rule 9 exempts it."""
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = deepcopy(payload)
    del candidate["measurement"]["unit"]
    candidate = _rehash(candidate)
    with pytest.raises(ValidationError) as caught:
        MetricResult.model_validate(candidate)
    assert "missing" in _reason_codes(caught.value)


def test_result_state_reuses_the_closed_registry_enum(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    for closed_value in ("measured", "insufficient_evidence", "invalidated"):
        candidate = deepcopy(payload)
        candidate["result_state"] = closed_value
        MetricResult.model_validate(_rehash(candidate))  # innocence

    candidate = deepcopy(payload)
    candidate["result_state"] = "com.example.unregistered_state"
    with pytest.raises(ValidationError) as caught:
        MetricResult.model_validate(_rehash(candidate))  # guilt
    assert "enum" in _reason_codes(caught.value)


def test_gate_disposition_reuses_the_closed_registry_enum(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    for closed_value in ("pass", "fail", "insufficient_evidence", "not_applicable"):
        candidate = deepcopy(payload)
        candidate["gate_disposition"] = closed_value
        MetricResult.model_validate(_rehash(candidate))  # innocence

    candidate = deepcopy(payload)
    candidate["gate_disposition"] = "com.example.unregistered_disposition"
    with pytest.raises(ValidationError) as caught:
        MetricResult.model_validate(_rehash(candidate))  # guilt
    assert "enum" in _reason_codes(caught.value)


def test_guardrail_result_verdict_is_closed_to_exactly_three_values(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_measured_with_extension.json")
    for closed_value in ("pass", "fail", "insufficient_evidence"):
        candidate = deepcopy(payload)
        candidate["guardrail_results"] = [
            {"metric_name": "com.example.refund_rate", "result": closed_value}
        ]
        MetricResult.model_validate(_rehash(candidate))  # innocence

    candidate = deepcopy(payload)
    candidate["guardrail_results"] = [
        {"metric_name": "com.example.refund_rate", "result": "pass_with_limits"}
    ]
    with pytest.raises(ValidationError) as caught:
        MetricResult.model_validate(_rehash(candidate))  # guilt: not one of the three
    assert "literal_error" in _reason_codes(caught.value)


def test_decision_rule_evaluation_result_shares_the_same_closed_verdict(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = deepcopy(payload)
    candidate["decision_rule_evaluation"] = {
        "result": "not_applicable",
        "reason_codes": [],
    }
    with pytest.raises(ValidationError) as caught:
        MetricResult.model_validate(_rehash(candidate))
    assert "literal_error" in _reason_codes(caught.value)


def test_window_ended_at_equal_to_started_at_is_rejected(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = deepcopy(payload)
    candidate["window"]["ended_at"] = candidate["window"]["started_at"]
    with pytest.raises(ValidationError) as caught:
        MetricResult.model_validate(_rehash(candidate))
    assert "window_ended_at_not_later" in _reason_codes(caught.value)


def test_data_cutoff_at_is_not_ordered_against_the_window(load_json: Any) -> None:
    """Deliberately NOT enforced -- see module docstring. A data_cutoff_at
    earlier than started_at is unusual but not spec-forbidden; asserting
    this stays valid pins that the model does not silently narrow it."""
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = deepcopy(payload)
    candidate["window"]["data_cutoff_at"] = candidate["window"]["started_at"]
    result = MetricResult.model_validate(_rehash(candidate))
    assert result.window.data_cutoff_at == result.window.started_at


def test_sample_counts_cannot_be_negative(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_measured_with_extension.json")

    candidate = deepcopy(payload)
    candidate["sample"]["subgroups"] = [{"name": "com.example.x", "size": -1}]
    with pytest.raises(ValidationError) as caught:
        MetricResult.model_validate(_rehash(candidate))
    assert "greater_than_equal" in _reason_codes(caught.value)

    candidate = deepcopy(payload)
    candidate["sample"]["exclusions"] = [
        {"reason_code": "com.example.excl_test_accounts", "count": -1}
    ]
    with pytest.raises(ValidationError) as caught:
        MetricResult.model_validate(_rehash(candidate))
    assert "greater_than_equal" in _reason_codes(caught.value)


def test_empty_guardrail_results_and_reason_codes_are_valid(load_json: Any) -> None:
    """Rule 9 corollary: an empty array is not a forced non-empty
    requirement anywhere in this kind -- a passing/uneventful result can
    legitimately carry zero guardrail_results and zero reason_codes."""
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    result = MetricResult.model_validate(payload)
    assert result.guardrail_results == ()


def test_reason_codes_accept_free_text_not_just_dotted_names(load_json: Any) -> None:
    """Section 20 types the top-level reason_codes as plain "string", not
    "registered namespaced string" (contrast RevocationReceipt.reason_code)
    -- a free-text reason without a dot/dash/underscore separator must not
    be rejected."""
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = deepcopy(payload)
    candidate["reason_codes"] = ["sample too small this window"]
    result = MetricResult.model_validate(_rehash(candidate))
    assert result.reason_codes == ("sample too small this window",)


def test_supersedes_ref_is_optional_and_binds_a_prior_result(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_superseding_result.json")
    result = MetricResult.model_validate(payload)
    assert result.supersedes_metric_result_ref is not None
    assert (
        str(result.supersedes_metric_result_ref.metric_result_id)
        == "c0000000-0000-4000-8000-000000000002"
    )


def test_extensions_reject_a_shadowed_core_field(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    candidate = deepcopy(payload)
    candidate["extensions"] = {
        "com.balizero.example": {
            "extension_version": "1.0.0",
            "payload": {"metric_profile_ref": "should not be allowed to shadow the core field"},
        }
    }
    candidate = _rehash(candidate)
    with pytest.raises(ValueError):
        MetricResult.model_validate(candidate)
