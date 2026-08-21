"""Deterministic, side-effect-free selection for the Universal Conductor.

The router consumes a caller-supplied snapshot of endpoint evidence. It never
probes an endpoint, launches a worker, starts a daemon, or retains state.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import logging
import re
from typing import Mapping

from scripts.conductor.contracts import (
    AuthSurface,
    CandidateRejection,
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
    conductor_assignment = _conductor_assignment(session)
    task_profile_hash = policy.task_profile_hashes.get(
        task.task_profile_id, "unavailable"
    )
    generator_family = _normalized_family(generator_family)

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

    if task.mutation and task.task_class is TaskClass.READ_ONLY:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=(),
            reason="read_only_mutation_contradiction",
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

    if task.task_class is TaskClass.REVIEW and generator_family is None:
        return _abstain(
            session=session,
            task=task,
            policy=policy,
            task_profile_hash=task_profile_hash,
            assignments=(conductor_assignment,),
            rejections=(),
            reason="generator_family_context_required",
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
    eligible: list[tuple[EndpointCandidate, TaskScore, str]] = []
    rejections: list[CandidateRejection] = []
    for candidate in sorted(candidates, key=lambda item: item.endpoint_id):
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
        )
        if rejection is not None:
            rejections.append(rejection)
            continue
        score = _benchmark_score(candidate, profile, as_of)
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
    mutation = task.mutation or profile.mutation
    return DispatchPlan(
        decision=Decision.DELEGATE_REQUIRED if mutation else Decision.ALLOW,
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
        separate_builder_session_required=mutation,
    )


def _profile_for(task: TaskIntent, policy: RoutingPolicy) -> TaskProfile | None:
    for profile in policy.task_profiles:
        if profile.id == task.task_profile_id:
            return profile
    return None


def _worker_role(task: TaskIntent) -> Role:
    if task.task_class is TaskClass.ARCHITECTURE:
        return Role.ARCHITECT
    if task.task_class is TaskClass.REVIEW:
        return Role.GRADER
    return Role.BUILDER


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
) -> CandidateRejection | None:
    reasons: list[str] = []
    mutation = task.mutation or profile.mutation

    if candidate.model_card_id == candidate.endpoint_id:
        reasons.append("abstract_model_card_not_invocable")
    if not candidate.automated_routing or candidate.routing_status != "eligible":
        reasons.append("endpoint_not_automated")
    if candidate.auth_surface is AuthSurface.UNKNOWN:
        reasons.append("auth_surface_unknown")
    if (
        candidate.auth_surface is AuthSurface.ANTHROPIC_PAID_API
        or candidate.uses_paid_anthropic_api
    ):
        reasons.append("paid_anthropic_api_forbidden")
    if (
        task.task_class is TaskClass.REVIEW
        and generator_family is not None
        and candidate.family.strip() == generator_family
    ):
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

    if (task.contains_pii or task.task_class is TaskClass.PII_LOCAL) and not (
        _has_capability(candidate, "local_only")
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
        benchmark_reason = _benchmark_rejection(candidate, profile, as_of)
        if benchmark_reason is not None:
            reasons.append(benchmark_reason)
    return (
        CandidateRejection(candidate.endpoint_id, tuple(reasons)) if reasons else None
    )


def _normalized_family(family: str | None) -> str | None:
    if not isinstance(family, str):
        return None
    normalized = family.strip()
    return normalized or None


def _policy_clock(policy: RoutingPolicy) -> tuple[datetime | None, str | None]:
    if (
        not isinstance(policy.max_health_age_days, int)
        or isinstance(policy.max_health_age_days, bool)
        or policy.max_health_age_days < 0
    ):
        return None, "policy_max_health_age_invalid"
    as_of = _parse_iso_timestamp(policy.as_of)
    if as_of is None:
        return None, "policy_timestamp_invalid"
    return as_of, None


def _host_observations(
    policy: RoutingPolicy, as_of: datetime
) -> tuple[Mapping[str, HostObservation] | None, str | None]:
    observations: dict[str, HostObservation] = {}
    for observation in policy.host_observations:
        if not isinstance(observation.host, str) or not observation.host:
            return None, "host_observation_host_invalid"
        if not isinstance(observation.available, bool):
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


def _parse_iso_timestamp(value: str) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return datetime.combine(
                date.fromisoformat(value), time.min, tzinfo=timezone.utc
            )
        normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


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
    return any(
        evidence.capability == capability_id
        and evidence.value is True
        and evidence.kind is not EvidenceKind.UNMEASURED
        and evidence.confidence > 0
        for evidence in candidate.features
    )


def _numeric_capability(candidate: EndpointCandidate, capability_id: str) -> int | None:
    values: list[int] = []
    for evidence in candidate.features:
        if (
            evidence.capability != capability_id
            or evidence.kind is EvidenceKind.UNMEASURED
        ):
            continue
        if isinstance(evidence.value, int) and not isinstance(evidence.value, bool):
            values.append(evidence.value)
    return max(values) if values else None


def _maximum_optional_integer(*values: int | None) -> int | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _benchmark_rejection(
    candidate: EndpointCandidate, profile: TaskProfile, as_of: datetime
) -> str | None:
    relevant = _profile_scores(candidate, profile)
    if not relevant:
        return "benchmark_unmeasured"
    failures = tuple(
        rejection
        for score in relevant
        if (rejection := _score_rejection(score, profile, as_of)) is not None
    )
    if len(failures) == len(relevant):
        return min(failures, key=_benchmark_failure_rank)
    return None


def _benchmark_score(
    candidate: EndpointCandidate, profile: TaskProfile, as_of: datetime
) -> TaskScore | None:
    relevant = [
        score
        for score in _profile_scores(candidate, profile)
        if _score_rejection(score, profile, as_of) is None
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
        if score.task_profile_id == profile.id
        and score.score is not None
        and score.evidence_kind is EvidenceKind.BENCHMARKED
        and score.benchmark_id
        and score.benchmark_version
        and score.sample_count > 0
    )


def _score_rejection(
    score: TaskScore, profile: TaskProfile, as_of: datetime
) -> str | None:
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
        if score.dispersion is None:
            return "benchmark_dispersion_unmeasured"
        if score.dispersion > profile.maximum_dispersion:
            return "benchmark_high_variance"
    versioned_contract = (
        profile.benchmark_id is not None or profile.benchmark_version is not None
    )
    if versioned_contract:
        if (
            len(score.sample_hashes) != score.sample_count
            or len(set(score.sample_hashes)) != score.sample_count
            or not score.scorer_id
            or not score.scorer_version
        ):
            return "benchmark_evidence_incomplete"
        measured_at = _parse_iso_timestamp(score.observed_at or "")
        expires_at = _parse_iso_timestamp(score.expires_at or "")
        if measured_at is None or expires_at is None:
            return "benchmark_timestamp_invalid"
        if measured_at > as_of:
            return "benchmark_timestamp_future"
        if expires_at < as_of:
            return "benchmark_stale"
    if (
        profile.minimum_task_score is not None
        and _effective_score(score) < profile.minimum_task_score
    ):
        return "benchmark_below_floor"
    return None


def _effective_score(score: TaskScore) -> float:
    if score.conservative_score is not None:
        return score.conservative_score
    return score.score if score.score is not None else -1.0


def _benchmark_failure_rank(reason: str) -> tuple[int, str]:
    priority = {
        "benchmark_id_mismatch": 0,
        "benchmark_version_mismatch": 1,
        "benchmark_low_sample": 2,
        "benchmark_high_variance": 3,
        "benchmark_dispersion_unmeasured": 4,
        "benchmark_evidence_incomplete": 5,
        "benchmark_timestamp_invalid": 6,
        "benchmark_timestamp_future": 7,
        "benchmark_stale": 8,
        "benchmark_below_floor": 9,
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
    logger.info("Conductor abstained from routing task %s: %s", task.task_id, reason)
    return DispatchPlan(
        decision=Decision.ABSTAIN,
        conductor=session,
        task=task,
        assignments=assignments,
        primary=None,
        fallbacks=(),
        policy_hash=policy.policy_hash,
        task_profile_hash=task_profile_hash,
        capability_index_hash=policy.capability_index_hash,
        selection_reason_codes=(reason,),
        rejections=rejections,
        degraded_reasons=(reason,),
        abstention_reason=reason,
        separate_builder_session_required=False,
    )
