import pytest
from organism.actuators import build_actuator_registry


@pytest.mark.asyncio
async def test_registry_has_all_four_actuators(fake_redis):
    reg = build_actuator_registry(redis=fake_redis)
    assert set(reg.keys()) == {"restart_agent", "cleanup_log", "notify_telegram", "quarantine"}


@pytest.mark.asyncio
async def test_quarantine_gets_redis_injected(fake_redis):
    reg = build_actuator_registry(redis=fake_redis)
    q = reg["quarantine"]
    assert q.redis is fake_redis


@pytest.mark.asyncio
async def test_other_actuators_are_construct_less(fake_redis):
    reg = build_actuator_registry(redis=fake_redis)
    for name in ("restart_agent", "cleanup_log", "notify_telegram"):
        actuator = reg[name]
        assert actuator.name == name
