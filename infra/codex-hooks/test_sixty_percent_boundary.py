# ruff: noqa: F811
"""SAETTA's declared 60% boundary for each parent role and native children.

These are synthetic token events in isolated test state, not real LLM usage.
The current-window denominator and exact boundary are exercised through hook().
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import context_bridge as bridge
from test_child_lifecycle import child_transcript
from test_context_bridge import setup, token  # noqa: F401


def declare_sixty_percent() -> None:
    policy_path = bridge.codex_home() / "nuzantara-context-policy.json"
    policy = bridge.load(policy_path)
    policy["thresholds"] = {role: 0.6 for role in ("imperator", "builder", "dux")}
    bridge.save(policy_path, policy)


@pytest.mark.parametrize("role", ["imperator", "builder", "dux"])
@pytest.mark.parametrize("used", [500, 599, 600, 601])
def test_parent_sixty_percent_boundary(
    setup: tuple, monkeypatch: pytest.MonkeyPatch, role: str, used: int
) -> None:
    _, log, initial = setup
    declare_sixty_percent()
    monkeypatch.setenv("CODEX_CONTEXT_ROLE", role)
    event = {**initial, "session_id": f"boundary-{role}-{used}"}
    bridge.hook(event)
    token(log, used, 1000)
    result = bridge.hook(
        {**event, "hook_event_name": "PreToolUse", "tool_name": "Read"}
    )
    state = bridge.load(bridge.state_path(event["session_id"]))
    assert (state["role"], state["used"], state["window"]) == (role, used, 1000)
    denied = result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
    assert denied is (used >= 600)


@pytest.mark.parametrize("used", [500, 599, 600, 601])
@pytest.mark.parametrize("parent_rollover", [True, False])
def test_native_child_sixty_percent_boundary(
    setup: tuple, used: int, parent_rollover: bool
) -> None:
    _, log, event = setup
    declare_sixty_percent()
    policy_path = bridge.codex_home() / "nuzantara-context-policy.json"
    policy = bridge.load(policy_path)
    policy["parent_rollover_enabled"] = parent_rollover
    bridge.save(policy_path, policy)
    child = f"boundary-child-{used}"
    child_transcript(log, child, event["session_id"])
    bridge.hook({**event, "agent_id": child, "hook_event_name": "SubagentStart"})
    # Append after SubagentStart: inherited parent tokens are outside this child.
    with log.open("a") as stream:
        stream.write(
            json.dumps(
                {
                    "type": "event_msg",
                    "timestamp": f"child-{used}",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "model_context_window": 1000,
                            "last_token_usage": {"total_tokens": used},
                            "total_token_usage": {"total_tokens": 99999999},
                        },
                    },
                }
            )
            + "\n"
        )
    result = bridge.hook(
        {
            **event,
            "agent_id": child,
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
        }
    )
    state = bridge.load(bridge.state_path(child))
    assert (state["role"], state["used"], state["window"]) == ("builder", used, 1000)
    assert state["topology"] == "child"
    assert state.get("return_required", False) is (used >= 600)
    denied = result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"
    assert denied is (used >= 600)
