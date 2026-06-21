"""H24 scheduler contract for the Autonomous Lab control plane."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from backend.services.autonomous_lab.state_store import (
    LabRuntimePlacement,
    current_runtime_placement,
)

SCHEDULER_CONTRACT_VERSION = "autonomous-lab-v1-h24-scheduler"
DEFAULT_SCHEDULER_TICK_INTERVAL_SECONDS = 60
SCHEDULER_SAFEGUARDS = (
    "single_tick_only",
    "internal_api_only",
    "db_required",
    "pro_run_execution_only",
    "manual_promotion_required",
    "no_deploy_merge_push",
)


class LabSchedulerState(str, Enum):
    """Operator-visible H24 scheduler state."""

    READY = "ready"
    DB_UNAVAILABLE = "db_unavailable"
    HOST_BLOCKED = "host_blocked"
    DISABLED = "disabled"


@dataclass(frozen=True)
class LabSchedulerStatus:
    """Receipt-safe scheduler status surfaced to the control room."""

    version: str
    updated_at: datetime
    enabled: bool
    db_available: bool
    placement: LabRuntimePlacement
    tick_interval_seconds: int
    worker_id: str
    state: LabSchedulerState
    can_tick: bool
    next_tick_not_before: datetime
    next_action: str
    tick_mode: str
    autonomous_execution_allowed: bool
    manual_promotion_required: bool
    safeguards: tuple[str, ...]

    def to_receipt(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "updated_at": self.updated_at.isoformat(),
            "enabled": self.enabled,
            "db_available": self.db_available,
            "placement": self.placement.to_receipt(),
            "tick_interval_seconds": self.tick_interval_seconds,
            "worker_id": self.worker_id,
            "state": self.state.value,
            "can_tick": self.can_tick,
            "next_tick_not_before": self.next_tick_not_before.isoformat(),
            "next_action": self.next_action,
            "tick_mode": self.tick_mode,
            "autonomous_execution_allowed": self.autonomous_execution_allowed,
            "manual_promotion_required": self.manual_promotion_required,
            "safeguards": list(self.safeguards),
        }


def build_lab_scheduler_status(
    *,
    db_available: bool,
    enabled: bool = True,
    placement: LabRuntimePlacement | None = None,
    tick_interval_seconds: int = DEFAULT_SCHEDULER_TICK_INTERVAL_SECONDS,
    worker_id: str | None = None,
    updated_at: datetime | None = None,
) -> LabSchedulerStatus:
    """Build a deterministic H24 scheduler status without mutating runtime state."""
    resolved_placement = placement or current_runtime_placement()
    timestamp = updated_at or datetime.now(tz=timezone.utc)
    bounded_interval = max(5, min(tick_interval_seconds, 3600))
    resolved_worker_id = worker_id or _default_worker_id(resolved_placement)
    state = _scheduler_state(
        enabled=enabled,
        db_available=db_available,
        placement=resolved_placement,
    )
    can_tick = state is LabSchedulerState.READY
    return LabSchedulerStatus(
        version=SCHEDULER_CONTRACT_VERSION,
        updated_at=timestamp,
        enabled=enabled,
        db_available=db_available,
        placement=resolved_placement,
        tick_interval_seconds=bounded_interval,
        worker_id=resolved_worker_id,
        state=state,
        can_tick=can_tick,
        next_tick_not_before=timestamp + timedelta(seconds=bounded_interval),
        next_action=_next_scheduler_action(state, resolved_placement),
        tick_mode="bounded_single_tick",
        autonomous_execution_allowed=False,
        manual_promotion_required=True,
        safeguards=SCHEDULER_SAFEGUARDS,
    )


def _scheduler_state(
    *,
    enabled: bool,
    db_available: bool,
    placement: LabRuntimePlacement,
) -> LabSchedulerState:
    if not enabled:
        return LabSchedulerState.DISABLED
    if not placement.can_claim_runs:
        return LabSchedulerState.HOST_BLOCKED
    if not db_available:
        return LabSchedulerState.DB_UNAVAILABLE
    return LabSchedulerState.READY


def _next_scheduler_action(
    state: LabSchedulerState,
    placement: LabRuntimePlacement,
) -> str:
    if state is LabSchedulerState.READY:
        return "claim one pending run, checkpoint stages, then pause at curator"
    if state is LabSchedulerState.DB_UNAVAILABLE:
        return "attach the runtime database before ticking the worker"
    if state is LabSchedulerState.HOST_BLOCKED:
        return f"route run execution to {placement.heavy_work_destination}"
    return "enable the autonomous lab runtime flag before scheduling ticks"


def _default_worker_id(placement: LabRuntimePlacement) -> str:
    return f"lab-worker:{placement.machine_role.value}"


__all__ = [
    "DEFAULT_SCHEDULER_TICK_INTERVAL_SECONDS",
    "SCHEDULER_CONTRACT_VERSION",
    "SCHEDULER_SAFEGUARDS",
    "LabSchedulerState",
    "LabSchedulerStatus",
    "build_lab_scheduler_status",
]
