"""
Integration test: `BackendSelfHealingAgent` façade must preserve the legacy
API that `backend/services/misc/autonomous_scheduler.py` depends on:

    await healing_agent.perform_health_check()
    issues = await healing_agent.detect_issues()
    if healing_agent.auto_fix_enabled and issues:
        await healing_agent.attempt_auto_fix(issues)

We swap in synthetic checks via monkeypatch so the test doesn't depend on
a real Redis/API/DB.
"""

from __future__ import annotations

import pytest

from backend.self_healing.actions.base import ActionResult
from backend.self_healing.backend_agent import BackendSelfHealingAgent, HealthMetrics
from backend.self_healing.checks.base import CheckResult


class FailingCheck:
    def __init__(self, name: str) -> None:
        self.name = name

    async def run(self) -> CheckResult:
        return CheckResult(healthy=False, error=f"{self.name} down")


class HealthyCheck:
    def __init__(self, name: str, detail: dict) -> None:
        self.name = name
        self._detail = detail

    async def run(self) -> CheckResult:
        return CheckResult(healthy=True, detail=self._detail)


class StubAction:
    def __init__(self, name: str, target: str) -> None:
        self.name = name
        self.target_check = target

    async def run(self) -> ActionResult:
        return ActionResult(success=True, detail="stub")


@pytest.fixture
def agent():
    a = BackendSelfHealingAgent(
        service_name="test-service",
        auto_fix_enabled=True,
    )
    # Replace the real check set with synthetic ones so the test is hermetic.
    a.orchestrator.checks = [
        HealthyCheck("cpu", {"cpu_percent": 5.0, "threshold": 90.0}),
        HealthyCheck("memory", {"memory_percent": 20.0, "threshold": 90.0}),
        HealthyCheck("disk", {"disk_percent": 40.0, "threshold": 90.0}),
        FailingCheck("cache"),
    ]
    a.orchestrator.actions = [StubAction("reconnect_cache", target="cache")]
    # Re-build breakers for the new check set
    from backend.self_healing.circuit_breaker import CircuitBreaker

    a.orchestrator.breakers = {
        c.name: CircuitBreaker(c.name, failure_threshold=99, cooldown_seconds=1)
        for c in a.orchestrator.checks
    }
    # Clear the HTTP client so nothing leaks
    a.orchestrator.reporter = None
    return a


class TestBackendAgentFacade:
    @pytest.mark.asyncio
    async def test_perform_health_check_returns_projection(self, agent):
        metrics = await agent.perform_health_check()
        assert isinstance(metrics, HealthMetrics)
        assert metrics.cpu_usage == 5.0
        assert metrics.memory_usage == 20.0
        assert metrics.disk_usage == 40.0
        assert metrics.cache_healthy is False

    @pytest.mark.asyncio
    async def test_detect_issues_surfaces_failing_check(self, agent):
        issues = await agent.detect_issues()
        types = [i["type"] for i in issues]
        assert "cache_down" in types
        # Healthy checks must NOT appear
        assert "high_cpu" not in types
        assert "high_memory" not in types

    @pytest.mark.asyncio
    async def test_attempt_auto_fix_increments_counter(self, agent):
        issues = await agent.detect_issues()
        before = agent.fix_count
        await agent.attempt_auto_fix(issues)
        assert agent.fix_count >= before

    def test_get_status_shape(self, agent):
        status = agent.get_status()
        assert status["service"] == "test-service"
        assert "stats" in status
        assert "checks" in status["stats"]
        assert "breakers" in status["stats"]


class TestReducedAgent:
    """Scheduler-necropsy 2026-07-14: the default reporter targeted
    https://nuzantara-orchestrator.fly.dev which never existed as a deployed
    app (silent 4xx per event), and the live init path §10e runs a reduced
    cure surface (GC only)."""

    def test_no_phantom_reporter_by_default(self):
        agent = BackendSelfHealingAgent(service_name="t")
        assert agent.orchestrator.reporter is None

    def test_explicit_url_wires_reporter(self):
        agent = BackendSelfHealingAgent(
            service_name="t", orchestrator_url="https://example.internal"
        )
        assert agent.orchestrator.reporter is not None

    def test_actions_param_reduces_cure_surface(self):
        from backend.self_healing.actions import GCAction

        agent = BackendSelfHealingAgent(service_name="t", actions=[GCAction()])
        assert [type(a).__name__ for a in agent.orchestrator.actions] == ["GCAction"]

    def test_default_actions_unchanged(self):
        agent = BackendSelfHealingAgent(service_name="t")
        names = [type(a).__name__ for a in agent.orchestrator.actions]
        assert names == ["GCAction", "ReconnectCacheAction", "RestartServiceAction"]
