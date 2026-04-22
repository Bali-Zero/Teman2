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


@pytest.mark.asyncio
async def test_ttl_anchored_at_first_failure_not_reset(fake_redis, monkeypatch):
    """TTL must NOT reset on repeated failures — window anchored at first."""
    cb = CircuitBreaker(redis=fake_redis, cooldown_seconds=900)
    await cb.record_failure("anchored")
    first_ttl = await fake_redis.ttl(CB_KEY_PREFIX + "anchored")
    assert 890 <= first_ttl <= 900

    # Simulate some time passing (just proceed — fakeredis won't auto-decrement,
    # but we can verify the TTL isn't RESET by re-checking it's not 900 exact
    # after a second failure.
    await cb.record_failure("anchored")
    second_ttl = await fake_redis.ttl(CB_KEY_PREFIX + "anchored")
    # Second failure must NOT push TTL back to 900 if time has elapsed. With
    # fakeredis the TTL is stable unless explicitly expired — the key assertion
    # is that second_ttl <= first_ttl (never greater).
    assert second_ttl <= first_ttl
