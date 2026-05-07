import pytest
import json
import time
from organism.schemas import Event, Severity
from organism.supervisor.daemon import run_once, SUPERVISOR_HB_KEY


@pytest.mark.asyncio
async def test_run_once_processes_pending_events_and_logs_decision(fake_redis, tmp_path):
    e = Event(severity=Severity.ERROR, source="s", kind="cron_agent_failure",
              payload={"agent": "foo"}, correlation_id="c", host="Pro")
    await fake_redis.xadd("organism:events", {"data": e.model_dump_json()})

    decisions_log = tmp_path / "decisions.jsonl"
    rules_yaml = """rules:
  - id: r1
    match: {kind: cron_agent_failure}
    action: {actuator: restart_agent, params: {agent_ref: "{payload.agent}"}}
    confidence: 0.95
"""
    processed = await run_once(
        redis=fake_redis,
        rules_yaml=rules_yaml,
        decisions_log=decisions_log,
        shadow_mode=True,
    )
    assert processed >= 1
    lines = decisions_log.read_text().strip().splitlines()
    assert len(lines) >= 1
    entry = json.loads(lines[0])
    assert entry["actuator"] == "restart_agent"
    assert entry["shadow_mode"] is True


@pytest.mark.asyncio
async def test_run_once_writes_heartbeat(fake_redis, tmp_path):
    await run_once(
        redis=fake_redis,
        rules_yaml="rules: []",
        decisions_log=tmp_path / "d.jsonl",
        shadow_mode=True,
    )
    hb = await fake_redis.get(SUPERVISOR_HB_KEY)
    assert hb is not None
    ts = float(hb)
    assert abs(time.time() - ts) < 5


# ============================================================================
# W2 active-mode tests (FASE 5)
# ============================================================================


class _RecordingActuator:
    """Test double for actuator registry — records calls."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[dict] = []

    async def run(self, *, params, correlation_id, dry_run=False):
        self.calls.append({
            "params": dict(params),
            "correlation_id": correlation_id,
            "dry_run": dry_run,
        })
        return {"success": True}


@pytest.mark.asyncio
async def test_run_once_active_mode_invokes_actuator(fake_redis, tmp_path):
    """W2: shadow_mode=False + actuator_registry → real run() called."""
    e = Event(severity=Severity.ERROR, source="s", kind="cron_agent_failure",
              payload={"agent": "foo"}, correlation_id="c-active", host="Pro")
    await fake_redis.xadd("organism:events", {"data": e.model_dump_json()})

    rules_yaml = """rules:
  - id: r1
    match: {kind: cron_agent_failure}
    action: {actuator: restart_agent, params: {agent_ref: "{payload.agent}"}}
    confidence: 0.95
"""
    fake = _RecordingActuator(name="restart_agent")
    decisions_log = tmp_path / "decisions.jsonl"
    blackout_flag = tmp_path / "pause.flag"

    processed = await run_once(
        redis=fake_redis,
        rules_yaml=rules_yaml,
        decisions_log=decisions_log,
        shadow_mode=False,
        actuator_registry={"restart_agent": fake},
        blackout_flag=blackout_flag,
    )
    assert processed >= 1
    assert len(fake.calls) == 1
    assert fake.calls[0]["correlation_id"] == "c-active"
    assert fake.calls[0]["params"]["agent_ref"] == "foo"
    assert fake.calls[0]["dry_run"] is False

    entry = json.loads(decisions_log.read_text().strip().splitlines()[0])
    assert entry["actuator"] == "restart_agent"
    assert entry["shadow_mode"] is False
    assert entry["dispatch_outcome"] == "dispatched"


@pytest.mark.asyncio
async def test_run_once_shadow_does_not_invoke_actuator(fake_redis, tmp_path):
    """Shadow mode: actuator MUST NOT be called even if registry provided."""
    e = Event(severity=Severity.ERROR, source="s", kind="cron_agent_failure",
              payload={"agent": "foo"}, correlation_id="c-shadow", host="Pro")
    await fake_redis.xadd("organism:events", {"data": e.model_dump_json()})

    rules_yaml = """rules:
  - id: r1
    match: {kind: cron_agent_failure}
    action: {actuator: restart_agent, params: {agent_ref: "{payload.agent}"}}
    confidence: 0.95
"""
    fake = _RecordingActuator(name="restart_agent")
    processed = await run_once(
        redis=fake_redis,
        rules_yaml=rules_yaml,
        decisions_log=tmp_path / "d.jsonl",
        shadow_mode=True,
        actuator_registry={"restart_agent": fake},
        blackout_flag=tmp_path / "pause.flag",
    )
    assert processed >= 1
    assert fake.calls == []


@pytest.mark.asyncio
async def test_run_once_active_invokes_on_dispatched_callback(fake_redis, tmp_path):
    """W2 Telegram path: on_dispatched fires once per DISPATCHED outcome."""
    e = Event(severity=Severity.ERROR, source="s", kind="cron_agent_failure",
              payload={"agent": "foo"}, correlation_id="c-cb", host="Pro")
    await fake_redis.xadd("organism:events", {"data": e.model_dump_json()})

    rules_yaml = """rules:
  - id: r1
    match: {kind: cron_agent_failure}
    action: {actuator: restart_agent, params: {agent_ref: "{payload.agent}"}}
    confidence: 0.95
"""
    fake = _RecordingActuator(name="restart_agent")
    captured: list[dict] = []

    async def cb(*, decision, target, correlation_id, result):
        captured.append({
            "actuator": decision.actuator,
            "target": target,
            "correlation_id": correlation_id,
            "success": result.get("success"),
        })

    await run_once(
        redis=fake_redis,
        rules_yaml=rules_yaml,
        decisions_log=tmp_path / "d.jsonl",
        shadow_mode=False,
        actuator_registry={"restart_agent": fake},
        blackout_flag=tmp_path / "pause.flag",
        on_dispatched=cb,
    )
    assert len(captured) == 1
    assert captured[0]["actuator"] == "restart_agent"
    assert captured[0]["correlation_id"] == "c-cb"
    assert captured[0]["success"] is True


@pytest.mark.asyncio
async def test_run_once_active_with_blackout_does_not_invoke_actuator(fake_redis, tmp_path):
    """Blackout flag set → DEFERRED_BLACKOUT, actuator NOT called."""
    e = Event(severity=Severity.ERROR, source="s", kind="cron_agent_failure",
              payload={"agent": "foo"}, correlation_id="c-blk", host="Pro")
    await fake_redis.xadd("organism:events", {"data": e.model_dump_json()})

    rules_yaml = """rules:
  - id: r1
    match: {kind: cron_agent_failure}
    action: {actuator: restart_agent, params: {agent_ref: "{payload.agent}"}}
    confidence: 0.95
"""
    from organism.blackout import BlackoutManager
    blackout_flag = tmp_path / "pause.flag"
    BlackoutManager(flag_path=blackout_flag).pause(minutes=5)

    fake = _RecordingActuator(name="restart_agent")
    processed = await run_once(
        redis=fake_redis,
        rules_yaml=rules_yaml,
        decisions_log=tmp_path / "d.jsonl",
        shadow_mode=False,
        actuator_registry={"restart_agent": fake},
        blackout_flag=blackout_flag,
    )
    assert processed >= 1
    assert fake.calls == []


@pytest.mark.asyncio
async def test_run_once_active_defer_to_human_does_not_invoke_actuator(fake_redis, tmp_path):
    """No rule match → defer_to_human → no actuator invoked, no Telegram callback."""
    e = Event(severity=Severity.INFO, source="s", kind="scheduled_tick",
              payload={"hour": 12}, correlation_id="c-defer", host="Pro")
    await fake_redis.xadd("organism:events", {"data": e.model_dump_json()})

    fake = _RecordingActuator(name="restart_agent")
    captured: list = []

    async def cb(**_):
        captured.append(1)

    await run_once(
        redis=fake_redis,
        rules_yaml="rules: []",  # no matching rule
        decisions_log=tmp_path / "d.jsonl",
        shadow_mode=False,
        actuator_registry={"restart_agent": fake},
        blackout_flag=tmp_path / "pause.flag",
        on_dispatched=cb,
    )
    assert fake.calls == []
    assert captured == []
