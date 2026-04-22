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
