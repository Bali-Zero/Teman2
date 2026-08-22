"""Unit tests for the deterministic Universal Conductor router."""

from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path
from typing import cast

from scripts.conductor.contracts import (
    AuthSurface,
    CapabilityEvidence,
    Decision,
    EndpointCandidate,
    EvidenceKind,
    HostObservation,
    Role,
    RoutingPolicy,
    SessionIdentity,
    TaskClass,
    TaskIntent,
    TaskProfile,
    TaskScore,
)
from scripts.conductor.model_registry import AbstractModelCardError, load_registry
from scripts.conductor import router
from scripts.conductor.router import plan_dispatch

AS_OF = "2026-08-21"
BENCHMARK_SAMPLES = tuple(f"{index:064x}" for index in range(1, 11))


def capability(
    name: str,
    *,
    kind: EvidenceKind = EvidenceKind.PROBED,
    value: bool | float | str | None = True,
) -> CapabilityEvidence:
    """Build a positive or negative capability observation for a test endpoint."""
    return CapabilityEvidence(
        capability=name,
        value=value,
        kind=kind,
        evidence_ref=f"test:{name}",
        observed_at=AS_OF,
        expires_at=None,
        confidence=1.0,
    )


def candidate(
    endpoint_id: str,
    *,
    model: str,
    family: str,
    score: float | None,
    capabilities: tuple[str, ...] = ("language", "coding"),
    hosts: tuple[str, ...] = ("pro",),
    cost_rank: int = 1,
    quota_rank: int = 1,
    latency_rank: int = 1,
    healthy: bool = True,
    enforcement_mode: str = "enforced",
    automated_routing: bool = True,
    context_limit: int | None = 32_000,
    auth_surface: AuthSurface = AuthSurface.OPENAI_CHATGPT_SUBSCRIPTION,
    uses_paid_anthropic_api: bool | None = None,
) -> EndpointCandidate:
    """Build an independently evidenced concrete endpoint fixture."""
    task_scores = ()
    if score is not None:
        task_scores = (
            TaskScore(
                task_profile_id="mechanical",
                score=score,
                benchmark_id="synthetic-routing-suite",
                benchmark_version="v1",
                sample_count=10,
                observed_at=AS_OF,
                evidence_kind=EvidenceKind.BENCHMARKED,
                sample_hashes=BENCHMARK_SAMPLES,
                scorer_id="synthetic-scorer",
                scorer_version="v1",
                endpoint_profile_hash=f"endpoint-{endpoint_id}",
                task_profile_hash="profile-mechanical",
            ),
            TaskScore(
                task_profile_id="standard_build",
                score=score,
                benchmark_id="synthetic-routing-suite",
                benchmark_version="v1",
                sample_count=10,
                observed_at=AS_OF,
                evidence_kind=EvidenceKind.BENCHMARKED,
                sample_hashes=BENCHMARK_SAMPLES,
                scorer_id="synthetic-scorer",
                scorer_version="v1",
                endpoint_profile_hash=f"endpoint-{endpoint_id}",
                task_profile_hash="profile-standard",
            ),
        )
    return EndpointCandidate(
        endpoint_id=endpoint_id,
        engine="codex",
        model_card_id=f"card-{endpoint_id}",
        model=model,
        family=family,
        role=Role.BUILDER,
        features=tuple(capability(name) for name in capabilities)
        + (
            ()
            if context_limit is None
            else (capability("context_tokens", value=context_limit),)
        ),
        task_scores=task_scores,
        healthy=healthy,
        health_observed_at=AS_OF,
        machine_allowlist=hosts,
        cost_rank=cost_rank,
        latency_rank=latency_rank,
        quota_pressure_rank=quota_rank,
        quality_tier=3,
        enforcement_mode=enforcement_mode,
        identity_confidence=1.0,
        model_card_hash=f"model-{endpoint_id}",
        endpoint_profile_hash=f"endpoint-{endpoint_id}",
        capability_snapshot_hash=f"snapshot-{endpoint_id}",
        automated_routing=automated_routing,
        routing_status="eligible",
        uses_paid_anthropic_api=(
            auth_surface is AuthSurface.ANTHROPIC_PAID_API
            if uses_paid_anthropic_api is None
            else uses_paid_anthropic_api
        ),
        auth_surface=auth_surface,
    )


def session() -> SessionIdentity:
    """Return a Sol-origin session that must remain the conductor."""
    return SessionIdentity(
        session_id="sol-root-session",
        root_session_id="sol-root-session",
        parent_session_id=None,
        role=Role.CONDUCTOR,
        engine="codex",
        model="gpt-5.6-sol",
        family="gpt-5.6",
        host="pro",
        repo_root=Path("/repo"),
        repo_head="abc123",
        started_at=AS_OF,
    )


def task(task_class: TaskClass, profile_id: str) -> TaskIntent:
    """Return a task with a concrete MIR profile binding."""
    mutation = task_class in {
        TaskClass.MECHANICAL,
        TaskClass.STANDARD_BUILD,
        TaskClass.HARD_BUILD,
    }
    return TaskIntent(
        task_id=f"task-{profile_id}",
        task_class=task_class,
        gear=2,
        mutation=mutation,
        files=("scripts/conductor/runtime.py",),
        requires=frozenset({"coding"}) if mutation else frozenset(),
        task_profile_id=profile_id,
        estimated_context_tokens=8_000,
        required_modalities=frozenset({"language"}),
        required_tools=frozenset(),
        contains_pii=task_class is TaskClass.PII_LOCAL,
    )


def policy() -> RoutingPolicy:
    """Return a fully explicit deterministic routing policy for fixtures."""
    return RoutingPolicy(
        policy_hash="policy-test-v1",
        task_profile_hashes={
            "mechanical": "profile-mechanical",
            "standard_build": "profile-standard",
        },
        capability_index_hash="index-test-v1",
        task_profiles=(
            TaskProfile(
                id="mechanical",
                mutation=True,
                minimum_quality_tier=1,
                minimum_task_score=0.70,
                required_capabilities=frozenset({"coding"}),
                allowed_modalities=frozenset({"language"}),
                pii_policy="forbidden_cloud",
            ),
            TaskProfile(
                id="standard_build",
                mutation=True,
                minimum_quality_tier=2,
                minimum_task_score=0.80,
                required_capabilities=frozenset({"coding"}),
                allowed_modalities=frozenset({"language"}),
                pii_policy="forbidden_cloud",
            ),
        ),
        as_of=AS_OF,
        max_health_age_days=1,
        host_observations=(
            HostObservation(host="pro", available=True, observed_at=AS_OF),
        ),
        require_enforced_mutation=True,
    )


def live_profile_policy(profile_id: str) -> tuple[TaskProfile, RoutingPolicy]:
    """Load one checked-in task profile with a deterministic test clock."""
    registry = load_registry(Path(__file__).resolve().parents[2])
    profile = registry.profile(profile_id)
    return profile, replace(
        policy(),
        task_profile_hashes={profile.id: f"live-profile-{profile.id}"},
        task_profiles=(profile,),
    )


def live_non_mutating_policy(profile_id: str) -> tuple[TaskProfile, RoutingPolicy]:
    """Load one checked-in non-mutating profile with a deterministic test clock."""
    profile, live_policy = live_profile_policy(profile_id)
    assert not profile.mutation
    return profile, live_policy


def read_only_task() -> TaskIntent:
    """Return a read-only task bound to the checked-in canonical profile."""
    return task(TaskClass.READ_ONLY, TaskClass.READ_ONLY.value)


def read_only_policy() -> RoutingPolicy:
    """Load the checked-in canonical read-only profile into fixture policy."""
    return live_non_mutating_policy(TaskClass.READ_ONLY.value)[1]


def live_profile_candidate(profile: TaskProfile) -> EndpointCandidate:
    """Build an eligible concrete endpoint for a checked-in live task profile."""
    base = candidate(
        f"eligible-{profile.id}",
        model="eligible-model",
        family="independent-family",
        score=None,
        capabilities=(
            "coding",
            "language",
            "reasoning_control",
            "vision",
            "local_only",
            "pii_safe_local",
        ),
        context_limit=32_768,
        auth_surface=(
            AuthSurface.LOCAL_RUNTIME
            if profile.pii_policy == "local_only"
            else AuthSurface.OPENAI_CHATGPT_SUBSCRIPTION
        ),
    )
    return replace(
        base,
        features=base.features + (capability("output_tokens", value=8_192),),
        task_scores=(
            TaskScore(
                task_profile_id=profile.id,
                score=0.95,
                benchmark_id=profile.benchmark_id,
                benchmark_version=profile.benchmark_version,
                sample_count=5,
                observed_at=AS_OF,
                evidence_kind=EvidenceKind.BENCHMARKED,
                sample_hashes=tuple(f"{index:064x}" for index in range(1, 6)),
                scorer_id="test-scorer",
                scorer_version="v1",
                expires_at="2026-08-22",
                dispersion=0.01,
                endpoint_profile_hash=base.endpoint_profile_hash,
                task_profile_hash=f"live-profile-{profile.id}",
            ),
        ),
        quality_tier=3,
    )


class ConductorRouterTest(unittest.TestCase):
    def test_read_only_class_cannot_smuggle_a_mutation_into_root_allowance(
        self,
    ) -> None:
        contradictory = replace(
            read_only_task(),
            mutation=True,
            files=("pkg/mutated.py",),
        )

        plan = plan_dispatch(
            session=session(),
            task=contradictory,
            candidates=(),
            policy=read_only_policy(),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.abstention_reason, "read_only_mutation_contradiction")
        self.assertIsNone(plan.primary)
        self.assertFalse(plan.separate_builder_session_required)

    def test_read_only_rejects_a_live_mutation_profile_before_retention(self) -> None:
        profile, live_policy = live_profile_policy("mechanical")

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.READ_ONLY, profile.id),
            candidates=(),
            policy=live_policy,
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.abstention_reason, "read_only_mutation_contradiction")

    def test_task_profile_class_binding_rejects_live_profile_confusion(self) -> None:
        registry = load_registry(Path(__file__).resolve().parents[2])
        profiles = tuple(registry.profile(task_class.value) for task_class in TaskClass)
        fixture_policy = policy()

        for task_class in TaskClass:
            for profile in profiles:
                if profile.id == task_class.value:
                    continue
                with self.subTest(task_class=task_class, profile_id=profile.id):
                    live_policy = replace(
                        fixture_policy,
                        task_profile_hashes={profile.id: f"live-profile-{profile.id}"},
                        task_profiles=(profile,),
                    )
                    plan = plan_dispatch(
                        session=session(),
                        task=task(task_class, profile.id),
                        candidates=(),
                        policy=live_policy,
                        generator_family="generator-family",
                    )
                    expected_reason = "task_profile_class_mismatch"
                    if task_class is TaskClass.READ_ONLY:
                        if profile.mutation:
                            expected_reason = "read_only_mutation_contradiction"
                        elif profile.pii_policy == "local_only":
                            expected_reason = "read_only_pii_safety_unproven"

                    self.assertEqual(plan.decision, Decision.ABSTAIN)
                    self.assertEqual(plan.abstention_reason, expected_reason)

    def test_live_canonical_task_profile_bindings_route_all_task_classes(self) -> None:
        registry = load_registry(Path(__file__).resolve().parents[2])
        fixture_policy = policy()

        for task_class in TaskClass:
            with self.subTest(task_class=task_class):
                profile = registry.profile(task_class.value)
                live_policy = replace(
                    fixture_policy,
                    task_profile_hashes={profile.id: f"live-profile-{profile.id}"},
                    task_profiles=(profile,),
                )
                is_read_only = task_class is TaskClass.READ_ONLY
                plan = plan_dispatch(
                    session=session(),
                    task=task(task_class, profile.id),
                    candidates=()
                    if is_read_only
                    else (live_profile_candidate(profile),),
                    policy=live_policy,
                    generator_family=(
                        "generator-family" if task_class is TaskClass.REVIEW else None
                    ),
                )

                self.assertEqual(
                    plan.decision,
                    Decision.ALLOW if is_read_only else Decision.DELEGATE_REQUIRED,
                )
                self.assertEqual(
                    plan.separate_builder_session_required, not is_read_only
                )

    def test_task_profile_mutation_contract_rejects_tampered_live_bindings(
        self,
    ) -> None:
        registry = load_registry(Path(__file__).resolve().parents[2])
        fixture_policy = policy()

        for task_class in TaskClass:
            with self.subTest(task_class=task_class):
                profile = registry.profile(task_class.value)
                tampered_profile = replace(profile, mutation=not profile.mutation)
                live_policy = replace(
                    fixture_policy,
                    task_profile_hashes={profile.id: f"live-profile-{profile.id}"},
                    task_profiles=(tampered_profile,),
                )
                plan = plan_dispatch(
                    session=session(),
                    task=task(task_class, profile.id),
                    candidates=(),
                    policy=live_policy,
                    generator_family="generator-family",
                )

                self.assertEqual(plan.decision, Decision.ABSTAIN)
                self.assertEqual(
                    plan.abstention_reason,
                    (
                        "read_only_mutation_contradiction"
                        if task_class is TaskClass.READ_ONLY
                        else "task_profile_mutation_mismatch"
                    ),
                )

    def test_task_mutation_contract_rejects_tampered_live_bindings(self) -> None:
        registry = load_registry(Path(__file__).resolve().parents[2])
        fixture_policy = policy()

        for task_class in TaskClass:
            with self.subTest(task_class=task_class):
                profile = registry.profile(task_class.value)
                live_policy = replace(
                    fixture_policy,
                    task_profile_hashes={profile.id: f"live-profile-{profile.id}"},
                    task_profiles=(profile,),
                )
                plan = plan_dispatch(
                    session=session(),
                    task=replace(
                        task(task_class, profile.id), mutation=not profile.mutation
                    ),
                    candidates=(),
                    policy=live_policy,
                    generator_family="generator-family",
                )

                self.assertEqual(plan.decision, Decision.ABSTAIN)
                self.assertEqual(
                    plan.abstention_reason,
                    (
                        "read_only_mutation_contradiction"
                        if task_class is TaskClass.READ_ONLY
                        else "task_profile_mutation_mismatch"
                    ),
                )

    def test_read_only_abstains_without_provable_local_pii_safety(self) -> None:
        pii_profile, pii_policy = live_non_mutating_policy("pii_local")
        pii_profile_plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.READ_ONLY, pii_profile.id),
            candidates=(),
            policy=pii_policy,
        )
        pii_task_plan = plan_dispatch(
            session=session(),
            task=replace(read_only_task(), contains_pii=True),
            candidates=(),
            policy=read_only_policy(),
        )

        self.assertEqual(pii_profile_plan.decision, Decision.ABSTAIN)
        self.assertEqual(
            pii_profile_plan.abstention_reason, "read_only_pii_safety_unproven"
        )
        self.assertEqual(pii_task_plan.decision, Decision.ABSTAIN)
        self.assertEqual(
            pii_task_plan.abstention_reason, "read_only_pii_safety_unproven"
        )

    def test_read_only_requires_valid_policy_and_host_evidence(self) -> None:
        base_policy = read_only_policy()
        cases = (
            (
                "malformed_policy_timestamp",
                replace(base_policy, as_of="not-an-iso-timestamp"),
                "policy_timestamp_invalid",
            ),
            (
                "invalid_max_health_age",
                replace(base_policy, max_health_age_days=-1),
                "policy_max_health_age_invalid",
            ),
            (
                "malformed_host_timestamp",
                replace(
                    base_policy,
                    host_observations=(
                        HostObservation(
                            host="pro",
                            available=True,
                            observed_at="not-an-iso-timestamp",
                        ),
                    ),
                ),
                "host_observation_timestamp_invalid",
            ),
            (
                "stale_host_evidence",
                replace(
                    base_policy,
                    host_observations=(
                        HostObservation(
                            host="pro",
                            available=True,
                            observed_at="2026-08-19",
                        ),
                    ),
                ),
                "host_observation_stale",
            ),
            (
                "missing_host_evidence",
                replace(base_policy, host_observations=()),
                "host_observation_missing",
            ),
        )

        for name, invalid_policy, reason in cases:
            with self.subTest(name=name):
                plan = plan_dispatch(
                    session=session(),
                    task=read_only_task(),
                    candidates=(),
                    policy=invalid_policy,
                )

                self.assertEqual(plan.decision, Decision.ABSTAIN)
                self.assertEqual(plan.abstention_reason, reason)

    def test_read_only_allows_with_valid_policy_and_host_evidence(self) -> None:
        plan = plan_dispatch(
            session=session(),
            task=read_only_task(),
            candidates=(),
            policy=read_only_policy(),
        )

        self.assertEqual(plan.decision, Decision.ALLOW)
        self.assertEqual(plan.selection_reason_codes, ("read_only_conductor_retained",))
        self.assertIsNone(plan.abstention_reason)

    def test_read_only_requires_its_own_host_observation(self) -> None:
        plan = plan_dispatch(
            session=session(),
            task=read_only_task(),
            candidates=(),
            policy=replace(
                read_only_policy(),
                host_observations=(
                    HostObservation(
                        host="mini-pro2", available=True, observed_at=AS_OF
                    ),
                ),
            ),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.abstention_reason, "host_observation_missing")

    def test_read_only_rejects_unavailable_session_host(self) -> None:
        plan = plan_dispatch(
            session=session(),
            task=read_only_task(),
            candidates=(),
            policy=replace(
                read_only_policy(),
                host_observations=(
                    HostObservation(
                        host="mini-pro2", available=True, observed_at=AS_OF
                    ),
                    HostObservation(host="pro", available=False, observed_at=AS_OF),
                ),
            ),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.abstention_reason, "host_unavailable")

    def test_read_only_accepts_matching_available_session_host(self) -> None:
        plan = plan_dispatch(
            session=session(),
            task=read_only_task(),
            candidates=(),
            policy=replace(
                read_only_policy(),
                host_observations=(
                    HostObservation(
                        host="mini-pro2", available=False, observed_at=AS_OF
                    ),
                    HostObservation(host="pro", available=True, observed_at=AS_OF),
                ),
            ),
        )

        self.assertEqual(plan.decision, Decision.ALLOW)
        self.assertEqual(plan.selection_reason_codes, ("read_only_conductor_retained",))

    def test_read_only_rejects_stale_session_host_even_with_fresh_peer(self) -> None:
        plan = plan_dispatch(
            session=session(),
            task=read_only_task(),
            candidates=(),
            policy=replace(
                read_only_policy(),
                host_observations=(
                    HostObservation(
                        host="mini-pro2", available=True, observed_at=AS_OF
                    ),
                    HostObservation(
                        host="pro", available=True, observed_at="2026-08-19"
                    ),
                ),
            ),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.abstention_reason, "host_observation_stale")

    def test_live_architecture_profile_requires_independent_architect(self) -> None:
        profile, live_policy = live_non_mutating_policy("architecture")
        architecture_task = task(TaskClass.ARCHITECTURE, profile.id)

        plan = plan_dispatch(
            session=session(),
            task=architecture_task,
            candidates=(live_profile_candidate(profile),),
            policy=live_policy,
        )

        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertTrue(plan.separate_builder_session_required)
        self.assertEqual(plan.primary.role, Role.ARCHITECT)

    def test_live_review_profile_requires_independent_grader(self) -> None:
        profile, live_policy = live_non_mutating_policy("review")
        review_task = task(TaskClass.REVIEW, profile.id)

        plan = plan_dispatch(
            session=session(),
            task=review_task,
            candidates=(live_profile_candidate(profile),),
            policy=live_policy,
            generator_family="generator-family",
        )

        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertTrue(plan.separate_builder_session_required)
        self.assertEqual(plan.primary.role, Role.GRADER)

    def test_live_pii_local_profile_requires_an_independent_local_session(self) -> None:
        profile, live_policy = live_non_mutating_policy("pii_local")
        pii_task = task(TaskClass.PII_LOCAL, profile.id)

        plan = plan_dispatch(
            session=session(),
            task=pii_task,
            candidates=(live_profile_candidate(profile),),
            policy=live_policy,
        )

        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertTrue(plan.separate_builder_session_required)
        self.assertEqual(plan.primary.role, Role.BUILDER)

    def test_sol_delegates_mechanical_work_to_luna_and_keeps_conductor_role(
        self,
    ) -> None:
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(
                candidate(
                    "terra",
                    model="gpt-5.6-terra",
                    family="gpt-5.6",
                    score=0.90,
                    cost_rank=2,
                ),
                candidate(
                    "luna",
                    model="gpt-5.6-luna",
                    family="gpt-5.6",
                    score=0.90,
                    cost_rank=1,
                ),
            ),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(plan.conductor.session_id, "sol-root-session")
        self.assertEqual(plan.primary.endpoint_id, "luna")
        self.assertEqual(plan.primary.role, Role.BUILDER)
        self.assertEqual(plan.fallbacks[0].endpoint_id, "terra")
        self.assertTrue(plan.separate_builder_session_required)

    def test_sol_delegates_standard_work_to_terra(self) -> None:
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.STANDARD_BUILD, "standard_build"),
            candidates=(
                candidate(
                    "luna",
                    model="gpt-5.6-luna",
                    family="gpt-5.6",
                    score=0.79,
                    cost_rank=1,
                ),
                candidate(
                    "terra",
                    model="gpt-5.6-terra",
                    family="gpt-5.6",
                    score=0.88,
                    cost_rank=2,
                ),
            ),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(plan.primary.endpoint_id, "terra")
        self.assertIn("benchmark_score:0.880", plan.selection_reason_codes)

    def test_unbenchmarked_capability_cannot_enter_load_bearing_lane(self) -> None:
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(
                candidate(
                    "declared-only", model="candidate", family="test", score=None
                ),
            ),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.rejections[0].reason_codes, ("benchmark_unmeasured",))

    def test_duplicate_valid_benchmark_selection_identity_cannot_win_routing(
        self,
    ) -> None:
        duplicated = candidate(
            "duplicated-evidence", model="candidate", family="test", score=0.80
        )
        duplicated_score = next(
            score
            for score in duplicated.task_scores
            if score.task_profile_id == "mechanical"
        )
        honest = candidate(
            "honest-evidence", model="candidate", family="test", score=0.90
        )

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(
                replace(
                    duplicated,
                    task_scores=(
                        duplicated_score,
                        replace(duplicated_score, score=0.99),
                    ),
                ),
                honest,
            ),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(plan.primary.endpoint_id, "honest-evidence")
        self.assertEqual(
            plan.rejections[0].reason_codes,
            ("benchmark_selection_identity_duplicate",),
        )

    def test_distinct_valid_benchmark_selection_identities_remain_routable(
        self,
    ) -> None:
        evidenced = candidate(
            "versioned-evidence", model="candidate", family="test", score=0.80
        )
        original_score = next(
            score
            for score in evidenced.task_scores
            if score.task_profile_id == "mechanical"
        )

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(
                replace(
                    evidenced,
                    task_scores=(
                        original_score,
                        replace(
                            original_score,
                            benchmark_version="v2",
                            score=0.99,
                        ),
                    ),
                ),
            ),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(plan.primary.endpoint_id, "versioned-evidence")
        self.assertEqual(plan.primary.benchmark_version, "v2")

    def test_unhealthy_endpoint_is_not_an_available_builder(self) -> None:
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(
                candidate(
                    "offline",
                    model="candidate",
                    family="test",
                    score=0.95,
                    healthy=False,
                ),
            ),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.rejections[0].reason_codes, ("health_unavailable",))

    def test_host_and_capability_constraints_are_explicit_rejections(self) -> None:
        no_coding = candidate(
            "missing-coding",
            model="candidate",
            family="test",
            score=0.95,
            capabilities=("language",),
        )
        mini_only = candidate(
            "mini-only",
            model="candidate",
            family="test",
            score=0.95,
            hosts=("mini-pro2",),
        )
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(no_coding, mini_only),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        rejection_map = {
            rejection.endpoint_id: rejection.reason_codes
            for rejection in plan.rejections
        }
        self.assertEqual(
            rejection_map["missing-coding"], ("missing_capability:coding",)
        )
        self.assertEqual(rejection_map["mini-only"], ("host_observation_missing",))

    def test_capability_mismatch_and_no_candidates_abstain_without_fallback(
        self,
    ) -> None:
        vision_task = replace(
            task(TaskClass.MECHANICAL, "mechanical"),
            required_modalities=frozenset({"vision"}),
        )
        vision_profile = replace(
            policy().task_profiles[0],
            allowed_modalities=frozenset({"language", "vision"}),
        )
        vision_policy = replace(
            policy(), task_profiles=(vision_profile, *policy().task_profiles[1:])
        )
        plan = plan_dispatch(
            session=session(),
            task=vision_task,
            candidates=(
                candidate("code-only", model="candidate", family="test", score=0.95),
            ),
            policy=vision_policy,
        )
        empty_plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.rejections[0].reason_codes, ("missing_modality:vision",))
        self.assertEqual(empty_plan.decision, Decision.ABSTAIN)
        self.assertEqual(empty_plan.abstention_reason, "no_eligible_endpoint")
        self.assertEqual(empty_plan.fallbacks, ())

    def test_equal_candidates_have_a_stable_endpoint_id_order(self) -> None:
        candidates = (
            candidate("zeta", model="zeta", family="test", score=0.90),
            candidate("alpha", model="alpha", family="test", score=0.90),
            candidate("middle", model="middle", family="test", score=0.90),
        )

        first = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=candidates,
            policy=policy(),
        )
        second = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=tuple(reversed(candidates)),
            policy=policy(),
        )

        self.assertEqual(first.primary.endpoint_id, "alpha")
        self.assertEqual(
            [item.endpoint_id for item in first.fallbacks], ["middle", "zeta"]
        )
        self.assertEqual(first.primary, second.primary)
        self.assertEqual(first.fallbacks, second.fallbacks)

    def test_paid_anthropic_api_is_never_selected(self) -> None:
        paid = candidate(
            "paid-anthropic",
            model="claude-opus",
            family="claude",
            score=0.99,
            auth_surface=AuthSurface.ANTHROPIC_PAID_API,
            uses_paid_anthropic_api=False,
        )
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(paid,),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(
            plan.rejections[0].reason_codes, ("paid_anthropic_api_forbidden",)
        )

    def test_paid_anthropic_usage_signal_rejects_inconsistent_auth_surface(
        self,
    ) -> None:
        inconsistent = candidate(
            "inconsistent-paid-anthropic",
            model="candidate",
            family="test",
            score=0.99,
            auth_surface=AuthSurface.OPENAI_CHATGPT_SUBSCRIPTION,
            uses_paid_anthropic_api=True,
        )

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(inconsistent,),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(
            plan.rejections[0].reason_codes, ("paid_anthropic_api_forbidden",)
        )

    def test_semantic_endpoint_ineligibility_is_not_reopened_by_false_values(
        self,
    ) -> None:
        base = candidate(
            "semantic-ineligible", model="candidate", family="test", score=0.95
        )
        cases = (
            (
                "automated_routing_false",
                replace(base, automated_routing=False),
            ),
            (
                "routing_status_not_eligible",
                replace(base, routing_status="suspended"),
            ),
        )

        for name, ineligible in cases:
            with self.subTest(name=name):
                plan = plan_dispatch(
                    session=session(),
                    task=task(TaskClass.MECHANICAL, "mechanical"),
                    candidates=(ineligible,),
                    policy=policy(),
                )

                self.assertEqual(plan.decision, Decision.ABSTAIN)
                self.assertEqual(
                    plan.rejections[0].reason_codes, ("endpoint_not_automated",)
                )

    def test_mutation_enforcement_policy_controls_shadow_and_advisory_endpoints(
        self,
    ) -> None:
        base = candidate(
            "mutation-enforcement", model="candidate", family="test", score=0.95
        )
        cases = (
            ("shadow_required", "shadow", True, Decision.ABSTAIN),
            ("advisory_required", "advisory", True, Decision.ABSTAIN),
            ("shadow_optional", "shadow", False, Decision.DELEGATE_REQUIRED),
            ("advisory_optional", "advisory", False, Decision.DELEGATE_REQUIRED),
        )

        for name, enforcement_mode, requires_enforcement, expected_decision in cases:
            with self.subTest(name=name):
                plan = plan_dispatch(
                    session=session(),
                    task=task(TaskClass.MECHANICAL, "mechanical"),
                    candidates=(replace(base, enforcement_mode=enforcement_mode),),
                    policy=replace(
                        policy(),
                        require_enforced_mutation=requires_enforcement,
                    ),
                )

                self.assertEqual(plan.decision, expected_decision)
                if requires_enforcement:
                    self.assertEqual(
                        plan.rejections[0].reason_codes,
                        ("enforcement_not_mutation_capable",),
                    )
                else:
                    self.assertEqual(plan.primary.endpoint_id, "mutation-enforcement")

    def test_paid_anthropic_hard_ban_ignores_compatibility_policy_switch(
        self,
    ) -> None:
        cases = (
            (
                "paid_auth_surface",
                candidate(
                    "paid-auth-surface",
                    model="claude-opus",
                    family="claude",
                    score=0.99,
                    auth_surface=AuthSurface.ANTHROPIC_PAID_API,
                    uses_paid_anthropic_api=False,
                ),
            ),
            (
                "paid_usage_signal",
                candidate(
                    "paid-usage-signal",
                    model="candidate",
                    family="test",
                    score=0.99,
                    uses_paid_anthropic_api=True,
                ),
            ),
        )

        for name, paid in cases:
            with self.subTest(name=name):
                plan = plan_dispatch(
                    session=session(),
                    task=task(TaskClass.MECHANICAL, "mechanical"),
                    candidates=(paid,),
                    policy=replace(policy(), forbid_paid_anthropic_api=False),
                )

                self.assertEqual(plan.decision, Decision.ABSTAIN)
                self.assertEqual(
                    plan.rejections[0].reason_codes,
                    ("paid_anthropic_api_forbidden",),
                )

    def test_local_only_profile_requires_local_candidates_without_task_pii(
        self,
    ) -> None:
        local_profile = replace(
            policy().task_profiles[0],
            pii_policy="local_only",
            required_capabilities=frozenset({"coding", "local_only", "pii_safe_local"}),
        )
        local_policy = replace(
            policy(), task_profiles=(local_profile, *policy().task_profiles[1:])
        )
        cloud = candidate("cloud", model="cloud", family="test", score=0.99)
        local = candidate(
            "local",
            model="local",
            family="test",
            score=0.90,
            capabilities=("language", "coding", "local_only", "pii_safe_local"),
            auth_surface=AuthSurface.LOCAL_RUNTIME,
        )

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(cloud, local),
            policy=local_policy,
        )

        self.assertFalse(plan.task.contains_pii)
        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(plan.primary.endpoint_id, "local")
        self.assertEqual(
            {
                rejection.endpoint_id: rejection.reason_codes
                for rejection in plan.rejections
            }["cloud"],
            (
                "privacy_ineligible",
                "missing_capability:local_only",
                "missing_capability:pii_safe_local",
            ),
        )

    def test_non_local_only_profile_does_not_require_local_candidates_without_pii(
        self,
    ) -> None:
        cloud = candidate("cloud", model="cloud", family="test", score=0.99)

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(cloud,),
            policy=policy(),
        )

        self.assertFalse(plan.task.contains_pii)
        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(plan.primary.endpoint_id, "cloud")

    def test_capability_evidence_freshness_rejects_invalid_or_expired_evidence(
        self,
    ) -> None:
        base = candidate("evidence", model="candidate", family="test", score=0.95)
        cases = (
            (
                "expired",
                replace(
                    base.features[0],
                    observed_at="2026-08-20",
                    expires_at="2026-08-20",
                ),
                "capability_stale",
            ),
            (
                "future_observation",
                replace(base.features[0], observed_at="2026-08-22T00:00:00Z"),
                "capability_timestamp_future",
            ),
            (
                "stale_observation",
                replace(base.features[0], observed_at="2026-08-19"),
                "capability_stale",
            ),
            (
                "malformed_observation",
                replace(base.features[0], observed_at="not-an-iso-timestamp"),
                "capability_timestamp_invalid",
            ),
            (
                "malformed_expiry",
                replace(base.features[0], expires_at="not-an-iso-timestamp"),
                "capability_timestamp_invalid",
            ),
            (
                "inverted_interval",
                replace(
                    base.features[0],
                    observed_at="2026-08-20",
                    expires_at="2026-08-19",
                ),
                "capability_timestamp_invalid",
            ),
        )

        for name, evidence, reason in cases:
            with self.subTest(name=name):
                plan = plan_dispatch(
                    session=session(),
                    task=task(TaskClass.MECHANICAL, "mechanical"),
                    candidates=(
                        replace(base, features=(evidence, *base.features[1:])),
                    ),
                    policy=policy(),
                )

                self.assertEqual(plan.decision, Decision.ABSTAIN)
                self.assertEqual(plan.rejections[0].reason_codes, (reason,))

    def test_current_capability_evidence_remains_eligible(self) -> None:
        base = candidate("current", model="candidate", family="test", score=0.95)
        current = replace(base.features[0], expires_at="2026-08-22")

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(replace(base, features=(current, *base.features[1:])),),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(plan.primary.endpoint_id, "current")

    def test_malformed_policy_and_host_structures_abstain_without_exceptions(
        self,
    ) -> None:
        base_policy = policy()
        invalid_max_age_cases = (-1, 10**100, "1", 1.5, True)
        for max_age in invalid_max_age_cases:
            with self.subTest(max_age=max_age):
                plan = plan_dispatch(
                    session=session(),
                    task=task(TaskClass.MECHANICAL, "mechanical"),
                    candidates=(),
                    policy=replace(base_policy, max_health_age_days=max_age),
                )

                self.assertEqual(plan.decision, Decision.ABSTAIN)
                self.assertEqual(
                    plan.abstention_reason, "policy_max_health_age_invalid"
                )

        malformed_host_cases = (
            None,
            "pro",
            [HostObservation(host="pro", available=True, observed_at=AS_OF)],
            (object(),),
            ({"host": "pro", "available": True, "observed_at": AS_OF},),
        )
        for observations in malformed_host_cases:
            with self.subTest(host_observations=repr(observations)):
                plan = plan_dispatch(
                    session=session(),
                    task=task(TaskClass.MECHANICAL, "mechanical"),
                    candidates=(),
                    policy=replace(base_policy, host_observations=observations),
                )

                self.assertEqual(plan.decision, Decision.ABSTAIN)
                self.assertEqual(plan.abstention_reason, "host_observation_invalid")

        valid = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(
                candidate("valid", model="candidate", family="test", score=0.95),
            ),
            policy=base_policy,
        )
        self.assertEqual(valid.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(valid.primary.endpoint_id, "valid")

    def test_review_routes_to_a_different_generator_family(self) -> None:
        profile, live_policy = live_non_mutating_policy("review")
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.REVIEW, profile.id),
            candidates=(
                replace(
                    live_profile_candidate(profile),
                    endpoint_id="independent-grader",
                    family="independent-family",
                ),
            ),
            policy=live_policy,
            generator_family="gpt-5.6",
        )

        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(plan.primary.role, Role.GRADER)
        self.assertEqual(plan.primary.endpoint_id, "independent-grader")

    def test_deserialized_review_task_class_keeps_grader_and_family_gates(self) -> None:
        profile, live_policy = live_non_mutating_policy("review")
        deserialized = replace(
            task(TaskClass.REVIEW, profile.id),
            task_class=cast(TaskClass, "review"),
        )

        eligible = plan_dispatch(
            session=session(),
            task=deserialized,
            candidates=(
                replace(
                    live_profile_candidate(profile),
                    endpoint_id="independent-grader",
                    family="independent-family",
                ),
            ),
            policy=live_policy,
            generator_family="gpt-5.6",
        )
        same_family = plan_dispatch(
            session=session(),
            task=deserialized,
            candidates=(
                replace(
                    live_profile_candidate(profile),
                    endpoint_id="same-family-grader",
                    family="gpt-5.6",
                ),
            ),
            policy=live_policy,
            generator_family="gpt-5.6",
        )

        self.assertEqual(eligible.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(eligible.task.task_class, TaskClass.REVIEW)
        self.assertEqual(eligible.primary.role, Role.GRADER)
        self.assertTrue(eligible.separate_builder_session_required)
        self.assertEqual(same_family.decision, Decision.ABSTAIN)
        self.assertEqual(
            same_family.rejections[0].reason_codes, ("generator_family_conflict",)
        )

    def test_deserialized_architecture_task_class_keeps_architect_gate(self) -> None:
        profile, live_policy = live_non_mutating_policy("architecture")
        deserialized = replace(
            task(TaskClass.ARCHITECTURE, profile.id),
            task_class=cast(TaskClass, "architecture"),
        )

        plan = plan_dispatch(
            session=session(),
            task=deserialized,
            candidates=(live_profile_candidate(profile),),
            policy=live_policy,
        )

        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(plan.task.task_class, TaskClass.ARCHITECTURE)
        self.assertEqual(plan.primary.role, Role.ARCHITECT)
        self.assertTrue(plan.separate_builder_session_required)

    def test_deserialized_pii_local_task_class_keeps_local_pii_gate(self) -> None:
        profile, live_policy = live_non_mutating_policy("pii_local")
        deserialized = replace(
            task(TaskClass.PII_LOCAL, profile.id),
            task_class=cast(TaskClass, "pii_local"),
        )
        non_local = candidate(
            "non-local",
            model="cloud-model",
            family="cloud-family",
            score=None,
            capabilities=("language", "reasoning_control"),
        )

        plan = plan_dispatch(
            session=session(),
            task=deserialized,
            candidates=(non_local, live_profile_candidate(profile)),
            policy=live_policy,
        )

        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(plan.task.task_class, TaskClass.PII_LOCAL)
        self.assertEqual(plan.primary.endpoint_id, f"eligible-{profile.id}")
        self.assertTrue(plan.separate_builder_session_required)
        self.assertIn("privacy_ineligible", plan.rejections[0].reason_codes)
        self.assertIn("missing_capability:local_only", plan.rejections[0].reason_codes)
        self.assertIn(
            "missing_capability:pii_safe_local", plan.rejections[0].reason_codes
        )

    def test_invalid_deserialized_task_class_abstains_before_policy_branches(
        self,
    ) -> None:
        invalid = replace(
            task(TaskClass.REVIEW, "review"),
            task_class=cast(TaskClass, "unrecognized"),
        )

        plan = plan_dispatch(
            session=session(),
            task=invalid,
            candidates=(),
            policy=policy(),
            generator_family="gpt-5.6",
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.abstention_reason, "task_class_invalid")

    def test_every_deserialized_task_class_is_canonicalized_before_routing(
        self,
    ) -> None:
        for task_class in TaskClass:
            with self.subTest(task_class=task_class):
                profile, live_policy = live_profile_policy(task_class.value)
                deserialized = replace(
                    task(task_class, profile.id),
                    task_class=cast(TaskClass, task_class.value),
                )
                plan = plan_dispatch(
                    session=session(),
                    task=deserialized,
                    candidates=()
                    if task_class is TaskClass.READ_ONLY
                    else (live_profile_candidate(profile),),
                    policy=live_policy,
                    generator_family=(
                        "gpt-5.6" if task_class is TaskClass.REVIEW else None
                    ),
                )

                self.assertIs(plan.task.task_class, task_class)
                self.assertEqual(
                    plan.decision,
                    (
                        Decision.ALLOW
                        if task_class is TaskClass.READ_ONLY
                        else Decision.DELEGATE_REQUIRED
                    ),
                )

    def test_review_rejects_grader_from_generator_family(self) -> None:
        profile, live_policy = live_non_mutating_policy("review")
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.REVIEW, profile.id),
            candidates=(
                replace(
                    live_profile_candidate(profile),
                    endpoint_id="same-family-grader",
                    family="gpt-5.6",
                ),
            ),
            policy=live_policy,
            generator_family="gpt-5.6",
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(
            plan.rejections[0].reason_codes, ("generator_family_conflict",)
        )

    def test_review_rejects_family_case_and_format_variants(self) -> None:
        profile, live_policy = live_non_mutating_policy("review")
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.REVIEW, profile.id),
            candidates=(
                replace(
                    live_profile_candidate(profile),
                    endpoint_id="malformed-same-family-grader",
                    family=" \tGPT_5.6\n",
                ),
            ),
            policy=live_policy,
            generator_family="gpt-5.6",
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(
            plan.rejections[0].reason_codes, ("generator_family_conflict",)
        )

    def test_review_keeps_cross_family_grader_eligible_after_normalization(
        self,
    ) -> None:
        profile, live_policy = live_non_mutating_policy("review")
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.REVIEW, profile.id),
            candidates=(
                replace(
                    live_profile_candidate(profile),
                    endpoint_id="independent-grader",
                    family=" \tClaude_4.6\n",
                ),
            ),
            policy=live_policy,
            generator_family=" GPT-5.6 ",
        )

        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(plan.primary.endpoint_id, "independent-grader")

    def test_review_without_generator_family_abstains_closed(self) -> None:
        profile, live_policy = live_non_mutating_policy("review")
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.REVIEW, profile.id),
            candidates=(
                replace(
                    live_profile_candidate(profile),
                    endpoint_id="independent-grader",
                    family="independent-family",
                ),
            ),
            policy=live_policy,
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.abstention_reason, "generator_family_context_required")

    def test_invalid_policy_and_host_timestamps_abstain_with_typed_receipts(
        self,
    ) -> None:
        invalid_policy_timestamp = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(),
            policy=replace(policy(), as_of="not-an-iso-timestamp"),
        )
        invalid_host_timestamp = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(),
            policy=replace(
                policy(),
                host_observations=(
                    HostObservation(
                        host="pro",
                        available=True,
                        observed_at="not-an-iso-timestamp",
                    ),
                ),
            ),
        )

        self.assertEqual(invalid_policy_timestamp.decision, Decision.ABSTAIN)
        self.assertEqual(
            invalid_policy_timestamp.abstention_reason, "policy_timestamp_invalid"
        )
        self.assertEqual(invalid_host_timestamp.decision, Decision.ABSTAIN)
        self.assertEqual(
            invalid_host_timestamp.abstention_reason,
            "host_observation_timestamp_invalid",
        )

    def test_versioned_benchmark_evidence_requires_verifier_provenance(self) -> None:
        versioned_profile = replace(
            policy().task_profiles[0],
            benchmark_id="synthetic-routing-suite",
            benchmark_version="v2",
        )
        versioned_policy = replace(
            policy(), task_profiles=(versioned_profile, *policy().task_profiles[1:])
        )
        incomplete = replace(
            candidate(
                "incomplete-benchmark", model="candidate", family="test", score=0.95
            ),
            task_scores=(
                TaskScore(
                    task_profile_id="mechanical",
                    score=0.95,
                    benchmark_id="synthetic-routing-suite",
                    benchmark_version="v2",
                    sample_count=1,
                    observed_at=AS_OF,
                    evidence_kind=EvidenceKind.BENCHMARKED,
                    expires_at="2026-08-22",
                    endpoint_profile_hash="endpoint-incomplete-benchmark",
                    task_profile_hash="profile-mechanical",
                ),
            ),
        )

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(incomplete,),
            policy=versioned_policy,
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(
            plan.rejections[0].reason_codes, ("benchmark_evidence_incomplete",)
        )

    def test_complete_versioned_benchmark_evidence_opens_the_lane(self) -> None:
        versioned_profile = replace(
            policy().task_profiles[0],
            benchmark_id="synthetic-routing-suite",
            benchmark_version="v2",
        )
        versioned_policy = replace(
            policy(), task_profiles=(versioned_profile, *policy().task_profiles[1:])
        )
        evidenced = replace(
            candidate(
                "evidenced-benchmark", model="candidate", family="test", score=0.95
            ),
            task_scores=(
                TaskScore(
                    task_profile_id="mechanical",
                    score=0.95,
                    benchmark_id="synthetic-routing-suite",
                    benchmark_version="v2",
                    sample_count=1,
                    observed_at=AS_OF,
                    evidence_kind=EvidenceKind.BENCHMARKED,
                    sample_hashes=("a" * 64,),
                    scorer_id="synthetic-scorer",
                    scorer_version="v2",
                    expires_at="2026-08-22",
                    endpoint_profile_hash="endpoint-evidenced-benchmark",
                    task_profile_hash="profile-mechanical",
                ),
            ),
        )

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(evidenced,),
            policy=versioned_policy,
        )

        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(plan.primary.endpoint_id, "evidenced-benchmark")

    def test_unknown_auth_surface_is_never_selected(self) -> None:
        unknown = candidate(
            "unknown-authority",
            model="unclassified",
            family="test",
            score=0.99,
            auth_surface=AuthSurface.UNKNOWN,
        )

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(unknown,),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.rejections[0].reason_codes, ("auth_surface_unknown",))

    def test_raw_paid_auth_surface_cannot_bypass_the_paid_api_ban(self) -> None:
        raw_paid = candidate(
            "raw-paid-anthropic",
            model="claude-opus",
            family="claude",
            score=0.99,
            auth_surface=cast(AuthSurface, "anthropic_paid_api"),
            uses_paid_anthropic_api=False,
        )

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(raw_paid,),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.rejections[0].reason_codes, ("auth_surface_invalid",))

    def test_missing_task_profile_hash_abstains_before_allow_or_delegate(self) -> None:
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(
                candidate("eligible", model="model", family="test", score=0.95),
            ),
            policy=replace(policy(), task_profile_hashes={}),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.abstention_reason, "task_profile_hash_missing")
        self.assertEqual(plan.task_profile_hash, "unavailable")

    def test_review_rejects_unknown_candidate_grader_family(self) -> None:
        profile, live_policy = live_non_mutating_policy("review")
        for raw_family in ("", "---", cast(str, None)):
            with self.subTest(raw_family=raw_family):
                plan = plan_dispatch(
                    session=session(),
                    task=task(TaskClass.REVIEW, profile.id),
                    candidates=(
                        replace(
                            live_profile_candidate(profile),
                            endpoint_id=f"unknown-family-{raw_family!r}",
                            family=raw_family,
                        ),
                    ),
                    policy=live_policy,
                    generator_family="gpt-5.6",
                )

                self.assertEqual(plan.decision, Decision.ABSTAIN)
                self.assertEqual(
                    plan.rejections[0].reason_codes,
                    (
                        ("grader_family_unknown",)
                        if raw_family == "---"
                        else ("candidate_family_invalid",)
                    ),
                )

    def test_review_rejects_unknown_generator_family(self) -> None:
        profile, live_policy = live_non_mutating_policy("review")
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.REVIEW, profile.id),
            candidates=(live_profile_candidate(profile),),
            policy=live_policy,
            generator_family="---",
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.abstention_reason, "grader_family_unknown")

    def test_raw_capability_evidence_kind_never_satisfies_required_capability(
        self,
    ) -> None:
        base = candidate("raw-capability", model="model", family="test", score=0.95)
        raw_coding = replace(
            next(item for item in base.features if item.capability == "coding"),
            kind=cast(EvidenceKind, "unmeasured"),
        )
        candidate_with_raw_kind = replace(
            base,
            features=tuple(
                raw_coding if item.capability == "coding" else item
                for item in base.features
            ),
        )

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(candidate_with_raw_kind,),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(
            plan.rejections[0].reason_codes,
            ("capability_evidence_kind_invalid", "missing_capability:coding"),
        )

    def test_raw_capability_kind_cannot_open_local_pii_lane(self) -> None:
        profile, live_policy = live_profile_policy("pii_local")
        base = live_profile_candidate(profile)
        raw_local_only = replace(
            next(item for item in base.features if item.capability == "local_only"),
            kind=cast(EvidenceKind, "unmeasured"),
        )
        unsafe = replace(
            base,
            endpoint_id="raw-local-only",
            features=tuple(
                raw_local_only if item.capability == "local_only" else item
                for item in base.features
            ),
        )

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.PII_LOCAL, profile.id),
            candidates=(unsafe,),
            policy=live_policy,
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertIn(
            "capability_evidence_kind_invalid", plan.rejections[0].reason_codes
        )
        self.assertIn("privacy_ineligible", plan.rejections[0].reason_codes)
        self.assertIn("missing_capability:local_only", plan.rejections[0].reason_codes)

    def test_unpinned_benchmark_requires_provenance_and_freshness(self) -> None:
        base = candidate("untrusted-score", model="model", family="test", score=0.95)
        score = next(
            item for item in base.task_scores if item.task_profile_id == "mechanical"
        )
        cases = {
            "missing-provenance": (
                replace(score, sample_hashes=()),
                "benchmark_evidence_incomplete",
            ),
            "missing-observed-at": (
                replace(score, observed_at=None),
                "benchmark_timestamp_invalid",
            ),
            "future-observed-at": (
                replace(score, observed_at="2026-08-22"),
                "benchmark_timestamp_future",
            ),
            "stale-observed-at": (
                replace(score, observed_at="2026-08-19"),
                "benchmark_stale",
            ),
            "invalid-expiry": (
                replace(score, expires_at="2026-08-20"),
                "benchmark_timestamp_invalid",
            ),
        }
        for name, (invalid_score, reason) in cases.items():
            with self.subTest(name=name):
                plan = plan_dispatch(
                    session=session(),
                    task=task(TaskClass.MECHANICAL, "mechanical"),
                    candidates=(replace(base, task_scores=(invalid_score,)),),
                    policy=policy(),
                )

                self.assertEqual(plan.decision, Decision.ABSTAIN)
                self.assertEqual(plan.rejections[0].reason_codes, (reason,))

    def test_runtime_boolean_and_numeric_tampering_fails_closed(self) -> None:
        """Deserializer truthiness must not turn malformed values into eligibility."""
        base_task = task(TaskClass.MECHANICAL, "mechanical")
        base_policy = policy()
        base_candidate = candidate(
            "runtime-shape", model="model", family="independent", score=0.95
        )
        score = next(
            item
            for item in base_candidate.task_scores
            if item.task_profile_id == "mechanical"
        )
        mechanical_profile = base_policy.task_profiles[0]
        cases = (
            (
                "candidate_healthy_string",
                base_task,
                (replace(base_candidate, healthy=cast(bool, "false")),),
                base_policy,
                "candidate_healthy_invalid",
            ),
            (
                "candidate_automated_string",
                base_task,
                (
                    replace(
                        base_candidate,
                        automated_routing=cast(bool, "false"),
                    ),
                ),
                base_policy,
                "candidate_automated_routing_invalid",
            ),
            (
                "candidate_identity_boolean",
                base_task,
                (replace(base_candidate, identity_confidence=cast(float, True)),),
                base_policy,
                "candidate_identity_confidence_invalid",
            ),
            (
                "candidate_paid_usage_string",
                base_task,
                (
                    replace(
                        base_candidate,
                        uses_paid_anthropic_api=cast(bool, "false"),
                    ),
                ),
                base_policy,
                "paid_anthropic_usage_invalid",
            ),
            (
                "score_conservative_boolean",
                base_task,
                (
                    replace(
                        base_candidate,
                        task_scores=(
                            replace(score, conservative_score=cast(float, True)),
                        ),
                    ),
                ),
                base_policy,
                "benchmark_evidence_incomplete",
            ),
            (
                "policy_enforcement_integer",
                base_task,
                (base_candidate,),
                replace(base_policy, require_enforced_mutation=cast(bool, 0)),
                "policy_require_enforced_mutation_invalid",
            ),
            (
                "policy_paid_api_switch_integer",
                base_task,
                (base_candidate,),
                replace(base_policy, forbid_paid_anthropic_api=cast(bool, 0)),
                "policy_forbid_paid_anthropic_api_invalid",
            ),
            (
                "policy_identity_boolean",
                base_task,
                (base_candidate,),
                replace(
                    base_policy,
                    minimum_identity_confidence=cast(float, False),
                ),
                "policy_minimum_identity_confidence_invalid",
            ),
            (
                "profile_score_boolean",
                base_task,
                (base_candidate,),
                replace(
                    base_policy,
                    task_profiles=(
                        replace(
                            mechanical_profile,
                            minimum_task_score=cast(float, False),
                        ),
                        *base_policy.task_profiles[1:],
                    ),
                ),
                "task_profile_minimum_task_score_invalid",
            ),
            (
                "task_contains_pii_integer",
                replace(base_task, contains_pii=cast(bool, 0)),
                (base_candidate,),
                base_policy,
                "task_contains_pii_invalid",
            ),
            (
                "profile_pii_policy_integer",
                base_task,
                (base_candidate,),
                replace(
                    base_policy,
                    task_profiles=(
                        replace(mechanical_profile, pii_policy=cast(str, 0)),
                        *base_policy.task_profiles[1:],
                    ),
                ),
                "task_profile_pii_policy_invalid",
            ),
        )

        for (
            name,
            malformed_task,
            malformed_candidates,
            malformed_policy,
            reason,
        ) in cases:
            with self.subTest(name=name):
                plan = plan_dispatch(
                    session=session(),
                    task=malformed_task,
                    candidates=malformed_candidates,
                    policy=malformed_policy,
                )

                self.assertEqual(plan.decision, Decision.ABSTAIN)
                if plan.rejections:
                    self.assertEqual(plan.rejections[0].reason_codes, (reason,))
                else:
                    self.assertEqual(plan.abstention_reason, reason)

    def test_ordering_and_age_inputs_reject_invalid_runtime_shapes(self) -> None:
        """Values used for ranking, freshness, or scoring cannot coerce silently."""
        base_task = task(TaskClass.MECHANICAL, "mechanical")
        base_policy = policy()
        base_candidate = candidate(
            "invalid-ranking", model="model", family="independent", score=0.95
        )
        score = next(
            item
            for item in base_candidate.task_scores
            if item.task_profile_id == "mechanical"
        )
        cases = (
            (
                "cost_boolean",
                replace(base_candidate, cost_rank=cast(int, True)),
                base_policy,
                "candidate_cost_rank_invalid",
            ),
            (
                "quota_string",
                replace(base_candidate, quota_pressure_rank=cast(int, "1")),
                base_policy,
                "candidate_quota_pressure_rank_invalid",
            ),
            (
                "latency_negative",
                replace(base_candidate, latency_rank=-1),
                base_policy,
                "candidate_latency_rank_invalid",
            ),
            (
                "quality_float",
                replace(base_candidate, quality_tier=cast(int, 1.5)),
                base_policy,
                "candidate_quality_tier_invalid",
            ),
            (
                "sample_count_boolean",
                replace(
                    base_candidate, task_scores=(replace(score, sample_count=True),)
                ),
                base_policy,
                "benchmark_evidence_incomplete",
            ),
            (
                "max_age_boolean",
                base_candidate,
                replace(base_policy, max_health_age_days=cast(int, True)),
                "policy_max_health_age_invalid",
            ),
        )

        for name, malformed_candidate, malformed_policy, reason in cases:
            with self.subTest(name=name):
                plan = plan_dispatch(
                    session=session(),
                    task=base_task,
                    candidates=(malformed_candidate,),
                    policy=malformed_policy,
                )

                self.assertEqual(plan.decision, Decision.ABSTAIN)
                if plan.rejections:
                    self.assertEqual(plan.rejections[0].reason_codes, (reason,))
                else:
                    self.assertEqual(plan.abstention_reason, reason)

    def test_places_on_observed_allowed_host_not_session_host(self) -> None:
        fleet_policy = replace(
            policy(),
            host_observations=(
                HostObservation(host="air-m5", available=True, observed_at=AS_OF),
                HostObservation(host="pro", available=True, observed_at=AS_OF),
                HostObservation(host="mini-pro2", available=True, observed_at=AS_OF),
            ),
        )
        mini_only = candidate(
            "mini-builder",
            model="builder",
            family="test",
            score=0.95,
            hosts=("mini-pro2",),
        )

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(mini_only,),
            policy=fleet_policy,
        )

        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(plan.primary.machine, "mini-pro2")
        self.assertNotEqual(plan.primary.machine, plan.conductor.host)

    def test_context_limit_must_be_observed_when_task_estimates_context(self) -> None:
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(
                candidate(
                    "unknown-context",
                    model="builder",
                    family="test",
                    score=0.95,
                    context_limit=None,
                ),
            ),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.rejections[0].reason_codes, ("context_limit_unknown",))

    def test_future_and_invalid_health_timestamps_are_rejected_without_clock_assumptions(
        self,
    ) -> None:
        future = replace(
            candidate("future-health", model="builder", family="test", score=0.95),
            health_observed_at="2026-08-22T00:00:00Z",
        )
        malformed = replace(
            candidate("invalid-health", model="builder", family="test", score=0.95),
            health_observed_at="not-an-iso-timestamp",
        )

        future_plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(future,),
            policy=policy(),
        )
        malformed_plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(malformed,),
            policy=policy(),
        )

        self.assertEqual(
            future_plan.rejections[0].reason_codes,
            ("health_timestamp_future", "health_clock_skew"),
        )
        self.assertEqual(
            malformed_plan.rejections[0].reason_codes, ("health_timestamp_invalid",)
        )

    def test_allowed_modalities_are_not_implicitly_required(self) -> None:
        profile = replace(
            policy().task_profiles[0],
            allowed_modalities=frozenset({"language", "vision"}),
        )
        fleet_policy = replace(
            policy(), task_profiles=(profile, *policy().task_profiles[1:])
        )

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(
                candidate("language-only", model="builder", family="test", score=0.95),
            ),
            policy=fleet_policy,
        )

        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(plan.primary.endpoint_id, "language-only")

    def test_required_modalities_must_be_permitted_by_the_task_profile(self) -> None:
        vision_task = replace(
            task(TaskClass.MECHANICAL, "mechanical"),
            required_modalities=frozenset({"vision"}),
        )
        plan = plan_dispatch(
            session=session(),
            task=vision_task,
            candidates=(
                candidate(
                    "vision",
                    model="builder",
                    family="test",
                    score=0.95,
                    capabilities=("coding", "vision"),
                ),
            ),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.abstention_reason, "required_modality_not_allowed:vision")

    def test_model_card_is_not_an_invocable_target(self) -> None:
        registry = load_registry(Path(__file__).resolve().parents[2])
        self.assertFalse(registry.endpoints())
        self.assertTrue(registry.endpoints(automated_only=False))
        with self.assertRaises(AbstractModelCardError):
            registry.endpoint(next(iter(registry.model_cards)))

    def test_invalid_session_never_receives_a_conductor_assignment(self) -> None:
        child_claiming_conductor = replace(
            session(), parent_session_id="parent-session"
        )

        plan = plan_dispatch(
            session=child_claiming_conductor,
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.abstention_reason, "session_child_conductor_forbidden")
        self.assertEqual(plan.assignments, ())

        untyped_plan = plan_dispatch(
            session=cast(SessionIdentity, object()),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(),
            policy=policy(),
        )
        self.assertEqual(untyped_plan.decision, Decision.ABSTAIN)
        self.assertEqual(untyped_plan.abstention_reason, "session_identity_invalid")
        self.assertEqual(untyped_plan.assignments, ())

    def test_session_root_coherence_and_metadata_fail_closed(self) -> None:
        cases = (
            (
                replace(session(), root_session_id="different-root"),
                "session_root_chain_invalid",
            ),
            (
                replace(session(), repo_root=cast(Path, "relative-repo")),
                "session_repo_root_invalid",
            ),
            (
                replace(session(), started_at="2026-08-22T00:00:00Z"),
                "session_timestamp_future",
            ),
        )

        for malformed_session, reason in cases:
            with self.subTest(reason=reason):
                plan = plan_dispatch(
                    session=malformed_session,
                    task=task(TaskClass.MECHANICAL, "mechanical"),
                    candidates=(),
                    policy=policy(),
                )

                self.assertEqual(plan.decision, Decision.ABSTAIN)
                self.assertEqual(plan.abstention_reason, reason)
                self.assertEqual(plan.assignments, ())

    def test_duplicate_task_profile_and_endpoint_identifiers_abstain(self) -> None:
        duplicate_profile = replace(
            policy(),
            task_profiles=(policy().task_profiles[0], policy().task_profiles[0]),
        )
        duplicate_endpoint = candidate(
            "duplicate-endpoint", model="builder", family="test", score=0.95
        )

        profile_plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(),
            policy=duplicate_profile,
        )
        endpoint_plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(duplicate_endpoint, duplicate_endpoint),
            policy=policy(),
        )

        self.assertEqual(profile_plan.abstention_reason, "task_profile_duplicate")
        self.assertEqual(
            endpoint_plan.abstention_reason, "candidate_endpoint_duplicate"
        )

    def test_declared_capability_never_opens_local_pii_lane(self) -> None:
        profile, local_policy = live_profile_policy("pii_local")
        base = live_profile_candidate(profile)
        declared_local_only = replace(
            next(item for item in base.features if item.capability == "local_only"),
            kind=EvidenceKind.DECLARED,
        )
        unsafe = replace(
            base,
            features=tuple(
                declared_local_only if item.capability == "local_only" else item
                for item in base.features
            ),
        )

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.PII_LOCAL, profile.id),
            candidates=(unsafe,),
            policy=local_policy,
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertIn("privacy_ineligible", plan.rejections[0].reason_codes)
        self.assertIn("missing_capability:local_only", plan.rejections[0].reason_codes)

    def test_pii_local_requires_local_runtime_auth_surface(self) -> None:
        profile, local_policy = live_profile_policy("pii_local")
        cloud_surface = replace(
            live_profile_candidate(profile),
            auth_surface=AuthSurface.OPENAI_CHATGPT_SUBSCRIPTION,
        )

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.PII_LOCAL, profile.id),
            candidates=(cloud_surface,),
            policy=local_policy,
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(
            plan.rejections[0].reason_codes,
            ("privacy_ineligible",),
        )

    def test_duplicate_or_conflicting_capability_evidence_fails_closed(self) -> None:
        base = candidate(
            "evidence-conflict", model="builder", family="test", score=0.95
        )
        coding = next(item for item in base.features if item.capability == "coding")
        duplicate = replace(base, features=base.features + (coding,))
        contradiction = replace(
            base,
            features=base.features
            + (replace(coding, value=False, evidence_ref="test:coding-negative"),),
        )

        for malformed in (duplicate, contradiction):
            with self.subTest(
                candidate=malformed.endpoint_id, features=malformed.features
            ):
                plan = plan_dispatch(
                    session=session(),
                    task=task(TaskClass.MECHANICAL, "mechanical"),
                    candidates=(malformed,),
                    policy=policy(),
                )

                self.assertEqual(plan.decision, Decision.ABSTAIN)
                self.assertIn(
                    "capability_evidence_duplicate", plan.rejections[0].reason_codes
                )
        contradiction_plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(contradiction,),
            policy=policy(),
        )
        self.assertIn(
            "capability_evidence_conflict",
            contradiction_plan.rejections[0].reason_codes,
        )
        self.assertIn(
            "missing_capability:coding", contradiction_plan.rejections[0].reason_codes
        )

    def test_zero_confidence_numeric_capability_does_not_satisfy_context_floor(
        self,
    ) -> None:
        base = candidate("zero-confidence", model="builder", family="test", score=0.95)
        zero_confidence_context = replace(
            next(item for item in base.features if item.capability == "context_tokens"),
            confidence=0.0,
        )
        untrusted = replace(
            base,
            features=tuple(
                zero_confidence_context if item.capability == "context_tokens" else item
                for item in base.features
            ),
        )

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(untrusted,),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.rejections[0].reason_codes, ("context_limit_unknown",))

    def test_benchmark_binding_rejects_endpoint_transplant_and_profile_drift(
        self,
    ) -> None:
        base = candidate("bound-endpoint", model="builder", family="test", score=0.95)
        transplanted = replace(base, endpoint_profile_hash="endpoint-other")
        drifted_policy = replace(
            policy(),
            task_profile_hashes={
                **policy().task_profile_hashes,
                "mechanical": "profile-mechanical-revision",
            },
        )

        endpoint_plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(transplanted,),
            policy=policy(),
        )
        profile_plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(base,),
            policy=drifted_policy,
        )
        unbound_score = replace(
            base.task_scores[0],
            endpoint_profile_hash=None,
            task_profile_hash=None,
        )
        unbound_plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(replace(base, task_scores=(unbound_score,)),),
            policy=policy(),
        )

        self.assertEqual(
            endpoint_plan.rejections[0].reason_codes,
            ("benchmark_endpoint_profile_mismatch",),
        )
        self.assertEqual(
            profile_plan.rejections[0].reason_codes,
            ("benchmark_task_profile_mismatch",),
        )
        self.assertEqual(
            unbound_plan.rejections[0].reason_codes,
            ("benchmark_endpoint_profile_mismatch",),
        )

    def test_benchmark_requires_lowercase_sha256_sample_hashes(self) -> None:
        base = candidate("hash-case", model="builder", family="test", score=0.95)
        score = next(
            item for item in base.task_scores if item.task_profile_id == "mechanical"
        )
        malformed = replace(score, sample_hashes=("A" * 64,) + score.sample_hashes[1:])

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(replace(base, task_scores=(malformed,)),),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(
            plan.rejections[0].reason_codes, ("benchmark_evidence_incomplete",)
        )

    def test_iso_parser_abstains_on_os_error_boundary(self) -> None:
        class RaisingDateTime:
            @staticmethod
            def fromisoformat(value: str) -> object:
                del value
                raise OSError("synthetic parser failure")

        original_datetime = router.datetime
        try:
            router.datetime = RaisingDateTime  # type: ignore[assignment]
            self.assertIsNone(router._parse_iso_timestamp("2026-08-21T00:00:00Z"))
        finally:
            router.datetime = original_datetime

    def test_malformed_public_task_or_policy_abstains_without_attribute_error(
        self,
    ) -> None:
        malformed_task = plan_dispatch(
            session=session(),
            task=cast(TaskIntent, object()),
            candidates=(),
            policy=policy(),
        )
        malformed_policy = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(),
            policy=cast(RoutingPolicy, object()),
        )
        all_malformed = plan_dispatch(
            session=cast(SessionIdentity, object()),
            task=cast(TaskIntent, object()),
            candidates=(),
            policy=cast(RoutingPolicy, object()),
        )

        self.assertEqual(malformed_task.decision, Decision.ABSTAIN)
        self.assertEqual(malformed_task.abstention_reason, "task_intent_invalid")
        self.assertEqual(malformed_policy.decision, Decision.ABSTAIN)
        self.assertEqual(malformed_policy.abstention_reason, "routing_policy_invalid")
        self.assertEqual(all_malformed.decision, Decision.ABSTAIN)
        self.assertEqual(all_malformed.abstention_reason, "session_identity_invalid")
        self.assertEqual(all_malformed.policy_hash, "unavailable")

    def test_expiry_at_policy_clock_is_stale_for_capability_and_benchmark(
        self,
    ) -> None:
        base = candidate("expiry-boundary", model="builder", family="test", score=0.95)
        expired_capability = replace(base.features[0], expires_at=AS_OF)
        capability_plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(
                replace(base, features=(expired_capability, *base.features[1:])),
            ),
            policy=policy(),
        )
        score = next(
            item for item in base.task_scores if item.task_profile_id == "mechanical"
        )
        expired_score = replace(score, expires_at=AS_OF)
        benchmark_plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(replace(base, task_scores=(expired_score,)),),
            policy=policy(),
        )

        self.assertEqual(
            capability_plan.rejections[0].reason_codes, ("capability_stale",)
        )
        self.assertEqual(
            benchmark_plan.rejections[0].reason_codes, ("benchmark_stale",)
        )

    def test_candidate_family_is_required_before_assignment_for_every_task(
        self,
    ) -> None:
        for raw_family in (cast(str, ""), cast(str, 7)):
            with self.subTest(raw_family=raw_family):
                malformed = candidate(
                    "invalid-family",
                    model="builder",
                    family=raw_family,
                    score=0.95,
                )
                plan = plan_dispatch(
                    session=session(),
                    task=task(TaskClass.MECHANICAL, "mechanical"),
                    candidates=(malformed,),
                    policy=policy(),
                )

                self.assertEqual(plan.decision, Decision.ABSTAIN)
                self.assertEqual(
                    plan.rejections[0].reason_codes, ("candidate_family_invalid",)
                )

    def test_mixed_or_invalid_endpoint_identifiers_abstain_before_sorting(self) -> None:
        valid = candidate("valid", model="builder", family="test", score=0.95)
        malformed = replace(valid, endpoint_id=cast(str, 7))

        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.MECHANICAL, "mechanical"),
            candidates=(valid, malformed),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.abstention_reason, "candidate_endpoint_id_invalid")

    def test_any_nonblank_root_engine_can_remain_conductor(self) -> None:
        builder = candidate(
            "engine-builder", model="builder", family="test", score=0.95
        )
        for engine in ("Jules", "NotebookLM", "Qwen", "Kimi", "Claude", "Codex"):
            with self.subTest(engine=engine):
                plan = plan_dispatch(
                    session=replace(session(), engine=engine),
                    task=task(TaskClass.MECHANICAL, "mechanical"),
                    candidates=(builder,),
                    policy=policy(),
                )

                self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
                self.assertEqual(plan.conductor.engine, engine)


if __name__ == "__main__":
    unittest.main()
