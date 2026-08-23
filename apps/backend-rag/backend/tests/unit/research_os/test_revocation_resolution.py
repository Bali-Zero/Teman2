from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError
from research_os.cli import FIXTURES_ROOT
from research_os.hashing import object_hash
from research_os.models.revocation_receipt import (
    QuarantinedRevocations,
    ResolvedRevocation,
    RevocationReceipt,
    resolve_revocation_replay,
)


def _validated_receipt(payload: dict[str, Any], **updates: Any) -> RevocationReceipt:
    candidate = deepcopy(payload)
    candidate.update(updates)
    candidate["object_hash"] = object_hash(candidate)
    return RevocationReceipt.model_validate(candidate)


def test_same_target_different_idempotency_keys_resolve_independently(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "revocation_receipt" / "valid_minimal.json")
    first = RevocationReceipt.model_validate(payload)
    second = _validated_receipt(
        payload,
        revocation_receipt_id="20000000-0000-4000-8000-000000000002",
        idempotency_key="synthetic-revocation-002",
        issued_at="2026-02-01T00:02:00Z",
    )

    result = resolve_revocation_replay([first, second])

    assert isinstance(result, ResolvedRevocation)
    assert result.receipts == (first, second)


def test_same_target_identical_idempotency_claims_collapse_to_one_receipt(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "revocation_receipt" / "valid_minimal.json")
    receipt = RevocationReceipt.model_validate(payload)

    result = resolve_revocation_replay([receipt, receipt])

    assert isinstance(result, ResolvedRevocation)
    assert result.receipts == (receipt,)
    assert result.receipt == receipt


def test_different_targets_with_same_idempotency_key_resolve_independently(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "revocation_receipt" / "valid_minimal.json")
    first = RevocationReceipt.model_validate(payload)
    second_target = {
        **payload["target_ref"],
        "object_id": "synthetic-target-002",
        "object_hash": "8" * 64,
    }
    second = _validated_receipt(
        payload,
        revocation_receipt_id="20000000-0000-4000-8000-000000000003",
        target_ref=second_target,
        issued_at="2026-02-01T00:03:00Z",
    )

    result = resolve_revocation_replay([first, second])

    assert isinstance(result, ResolvedRevocation)
    assert result.receipts == (first, second)


def test_same_target_identity_and_key_with_conflicting_target_hash_quarantines(
    load_json: Any,
) -> None:
    payload = load_json(FIXTURES_ROOT / "revocation_receipt" / "valid_minimal.json")
    first = RevocationReceipt.model_validate(payload)
    conflicting_target = {**payload["target_ref"], "object_hash": "8" * 64}
    conflicting = _validated_receipt(
        payload,
        revocation_receipt_id="20000000-0000-4000-8000-000000000004",
        target_ref=conflicting_target,
        issued_at="2026-02-01T00:04:00Z",
    )

    result = resolve_revocation_replay([first, conflicting])

    assert isinstance(result, QuarantinedRevocations)
    assert "conflicting_idempotency_key" in result.reason_codes


def test_conflicting_duplicate_idempotency_key_quarantines(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "revocation_receipt" / "valid_minimal.json")
    first = RevocationReceipt.model_validate(payload)
    conflicting = _validated_receipt(
        payload,
        revocation_receipt_id="20000000-0000-4000-8000-000000000005",
        reason_code="com.example.different_reason",
        issued_at="2026-02-01T00:05:00Z",
    )

    result = resolve_revocation_replay([first, conflicting])

    assert isinstance(result, QuarantinedRevocations)
    assert "conflicting_idempotency_key" in result.reason_codes


def test_conflicting_authority_for_same_target_and_key_quarantines(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "revocation_receipt" / "valid_minimal.json")
    first = RevocationReceipt.model_validate(payload)
    conflicting_authority = {**payload["authority"], "scope": "research.other_scope"}
    conflicting = _validated_receipt(
        payload,
        revocation_receipt_id="20000000-0000-4000-8000-000000000006",
        authority=conflicting_authority,
        issued_at="2026-02-01T00:06:00Z",
    )

    result = resolve_revocation_replay([first, conflicting])

    assert isinstance(result, QuarantinedRevocations)
    assert "conflicting_idempotency_key" in result.reason_codes


def test_same_idempotency_identity_with_distinct_canonical_receipts_quarantines(
    load_json: Any,
) -> None:
    payload = load_json(FIXTURES_ROOT / "revocation_receipt" / "valid_minimal.json")
    first = RevocationReceipt.model_validate(payload)
    distinct_claim = _validated_receipt(
        payload,
        revocation_receipt_id=str(UUID("20000000-0000-4000-8000-000000000099")),
        issued_at="2026-02-01T00:09:00Z",
    )

    result = resolve_revocation_replay([first, distinct_claim])

    assert isinstance(result, QuarantinedRevocations)
    assert "conflicting_idempotency_key" in result.reason_codes


def test_same_idempotency_identity_with_literal_same_receipt_resolves(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "revocation_receipt" / "valid_minimal.json")
    first = RevocationReceipt.model_validate(payload)
    literal_replay = RevocationReceipt.model_validate(deepcopy(payload))

    result = resolve_revocation_replay([first, literal_replay])

    assert isinstance(result, ResolvedRevocation)
    assert result.receipts == (first,)


def test_receipt_invalidates_only_its_exact_target_hash(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "revocation_receipt" / "valid_minimal.json")
    receipt = RevocationReceipt.model_validate(payload)
    assert receipt.invalidates(receipt.target_ref) is True
    assert (
        receipt.invalidates(receipt.target_ref.model_copy(update={"object_hash": "f" * 64}))
        is False
    )


def test_revocation_receipt_is_immutable_and_has_no_unrevoke(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "revocation_receipt" / "valid_minimal.json")
    receipt = RevocationReceipt.model_validate(payload)
    with pytest.raises(ValidationError):
        receipt.idempotency_key = "changed"
