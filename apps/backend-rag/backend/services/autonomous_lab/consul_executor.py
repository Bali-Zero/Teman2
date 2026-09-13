"""Dual Consul's first slice: one fenced, same-database synthetic effect.

The caller is a trusted broker, not a model-facing API. It supplies authenticated
grants and reviewer observations. This does not establish service-UID isolation
or qualify a shell, remote tool, model invocation, or production effect.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any, Literal, TypeVar
from uuid import NAMESPACE_URL, uuid5

import asyncpg

from backend.services.research_os import _core_path as _core_path

# isort: split

from research_os.hashing import canonicalize, object_hash
from research_os.models.action_intent import ActionIntent
from research_os.models.approval_receipt import ApprovalReceipt, authorizes_action_intent
from research_os.models.execution_attempt import (
    ExecutionAttempt,
    validate_execution_attempt_authorization,
)
from research_os.models.operational_receipt import OperationalReceipt, close_execution_attempt
from research_os.models.verification_receipt import VerificationReceipt
from research_os.primitives import FrozenCoreModel

from backend.services.autonomous_lab import consul_store
from backend.services.autonomous_lab.runtime_contracts import (
    LabArtifactKind,
    LabStageName,
    LabStageStatus,
)
from backend.services.autonomous_lab.stages import LabStageRiskClass, StageResult
from backend.services.autonomous_lab.state_store import (
    LabRunRecord,
)

EFFECT = "com.balizero.consul.synthetic_checkpoint"
CRITERIA = "dual-consul/v4-synthetic"
PRODUCER = {"name": "com.balizero.consul.synthetic_executor", "version": "4.0.0"}
Model = TypeVar("Model", bound=FrozenCoreModel)


@dataclass(frozen=True)
class FrozenInputs:
    """Actual bytes received by the executor; only their digests are persisted."""

    run_id: str
    artifact: bytes
    effective_input: bytes
    configuration: bytes
    evidence: bytes
    runtime_binding: bytes
    builder: Literal["astra", "fable"]
    reviewer: Literal["astra", "fable"]

    @property
    def digest(self) -> str:
        packet = {
            "run_id": self.run_id,
            "builder": self.builder,
            "reviewer": self.reviewer,
            **{
                key: sha256(getattr(self, key)).hexdigest()
                for key in (
                    "artifact",
                    "effective_input",
                    "configuration",
                    "evidence",
                    "runtime_binding",
                )
            },
        }
        return sha256(canonicalize(packet)).hexdigest()

    @property
    def arguments_hash(self) -> str:
        return sha256(canonicalize({"run_id": self.run_id, "effect": EFFECT})).hexdigest()


@dataclass(frozen=True)
class ConsulRequest:
    inputs: FrozenInputs
    intent: ActionIntent
    approval: ApprovalReceipt
    review: VerificationReceipt

    @property
    def pins(self) -> dict[str, str]:
        return {
            "resource": f"synthetic:{self.inputs.run_id}",
            "intent_hash": self.intent.object_hash,
            "approval_hash": self.approval.object_hash,
            "review_hash": self.review.object_hash,
            "packet_hash": self.inputs.digest,
        }

    def validate(self, at: datetime) -> None:
        """Check canonical grants plus the effect, resource, and frozen review."""
        intent, approval, review, inputs = self.intent, self.approval, self.review, self.inputs
        # Frozen Pydantic models still permit nested mutation / model_copy(update).
        # Revalidate their wire forms at the trust boundary, including every hash.
        for model in (intent, approval, review):
            type(model).model_validate_json(model.model_dump_json(exclude_unset=True))
        authorizes_action_intent(approval, intent, at=at)
        if (
            inputs.builder not in {"astra", "fable"}
            or {inputs.builder, inputs.reviewer}
            != {
                "astra",
                "fable",
            }
            or intent.producer.name != f"com.balizero.consul.{inputs.builder}"
        ):
            raise PermissionError("independent_consul_required")
        if (
            intent.action_type != EFFECT
            or approval.authorized_effects != (EFFECT,)
            or intent.target.system != "com.balizero.autonomous_lab"
            or intent.target.object_ref is None
            or intent.target.object_ref.object_kind != "com.balizero.lab_run"
            or intent.target.object_ref.object_id != inputs.run_id
            or intent.target.object_ref.object_hash != inputs.digest
            or intent.input_revision_hash != inputs.digest
            or intent.arguments_hash != inputs.arguments_hash
            or intent.risk_class != "green"
            or intent.sensitivity != "internal"
        ):
            raise PermissionError("synthetic_scope_or_input_mismatch")
        if (
            approval.authority.role != "consul.synthetic_broker"
            or intent.authority_required.role != approval.authority.role
            or approval.authority.scope != inputs.run_id
            or intent.authority_required.scope != inputs.run_id
            or not (approval.authority.verified_at <= approval.issued_at <= at)
            or (approval.expires_at - approval.issued_at).total_seconds()
            > intent.authority_required.expires_after_seconds
        ):
            raise PermissionError("authority_scope_mismatch")
        target = _ref("action_intent", intent.action_intent_id, intent.object_hash)
        if (
            review.verdict != "pass"
            or review.limits
            or not review.checks
            or any(check.result != "pass" for check in review.checks)
            or [ref.model_dump(mode="json") for ref in review.target_objects] != [target]
            or review.verifier.name != f"com.balizero.consul.{inputs.reviewer}"
            or review.verifier.independence_class != "cross_family"
            or review.criteria_version != CRITERIA
            or review.classification != approval.classification
            or review.expires_at is None
            or not (review.issued_at <= review.recorded_at <= at < review.expires_at)
            or not (intent.created_at <= review.temporal_scope.checked_at <= review.issued_at)
        ):
            raise PermissionError("review_missing_stale_or_mismatched")


def _ref(kind: str, identifier: object, digest: str) -> dict[str, str]:
    return {"object_kind": kind, "object_id": str(identifier), "object_hash": digest}


def seal(model: type[Model], payload: dict[str, Any]) -> Model:
    """Create a canonical ROS object without bypassing its validators."""
    return model.model_validate({**payload, "object_hash": object_hash(payload)})


async def _persist(
    conn: asyncpg.Connection, kind: str, identifier: object, model: FrozenCoreModel
) -> None:
    payload = model.model_dump(mode="json", exclude_unset=True)
    await conn.execute(
        """INSERT INTO research_os_objects
           (object_kind, object_id, object_hash, contract_version, tenant, payload)
           VALUES ($1, $2, $3, $4, 'bali-zero', $5::text::jsonb)
           ON CONFLICT (object_id) DO NOTHING""",
        kind,
        str(identifier),
        payload["object_hash"],
        payload["contract_version"],
        json.dumps(payload),
    )
    stored = await conn.fetchval(
        "SELECT object_hash FROM research_os_objects WHERE object_id = $1", str(identifier)
    )
    if stored != payload["object_hash"]:
        raise PermissionError("immutable_object_collision")


async def execute_synthetic(
    conn: asyncpg.Connection, *, lease: consul_store.Lease, request: ConsulRequest
) -> OperationalReceipt:
    """Commit attempt, synthetic checkpoint and result atomically under PG locks.

    No external callback is accepted: a local timeout cannot be misrepresented as
    remote cancellation. On a lost commit acknowledgement, replay reads the same
    immutable receipt instead of repeating the effect.
    """
    if lease.run_id != request.inputs.run_id:
        raise PermissionError("mission_mismatch")
    async with consul_store.guard(conn, lease=lease, **request.pins) as at:
        request.validate(at)
        intent, approval, review = request.intent, request.approval, request.review
        identity = f"dual-consul:{intent.action_intent_id}:{intent.object_hash}"
        result_id = uuid5(NAMESPACE_URL, identity + ":result")
        existing = await conn.fetchval(
            "SELECT payload FROM research_os_objects WHERE object_id = $1", str(result_id)
        )
        if existing is not None:
            return (
                OperationalReceipt.model_validate(existing)
                if isinstance(existing, Mapping)
                else OperationalReceipt.model_validate_json(existing)
            )
        for kind, identifier, obj in (
            ("action_intent", intent.action_intent_id, intent),
            ("approval_receipt", approval.approval_receipt_id, approval),
            ("verification_receipt", review.verification_receipt_id, review),
        ):
            await _persist(conn, kind, identifier, obj)
        stamp = at.isoformat().replace("+00:00", "Z")
        base = {
            "contract_version": "research-os/v1.0.0",
            "tenant": "bali-zero",
            "producer": PRODUCER,
            "lineage": {"input_hashes": [intent.object_hash]},
            "retention": {"retention_class": "audit", "legal_hold": False},
        }
        attempt = seal(
            ExecutionAttempt,
            {
                **base,
                "execution_attempt_id": str(uuid5(NAMESPACE_URL, identity + ":attempt")),
                "action_intent_ref": {
                    "action_intent_id": str(intent.action_intent_id),
                    "object_hash": intent.object_hash,
                },
                "approval_receipt_ref": {
                    "approval_receipt_id": str(approval.approval_receipt_id),
                    "object_hash": approval.object_hash,
                },
                "attempt_number": 1,
                "state": "started",
                "idempotency_key": identity,
                "executor": PRODUCER,
                "started_at": stamp,
                "extensions": {
                    "com.balizero.dual-consul": {
                        "extension_version": "1.0.0",
                        "payload": {
                            "lease_generation": lease.generation,
                            "bound_context_digest": request.inputs.digest,
                        },
                    }
                },
            },
        )
        validate_execution_attempt_authorization(attempt, intent=intent, receipt=approval)
        await _persist(conn, "execution_attempt", attempt.execution_attempt_id, attempt)
        # This is the ONLY effect this implementation can perform.
        # Expiry remains live while locks are held. Recheck it in the effect
        # statement itself, even if an earlier receipt insert was delayed.
        effect_at = await conn.fetchval(
            """INSERT INTO autonomous_lab_events_outbox (run_id, event_type, payload)
               SELECT run_id, 'run_checkpointed', $3::text::jsonb
               FROM autonomous_lab_consul_leases
               WHERE run_id = $1 AND generation = $2 AND revoked_at IS NULL
                 AND clock_timestamp() < lease_expires_at
                 AND clock_timestamp() < grant_expires_at
               RETURNING clock_timestamp()""",
            lease.run_id,
            lease.generation,
            json.dumps(
                {
                    "run_id": lease.run_id,
                    "stage": "experiment",
                    "result": "synthetic_confirmed",
                    "checkpoint_fingerprint": request.inputs.digest,
                }
            ),
        )
        if effect_at is None:
            raise PermissionError("lease_expired_before_effect")
        stamp = effect_at.isoformat().replace("+00:00", "Z")
        receipt = seal(
            OperationalReceipt,
            {
                **base,
                "operational_receipt_id": str(result_id),
                "operational_receipt_family_id": "com.balizero.consul.synthetic_result",
                "receipt_type": "execution.result",
                "subject_refs": [
                    _ref("action_intent", intent.action_intent_id, intent.object_hash)
                ],
                "execution_attempt_ref": {
                    "execution_attempt_id": str(attempt.execution_attempt_id),
                    "object_hash": attempt.object_hash,
                },
                "classification": approval.classification.model_dump(mode="json"),
                "actor_or_executor": {"producer": PRODUCER},
                "terminal_outcome": "succeeded",
                "outcome_code": "com.balizero.consul.synthetic_confirmed",
                "effects": [{"effect_type": EFFECT, "status": "confirmed"}],
                "artifact_refs": [],
                "evidence_refs": [
                    _ref("verification_receipt", review.verification_receipt_id, review.object_hash)
                ],
                "observed_at": stamp,
                "recorded_at": stamp,
                "idempotency_key": identity + ":result",
                "reconciliation": {"state": "confirmed", "checked_at": stamp, "evidence_refs": []},
            },
        )
        close_execution_attempt(receipt, attempt)
        await _persist(conn, "operational_receipt", result_id, receipt)
        return receipt


@dataclass
class ConsulSyntheticStage:
    """Opt-in stage for AutonomousLabWorker; no scheduler or default activation."""

    conn: asyncpg.Connection
    request: ConsulRequest
    owner_id: str
    name = LabStageName.EXPERIMENT
    input_data_class = "ConsulRequest"
    output_data_class = "OperationalReceipt"
    risk_class = LabStageRiskClass.LOW

    async def run(self, run: LabRunRecord, context: Mapping[str, Any]) -> StageResult:
        if run.run_id != self.request.inputs.run_id:
            raise PermissionError("mission_mismatch")
        at = await self.conn.fetchval("SELECT clock_timestamp()")
        self.request.validate(at)
        lease = await consul_store.bind(
            self.conn,
            run_id=run.run_id,
            owner_id=self.owner_id,
            **self.request.pins,
            grant_expires_at=min(self.request.approval.expires_at, self.request.review.expires_at),
        )
        result = await execute_synthetic(self.conn, lease=lease, request=self.request)
        return StageResult(
            stage=self.name,
            status=LabStageStatus.SUCCEEDED,
            artifact_kind=LabArtifactKind.SANDBOX_RUN_RESULT,
            summary="synthetic checkpoint confirmed under current ownership",
            payload={
                "run_id": run.run_id,
                "result": "synthetic_confirmed",
                "checkpoint_fingerprint": result.object_hash,
            },
        )
