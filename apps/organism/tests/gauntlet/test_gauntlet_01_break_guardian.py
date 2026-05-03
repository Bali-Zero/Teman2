"""Scenario 1: a guardian is intentionally crashed. zombie_hunter detects,
emits zombie_detected, Supervisor L0 matches the zombie rule and decides
to dispatch restart_agent.
"""
import pytest
from organism.schemas import Severity


@pytest.mark.gauntlet
@pytest.mark.asyncio
async def test_gauntlet_01_break_guardian(staging_organism):
    staging_organism.inject_crash("system_doctor")
    # Simulate zombie_hunter detecting the crashed guardian
    await staging_organism.emit(
        kind="zombie_detected",
        source="guardian.zombie_hunter",
        severity=Severity.CRITICAL,
        payload={"agent": "system_doctor", "consecutive_exit1": 3},
    )

    await staging_organism.drive_supervisor()

    decisions = staging_organism.decisions_for_actuator("restart_agent")
    assert len(decisions) == 1, (
        f"MTTR: Supervisor did not decide restart_agent for crashed guardian: "
        f"decisions={staging_organism.decisions()}"
    )
    assert decisions[0]["tier"] == "L0_yaml"
