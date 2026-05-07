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


# ============================================================================
# W2: Active-mode actuator invocation (FASE 5)
# ============================================================================


class _RecordingActuator:
    """Test double — records its run() invocations without side effects."""

    def __init__(self, *, name: str, raises: Exception | None = None) -> None:
        self.name = name
        self.calls: list[dict] = []
        self._raises = raises

    async def run(self, *, params, correlation_id, dry_run=False):
        self.calls.append({
            "params": dict(params),
            "correlation_id": correlation_id,
            "dry_run": dry_run,
        })
        if self._raises is not None:
            raise self._raises
        return {"success": True, "fake": True}


@pytest.mark.asyncio
async def test_dispatch_active_invokes_actuator(fake_redis, tmp_path):
    """Active mode + DISPATCHED outcome → actuator.run() called once."""
    fake = _RecordingActuator(name="restart_agent")
    d = Dispatcher(
        redis=fake_redis,
        circuit_breaker=CircuitBreaker(redis=fake_redis),
        mutex=Mutex(redis=fake_redis),
        blackout=BlackoutManager(flag_path=tmp_path / "pause.flag"),
        shadow_mode=False,
        actuator_registry={"restart_agent": fake},
    )
    outcome = await d.dispatch(
        decision=_decision(),
        target="core-guardian",
        correlation_id="c1",
    )
    assert outcome == DispatchOutcome.DISPATCHED
    assert len(fake.calls) == 1
    assert fake.calls[0]["correlation_id"] == "c1"
    assert fake.calls[0]["dry_run"] is False
    assert fake.calls[0]["params"] == {"agent_ref": "core-guardian"}


@pytest.mark.asyncio
async def test_dispatch_shadow_does_not_invoke_actuator(fake_redis, tmp_path):
    """Shadow mode → actuator.run() must NOT be called."""
    fake = _RecordingActuator(name="restart_agent")
    d = Dispatcher(
        redis=fake_redis,
        circuit_breaker=CircuitBreaker(redis=fake_redis),
        mutex=Mutex(redis=fake_redis),
        blackout=BlackoutManager(flag_path=tmp_path / "pause.flag"),
        shadow_mode=True,
        actuator_registry={"restart_agent": fake},
    )
    outcome = await d.dispatch(
        decision=_decision(), target="x", correlation_id="c",
    )
    assert outcome == DispatchOutcome.SHADOW_LOGGED
    assert fake.calls == []


@pytest.mark.asyncio
async def test_dispatch_active_actuator_missing_in_registry(fake_redis, tmp_path):
    """Active + actuator in SAFE list but missing from registry → rejected."""
    d = Dispatcher(
        redis=fake_redis,
        circuit_breaker=CircuitBreaker(redis=fake_redis),
        mutex=Mutex(redis=fake_redis),
        blackout=BlackoutManager(flag_path=tmp_path / "pause.flag"),
        shadow_mode=False,
        actuator_registry={},  # empty: restart_agent not present
    )
    outcome = await d.dispatch(
        decision=_decision(), target="x", correlation_id="c",
    )
    assert outcome == DispatchOutcome.REJECTED_UNKNOWN


@pytest.mark.asyncio
async def test_dispatch_active_actuator_failure_records_cb(fake_redis, tmp_path):
    """Actuator raising → circuit breaker records failure, outcome DISPATCHED.

    The actuator's own `.run()` swallows exceptions and returns
    {"success": False, "error": ...}, so an exception bubbling up to the
    dispatcher is unexpected — but if it happens (registry test double
    raising), we still record a CB failure so subsequent dispatches against
    the same target back off, and we surface DISPATCHED with success=False
    via the actuator base class. We model it here by having the test double
    raise; the dispatcher must NOT crash.
    """
    boom = _RecordingActuator(name="restart_agent", raises=RuntimeError("boom"))
    cb = CircuitBreaker(redis=fake_redis, max_tries=2)
    d = Dispatcher(
        redis=fake_redis,
        circuit_breaker=cb,
        mutex=Mutex(redis=fake_redis),
        blackout=BlackoutManager(flag_path=tmp_path / "pause.flag"),
        shadow_mode=False,
        actuator_registry={"restart_agent": boom},
    )
    outcome = await d.dispatch(
        decision=_decision(), target="x", correlation_id="c",
    )
    # We treat actuator-raised exception as a failure but not a crash.
    assert outcome == DispatchOutcome.DISPATCHED
    assert len(boom.calls) == 1


@pytest.mark.asyncio
async def test_dispatch_active_calls_on_dispatched_callback(fake_redis, tmp_path):
    """Caller can register an `on_dispatched` callback for Telegram side-effects."""
    fake = _RecordingActuator(name="restart_agent")
    captured: list[dict] = []

    async def callback(*, decision, target, correlation_id, result):
        captured.append({
            "actuator": decision.actuator,
            "target": target,
            "correlation_id": correlation_id,
            "result": result,
        })

    d = Dispatcher(
        redis=fake_redis,
        circuit_breaker=CircuitBreaker(redis=fake_redis),
        mutex=Mutex(redis=fake_redis),
        blackout=BlackoutManager(flag_path=tmp_path / "pause.flag"),
        shadow_mode=False,
        actuator_registry={"restart_agent": fake},
        on_dispatched=callback,
    )
    outcome = await d.dispatch(
        decision=_decision(),
        target="core-guardian",
        correlation_id="c1",
    )
    assert outcome == DispatchOutcome.DISPATCHED
    assert len(captured) == 1
    assert captured[0]["actuator"] == "restart_agent"
    assert captured[0]["target"] == "core-guardian"


@pytest.mark.asyncio
async def test_dispatch_callback_failure_does_not_break_dispatch(fake_redis, tmp_path):
    """If callback raises, dispatch must still report DISPATCHED — Telegram is best-effort."""
    fake = _RecordingActuator(name="restart_agent")

    async def bad_callback(**kwargs):
        raise RuntimeError("telegram down")

    d = Dispatcher(
        redis=fake_redis,
        circuit_breaker=CircuitBreaker(redis=fake_redis),
        mutex=Mutex(redis=fake_redis),
        blackout=BlackoutManager(flag_path=tmp_path / "pause.flag"),
        shadow_mode=False,
        actuator_registry={"restart_agent": fake},
        on_dispatched=bad_callback,
    )
    outcome = await d.dispatch(
        decision=_decision(), target="x", correlation_id="c",
    )
    assert outcome == DispatchOutcome.DISPATCHED
    assert len(fake.calls) == 1
