"""Scenario 8: clock drifts +5 minutes on Air relative to Pro.
Events emitted with Air timestamp will appear in the future from Pro's
perspective. Supervisor must still process them (timestamps are
informational, not gating).
"""
import pytest
from datetime import datetime, timezone, timedelta
from organism.schemas import Severity


@pytest.mark.gauntlet
@pytest.mark.asyncio
async def test_gauntlet_08_clock_skew(staging_organism):
    # Emit with a future timestamp (+5 min)
    future_ts = datetime.now(timezone.utc) + timedelta(minutes=5)
    await staging_organism.emit(
        kind="cron_agent_failure",
        source="guardian.system_doctor",
        severity=Severity.ERROR,
        payload={"agent": "air_cron", "observed_ts_utc": future_ts.isoformat()},
    )

    await staging_organism.drive_supervisor()

    # Rule must still match (timestamp is payload data, not filter criterion)
    decisions = staging_organism.decisions_for_actuator("restart_agent")
    assert len(decisions) == 1, "Clock skew should not gate Supervisor decisions"
