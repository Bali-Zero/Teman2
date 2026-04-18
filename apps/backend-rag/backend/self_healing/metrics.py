"""
In-memory metrics for the self-healing subsystem.

Exposed via `GET /api/admin/self-healing/stats` (see
`backend/app/routers/admin_self_healing.py`). Replaced by Prometheus
counters if/when we grow a dedicated metrics pipeline.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class CheckStats:
    name: str
    total_runs: int = 0
    total_success: int = 0
    total_failure: int = 0
    last_run_at: float | None = None
    last_success_at: float | None = None
    last_failure_at: float | None = None
    last_error: str | None = None
    last_recovery_duration_seconds: float | None = None  # time between last failure → success

    def record_success(self) -> None:
        now = time.time()
        self.total_runs += 1
        self.total_success += 1
        self.last_run_at = now
        if self.last_failure_at is not None and self.last_success_at != now:
            self.last_recovery_duration_seconds = now - self.last_failure_at
        self.last_success_at = now

    def record_failure(self, error: str | None = None) -> None:
        now = time.time()
        self.total_runs += 1
        self.total_failure += 1
        self.last_run_at = now
        self.last_failure_at = now
        self.last_error = error


@dataclass
class ActionStats:
    name: str
    total_runs: int = 0
    total_success: int = 0
    total_failure: int = 0
    last_run_at: float | None = None
    last_error: str | None = None

    def record(self, *, success: bool, error: str | None = None) -> None:
        self.total_runs += 1
        if success:
            self.total_success += 1
        else:
            self.total_failure += 1
        self.last_run_at = time.time()
        if error is not None:
            self.last_error = error


@dataclass
class SelfHealingStats:
    """
    Global registry of check- and action-level stats. One instance per
    BackendSelfHealingAgent (so each Fly machine reports its own).
    """

    started_at: float = field(default_factory=time.time)
    checks: dict[str, CheckStats] = field(default_factory=dict)
    actions: dict[str, ActionStats] = field(default_factory=dict)

    def check(self, name: str) -> CheckStats:
        if name not in self.checks:
            self.checks[name] = CheckStats(name=name)
        return self.checks[name]

    def action(self, name: str) -> ActionStats:
        if name not in self.actions:
            self.actions[name] = ActionStats(name=name)
        return self.actions[name]

    def snapshot(self) -> dict[str, object]:
        return {
            "started_at": self.started_at,
            "uptime_seconds": time.time() - self.started_at,
            "checks": {name: cs.__dict__ for name, cs in self.checks.items()},
            "actions": {name: a.__dict__ for name, a in self.actions.items()},
        }
