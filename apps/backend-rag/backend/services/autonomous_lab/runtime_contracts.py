"""Runtime contracts for the Autonomous Lab control room and worker lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from backend.services.autonomous_lab.operational_plan import (
    LabOperationalPlan,
    default_operational_plan,
)
from backend.services.autonomous_lab.receipt_safety import (
    receipt_safe_evidence,
    safe_sha256_fingerprint,
)
from backend.services.autonomous_lab.state_store import (
    LabRuntimePlacement,
    current_runtime_placement,
)

RUNTIME_CONTRACT_VERSION = "autonomous-lab-v1-runtime-contract"


class LabTone(str, Enum):
    """UI tone vocabulary shared by backend receipts and the control room."""

    GOOD = "good"
    WARN = "warn"
    DANGER = "danger"
    NEUTRAL = "neutral"


class LabControlRoomStageStatus(str, Enum):
    """Operator-visible status for the dashboard stage cards."""

    LIVE = "live"
    PLANNED = "planned"
    BLOCKED = "blocked"
    PAUSED = "paused"
    DESIGNING = "designing"


class LabStageStatus(str, Enum):
    """Canonical durable lifecycle status for a Lab stage checkpoint."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class LabGateState(str, Enum):
    """Gate state used by runtime snapshots."""

    PASSED = "passed"
    PENDING = "pending"
    BLOCKED = "blocked"
    MANUAL = "manual"


class LabStageKey(str, Enum):
    """Dashboard stage keys for Lab UI cards."""

    WATCH = "watch"
    INTAKE = "intake"
    PLAN = "plan"
    WORKER = "worker"
    ARENA = "arena"
    TRIBUNAL = "tribunal"
    CURATOR = "curator"
    ARCHIVE = "archive"


class LabStageName(str, Enum):
    """Canonical worker lifecycle stage names."""

    WATCH = "watch"
    INTAKE = "intake"
    NORMALIZE = "normalize"
    COMPOSE = "compose"
    RECONSTRUCT = "reconstruct"
    EXPERIMENT = "experiment"
    VERIFY = "verify"
    CURATE = "curate"
    ARCHIVE = "archive"


class LabArtifactKind(str, Enum):
    """Canonical artifact names emitted by Lab stages."""

    FRONTIER_SIGNAL = "FrontierSignal"
    RESEARCH_MATERIAL = "ResearchMaterial"
    LAB_RUN = "LabRun"
    LAB_CHECKPOINT = "LabCheckpoint"
    SANDBOX_RUN_RESULT = "SandboxRunResult"
    EVALUATION_REPORT = "EvaluationReport"
    CURATOR_DECISION = "CuratorDecision"
    TRAJECTORY_SUMMARY = "TrajectorySummary"


class CuratorDecision(str, Enum):
    """Manual curator decisions allowed at the interrupt gate."""

    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"
    CANCEL = "cancel"


@dataclass(frozen=True)
class LabCheckpoint:
    """Durable, receipt-safe checkpoint emitted after a stage transition."""

    run_id: str
    stage: LabStageName
    status: LabStageStatus
    fingerprint: str
    created_at: datetime
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.stage, LabStageName):
            raise ValueError("Lab checkpoint stage must use canonical LabStageName")
        if not isinstance(self.status, LabStageStatus):
            raise ValueError("Lab checkpoint status must use canonical LabStageStatus")

    def to_receipt(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "stage": self.stage.value,
            "status": self.status.value,
            "fingerprint": self.fingerprint,
            "created_at": self.created_at.isoformat(),
            "payload": _safe_lifecycle_payload(self.payload),
        }


@dataclass(frozen=True)
class LabArtifactManifest:
    """Receipt-safe artifact pointer produced by sandbox or evaluator stages."""

    artifact_id: str
    kind: LabArtifactKind
    path_or_ref: str
    sha256: str
    data_class: str
    retention_policy: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, LabArtifactKind):
            raise ValueError("Lab artifact kind must use canonical LabArtifactKind")

    def to_receipt(self) -> dict[str, str]:
        return {
            "artifact_id": receipt_safe_evidence(self.artifact_id, force_fingerprint=True),
            "kind": self.kind.value,
            "path_or_ref": receipt_safe_evidence(self.path_or_ref, force_fingerprint=True),
            "sha256": self.sha256,
            "data_class": self.data_class,
            "retention_policy": self.retention_policy,
        }


def build_lab_checkpoint(
    *,
    run_id: str,
    stage: LabStageName,
    status: LabStageStatus,
    payload: dict[str, Any] | None = None,
    created_at: datetime | None = None,
) -> LabCheckpoint:
    """Build a canonical checkpoint with a deterministic payload fingerprint."""
    safe_payload = _safe_lifecycle_payload(payload or {})
    fingerprint = safe_sha256_fingerprint(
        f"{run_id}:{stage.value}:{status.value}:{safe_payload}",
        hex_chars=24,
    )
    return LabCheckpoint(
        run_id=run_id,
        stage=stage,
        status=status,
        fingerprint=fingerprint,
        created_at=created_at or datetime.now(tz=timezone.utc),
        payload=safe_payload,
    )


@dataclass(frozen=True)
class LabRuntimeMetric:
    """One compact status metric for the control room header."""

    label: str
    value: str
    tone: LabTone

    def to_receipt(self) -> dict[str, str]:
        return {
            "label": self.label,
            "value": self.value,
            "tone": self.tone.value,
        }


@dataclass(frozen=True)
class LabRuntimeStage:
    """One operator-visible stage in the Lab pipeline."""

    key: LabStageKey
    label: str
    status: LabControlRoomStageStatus
    owner: str
    gate: str
    gate_state: LabGateState
    summary: str
    artifact: LabArtifactKind

    def to_receipt(self) -> dict[str, str]:
        return {
            "id": self.key.value,
            "label": self.label,
            "status": self.status.value,
            "owner": self.owner,
            "gate": self.gate,
            "gate_state": self.gate_state.value,
            "summary": self.summary,
            "artifact": self.artifact.value,
        }


@dataclass(frozen=True)
class LabRuntimeLane:
    """Parallel work lane surfaced by the control room."""

    name: str
    status: str
    next: str
    proof: str
    tone: LabTone

    def to_receipt(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "next": self.next,
            "proof": self.proof,
            "tone": self.tone.value,
        }


@dataclass(frozen=True)
class LabRuntimeAction:
    """Near-term implementation unit shown in the control room."""

    order: int
    title: str
    backend: str
    ui: str
    gate: str

    def to_receipt(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "title": self.title,
            "backend": self.backend,
            "ui": self.ui,
            "gate": self.gate,
        }


@dataclass(frozen=True)
class LabRuntimeRisk:
    """Known Lab failure mode and its active control."""

    label: str
    control: str
    tone: LabTone

    def to_receipt(self) -> dict[str, str]:
        return {
            "label": self.label,
            "control": self.control,
            "tone": self.tone.value,
        }


@dataclass(frozen=True)
class LabRuntimeSnapshot:
    """Receipt-safe snapshot consumed by the Lab Control Room."""

    version: str
    updated_at: datetime
    machine: str
    machine_role: str
    sync_state: str
    doctrine: str
    metrics: tuple[LabRuntimeMetric, ...]
    stages: tuple[LabRuntimeStage, ...]
    lanes: tuple[LabRuntimeLane, ...]
    first_batch: tuple[LabRuntimeAction, ...]
    risks: tuple[LabRuntimeRisk, ...]
    runtime_placement: LabRuntimePlacement
    operational_plan: dict[str, Any]

    def to_receipt(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "updatedAt": self.updated_at.date().isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "machine": self.machine,
            "machine_role": self.machine_role,
            "syncState": self.sync_state,
            "sync_state": self.sync_state,
            "doctrine": self.doctrine,
            "metrics": [metric.to_receipt() for metric in self.metrics],
            "stages": [stage.to_receipt() for stage in self.stages],
            "lanes": [lane.to_receipt() for lane in self.lanes],
            "firstBatch": [action.to_receipt() for action in self.first_batch],
            "first_batch": [action.to_receipt() for action in self.first_batch],
            "risks": [risk.to_receipt() for risk in self.risks],
            "runtime_placement": self.runtime_placement.to_receipt(),
            "operational_plan": self.operational_plan,
        }


def build_runtime_snapshot(
    *,
    plan: LabOperationalPlan | None = None,
    placement: LabRuntimePlacement | None = None,
    updated_at: datetime | None = None,
    sync_state: str = "peer sync not checked by API",
) -> LabRuntimeSnapshot:
    """Build a receipt-safe, read-only runtime snapshot."""
    active_plan = plan or default_operational_plan()
    active_placement = placement or current_runtime_placement()
    blocked_components = set(active_plan.blocked_component_keys)
    missing_components = set(active_plan.missing_component_keys)

    worker_tone = (
        LabTone.WARN
        if "operational_queue" not in missing_components
        else LabTone.DANGER
    )
    runtime_metric = (
        "claim-ready"
        if active_placement.can_claim_runs
        else active_placement.machine_role.value
    )

    return LabRuntimeSnapshot(
        version=RUNTIME_CONTRACT_VERSION,
        updated_at=updated_at or datetime.now(tz=timezone.utc),
        machine=_machine_label(active_placement),
        machine_role=active_placement.machine_role.value,
        sync_state=sync_state,
        doctrine="state + sandbox + evaluator + curator",
        metrics=(
            LabRuntimeMetric("Governance", "9 gates", LabTone.GOOD),
            LabRuntimeMetric("Runtime", runtime_metric, LabTone.GOOD),
            LabRuntimeMetric("Worker loop", _worker_metric_value(missing_components), worker_tone),
            LabRuntimeMetric("Promotion", "manual only", LabTone.GOOD),
        ),
        stages=_runtime_stages(blocked_components=blocked_components),
        lanes=_runtime_lanes(),
        first_batch=_first_batch_actions(),
        risks=_runtime_risks(),
        runtime_placement=active_placement,
        operational_plan=active_plan.to_receipt(),
    )


def _runtime_stages(*, blocked_components: set[str]) -> tuple[LabRuntimeStage, ...]:
    return (
        LabRuntimeStage(
            LabStageKey.WATCH,
            "Watch",
            LabControlRoomStageStatus.DESIGNING,
            "Source adapters",
            "freshness + novelty",
            LabGateState.PENDING,
            "Frontier signals from papers, repos, SDK docs, MCP, and notebooks.",
            LabArtifactKind.FRONTIER_SIGNAL,
        ),
        LabRuntimeStage(
            LabStageKey.INTAKE,
            "Intake",
            LabControlRoomStageStatus.LIVE,
            "Normalizer",
            "receipt-safe",
            LabGateState.PASSED,
            "Metadata-first ingestion with default hashing for external refs.",
            LabArtifactKind.RESEARCH_MATERIAL,
        ),
        LabRuntimeStage(
            LabStageKey.PLAN,
            "Plan",
            LabControlRoomStageStatus.LIVE,
            "Planner",
            "no raw text",
            LabGateState.PASSED,
            "Drafts LabRun receipts and bounded verification plans.",
            LabArtifactKind.LAB_RUN,
        ),
        LabRuntimeStage(
            LabStageKey.WORKER,
            "Worker",
            _blocked_if("operational_queue", blocked_components),
            "Durable runtime",
            "heartbeat",
            _gate_state_for("operational_queue", blocked_components),
            "Claims queue rows and checkpoints every stage transition.",
            LabArtifactKind.LAB_CHECKPOINT,
        ),
        LabRuntimeStage(
            LabStageKey.ARENA,
            "Arena",
            _blocked_if("worktree_experiment_runner", blocked_components),
            "Sandbox runner",
            "policy before execution",
            _gate_state_for("worktree_experiment_runner", blocked_components),
            "Runs only inside a declared filesystem, network, env, and timeout policy.",
            LabArtifactKind.SANDBOX_RUN_RESULT,
        ),
        LabRuntimeStage(
            LabStageKey.TRIBUNAL,
            "Tribunal",
            _blocked_if("verification_runner", blocked_components),
            "Evaluator",
            "Law 2 + sandbox hard fail",
            _gate_state_for("verification_runner", blocked_components),
            "Judges correctness, regression, leakage, cost, latency, and novelty.",
            LabArtifactKind.EVALUATION_REPORT,
        ),
        LabRuntimeStage(
            LabStageKey.CURATOR,
            "Curator",
            LabControlRoomStageStatus.PAUSED,
            "Operator gate",
            "manual decision",
            LabGateState.MANUAL,
            "Approves, rejects, cancels, or requests changes from compact evidence.",
            LabArtifactKind.CURATOR_DECISION,
        ),
        LabRuntimeStage(
            LabStageKey.ARCHIVE,
            "Archive",
            LabControlRoomStageStatus.PLANNED,
            "Learning library",
            "approved summaries only",
            LabGateState.PENDING,
            "Stores reusable technique summaries and failure taxonomy.",
            LabArtifactKind.TRAJECTORY_SUMMARY,
        ),
    )


def _runtime_lanes() -> tuple[LabRuntimeLane, ...]:
    return (
        LabRuntimeLane(
            "Backend organism",
            "Phase 0",
            "runtime contracts, worker skeleton, stage nodes",
            "queued run reaches curator pause",
            LabTone.WARN,
        ),
        LabRuntimeLane(
            "Visual control room",
            "Phase 0",
            "read-only status, run preview, sandbox policy",
            "UI mirrors every backend gate",
            LabTone.GOOD,
        ),
        LabRuntimeLane(
            "Safety arena",
            "Phase 1",
            "sandbox timeout runner, output redaction, evaluator schema",
            "no command executes without policy",
            LabTone.DANGER,
        ),
    )


def _first_batch_actions() -> tuple[LabRuntimeAction, ...]:
    return (
        LabRuntimeAction(
            1,
            "Lifecycle contracts",
            "runtime_contracts.py",
            "stage vocabulary and status tones",
            "unknown states fail closed",
        ),
        LabRuntimeAction(
            2,
            "Worker skeleton",
            "worker.py",
            "run timeline and heartbeat strip",
            "one claimed run pauses at curator",
        ),
        LabRuntimeAction(
            3,
            "Stage node interface",
            "stages.py",
            "canonical worker lifecycle",
            "stage outputs are receipt-safe",
        ),
        LabRuntimeAction(
            4,
            "Receipt store unification",
            "planner.py + receipt_store.py",
            "append-only receipt events",
            "no overwrite and no raw text",
        ),
        LabRuntimeAction(
            5,
            "Sandbox runner contract",
            "sandbox_runner.py",
            "timeout and redacted output",
            "allowlisted commands only",
        ),
        LabRuntimeAction(
            6,
            "Source adapters v1",
            "source_adapters.py",
            "watchtower signals",
            "metadata-only shadow ticks",
        ),
        LabRuntimeAction(
            7,
            "Normalizer and dedupe",
            "normalizer.py",
            "cluster and novelty readout",
            "raw material never leaves envelope",
        ),
        LabRuntimeAction(
            8,
            "Experiment spec",
            "experiment_spec.py",
            "candidate acceptance contract",
            "manual promotion required",
        ),
        LabRuntimeAction(
            9,
            "Evaluator tribunal",
            "evaluator.py",
            "policy, command, leakage, novelty verdict",
            "pending checks cannot pass silently",
        ),
        LabRuntimeAction(
            10,
            "Curator gate",
            "curator.py",
            "operator decision record",
            "promotion_allowed remains false",
        ),
        LabRuntimeAction(
            11,
            "Shadow run proof",
            "shadow_run.py",
            "watch-to-curate timeline",
            "external_calls equals zero",
        ),
        LabRuntimeAction(
            12,
            "Router shadow endpoint",
            "autonomous_lab.py",
            "control room data feed",
            "internal API only",
        ),
        LabRuntimeAction(
            13,
            "Sandbox hardening",
            "sandbox_runner.py",
            "command and env refusal receipts",
            "no shell escape",
        ),
        LabRuntimeAction(
            14,
            "Visual Lab panels",
            "app/autonomous-lab/page.tsx",
            "candidate, evaluator, curator, timeline",
            "read-only UI",
        ),
        LabRuntimeAction(
            15,
            "End-to-end shadow test",
            "test_shadow_run.py",
            "pipeline receipt proof",
            "no network or subprocess side effects",
        ),
    )


def _runtime_risks() -> tuple[LabRuntimeRisk, ...]:
    return (
        LabRuntimeRisk("phantom safety", "evaluator-first lifecycle", LabTone.DANGER),
        LabRuntimeRisk("raw leakage", "default hash + receipt tests", LabTone.DANGER),
        LabRuntimeRisk("split brain", "placement policy + claim rules", LabTone.WARN),
        LabRuntimeRisk("over-frameworking", "local contracts before adapters", LabTone.NEUTRAL),
    )


def _blocked_if(component: str, blocked_components: set[str]) -> LabControlRoomStageStatus:
    return (
        LabControlRoomStageStatus.BLOCKED
        if component in blocked_components
        else LabControlRoomStageStatus.PLANNED
    )


def _gate_state_for(component: str, blocked_components: set[str]) -> LabGateState:
    return LabGateState.BLOCKED if component in blocked_components else LabGateState.PENDING


def _worker_metric_value(missing_components: set[str]) -> str:
    if "operational_queue" in missing_components:
        return "contracted"
    return "ready"


def _machine_label(placement: LabRuntimePlacement) -> str:
    if placement.machine_role.value == "pro_runtime":
        return "Pro"
    if placement.machine_role.value == "mini_scheduler":
        return "Mini"
    if placement.machine_role.value == "air_m5_cockpit":
        return "Air-M5"
    return "Unknown"


def _safe_lifecycle_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe_lifecycle_payload(child) for key, child in value.items()}
    if isinstance(value, list | tuple):
        return [_safe_lifecycle_payload(child) for child in value]
    if isinstance(value, str):
        return receipt_safe_evidence(value, force_fingerprint=True)
    if value is None or isinstance(value, bool | int | float):
        return value
    return receipt_safe_evidence(repr(value), force_fingerprint=True)


__all__ = [
    "RUNTIME_CONTRACT_VERSION",
    "CuratorDecision",
    "LabArtifactKind",
    "LabArtifactManifest",
    "LabCheckpoint",
    "LabControlRoomStageStatus",
    "LabGateState",
    "LabRuntimeAction",
    "LabRuntimeLane",
    "LabRuntimeMetric",
    "LabRuntimeRisk",
    "LabRuntimeSnapshot",
    "LabRuntimeStage",
    "LabStageKey",
    "LabStageName",
    "LabStageStatus",
    "LabTone",
    "build_lab_checkpoint",
    "build_runtime_snapshot",
]
