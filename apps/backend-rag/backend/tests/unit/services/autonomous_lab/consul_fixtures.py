"""Synthetic canonical ROS inputs shared by the focused Consul tests."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Literal, TypeVar
from uuid import NAMESPACE_URL, uuid5

from backend.services.autonomous_lab.consul_executor import (
    CRITERIA,
    EFFECT,
    ConsulRequest,
    FrozenInputs,
    seal,
)

# isort: split
from research_os.cli import FIXTURES_ROOT
from research_os.models.action_intent import ActionIntent
from research_os.models.approval_receipt import ApprovalReceipt
from research_os.models.verification_receipt import VerificationReceipt
from research_os.primitives import FrozenCoreModel

Model = TypeVar("Model", bound=FrozenCoreModel)


def reseal(model: Model, **changes: Any) -> Model:
    payload = model.model_dump(mode="json", exclude_unset=True)
    payload.pop("object_hash")
    return seal(type(model), {**payload, **changes})


def _base(kind: str, filename: str = "valid_minimal.json") -> dict[str, Any]:
    payload = json.loads((FIXTURES_ROOT / kind / filename).read_text())
    payload.pop("object_hash")
    payload["retention"] = {"retention_class": "audit", "legal_hold": False}
    return payload


def make_request(
    now: datetime,
    run_id: str = "dual-consul-synthetic",
    *,
    builder: Literal["astra", "fable"] = "astra",
    reviewer: Literal["astra", "fable"] | None = None,
    grant_revision: int = 1,
) -> ConsulRequest:
    reviewer = reviewer or ("fable" if builder == "astra" else "astra")
    inputs = FrozenInputs(
        run_id=run_id,
        artifact=b"synthetic artifact",
        effective_input=b"synthetic objective",
        configuration=b"synthetic config v4",
        evidence=b"synthetic evidence",
        runtime_binding=b"synthetic runtime v1",
        builder=builder,
        reviewer=reviewer,
    )

    def identifier(kind: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"{run_id}:{kind}:{grant_revision}"))

    intent_payload = _base("action_intent")
    intent_payload.update(
        {
            "action_intent_id": identifier("intent"),
            "action_type": EFFECT,
            "target": {
                "system": "com.balizero.autonomous_lab",
                "object_ref": {
                    "object_kind": "com.balizero.lab_run",
                    "object_id": run_id,
                    "object_hash": inputs.digest,
                },
            },
            "arguments_ref": f"synthetic:{run_id}",
            "arguments_hash": inputs.arguments_hash,
            "input_revision_hash": inputs.digest,
            "risk_class": "green",
            "sensitivity": "internal",
            "authority_required": {
                "role": "consul.synthetic_broker",
                "scope": run_id,
                "expires_after_seconds": 3600,
            },
            "idempotency_key": identifier("intent"),
            "expected_outcome_types": [EFFECT],
            "created_at": (now - timedelta(seconds=20)).isoformat().replace("+00:00", "Z"),
            "producer": {"name": f"com.balizero.consul.{builder}", "version": "4.0.0"},
        }
    )
    intent = seal(ActionIntent, intent_payload)
    approval_payload = _base("approval_receipt", "valid_action_intent_approve.json")
    approval_payload.update(
        {
            "approval_receipt_id": identifier("approval"),
            "subject": {
                "kind": "action_intent",
                "object_id": str(intent.action_intent_id),
                "object_hash": intent.object_hash,
            },
            "context": {"action_item_ref": intent.action_item_ref.model_dump(mode="json")},
            "authority": {
                "role": "consul.synthetic_broker",
                "scope": run_id,
                "verified_at": (now - timedelta(seconds=12)).isoformat().replace("+00:00", "Z"),
            },
            "bindings": {
                "input_revision_hash": inputs.digest,
                "arguments_hash": inputs.arguments_hash,
            },
            "authorized_effects": [EFFECT],
            "classification": {"risk_class": "green", "sensitivity": "internal"},
            "issued_at": (now - timedelta(seconds=10)).isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            "idempotency_key": identifier("approval"),
        }
    )
    approval = seal(ApprovalReceipt, approval_payload)
    review_payload = _base("verification_receipt")
    review_payload.update(
        {
            "verification_receipt_id": identifier("review"),
            "target_objects": [
                {
                    "object_kind": "action_intent",
                    "object_id": str(intent.action_intent_id),
                    "object_hash": intent.object_hash,
                }
            ],
            "verifier": {
                "name": f"com.balizero.consul.{reviewer}",
                "version": "4.0.0",
                "independence_class": "cross_family",
            },
            "criteria_version": CRITERIA,
            "temporal_scope": {
                "checked_at": (now - timedelta(seconds=8)).isoformat().replace("+00:00", "Z")
            },
            "issued_at": (now - timedelta(seconds=7)).isoformat().replace("+00:00", "Z"),
            "recorded_at": (now - timedelta(seconds=6)).isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(minutes=4)).isoformat().replace("+00:00", "Z"),
        }
    )
    return ConsulRequest(inputs, intent, approval, seal(VerificationReceipt, review_payload))


def with_intent(request: ConsulRequest, **changes: Any) -> ConsulRequest:
    """Repin approvals/review so a test reaches semantic, rather than hash, checks."""
    intent = reseal(request.intent, **changes)
    subject = {
        "kind": "action_intent",
        "object_id": str(intent.action_intent_id),
        "object_hash": intent.object_hash,
    }
    approval = reseal(
        request.approval,
        subject=subject,
        bindings={
            "input_revision_hash": intent.input_revision_hash,
            "arguments_hash": intent.arguments_hash,
        },
    )
    review = reseal(
        request.review,
        target_objects=[
            {
                "object_kind": "action_intent",
                "object_id": str(intent.action_intent_id),
                "object_hash": intent.object_hash,
            }
        ],
    )
    return replace(request, intent=intent, approval=approval, review=review)
