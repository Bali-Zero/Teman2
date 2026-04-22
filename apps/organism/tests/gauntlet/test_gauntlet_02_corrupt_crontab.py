"""Scenario 2: crontab is corrupted. cron-agent job fails, emits
cron_agent_failure, Supervisor matches restart rule.
"""
import pytest
from organism.schemas import Severity


@pytest.mark.gauntlet
@pytest.mark.asyncio
async def test_gauntlet_02_corrupt_crontab(staging_organism):
    staging_organism.inject_crash("crontab")
    await staging_organism.emit(
        kind="cron_agent_failure",
        source="guardian.system_doctor",
        severity=Severity.ERROR,
        payload={
            "agent": "drive-poll",
            "line": "ERROR crontab syntax",
            "log_path": "/Users/nuzantara/logs/cron-agent/drive-poll.log",
        },
    )

    await staging_organism.drive_supervisor()

    decisions = staging_organism.decisions_for_actuator("restart_agent")
    assert len(decisions) == 1
    # Supervisor should have extracted the agent name
    events = await staging_organism.events_of_kind("cron_agent_failure")
    assert events and events[0]["payload"]["agent"] == "drive-poll"
