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
        uses_paid_anthropic_api=auth_surface is AuthSurface.ANTHROPIC_PAID_API,
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
