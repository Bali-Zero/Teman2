import pytest
from organism.schemas import Event, Severity
from organism.supervisor.yaml_rules import RuleMatcher


BASE_YAML = """
rules:
  - id: cron_agent_failure_restart
    match:
      kind: cron_agent_failure
      severity: [error, critical]
    action:
      actuator: restart_agent
      params:
        agent_ref: "{payload.agent}"
    confidence: 0.95

  - id: disk_fill_cleanup
    match:
      kind: disk_fill
      payload.percent_gte: 85
    action:
      actuator: cleanup_log
      params:
        min_age_days: 30
    confidence: 0.90
"""


def test_matches_cron_agent_failure():
    matcher = RuleMatcher.from_yaml_text(BASE_YAML)
    e = Event(severity=Severity.ERROR, source="s", kind="cron_agent_failure",
              payload={"agent": "core-guardian"}, correlation_id="c", host="Pro")
    decision = matcher.match(e)
    assert decision is not None
    assert decision.actuator == "restart_agent"
    assert decision.params["agent_ref"] == "core-guardian"
    assert decision.tier == "L0_yaml"


def test_no_match_returns_none():
    matcher = RuleMatcher.from_yaml_text(BASE_YAML)
    e = Event(severity=Severity.INFO, source="s", kind="unknown_kind",
              payload={}, correlation_id="c", host="Pro")
    assert matcher.match(e) is None


def test_ignores_is_actuation_events():
    matcher = RuleMatcher.from_yaml_text(BASE_YAML)
    e = Event(severity=Severity.ERROR, source="s", kind="cron_agent_failure",
              payload={"agent": "x"}, correlation_id="c", host="Pro",
              is_actuation=True)
    assert matcher.match(e) is None
