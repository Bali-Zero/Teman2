"""Deterministic, side-effect-free selection for the Universal Conductor.

The router consumes a caller-supplied snapshot of endpoint evidence. It never
probes an endpoint, launches a worker, starts a daemon, or retains state.
"""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Mapping
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import TypeGuard

from scripts.conductor.contracts import (
    AuthSurface,
    CandidateRejection,
    CapabilityEvidence,
    Decision,
    DispatchPlan,
    EndpointCandidate,
    EvidenceKind,
    HostObservation,
    Role,
    RoleAssignment,
    RoutingPolicy,
    SessionIdentity,
    TaskClass,
    TaskIntent,
    TaskProfile,
    TaskScore,
)

logger = logging.getLogger(__name__)

_MAX_HEALTH_AGE_DAYS = timedelta.max.days
_SHA256_LOWER_RE = re.compile(r"[0-9a-f]{64}\Z")
_TRUSTED_CAPABILITY_EVIDENCE_KINDS = frozenset(
    {
        EvidenceKind.PROBED,
        EvidenceKind.BENCHMARKED,
        EvidenceKind.PRODUCTION,
    }
)
_CANONICAL_TASK_PROFILE_BINDINGS: Mapping[TaskClass, tuple[str, bool]] = {
    TaskClass.READ_ONLY: ("read_only", False),
    TaskClass.MECHANICAL: ("mechanical", True),
    TaskClass.STANDARD_BUILD: ("standard_build", True),
    TaskClass.HARD_BUILD: ("hard_build", True),
    TaskClass.ARCHITECTURE: ("architecture", False),
    TaskClass.REVIEW: ("review", False),
    TaskClass.PII_LOCAL: ("pii_local", False),
}


class RoutingPolicyError(ValueError):
    """Raised when a routing policy cannot be evaluated deterministically."""


def plan_dispatch(
    *,
    session: SessionIdentity,
    task: TaskIntent,
    candidates: tuple[EndpointCandidate, ...],
    policy: RoutingPolicy,
    generator_family: str | None = None,
) -> DispatchPlan:
    """Return an explainable plan without taking any execution action.

    The opener remains the conductor. For every mutation with an eligible
    builder, the selected builder is a separate child-session role; this
    function never assigns the conductor role to implementation. Review tasks
    must name the family that generated the work so an independent grader can
    be selected.
    """
    resolved_task_profile_hash: str | None = None
    task_profile_hash = "unavailable"

    # SessionIdentity is supplied by an external session bridge.  Dataclass
    # annotations do not defend this boundary after JSON deserialization, and
    # constructing a conductor assignment from an untrusted child would itself
    # grant it a misleading authority receipt.  Validate before any assignment.
    if not _is_session_identity(session):
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(),
            rejections=(),
            reason="session_identity_invalid",
        )
    session_rejection = _session_runtime_rejection(
        session,
        _parse_iso_timestamp(policy.as_of) if _is_routing_policy(policy) else None,
    )
    if session_rejection is not None:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(),
            rejections=(),
            reason=session_rejection,
        )
    conductor_assignment = _conductor_assignment(session)

    if not _is_task_intent(task):
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=(),
            reason="task_intent_invalid",
        )
    if not _is_routing_policy(policy):
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=(),
            reason="routing_policy_invalid",
        )

    # TaskIntent is deliberately a small frozen dataclass rather than a parsing
    # framework object.  Its annotation therefore cannot prevent a deserialized
    # JSON string from arriving here at runtime.  Every branch below relies on
    # identity comparisons against TaskClass, so canonicalize once at the
    # boundary or abstain before any class-specific control can be skipped.
    normalized_task = _normalize_task_class(task)
    if normalized_task is None:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=(),
            reason="task_class_invalid",
        )
    task = normalized_task
    raw_generator_family = generator_family
    generator_family = _normalized_family(generator_family)

    task_rejection = _task_runtime_rejection(task)
    if task_rejection is not None:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=(),
            reason=task_rejection,
        )

    policy_rejection = _policy_runtime_rejection(policy)
    if policy_rejection is not None:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=(),
            reason=policy_rejection,
        )
    resolved_task_profile_hash = _task_profile_hash(policy, task.task_profile_id)
    task_profile_hash = resolved_task_profile_hash or "unavailable"

    if session.role is not Role.CONDUCTOR:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=(),
            reason="session_not_conductor",
        )

    profile = _profile_for(task, policy)
    if profile is None:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=(),
            reason="task_profile_unknown",
        )

    profile_rejection = _task_profile_runtime_rejection(profile)
    if profile_rejection is not None:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=(),
            reason=profile_rejection,
        )

    binding_rejection = _task_profile_binding_rejection(task, profile)
    if binding_rejection is not None:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=(),
            reason=binding_rejection,
        )

    if resolved_task_profile_hash is None:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash="unavailable",
            assignments=(conductor_assignment,),
            rejections=(),
            reason="task_profile_hash_missing",
        )

    if task.task_class is TaskClass.REVIEW and raw_generator_family is None:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=(),
            reason="generator_family_context_required",
        )
    if task.task_class is TaskClass.REVIEW and generator_family is None:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=(),
            reason="grader_family_unknown",
        )

    disallowed_modalities = sorted(
        task.required_modalities - profile.allowed_modalities
    )
    if disallowed_modalities:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=(),
            reason=f"required_modality_not_allowed:{disallowed_modalities[0]}",
        )

    if task.task_class is TaskClass.READ_ONLY:
        as_of, policy_rejection = _policy_clock(policy)
        if policy_rejection is not None:
            return _abstain(
                session=session,
                task=task,
                policy=policy,
                task_profile_hash=task_profile_hash,
                assignments=(conductor_assignment,),
                rejections=(),
                reason=policy_rejection,
            )
        assert as_of is not None
        host_observations, host_policy_rejection = _host_observations(policy, as_of)
        if host_policy_rejection is not None:
            return _abstain(
                session=session,
                task=task,
                policy=policy,
                task_profile_hash=task_profile_hash,
                assignments=(conductor_assignment,),
                rejections=(),
                reason=host_policy_rejection,
            )
        assert host_observations is not None
        retention_host_rejection = _retention_host_rejection(
            session, host_observations, as_of, policy
        )
        if retention_host_rejection is not None:
            return _abstain(
                session=session,
                task=task,
                policy=policy,
                task_profile_hash=task_profile_hash,
                assignments=(conductor_assignment,),
                rejections=(),
                reason=retention_host_rejection,
            )
        return DispatchPlan(
            decision=Decision.ALLOW,
            conductor=session,
            task=task,
            assignments=(conductor_assignment,),
            primary=None,
            fallbacks=(),
            policy_hash=policy.policy_hash,
            task_profile_hash=task_profile_hash,
            capability_index_hash=policy.capability_index_hash,
            selection_reason_codes=("read_only_conductor_retained",),
            rejections=(),
            degraded_reasons=(),
            abstention_reason=None,
            separate_builder_session_required=False,
        )

    as_of, policy_rejection = _policy_clock(policy)
    if policy_rejection is not None:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=(),
            reason=policy_rejection,
        )
    assert as_of is not None
    host_observations, host_policy_rejection = _host_observations(policy, as_of)
    if host_policy_rejection is not None:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=(),
            reason=host_policy_rejection,
        )
    assert host_observations is not None
    candidate_container_rejection = _candidate_container_rejection(candidates)
    if candidate_container_rejection is not None:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=(),
            reason=candidate_container_rejection,
        )

    eligible: list[tuple[EndpointCandidate, TaskScore, str]] = []
    rejections: list[CandidateRejection] = []
    for candidate in sorted(candidates, key=lambda item: item.endpoint_id):
        candidate_runtime_rejection = _candidate_runtime_rejection(candidate)
        if candidate_runtime_rejection is not None:
            rejections.append(
                CandidateRejection(
                    candidate.endpoint_id, (candidate_runtime_rejection,)
                )
            )
            continue
        machine, host_rejection = _placement_for(
            candidate, host_observations, as_of, policy
        )
        rejection = _rejection_for(
            candidate=candidate,
            task=task,
            profile=profile,
            policy=policy,
            as_of=as_of,
            host_rejection=host_rejection,
            generator_family=generator_family,
            task_profile_hash=task_profile_hash,
        )
        if rejection is not None:
            rejections.append(rejection)
            continue
        score = _benchmark_score(candidate, profile, task_profile_hash, as_of, policy)
        if score is None:
            raise RoutingPolicyError(
                "candidate passed benchmark filter without a benchmark score"
            )
        if machine is None:
            raise RoutingPolicyError("candidate without a placement passed the router")
        eligible.append((candidate, score, machine))

    if not eligible:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=tuple(rejections),
            reason="no_eligible_endpoint",
        )

    eligible.sort(key=lambda item: _candidate_sort_key(item[0], item[1]))
    role = _worker_role(task)
    primary_candidate, primary_score, primary_machine = eligible[0]
    primary = _assignment(
        candidate=primary_candidate,
        score=primary_score,
        role=role,
        machine=primary_machine,
        reason_code="selected_primary",
    )
    fallbacks = tuple(
        _assignment(
            candidate=candidate,
            score=score,
            role=role,
            machine=machine,
            reason_code="selected_fallback",
        )
        for candidate, score, machine in eligible[1:]
    )
    separate_session_required = _requires_independent_session(task, profile)
    return DispatchPlan(
        decision=(
            Decision.DELEGATE_REQUIRED if separate_session_required else Decision.ALLOW
        ),
        conductor=session,
        task=task,
        assignments=(conductor_assignment, primary, *fallbacks),
        primary=primary,
        fallbacks=fallbacks,
        policy_hash=policy.policy_hash,
        task_profile_hash=task_profile_hash,
        capability_index_hash=policy.capability_index_hash,
        selection_reason_codes=_selection_reason_codes(
            primary_candidate, primary_score
        ),
        rejections=tuple(rejections),
        degraded_reasons=(),
        abstention_reason=None,
        separate_builder_session_required=separate_session_required,
    )


def _profile_for(task: TaskIntent, policy: RoutingPolicy) -> TaskProfile | None:
    for profile in policy.task_profiles:
        if profile.id == task.task_profile_id:
            return profile
    return None


def _task_profile_hash(policy: RoutingPolicy, profile_id: object) -> str | None:
    """Return a present profile hash only when its runtime shape is trustworthy."""
    hashes = policy.task_profile_hashes
    if not isinstance(hashes, Mapping) or type(profile_id) is not str:
        return None
    try:
        value = hashes.get(profile_id)
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    if type(value) is not str or not value.strip():
        return None
    return value


def _is_nonempty_string(value: object) -> bool:
    """Return whether ``value`` is a non-blank runtime string."""
    return type(value) is str and bool(value.strip())


def _is_finite_number(value: object) -> TypeGuard[int | float]:
    """Return whether ``value`` is a finite numeric scalar, never a boolean."""
    return (
        isinstance(value, (int, float))
        and type(value) is not bool
        and math.isfinite(value)
    )


def _is_session_identity(value: object) -> TypeGuard[SessionIdentity]:
    """Return whether a deserialized public input is a SessionIdentity."""
    return isinstance(value, SessionIdentity)


def _is_task_intent(value: object) -> TypeGuard[TaskIntent]:
    """Return whether a deserialized public input is a TaskIntent."""
    return isinstance(value, TaskIntent)


def _is_routing_policy(value: object) -> TypeGuard[RoutingPolicy]:
    """Return whether a deserialized public input is a RoutingPolicy."""
    return isinstance(value, RoutingPolicy)


def _is_nonnegative_integer(value: object) -> bool:
    return type(value) is int and value >= 0


def _is_positive_integer(value: object) -> bool:
    return type(value) is int and value > 0


def _is_string_frozenset(value: object) -> bool:
    return isinstance(value, frozenset) and all(
        _is_nonempty_string(item) for item in value
    )


def _session_runtime_rejection(
    session: SessionIdentity, as_of: datetime | None
) -> str | None:
    """Validate the session authority chain before producing an assignment."""
    for value, code in (
        (session.session_id, "session_id_invalid"),
        (session.root_session_id, "session_root_session_id_invalid"),
        (session.engine, "session_engine_invalid"),
        (session.model, "session_model_invalid"),
        (session.family, "session_family_invalid"),
        (session.host, "session_host_invalid"),
        (session.repo_head, "session_repo_head_invalid"),
    ):
        if not _is_nonempty_string(value):
            return code
    if session.parent_session_id is not None and not _is_nonempty_string(
        session.parent_session_id
    ):
        return "session_parent_session_id_invalid"
    if not isinstance(session.role, Role):
        return "session_role_invalid"
    if not isinstance(session.repo_root, Path) or not session.repo_root.is_absolute():
        return "session_repo_root_invalid"
    started_at = _parse_iso_timestamp(session.started_at)
    if started_at is None:
        return "session_timestamp_invalid"
    if as_of is not None and started_at > as_of:
        return "session_timestamp_future"
    if session.parent_session_id is not None:
        return (
            "session_child_conductor_forbidden"
            if session.role is Role.CONDUCTOR
            else "session_not_root_conductor"
        )
    if session.session_id != session.root_session_id:
        return "session_root_chain_invalid"
    if session.role is not Role.CONDUCTOR:
        return "session_root_role_invalid"
    return None


def _task_runtime_rejection(task: TaskIntent) -> str | None:
    """Validate untrusted deserialized task fields before policy branching."""
    if not _is_nonempty_string(task.task_id):
        return "task_id_invalid"
    if task.task_class is not None and not isinstance(task.task_class, TaskClass):
        return "task_class_invalid"
    if type(task.gear) is not int or task.gear not in {1, 2, 3}:
        return "task_gear_invalid"
    if type(task.mutation) is not bool:
        return "task_mutation_invalid"
    if type(task.contains_pii) is not bool:
        return "task_contains_pii_invalid"
    if not isinstance(task.files, tuple) or not all(
        _is_nonempty_string(path) for path in task.files
    ):
        return "task_files_invalid"
    if not _is_string_frozenset(task.requires):
        return "task_requires_invalid"
    if not _is_nonempty_string(task.task_profile_id):
        return "task_profile_id_invalid"
    if task.estimated_context_tokens is not None and not _is_positive_integer(
        task.estimated_context_tokens
    ):
        return "task_context_tokens_invalid"
    if not _is_string_frozenset(task.required_modalities):
        return "task_modalities_invalid"
    if not _is_string_frozenset(task.required_tools):
        return "task_tools_invalid"
    return None


def _policy_runtime_rejection(policy: RoutingPolicy) -> str | None:
    """Validate policy control values before any fast path can consume them."""
    if not _is_nonempty_string(policy.policy_hash):
        return "policy_hash_invalid"
    if not _is_nonempty_string(policy.capability_index_hash):
        return "policy_capability_index_hash_invalid"
    if not isinstance(policy.task_profile_hashes, Mapping):
        return "policy_task_profile_hashes_invalid"
    try:
        task_profile_hash_items = tuple(policy.task_profile_hashes.items())
    except (AttributeError, TypeError, ValueError):
        return "policy_task_profile_hashes_invalid"
    if any(
        not _is_nonempty_string(profile_id) or not _is_nonempty_string(profile_hash)
        for profile_id, profile_hash in task_profile_hash_items
    ):
        return "policy_task_profile_hashes_invalid"
    if not isinstance(policy.task_profiles, tuple) or not all(
        isinstance(profile, TaskProfile) for profile in policy.task_profiles
    ):
        return "policy_task_profiles_invalid"
    profile_ids = tuple(profile.id for profile in policy.task_profiles)
    if any(not _is_nonempty_string(profile_id) for profile_id in profile_ids):
        return "policy_task_profiles_invalid"
    if len(set(profile_ids)) != len(profile_ids):
        return "task_profile_duplicate"
    if not _is_nonempty_string(policy.as_of):
        return "policy_timestamp_invalid"
    if not _is_nonnegative_integer(policy.max_health_age_days) or (
        policy.max_health_age_days > _MAX_HEALTH_AGE_DAYS
    ):
        return "policy_max_health_age_invalid"
    if type(policy.require_enforced_mutation) is not bool:
        return "policy_require_enforced_mutation_invalid"
    if type(policy.forbid_paid_anthropic_api) is not bool:
        return "policy_forbid_paid_anthropic_api_invalid"
    if not _is_finite_number(policy.minimum_identity_confidence) or not (
        0 <= policy.minimum_identity_confidence <= 1
    ):
        return "policy_minimum_identity_confidence_invalid"
    return None


def _task_profile_runtime_rejection(profile: TaskProfile) -> str | None:
    """Validate a selected task profile before it influences routing semantics."""
    if not _is_nonempty_string(profile.id):
        return "task_profile_id_invalid"
    if type(profile.mutation) is not bool:
        return "task_profile_mutation_invalid"
    if not _is_nonnegative_integer(profile.minimum_quality_tier):
        return "task_profile_minimum_quality_invalid"
    if profile.minimum_task_score is not None and (
        not _is_finite_number(profile.minimum_task_score)
        or not 0 <= profile.minimum_task_score <= 1
    ):
        return "task_profile_minimum_task_score_invalid"
    if not _is_string_frozenset(profile.required_capabilities):
        return "task_profile_capabilities_invalid"
    if not _is_string_frozenset(profile.allowed_modalities):
        return "task_profile_modalities_invalid"
    if type(profile.pii_policy) is not str or profile.pii_policy not in {
        "context_dependent",
        "forbidden_cloud",
        "local_only",
    }:
        return "task_profile_pii_policy_invalid"
    if (
        (profile.benchmark_id is None) != (profile.benchmark_version is None)
        or (
            profile.benchmark_id is not None
            and not _is_nonempty_string(profile.benchmark_id)
        )
        or (
            profile.benchmark_version is not None
            and not _is_nonempty_string(profile.benchmark_version)
        )
    ):
        return "task_profile_benchmark_contract_invalid"
    if not _is_positive_integer(profile.minimum_sample_count):
        return "task_profile_minimum_sample_count_invalid"
    if profile.maximum_dispersion is not None and (
        not _is_finite_number(profile.maximum_dispersion)
        or not 0 <= profile.maximum_dispersion <= 1
    ):
        return "task_profile_maximum_dispersion_invalid"
    if profile.minimum_context_tokens is not None and not _is_positive_integer(
        profile.minimum_context_tokens
    ):
        return "task_profile_minimum_context_invalid"
    if profile.minimum_output_tokens is not None and not _is_positive_integer(
        profile.minimum_output_tokens
    ):
        return "task_profile_minimum_output_invalid"
    return None


def _candidate_container_rejection(
    candidates: tuple[EndpointCandidate, ...],
) -> str | None:
    """Reject malformed collections before sorting invokes arbitrary values."""
    if not isinstance(candidates, tuple):
        return "candidate_container_invalid"
    if any(not isinstance(candidate, EndpointCandidate) for candidate in candidates):
        return "candidate_container_invalid"
    endpoint_ids = tuple(candidate.endpoint_id for candidate in candidates)
    if any(not _is_nonempty_string(endpoint_id) for endpoint_id in endpoint_ids):
        return "candidate_endpoint_id_invalid"
    if len(set(endpoint_ids)) != len(endpoint_ids):
        return "candidate_endpoint_duplicate"
    return None


def _candidate_runtime_rejection(candidate: EndpointCandidate) -> str | None:
    """Validate fields used by ordering and security gates before candidate selection."""
    for value, code in (
        (candidate.endpoint_id, "candidate_endpoint_id_invalid"),
        (candidate.engine, "candidate_engine_invalid"),
        (candidate.model_card_id, "candidate_model_card_id_invalid"),
        (candidate.model, "candidate_model_invalid"),
        (candidate.family, "candidate_family_invalid"),
        (candidate.model_card_hash, "candidate_model_card_hash_invalid"),
        (candidate.endpoint_profile_hash, "candidate_endpoint_profile_hash_invalid"),
        (
            candidate.capability_snapshot_hash,
            "candidate_capability_snapshot_hash_invalid",
        ),
    ):
        if not _is_nonempty_string(value):
            return code
    if not isinstance(candidate.role, Role):
        return "candidate_role_invalid"
    if not isinstance(candidate.features, tuple):
        return "candidate_features_invalid"
    if not isinstance(candidate.task_scores, tuple):
        return "candidate_task_scores_invalid"
    if type(candidate.healthy) is not bool:
        return "candidate_healthy_invalid"
    if not _is_nonempty_string(candidate.health_observed_at):
        return "candidate_health_timestamp_invalid"
    if (
        not isinstance(candidate.machine_allowlist, tuple)
        or not candidate.machine_allowlist
        or any(not _is_nonempty_string(host) for host in candidate.machine_allowlist)
    ):
        return "candidate_machine_allowlist_invalid"
    for rank, code in (
        (candidate.cost_rank, "candidate_cost_rank_invalid"),
        (candidate.latency_rank, "candidate_latency_rank_invalid"),
        (candidate.quota_pressure_rank, "candidate_quota_pressure_rank_invalid"),
        (candidate.quality_tier, "candidate_quality_tier_invalid"),
    ):
        if not _is_nonnegative_integer(rank):
            return code
    if type(
        candidate.enforcement_mode
    ) is not str or candidate.enforcement_mode not in {
        "enforced",
        "shadow",
        "advisory",
        "advisory_only",
        "manual_only",
        "unmeasured",
    }:
        return "candidate_enforcement_mode_invalid"
    if not _is_finite_number(candidate.identity_confidence) or not (
        0 <= candidate.identity_confidence <= 1
    ):
        return "candidate_identity_confidence_invalid"
    if type(candidate.automated_routing) is not bool:
        return "candidate_automated_routing_invalid"
    if type(candidate.routing_status) is not str:
        return "candidate_routing_status_invalid"
    if type(candidate.uses_paid_anthropic_api) is not bool:
        return "paid_anthropic_usage_invalid"
    return None


def _normalize_task_class(task: TaskIntent) -> TaskIntent | None:
    """Return a TaskIntent with a canonical TaskClass, or fail closed.

    Registry and CLI deserializers may supply one of the exact string values
    declared by TaskClass.  Accept those values, but reject every other runtime
    shape rather than silently falling through the identity-based policy gates.
    """
    raw_task_class = task.task_class
    if isinstance(raw_task_class, TaskClass):
        return task
    if not isinstance(raw_task_class, str):
        return None
    try:
        canonical_task_class = TaskClass(raw_task_class)
    except ValueError:
        return None
    return replace(task, task_class=canonical_task_class)


def _task_profile_binding_rejection(
    task: TaskIntent, profile: TaskProfile
) -> str | None:
    """Reject task/profile bindings that cannot safely retain the conductor.

    The checked-in task profile contract assigns one canonical profile identifier to
    each ``TaskClass``.  The read-only fast path bypasses candidate evaluation, so it
    must additionally prove that neither the request nor the bound profile introduces
    mutation or local-PII requirements that ``SessionIdentity`` cannot attest.
    """
    expected = _CANONICAL_TASK_PROFILE_BINDINGS.get(task.task_class)
    if expected is None:
        return "task_profile_class_mismatch"
    expected_profile_id, expected_mutation = expected

    if task.task_class is TaskClass.READ_ONLY:
        if task.mutation or profile.mutation:
            return "read_only_mutation_contradiction"
        if task.contains_pii or profile.pii_policy == "local_only":
            return "read_only_pii_safety_unproven"

    if task.task_profile_id != expected_profile_id:
        return "task_profile_class_mismatch"
    if task.mutation != expected_mutation or profile.mutation != expected_mutation:
        return "task_profile_mutation_mismatch"
    return None


def _worker_role(task: TaskIntent) -> Role:
    if task.task_class is TaskClass.ARCHITECTURE:
        return Role.ARCHITECT
    if task.task_class is TaskClass.REVIEW:
        return Role.GRADER
    return Role.BUILDER


def _requires_independent_session(task: TaskIntent, profile: TaskProfile) -> bool:
    """Return whether this plan must execute in an independent child session."""
    return (
        task.mutation
        or profile.mutation
        or task.task_class in {TaskClass.ARCHITECTURE, TaskClass.REVIEW}
        or _requires_local_pii(task, profile)
    )


def _conductor_assignment(session: SessionIdentity) -> RoleAssignment:
    return RoleAssignment(
        role=Role.CONDUCTOR,
        engine=session.engine,
        endpoint_id=f"session:{session.session_id}",
        model=session.model,
        family=session.family,
        machine=session.host,
        reason_code="session_origin_conductor",
        model_card_hash="session-origin",
        endpoint_profile_hash="session-origin",
        capability_snapshot_hash="session-origin",
        benchmark_version=None,
        auth_surface=AuthSurface.UNKNOWN,
    )


def _rejection_for(
    *,
    candidate: EndpointCandidate,
    task: TaskIntent,
    profile: TaskProfile,
    policy: RoutingPolicy,
    as_of: datetime,
    host_rejection: str | None,
    generator_family: str | None,
    task_profile_hash: str,
) -> CandidateRejection | None:
    reasons: list[str] = []
    mutation = task.mutation or profile.mutation

    if candidate.model_card_id == candidate.endpoint_id:
        reasons.append("abstract_model_card_not_invocable")
    if not candidate.automated_routing or candidate.routing_status != "eligible":
        reasons.append("endpoint_not_automated")
    auth_surface = _auth_surface(candidate.auth_surface)
    if auth_surface is None:
        reasons.append("auth_surface_invalid")
    elif auth_surface is AuthSurface.UNKNOWN:
        reasons.append("auth_surface_unknown")
    if type(candidate.uses_paid_anthropic_api) is not bool:
        reasons.append("paid_anthropic_usage_invalid")
    elif (
        auth_surface is AuthSurface.ANTHROPIC_PAID_API
        or candidate.uses_paid_anthropic_api
    ):
        reasons.append("paid_anthropic_api_forbidden")
    if task.task_class is TaskClass.REVIEW:
        candidate_family = _normalized_family(candidate.family)
        if candidate_family is None:
            reasons.append("grader_family_unknown")
        elif candidate_family == generator_family:
            reasons.append("generator_family_conflict")
    if not candidate.healthy:
        reasons.append("health_unavailable")
    else:
        reasons.extend(_health_timestamp_rejections(candidate, as_of, policy))
    if host_rejection is not None:
        reasons.append(host_rejection)
    if candidate.identity_confidence < policy.minimum_identity_confidence:
        reasons.append("identity_confidence_insufficient")
    if (
        mutation
        and policy.require_enforced_mutation
        and candidate.enforcement_mode != "enforced"
    ):
        reasons.append("enforcement_not_mutation_capable")

    reasons.extend(_capability_evidence_rejections(candidate, as_of, policy))

    if _requires_local_pii(task, profile) and not (
        auth_surface is AuthSurface.LOCAL_RUNTIME
        and _has_capability(candidate, "local_only")
        and _has_capability(candidate, "pii_safe_local")
    ):
        reasons.append("privacy_ineligible")
    required_context = _maximum_optional_integer(
        task.estimated_context_tokens, profile.minimum_context_tokens
    )
    if required_context is not None:
        context_capacity = _numeric_capability(candidate, "context_tokens")
        if context_capacity is None:
            reasons.append("context_limit_unknown")
        elif context_capacity < required_context:
            reasons.append("context_insufficient")
    if profile.minimum_output_tokens is not None:
        output_capacity = _numeric_capability(candidate, "output_tokens")
        if output_capacity is None:
            reasons.append("output_limit_unknown")
        elif output_capacity < profile.minimum_output_tokens:
            reasons.append("output_insufficient")

    for capability in _required_capabilities(task, profile):
        if not _has_capability(candidate, capability):
            reasons.append(f"missing_capability:{capability}")
    for modality in _required_modalities(task, profile):
        if not _has_capability(candidate, modality):
            reasons.append(f"missing_modality:{modality}")
    if candidate.quality_tier < profile.minimum_quality_tier:
        reasons.append("quality_tier_insufficient")

    # A failed liveness check must not hide the independent benchmark gate.  The
    # resulting abstention explains that static inventory data is insufficient on
    # both dimensions, while capability failures remain concise and actionable.
    if not reasons or any(reason.startswith("health_") for reason in reasons):
        benchmark_reason = _benchmark_rejection(
            candidate, profile, task_profile_hash, as_of, policy
        )
        if benchmark_reason is not None:
            reasons.append(benchmark_reason)
    return (
        CandidateRejection(candidate.endpoint_id, tuple(reasons)) if reasons else None
    )


def _normalized_family(family: str | None) -> str | None:
    if type(family) is not str:
        return None
    normalized = re.sub(r"[^0-9a-z]+", "-", family.casefold()).strip("-")
    return normalized or None


def _auth_surface(value: object) -> AuthSurface | None:
    """Accept only the typed enum at this security-critical boundary.

    Contract dataclasses are intentionally permissive at runtime, so a JSON string
    can otherwise bypass identity comparisons (notably the paid Anthropic ban).
    The registry loader owns canonicalization; the pure router fails closed.
    """
    return value if isinstance(value, AuthSurface) else None


def _policy_clock(policy: RoutingPolicy) -> tuple[datetime | None, str | None]:
    if (
        type(policy.max_health_age_days) is not int
        or policy.max_health_age_days < 0
        or policy.max_health_age_days > _MAX_HEALTH_AGE_DAYS
    ):
        return None, "policy_max_health_age_invalid"
    as_of = _parse_iso_timestamp(policy.as_of)
    if as_of is None:
        return None, "policy_timestamp_invalid"
    return as_of, None


def _host_observations(
    policy: RoutingPolicy,
    as_of: datetime,
) -> tuple[Mapping[str, HostObservation] | None, str | None]:
    raw_observations = policy.host_observations
    if not isinstance(raw_observations, tuple):
        return None, "host_observation_invalid"

    observations: dict[str, HostObservation] = {}
    for observation in raw_observations:
        if not isinstance(observation, HostObservation):
            return None, "host_observation_invalid"
        if not _is_nonempty_string(observation.host):
            return None, "host_observation_host_invalid"
        if type(observation.available) is not bool:
            return None, "host_observation_availability_invalid"
        if observation.host in observations:
            return None, "host_observation_duplicate"
        observed_at = _parse_iso_timestamp(observation.observed_at)
        if observed_at is None:
            return None, "host_observation_timestamp_invalid"
        if observed_at > as_of:
            return None, "host_observation_timestamp_future"
        observations[observation.host] = observation
    return observations, None


def _placement_for(
    candidate: EndpointCandidate,
    observations: Mapping[str, HostObservation],
    as_of: datetime,
    policy: RoutingPolicy,
) -> tuple[str | None, str | None]:
    allowed = tuple(sorted(set(candidate.machine_allowlist)))
    observed = [(host, observations[host]) for host in allowed if host in observations]
    if not observed:
        return None, "host_observation_missing"

    fresh = []
    for host, observation in observed:
        observed_at = _parse_iso_timestamp(observation.observed_at)
        if observed_at is None:
            return None, "host_observation_timestamp_invalid"
        if (as_of - observed_at).total_seconds() <= timedelta(
            days=policy.max_health_age_days
        ).total_seconds():
            fresh.append((host, observation))
    if not fresh:
        return None, "host_observation_stale"
    available = [host for host, observation in fresh if observation.available]
    if not available:
        return None, "host_unavailable"
    return min(available), None


def _retention_host_rejection(
    session: SessionIdentity,
    observations: Mapping[str, HostObservation],
    as_of: datetime,
    policy: RoutingPolicy,
) -> str | None:
    """Require a fresh, available observation for the conductor's own host."""
    observation = observations.get(session.host)
    if observation is None:
        return "host_observation_missing"

    observed_at = _parse_iso_timestamp(observation.observed_at)
    if observed_at is None:
        return "host_observation_timestamp_invalid"
    if observed_at > as_of:
        return "host_observation_timestamp_future"
    if as_of - observed_at > timedelta(days=policy.max_health_age_days):
        return "host_observation_stale"
    if not observation.available:
        return "host_unavailable"
    return None


def _health_timestamp_rejections(
    candidate: EndpointCandidate, as_of: datetime, policy: RoutingPolicy
) -> tuple[str, ...]:
    observed = _parse_iso_timestamp(candidate.health_observed_at)
    if observed is None:
        return ("health_timestamp_invalid",)
    if observed > as_of:
        return ("health_timestamp_future", "health_clock_skew")
    if as_of - observed > timedelta(days=policy.max_health_age_days):
        return ("health_stale",)
    return ()


def _requires_local_pii(task: TaskIntent, profile: TaskProfile) -> bool:
    return (
        task.contains_pii
        or task.task_class is TaskClass.PII_LOCAL
        or profile.pii_policy == "local_only"
    )


def _capability_evidence_rejections(
    candidate: EndpointCandidate,
    as_of: datetime,
    policy: RoutingPolicy,
) -> tuple[str, ...]:
    """Return deterministic freshness failures for every capability assertion."""
    reasons: set[str] = set()
    for evidence in candidate.features:
        if not isinstance(evidence, CapabilityEvidence):
            reasons.add("capability_evidence_invalid")
            continue
        if not _is_nonempty_string(evidence.capability) or not _is_nonempty_string(
            evidence.evidence_ref
        ):
            reasons.add("capability_evidence_invalid")
            continue
        if not isinstance(evidence.kind, EvidenceKind):
            reasons.add("capability_evidence_kind_invalid")
            continue
        if not _is_finite_number(evidence.confidence) or not (
            0 <= evidence.confidence <= 1
        ):
            reasons.add("capability_confidence_invalid")
            continue
        observed_at = _parse_iso_timestamp(evidence.observed_at)
        if observed_at is None:
            reasons.add("capability_timestamp_invalid")
            continue
        if observed_at > as_of:
            reasons.add("capability_timestamp_future")
            continue

        expires_at = None
        if evidence.expires_at is not None:
            expires_at = _parse_iso_timestamp(evidence.expires_at)
            if expires_at is None or expires_at < observed_at:
                reasons.add("capability_timestamp_invalid")
                continue
            if expires_at <= as_of:
                reasons.add("capability_stale")
                continue

        if as_of - observed_at > timedelta(days=policy.max_health_age_days):
            reasons.add("capability_stale")

    values_by_capability: dict[str, set[bool]] = {}
    counts_by_capability: dict[str, int] = {}
    for evidence in candidate.features:
        if (
            isinstance(evidence, CapabilityEvidence)
            and _is_nonempty_string(evidence.capability)
            and type(evidence.value) is bool
        ):
            counts_by_capability[evidence.capability] = (
                counts_by_capability.get(evidence.capability, 0) + 1
            )
            values_by_capability.setdefault(evidence.capability, set()).add(
                evidence.value
            )
        elif isinstance(evidence, CapabilityEvidence) and _is_nonempty_string(
            evidence.capability
        ):
            counts_by_capability[evidence.capability] = (
                counts_by_capability.get(evidence.capability, 0) + 1
            )
    if any(count > 1 for count in counts_by_capability.values()):
        reasons.add("capability_evidence_duplicate")
    if any(len(values) > 1 for values in values_by_capability.values()):
        reasons.add("capability_evidence_conflict")

    return tuple(sorted(reasons, key=_capability_failure_rank))


def _capability_failure_rank(reason: str) -> tuple[int, str]:
    priority = {
        "capability_evidence_invalid": 0,
        "capability_evidence_kind_invalid": 1,
        "capability_confidence_invalid": 2,
        "capability_timestamp_invalid": 3,
        "capability_timestamp_future": 4,
        "capability_stale": 5,
        "capability_evidence_duplicate": 6,
        "capability_evidence_conflict": 7,
    }
    return priority.get(reason, 99), reason


def _parse_iso_timestamp(value: str) -> datetime | None:
    if type(value) is not str or not value:
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return datetime.combine(
                date.fromisoformat(value), time.min, tzinfo=timezone.utc
            )
        normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
    except (OSError, OverflowError, TypeError, ValueError):
        return None
    try:
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None


def _required_capabilities(task: TaskIntent, profile: TaskProfile) -> tuple[str, ...]:
    return tuple(
        sorted(
            set(profile.required_capabilities)
            | set(task.requires)
            | set(task.required_tools)
        )
    )


def _required_modalities(task: TaskIntent, profile: TaskProfile) -> tuple[str, ...]:
    del profile
    return tuple(sorted(task.required_modalities))


def _has_capability(candidate: EndpointCandidate, capability_id: str) -> bool:
    matching = tuple(
        evidence
        for evidence in candidate.features
        if isinstance(evidence, CapabilityEvidence)
        and evidence.capability == capability_id
    )
    if any(evidence.value is False for evidence in matching):
        return False
    return any(
        evidence.value is True
        and evidence.kind in _TRUSTED_CAPABILITY_EVIDENCE_KINDS
        and _is_finite_number(evidence.confidence)
        and 0 < evidence.confidence <= 1
        for evidence in matching
    )


def _numeric_capability(candidate: EndpointCandidate, capability_id: str) -> int | None:
    values: list[int] = []
    for evidence in candidate.features:
        if (
            not isinstance(evidence, CapabilityEvidence)
            or evidence.capability != capability_id
            or evidence.kind not in _TRUSTED_CAPABILITY_EVIDENCE_KINDS
            or not _is_finite_number(evidence.confidence)
            or not 0 < evidence.confidence <= 1
        ):
            continue
        if type(evidence.value) is int and evidence.value >= 0:
            values.append(evidence.value)
    return max(values) if values else None


def _maximum_optional_integer(*values: int | None) -> int | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _benchmark_rejection(
    candidate: EndpointCandidate,
    profile: TaskProfile,
    task_profile_hash: str,
    as_of: datetime,
    policy: RoutingPolicy,
) -> str | None:
    relevant = _profile_scores(candidate, profile)
    if not relevant:
        return "benchmark_unmeasured"
    failures = tuple(
        rejection
        for score in relevant
        if (
            rejection := _score_rejection(
                candidate, score, profile, task_profile_hash, as_of, policy
            )
        )
        is not None
    )
    if len(failures) == len(relevant):
        return min(failures, key=_benchmark_failure_rank)
    return None


def _benchmark_score(
    candidate: EndpointCandidate,
    profile: TaskProfile,
    task_profile_hash: str,
    as_of: datetime,
    policy: RoutingPolicy,
) -> TaskScore | None:
    relevant = [
        score
        for score in _profile_scores(candidate, profile)
        if _score_rejection(candidate, score, profile, task_profile_hash, as_of, policy)
        is None
    ]
    if not relevant:
        return None
    return min(
        relevant,
        key=lambda score: (
            -_effective_score(score),
            score.benchmark_id or "",
            score.benchmark_version or "",
        ),
    )


def _profile_scores(
    candidate: EndpointCandidate, profile: TaskProfile
) -> tuple[TaskScore, ...]:
    return tuple(
        score
        for score in candidate.task_scores
        if isinstance(score, TaskScore)
        and type(score.task_profile_id) is str
        and score.task_profile_id == profile.id
    )


def _score_rejection(
    candidate: EndpointCandidate,
    score: TaskScore,
    profile: TaskProfile,
    task_profile_hash: str,
    as_of: datetime,
    policy: RoutingPolicy,
) -> str | None:
    if not isinstance(score.evidence_kind, EvidenceKind):
        return "benchmark_evidence_kind_invalid"
    if score.evidence_kind is not EvidenceKind.BENCHMARKED:
        return "benchmark_unmeasured"
    if not _is_nonempty_string(score.task_profile_id):
        return "benchmark_evidence_incomplete"
    if score.endpoint_profile_hash != candidate.endpoint_profile_hash:
        return "benchmark_endpoint_profile_mismatch"
    if score.task_profile_hash != task_profile_hash:
        return "benchmark_task_profile_mismatch"
    score_value = score.score
    if not _is_finite_number(score_value) or not 0 <= score_value <= 1:
        return "benchmark_evidence_incomplete"
    conservative_score = score.conservative_score
    if conservative_score is not None and (
        not _is_finite_number(conservative_score)
        or not 0 <= conservative_score <= 1
        or conservative_score > score_value
    ):
        return "benchmark_evidence_incomplete"
    if not isinstance(score.benchmark_id, str) or not score.benchmark_id.strip():
        return "benchmark_evidence_incomplete"
    if (
        not isinstance(score.benchmark_version, str)
        or not score.benchmark_version.strip()
    ):
        return "benchmark_evidence_incomplete"
    if (
        not isinstance(score.sample_count, int)
        or isinstance(score.sample_count, bool)
        or score.sample_count <= 0
    ):
        return "benchmark_evidence_incomplete"
    if profile.benchmark_id is not None and score.benchmark_id != profile.benchmark_id:
        return "benchmark_id_mismatch"
    if (
        profile.benchmark_version is not None
        and score.benchmark_version != profile.benchmark_version
    ):
        return "benchmark_version_mismatch"
    if score.sample_count < profile.minimum_sample_count:
        return "benchmark_low_sample"
    if profile.maximum_dispersion is not None:
        dispersion = score.dispersion
        if not _is_finite_number(dispersion) or not 0 <= dispersion <= 1:
            return "benchmark_dispersion_unmeasured"
        if dispersion > profile.maximum_dispersion:
            return "benchmark_high_variance"
    if (
        not isinstance(score.sample_hashes, tuple)
        or len(score.sample_hashes) != score.sample_count
        or any(
            type(sample_hash) is not str
            or _SHA256_LOWER_RE.fullmatch(sample_hash) is None
            for sample_hash in score.sample_hashes
        )
        or len(set(score.sample_hashes)) != score.sample_count
        or not _is_nonempty_string(score.scorer_id)
        or not _is_nonempty_string(score.scorer_version)
    ):
        return "benchmark_evidence_incomplete"
    measured_at = _parse_iso_timestamp(score.observed_at or "")
    if measured_at is None:
        return "benchmark_timestamp_invalid"
    if measured_at > as_of:
        return "benchmark_timestamp_future"
    if as_of - measured_at > timedelta(days=policy.max_health_age_days):
        return "benchmark_stale"
    if score.expires_at is not None:
        expires_at = _parse_iso_timestamp(score.expires_at)
        if expires_at is None or expires_at < measured_at:
            return "benchmark_timestamp_invalid"
        if expires_at <= as_of:
            return "benchmark_stale"
    if (
        profile.minimum_task_score is not None
        and _effective_score(score) < profile.minimum_task_score
    ):
        return "benchmark_below_floor"
    return None


def _effective_score(score: TaskScore) -> float:
    conservative_score = score.conservative_score
    if _is_finite_number(conservative_score):
        return float(conservative_score)
    score_value = score.score
    return float(score_value) if _is_finite_number(score_value) else -1.0


def _benchmark_failure_rank(reason: str) -> tuple[int, str]:
    priority = {
        "benchmark_evidence_kind_invalid": 0,
        "benchmark_endpoint_profile_mismatch": 1,
        "benchmark_task_profile_mismatch": 2,
        "benchmark_id_mismatch": 3,
        "benchmark_version_mismatch": 4,
        "benchmark_low_sample": 5,
        "benchmark_high_variance": 6,
        "benchmark_dispersion_unmeasured": 7,
        "benchmark_evidence_incomplete": 8,
        "benchmark_timestamp_invalid": 9,
        "benchmark_timestamp_future": 10,
        "benchmark_stale": 11,
        "benchmark_below_floor": 12,
    }
    return priority.get(reason, 99), reason


def _candidate_sort_key(
    candidate: EndpointCandidate, score: TaskScore
) -> tuple[float, int, int, int, str]:
    return (
        -_effective_score(score),
        candidate.cost_rank,
        candidate.quota_pressure_rank,
        candidate.latency_rank,
        candidate.endpoint_id,
    )


def _assignment(
    *,
    candidate: EndpointCandidate,
    score: TaskScore,
    role: Role,
    machine: str,
    reason_code: str,
) -> RoleAssignment:
    return RoleAssignment(
        role=role,
        engine=candidate.engine,
        endpoint_id=candidate.endpoint_id,
        model=candidate.model,
        family=candidate.family,
        machine=machine,
        reason_code=reason_code,
        model_card_hash=candidate.model_card_hash,
        endpoint_profile_hash=candidate.endpoint_profile_hash,
        capability_snapshot_hash=candidate.capability_snapshot_hash,
        benchmark_version=score.benchmark_version,
        auth_surface=candidate.auth_surface,
    )


def _selection_reason_codes(
    candidate: EndpointCandidate, score: TaskScore
) -> tuple[str, ...]:
    return (
        f"benchmark_score:{_effective_score(score):.3f}",
        f"cost_rank:{candidate.cost_rank}",
        f"quota_pressure_rank:{candidate.quota_pressure_rank}",
        f"latency_rank:{candidate.latency_rank}",
        "stable_endpoint_id",
    )


def _abstain(
    *,
    session: SessionIdentity,
    task: TaskIntent,
    policy: RoutingPolicy,
    task_profile_hash: str,
    assignments: tuple[RoleAssignment, ...],
    rejections: tuple[CandidateRejection, ...],
    reason: str,
) -> DispatchPlan:
    task_id = _safe_contract_string(task, "task_id", "unavailable")
    policy_hash = _safe_contract_string(policy, "policy_hash", "unavailable")
    capability_index_hash = _safe_contract_string(
        policy, "capability_index_hash", "unavailable"
    )
    logger.info("Conductor abstained from routing task %s: %s", task_id, reason)
    return DispatchPlan(
        decision=Decision.ABSTAIN,
        conductor=session,
        task=task,
        assignments=assignments,
        primary=None,
        fallbacks=(),
        policy_hash=policy_hash,
        task_profile_hash=task_profile_hash,
        capability_index_hash=capability_index_hash,
        selection_reason_codes=(reason,),
        rejections=rejections,
        degraded_reasons=(reason,),
        abstention_reason=reason,
        separate_builder_session_required=False,
    )


def _safe_contract_string(value: object, attribute: str, fallback: str) -> str:
    """Read a public receipt field without dereferencing malformed input."""
    try:
        field = getattr(value, attribute)
    except (AttributeError, TypeError):
        return fallback
    return field if _is_nonempty_string(field) else fallback
