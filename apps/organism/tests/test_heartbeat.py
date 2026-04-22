import pytest
import time
from organism.heartbeat import supervisor_heartbeat_check, SUPERVISOR_HB_KEY


@pytest.mark.asyncio
async def test_healthy_when_recent_heartbeat(fake_redis):
    await fake_redis.set(SUPERVISOR_HB_KEY, str(time.time()).encode())
    result = await supervisor_heartbeat_check(redis=fake_redis, max_lag_seconds=300)
    assert result.supervisor_alive is True
    assert result.should_enter_emergency_mode is False


@pytest.mark.asyncio
async def test_emergency_when_lag_exceeds_threshold(fake_redis):
    stale = time.time() - 600  # 10 min ago
    await fake_redis.set(SUPERVISOR_HB_KEY, str(stale).encode())
    result = await supervisor_heartbeat_check(redis=fake_redis, max_lag_seconds=300)
    assert result.supervisor_alive is False
    assert result.should_enter_emergency_mode is True


@pytest.mark.asyncio
async def test_emergency_when_no_heartbeat_ever(fake_redis):
    result = await supervisor_heartbeat_check(redis=fake_redis, max_lag_seconds=300)
    assert result.should_enter_emergency_mode is True


@pytest.mark.asyncio
async def test_emergency_when_heartbeat_is_malformed(fake_redis):
    """Non-numeric heartbeat value must be treated as no heartbeat."""
    await fake_redis.set(SUPERVISOR_HB_KEY, b"not-a-timestamp")
    result = await supervisor_heartbeat_check(redis=fake_redis, max_lag_seconds=300)
    assert result.should_enter_emergency_mode is True


@pytest.mark.asyncio
async def test_lag_seconds_computed_correctly(fake_redis):
    """lag_seconds returns how old the heartbeat is."""
    ts = time.time() - 120  # 2 min ago
    await fake_redis.set(SUPERVISOR_HB_KEY, str(ts).encode())
    result = await supervisor_heartbeat_check(redis=fake_redis, max_lag_seconds=300)
    assert result.lag_seconds is not None
    assert 110 <= result.lag_seconds <= 130  # some slack for test time
