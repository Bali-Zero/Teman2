from __future__ import annotations

import itertools
from copy import deepcopy
from typing import Any
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from pydantic import ValidationError
from research_os.cli import FIXTURES_ROOT
from research_os.graph import Current, GraphMember, Quarantined, select_current_member
from research_os.hashing import object_hash
from research_os.models.outcome_event import OutcomeEvent
from research_os.models.successor_edge import ObjectSuccessorEdge
from research_os.schemas import SCHEMA_DIRECTORY

CONTRACT_KIND = "outcome_event"


def _reason_codes(exc: ValidationError) -> set[str]:
    return {str(error["type"]) for error in exc.errors()}


def test_valid_fixtures_round_trip(load_json: Any) -> None:
    schema = load_json(SCHEMA_DIRECTORY / f"{CONTRACT_KIND}.schema.json")
    fixture_paths = sorted((FIXTURES_ROOT / CONTRACT_KIND).glob("valid_*.json"))
    # An empty glob (fixtures dir renamed/emptied) would otherwise make this
    # loop pass having validated zero fixtures -- assert it actually found
    # some before trusting the loop below.
    assert fixture_paths, f"expected at least one valid fixture for {CONTRACT_KIND}"
    for fixture_path in fixture_paths:
        payload = load_json(fixture_path)
        Draft202012Validator(schema).validate(payload)
        instance = OutcomeEvent.model_validate(payload)
        assert instance.model_dump(mode="json", exclude_none=True) == payload, fixture_path.name


def test_invalid_fixtures_reject_with_exact_expected_reason(load_json: Any) -> None:
    fixture_paths = sorted(
        path
        for path in (FIXTURES_ROOT / CONTRACT_KIND).glob("invalid_*.json")
        if not path.name.endswith(".expect.json")
    )
    # Same empty-glob hole as test_valid_fixtures_round_trip above.
    assert fixture_paths, f"expected at least one invalid fixture for {CONTRACT_KIND}"
    for fixture_path in fixture_paths:
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


# ---------------------------------------------------------------------------
# Adversarial-review findings, 2026-08-23.
# ---------------------------------------------------------------------------


def _graph_member_from_payload(payload: dict[str, Any]) -> GraphMember:
    return GraphMember(
        object_kind=CONTRACT_KIND,
        object_id=payload["outcome_event_id"],
        object_hash=payload["object_hash"],
        tenant=payload["tenant"],
        family_id=payload["outcome_event_family_id"],
        recorded_at=payload["recorded_at"],
    )


def _successor_edge(predecessor: GraphMember, successor: GraphMember) -> ObjectSuccessorEdge:
    edge_payload = {
        "object_successor_edge_id": str(uuid4()),
        "contract_version": "research-os/v1.0.0",
        "tenant": "bali-zero",
        "object_kind": predecessor.object_kind,
        "family_id": predecessor.family_id,
        "predecessor_ref": predecessor.exact_ref.model_dump(mode="json"),
        "successor_ref": successor.exact_ref.model_dump(mode="json"),
        "reason_code": "com.example.corrected",
        "recorded_at": successor.recorded_at.isoformat().replace("+00:00", "Z"),
        "producer": {"name": "synthetic.test", "version": "1.0.0"},
        "lineage": {"input_hashes": []},
        "retention": {"retention_class": "audit", "legal_hold": False},
    }
    edge_payload["object_hash"] = object_hash(edge_payload)
    return ObjectSuccessorEdge.model_validate(edge_payload)


def test_supersedes_fixture_is_current_in_the_real_graph_resolver(load_json: Any) -> None:
    """Finding: `valid_with_supersedes_and_extension.json` supersedes
    `valid_minimal.json` but the two used to carry the BYTE-IDENTICAL
    `recorded_at`. `graph.py::select_current_member` quarantines a
    successor whose `recorded_at` is not strictly later than its
    predecessor's (`successor_recorded_at_not_later`, CONTRACTS.md:863
    requires a later `recorded_at` for a correction) -- so the one fixture
    whose entire purpose is to demonstrate a working supersedes chain was
    rejected by the resolver it exists to exercise, despite being named
    `valid_*`.

    Proves BOTH arms through the REAL resolver (not a re-implementation of
    its logic): the fixed fixture returns `Current`, and the old
    tied-timestamp shape returns exactly
    `Quarantined(('successor_recorded_at_not_later',))`. A test that only
    asserts the good arm cannot tell you the guard actually works.
    """
    predecessor_payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")
    successor_payload = load_json(
        FIXTURES_ROOT / CONTRACT_KIND / "valid_with_supersedes_and_extension.json"
    )

    predecessor = _graph_member_from_payload(predecessor_payload)
    successor = _graph_member_from_payload(successor_payload)

    # Arm 1: the fixed fixture (strictly-later recorded_at) resolves Current.
    edge = _successor_edge(predecessor, successor)
    result = select_current_member([edge], [predecessor, successor])
    assert isinstance(result, Current), result
    assert result.member == successor

    # Arm 2: reproduce the ORIGINAL defect (byte-identical recorded_at) and
    # prove the guard actually fires -- the tied successor must quarantine
    # with exactly successor_recorded_at_not_later, not silently pass.
    tied_successor = successor.model_copy(update={"recorded_at": predecessor.recorded_at})
    tied_edge = _successor_edge(predecessor, tied_successor)
    tied_result = select_current_member([tied_edge], [predecessor, tied_successor])
    assert isinstance(tied_result, Quarantined), tied_result
    assert tied_result.reason_codes == ("successor_recorded_at_not_later",)


def test_metric_profile_and_result_schema_and_model_agree_on_all_nine_cases(
    load_json: Any,
) -> None:
    """Finding: the checked-in schema had zero if/then/allOf/oneOf/
    dependentRequired -- the metric_profile_ref/metric_result_ref
    joint-presence invariant (CONTRACTS.md:865, enforced in
    outcome_event.py's validate_event()) lived ONLY in Python. A consumer
    validating against the published schema alone would accept a document
    the model rejects.

    A bare `dependentRequired` would be insufficient on its own: it tests
    KEY PRESENCE, not VALUE, and this contract uses presence-preserving
    null semantics (hashing.py) where an absent key and an explicit `null`
    are different wire documents. A document with both keys PRESENT but one
    explicitly `null` would slip past `dependentRequired` while still being
    rejected by the model. This test enumerates every combination of
    {absent, explicit null, present-with-value} across both fields -- nine
    cases -- and asserts the schema verdict and the model verdict AGREE on
    all nine. One passing example proves nothing here.
    """
    schema = load_json(SCHEMA_DIRECTORY / f"{CONTRACT_KIND}.schema.json")
    validator = Draft202012Validator(schema)
    base_payload = load_json(FIXTURES_ROOT / CONTRACT_KIND / "valid_minimal.json")

    profile_value = {
        "metric_profile_id": "d0000000-0000-4000-8000-000000000001",
        "object_hash": "1" * 64,
    }
    result_value = {
        "metric_result_id": "d0000000-0000-4000-8000-000000000002",
        "object_hash": "2" * 64,
    }
    cases = ("absent", "null", "value")
    # (profile_case, result_case) -> expected ACCEPT/REJECT, derived from the
    # model's own rule: jointly None-class (absent or null on BOTH sides) or
    # jointly value-bearing accepts; any mismatch rejects.
    none_class = {"absent", "null"}
    expected_by_case = {
        (p, r): "ACCEPT" if (p in none_class) == (r in none_class) else "REJECT"
        for p, r in itertools.product(cases, cases)
    }

    table: list[tuple[str, str, str, str]] = []
    for profile_case, result_case in itertools.product(cases, cases):
        candidate = deepcopy(base_payload)
        if profile_case == "value":
            candidate["metric_profile_ref"] = profile_value
        elif profile_case == "null":
            candidate["metric_profile_ref"] = None
        # "absent" -> leave the key unset entirely.
        if result_case == "value":
            candidate["metric_result_ref"] = result_value
        elif result_case == "null":
            candidate["metric_result_ref"] = None

        candidate.pop("object_hash", None)
        candidate["object_hash"] = object_hash(candidate)

        schema_verdict = "REJECT" if list(validator.iter_errors(candidate)) else "ACCEPT"
        try:
            OutcomeEvent.model_validate(candidate)
            model_verdict = "ACCEPT"
        except ValidationError:
            model_verdict = "REJECT"

        table.append((profile_case, result_case, schema_verdict, model_verdict))
        expected = expected_by_case[(profile_case, result_case)]
        assert schema_verdict == model_verdict == expected, (
            f"disagreement at profile={profile_case!r} result={result_case!r}: "
            f"schema={schema_verdict} model={model_verdict} expected={expected}"
        )

    # All nine combinations must have actually run (guards against a
    # silently-narrowed itertools.product call passing on fewer than 9).
    assert len(table) == 9, table
