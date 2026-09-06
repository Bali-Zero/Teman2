"""One-turn native admission through the existing PostgreSQL Lab lifecycle.

Only a protected, separate-UID helper may construct this broker. ``NativeGrant``
validates content, NOT issuer authenticity: the helper loads pre-issued bundles
from its protected grant directory and never accepts approval objects over stdin.
Models receive neither this connection nor permission to install grant files.

The native request and its response cannot share a PostgreSQL transaction. A
started attempt with no terminal receipt requires reconciliation, never replay.
"""

from __future__ import annotations

import json
import os
import pwd
import re
import socket
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import asyncpg

from backend.services.autonomous_lab import consul_store
from backend.services.autonomous_lab.consul_executor import _persist, _ref, seal
from backend.services.autonomous_lab.state_store import (
    AutonomousLabStateStore,
    LabMachineRole,
    LabRunQueueItem,
    LabRuntimePlacement,
)

# isort: split
from research_os.hashing import canonicalize
from research_os.models.action_intent import ActionIntent
from research_os.models.approval_receipt import ApprovalReceipt, authorizes_action_intent
from research_os.models.execution_attempt import (
    ExecutionAttempt,
    validate_execution_attempt_authorization,
)
from research_os.models.operational_receipt import OperationalReceipt, close_execution_attempt
from research_os.models.revocation_receipt import RevocationReceipt
from research_os.models.verification_receipt import VerificationReceipt

EFFECT = "com.balizero.consul.native_text_invocation"
CRITERIA = "dual-consul/v4-native"
AUTHORITY = "consul.native_broker"
PRODUCER = {"name": "com.balizero.consul.native_executor", "version": "1.0.0"}
EXTENSION = "com.balizero.dual-consul-native"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,191}")
_HASH = re.compile(r"[a-f0-9]{64}")


def service_state_store(*, service_user: str = "_nuz_consul") -> AutonomousLabStateStore:
    """Bind the protected helper to its configured, non-human Pro service UID.

    ``service_user`` comes from the root-owned launcher, never request fields or
    environment. No account is provisioned or permission escalated here.
    """
    account = pwd.getpwnam(service_user)
    if (
        account.pw_uid == 0
        or os.geteuid() != account.pw_uid
        or account.pw_name in {"nuzantara", "balizero", "root"}
        or socket.gethostname().lower().removesuffix(".local") != "nuzantara"
    ):
        raise PermissionError("native_service_identity_required")
    store = AutonomousLabStateStore()
    store.placement = LabRuntimePlacement(
        LabMachineRole.PRO_RUNTIME,
        True,
        True,
        True,
        "local Pro runtime",
        "Kernel-verified separate Consul service identity",
    )
    return store


def _digest(value: object) -> str:
    return sha256(canonicalize(value)).hexdigest()


def _stamp(at: datetime) -> str:
    return at.isoformat().replace("+00:00", "Z")


def _binding(value: Mapping[str, Any]) -> dict[str, Any]:
    """Accept exactly the selected NativeBinding wire representation."""
    keys = {"mission_id", "input_hash", "discovery_key", "model", "effort", "thread_id"}
    if not isinstance(value, Mapping):
        raise PermissionError("native_binding_shape")
    discovery = value.get("discovery_key")
    if (
        set(value) != keys
        or not isinstance(discovery, dict)
        or set(discovery) != {"runtime_version", "config_hash", "host", "auth_context_hash"}
    ):
        raise PermissionError("native_binding_shape")
    for key, item in {**value, **discovery}.items():
        if key in {"discovery_key", "thread_id"}:
            continue
        if not isinstance(item, str) or not item or len(item) > 256:
            raise PermissionError("native_binding_shape")
        if key.endswith("hash") and not _HASH.fullmatch(item):
            raise PermissionError("native_binding_hash")
    if not _ID.fullmatch(value["mission_id"]):
        raise PermissionError("native_mission_id")
    if value["thread_id"] is not None and (
        not isinstance(value["thread_id"], str) or not _ID.fullmatch(value["thread_id"])
    ):
        raise PermissionError("native_thread_id")
    return json.loads(json.dumps(dict(value), allow_nan=False))


@dataclass(frozen=True)
class NativeGrant:
    """Immutable *content* of one protected, pre-issued, one-invocation bundle."""

    grant_id: str
    binding: dict[str, Any]
    intent: ActionIntent
    approval: ApprovalReceipt
    review: VerificationReceipt

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> NativeGrant:
        if set(payload) != {"grant_id", "binding", "intent", "approval", "review"}:
            raise PermissionError("native_grant_shape")
        grant = cls(
            payload["grant_id"],
            _binding(payload["binding"]),
            ActionIntent.model_validate(payload["intent"]),
            ApprovalReceipt.model_validate(payload["approval"]),
            VerificationReceipt.model_validate(payload["review"]),
        )
        grant.validate()
        return grant

    @property
    def run_id(self) -> str:
        return self.binding["mission_id"]

    @property
    def packet_hash(self) -> str:
        return _digest(self.binding)

    @property
    def arguments_hash(self) -> str:
        return _digest({"effect": EFFECT, "max_invocations": 1, "binding": self.binding})

    @property
    def pins(self) -> dict[str, str]:
        return {
            "resource": f"native:{self.run_id}",
            "intent_hash": self.intent.object_hash,
            "approval_hash": self.approval.object_hash,
            "review_hash": self.review.object_hash,
            "packet_hash": self.packet_hash,
        }

    def object_id(self, kind: str) -> UUID:
        # One spend per exact approval, regardless of retries, process or generation.
        return uuid5(NAMESPACE_URL, f"dual-consul-native:{self.approval.object_hash}:{kind}")

    def validate(self, at: datetime | None = None) -> None:
        if not isinstance(self.grant_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,80}", self.grant_id
        ):
            raise PermissionError("native_grant_id")
        binding = _binding(self.binding)
        if binding["thread_id"] is not None:
            raise PermissionError("preissued_thread_must_be_unbound")
        intent, approval, review = self.intent, self.approval, self.review
        for model in (intent, approval, review):
            type(model).model_validate_json(model.model_dump_json(exclude_unset=True))
        authorizes_action_intent(approval, intent, at=at or approval.issued_at)
        if (
            intent.action_type != EFFECT
            or approval.authorized_effects != (EFFECT,)
            or intent.expected_outcome_types != (EFFECT,)
            or intent.target.system != "com.balizero.autonomous_lab"
            or intent.target.object_ref is None
            or intent.target.object_ref.model_dump(mode="json")
            != _ref("com.balizero.lab_run", self.run_id, self.packet_hash)
            or intent.input_revision_hash != self.packet_hash
            or intent.arguments_hash != self.arguments_hash
            or intent.arguments_ref != f"native:{self.run_id}"
            or intent.risk_class != "green"
            or intent.sensitivity != "internal"
            or approval.authority.role != AUTHORITY
            or intent.authority_required.role != AUTHORITY
            or approval.authority.scope != self.run_id
            or intent.authority_required.scope != self.run_id
            or not approval.authority.verified_at <= approval.issued_at
            or not 0
            < (approval.expires_at - approval.issued_at).total_seconds()
            <= min(3600, intent.authority_required.expires_after_seconds)
        ):
            raise PermissionError("native_grant_scope_mismatch")
        if (
            {intent.producer.name, review.verifier.name}
            != {"com.balizero.consul.astra", "com.balizero.consul.fable"}
            or review.verifier.independence_class != "cross_family"
            or review.verdict != "pass"
            or review.limits
            or not review.checks
            or any(check.result != "pass" for check in review.checks)
            or review.criteria_version != CRITERIA
            or review.classification != approval.classification
            or [ref.model_dump(mode="json") for ref in review.target_objects]
            != [_ref("action_intent", intent.action_intent_id, intent.object_hash)]
            or review.expires_at is None
            or not (
                intent.created_at
                <= review.temporal_scope.checked_at
                <= review.issued_at
                <= review.recorded_at
                < review.expires_at
            )
            or (at is not None and not review.recorded_at <= at < review.expires_at)
        ):
            raise PermissionError("native_review_missing_or_mismatched")

    def check_binding(self, supplied: Mapping[str, Any]) -> dict[str, Any]:
        binding = _binding(supplied)
        if {**binding, "thread_id": None} != self.binding:
            raise PermissionError("native_binding_changed")
        return binding


class NativeBroker:
    """Trusted helper's DB operations; no model invocation, loop, shell or SQL API."""

    def __init__(
        self,
        conn: asyncpg.Connection,
        *,
        owner_id: str,
        state_store: AutonomousLabStateStore,
        lease_seconds: int,
    ) -> None:
        if not _ID.fullmatch(owner_id):
            raise ValueError("invalid_broker_owner")
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
            raise ValueError("invalid_native_lease_budget")
        # The protected helper injects its shared consumer budget, never stdin.
        self.lease_seconds = lease_seconds
        self.conn, self.owner_id, self.store = conn, owner_id, state_store

    async def _load(self, identifier: UUID, model: type) -> Any:
        value = await self.conn.fetchval(
            "SELECT payload FROM research_os_objects WHERE object_id = $1", str(identifier)
        )
        if value is None:
            return None
        return (
            model.model_validate(value)
            if isinstance(value, Mapping)
            else model.model_validate_json(value)
        )

    async def _persist_grant(self, grant: NativeGrant) -> None:
        for kind, identifier, model in (
            ("action_intent", grant.intent.action_intent_id, grant.intent),
            ("approval_receipt", grant.approval.approval_receipt_id, grant.approval),
            ("verification_receipt", grant.review.verification_receipt_id, grant.review),
        ):
            await _persist(self.conn, kind, identifier, model)

    async def _unrevoked(self, grant: NativeGrant) -> None:
        target = _ref(
            "approval_receipt", grant.approval.approval_receipt_id, grant.approval.object_hash
        )
        revoked = await self.conn.fetchval(
            "SELECT payload FROM research_os_objects WHERE object_kind='revocation_receipt' "
            "AND payload @> $1::text::jsonb LIMIT 1",
            json.dumps({"target_ref": target}),
        )
        if revoked is not None:
            (
                RevocationReceipt.model_validate(revoked)
                if isinstance(revoked, Mapping)
                else RevocationReceipt.model_validate_json(revoked)
            )
            raise PermissionError("native_grant_revoked")

    async def admit(self, grant: NativeGrant, binding: Mapping[str, Any]) -> dict[str, Any]:
        grant.check_binding(binding)
        if binding.get("thread_id") is not None:
            raise PermissionError("native_admit_requires_new_binding")
        async with self.conn.transaction():
            # Serialize pre-admit cancellation even when no Lab row exists yet.
            await self.conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext($1))", f"consul:{grant.run_id}"
            )
            at = await self.conn.fetchval("SELECT clock_timestamp()")
            grant.validate(at)
            grant_deadline = min(grant.approval.expires_at, grant.review.expires_at)
            if (grant_deadline - at).total_seconds() < self.lease_seconds:
                raise PermissionError("native_grant_window_too_short")
            await self._unrevoked(grant)
            if await self._load(grant.object_id("attempt"), ExecutionAttempt):
                raise PermissionError("needs_reconcile")
            await self._persist_grant(grant)
            await self.store.enqueue_run(
                self.conn,
                LabRunQueueItem(
                    run_id=grant.run_id,
                    idempotency_key=f"native:{grant.run_id}",
                    max_attempts=1,
                    objective="Bounded native Consul invocation",
                    receipt={
                        "run_id": grant.run_id,
                        "blocked": False,
                        "summary": "native admission",
                    },
                ),
            )
            parent = await self.conn.fetchrow(
                "SELECT worker_id, status FROM autonomous_lab_runs WHERE run_id=$1 FOR UPDATE",
                grant.run_id,
            )
            previous = await self.conn.fetchrow(
                "SELECT * FROM autonomous_lab_consul_leases WHERE run_id=$1 FOR UPDATE",
                grant.run_id,
            )
            if previous is not None:
                lease = consul_store.Lease(grant.run_id, self.owner_id, previous["generation"])
                async with consul_store.guard(self.conn, lease=lease, **grant.pins):
                    return {"status": "admitted", "lease": asdict(lease), "max_invocations": 1}
            if parent["status"] != "pending" or not await self.store.claim_run(
                self.conn, run_id=grant.run_id, worker_id=self.owner_id
            ):
                raise PermissionError("native_run_not_claimable")
            lease = await consul_store.bind(
                self.conn,
                run_id=grant.run_id,
                owner_id=self.owner_id,
                **grant.pins,
                grant_expires_at=grant_deadline,
                lease_seconds=self.lease_seconds,
            )
            return {"status": "admitted", "lease": asdict(lease), "max_invocations": 1}

    async def _attempt(
        self, grant: NativeGrant, lease: consul_store.Lease, binding: dict[str, Any]
    ) -> ExecutionAttempt:
        attempt = await self._load(grant.object_id("attempt"), ExecutionAttempt)
        if attempt is None:
            raise PermissionError("native_attempt_missing")
        validate_execution_attempt_authorization(attempt, grant.intent, grant.approval)
        extension = (attempt.extensions or {}).get(EXTENSION)
        payload = extension.payload if extension else {}
        if payload != {"lease_generation": lease.generation, "binding": binding}:
            raise PermissionError("native_attempt_binding_changed")
        return attempt

    def _base(self, grant: NativeGrant) -> dict[str, Any]:
        return {
            "contract_version": "research-os/v1.0.0",
            "tenant": "bali-zero",
            "producer": PRODUCER,
            "lineage": {"input_hashes": [grant.intent.object_hash]},
            "retention": {"retention_class": "audit", "legal_hold": False},
        }

    async def check(
        self, grant: NativeGrant, lease: consul_store.Lease, binding: Mapping[str, Any], phase: str
    ) -> dict[str, Any]:
        if phase not in {"start", "resume", "turn", "complete"}:
            raise PermissionError("native_phase_invalid")
        actual = grant.check_binding(binding)
        self._lease(grant, lease)
        if phase == "start" and actual["thread_id"] is not None:
            raise PermissionError("native_start_requires_new_thread")
        async with consul_store.guard(self.conn, lease=lease, **grant.pins) as at:
            grant.validate(at)
            await self._unrevoked(grant)
            if phase == "complete":
                await self._attempt(grant, lease, actual)
                await self.conn.execute(
                    "UPDATE autonomous_lab_consul_leases SET native_completion_generation=$2 WHERE run_id=$1",
                    grant.run_id,
                    lease.generation,
                )
            elif await self._load(grant.object_id("attempt"), ExecutionAttempt):
                raise PermissionError("needs_reconcile")
            elif phase == "resume":
                # A first-canary grant has no reviewed continuation/thread pin.
                raise PermissionError("native_resume_not_checkpointed")
            elif phase == "turn":
                if actual["thread_id"] is None:
                    raise PermissionError("native_turn_requires_thread")
                attempt = seal(
                    ExecutionAttempt,
                    {
                        **self._base(grant),
                        "execution_attempt_id": str(grant.object_id("attempt")),
                        "action_intent_ref": {
                            "action_intent_id": str(grant.intent.action_intent_id),
                            "object_hash": grant.intent.object_hash,
                        },
                        "approval_receipt_ref": {
                            "approval_receipt_id": str(grant.approval.approval_receipt_id),
                            "object_hash": grant.approval.object_hash,
                        },
                        "attempt_number": 1,
                        "state": "started",
                        "executor": PRODUCER,
                        "started_at": _stamp(at),
                        "idempotency_key": f"native:{grant.approval.object_hash}",
                        "extensions": {
                            EXTENSION: {
                                "extension_version": "1.0.0",
                                "payload": {
                                    "lease_generation": lease.generation,
                                    "binding": actual,
                                },
                            }
                        },
                    },
                )
                validate_execution_attempt_authorization(attempt, grant.intent, grant.approval)
                await _persist(
                    self.conn, "execution_attempt", attempt.execution_attempt_id, attempt
                )
                # Locks serialize ownership, not time. Refuse expiry during writes.
                async with consul_store.guard(self.conn, lease=lease, **grant.pins) as final_at:
                    grant.validate(final_at)
            return {"status": "authorized", "phase": phase, "lease": asdict(lease)}

    def _lease(self, grant: NativeGrant, lease: consul_store.Lease) -> None:
        if (
            lease.run_id != grant.run_id
            or lease.owner_id != self.owner_id
            or type(lease.generation) is not int
            or lease.generation < 1
        ):
            raise PermissionError("native_lease_identity")

    async def cancel(
        self, grant: NativeGrant, lease: consul_store.Lease | None = None
    ) -> dict[str, Any]:
        grant.validate()  # Cancellation remains available after approval/review expiry.
        if lease is not None:
            self._lease(grant, lease)
        async with self.conn.transaction():
            await self.conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext($1))", f"consul:{grant.run_id}"
            )
            await self.conn.fetchrow(
                "SELECT run_id FROM autonomous_lab_runs WHERE run_id=$1 FOR UPDATE", grant.run_id
            )
            await self._persist_grant(grant)
            revocation = await self._load(grant.object_id("revocation"), RevocationReceipt)
            if revocation is None:
                at = await self.conn.fetchval("SELECT clock_timestamp()")
                revocation = seal(
                    RevocationReceipt,
                    {
                        **self._base(grant),
                        "revocation_receipt_id": str(grant.object_id("revocation")),
                        "target_ref": _ref(
                            "approval_receipt",
                            grant.approval.approval_receipt_id,
                            grant.approval.object_hash,
                        ),
                        "reason_code": "com.balizero.consul.cancelled",
                        "authority": {
                            "role": AUTHORITY,
                            "scope": grant.run_id,
                            "verified_at": _stamp(at),
                        },
                        "actor_ref": grant.approval.actor_ref.model_dump(mode="json"),
                        "required_propagation_targets": [],
                        "classification": grant.approval.classification.model_dump(mode="json"),
                        "issued_at": _stamp(at),
                        "idempotency_key": f"native-revoke:{grant.approval.object_hash}",
                    },
                )
                await _persist(
                    self.conn, "revocation_receipt", revocation.revocation_receipt_id, revocation
                )
            await consul_store.revoke_approval(
                self.conn, run_id=grant.run_id, approval_hash=grant.approval.object_hash
            )
            cancelled = False
            current = await self.conn.fetchrow(
                "SELECT approval_hash, owner_id, generation FROM autonomous_lab_consul_leases WHERE run_id=$1",
                grant.run_id,
            )
            if current and current["approval_hash"] == grant.approval.object_hash:
                if lease is None and current["owner_id"] == self.owner_id:
                    lease = consul_store.Lease(grant.run_id, self.owner_id, current["generation"])
                if lease is not None:
                    cancelled = await self.store.cancel_fenced_run(
                        self.conn,
                        run_id=grant.run_id,
                        worker_id=lease.owner_id,
                        generation=lease.generation,
                    )
            return {
                "status": "revoked",
                "run_cancelled": cancelled,
                "revocation_hash": revocation.object_hash,
                "remote_cancelled": None,
            }

    async def checkpoint(
        self,
        grant: NativeGrant,
        lease: consul_store.Lease,
        binding: Mapping[str, Any],
        result: Mapping[str, Any],
    ) -> dict[str, Any]:
        actual = grant.check_binding(binding)
        self._lease(grant, lease)
        selected = _result(actual, result)
        replay = await self._replay(grant, lease, actual, selected)
        if replay is not None:
            return replay
        async with consul_store.guard(self.conn, lease=lease, **grant.pins) as at:
            grant.validate(at)
            await self._unrevoked(grant)
            attempt = await self._attempt(grant, lease, actual)
            if (
                await self.conn.fetchval(
                    "SELECT native_completion_generation FROM autonomous_lab_consul_leases WHERE run_id=$1",
                    grant.run_id,
                )
                != lease.generation
            ):
                raise PermissionError("native_completion_not_checked")
            previous = await self._load(grant.object_id("result"), OperationalReceipt)
            if previous is not None:
                if previous.extensions[EXTENSION].payload["result"] != _stored_result(selected):
                    raise PermissionError("native_result_conflict")
                return _receipt_reply(previous)
            succeeded = selected["status"] == "completed" and selected["local_interrupted"] is False
            observed = (
                selected["status"] in {"completed", "incomplete", "failed"}
                and not selected["local_interrupted"]
            )
            result_status = (
                "recorded" if succeeded else selected["status"] if observed else "needs_reconcile"
            )
            receipt = seal(
                OperationalReceipt,
                {
                    **self._base(grant),
                    "operational_receipt_id": str(grant.object_id("result")),
                    "operational_receipt_family_id": "com.balizero.consul.native_result",
                    "receipt_type": "execution.result",
                    "subject_refs": [
                        _ref(
                            "action_intent", grant.intent.action_intent_id, grant.intent.object_hash
                        )
                    ],
                    "execution_attempt_ref": {
                        "execution_attempt_id": str(attempt.execution_attempt_id),
                        "object_hash": attempt.object_hash,
                    },
                    "classification": grant.approval.classification.model_dump(mode="json"),
                    "actor_or_executor": {"producer": PRODUCER},
                    "terminal_outcome": "succeeded"
                    if succeeded
                    else "failed"
                    if observed
                    else "unknown",
                    "outcome_code": "com.balizero.consul.native_observed"
                    if succeeded
                    else f"com.balizero.consul.native_{selected['status']}"
                    if observed
                    else "com.balizero.consul.needs_reconcile",
                    "effects": [
                        {"effect_type": EFFECT, "status": "confirmed" if observed else "unknown"}
                    ],
                    "artifact_refs": [],
                    "evidence_refs": [],
                    "observed_at": _stamp(at),
                    "recorded_at": _stamp(at),
                    "idempotency_key": f"native-result:{grant.approval.object_hash}",
                    "reconciliation": {
                        "state": "confirmed" if observed else "pending",
                        "checked_at": _stamp(at),
                        "evidence_refs": [],
                    },
                    "extensions": {
                        EXTENSION: {
                            "extension_version": "1.0.0",
                            "payload": {"result": _stored_result(selected)},
                        }
                    },
                },
            )
            close_execution_attempt(receipt, attempt)
            await _persist(
                self.conn, "operational_receipt", receipt.operational_receipt_id, receipt
            )
            marked = await self.store.checkpoint_fenced_run(
                self.conn,
                run_id=grant.run_id,
                worker_id=lease.owner_id,
                generation=lease.generation,
                succeeded=succeeded,
                receipt_hash=receipt.object_hash,
            )
            if not marked:
                raise PermissionError("native_checkpoint_lost_owner")
            return {
                "status": result_status,
                "receipt_hash": receipt.object_hash,
            }

    async def _replay(
        self,
        grant: NativeGrant,
        lease: consul_store.Lease,
        binding: dict[str, Any],
        selected: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Read an already committed result without reopening a terminal run."""
        async with self.conn.transaction():
            parent = await self.conn.fetchrow(
                "SELECT status, worker_id FROM autonomous_lab_runs WHERE run_id=$1 FOR UPDATE",
                grant.run_id,
            )
            row = await self.conn.fetchrow(
                "SELECT * FROM autonomous_lab_consul_leases WHERE run_id=$1 FOR UPDATE",
                grant.run_id,
            )
            previous = await self._load(grant.object_id("result"), OperationalReceipt)
            if previous is None:
                return None
            at = await self.conn.fetchval("SELECT clock_timestamp()")
            grant.validate(at)
            await self._unrevoked(grant)
            expected = {**grant.pins, "owner_id": lease.owner_id, "generation": lease.generation}
            if (
                not parent
                or parent["worker_id"] != lease.owner_id
                or parent["status"] not in {"succeeded", "paused"}
                or not row
                or any(row[key] != value for key, value in expected.items())
                or row["revoked_at"] is not None
                or grant.approval.object_hash in row["revoked_approval_hashes"]
                or at >= min(row["lease_expires_at"], row["grant_expires_at"])
            ):
                raise PermissionError("native_replay_fence_changed")
            await self._attempt(grant, lease, binding)
            if previous.extensions[EXTENSION].payload["result"] != _stored_result(selected):
                raise PermissionError("native_result_conflict")
            return _receipt_reply(previous)


def _receipt_reply(receipt: OperationalReceipt) -> dict[str, str]:
    """Every persisted-result path reports the same observed outcome."""
    if receipt.terminal_outcome == "succeeded":
        status = "recorded"
    elif receipt.terminal_outcome == "failed":
        native_status = receipt.extensions[EXTENSION].payload["result"]["native_status"]
        status = native_status if native_status in {"incomplete", "failed"} else "needs_reconcile"
    else:
        status = "needs_reconcile"
    return {"status": status, "receipt_hash": receipt.object_hash}


def _stored_result(selected: dict[str, Any]) -> dict[str, Any]:
    # ROS reserves `status` recursively; keep native status namespaced explicitly.
    return {
        **{key: value for key, value in selected.items() if key != "status"},
        "native_status": selected["status"],
    }


def _result(binding: dict[str, Any], value: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "mission_id": binding["mission_id"],
        "thread_id": binding["thread_id"],
        "input_hash": binding["input_hash"],
        "requested_model": binding["model"],
        "runtime_model": binding["model"],
        "inference_model": None,
        "identity_evidence": "request_observed",
        "model_evidence_source": "native_thread_configuration",
        "effort": binding["effort"],
        **binding["discovery_key"],
        "remote_cancelled": None,
    }
    variable = {"turn_id", "output_hash", "status", "native_usage", "local_interrupted"}
    if set(value) != set(expected) | variable or any(
        value.get(k) != v for k, v in expected.items()
    ):
        raise PermissionError("native_result_binding_or_fields")
    if (
        binding["thread_id"] is None
        or not isinstance(value["turn_id"], str)
        or not _ID.fullmatch(value["turn_id"])
        or not isinstance(value["output_hash"], str)
        or not _HASH.fullmatch(value["output_hash"])
        or value["status"] not in {"completed", "incomplete", "interrupted", "failed"}
        or type(value["local_interrupted"]) is not bool
    ):
        raise PermissionError("native_result_shape")
    usage = value["native_usage"]
    if not isinstance(usage, dict) or set(usage) - {
        "total",
        "last",
        "modelContextWindow",
        "unknownCounters",
    }:
        raise PermissionError("native_usage_shape")
    for key, bucket in usage.items():
        if key == "unknownCounters":
            if (
                not isinstance(bucket, dict)
                or set(bucket) != {"names", "omitted"}
                or type(bucket["omitted"]) is not bool
                or not isinstance(bucket["names"], list)
                or len(bucket["names"]) > 16
                or any(
                    not isinstance(name, str)
                    or not re.fullmatch(r"(?:last|total|root)\.[A-Za-z][A-Za-z0-9_]{0,63}", name)
                    for name in bucket["names"]
                )
                or bucket["names"] != sorted(set(bucket["names"]))
                or (not bucket["names"] and not bucket["omitted"])
            ):
                raise PermissionError("native_usage_shape")
            continue
        if key == "modelContextWindow":
            numbers = [bucket]
        else:
            if not isinstance(bucket, dict) or set(bucket) - {
                "inputTokens",
                "cachedInputTokens",
                "cacheWriteInputTokens",
                "outputTokens",
                "reasoningOutputTokens",
                "totalTokens",
            }:
                raise PermissionError("native_usage_shape")
            numbers = list(bucket.values())
        if any(type(number) is not int or not 0 <= number < 2**63 for number in numbers):
            raise PermissionError("native_usage_shape")
    return json.loads(json.dumps(dict(value), allow_nan=False))
