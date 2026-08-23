"""Packet 04 deliverable 1: the decision/authority/execution chain (CONTRACTS.md
section 13) -- ActionItem, ActionIntent, ApprovalReceipt, ExecutionAttempt,
OperationalReceipt.

Kept as its own file rather than extending ``test_models_and_fixtures.py``:
another lane is concurrently building the section 4/5/6/11 evidence spine in
this same tree, and that shared test file's ``CONTRACT_MODELS`` dict is a
natural place for both lanes to want to touch at once. This file duplicates
that generic fixture-coverage shape (round trip against schema + model,
invalid-reason-code check, reject-unknown-top-level-field, hash-bypass
resistance) scoped to only the five kinds this packet owns, then adds the
chain-specific cross-object invariant tests no generic fixture loop can
express (a JSON fixture is one object; an authorization or closure check
needs two or three).
"""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
from typing import Any

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from pydantic import BaseModel, ValidationError
from research_os.cli import FIXTURES_ROOT
from research_os.hashing import object_hash
from research_os.models.action_intent import ActionIntent, verify_action_intent_matches_action_item
from research_os.models.action_item import ActionIntentRef, ActionItem
from research_os.models.approval_receipt import ApprovalReceipt, authorizes_action_intent
from research_os.models.execution_attempt import (
    ExecutionAttempt,
    validate_execution_attempt_authorization,
)
from research_os.models.operational_receipt import (
    OperationalReceipt,
    QuarantinedOperationalReceipts,
    ResolvedOperationalReceipts,
    close_execution_attempt,
    resolve_operational_receipt_replay,
)
from research_os.schemas import SCHEMA_DIRECTORY

DECISION_CHAIN_MODELS: dict[str, type[BaseModel]] = {
    "action_item": ActionItem,
    "action_intent": ActionIntent,
    "approval_receipt": ApprovalReceipt,
    "execution_attempt": ExecutionAttempt,
    "operational_receipt": OperationalReceipt,
}


def _reason_codes(exc: ValidationError) -> set[str]:
    return {str(error["type"]) for error in exc.errors()}


def _revalidated(model: type[BaseModel], payload: dict[str, Any], **updates: Any) -> Any:
    """Deepcopy a valid fixture, apply field updates, recompute object_hash,
    and validate -- the same helper shape as
    ``test_revocation_resolution.py::_validated_receipt``, generalized
    across models.
    """

    candidate = deepcopy(payload)
    candidate.update(updates)
    candidate.pop("object_hash", None)
    candidate["object_hash"] = object_hash(candidate)
    return model.model_validate(candidate)


# ---------------------------------------------------------------------------
# Generic fixture coverage (scoped CONTRACT_MODELS, see module docstring)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("contract_kind", sorted(DECISION_CHAIN_MODELS))
def test_valid_fixtures_round_trip(contract_kind: str, load_json: Any) -> None:
    model = DECISION_CHAIN_MODELS[contract_kind]
    fixture_paths = sorted((FIXTURES_ROOT / contract_kind).glob("valid_*.json"))
    assert fixture_paths, f"expected at least one valid fixture for {contract_kind}"
    for fixture_path in fixture_paths:
        payload = load_json(fixture_path)
        schema = load_json(SCHEMA_DIRECTORY / f"{contract_kind}.schema.json")
        Draft202012Validator(schema).validate(payload)
        instance = model.model_validate(payload)
        assert instance.model_dump(mode="json", exclude_none=True) == payload


@pytest.mark.parametrize("contract_kind", sorted(DECISION_CHAIN_MODELS))
def test_invalid_fixtures_reject_with_exact_expected_reason(
    contract_kind: str, load_json: Any
) -> None:
    model = DECISION_CHAIN_MODELS[contract_kind]
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
        assert expected in _reason_codes(caught.value), fixture_path.name


@pytest.mark.parametrize("contract_kind", sorted(DECISION_CHAIN_MODELS))
def test_rejects_unknown_top_level_field(contract_kind: str, load_json: Any) -> None:
    model = DECISION_CHAIN_MODELS[contract_kind]
    fixture_path = next((FIXTURES_ROOT / contract_kind).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "unexpected_field": True}
    with pytest.raises(ValidationError) as caught:
        model.model_validate(payload)
    assert "extra_forbidden" in _reason_codes(caught.value)


@pytest.mark.parametrize("contract_kind", sorted(DECISION_CHAIN_MODELS))
def test_context_cannot_bypass_exact_object_hash(contract_kind: str, load_json: Any) -> None:
    model = DECISION_CHAIN_MODELS[contract_kind]
    fixture_path = next((FIXTURES_ROOT / contract_kind).glob("valid_*.json"))
    payload = {**load_json(fixture_path), "object_hash": "0" * 64}
    with pytest.raises(ValidationError) as caught:
        model.model_validate(payload, context={"skip_object_hash_check": True})
    assert "object_hash_mismatch" in _reason_codes(caught.value)


@pytest.mark.parametrize("contract_kind", sorted(DECISION_CHAIN_MODELS))
def test_frozen_model_rejects_mutation(contract_kind: str, load_json: Any) -> None:
    """ "An attempt must be immutable once started" generalizes: every kind
    in this chain is a ``FrozenCoreModel`` and none has a legitimate setter.
    """

    model = DECISION_CHAIN_MODELS[contract_kind]
    fixture_path = next((FIXTURES_ROOT / contract_kind).glob("valid_*.json"))
    instance = model.model_validate(load_json(fixture_path))
    with pytest.raises(ValidationError):
        instance.idempotency_key = "changed"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Chain invariant: ActionItem <-> ActionIntent lossless transfer
# (verify_action_intent_matches_action_item)
# ---------------------------------------------------------------------------


def _item_and_matching_intent(load_json: Any) -> tuple[ActionItem, ActionIntent]:
    # valid_minimal_new.json (not valid_assigned_with_intent.json) is the
    # base here deliberately: it carries no current_intent_ref. Building a
    # real intent to match this item and separately exercising
    # current_intent_ref via model_copy (see the tests below) would
    # otherwise require item.current_intent_ref and intent.action_item_ref
    # to each name the other's TRUE final object_hash simultaneously -- a
    # mutual SHA-256 fixed point, computationally infeasible. A base
    # fixture with no current_intent_ref sidesteps that entirely.
    item = ActionItem.model_validate(
        load_json(FIXTURES_ROOT / "action_item" / "valid_minimal_new.json")
    )
    intent_payload = load_json(FIXTURES_ROOT / "action_intent" / "valid_minimal.json")
    intent = _revalidated(
        ActionIntent,
        intent_payload,
        action_item_ref={
            "action_item_id": str(item.action_item_id),
            "object_hash": item.object_hash,
        },
        risk_class=item.risk_class.value,
        sensitivity=item.sensitivity.value,
        requested_action_spec_ref=item.requested_action_spec_ref.model_dump(mode="json"),
    )
    return item, intent


def test_verify_action_intent_matches_action_item_accepts_a_lossless_transfer(
    load_json: Any,
) -> None:
    item, intent = _item_and_matching_intent(load_json)
    assert verify_action_intent_matches_action_item(item, intent) is None


def test_verify_action_intent_matches_action_item_rejects_wrong_action_item_id(
    load_json: Any,
) -> None:
    item, intent = _item_and_matching_intent(load_json)
    # other_item must differ from _item_and_matching_intent's own base
    # fixture (now valid_minimal_new.json) or this stops testing a
    # mismatch at all -- valid_closed_completed.json is a distinct
    # action_item_id in the same family.
    other_item = _revalidated(
        ActionItem,
        load_json(FIXTURES_ROOT / "action_item" / "valid_closed_completed.json"),
    )
    with pytest.raises(ValueError, match="does not name this action_item"):
        verify_action_intent_matches_action_item(other_item, intent)


def test_verify_action_intent_matches_action_item_rejects_stale_item_hash(load_json: Any) -> None:
    item, intent = _item_and_matching_intent(load_json)
    # Same family/id, different exact revision (a superseded snapshot).
    stale_item = _revalidated(
        ActionItem,
        item.model_dump(mode="json", exclude_none=True),
        recorded_at="2026-03-01T00:00:02Z",
    )
    assert stale_item.action_item_id == item.action_item_id
    assert stale_item.object_hash != item.object_hash
    with pytest.raises(ValueError, match="pin this exact action_item revision"):
        verify_action_intent_matches_action_item(stale_item, intent)


def test_verify_action_intent_matches_action_item_rejects_risk_divergence(load_json: Any) -> None:
    item, intent = _item_and_matching_intent(load_json)
    lower_risk_intent = _revalidated(
        ActionIntent, intent.model_dump(mode="json", exclude_none=True), risk_class="green"
    )
    with pytest.raises(ValueError, match="risk_class diverges"):
        verify_action_intent_matches_action_item(item, lower_risk_intent)


def test_verify_action_intent_matches_action_item_rejects_sensitivity_divergence(
    load_json: Any,
) -> None:
    item, intent = _item_and_matching_intent(load_json)
    lower_sensitivity_intent = _revalidated(
        ActionIntent, intent.model_dump(mode="json", exclude_none=True), sensitivity="public"
    )
    with pytest.raises(ValueError, match="sensitivity diverges"):
        verify_action_intent_matches_action_item(item, lower_sensitivity_intent)


def test_verify_action_intent_matches_action_item_rejects_spec_ref_divergence(
    load_json: Any,
) -> None:
    item, intent = _item_and_matching_intent(load_json)
    other_spec_intent = _revalidated(
        ActionIntent,
        intent.model_dump(mode="json", exclude_none=True),
        requested_action_spec_ref={
            "requested_action_spec_id": "d2000000-0000-4000-8000-000000000099",
            "object_hash": "9" * 64,
        },
    )
    with pytest.raises(ValueError, match="requested_action_spec_ref diverges"):
        verify_action_intent_matches_action_item(item, other_spec_intent)


def test_verify_action_intent_matches_action_item_accepts_a_matching_current_intent_ref(
    load_json: Any,
) -> None:
    item, intent = _item_and_matching_intent(load_json)
    linked_item = item.model_copy(
        update={
            "current_intent_ref": ActionIntentRef(
                action_intent_id=intent.action_intent_id,
                object_hash=intent.object_hash,
            )
        }
    )
    assert verify_action_intent_matches_action_item(linked_item, intent) is None


def test_verify_action_intent_matches_action_item_rejects_current_intent_ref_wrong_id(
    load_json: Any,
) -> None:
    item, intent = _item_and_matching_intent(load_json)
    linked_item = item.model_copy(
        update={
            "current_intent_ref": ActionIntentRef(
                action_intent_id="a2000000-0000-4000-8000-000000000099",
                object_hash=intent.object_hash,
            )
        }
    )
    with pytest.raises(ValueError, match="current_intent_ref does not name this action_intent"):
        verify_action_intent_matches_action_item(linked_item, intent)


def test_verify_action_intent_matches_action_item_rejects_current_intent_ref_wrong_hash(
    load_json: Any,
) -> None:
    item, intent = _item_and_matching_intent(load_json)
    linked_item = item.model_copy(
        update={
            "current_intent_ref": ActionIntentRef(
                action_intent_id=intent.action_intent_id,
                object_hash="9" * 64,
            )
        }
    )
    with pytest.raises(ValueError, match="does not pin this exact action_intent revision"):
        verify_action_intent_matches_action_item(linked_item, intent)


# ---------------------------------------------------------------------------
# Chain invariant: an ActionIntent needs an unexpired ApprovalReceipt
# (authorizes_action_intent)
# ---------------------------------------------------------------------------


def _intent_and_matching_receipt(load_json: Any) -> tuple[ActionIntent, ApprovalReceipt]:
    intent = ActionIntent.model_validate(
        load_json(FIXTURES_ROOT / "action_intent" / "valid_minimal.json")
    )
    receipt_payload = load_json(
        FIXTURES_ROOT / "approval_receipt" / "valid_action_intent_approve.json"
    )
    receipt = _revalidated(
        ApprovalReceipt,
        receipt_payload,
        subject={
            "kind": "action_intent",
            "object_id": str(intent.action_intent_id),
            "object_hash": intent.object_hash,
        },
        bindings={
            "input_revision_hash": intent.input_revision_hash,
            "arguments_hash": intent.arguments_hash,
        },
        context={"action_item_ref": intent.action_item_ref.model_dump(mode="json")},
        classification={
            "risk_class": intent.risk_class.value,
            "sensitivity": intent.sensitivity.value,
        },
    )
    return intent, receipt


def test_authorizes_action_intent_accepts_a_matching_unexpired_approval(load_json: Any) -> None:
    intent, receipt = _intent_and_matching_receipt(load_json)
    at = receipt.issued_at + timedelta(minutes=1)
    assert authorizes_action_intent(receipt, intent, at=at) is None


def test_authorizes_action_intent_rejects_expired_approval(load_json: Any) -> None:
    intent, receipt = _intent_and_matching_receipt(load_json)
    with pytest.raises(ValueError, match="not unexpired"):
        authorizes_action_intent(receipt, intent, at=receipt.expires_at)


def test_authorizes_action_intent_rejects_wrong_decision(load_json: Any) -> None:
    intent, receipt = _intent_and_matching_receipt(load_json)
    rejected = _revalidated(
        ApprovalReceipt,
        receipt.model_dump(mode="json", exclude_none=True),
        decision="reject",
        authorized_effects=[],
    )
    with pytest.raises(ValueError, match="decision is not approve"):
        authorizes_action_intent(rejected, intent, at=receipt.issued_at)


def test_authorizes_action_intent_rejects_arguments_hash_mismatch(load_json: Any) -> None:
    intent, receipt = _intent_and_matching_receipt(load_json)
    diverged = _revalidated(
        ApprovalReceipt,
        receipt.model_dump(mode="json", exclude_none=True),
        bindings={"input_revision_hash": intent.input_revision_hash, "arguments_hash": "9" * 64},
    )
    with pytest.raises(ValueError, match="arguments_hash diverges"):
        authorizes_action_intent(diverged, intent, at=receipt.issued_at)


def test_authorizes_action_intent_rejects_classification_mismatch(load_json: Any) -> None:
    intent, receipt = _intent_and_matching_receipt(load_json)
    diverged = _revalidated(
        ApprovalReceipt,
        receipt.model_dump(mode="json", exclude_none=True),
        classification={"risk_class": "green", "sensitivity": intent.sensitivity.value},
    )
    with pytest.raises(ValueError, match="risk_class diverges"):
        authorizes_action_intent(diverged, intent, at=receipt.issued_at)


def test_authorizes_action_intent_rejects_subject_of_wrong_kind(load_json: Any) -> None:
    intent = ActionIntent.model_validate(
        load_json(FIXTURES_ROOT / "action_intent" / "valid_minimal.json")
    )
    lock_receipt = ApprovalReceipt.model_validate(
        load_json(FIXTURES_ROOT / "approval_receipt" / "valid_topic_lock_approve.json")
    )
    with pytest.raises(ValueError, match="subject.kind is not action_intent"):
        authorizes_action_intent(lock_receipt, intent, at=lock_receipt.issued_at)


# ---------------------------------------------------------------------------
# Chain invariant: an ExecutionAttempt needs an unexpired approval of exactly
# this intent (validate_execution_attempt_authorization)
# ---------------------------------------------------------------------------


def _full_chain_triple(load_json: Any) -> tuple[ActionIntent, ApprovalReceipt, ExecutionAttempt]:
    intent, receipt = _intent_and_matching_receipt(load_json)
    attempt_payload = load_json(FIXTURES_ROOT / "execution_attempt" / "valid_first_attempt.json")
    attempt = _revalidated(
        ExecutionAttempt,
        attempt_payload,
        action_intent_ref={
            "action_intent_id": str(intent.action_intent_id),
            "object_hash": intent.object_hash,
        },
        approval_receipt_ref={
            "approval_receipt_id": str(receipt.approval_receipt_id),
            "object_hash": receipt.object_hash,
        },
        started_at=(receipt.issued_at + timedelta(minutes=2)).isoformat().replace("+00:00", "Z"),
    )
    return intent, receipt, attempt


def test_validate_execution_attempt_authorization_accepts_a_matching_triple(
    load_json: Any,
) -> None:
    intent, receipt, attempt = _full_chain_triple(load_json)
    assert validate_execution_attempt_authorization(attempt, intent, receipt) is None


def test_validate_execution_attempt_authorization_rejects_wrong_intent_ref(load_json: Any) -> None:
    intent, receipt, attempt = _full_chain_triple(load_json)
    other_intent = ActionIntent.model_validate(
        load_json(FIXTURES_ROOT / "action_intent" / "valid_green_public.json")
    )
    with pytest.raises(ValueError, match="does not name this action_intent"):
        validate_execution_attempt_authorization(attempt, other_intent, receipt)


def test_validate_execution_attempt_authorization_rejects_wrong_receipt_ref(load_json: Any) -> None:
    intent, receipt, attempt = _full_chain_triple(load_json)
    other_receipt = ApprovalReceipt.model_validate(
        load_json(FIXTURES_ROOT / "approval_receipt" / "valid_topic_lock_approve.json")
    )
    with pytest.raises(ValueError, match="does not name this approval_receipt"):
        validate_execution_attempt_authorization(attempt, intent, other_receipt)


def test_validate_execution_attempt_authorization_rejects_attempt_started_after_expiry(
    load_json: Any,
) -> None:
    intent, receipt, attempt = _full_chain_triple(load_json)
    late_attempt = _revalidated(
        ExecutionAttempt,
        attempt.model_dump(mode="json", exclude_none=True),
        started_at=receipt.expires_at.isoformat().replace("+00:00", "Z"),
    )
    with pytest.raises(ValueError, match="not unexpired"):
        validate_execution_attempt_authorization(late_attempt, intent, receipt)


# ---------------------------------------------------------------------------
# Chain invariant: a typed terminal OperationalReceipt closes the
# ExecutionAttempt (close_execution_attempt)
# ---------------------------------------------------------------------------


def _attempt_and_matching_result_receipt(
    load_json: Any,
) -> tuple[ExecutionAttempt, OperationalReceipt]:
    _, _, attempt = _full_chain_triple(load_json)
    receipt_payload = load_json(
        FIXTURES_ROOT / "operational_receipt" / "valid_execution_result.json"
    )
    result_receipt = _revalidated(
        OperationalReceipt,
        receipt_payload,
        execution_attempt_ref={
            "execution_attempt_id": str(attempt.execution_attempt_id),
            "object_hash": attempt.object_hash,
        },
        observed_at=(attempt.started_at + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        recorded_at=(attempt.started_at + timedelta(minutes=5, seconds=1))
        .isoformat()
        .replace("+00:00", "Z"),
    )
    return attempt, result_receipt


def test_close_execution_attempt_accepts_a_matching_terminal_result(load_json: Any) -> None:
    attempt, result_receipt = _attempt_and_matching_result_receipt(load_json)
    assert close_execution_attempt(result_receipt, attempt) is None


def test_close_execution_attempt_rejects_non_result_receipt_type(load_json: Any) -> None:
    attempt, result_receipt = _attempt_and_matching_result_receipt(load_json)
    queue_receipt = OperationalReceipt.model_validate(
        load_json(FIXTURES_ROOT / "operational_receipt" / "valid_queue_triage.json")
    )
    with pytest.raises(ValueError, match="receipt_type is not execution.result"):
        close_execution_attempt(queue_receipt, attempt)


def test_close_execution_attempt_rejects_wrong_attempt_ref(load_json: Any) -> None:
    attempt, result_receipt = _attempt_and_matching_result_receipt(load_json)
    other_attempt = ExecutionAttempt.model_validate(
        load_json(FIXTURES_ROOT / "execution_attempt" / "valid_retry_with_actor.json")
    )
    with pytest.raises(ValueError, match="does not name this execution_attempt"):
        close_execution_attempt(result_receipt, other_attempt)


def test_close_execution_attempt_rejects_observed_before_started(load_json: Any) -> None:
    attempt, result_receipt = _attempt_and_matching_result_receipt(load_json)
    early_receipt = _revalidated(
        OperationalReceipt,
        result_receipt.model_dump(mode="json", exclude_none=True),
        observed_at=(attempt.started_at - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
    )
    with pytest.raises(ValueError, match="observed_at precedes"):
        close_execution_attempt(early_receipt, attempt)


# ---------------------------------------------------------------------------
# OperationalReceipt idempotent replay (resolve_operational_receipt_replay)
# ---------------------------------------------------------------------------


def test_resolve_operational_receipt_replay_collapses_identical_duplicate(load_json: Any) -> None:
    receipt = OperationalReceipt.model_validate(
        load_json(FIXTURES_ROOT / "operational_receipt" / "valid_execution_result.json")
    )
    literal_replay = OperationalReceipt.model_validate(
        deepcopy(receipt.model_dump(mode="json", exclude_none=True))
    )

    result = resolve_operational_receipt_replay([receipt, literal_replay])

    assert isinstance(result, ResolvedOperationalReceipts)
    assert result.receipts == (receipt,)


def test_resolve_operational_receipt_replay_keeps_distinct_attempts_independent(
    load_json: Any,
) -> None:
    first = OperationalReceipt.model_validate(
        load_json(FIXTURES_ROOT / "operational_receipt" / "valid_execution_result.json")
    )
    second = _revalidated(
        OperationalReceipt,
        first.model_dump(mode="json", exclude_none=True),
        operational_receipt_id="a5000000-0000-4000-8000-000000000021",
        execution_attempt_ref={
            "execution_attempt_id": "a4000000-0000-4000-8000-000000000002",
            "object_hash": "b" * 64,
        },
        idempotency_key="synthetic-operational-receipt-021",
    )

    result = resolve_operational_receipt_replay([first, second])

    assert isinstance(result, ResolvedOperationalReceipts)
    assert result.receipts == (first, second)


def test_resolve_operational_receipt_replay_quarantines_conflicting_duplicate_idempotency(
    load_json: Any,
) -> None:
    first = OperationalReceipt.model_validate(
        load_json(FIXTURES_ROOT / "operational_receipt" / "valid_execution_result.json")
    )
    conflicting = _revalidated(
        OperationalReceipt,
        first.model_dump(mode="json", exclude_none=True),
        operational_receipt_id="a5000000-0000-4000-8000-000000000022",
        outcome_code="com.example.outcome.different",
    )

    result = resolve_operational_receipt_replay([first, conflicting])

    assert isinstance(result, QuarantinedOperationalReceipts)
    assert "conflicting_idempotency_key" in result.reason_codes


def test_resolve_operational_receipt_replay_of_empty_sequence_quarantines() -> None:
    result = resolve_operational_receipt_replay([])
    assert isinstance(result, QuarantinedOperationalReceipts)
    assert result.reason_codes == ("missing_receipt",)
