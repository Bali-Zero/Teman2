from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError
from research_os.cli import FIXTURES_ROOT
from research_os.models.revocation_receipt import (
    QuarantinedRevocations,
    ResolvedRevocation,
    RevocationReceipt,
    resolve_revocation_replay,
)


def test_duplicate_idempotency_key_for_same_receipt_resolves_idempotently(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "revocation_receipt" / "valid_minimal.json")
    receipt = RevocationReceipt.model_validate(payload)
    result = resolve_revocation_replay([receipt, receipt])
    assert isinstance(result, ResolvedRevocation)
    assert result.receipt == receipt


def test_conflicting_duplicate_idempotency_key_quarantines(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "revocation_receipt" / "valid_minimal.json")
    first = RevocationReceipt.model_validate(payload)
    conflicting = first.model_copy(
        update={
            "reason_code": "com.example.different_reason",
            "object_hash": "f" * 64,
        }
    )
    result = resolve_revocation_replay([first, conflicting])
    assert isinstance(result, QuarantinedRevocations)
    assert "conflicting_idempotency_key" in result.reason_codes


def test_duplicate_key_with_same_named_gate_fields_resolves_existing_receipt(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "revocation_receipt" / "valid_minimal.json")
    first = RevocationReceipt.model_validate(payload)
    replay = first.model_copy(
        update={
            "revocation_receipt_id": UUID("20000000-0000-4000-8000-000000000099"),
            "object_hash": "f" * 64,
        }
    )
    result = resolve_revocation_replay([first, replay])
    assert isinstance(result, ResolvedRevocation)
    assert result.receipt == first


def test_receipt_invalidates_only_its_exact_target_hash(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "revocation_receipt" / "valid_minimal.json")
    receipt = RevocationReceipt.model_validate(payload)
    assert receipt.invalidates(receipt.target_ref) is True
    assert receipt.invalidates(receipt.target_ref.model_copy(update={"object_hash": "f" * 64})) is False


def test_revocation_receipt_is_immutable_and_has_no_unrevoke(load_json: Any) -> None:
    payload = load_json(FIXTURES_ROOT / "revocation_receipt" / "valid_minimal.json")
    receipt = RevocationReceipt.model_validate(payload)
    with pytest.raises(ValidationError):
        receipt.idempotency_key = "changed"  # type: ignore[misc]
