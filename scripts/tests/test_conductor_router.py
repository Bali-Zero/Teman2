"""Unit tests for the deterministic Universal Conductor router."""

from __future__ import annotations

import unittest
from dataclasses import replace
from pathlib import Path

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
from scripts.conductor.router import plan_dispatch


AS_OF = "2026-08-21"


def capability(
    name: str,
    *,
    kind: EvidenceKind = EvidenceKind.PROBED,
    value: bool | int | float | str | None = True,
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
            ),
            TaskScore(
                task_profile_id="standard_build",
                score=score,
                benchmark_id="synthetic-routing-suite",
                benchmark_version="v1",
                sample_count=10,
                observed_at=AS_OF,
                evidence_kind=EvidenceKind.BENCHMARKED,
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
    """Return a code-mutation task with a concrete MIR profile binding."""
    return TaskIntent(
        task_id=f"task-{profile_id}",
        task_class=task_class,
        gear=2,
        mutation=task_class is not TaskClass.READ_ONLY,
        files=("scripts/conductor/runtime.py",),
        requires=frozenset({"coding"})
        if task_class is not TaskClass.READ_ONLY
        else frozenset(),
        task_profile_id=profile_id,
        estimated_context_tokens=8_000,
        required_modalities=frozenset({"language"}),
        required_tools=frozenset(),
        contains_pii=False,
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


class ConductorRouterTest(unittest.TestCase):
    def test_read_only_class_cannot_smuggle_a_mutation_into_root_allowance(
        self,
    ) -> None:
        contradictory = replace(
            task(TaskClass.READ_ONLY, "mechanical"),
            mutation=True,
            files=("pkg/mutated.py",),
        )

        plan = plan_dispatch(
            session=session(),
            task=contradictory,
            candidates=(),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(plan.abstention_reason, "read_only_mutation_contradiction")
        self.assertIsNone(plan.primary)
        self.assertFalse(plan.separate_builder_session_required)

    def test_read_only_requires_valid_policy_and_host_evidence(self) -> None:
        cases = (
            (
                "malformed_policy_timestamp",
                replace(policy(), as_of="not-an-iso-timestamp"),
                "policy_timestamp_invalid",
            ),
            (
                "invalid_max_health_age",
                replace(policy(), max_health_age_days=-1),
                "policy_max_health_age_invalid",
            ),
            (
                "malformed_host_timestamp",
                replace(
                    policy(),
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
                    policy(),
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
                replace(policy(), host_observations=()),
                "host_observation_missing",
            ),
        )

        for name, invalid_policy, reason in cases:
            with self.subTest(name=name):
                plan = plan_dispatch(
                    session=session(),
                    task=task(TaskClass.READ_ONLY, "mechanical"),
                    candidates=(),
                    policy=invalid_policy,
                )

                self.assertEqual(plan.decision, Decision.ABSTAIN)
                self.assertEqual(plan.abstention_reason, reason)

    def test_read_only_allows_with_valid_policy_and_host_evidence(self) -> None:
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.READ_ONLY, "mechanical"),
            candidates=(),
            policy=policy(),
        )

        self.assertEqual(plan.decision, Decision.ALLOW)
        self.assertEqual(plan.selection_reason_codes, ("read_only_conductor_retained",))
        self.assertIsNone(plan.abstention_reason)

    def test_read_only_requires_its_own_host_observation(self) -> None:
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.READ_ONLY, "mechanical"),
            candidates=(),
            policy=replace(
                policy(),
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
            task=task(TaskClass.READ_ONLY, "mechanical"),
            candidates=(),
            policy=replace(
                policy(),
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
            task=task(TaskClass.READ_ONLY, "mechanical"),
            candidates=(),
            policy=replace(
                policy(),
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
            task=task(TaskClass.READ_ONLY, "mechanical"),
            candidates=(),
            policy=replace(
                policy(),
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
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.REVIEW, "mechanical"),
            candidates=(
                candidate(
                    "independent-grader",
                    model="independent",
                    family="independent-family",
                    score=0.95,
                ),
            ),
            policy=policy(),
            generator_family="gpt-5.6",
        )

        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(plan.primary.role, Role.GRADER)
        self.assertEqual(plan.primary.endpoint_id, "independent-grader")

    def test_review_rejects_grader_from_generator_family(self) -> None:
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.REVIEW, "mechanical"),
            candidates=(
                candidate(
                    "same-family-grader",
                    model="same-family",
                    family="gpt-5.6",
                    score=0.95,
                ),
            ),
            policy=policy(),
            generator_family="gpt-5.6",
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(
            plan.rejections[0].reason_codes, ("generator_family_conflict",)
        )

    def test_review_rejects_family_case_and_format_variants(self) -> None:
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.REVIEW, "mechanical"),
            candidates=(
                candidate(
                    "malformed-same-family-grader",
                    model="same-family",
                    family=" \tGPT_5.6\n",
                    score=0.95,
                ),
            ),
            policy=policy(),
            generator_family="gpt-5.6",
        )

        self.assertEqual(plan.decision, Decision.ABSTAIN)
        self.assertEqual(
            plan.rejections[0].reason_codes, ("generator_family_conflict",)
        )

    def test_review_keeps_cross_family_grader_eligible_after_normalization(
        self,
    ) -> None:
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.REVIEW, "mechanical"),
            candidates=(
                candidate(
                    "independent-grader",
                    model="independent",
                    family=" \tClaude_4.6\n",
                    score=0.95,
                ),
            ),
            policy=policy(),
            generator_family=" GPT-5.6 ",
        )

        self.assertEqual(plan.decision, Decision.DELEGATE_REQUIRED)
        self.assertEqual(plan.primary.endpoint_id, "independent-grader")

    def test_review_without_generator_family_abstains_closed(self) -> None:
        plan = plan_dispatch(
            session=session(),
            task=task(TaskClass.REVIEW, "mechanical"),
            candidates=(
                candidate(
                    "independent-grader",
                    model="independent",
                    family="independent-family",
                    score=0.95,
                ),
            ),
            policy=policy(),
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
                    sample_hashes=("sample-sha256",),
                    scorer_id="synthetic-scorer",
                    scorer_version="v2",
                    expires_at="2026-08-22",
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


if __name__ == "__main__":
    unittest.main()
