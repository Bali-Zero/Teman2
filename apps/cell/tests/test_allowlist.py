"""Tests for action allowlist."""
from cell.effectors.allowlist import ActionRegistry, ActionNotAllowed

def test_known_action_allowed():
    registry = ActionRegistry()
    action = registry.get("check_health")
    assert action is not None
    assert action.name == "check_health"

def test_unknown_action_rejected():
    registry = ActionRegistry()
    try:
        registry.get("hack_pentagon")
        assert False, "Should have raised"
    except ActionNotAllowed:
        pass

def test_restart_has_cooldown():
    registry = ActionRegistry()
    action = registry.get("restart_service")
    assert action.cooldown_seconds == 3600
    assert action.max_per_day == 3

def test_alert_human_always_allowed():
    registry = ActionRegistry()
    action = registry.get("alert_human")
    assert action.cooldown_seconds == 300
    assert action.max_per_day == 20

def test_all_actions_have_cooldowns():
    registry = ActionRegistry()
    for name, action in registry.all().items():
        assert action.cooldown_seconds >= 0, f"{name} missing cooldown"
        assert action.max_per_day > 0, f"{name} missing max_per_day"
