"""Scenario 7: Pro<->Air network partition. Heartbeat from Supervisor
can't reach Air. Guardian on Air detects stale heartbeat and enters
local_emergency_mode (W0.3 SPOF prevention).
"""
import pytest
import time
from organism.heartbeat import supervisor_heartbeat_check, SUPERVISOR_HB_KEY


@pytest.mark.gauntlet
@pytest.mark.asyncio
async def test_gauntlet_07_network_partition(staging_organism):
    # Simulate stale heartbeat (written 10 minutes ago, Pro-Air partition
    # means Air can see the old value but Supervisor on Pro can't refresh it
    # because Air's Redis is unreachable from Pro — or vice versa).
    stale_ts = time.time() - 600
    await staging_organism.redis.set(SUPERVISOR_HB_KEY, str(stale_ts).encode())

    status = await supervisor_heartbeat_check(
        redis=staging_organism.redis, max_lag_seconds=300,
    )
    assert status.supervisor_alive is False
    assert status.should_enter_emergency_mode is True


@pytest.mark.gauntlet
@pytest.mark.asyncio
async def test_gauntlet_07b_partition_recovery(staging_organism):
    """After partition heals, Supervisor writes fresh heartbeat and
    guardian exits local_emergency_mode on next cycle."""
    stale_ts = time.time() - 600
    await staging_organism.redis.set(SUPERVISOR_HB_KEY, str(stale_ts).encode())
    # Supervisor recovers and writes fresh heartbeat via run_once
    await staging_organism.drive_supervisor()
    status = await supervisor_heartbeat_check(
        redis=staging_organism.redis, max_lag_seconds=300,
    )
    assert status.supervisor_alive is True, "Supervisor didn't refresh heartbeat after recovery"
