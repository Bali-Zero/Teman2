from __future__ import annotations

from datetime import datetime, timezone

from backend.services.autonomous_lab.scheduler import (
    DEFAULT_SCHEDULER_TICK_INTERVAL_SECONDS,
    LabSchedulerState,
    build_lab_scheduler_status,
)
from backend.services.autonomous_lab.state_store import resolve_runtime_placement


def test_scheduler_ready_on_pro_with_database() -> None:
    now = datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc)
    status = build_lab_scheduler_status(
        db_available=True,
        placement=resolve_runtime_placement("Nuzantara", "nuzantara"),
        updated_at=now,
    )
    receipt = status.to_receipt()

    assert status.state is LabSchedulerState.READY
    assert status.can_tick is True
    assert receipt["tick_interval_seconds"] == DEFAULT_SCHEDULER_TICK_INTERVAL_SECONDS
    assert receipt["next_tick_not_before"] == "2026-06-17T12:01:00+00:00"
    assert receipt["autonomous_execution_allowed"] is False
    assert receipt["manual_promotion_required"] is True
    assert "no_deploy_merge_push" in receipt["safeguards"]


def test_scheduler_blocks_without_database_even_on_pro() -> None:
    status = build_lab_scheduler_status(
        db_available=False,
        placement=resolve_runtime_placement("Nuzantara", "nuzantara"),
    )

    assert status.state is LabSchedulerState.DB_UNAVAILABLE
    assert status.can_tick is False
    assert "database" in status.next_action


def test_scheduler_routes_air_m5_execution_to_pro() -> None:
    status = build_lab_scheduler_status(
        db_available=True,
        placement=resolve_runtime_placement("Air-M5", "balizero"),
    )
    receipt = status.to_receipt()

    assert status.state is LabSchedulerState.HOST_BLOCKED
    assert status.can_tick is False
    assert receipt["placement"]["machine_role"] == "air_m5_cockpit"
    assert receipt["placement"]["heavy_work_destination"] == "ssh pro"
    assert "ssh pro" in receipt["next_action"]


def test_scheduler_status_is_disabled_fail_closed() -> None:
    status = build_lab_scheduler_status(
        db_available=True,
        enabled=False,
        placement=resolve_runtime_placement("Nuzantara", "nuzantara"),
    )

    assert status.state is LabSchedulerState.DISABLED
    assert status.can_tick is False
    assert status.autonomous_execution_allowed is False
