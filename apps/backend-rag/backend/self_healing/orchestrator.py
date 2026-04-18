"""
Orchestrator — wires checks, circuit breakers, remediation actions, and
metrics into a single callable surface.

One `SelfHealingOrchestrator` instance per agent. The autonomous scheduler
(see `backend/services/misc/autonomous_scheduler.py`) ticks it every
5 minutes. External consumers use:

- `run_cycle()`          — one iteration: check + remediate + report
- `get_stats()`          — snapshot for the admin endpoint
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.self_healing.actions.base import RemediationAction
from backend.self_healing.checks.base import CheckResult, HealthCheck
from backend.self_healing.circuit_breaker import CircuitBreaker
from backend.self_healing.metrics import SelfHealingStats

logger = logging.getLogger(__name__)


@dataclass
class CycleOutcome:
    check_results: dict[str, CheckResult] = field(default_factory=dict)
    actions_fired: list[str] = field(default_factory=list)
    breakers_open: list[str] = field(default_factory=list)


class SelfHealingOrchestrator:
    def __init__(
        self,
        checks: list[HealthCheck],
        actions: list[RemediationAction] | None = None,
        *,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
        reporter=None,
    ) -> None:
        self.checks = checks
        self.actions = actions or []
        self.reporter = reporter
        self.stats = SelfHealingStats()
        self.breakers: dict[str, CircuitBreaker] = {
            c.name: CircuitBreaker(
                name=c.name,
                failure_threshold=failure_threshold,
                cooldown_seconds=cooldown_seconds,
            )
            for c in self.checks
        }

    async def run_cycle(self) -> CycleOutcome:
        outcome = CycleOutcome()

        # 1. Run checks (skip any whose breaker is OPEN and still in cooldown).
        for check in self.checks:
            breaker = self.breakers[check.name]
            if not breaker.allow():
                outcome.breakers_open.append(check.name)
                continue

            try:
                result = await check.run()
            except Exception as exc:  # noqa: BLE001 — guard against rogue check
                result = CheckResult(healthy=False, error=f"{type(exc).__name__}: {exc}")

            outcome.check_results[check.name] = result
            check_stats = self.stats.check(check.name)

            if result.healthy:
                check_stats.record_success()
                breaker.record_success()
            else:
                check_stats.record_failure(result.error)
                breaker.record_failure(result.error)

        # 2. Fire actions for any failing check (that wasn't skipped).
        failing = {
            name for name, r in outcome.check_results.items() if not r.healthy
        }
        for action in self.actions:
            if action.target_check not in failing:
                continue
            try:
                action_result = await action.run()
            except Exception as exc:  # noqa: BLE001
                self.stats.action(action.name).record(
                    success=False, error=f"{type(exc).__name__}: {exc}",
                )
                continue

            self.stats.action(action.name).record(
                success=action_result.success, error=action_result.error,
            )
            if action_result.success:
                outcome.actions_fired.append(action.name)

        # 3. Report cycle to orchestrator.
        if self.reporter is not None:
            try:
                await self.reporter.report({
                    "type": "self_heal_cycle",
                    "severity": "low" if not failing else "medium",
                    "data": {
                        "failing_checks": sorted(failing),
                        "breakers_open": outcome.breakers_open,
                        "actions_fired": outcome.actions_fired,
                    },
                })
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"reporter.report raised: {exc}")

        return outcome

    def get_stats(self) -> dict[str, object]:
        return {
            **self.stats.snapshot(),
            "breakers": {
                name: breaker.snapshot() for name, breaker in self.breakers.items()
            },
        }
