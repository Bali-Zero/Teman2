import pytest
from pathlib import Path
from organism.schemas import ActionDecision, Event, Severity
from organism.supervisor.dispatch import (
    Dispatcher,
    DispatchOutcome,
    SAFE_ACTUATORS,
    HUMAN_ONLY_ACTUATORS,
)
from organism.supervisor.circuit_breaker import CircuitBreaker
from organism.supervisor.mutex import Mutex
from organism.blackout import BlackoutManager


def _decision(actuator="restart_agent", target="core-guardian"):
    return ActionDecision(
        actuator=actuator,
        params={"agent_ref": target},
        confidence=0.9,
        tier="L0_yaml",
        reasoning="test",
    )


@pytest.mark.asyncio
async def test_dispatch_shadow_mode_logs_only(fake_redis, tmp_path):
    d = Dispatcher(
        redis=fake_redis,
        circuit_breaker=CircuitBreaker(redis=fake_redis),
        mutex=Mutex(redis=fake_redis),
        blackout=BlackoutManager(flag_path=tmp_path / "pause.flag"),
        shadow_mode=True,
    )
    outcome = await d.dispatch(
        decision=_decision(),
        target="core-guardian",
        correlation_id="c",
    )
    assert outcome == DispatchOutcome.SHADOW_LOGGED


@pytest.mark.asyncio
async def test_dispatch_deferred_when_blackout_active(fake_redis, tmp_path):
    bm = BlackoutManager(flag_path=tmp_path / "pause.flag")
    bm.pause(minutes=5)
    d = Dispatcher(
        redis=fake_redis,
        circuit_breaker=CircuitBreaker(redis=fake_redis),
        mutex=Mutex(redis=fake_redis),
        blackout=bm,
        shadow_mode=False,
    )
    outcome = await d.dispatch(
        decision=_decision(), target="x", correlation_id="c",
    )
    assert outcome == DispatchOutcome.DEFERRED_BLACKOUT


@pytest.mark.asyncio
async def test_dispatch_deferred_when_circuit_breaker_tripped(fake_redis, tmp_path):
    cb = CircuitBreaker(redis=fake_redis, max_tries=1)
    await cb.record_failure("restart_agent:x")
    d = Dispatcher(
        redis=fake_redis,
        circuit_breaker=cb,
        mutex=Mutex(redis=fake_redis),
        blackout=BlackoutManager(flag_path=tmp_path / "pause.flag"),
        shadow_mode=False,
    )
    outcome = await d.dispatch(
        decision=_decision(), target="x", correlation_id="c",
    )
    assert outcome == DispatchOutcome.DEFERRED_CB


@pytest.mark.asyncio
async def test_dispatch_deferred_when_mutex_held(fake_redis, tmp_path):
    mutex = Mutex(redis=fake_redis)
    # Pre-hold the mutex for this target
    await mutex.acquire("restart_agent:x", ttl_seconds=300)
    d = Dispatcher(
        redis=fake_redis,
        circuit_breaker=CircuitBreaker(redis=fake_redis),
        mutex=mutex,
        blackout=BlackoutManager(flag_path=tmp_path / "pause.flag"),
        shadow_mode=False,
    )
    outcome = await d.dispatch(
        decision=_decision(), target="x", correlation_id="c",
    )
    assert outcome == DispatchOutcome.DEFERRED_MUTEX


@pytest.mark.asyncio
async def test_dispatch_awaiting_human_for_blacklisted_actuator(fake_redis, tmp_path):
    d = Dispatcher(
        redis=fake_redis,
        circuit_breaker=CircuitBreaker(redis=fake_redis),
        mutex=Mutex(redis=fake_redis),
        blackout=BlackoutManager(flag_path=tmp_path / "pause.flag"),
        shadow_mode=False,
    )
    # rollback_deploy is in HUMAN_ONLY_ACTUATORS
    outcome = await d.dispatch(
        decision=_decision(actuator="rollback_deploy"),
        target="some-target", correlation_id="c",
    )
    assert outcome == DispatchOutcome.AWAITING_HUMAN


@pytest.mark.asyncio
async def test_dispatch_unknown_actuator_rejected(fake_redis, tmp_path):
    d = Dispatcher(
        redis=fake_redis,
        circuit_breaker=CircuitBreaker(redis=fake_redis),
        mutex=Mutex(redis=fake_redis),
        blackout=BlackoutManager(flag_path=tmp_path / "pause.flag"),
        shadow_mode=False,
    )
    outcome = await d.dispatch(
        decision=_decision(actuator="bogus_actuator_not_in_any_set"),
        target="x", correlation_id="c",
    )
    assert outcome == DispatchOutcome.REJECTED_UNKNOWN
