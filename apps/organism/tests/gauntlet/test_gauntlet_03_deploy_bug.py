"""Scenario 3: a broken deploy lands in prod. deploy_failure event fires.
Supervisor decides rollback_deploy. Rollback is L3 IRREVERSIBLE — Supervisor
dispatch layer would route through Consiglio, but at the L0 decider level
we just verify the rule matched and produced the right actuator name.
"""
import pytest
from organism.schemas import Severity


@pytest.mark.gauntlet
@pytest.mark.asyncio
async def test_gauntlet_03_deploy_bug(staging_organism):
    staging_organism.inject_crash("deploy")
    await staging_organism.emit(
        kind="deploy_failure",
        source="guardian.fly_watcher",
        severity=Severity.CRITICAL,
        payload={"target": "nuzantara-rag", "version": "v1.2.3", "exit_code": 137},
    )

    await staging_organism.drive_supervisor()

    decisions = staging_organism.decisions_for_actuator("rollback_deploy")
    assert len(decisions) == 1, (
        f"MTTR: Supervisor did not decide rollback_deploy after deploy_failure: "
        f"decisions={staging_organism.decisions()}"
    )
    assert decisions[0]["tier"] == "L0_yaml"
