"""Scenario 4: disk fills to 90%. system_doctor emits disk_fill.
Supervisor matches the >=85% threshold rule and decides cleanup_log.
"""
import pytest
from organism.schemas import Severity


@pytest.mark.gauntlet
@pytest.mark.asyncio
async def test_gauntlet_04_disk_fill(staging_organism):
    staging_organism.inject_crash("disk_full")
    await staging_organism.emit(
        kind="disk_fill",
        source="guardian.system_doctor",
        severity=Severity.WARNING,
        payload={"volume": "/data", "percent": 92, "free_bytes": 1024 * 1024 * 100},
    )

    await staging_organism.drive_supervisor()

    decisions = staging_organism.decisions_for_actuator("cleanup_log")
    assert len(decisions) == 1
    assert decisions[0]["tier"] == "L0_yaml"


@pytest.mark.gauntlet
@pytest.mark.asyncio
async def test_gauntlet_04b_disk_below_threshold(staging_organism):
    """Edge case: 80% (below 85% threshold) — rule must NOT match."""
    await staging_organism.emit(
        kind="disk_fill",
        source="guardian.system_doctor",
        severity=Severity.INFO,
        payload={"volume": "/data", "percent": 80},
    )

    await staging_organism.drive_supervisor()

    # cleanup_log not triggered; either defer_to_human or no decision
    decisions = staging_organism.decisions_for_actuator("cleanup_log")
    assert len(decisions) == 0, (
        "cleanup_log fired at 80% disk fill — threshold misconfigured"
    )
