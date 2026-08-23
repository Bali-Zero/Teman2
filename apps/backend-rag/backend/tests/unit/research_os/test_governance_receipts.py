"""Packet 04 deliverable 1: the governance receipts (CONTRACTS.md sections
17-18) -- SanitizationReceipt and RiskReclassificationReceipt. These are the
ONLY two instruments in ``research-os/v1.0.0`` that may ever lower a
classification dimension (section 1 rule 7); every guard exercised here must
fail CLOSED.

Kept as its own file rather than extending ``test_models_and_fixtures.py``
for the same reason as the sibling decision-chain lane's
``test_decision_chain.py``: several lanes are concurrently building other
sections of this contract family in the same tree, and the shared
``CONTRACT_MODELS`` dict there is a natural collision point. This file
duplicates the generic fixture-coverage shape (round trip against schema +
model, invalid-reason-code check, reject-unknown-top-level-field,
hash-bypass resistance, frozen-mutation rejection) scoped to only the two
kinds this module owns, then adds the cross-object authorization checks no
single JSON fixture can express.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from pydantic import BaseModel, ValidationError
from research_os.cli import FIXTURES_ROOT
from research_os.graph import GraphMember, Quarantined, select_current_member
from research_os.hashing import object_hash
from research_os.models.risk_reclassification_receipt import (
    RiskReclassificationReceipt,
    risk_reclassification_authorizes_output,
)
from research_os.models.sanitization_receipt import (
    SanitizationReceipt,
    sanitization_authorizes_output,
)
from research_os.primitives import ExactObjectRef
from research_os.schemas import SCHEMA_DIRECTORY

GOVERNANCE_RECEIPT_MODELS: dict[str, type[BaseModel]] = {
    "risk_reclassification_receipt": RiskReclassificationReceipt,
    "sanitization_receipt": SanitizationReceipt,
}


def _reason_codes(exc: ValidationError) -> set[str]:
    return {str(error["type"]) for error in exc.errors()}


def _revalidated(model: type[BaseModel], payload: dict[str, Any], **updates: Any) -> Any:
    """Deepcopy a valid fixture, apply field updates, recompute
    object_hash, and validate -- same helper shape as the sibling
    decision-chain lane's ``test_decision_chain.py::_revalidated``.
    """

    candidate = deepcopy(payload)
    candidate.update(updates)
    candidate.pop("object_hash", None)
    candidate["object_hash"] = object_hash(candidate)
    return model.model_validate(candidate)


# ---------------------------------------------------------------------------
# Generic fixture coverage (scoped to the two governance-receipt kinds)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("contract_kind", sorted(GOVERNANCE_RECEIPT_MODELS))
def test_valid_fixtures_round_trip(contract_kind: str, load_json: Any) -> None:
    model = GOVERNANCE_RECEIPT_MODELS[contract_kind]
    fixture_paths = sorted((FIXTURES_ROOT / contract_kind).glob("valid_*.json"))
    assert len(fixture_paths) >= 3, f"expected at least 3 valid fixtures for {contract_kind}"
    for fixture_path in fixture_paths:
        payload = load_json(fixture_path)
        schema = load_json(SCHEMA_DIRECTORY / f"{contract_kind}.schema.json")
        Draft202012Validator(schema).validate(payload)
        instance = model.model_validate(payload)
        assert instance.model_dump(mode="json", exclude_none=True) == payload


@pytest.mark.parametrize("contract_kind", sorted(GOVERNANCE_RECEIPT_MODELS))
def test_invalid_fixtures_reject_with_exact_expected_reason(
    contract_kind: str, load_json: Any
) -> None:
    model = GOVERNANCE_RECEIPT_MODELS[contract_kind]
    fixture_paths = [
        path
        for path in sorted((FIXTURES_ROOT / contract_kind).glob("invalid_*.json"))
        if not path.name.endswith(".expect.json")
    ]
    assert len(fixture_paths) >= 3, f"expected at least 3 invalid fixtures for {contract_kind}"
    for fixture_path in fixture_paths:
        expected = load_json(fixture_path.with_suffix(".expect.json"))["reason_code"]
        with pytest.raises(ValidationError) as caught:
            model.model_validate(load_json(fixture_path))
        codes = _reason_codes(caught.value)
        assert codes == {expected}, (
            f"{fixture_path.name}: expected singleton reason {{{expected}}}, got {codes} "
            "(rule 5: fixing only the declared defect must make the document fully valid)"
        )


@pytest.mark.parametrize("contract_kind", sorted(GOVERNANCE_RECEIPT_MODELS))
def test_rejects_unknown_top_level_field(contract_kind: str, load_json: Any) -> None:
    model = GOVERNANCE_RECEIPT_MODELS[contract_kind]
    fixture_path = next((FIXTURES_ROOT / contract_kind).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "unexpected_field": True}
    with pytest.raises(ValidationError) as caught:
        model.model_validate(payload)
    assert "extra_forbidden" in _reason_codes(caught.value)


@pytest.mark.parametrize("contract_kind", sorted(GOVERNANCE_RECEIPT_MODELS))
def test_validation_context_cannot_bypass_exact_object_hash(
    contract_kind: str, load_json: Any
) -> None:
    model = GOVERNANCE_RECEIPT_MODELS[contract_kind]
    fixture_path = next((FIXTURES_ROOT / contract_kind).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "object_hash": "0" * 64}
    with pytest.raises(ValidationError) as caught:
        model.model_validate(payload, context={"skip_object_hash_check": True})
    assert "object_hash_mismatch" in _reason_codes(caught.value)


@pytest.mark.parametrize("contract_kind", sorted(GOVERNANCE_RECEIPT_MODELS))
def test_frozen_model_rejects_mutation(contract_kind: str, load_json: Any) -> None:
    model = GOVERNANCE_RECEIPT_MODELS[contract_kind]
    fixture_path = next((FIXTURES_ROOT / contract_kind).glob("valid_*.json"))
    instance = model.model_validate(load_json(fixture_path))
    with pytest.raises(ValidationError):
        instance.issued_at = datetime.now(timezone.utc)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# SanitizationReceipt -- risk_class-cannot-be-lowered guard, guilt + innocence
# ---------------------------------------------------------------------------


def test_sanitization_receipt_accepts_output_risk_equal_to_worst_source(load_json: Any) -> None:
    # valid_minimal.json: 1 source (amber), output amber -- equal, innocent.
    payload = load_json(FIXTURES_ROOT / "sanitization_receipt" / "valid_minimal.json")
    assert (
        SanitizationReceipt.model_validate(payload).output_object.classification.risk_class
        == "amber"
    )


def test_sanitization_receipt_accepts_output_risk_above_worst_source(load_json: Any) -> None:
    # valid_multiple_sources.json: sources green+amber, output red -- an
    # increase above the worst source, innocent (only a decrease is
    # forbidden).
    payload = load_json(FIXTURES_ROOT / "sanitization_receipt" / "valid_multiple_sources.json")
    instance = SanitizationReceipt.model_validate(payload)
    assert instance.output_object.classification.risk_class == "red"


def test_sanitization_receipt_accepts_empty_source_objects(load_json: Any) -> None:
    # valid_with_extension.json: zero source_objects -- the guard is a
    # structural no-op (nothing to compare against), never rejected.
    payload = load_json(FIXTURES_ROOT / "sanitization_receipt" / "valid_with_extension.json")
    instance = SanitizationReceipt.model_validate(payload)
    assert instance.source_objects == ()


def test_sanitization_receipt_rejects_output_risk_below_worst_source(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "sanitization_receipt" / "valid_multiple_sources.json")
    lowered_output = {
        **payload["output_object"],
        "classification": {"risk_class": "green", "sensitivity": "public"},
    }
    with pytest.raises(ValidationError) as caught:
        _revalidated(SanitizationReceipt, payload, output_object=lowered_output)
    assert "risk_class_lowered" in _reason_codes(caught.value)


# ---------------------------------------------------------------------------
# SanitizationReceipt -- sanitization_authorizes_output, guilt + innocence
# ---------------------------------------------------------------------------


def _sanitization_receipt(load_json: Any) -> SanitizationReceipt:
    payload = load_json(FIXTURES_ROOT / "sanitization_receipt" / "valid_minimal.json")
    return SanitizationReceipt.model_validate(payload)


def test_sanitization_authorizes_output_accepts_exact_unexpired_match(load_json: Any) -> None:
    receipt = _sanitization_receipt(load_json)
    ref = ExactObjectRef(
        object_kind=receipt.output_object.object_kind,
        object_id=receipt.output_object.object_id,
        object_hash=receipt.output_object.object_hash,
    )
    at = receipt.permitted_use.expires_at - timedelta(seconds=1)
    assert sanitization_authorizes_output(receipt, output_ref=ref, at=at) is None


def test_sanitization_authorizes_output_rejects_wrong_object_id(load_json: Any) -> None:
    receipt = _sanitization_receipt(load_json)
    ref = ExactObjectRef(
        object_kind=receipt.output_object.object_kind,
        object_id="a-different-output-id",
        object_hash=receipt.output_object.object_hash,
    )
    with pytest.raises(ValueError, match="does not name this output_ref"):
        sanitization_authorizes_output(
            receipt, output_ref=ref, at=receipt.permitted_use.expires_at - timedelta(seconds=1)
        )


def test_sanitization_authorizes_output_rejects_stale_output_hash(load_json: Any) -> None:
    receipt = _sanitization_receipt(load_json)
    ref = ExactObjectRef(
        object_kind=receipt.output_object.object_kind,
        object_id=receipt.output_object.object_id,
        object_hash="9" * 64,
    )
    with pytest.raises(ValueError, match="pin this exact output revision"):
        sanitization_authorizes_output(
            receipt, output_ref=ref, at=receipt.permitted_use.expires_at - timedelta(seconds=1)
        )


def test_sanitization_authorizes_output_rejects_expired_receipt(load_json: Any) -> None:
    receipt = _sanitization_receipt(load_json)
    ref = ExactObjectRef(
        object_kind=receipt.output_object.object_kind,
        object_id=receipt.output_object.object_id,
        object_hash=receipt.output_object.object_hash,
    )
    with pytest.raises(ValueError, match="expired"):
        sanitization_authorizes_output(receipt, output_ref=ref, at=receipt.permitted_use.expires_at)


# ---------------------------------------------------------------------------
# RiskReclassificationReceipt -- successor-distinctness guards, guilt +
# innocence
# ---------------------------------------------------------------------------


def test_risk_reclassification_accepts_strict_risk_decrease(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "risk_reclassification_receipt" / "valid_minimal.json")
    instance = RiskReclassificationReceipt.model_validate(payload)
    assert instance.source_object.risk_class == "red"
    assert instance.output_object.risk_class == "amber"


def test_risk_reclassification_accepts_risk_staying_equal(load_json: Any) -> None:
    # valid_with_extension.json: source amber -> output amber -- this
    # receipt is not forced to represent a strict decrease (see module
    # docstring's judgment-call note).
    payload = load_json(
        FIXTURES_ROOT / "risk_reclassification_receipt" / "valid_with_extension.json"
    )
    instance = RiskReclassificationReceipt.model_validate(payload)
    assert instance.source_object.risk_class == instance.output_object.risk_class == "amber"


def test_risk_reclassification_accepts_sensitivity_staying_equal(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "risk_reclassification_receipt" / "valid_minimal.json")
    instance = RiskReclassificationReceipt.model_validate(payload)
    assert instance.source_object.sensitivity == instance.output_object.sensitivity == "internal"


def test_risk_reclassification_accepts_missing_optional_expiry(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "risk_reclassification_receipt" / "valid_minimal.json")
    instance = RiskReclassificationReceipt.model_validate(payload)
    assert instance.permitted_use.expires_at is None


def test_risk_reclassification_accepts_empty_ref_lists(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "risk_reclassification_receipt" / "valid_with_expiry.json")
    instance = RiskReclassificationReceipt.model_validate(payload)
    assert instance.claim_refs == ()
    assert instance.evidence_refs == ()
    assert instance.verification_receipt_refs == ()


def test_risk_reclassification_rejects_sensitivity_decrease(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "risk_reclassification_receipt" / "valid_minimal.json")
    lowered_output = {**payload["output_object"], "sensitivity": "public"}
    with pytest.raises(ValidationError) as caught:
        _revalidated(RiskReclassificationReceipt, payload, output_object=lowered_output)
    assert "sensitivity_lowered" in _reason_codes(caught.value)


def test_risk_reclassification_rejects_output_hash_equal_to_source(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "risk_reclassification_receipt" / "valid_minimal.json")
    same_hash_output = {
        **payload["output_object"],
        "object_hash": payload["source_object"]["object_hash"],
    }
    with pytest.raises(ValidationError) as caught:
        _revalidated(RiskReclassificationReceipt, payload, output_object=same_hash_output)
    assert "output_same_as_source_hash" in _reason_codes(caught.value)


def test_risk_reclassification_rejects_output_kind_mismatch(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "risk_reclassification_receipt" / "valid_minimal.json")
    other_kind_output = {**payload["output_object"], "object_kind": "com.example.other_kind"}
    with pytest.raises(ValidationError) as caught:
        _revalidated(RiskReclassificationReceipt, payload, output_object=other_kind_output)
    assert "output_object_kind_mismatch" in _reason_codes(caught.value)


def test_risk_reclassification_rejects_output_id_equal_to_source(load_json: Any) -> None:
    # object_id must differ even when object_hash already differs:
    # CONTRACTS.md section 9 gives ContentObject a SEPARATE
    # content_object_family_id field for cross-revision stability, so
    # content_object_id identifies one immutable version (same split as
    # section 6 Claim's claim_id / claim_family_id) -- see
    # test_risk_reclassification_same_object_id_would_quarantine_the_graph_family
    # below for the operational proof.
    payload = load_json(FIXTURES_ROOT / "risk_reclassification_receipt" / "valid_minimal.json")
    same_id_output = {
        **payload["output_object"],
        "object_id": payload["source_object"]["object_id"],
    }
    with pytest.raises(ValidationError) as caught:
        _revalidated(RiskReclassificationReceipt, payload, output_object=same_id_output)
    assert "output_object_id_same_as_source" in _reason_codes(caught.value)


def test_risk_reclassification_rejects_output_same_as_source_on_full_identity(
    load_json: Any,
) -> None:
    # Guilt arm: source and output equal across their WHOLE identity
    # (object_kind AND object_id AND object_hash) -- mirrors
    # ObjectSuccessorEdge.validate_edge's
    # predecessor_ref == successor_ref check. This is the specific,
    # informative reason a fully-identical pair gets, ahead of the more
    # generic output_object_id_same_as_source above.
    payload = load_json(FIXTURES_ROOT / "risk_reclassification_receipt" / "valid_minimal.json")
    identical_output = {
        **payload["output_object"],
        "object_id": payload["source_object"]["object_id"],
        "object_hash": payload["source_object"]["object_hash"],
    }
    with pytest.raises(ValidationError) as caught:
        _revalidated(RiskReclassificationReceipt, payload, output_object=identical_output)
    assert "output_object_same_as_source" in _reason_codes(caught.value)


def test_risk_reclassification_same_object_id_would_quarantine_the_graph_family(
    load_json: Any,
) -> None:
    # Grounds the module docstring's claim in the package's OWN graph
    # resolver rather than asserting it: if a revision reused its
    # predecessor's object_id, the two GraphMembers for that family would
    # collide on select_current_member's (object_kind, object_id) key and
    # the family would quarantine as duplicate_member -- fatal to a
    # contract family whose entire purpose is to accumulate revisions.
    payload = load_json(FIXTURES_ROOT / "risk_reclassification_receipt" / "valid_minimal.json")
    source = GraphMember(
        object_kind=payload["source_object"]["object_kind"],
        object_id=payload["source_object"]["object_id"],
        object_hash=payload["source_object"]["object_hash"],
        tenant="bali-zero",
        family_id="com.example.family-1",
        recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    same_id_output = source.model_copy(
        update={
            "object_hash": payload["output_object"]["object_hash"],
            "recorded_at": datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
        }
    )
    result = select_current_member([], [source, same_id_output])
    assert isinstance(result, Quarantined)
    assert "duplicate_member" in result.reason_codes


# ---------------------------------------------------------------------------
# RiskReclassificationReceipt -- risk_reclassification_authorizes_output,
# guilt + innocence
# ---------------------------------------------------------------------------


def _risk_reclassification_receipt(load_json: Any) -> RiskReclassificationReceipt:
    payload = load_json(FIXTURES_ROOT / "risk_reclassification_receipt" / "valid_with_expiry.json")
    return RiskReclassificationReceipt.model_validate(payload)


def test_risk_reclassification_authorizes_output_accepts_exact_unexpired_match(
    load_json: Any,
) -> None:
    receipt = _risk_reclassification_receipt(load_json)
    assert receipt.permitted_use.expires_at is not None
    assert (
        risk_reclassification_authorizes_output(
            receipt,
            output_kind=receipt.output_object.object_kind,
            output_id=receipt.output_object.object_id,
            output_hash=receipt.output_object.object_hash,
            at=receipt.permitted_use.expires_at - timedelta(seconds=1),
        )
        is None
    )


def test_risk_reclassification_authorizes_output_accepts_no_expiry_set(load_json: Any) -> None:
    # valid_minimal.json omits permitted_use.expires_at entirely -- an
    # absent expiry must never fail this check, at any instant.
    payload = load_json(FIXTURES_ROOT / "risk_reclassification_receipt" / "valid_minimal.json")
    receipt = RiskReclassificationReceipt.model_validate(payload)
    assert receipt.permitted_use.expires_at is None
    far_future = datetime(2099, 1, 1, tzinfo=timezone.utc)
    assert (
        risk_reclassification_authorizes_output(
            receipt,
            output_kind=receipt.output_object.object_kind,
            output_id=receipt.output_object.object_id,
            output_hash=receipt.output_object.object_hash,
            at=far_future,
        )
        is None
    )


def test_risk_reclassification_authorizes_output_rejects_wrong_output_id(load_json: Any) -> None:
    receipt = _risk_reclassification_receipt(load_json)
    assert receipt.permitted_use.expires_at is not None
    with pytest.raises(ValueError, match="does not name this output"):
        risk_reclassification_authorizes_output(
            receipt,
            output_kind=receipt.output_object.object_kind,
            output_id="a-different-output-id",
            output_hash=receipt.output_object.object_hash,
            at=receipt.permitted_use.expires_at - timedelta(seconds=1),
        )


def test_risk_reclassification_authorizes_output_rejects_stale_output_hash(load_json: Any) -> None:
    receipt = _risk_reclassification_receipt(load_json)
    assert receipt.permitted_use.expires_at is not None
    with pytest.raises(ValueError, match="pin this exact output revision"):
        risk_reclassification_authorizes_output(
            receipt,
            output_kind=receipt.output_object.object_kind,
            output_id=receipt.output_object.object_id,
            output_hash="9" * 64,
            at=receipt.permitted_use.expires_at - timedelta(seconds=1),
        )


def test_risk_reclassification_authorizes_output_rejects_expired_receipt(load_json: Any) -> None:
    receipt = _risk_reclassification_receipt(load_json)
    assert receipt.permitted_use.expires_at is not None
    with pytest.raises(ValueError, match="expired"):
        risk_reclassification_authorizes_output(
            receipt,
            output_kind=receipt.output_object.object_kind,
            output_id=receipt.output_object.object_id,
            output_hash=receipt.output_object.object_hash,
            at=receipt.permitted_use.expires_at,
        )
