"""
Unit tests for SelfHealingOrchestrator — covers check success/failure,
circuit breaker skipping, action firing, and stats snapshot.
"""

from __future__ import annotations

import pytest

from backend.self_healing.actions.base import ActionResult
from backend.self_healing.checks.base import CheckResult
from backend.self_healing.orchestrator import SelfHealingOrchestrator


class FakeCheck:
    def __init__(self, name: str, healthy_sequence: list[bool], detail=None) -> None:
        self.name = name
        self._sequence = iter(healthy_sequence)
        self._detail = detail or {}
        self.runs = 0

    async def run(self) -> CheckResult:
        self.runs += 1
        try:
            healthy = next(self._sequence)
        except StopIteration:
            healthy = True
        return CheckResult(
            healthy=healthy,
            detail=self._detail,
            error=None if healthy else f"{self.name} failed",
        )


class FakeAction:
    def __init__(self, name: str, target: str, success: bool = True) -> None:
        self.name = name
        self.target_check = target
        self._success = success
        self.runs = 0

    async def run(self) -> ActionResult:
        self.runs += 1
        return ActionResult(success=self._success, detail="stub")


class CountingReporter:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def report(self, event: dict) -> None:
        self.events.append(event)


class TestOrchestratorCycle:
    @pytest.mark.asyncio
    async def test_healthy_cycle_no_actions_fire(self):
        check = FakeCheck("cpu", [True])
        action = FakeAction("gc", target="memory")
        orch = SelfHealingOrchestrator(checks=[check], actions=[action])

        outcome = await orch.run_cycle()

        assert outcome.check_results["cpu"].healthy
        assert outcome.actions_fired == []
        assert action.runs == 0
        assert orch.stats.check("cpu").total_success == 1

    @pytest.mark.asyncio
    async def test_failing_check_triggers_matching_action(self):
        check = FakeCheck("cache", [False])
        matching_action = FakeAction("reconnect_cache", target="cache")
        nonmatching_action = FakeAction("gc", target="memory")
        orch = SelfHealingOrchestrator(
            checks=[check],
            actions=[matching_action, nonmatching_action],
        )

        outcome = await orch.run_cycle()

        assert not outcome.check_results["cache"].healthy
        assert "reconnect_cache" in outcome.actions_fired
        assert matching_action.runs == 1
        assert nonmatching_action.runs == 0  # different target

    @pytest.mark.asyncio
    async def test_breaker_opens_and_skips(self):
        # 3 consecutive failures → breaker OPEN → next cycle skips check
        check = FakeCheck("api", [False, False, False, False])
        orch = SelfHealingOrchestrator(
            checks=[check], failure_threshold=3, cooldown_seconds=9999,
        )

        await orch.run_cycle()
        await orch.run_cycle()
        await orch.run_cycle()  # breaker opens here
        assert orch.breakers["api"].state.value == "open"

        outcome = await orch.run_cycle()
        assert "api" in outcome.breakers_open
        assert check.runs == 3, "Check must not run when breaker is open"

    @pytest.mark.asyncio
    async def test_reporter_invoked_each_cycle(self):
        check = FakeCheck("cpu", [True])
        reporter = CountingReporter()
        orch = SelfHealingOrchestrator(checks=[check], reporter=reporter)
        await orch.run_cycle()
        assert len(reporter.events) == 1
        assert reporter.events[0]["type"] == "self_heal_cycle"

    @pytest.mark.asyncio
    async def test_stats_snapshot_exposes_breakers_and_checks(self):
        check = FakeCheck("disk", [True, False])
        orch = SelfHealingOrchestrator(checks=[check])
        await orch.run_cycle()
        await orch.run_cycle()
        stats = orch.get_stats()
        assert "checks" in stats
        assert "breakers" in stats
        assert stats["checks"]["disk"]["total_success"] == 1
        assert stats["checks"]["disk"]["total_failure"] == 1
        assert stats["breakers"]["disk"]["state"] == "closed"  # below threshold=3
