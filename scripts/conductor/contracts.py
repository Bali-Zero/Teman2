"""Typed, immutable contracts for deterministic Conductor routing.

The module is deliberately standard-library only so hooks and tests can import it
without the backend virtual environment.  It is a session-local decision library:
it never performs I/O, probes an endpoint, or launches a worker.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal, Mapping


class Role(StrEnum):
    """A role in a session-local control-plane plan."""

    CONDUCTOR = "conductor"
    ARCHITECT = "architect"
    BUILDER = "builder"
    GRADER = "grader"


class TaskClass(StrEnum):
    """The deterministic task classes defined by the conductor design."""

    READ_ONLY = "read_only"
    MECHANICAL = "mechanical"
    STANDARD_BUILD = "standard_build"
    HARD_BUILD = "hard_build"
    ARCHITECTURE = "architecture"
    REVIEW = "review"
    PII_LOCAL = "pii_local"


class Decision(StrEnum):
    """An outcome of pure planning, including a visible abstention."""

    ALLOW = "allow"
    DELEGATE_REQUIRED = "delegate_required"
    BLOCK = "block"
    DEGRADED = "degraded"
    ABSTAIN = "abstain"


class EvidenceKind(StrEnum):
    """Provenance of a capability or score; unknown data is never positive proof."""

    DECLARED = "declared"
    PROBED = "probed"
    BENCHMARKED = "benchmarked"
    PRODUCTION = "production"
    UNMEASURED = "unmeasured"


class AuthSurface(StrEnum):
    """Concrete authentication/billing surface asserted by an EndpointProfile.

    ``UNKNOWN`` is intentionally a real registry value rather than an omitted
    field: callers can see that authority was not established, and the router
    must reject it rather than inferring safety from a provider or harness name.
    """

    UNKNOWN = "unknown"
    LOCAL_RUNTIME = "local_runtime"
    ANTHROPIC_OAUTH_SUBSCRIPTION = "anthropic_oauth_subscription"
    ANTHROPIC_PAID_API = "anthropic_paid_api"
    OPENAI_CHATGPT_SUBSCRIPTION = "openai_chatgpt_subscription"
    GOOGLE_OAUTH_SUBSCRIPTION = "google_oauth_subscription"
    MANUAL_GUI = "manual_gui"
    OTHER_PROVIDER_API = "other_provider_api"


@dataclass(frozen=True)
class SessionIdentity:
    """Origin of an interactive session; the starter remains its conductor."""

    session_id: str
    root_session_id: str
    parent_session_id: str | None
    role: Role
    engine: Literal["claude", "codex", "agy", "kimi", "unknown"] | str
    model: str
    family: str
    host: str
    repo_root: Path
    repo_head: str
    started_at: str


@dataclass(frozen=True)
class TaskIntent:
    """A typed task request supplied by the conductor or deterministic classifier."""

    task_id: str
    task_class: TaskClass
    gear: Literal[1, 2, 3]
    mutation: bool
    files: tuple[str, ...]
    requires: frozenset[str]
    task_profile_id: str
    estimated_context_tokens: int | None
    required_modalities: frozenset[str]
    required_tools: frozenset[str]
    contains_pii: bool


# TaskRequest is the public, plain-language name used by callers.  TaskIntent is kept
# as the canonical name from the approved control-plane contract.
TaskRequest = TaskIntent


@dataclass(frozen=True)
class CapabilityEvidence:
    """A single capability assertion with its evidence class and freshness metadata."""

    capability: str
    value: bool | int | float | str | None
    kind: EvidenceKind
    evidence_ref: str
    observed_at: str
    expires_at: str | None
    confidence: float


@dataclass(frozen=True)
class TaskScore:
    """A task-profile-specific score; only a benchmarked score opens a load-bearing lane."""

    task_profile_id: str
    score: float | None
    benchmark_id: str | None
    benchmark_version: str | None
    sample_count: int
    observed_at: str | None
    evidence_kind: EvidenceKind = EvidenceKind.UNMEASURED
    conservative_score: float | None = None
    sample_hashes: tuple[str, ...] = ()
    scorer_id: str | None = None
    scorer_version: str | None = None
    expires_at: str | None = None
    dispersion: float | None = None


@dataclass(frozen=True)
class EndpointCandidate:
    """A concrete invocation surface assembled from a model card and endpoint profile."""

    endpoint_id: str
    engine: str
    model_card_id: str
    model: str
    family: str
    role: Role
    features: tuple[CapabilityEvidence, ...]
    task_scores: tuple[TaskScore, ...]
    healthy: bool
    health_observed_at: str
    machine_allowlist: tuple[str, ...]
    cost_rank: int
    latency_rank: int
    quota_pressure_rank: int
    quality_tier: int
    enforcement_mode: Literal[
        "enforced", "shadow", "advisory", "advisory_only", "manual_only", "unmeasured"
    ]
    identity_confidence: float
    model_card_hash: str
    endpoint_profile_hash: str
    capability_snapshot_hash: str
    automated_routing: bool = True
    routing_status: str = "eligible"
    uses_paid_anthropic_api: bool = False
    auth_surface: AuthSurface = AuthSurface.UNKNOWN


@dataclass(frozen=True)
class TaskProfile:
    """The task-shape floor loaded from MIR task profiles plus reviewed calibration."""

    id: str
    mutation: bool
    minimum_quality_tier: int
    minimum_task_score: float | None
    required_capabilities: frozenset[str]
    allowed_modalities: frozenset[str]
    pii_policy: Literal["context_dependent", "forbidden_cloud", "local_only"] | str
    benchmark_id: str | None = None
    benchmark_version: str | None = None
    minimum_sample_count: int = 1
    maximum_dispersion: float | None = None
    minimum_context_tokens: int | None = None
    minimum_output_tokens: int | None = None


@dataclass(frozen=True)
class HostObservation:
    """A caller-provided, timestamped availability observation for one fleet host.

    The router consumes this as evidence only; it never attempts a host probe or
    assumes that the conductor's local host is available for a selected endpoint.
    """

    host: str
    available: bool
    observed_at: str


@dataclass(frozen=True)
class RoutingPolicy:
    """All policy inputs needed by the pure router, including its explicit clock."""

    policy_hash: str
    task_profile_hashes: Mapping[str, str]
    capability_index_hash: str
    task_profiles: tuple[TaskProfile, ...]
    as_of: str
    max_health_age_days: int
    host_observations: tuple[HostObservation, ...] = ()
    require_enforced_mutation: bool = True
    minimum_identity_confidence: float = 1.0
    forbid_paid_anthropic_api: bool = True


@dataclass(frozen=True)
class RoleAssignment:
    """A selected concrete endpoint for a role; never an abstract model card."""

    role: Role
    engine: str
    endpoint_id: str
    model: str
    family: str
    machine: str
    reason_code: str
    model_card_hash: str
    endpoint_profile_hash: str
    capability_snapshot_hash: str
    benchmark_version: str | None
    auth_surface: AuthSurface = AuthSurface.UNKNOWN


@dataclass(frozen=True)
class CandidateRejection:
    """Why one endpoint could not be selected, in stable endpoint order."""

    endpoint_id: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class DispatchPlan:
    """A pure, explainable selection plan with a primary endpoint and fallbacks."""

    decision: Decision
    conductor: SessionIdentity
    task: TaskIntent
    assignments: tuple[RoleAssignment, ...]
    primary: RoleAssignment | None
    fallbacks: tuple[RoleAssignment, ...]
    policy_hash: str
    task_profile_hash: str
    capability_index_hash: str
    selection_reason_codes: tuple[str, ...]
    rejections: tuple[CandidateRejection, ...]
    degraded_reasons: tuple[str, ...]
    abstention_reason: str | None
    separate_builder_session_required: bool


# SelectionPlan is a clearer public synonym for integrations that do not need the
# broader dispatch lifecycle yet.
SelectionPlan = DispatchPlan
