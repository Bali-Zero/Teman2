"""Operational v1 control-plane contract for the autonomous lab."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

OPERATIONAL_PLAN_VERSION = "autonomous-lab-v1-control-plane"


class ComponentState(str, Enum):
    """Implementation state for a lab control-plane component."""

    ANCHORED = "anchored"
    CONTRACTED = "contracted"
    PLANNED = "planned"
    BLOCKED = "blocked"


class ParallelizationMode(str, Enum):
    """How a work package may run."""

    SERIAL_GATE = "serial_gate"
    PARALLEL_SAFE = "parallel_safe"
    MANUAL_GATE = "manual_gate"


@dataclass(frozen=True)
class SotaGovernancePiece:
    """One of the P1-P9 governance pieces that constrains lab execution."""

    key: str
    name: str
    lab_gate: str

    def to_receipt(self) -> dict[str, str]:
        return {
            "key": self.key,
            "name": self.name,
            "lab_gate": self.lab_gate,
        }


@dataclass(frozen=True)
class MetaWorkflowStage:
    """Repo-level meta-dev-loop stage that a lab run must account for."""

    order: int
    key: str
    label: str
    gate: str
    required_before_parallel: bool = False

    def to_receipt(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "key": self.key,
            "label": self.label,
            "gate": self.gate,
            "required_before_parallel": self.required_before_parallel,
        }


@dataclass(frozen=True)
class LabControlPlaneComponent:
    """One concrete v1 component that can be assigned to an agent lane."""

    key: str
    agent_role: str
    responsibility: str
    output: str
    gate: str
    state: ComponentState
    depends_on: tuple[str, ...] = ()
    parallel_group: str = "foundation"

    def to_receipt(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "agent_role": self.agent_role,
            "responsibility": self.responsibility,
            "output": self.output,
            "gate": self.gate,
            "state": self.state.value,
            "depends_on": list(self.depends_on),
            "parallel_group": self.parallel_group,
        }


@dataclass(frozen=True)
class ParallelWorkPackage:
    """A bounded package that can be delegated after its gate is satisfied."""

    key: str
    components: tuple[str, ...]
    mode: ParallelizationMode
    merge_gate: str
    rationale: str

    def to_receipt(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "components": list(self.components),
            "mode": self.mode.value,
            "merge_gate": self.merge_gate,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class LabOperationalPlan:
    """Receipt-safe v1 plan for turning lab v0 into an operational loop."""

    version: str
    governance_pieces: tuple[SotaGovernancePiece, ...]
    meta_workflow: tuple[MetaWorkflowStage, ...]
    anchor_jobs: tuple[LabControlPlaneComponent, ...]
    missing_components: tuple[LabControlPlaneComponent, ...]
    work_packages: tuple[ParallelWorkPackage, ...]

    @property
    def missing_component_keys(self) -> list[str]:
        return [component.key for component in self.missing_components]

    @property
    def parallelizable_component_keys(self) -> list[str]:
        package_components = {
            component
            for package in self.work_packages
            if package.mode == ParallelizationMode.PARALLEL_SAFE
            for component in package.components
        }
        return [
            component.key
            for component in self.missing_components
            if component.key in package_components
        ]

    @property
    def blocked_component_keys(self) -> list[str]:
        return [
            component.key
            for component in self.missing_components
            if component.state == ComponentState.BLOCKED
        ]

    def to_receipt(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "governance_pieces": [
                piece.to_receipt() for piece in self.governance_pieces
            ],
            "meta_workflow": [stage.to_receipt() for stage in self.meta_workflow],
            "anchor_jobs": [component.to_receipt() for component in self.anchor_jobs],
            "missing_components": [
                component.to_receipt() for component in self.missing_components
            ],
            "work_packages": [package.to_receipt() for package in self.work_packages],
            "missing_component_keys": self.missing_component_keys,
            "parallelizable_component_keys": self.parallelizable_component_keys,
            "blocked_component_keys": self.blocked_component_keys,
        }


SOTA_GOVERNANCE_PIECES: tuple[SotaGovernancePiece, ...] = (
    SotaGovernancePiece("P1", "verify_the_verifiers", "reviewer_is_imperfect"),
    SotaGovernancePiece("P2", "router_confine_pii", "private_material_boundary"),
    SotaGovernancePiece("P3", "test_prod_sandbox", "prod_like_isolation"),
    SotaGovernancePiece("P4", "seam_verify", "contract_before_assembly"),
    SotaGovernancePiece("P5", "spec_as_keystone", "spec_is_gate_not_note"),
    SotaGovernancePiece("P6", "parallelize_gate", "fanout_requires_contracts"),
    SotaGovernancePiece("P7", "learn_close_loop", "learning_is_quarantined"),
    SotaGovernancePiece("P8", "design_internal_app", "ui_generation_is_bounded"),
    SotaGovernancePiece("P9", "govern_silent_guardian", "deadman_liveness"),
)


META_WORKFLOW_STAGES: tuple[MetaWorkflowStage, ...] = (
    MetaWorkflowStage(
        0,
        "study",
        "continuous AI/software scouting, reuse-first memory recall, hot-file and risk scan",
        "fresh_research_or_idle_receipt",
        required_before_parallel=True,
    ),
    MetaWorkflowStage(1, "spec", "verifiable contract artifact", "acceptance_gates_named"),
    MetaWorkflowStage(2, "arch", "architecture decision loop", "dependencies_declared"),
    MetaWorkflowStage(
        3,
        "plan_squad",
        "parallelization decision and agent assignment",
        "fanout_contract_declared",
        required_before_parallel=True,
    ),
    MetaWorkflowStage(4, "build_parallel", "isolated worktree implementation", "worktree_isolated"),
    MetaWorkflowStage(5, "seam_verify", "contract checks at integration seams", "seams_verified"),
    MetaWorkflowStage(6, "enrich", "design and internal app enrichment", "enrichment_bounded"),
    MetaWorkflowStage(7, "test_prod", "prod-like verification", "prod_like_check_recorded"),
    MetaWorkflowStage(8, "review", "adversarial delegated review", "review_findings_closed"),
    MetaWorkflowStage(9, "ship", "merge and promotion gate", "manual_promotion_only"),
    MetaWorkflowStage(10, "learn", "quarantined memory or skill update", "learning_quarantined"),
    MetaWorkflowStage(99, "govern", "liveness and cost governance", "guardian_observed"),
)


ANCHOR_JOBS: tuple[LabControlPlaneComponent, ...] = (
    LabControlPlaneComponent(
        key="lab_intake_sweeper",
        agent_role="intake_sweeper",
        responsibility="collect eligible material envelopes from approved sources",
        output="ResearchMaterial envelopes",
        gate="source_provenance_captured",
        state=ComponentState.ANCHORED,
        parallel_group="intake",
    ),
)


MISSING_V1_COMPONENTS: tuple[LabControlPlaneComponent, ...] = (
    LabControlPlaneComponent(
        key="operational_queue",
        agent_role="queue_operator",
        responsibility="persist run state, idempotency, retries, visibility, and leases",
        output="autonomous_lab_runs state transition contract",
        gate="skip_locked_or_equivalent_claim",
        state=ComponentState.CONTRACTED,
        parallel_group="foundation",
    ),
    LabControlPlaneComponent(
        key="events_outbox",
        agent_role="outbox_guardian",
        responsibility="append durable lab events before any async notification",
        output="autonomous lab event envelope contract",
        gate="ack_after_success",
        state=ComponentState.CONTRACTED,
        depends_on=("operational_queue",),
        parallel_group="foundation",
    ),
    LabControlPlaneComponent(
        key="source_adapters",
        agent_role="source_adapter_engineer",
        responsibility="turn repo, web, dataset, and operator-note inputs into safe envelopes",
        output="adapter registry with provenance and raw-content ownership",
        gate="no_raw_receipt_persistence",
        state=ComponentState.PLANNED,
        depends_on=("operational_queue",),
        parallel_group="ingestion",
    ),
    LabControlPlaneComponent(
        key="ai_software_watchtower",
        agent_role="frontier_watchtower",
        responsibility=(
            "continuously scan approved AI research, model releases, SDK and framework "
            "changelogs, and software implementation patterns for Nuzantara applicability; "
            "route NotebookLM reads through frontier_radar and agent_engineering_core, "
            "and route new writes through ai_research_overflow when the radar is near cap"
        ),
        output="ranked FrontierSignal envelopes with NotebookLM route receipts",
        gate="fresh_sources_or_explicit_idle_receipt_and_notebook_route",
        state=ComponentState.PLANNED,
        depends_on=("operational_queue", "source_adapters"),
        parallel_group="ingestion",
    ),
    LabControlPlaneComponent(
        key="composer",
        agent_role="hypothesis_composer",
        responsibility="compose evidence-backed hypotheses and implementation briefs",
        output="hypothesis and spec bundle",
        gate="evidence_quorum_or_warning",
        state=ComponentState.PLANNED,
        depends_on=("source_adapters", "ai_software_watchtower"),
        parallel_group="reasoning",
    ),
    LabControlPlaneComponent(
        key="prod_like_context_builder",
        agent_role="context_builder",
        responsibility="reconstruct git, config, fixture, schema, and runtime context",
        output="sanitized simulation context manifest",
        gate="no_secret_values",
        state=ComponentState.PLANNED,
        depends_on=("source_adapters",),
        parallel_group="reasoning",
    ),
    LabControlPlaneComponent(
        key="worktree_experiment_runner",
        agent_role="worktree_experimenter",
        responsibility="apply bounded experiments only in agent_start worktrees",
        output="patch, artifact bundle, and failure notes",
        gate="worktree_isolation",
        state=ComponentState.PLANNED,
        depends_on=("composer", "prod_like_context_builder"),
        parallel_group="execution",
    ),
    LabControlPlaneComponent(
        key="verification_runner",
        agent_role="verification_runner",
        responsibility="run allowlisted tests, lint, metrics, and failure analysis",
        output="verification report",
        gate="empirical_result_recorded",
        state=ComponentState.PLANNED,
        depends_on=("worktree_experiment_runner",),
        parallel_group="execution",
    ),
    LabControlPlaneComponent(
        key="curator_decision_gate",
        agent_role="curator",
        responsibility="rank verified candidates and surface only decision-grade proposals",
        output="manual promotion recommendation or archive decision",
        gate="manual_operator_decision_only",
        state=ComponentState.PLANNED,
        depends_on=("verification_runner",),
        parallel_group="curation",
    ),
    LabControlPlaneComponent(
        key="scheduler_daemon",
        agent_role="scheduler_operator",
        responsibility="schedule safe lab ticks on Pro or Mini after the state contract is stable",
        output="cron or LaunchAgent handoff plan",
        gate="state_contract_stable_first",
        state=ComponentState.BLOCKED,
        depends_on=("operational_queue", "events_outbox", "curator_decision_gate"),
        parallel_group="ops",
    ),
    LabControlPlaneComponent(
        key="dashboard_api",
        agent_role="dashboard_api_engineer",
        responsibility="expose run status, blockers, receipts, and candidate proposals",
        output="read-only internal API and dashboard contract",
        gate="read_only_until_operator_action",
        state=ComponentState.PLANNED,
        depends_on=("operational_queue", "events_outbox"),
        parallel_group="ops",
    ),
)


PARALLEL_WORK_PACKAGES: tuple[ParallelWorkPackage, ...] = (
    ParallelWorkPackage(
        key="foundation_serial",
        components=("operational_queue", "events_outbox"),
        mode=ParallelizationMode.SERIAL_GATE,
        merge_gate="queue_and_outbox_contract_tests",
        rationale="state and event semantics must be stable before H24 scheduling",
    ),
    ParallelWorkPackage(
        key="ingestion_reasoning_parallel",
        components=(
            "source_adapters",
            "ai_software_watchtower",
            "composer",
            "prod_like_context_builder",
        ),
        mode=ParallelizationMode.PARALLEL_SAFE,
        merge_gate="receipt_safe_material_contract",
        rationale=(
            "watchtower, adapters, composer, and context builder can advance against "
            "one envelope contract"
        ),
    ),
    ParallelWorkPackage(
        key="execution_parallel",
        components=("worktree_experiment_runner", "verification_runner"),
        mode=ParallelizationMode.PARALLEL_SAFE,
        merge_gate="allowlisted_execution_and_verification",
        rationale="runner and verifier share the worktree contract and can be tested independently",
    ),
    ParallelWorkPackage(
        key="curation_ops_parallel",
        components=("curator_decision_gate", "dashboard_api"),
        mode=ParallelizationMode.PARALLEL_SAFE,
        merge_gate="read_only_candidate_surface",
        rationale="curation and visibility can be built without enabling scheduler mutations",
    ),
    ParallelWorkPackage(
        key="scheduler_last",
        components=("scheduler_daemon",),
        mode=ParallelizationMode.MANUAL_GATE,
        merge_gate="operator_approval_after_state_contract",
        rationale="H24 automation is last because it amplifies every upstream mistake",
    ),
)


def default_operational_plan() -> LabOperationalPlan:
    """Return the canonical v1 control-plane plan."""
    return LabOperationalPlan(
        version=OPERATIONAL_PLAN_VERSION,
        governance_pieces=SOTA_GOVERNANCE_PIECES,
        meta_workflow=META_WORKFLOW_STAGES,
        anchor_jobs=ANCHOR_JOBS,
        missing_components=MISSING_V1_COMPONENTS,
        work_packages=PARALLEL_WORK_PACKAGES,
    )


__all__ = [
    "ANCHOR_JOBS",
    "META_WORKFLOW_STAGES",
    "MISSING_V1_COMPONENTS",
    "OPERATIONAL_PLAN_VERSION",
    "PARALLEL_WORK_PACKAGES",
    "SOTA_GOVERNANCE_PIECES",
    "ComponentState",
    "LabControlPlaneComponent",
    "LabOperationalPlan",
    "MetaWorkflowStage",
    "ParallelWorkPackage",
    "ParallelizationMode",
    "SotaGovernancePiece",
    "default_operational_plan",
]
