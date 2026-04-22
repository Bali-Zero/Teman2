import pytest
from organism.supervisor.circuit_breaker import CircuitBreaker, CB_KEY_PREFIX


@pytest.mark.asyncio
async def test_first_call_is_allowed(fake_redis):
    cb = CircuitBreaker(redis=fake_redis)
    assert await cb.allow("restart_agent:core-guardian") is True


@pytest.mark.asyncio
async def test_blocks_after_two_failures(fake_redis):
    cb = CircuitBreaker(redis=fake_redis, max_tries=2)
    target = "restart_agent:core-guardian"
    assert await cb.allow(target) is True
    await cb.record_failure(target)
    assert await cb.allow(target) is True
    await cb.record_failure(target)
    # Third attempt blocked
    assert await cb.allow(target) is False


@pytest.mark.asyncio
async def test_record_success_resets_counter(fake_redis):
    cb = CircuitBreaker(redis=fake_redis, max_tries=2)
    target = "x"
    await cb.record_failure(target)
    await cb.record_failure(target)
    assert await cb.allow(target) is False
    await cb.record_success(target)
    # After success, counter cleared → next call allowed
    assert await cb.allow(target) is True


@pytest.mark.asyncio
async def test_cooldown_ttl_on_failure_record(fake_redis):
    cb = CircuitBreaker(redis=fake_redis, cooldown_seconds=900)
    await cb.record_failure("y")
    ttl = await fake_redis.ttl(CB_KEY_PREFIX + "y")
    # should be ~900 (15min)
    assert 890 <= ttl <= 900
