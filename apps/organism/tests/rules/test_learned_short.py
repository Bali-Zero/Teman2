"""Auto-generated test for learned rule short.

Loads the learned YAML rule and asserts it correctly matches the kind
it was proposed for. Regenerating this test is safe — the propose_yaml_rule
actuator will overwrite both files as a pair.
"""
import pytest
from pathlib import Path
from organism.supervisor.yaml_rules import RuleMatcher
from organism.schemas import Event, Severity


LEARNED_DIR = Path(__file__).resolve().parents[2] / "organism" / "rules" / "learned"


def _load_rule_text() -> str:
    for path in LEARNED_DIR.glob("*-short.yaml"):
        return path.read_text(encoding="utf-8")
    raise FileNotFoundError("learned rule file for short not found")


def test_learned_rule_short_matches_expected_kind():
    matcher = RuleMatcher.from_yaml_text(_load_rule_text())
    event = Event(
        severity=Severity.ERROR,
        source="guardian.test",
        kind='custom_probe_event',
        payload={"probe": "value"},
        correlation_id="c-test",
        host="Pro",
    )
    decision = matcher.match(event)
    assert decision is not None, "learned rule did not match its intended kind"
    assert decision.tier == "L0_yaml"
