"""PostgreSQL state machine for Autonomous Lab runs and events.

The Lab starts from receipt-only planning, but the v1 control plane needs two
durable primitives before any daemon can run safely:

* ``autonomous_lab_runs``: idempotent run queue with SKIP LOCKED claiming.
* ``autonomous_lab_events_outbox``: at-least-once events, acked after success.

This module is intentionally storage-only. It does not execute shell commands,
spawn agents, deploy, or touch production data.
"""

from __future__ import annotations

import getpass
import json
import re
import socket
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any, Protocol

from backend.services.autonomous_lab.receipt_safety import (
    contains_receipt_sensitive_value,
    receipt_safe_evidence,
)
from backend.services.autonomous_lab.receipt_store import assert_receipt_persistable
from backend.services.autonomous_lab.reviewer import invalid_autonomous_lab_target_path_reason

DEFAULT_RUN_MAX_ATTEMPTS = 3
DEFAULT_RUN_RETRY_DELAY = timedelta(minutes=5)
DEFAULT_EVENT_MAX_ATTEMPTS = 5
DEFAULT_EVENT_RETRY_DELAY = timedelta(minutes=5)
MAX_OBJECTIVE_CHARS = 4000
MAX_METADATA_ITEMS = 50
MAX_PAYLOAD_ITEMS = 100
MAX_PAYLOAD_LIST_ITEMS = 100

_SAFE_PAYLOAD_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,63}$")
_SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SAFE_DECISION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,191}$")
_LOW_RISK_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/@+-]{0,127}$")
_CURATOR_DECISIONS = frozenset({"approve", "reject", "request_changes", "cancel"})
_RAW_PAYLOAD_KEYS = frozenset(
    {
        "body",
        "content",
        "full_text",
        "html",
        "html_content",
        "message",
        "note",
        "notes",
        "prompt",
        "raw",
        "raw_text",
        "source",
        "text",
        "transcript",
    }
)
_PRESERVE_TOKEN_KEYS = frozenset(
    {
        "agent_id",
        "adapter_key",
        "component",
        "command_id",
        "consumer_id",
        "decision",
        "error_reference",
        "event_type",
        "idempotency_key",
        "kind",
        "lane",
        "machine_role",
        "phase",
        "plan_version",
        "priority_class",
        "result",
        "run_id",
        "signal_id",
        "spec_id",
        "stage",
        "source_ref",
        "state",
        "status",
        "task_id",
        "timeline_stage",
        "verdict",
        "worker_id",
        "checkpoint_fingerprint",
        "data_class",
        "risk_class",
    }
)


class AsyncConnection(Protocol):
    """Small asyncpg-compatible subset used by the Lab state store."""

    async def fetchrow(self, query: str, *args: Any) -> Any: ...

    async def fetch(self, query: str, *args: Any) -> Sequence[Any]: ...

    async def execute(self, query: str, *args: Any) -> str: ...


class LabMachineRole(str, Enum):
    """Machine placement roles for the local Bali Zero fleet."""

    AIR_COCKPIT = "air_m5_cockpit"
    PRO_RUNTIME = "pro_runtime"
    MINI_SCHEDULER = "mini_scheduler"
    UNKNOWN = "unknown"


class LabRunStatus(str, Enum):
    """Durable states for a Lab run."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LabOutboxStatus(str, Enum):
    """Durable states for a Lab outbox event."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    CONSUMED = "consumed"
    FAILED_DLQ = "failed_dlq"


class LabEventType(str, Enum):
    """Event vocabulary for v1 Lab orchestration."""

    RUN_ENQUEUED = "run_enqueued"
    RUN_CLAIMED = "run_claimed"
    RUN_CHECKPOINTED = "run_checkpointed"
    RUN_PAUSED = "run_paused"
    RUN_SUCCEEDED = "run_succeeded"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"
    MATERIAL_INGESTED = "material_ingested"
    RUN_DRAFTED = "run_drafted"
    EXPERIMENT_READY = "experiment_ready"
    VERIFICATION_FAILED = "verification_failed"
    CANDIDATE_READY = "candidate_ready"
    EVALUATION_RECORDED = "evaluation_recorded"
    CURATOR_DECISION_RECORDED = "curator_decision_recorded"
    SHADOW_RUN_COMPLETED = "shadow_run_completed"


@dataclass(frozen=True)
class LabRuntimePlacement:
    """Resolved runtime placement for the current host."""

    machine_role: LabMachineRole
    can_enqueue: bool
    can_claim_runs: bool
    can_consume_outbox: bool
    heavy_work_destination: str
    reason: str

    def to_receipt(self) -> dict[str, Any]:
        """Return a receipt-safe placement summary."""
        return {
            "machine_role": self.machine_role.value,
            "can_enqueue": self.can_enqueue,
            "can_claim_runs": self.can_claim_runs,
            "can_consume_outbox": self.can_consume_outbox,
            "heavy_work_destination": self.heavy_work_destination,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class LabRunQueueItem:
    """Input for creating a run queue item."""

    run_id: str
    idempotency_key: str
    objective: str
    receipt: Mapping[str, Any]
    target_paths: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    priority: int = 0
    max_attempts: int = DEFAULT_RUN_MAX_ATTEMPTS


@dataclass(frozen=True)
class LabRunRecord:
    """Persisted Lab run row."""

    run_id: str
    idempotency_key: str
    status: LabRunStatus
    objective: str
    receipt: Mapping[str, Any]
    target_paths: tuple[str, ...]
    metadata: Mapping[str, Any]
    priority: int
    attempts: int
    max_attempts: int
    inserted: bool = False

    def to_receipt(self) -> dict[str, Any]:
        """Return a read-only, receipt-safe run view for operator APIs."""
        assert_receipt_persistable({"run_id": self.run_id, "receipt": self.receipt, "blocked": False})
        return {
            "run_id": self.run_id,
            "idempotency_key": self.idempotency_key,
            "status": self.status.value,
            "objective_reference": receipt_safe_evidence(self.objective, force_fingerprint=True),
            "receipt": dict(self.receipt),
            "target_paths": list(self.target_paths),
            "metadata": _safe_operational_payload(
                self.metadata,
                max_items=MAX_METADATA_ITEMS,
                path="$metadata",
            ),
            "priority": self.priority,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "inserted": self.inserted,
        }


@dataclass(frozen=True)
class LabOutboxEvent:
    """Persisted Lab outbox event row."""

    event_id: int
    run_id: str
    event_type: LabEventType
    payload: Mapping[str, Any]
    status: LabOutboxStatus
    attempts: int

    def to_receipt(self) -> dict[str, Any]:
        """Return a receipt-safe outbox event view."""
        assert_receipt_persistable(
            {
                "run_id": self.run_id,
                "event_type": self.event_type.value,
                "payload": dict(self.payload),
                "blocked": False,
            }
        )
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "event_type": self.event_type.value,
            "payload": dict(self.payload),
            "status": self.status.value,
            "attempts": self.attempts,
        }


@dataclass(frozen=True)
class LabControlMutationResult:
    """Receipt-safe result for an operator control-plane mutation."""

    run_id: str
    changed: bool
    idempotent_replay: bool
    status: LabRunStatus | None
    event_id: int | None

    def to_receipt(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "changed": self.changed,
            "idempotent_replay": self.idempotent_replay,
            "status": self.status.value if self.status is not None else None,
            "event_id": self.event_id,
        }


ENQUEUE_RUN_SQL = """
WITH inserted AS (
    INSERT INTO autonomous_lab_runs (
        run_id,
        idempotency_key,
        objective,
        receipt,
        target_paths,
        metadata,
        priority,
        max_attempts
    )
    VALUES ($1, $2, $3, $4::jsonb, $5::text[], $6::jsonb, $7, $8)
    ON CONFLICT (idempotency_key) DO NOTHING
    RETURNING
        run_id,
        idempotency_key,
        status,
        objective,
        receipt,
        target_paths,
        metadata,
        priority,
        attempts,
        max_attempts,
        TRUE AS inserted
),
selected AS (
    SELECT * FROM inserted
    UNION ALL
    SELECT
        run_id,
        idempotency_key,
        status,
        objective,
        receipt,
        target_paths,
        metadata,
        priority,
        attempts,
        max_attempts,
        FALSE AS inserted
    FROM autonomous_lab_runs
    WHERE idempotency_key = $2
      AND NOT EXISTS (SELECT 1 FROM inserted)
    LIMIT 1
),
event_insert AS (
    INSERT INTO autonomous_lab_events_outbox (run_id, event_type, payload)
    SELECT
        run_id,
        'run_enqueued',
        jsonb_build_object(
            'run_id', run_id,
            'idempotency_key', idempotency_key,
            'target_path_count', cardinality(target_paths)
        )
    FROM selected
    WHERE inserted
    RETURNING event_id
)
SELECT selected.*, (SELECT event_id FROM event_insert) AS event_id
FROM selected
"""

CLAIM_NEXT_RUN_SQL = """
WITH candidate AS (
    SELECT run_id
    FROM autonomous_lab_runs
    WHERE status = 'pending'
      AND next_attempt_at <= NOW()
      AND attempts < max_attempts
    ORDER BY priority DESC, created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
),
claimed AS (
    UPDATE autonomous_lab_runs AS run
    SET
        status = 'running',
        worker_id = $1,
        machine_role = $2,
        attempts = attempts + 1,
        claimed_at = NOW(),
        heartbeat_at = NOW(),
        updated_at = NOW()
    FROM candidate
    WHERE run.run_id = candidate.run_id
    RETURNING
        run.run_id,
        run.idempotency_key,
        run.status,
        run.objective,
        run.receipt,
        run.target_paths,
        run.metadata,
        run.priority,
        run.attempts,
        run.max_attempts,
        TRUE AS inserted
),
event_insert AS (
    INSERT INTO autonomous_lab_events_outbox (run_id, event_type, payload)
    SELECT
        run_id,
        'run_claimed',
        jsonb_build_object(
            'run_id', run_id,
            'worker_id', $1,
            'machine_role', $2
        )
    FROM claimed
    RETURNING event_id
)
SELECT claimed.*, (SELECT event_id FROM event_insert) AS event_id
FROM claimed
"""

MARK_RUN_SUCCEEDED_SQL = """
WITH updated AS (
    UPDATE autonomous_lab_runs
    SET
        status = 'succeeded',
        completed_at = NOW(),
        updated_at = NOW(),
        last_error = NULL
    WHERE run_id = $1
      AND worker_id = $2
      AND status = 'running'
    RETURNING run_id
),
event_insert AS (
    INSERT INTO autonomous_lab_events_outbox (run_id, event_type, payload)
    SELECT run_id, 'run_succeeded', $3::jsonb
    FROM updated
    RETURNING event_id
)
SELECT
    (SELECT COUNT(*) FROM updated) AS updated_count,
    (SELECT event_id FROM event_insert) AS event_id
"""

MARK_RUN_PAUSED_SQL = """
WITH updated AS (
    UPDATE autonomous_lab_runs
    SET
        status = 'paused',
        metadata = metadata || $3::jsonb,
        worker_id = NULL,
        updated_at = NOW(),
        last_error = NULL
    WHERE run_id = $1
      AND worker_id = $2
      AND status = 'running'
    RETURNING run_id
),
event_insert AS (
    INSERT INTO autonomous_lab_events_outbox (run_id, event_type, payload)
    SELECT run_id, 'run_paused', $4::jsonb
    FROM updated
    RETURNING event_id
)
SELECT
    (SELECT COUNT(*) FROM updated) AS updated_count,
    (SELECT event_id FROM event_insert) AS event_id
"""

MARK_RUN_FAILED_SQL = """
WITH updated AS (
    UPDATE autonomous_lab_runs
    SET
        status = CASE WHEN attempts >= max_attempts THEN 'failed' ELSE 'pending' END,
        last_error = $3,
        next_attempt_at = CASE
            WHEN attempts >= max_attempts THEN next_attempt_at
            ELSE NOW() + $4::interval
        END,
        worker_id = NULL,
        updated_at = NOW()
    WHERE run_id = $1
      AND worker_id = $2
      AND status = 'running'
    RETURNING run_id
),
event_insert AS (
    INSERT INTO autonomous_lab_events_outbox (run_id, event_type, payload)
    SELECT run_id, 'run_failed', $5::jsonb
    FROM updated
    RETURNING event_id
)
SELECT
    (SELECT COUNT(*) FROM updated) AS updated_count,
    (SELECT event_id FROM event_insert) AS event_id
"""

CLAIM_OUTBOX_EVENTS_SQL = """
WITH candidate AS (
    SELECT event_id
    FROM autonomous_lab_events_outbox
    WHERE status = 'pending'
      AND next_attempt_at <= NOW()
      AND attempts < max_attempts
    ORDER BY created_at ASC
    LIMIT $1
    FOR UPDATE SKIP LOCKED
)
UPDATE autonomous_lab_events_outbox AS event
SET
    status = 'in_progress',
    attempts = attempts + 1,
    claimed_by = $2,
    claimed_at = NOW(),
    updated_at = NOW()
FROM candidate
WHERE event.event_id = candidate.event_id
RETURNING
    event.event_id,
    event.run_id,
    event.event_type,
    event.payload,
    event.status,
    event.attempts
"""

GET_RUN_SQL = """
SELECT
    run_id,
    idempotency_key,
    status,
    objective,
    receipt,
    target_paths,
    metadata,
    priority,
    attempts,
    max_attempts,
    FALSE AS inserted
FROM autonomous_lab_runs
WHERE run_id = $1
"""

LIST_RUN_EVENTS_SQL = """
SELECT
    event_id,
    run_id,
    event_type,
    payload,
    status,
    attempts
FROM autonomous_lab_events_outbox
WHERE run_id = $1
ORDER BY event_id ASC
LIMIT $2
"""

RECORD_CURATOR_DECISION_SQL = """
WITH existing AS (
    SELECT
        run_id,
        status,
        FALSE AS changed
    FROM autonomous_lab_runs
    WHERE run_id = $1
      AND metadata->>'curator_decision_id' = $2
),
updated AS (
    UPDATE autonomous_lab_runs
    SET
        status = $4,
        metadata = metadata || $5::jsonb,
        worker_id = NULL,
        next_attempt_at = CASE WHEN $4 = 'pending' THEN NOW() ELSE next_attempt_at END,
        updated_at = NOW()
    WHERE run_id = $1
      AND status = 'paused'
      AND NOT EXISTS (SELECT 1 FROM existing)
    RETURNING
        run_id,
        status,
        TRUE AS changed
),
event_insert AS (
    INSERT INTO autonomous_lab_events_outbox (run_id, event_type, payload)
    SELECT run_id, 'curator_decision_recorded', $6::jsonb
    FROM updated
    RETURNING event_id
)
SELECT
    COALESCE((SELECT run_id FROM updated), (SELECT run_id FROM existing)) AS run_id,
    COALESCE((SELECT status FROM updated), (SELECT status FROM existing)) AS status,
    (SELECT COUNT(*) FROM updated) AS updated_count,
    (SELECT COUNT(*) FROM existing) AS existing_count,
    (SELECT event_id FROM event_insert) AS event_id
"""

CANCEL_RUN_SQL = """
WITH existing AS (
    SELECT
        run_id,
        status,
        FALSE AS changed
    FROM autonomous_lab_runs
    WHERE run_id = $1
      AND metadata->>'cancel_id' = $2
),
updated AS (
    UPDATE autonomous_lab_runs
    SET
        status = 'cancelled',
        metadata = metadata || $3::jsonb,
        worker_id = NULL,
        updated_at = NOW()
    WHERE run_id = $1
      AND status IN ('pending', 'paused')
      AND NOT EXISTS (SELECT 1 FROM existing)
    RETURNING
        run_id,
        status,
        TRUE AS changed
),
event_insert AS (
    INSERT INTO autonomous_lab_events_outbox (run_id, event_type, payload)
    SELECT run_id, 'run_cancelled', $4::jsonb
    FROM updated
    RETURNING event_id
)
SELECT
    COALESCE((SELECT run_id FROM updated), (SELECT run_id FROM existing)) AS run_id,
    COALESCE((SELECT status FROM updated), (SELECT status FROM existing)) AS status,
    (SELECT COUNT(*) FROM updated) AS updated_count,
    (SELECT COUNT(*) FROM existing) AS existing_count,
    (SELECT event_id FROM event_insert) AS event_id
"""


def resolve_runtime_placement(hostname: str, username: str = "") -> LabRuntimePlacement:
    """Resolve the safe Lab role for a local fleet host."""
    if hostname == "Air-M5" and username == "balizero":
        return LabRuntimePlacement(
            machine_role=LabMachineRole.AIR_COCKPIT,
            can_enqueue=True,
            can_claim_runs=False,
            can_consume_outbox=False,
            heavy_work_destination="ssh pro",
            reason="Air-M5 is the thin-client cockpit; heavy Lab runtime belongs on Pro.",
        )
    if hostname == "Nuzantara" and username == "nuzantara":
        return LabRuntimePlacement(
            machine_role=LabMachineRole.PRO_RUNTIME,
            can_enqueue=True,
            can_claim_runs=True,
            can_consume_outbox=True,
            heavy_work_destination="local Pro runtime",
            reason="Pro is the workhorse node for Lab workers, DB, deploy tooling, and heavy execution.",
        )
    if hostname == "Mini-Pro2" and username == "nuzantara":
        return LabRuntimePlacement(
            machine_role=LabMachineRole.MINI_SCHEDULER,
            can_enqueue=True,
            can_claim_runs=False,
            can_consume_outbox=True,
            heavy_work_destination="ssh pro",
            reason="Mini can host H24 scheduling and outbox drains, but run execution routes to Pro.",
        )
    return LabRuntimePlacement(
        machine_role=LabMachineRole.UNKNOWN,
        can_enqueue=False,
        can_claim_runs=False,
        can_consume_outbox=False,
        heavy_work_destination="operator decision required",
        reason="Unknown host; Lab runtime is disabled fail-closed.",
    )


def current_runtime_placement() -> LabRuntimePlacement:
    """Resolve the placement for the current local process."""
    return resolve_runtime_placement(socket.gethostname(), getpass.getuser())


def assert_run_worker_allowed(machine_role: LabMachineRole | str) -> LabMachineRole:
    """Raise unless this role is allowed to claim and execute Lab runs."""
    role = _coerce_machine_role(machine_role)
    if role is not LabMachineRole.PRO_RUNTIME:
        raise ValueError("Autonomous Lab run workers must execute on Pro runtime")
    return role


def assert_outbox_consumer_allowed(machine_role: LabMachineRole | str) -> LabMachineRole:
    """Raise unless this role may consume Lab outbox events."""
    role = _coerce_machine_role(machine_role)
    if role not in {LabMachineRole.PRO_RUNTIME, LabMachineRole.MINI_SCHEDULER}:
        raise ValueError("Autonomous Lab outbox consumers are Pro/Mini only")
    return role


def assert_run_queue_item_persistable(item: LabRunQueueItem) -> None:
    """Raise if any run queue field is unsafe for durable storage."""
    _assert_target_paths_persistable(item.target_paths)
    objective_reference = _safe_objective_reference(item.objective)
    safe_metadata = _safe_operational_payload(
        item.metadata,
        max_items=MAX_METADATA_ITEMS,
        path="$metadata",
    )
    assert_receipt_persistable(
        {
            "run_id": item.run_id,
            "idempotency_key": item.idempotency_key,
            "objective_reference": objective_reference,
            "receipt": dict(item.receipt),
            "target_paths": list(item.target_paths),
            "metadata": safe_metadata,
            "blocked": False,
        }
    )


class AutonomousLabStateStore:
    """Storage adapter for Lab run queue and outbox events."""

    def __init__(self) -> None:
        self.placement = current_runtime_placement()

    async def enqueue_run(self, conn: AsyncConnection, item: LabRunQueueItem) -> LabRunRecord:
        """Insert one run idempotently and atomically append its creation event."""
        assert_run_queue_item_persistable(item)
        safe_objective = _safe_objective_reference(item.objective)
        safe_metadata = _safe_operational_payload(
            item.metadata,
            max_items=MAX_METADATA_ITEMS,
            path="$metadata",
        )
        row = await conn.fetchrow(
            ENQUEUE_RUN_SQL,
            item.run_id,
            item.idempotency_key,
            safe_objective,
            _jsonb(item.receipt),
            list(item.target_paths),
            _jsonb(safe_metadata),
            item.priority,
            item.max_attempts,
        )
        if row is None:
            raise RuntimeError("autonomous_lab_runs enqueue returned no row")

        return _run_record(row)

    async def get_run(self, conn: AsyncConnection, *, run_id: str) -> LabRunRecord | None:
        """Read one Lab run without mutating queue state."""
        _validate_run_id(run_id)
        row = await conn.fetchrow(GET_RUN_SQL, run_id)
        if row is None:
            return None
        return _run_record(row)

    async def list_run_events(
        self,
        conn: AsyncConnection,
        *,
        run_id: str,
        limit: int = 100,
    ) -> list[LabOutboxEvent]:
        """Read receipt-safe event rows for one Lab run."""
        _validate_run_id(run_id)
        bounded_limit = min(max(limit, 1), 500)
        rows = await conn.fetch(LIST_RUN_EVENTS_SQL, run_id, bounded_limit)
        return [_outbox_event(row) for row in rows]

    async def claim_next_run(
        self,
        conn: AsyncConnection,
        *,
        worker_id: str,
        machine_role: LabMachineRole | str | None = None,
    ) -> LabRunRecord | None:
        """Atomically claim one pending run and append its claim event."""
        role = self._assert_run_worker_allowed(machine_role)
        row = await conn.fetchrow(CLAIM_NEXT_RUN_SQL, worker_id, role.value)
        if row is None:
            return None
        return _run_record(row)

    async def heartbeat_run(
        self,
        conn: AsyncConnection,
        *,
        run_id: str,
        worker_id: str,
    ) -> bool:
        """Refresh a running worker heartbeat without changing ownership."""
        self._assert_run_worker_allowed()
        result = await conn.execute(
            """
            UPDATE autonomous_lab_runs
            SET heartbeat_at = NOW(), updated_at = NOW()
            WHERE run_id = $1
              AND worker_id = $2
              AND status = 'running'
            """,
            run_id,
            worker_id,
        )
        return _execute_updated(result)

    async def mark_run_succeeded(
        self,
        conn: AsyncConnection,
        *,
        run_id: str,
        worker_id: str,
        summary: Mapping[str, Any] | None = None,
    ) -> bool:
        """Mark a run complete and append success if the owner update succeeds."""
        self._assert_run_worker_allowed()
        payload = {
            "worker_id": worker_id,
            "summary": _safe_operational_payload(
                summary or {},
                max_items=MAX_PAYLOAD_ITEMS,
                path="$summary",
            ),
        }
        assert_receipt_persistable({"run_id": run_id, "payload": payload, "blocked": False})
        row = await conn.fetchrow(
            MARK_RUN_SUCCEEDED_SQL,
            run_id,
            worker_id,
            _jsonb({"run_id": run_id, **payload}),
        )
        return _row_updated(row)

    async def mark_run_paused(
        self,
        conn: AsyncConnection,
        *,
        run_id: str,
        worker_id: str,
        stage: str,
        checkpoint: Mapping[str, Any],
    ) -> bool:
        """Pause a running Lab run at an operator gate and append an event."""
        self._assert_run_worker_allowed()
        safe_stage = _safe_operational_value(stage, path="$stage", key="stage")
        safe_checkpoint = _safe_operational_payload(
            dict(checkpoint),
            max_items=MAX_PAYLOAD_ITEMS,
            path="$checkpoint",
        )
        metadata_patch = {
            "paused_at_stage": safe_stage,
            "last_checkpoint_stage": safe_stage,
            "checkpoint_fingerprint": safe_checkpoint.get("fingerprint"),
        }
        payload = {
            "run_id": run_id,
            "worker_id": worker_id,
            "stage": safe_stage,
            "checkpoint": safe_checkpoint,
        }
        assert_receipt_persistable({"run_id": run_id, "payload": payload, "blocked": False})
        row = await conn.fetchrow(
            MARK_RUN_PAUSED_SQL,
            run_id,
            worker_id,
            _jsonb(metadata_patch),
            _jsonb(payload),
        )
        return _row_updated(row)

    async def mark_run_failed(
        self,
        conn: AsyncConnection,
        *,
        run_id: str,
        worker_id: str,
        error: str,
        retry_delay: timedelta = DEFAULT_RUN_RETRY_DELAY,
    ) -> bool:
        """Mark a run failed or retryable and append the failure event."""
        self._assert_run_worker_allowed()
        safe_error = _safe_error_reference(error)
        payload = {"run_id": run_id, "worker_id": worker_id, "error_reference": safe_error}
        row = await conn.fetchrow(
            MARK_RUN_FAILED_SQL,
            run_id,
            worker_id,
            safe_error,
            retry_delay,
            _jsonb(payload),
        )
        return _row_updated(row)

    async def record_curator_decision(
        self,
        conn: AsyncConnection,
        *,
        run_id: str,
        decision: str,
        decision_id: str,
        operator_id: str,
        note: str | None = None,
    ) -> LabControlMutationResult:
        """Record an idempotent manual curator decision for a paused run."""
        _validate_run_id(run_id)
        safe_decision = _coerce_curator_decision(decision)
        safe_decision_id = _validate_decision_id(decision_id)
        note_reference = _optional_note_reference(note)
        operator_reference = receipt_safe_evidence(operator_id, force_fingerprint=True)
        next_status = _status_after_curator_decision(safe_decision)
        metadata_patch = {
            "curator_decision": safe_decision,
            "curator_decision_id": safe_decision_id,
            "curator_operator_reference": operator_reference,
            "last_checkpoint_stage": _resume_stage_after_curator_decision(safe_decision),
        }
        payload = {
            "run_id": run_id,
            "decision": safe_decision,
            "decision_id": safe_decision_id,
            "operator_reference": operator_reference,
            "next_status": next_status,
        }
        if note_reference is not None:
            metadata_patch["curator_note_reference"] = note_reference
            payload["note_reference"] = note_reference

        assert_receipt_persistable({"run_id": run_id, "payload": payload, "blocked": False})
        row = await conn.fetchrow(
            RECORD_CURATOR_DECISION_SQL,
            run_id,
            safe_decision_id,
            safe_decision,
            next_status,
            _jsonb(metadata_patch),
            _jsonb(payload),
        )
        return _control_mutation_result(row, run_id=run_id)

    async def cancel_run(
        self,
        conn: AsyncConnection,
        *,
        run_id: str,
        cancel_id: str,
        operator_id: str,
        reason: str | None = None,
    ) -> LabControlMutationResult:
        """Cancel a non-running Lab run with an idempotent operator action."""
        _validate_run_id(run_id)
        safe_cancel_id = _validate_decision_id(cancel_id)
        operator_reference = receipt_safe_evidence(operator_id, force_fingerprint=True)
        reason_reference = _optional_note_reference(reason)
        metadata_patch = {
            "cancel_id": safe_cancel_id,
            "cancel_operator_reference": operator_reference,
        }
        payload = {
            "run_id": run_id,
            "cancel_id": safe_cancel_id,
            "operator_reference": operator_reference,
        }
        if reason_reference is not None:
            metadata_patch["cancel_reason_reference"] = reason_reference
            payload["reason_reference"] = reason_reference

        assert_receipt_persistable({"run_id": run_id, "payload": payload, "blocked": False})
        row = await conn.fetchrow(
            CANCEL_RUN_SQL,
            run_id,
            safe_cancel_id,
            _jsonb(metadata_patch),
            _jsonb(payload),
        )
        return _control_mutation_result(row, run_id=run_id)

    async def append_event(
        self,
        conn: AsyncConnection,
        *,
        run_id: str,
        event_type: LabEventType | str,
        payload: Mapping[str, Any],
        max_attempts: int = DEFAULT_EVENT_MAX_ATTEMPTS,
    ) -> int:
        """Append one receipt-safe outbox event."""
        event = _coerce_event_type(event_type)
        event_payload = _safe_operational_payload(
            {**dict(payload), "run_id": run_id},
            max_items=MAX_PAYLOAD_ITEMS,
            path="$event_payload",
        )
        assert_receipt_persistable(
            {
                "run_id": run_id,
                "event_type": event.value,
                "payload": event_payload,
                "blocked": False,
            }
        )
        row = await conn.fetchrow(
            """
            INSERT INTO autonomous_lab_events_outbox (
                run_id,
                event_type,
                payload,
                max_attempts
            )
            VALUES ($1, $2, $3::jsonb, $4)
            RETURNING event_id
            """,
            run_id,
            event.value,
            _jsonb(event_payload),
            max_attempts,
        )
        if row is None:
            raise RuntimeError("autonomous_lab_events_outbox append returned no row")
        return int(_row_get(row, "event_id"))

    async def claim_outbox_events(
        self,
        conn: AsyncConnection,
        *,
        consumer_id: str,
        machine_role: LabMachineRole | str | None = None,
        limit: int = 50,
    ) -> list[LabOutboxEvent]:
        """Claim pending outbox events for a Pro/Mini consumer."""
        self._assert_outbox_consumer_allowed(machine_role)
        bounded_limit = min(max(limit, 1), 500)
        rows = await conn.fetch(CLAIM_OUTBOX_EVENTS_SQL, bounded_limit, consumer_id)
        return [_outbox_event(row) for row in rows]

    async def ack_outbox_event(
        self,
        conn: AsyncConnection,
        *,
        event_id: int,
        consumer_id: str,
    ) -> bool:
        """Ack an event only after the downstream handler succeeds."""
        self._assert_outbox_consumer_allowed()
        result = await conn.execute(
            """
            UPDATE autonomous_lab_events_outbox
            SET
                status = 'consumed',
                consumed_at = NOW(),
                updated_at = NOW()
            WHERE event_id = $1
              AND claimed_by = $2
              AND status = 'in_progress'
              AND consumed_at IS NULL
            """,
            event_id,
            consumer_id,
        )
        return _execute_updated(result)

    async def retry_outbox_event(
        self,
        conn: AsyncConnection,
        *,
        event_id: int,
        consumer_id: str,
        error: str,
        retry_delay: timedelta = DEFAULT_EVENT_RETRY_DELAY,
    ) -> bool:
        """Release an event for retry, or send it to DLQ after max attempts."""
        self._assert_outbox_consumer_allowed()
        safe_error = _safe_error_reference(error)
        result = await conn.execute(
            """
            UPDATE autonomous_lab_events_outbox
            SET
                status = CASE
                    WHEN attempts >= max_attempts THEN 'failed_dlq'
                    ELSE 'pending'
                END,
                next_attempt_at = CASE
                    WHEN attempts >= max_attempts THEN next_attempt_at
                    ELSE NOW() + $4::interval
                END,
                claimed_by = NULL,
                last_error = $3,
                updated_at = NOW()
            WHERE event_id = $1
              AND claimed_by = $2
              AND status = 'in_progress'
            """,
            event_id,
            consumer_id,
            safe_error,
            retry_delay,
        )
        return _execute_updated(result)

    def _assert_run_worker_allowed(
        self,
        requested_role: LabMachineRole | str | None = None,
    ) -> LabMachineRole:
        actual_role = assert_run_worker_allowed(self.placement.machine_role)
        if requested_role is not None and _coerce_machine_role(requested_role) != actual_role:
            raise ValueError("requested Lab machine role does not match current host placement")
        return actual_role

    def _assert_outbox_consumer_allowed(
        self,
        requested_role: LabMachineRole | str | None = None,
    ) -> LabMachineRole:
        actual_role = assert_outbox_consumer_allowed(self.placement.machine_role)
        if requested_role is not None and _coerce_machine_role(requested_role) != actual_role:
            raise ValueError("requested Lab machine role does not match current host placement")
        return actual_role


def _coerce_machine_role(machine_role: LabMachineRole | str) -> LabMachineRole:
    if isinstance(machine_role, LabMachineRole):
        return machine_role
    return LabMachineRole(machine_role)


def _coerce_event_type(event_type: LabEventType | str) -> LabEventType:
    if isinstance(event_type, LabEventType):
        return event_type
    return LabEventType(event_type)


def _validate_run_id(run_id: str) -> None:
    if not _SAFE_RUN_ID_RE.match(run_id):
        raise ValueError("run_id must match autonomous lab safe id pattern")


def _validate_decision_id(decision_id: str) -> str:
    safe_decision_id = decision_id.strip()
    if not _SAFE_DECISION_ID_RE.match(safe_decision_id):
        raise ValueError("decision_id must match autonomous lab safe id pattern")
    return safe_decision_id


def _coerce_curator_decision(decision: str) -> str:
    safe_decision = decision.strip()
    if safe_decision not in _CURATOR_DECISIONS:
        raise ValueError("unsupported autonomous lab curator decision")
    return safe_decision


def _status_after_curator_decision(decision: str) -> str:
    if decision in {"reject", "cancel"}:
        return LabRunStatus.CANCELLED.value
    return LabRunStatus.PENDING.value


def _resume_stage_after_curator_decision(decision: str) -> str:
    if decision == "request_changes":
        return "reconstruct"
    return "curate"


def _optional_note_reference(note: str | None) -> str | None:
    if note is None or not note.strip():
        return None
    return receipt_safe_evidence(note[:4000], force_fingerprint=True)


def _jsonb(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), allow_nan=False, ensure_ascii=False, sort_keys=True)


def _assert_target_paths_persistable(target_paths: Sequence[str]) -> None:
    for index, target_path in enumerate(target_paths):
        if not isinstance(target_path, str):
            raise ValueError(f"unsafe_target_path: target_paths[{index}] must be a string")
        reason = invalid_autonomous_lab_target_path_reason(target_path)
        if reason:
            raise ValueError(f"unsafe_target_path: {reason}")


def _safe_objective_reference(objective: str) -> str:
    candidate = objective.strip()
    if not candidate:
        raise ValueError("objective must be a non-empty receipt-safe summary")
    if len(candidate) > MAX_OBJECTIVE_CHARS:
        raise ValueError("objective exceeds autonomous lab persistence limit")
    assert_receipt_persistable({"objective": candidate, "blocked": False})
    return receipt_safe_evidence(candidate, force_fingerprint=True)


def _safe_operational_payload(
    value: Mapping[str, Any],
    *,
    max_items: int,
    path: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be a JSON object")
    if len(value) > max_items:
        raise ValueError(f"{path} exceeds autonomous lab persistence item limit")
    sanitized = _safe_operational_value(value, path=path, key="")
    if not isinstance(sanitized, dict):
        raise ValueError(f"{path} must sanitize to a JSON object")
    return sanitized


def _safe_operational_value(value: Any, *, path: str, key: str) -> Any:
    if isinstance(value, Mapping):
        if len(value) > MAX_PAYLOAD_ITEMS:
            raise ValueError(f"{path} exceeds autonomous lab persistence item limit")
        output: dict[str, Any] = {}
        for raw_key, child in value.items():
            key_text = str(raw_key)
            key_path = f"{path}.{key_text}"
            _assert_safe_payload_key(key_text, key_path)
            output[key_text] = _safe_operational_value(child, path=key_path, key=key_text)
        return output
    if isinstance(value, list | tuple):
        if len(value) > MAX_PAYLOAD_LIST_ITEMS:
            raise ValueError(f"{path} exceeds autonomous lab persistence list limit")
        return [
            _safe_operational_value(child, path=f"{path}[{index}]", key=key)
            for index, child in enumerate(value)
        ]
    if isinstance(value, str):
        assert_receipt_persistable({"value": value, "blocked": False})
        if contains_receipt_sensitive_value(value):
            raise ValueError(f"{path} contains unsafe raw or secret-like value")
        if key in _PRESERVE_TOKEN_KEYS and _LOW_RISK_TOKEN_RE.match(value.strip()):
            return value.strip()
        return receipt_safe_evidence(value, force_fingerprint=True)
    if value is None or isinstance(value, bool | int | float):
        return value
    raise TypeError(f"{path} contains non-JSON value: {type(value).__name__}")


def _assert_safe_payload_key(key: str, path: str) -> None:
    normalized = key.lower()
    if normalized in _RAW_PAYLOAD_KEYS:
        raise ValueError(f"{path} uses raw-content metadata key: {key}")
    if not _SAFE_PAYLOAD_KEY_RE.match(key):
        raise ValueError(f"{path} uses unsafe metadata key: {key}")


def _run_record(row: Any) -> LabRunRecord:
    target_paths = _row_get(row, "target_paths") or []
    return LabRunRecord(
        run_id=str(_row_get(row, "run_id")),
        idempotency_key=str(_row_get(row, "idempotency_key")),
        status=LabRunStatus(str(_row_get(row, "status"))),
        objective=str(_row_get(row, "objective")),
        receipt=dict(_row_get(row, "receipt") or {}),
        target_paths=tuple(str(path) for path in target_paths),
        metadata=dict(_row_get(row, "metadata") or {}),
        priority=int(_row_get(row, "priority") or 0),
        attempts=int(_row_get(row, "attempts") or 0),
        max_attempts=int(_row_get(row, "max_attempts") or DEFAULT_RUN_MAX_ATTEMPTS),
        inserted=bool(_row_get(row, "inserted")),
    )


def _outbox_event(row: Any) -> LabOutboxEvent:
    return LabOutboxEvent(
        event_id=int(_row_get(row, "event_id")),
        run_id=str(_row_get(row, "run_id")),
        event_type=LabEventType(str(_row_get(row, "event_type"))),
        payload=dict(_row_get(row, "payload") or {}),
        status=LabOutboxStatus(str(_row_get(row, "status"))),
        attempts=int(_row_get(row, "attempts") or 0),
    )


def _control_mutation_result(row: Any, *, run_id: str) -> LabControlMutationResult:
    if row is None or _row_get(row, "run_id") is None:
        return LabControlMutationResult(
            run_id=run_id,
            changed=False,
            idempotent_replay=False,
            status=None,
            event_id=None,
        )
    status_value = _row_get(row, "status")
    event_id = _row_get(row, "event_id")
    return LabControlMutationResult(
        run_id=str(_row_get(row, "run_id")),
        changed=int(_row_get(row, "updated_count") or 0) > 0,
        idempotent_replay=int(_row_get(row, "existing_count") or 0) > 0,
        status=LabRunStatus(str(status_value)) if status_value is not None else None,
        event_id=int(event_id) if event_id is not None else None,
    )


def _row_get(row: Any, key: str) -> Any:
    if isinstance(row, Mapping):
        return row[key]
    return row[key]


def _row_updated(row: Any) -> bool:
    if row is None:
        return False
    return int(_row_get(row, "updated_count") or 0) > 0


def _execute_updated(result: str) -> bool:
    count = _updated_row_count(result)
    return count is None or count > 0


def _updated_row_count(result: str) -> int | None:
    parts = result.split()
    if len(parts) < 2:
        return None
    try:
        return int(parts[-1])
    except ValueError:
        return None


def _safe_error_reference(error: str) -> str:
    return receipt_safe_evidence(error[:4000], force_fingerprint=True)


__all__ = [
    "CANCEL_RUN_SQL",
    "CLAIM_NEXT_RUN_SQL",
    "CLAIM_OUTBOX_EVENTS_SQL",
    "DEFAULT_EVENT_MAX_ATTEMPTS",
    "DEFAULT_EVENT_RETRY_DELAY",
    "DEFAULT_RUN_MAX_ATTEMPTS",
    "DEFAULT_RUN_RETRY_DELAY",
    "ENQUEUE_RUN_SQL",
    "GET_RUN_SQL",
    "LIST_RUN_EVENTS_SQL",
    "MARK_RUN_FAILED_SQL",
    "MARK_RUN_PAUSED_SQL",
    "MARK_RUN_SUCCEEDED_SQL",
    "RECORD_CURATOR_DECISION_SQL",
    "AutonomousLabStateStore",
    "LabControlMutationResult",
    "LabEventType",
    "LabMachineRole",
    "LabOutboxEvent",
    "LabOutboxStatus",
    "LabRunQueueItem",
    "LabRunRecord",
    "LabRunStatus",
    "LabRuntimePlacement",
    "assert_outbox_consumer_allowed",
    "assert_run_queue_item_persistable",
    "assert_run_worker_allowed",
    "current_runtime_placement",
    "resolve_runtime_placement",
]
