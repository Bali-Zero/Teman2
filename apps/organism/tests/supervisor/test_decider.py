import pytest
from organism.schemas import Event, Severity
from organism.supervisor.decider import Decider
from organism.supervisor.yaml_rules import RuleMatcher
from organism.supervisor.incident_context import IncidentStore


BASE_YAML = """
rules:
  - id: r1
    match: {kind: cron_agent_failure}
    action: {actuator: restart_agent, params: {agent_ref: "{payload.agent}"}}
    confidence: 0.95
"""


@pytest.mark.asyncio
async def test_l0_match_returns_yaml_decision(fake_redis):
    decider = Decider(
        matcher=RuleMatcher.from_yaml_text(BASE_YAML),
        incident_store=IncidentStore(redis=fake_redis),
    )
    e = Event(severity=Severity.ERROR, source="s", kind="cron_agent_failure",
              payload={"agent": "foo"}, correlation_id="c", host="Pro")
    decision = await decider.decide(e)
    assert decision.tier == "L0_yaml"
    assert decision.actuator == "restart_agent"


@pytest.mark.asyncio
async def test_l0_no_match_returns_defer_decision(fake_redis):
    decider = Decider(
        matcher=RuleMatcher.from_yaml_text(BASE_YAML),
        incident_store=IncidentStore(redis=fake_redis),
    )
    e = Event(severity=Severity.INFO, source="s", kind="unknown",
              payload={}, correlation_id="c", host="Pro")
    decision = await decider.decide(e)
    assert decision.actuator == "defer_to_human"
