import pytest
from organism.actuators import build_actuator_registry


# W1 baseline actuators — always present. Using subset check (>=) keeps this
# test merge-safe when W3/W4 parallel PRs land their own actuators alongside.
W1_BASELINE = {"restart_agent", "cleanup_log", "notify_telegram", "quarantine"}


@pytest.mark.asyncio
async def test_registry_has_all_baseline_actuators(fake_redis):
    reg = build_actuator_registry(redis=fake_redis)
    assert set(reg.keys()) >= W1_BASELINE


@pytest.mark.asyncio
async def test_registry_includes_adopt_module(fake_redis):
    """W3.A — adopt_module is wired with redis injection."""
    reg = build_actuator_registry(redis=fake_redis)
    assert "adopt_module" in reg
    assert reg["adopt_module"].name == "adopt_module"


@pytest.mark.asyncio
async def test_registry_includes_consolidate_redundancy(fake_redis):
    """W3.C — consolidate_redundancy is wired into the shared registry."""
    reg = build_actuator_registry(redis=fake_redis)
    assert "consolidate_redundancy" in reg
    assert reg["consolidate_redundancy"].name == "consolidate_redundancy"


@pytest.mark.asyncio
async def test_registry_includes_cleanup_suite(fake_redis):
    """W3.B — cleanup_cache / cleanup_branches / cleanup_zombie_plist wired."""
    reg = build_actuator_registry(redis=fake_redis)
    assert {"cleanup_cache", "cleanup_branches", "cleanup_zombie_plist"} <= set(reg.keys())


@pytest.mark.asyncio
async def test_registry_includes_propose_yaml_rule(fake_redis):
    """W4.A — propose_yaml_rule is wired (zero-arg, shells out to git/gh)."""
    reg = build_actuator_registry(redis=fake_redis)
    assert "propose_yaml_rule" in reg
    assert reg["propose_yaml_rule"].name == "propose_yaml_rule"


@pytest.mark.asyncio
async def test_quarantine_gets_redis_injected(fake_redis):
    reg = build_actuator_registry(redis=fake_redis)
    q = reg["quarantine"]
    assert q.redis is fake_redis


@pytest.mark.asyncio
async def test_adopt_module_gets_redis_injected(fake_redis):
    reg = build_actuator_registry(redis=fake_redis)
    a = reg["adopt_module"]
    assert a.redis is fake_redis


@pytest.mark.asyncio
async def test_other_actuators_are_construct_less(fake_redis):
    reg = build_actuator_registry(redis=fake_redis)
    for name in ("restart_agent", "cleanup_log", "notify_telegram"):
        actuator = reg[name]
        assert actuator.name == name
