import pytest
from organism.supervisor.mutex import Mutex, MUTEX_KEY_PREFIX


@pytest.mark.asyncio
async def test_acquire_returns_lock_id_when_free(fake_redis):
    m = Mutex(redis=fake_redis)
    lock_id = await m.acquire("target-1", ttl_seconds=300)
    assert lock_id is not None
    assert len(lock_id) > 8


@pytest.mark.asyncio
async def test_acquire_returns_none_when_locked(fake_redis):
    m = Mutex(redis=fake_redis)
    first = await m.acquire("target-2", ttl_seconds=300)
    assert first is not None
    second = await m.acquire("target-2", ttl_seconds=300)
    assert second is None


@pytest.mark.asyncio
async def test_release_only_if_owner(fake_redis):
    m = Mutex(redis=fake_redis)
    lock_id = await m.acquire("target-3", ttl_seconds=300)
    # Wrong owner attempt
    assert await m.release("target-3", "not-the-owner") is False
    # Correct owner
    assert await m.release("target-3", lock_id) is True
    # Now reacquire works
    assert await m.acquire("target-3", ttl_seconds=300) is not None
