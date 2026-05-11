"""Integration tests for FASE 5 W2 dispatch — end-to-end through run_once.

These cover the soft-canary scenarios from the FASE 5 brief Steps T2/T3
without needing a live daemon: exercise daemon.run_once with a real fakeredis
stream and a recording actuator double, then assert (a) the decision JSONL
matches the contract, (b) actuator was invoked once, (c) Telegram callback
fired once, (d) outcome is `dispatched`.
"""
from __future__ import annotations

import json

import pytest

from organism.schemas import Event, Severity
from organism.supervisor.daemon import run_once


class _RecordingActuator:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[dict] = []

    async def run(self, *, params, correlation_id, dry_run=False):
        self.calls.append({
            "params": dict(params),
            "correlation_id": correlation_id,
            "dry_run": dry_run,
        })
        return {"success": True, "fake": True}


class _RecordingNotifyTelegram:
    name = "notify_telegram"

    def __init__(self) -> None:
        self.messages: list[str] = []

    async def run(self, *, params, correlation_id, dry_run=False):
        self.messages.append(params["message"])
        return {"success": True}


@pytest.mark.asyncio
async def test_canary_t2_shadow_low_stakes_target(fake_redis, tmp_path):
    """T2-equivalent: emit a low-stakes event in SHADOW mode → no actuator,
    JSONL records shadow_logged outcome."""
    e = Event(
        severity=Severity.WARNING,
        source="canary.test",
        kind="cron_agent_failure",
        payload={"agent": "low-stakes-test-cron"},
        correlation_id="canary-t2",
        host="Pro",
    )
    await fake_redis.xadd("organism:events", {"data": e.model_dump_json()})

    rules_yaml = """rules:
  - id: r1
    match: {kind: cron_agent_failure}
    action: {actuator: restart_agent, params: {agent_ref: "{payload.agent}"}}
    confidence: 0.95
"""
    actuator = _RecordingActuator(name="restart_agent")
    decisions_log = tmp_path / "decisions.jsonl"

    await run_once(
        redis=fake_redis,
        rules_yaml=rules_yaml,
        decisions_log=decisions_log,
        shadow_mode=True,  # canonical T2 = shadow
        actuator_registry={"restart_agent": actuator},
        blackout_flag=tmp_path / "pause.flag",
    )

    assert actuator.calls == [], "shadow mode must NOT invoke actuator"
    entry = json.loads(decisions_log.read_text().strip().splitlines()[0])
    assert entry["actuator"] == "restart_agent"
    assert entry["target"] == "low-stakes-test-cron"
    assert entry["dispatch_outcome"] == "shadow_logged"
    assert entry["shadow_mode"] is True


@pytest.mark.asyncio
async def test_canary_t3_active_low_stakes_target_with_telegram(fake_redis, tmp_path):
    """T3-equivalent: kill switch ON, low-stakes target → actuator called once,
    Telegram alert fires once, JSONL records dispatched."""
    e = Event(
        severity=Severity.WARNING,
        source="canary.test",
        kind="cron_agent_failure",
        payload={"agent": "low-stakes-test-cron"},
        correlation_id="canary-t3",
        host="Pro",
    )
    await fake_redis.xadd("organism:events", {"data": e.model_dump_json()})

    rules_yaml = """rules:
  - id: r1
    match: {kind: cron_agent_failure}
    action: {actuator: restart_agent, params: {agent_ref: "{payload.agent}"}}
    confidence: 0.95
"""
    actuator = _RecordingActuator(name="restart_agent")
    notifier = _RecordingNotifyTelegram()
    registry = {"restart_agent": actuator, "notify_telegram": notifier}

    from organism.supervisor.telegram_alert import build_dispatch_alerter
    alerter = build_dispatch_alerter(registry)

    decisions_log = tmp_path / "decisions.jsonl"

    await run_once(
        redis=fake_redis,
        rules_yaml=rules_yaml,
        decisions_log=decisions_log,
        shadow_mode=False,  # kill switch ON
        actuator_registry=registry,
        blackout_flag=tmp_path / "pause.flag",
        on_dispatched=alerter,
    )

    # Actuator invoked exactly once with expected params
    assert len(actuator.calls) == 1
    assert actuator.calls[0]["correlation_id"] == "canary-t3"
    assert actuator.calls[0]["params"]["agent_ref"] == "low-stakes-test-cron"

    # Telegram alert fired exactly once with success marker
    assert len(notifier.messages) == 1
    msg = notifier.messages[0]
    assert "restart_agent" in msg
    assert "low-stakes-test-cron" in msg
    assert "✅" in msg or "success" in msg.lower()

    # JSONL contract
    entry = json.loads(decisions_log.read_text().strip().splitlines()[0])
    assert entry["dispatch_outcome"] == "dispatched"
    assert entry["target"] == "low-stakes-test-cron"
    assert entry["shadow_mode"] is False


@pytest.mark.asyncio
async def test_canary_blackout_blocks_active_dispatch(fake_redis, tmp_path):
    """Operator paused via blackout flag → DEFERRED_BLACKOUT, no actuator."""
    e = Event(
        severity=Severity.WARNING,
        source="canary.test",
        kind="cron_agent_failure",
        payload={"agent": "test"},
        correlation_id="canary-blackout",
        host="Pro",
    )
    await fake_redis.xadd("organism:events", {"data": e.model_dump_json()})

    from organism.blackout import BlackoutManager
    blackout_flag = tmp_path / "pause.flag"
    BlackoutManager(flag_path=blackout_flag).pause(minutes=5)

    actuator = _RecordingActuator(name="restart_agent")
    notifier = _RecordingNotifyTelegram()

    rules_yaml = """rules:
  - id: r1
    match: {kind: cron_agent_failure}
    action: {actuator: restart_agent, params: {agent_ref: "{payload.agent}"}}
    confidence: 0.95
"""
    decisions_log = tmp_path / "decisions.jsonl"

    await run_once(
        redis=fake_redis,
        rules_yaml=rules_yaml,
        decisions_log=decisions_log,
        shadow_mode=False,
        actuator_registry={"restart_agent": actuator, "notify_telegram": notifier},
        blackout_flag=blackout_flag,
    )

    assert actuator.calls == [], "blackout must skip actuator invocation"
    assert notifier.messages == [], "blackout must skip telegram alert"

    entry = json.loads(decisions_log.read_text().strip().splitlines()[0])
    assert entry["dispatch_outcome"] == "deferred_blackout"
