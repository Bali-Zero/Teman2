"""Behavioral regression tests; no cloud calls or real session mutations."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import context_bridge as bridge


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, dict]:
    seat = tmp_path / "seat"
    seat.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(seat))
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    bridge.save(
        seat / "nuzantara-context-policy.json", {"enabled": True, "roots": [str(repo)]}
    )
    log = tmp_path / "rollout.jsonl"
    log.write_text("")
    event = {
        "session_id": "source-session-123",
        "cwd": str(repo),
        "transcript_path": str(log),
        "hook_event_name": "SessionStart",
    }
    bridge.hook(event)
    return repo, log, event


def token(log: Path, used: int, window: int | None, total: int = 99999999) -> None:
    log.write_text(
        json.dumps(
            {
                "type": "event_msg",
                "timestamp": "2026-09-09T05:00:00Z",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "model_context_window": window,
                        "last_token_usage": {"total_tokens": used},
                        "total_token_usage": {"total_tokens": total},
                    },
                },
            }
        )
        + "\n"
    )


def test_uses_current_window_not_lifetime_or_claude_environment(
    setup: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, log, e = setup
    monkeypatch.setenv("CONTEXT_WINDOW_TOKENS", "1000000")
    token(log, 401, 1000)
    out = bridge.hook({**e, "hook_event_name": "PreToolUse", "tool_name": "Bash"})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert bridge.measure(str(log))["window"] == 1000


@pytest.mark.parametrize("window,used", [(None, 500000), (1000, 399)])
def test_missing_or_below_threshold_never_blocks(
    setup: tuple, window: int, used: int
) -> None:
    _, log, e = setup
    token(log, used, window)
    assert bridge.hook({**e, "hook_event_name": "PreToolUse"}) == {}


def test_postcompact_does_not_reuse_stale_measurement(setup: tuple) -> None:
    _, log, e = setup
    token(log, 401, 1000)
    bridge.hook({**e, "hook_event_name": "PostCompact"})
    assert bridge.hook({**e, "hook_event_name": "PreToolUse"}) == {}


def test_unrelated_session_cannot_claim_handoff(setup: tuple) -> None:
    _, _, e = setup
    bridge.checkpoint(
        e["session_id"], {"objective": "Fix retry", "next_action": "Run focused tests"}
    )
    bridge.hook({**e, "session_id": "unrelated-session-456"})
    assert "checkpoint" not in bridge.load(bridge.state_path("unrelated-session-456"))


def test_actual_exit_status_and_edits_invalidate_proof(setup: tuple) -> None:
    repo, _, e = setup
    sid = e["session_id"]
    (repo / "new.py").write_text("x = 1\n")
    fail = bridge.verify(
        sid, {"commands": [[sys.executable, "-c", "raise SystemExit(7)"]]}
    )
    assert not fail["passed"] and fail["checks"][0]["exit_code"] == 7
    assert bridge.hook({**e, "hook_event_name": "Stop"})["decision"] == "block"
    good = bridge.verify(
        sid, {"commands": [[sys.executable, "-c", "assert 2 + 2 == 4"]]}
    )
    assert good["passed"]
    assert bridge.hook({**e, "hook_event_name": "Stop"}) == {}
    (repo / "new.py").write_text("x = 2\n")
    assert bridge.hook({**e, "hook_event_name": "Stop"})["decision"] == "block"


def test_failed_launch_preserves_source(setup: tuple) -> None:
    _, log, e = setup
    sid = e["session_id"]
    token(log, 401, 1000)
    bridge.hook({**e, "hook_event_name": "PreToolUse"})
    bridge.checkpoint(sid, {"objective": "Fix retry", "next_action": "Run tests"})
    with patch.object(
        bridge, "continuation_command", side_effect=RuntimeError("offline")
    ):
        bridge.continue_session(sid)
    state = bridge.load(bridge.state_path(sid))
    assert state["rollover"] == "needs_attention"
    assert "to_session" not in state


def test_hop_limit_stops_unbounded_chain(setup: tuple) -> None:
    _, _, e = setup
    sid = e["session_id"]
    with bridge.locked(sid) as (path, state):
        state.update(rollover="requested", hops=3)
        bridge.save(path, state)
    assert "systemMessage" in bridge.launch(sid, 3)
    assert bridge.load(bridge.state_path(sid))["rollover"] == "needs_attention"


def test_sensitive_checkpoint_rejected(setup: tuple) -> None:
    with pytest.raises(ValueError):
        bridge.checkpoint(
            setup[2]["session_id"],
            {"objective": "Contact person@example.invalid", "next_action": "Wait"},
        )


def test_invalid_id_and_malformed_transcript(setup: tuple) -> None:
    with pytest.raises(ValueError):
        bridge.state_path("../../another-session")
    setup[1].write_text("not json\n")
    assert bridge.measure(str(setup[1])) == {}


def test_native_messages_keep_intermediate_constraints_and_skip_injections(
    setup: tuple,
) -> None:
    _, log, _ = setup
    messages = ["Original mandate", *[f"Constraint {i}" for i in range(12)]]
    rows = []
    for value in messages:
        rows.append(
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "internal_chat_message_metadata_passthrough": {
                        "content_item_kinds": ["user.text"]
                    },
                    "content": [{"type": "input_text", "text": value}],
                },
            }
        )
    rows.append(
        {
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "internal_chat_message_metadata_passthrough": {
                    "content_item_kinds": ["agents_md.instructions"]
                },
                "content": [{"type": "input_text", "text": "Reloaded by Codex"}],
            },
        }
    )
    log.write_text("".join(json.dumps(row) + "\n" for row in rows))
    result = bridge.prompts([str(log)])
    assert all(value in result for value in messages)
    assert "Reloaded by Codex" not in result


def test_cli_preserves_permissions_and_model() -> None:
    policy = {
        "type": "workspace-write",
        "writable_roots": ["/tmp/approved"],
        "network_access": False,
        "exclude_slash_tmp": True,
        "exclude_tmpdir_env_var": True,
    }
    runtime = {
        "model": "gpt-6-astra",
        "effort": "ultra",
        "approval_policy": "on-request",
        "sandbox_policy": policy,
    }
    command = bridge.continuation_command(runtime)
    assert command[command.index("--model") + 1] == "gpt-6-astra"
    assert command[command.index("--ask-for-approval") + 1] == "on-request"
    assert "sandbox_workspace_write.network_access=false" in command
    assert 'sandbox_workspace_write.writable_roots=["/tmp/approved"]' in command
    assert 'model_reasoning_effort="ultra"' in command
    assert all("bypass" not in part for part in command)
    runtime["sandbox_policy"] = {"type": "external-sandbox"}
    with pytest.raises(ValueError):
        bridge.continuation_command(runtime)


def test_only_exact_helper_is_allowed_at_threshold(setup: tuple) -> None:
    _, log, e = setup
    sid = e["session_id"]
    token(log, 401, 1000)
    command = (
        f"{sys.executable} {bridge.SELF} checkpoint {sid} <<'JSON'\n"
        + json.dumps({"objective": "Fix retry", "next_action": "Run test"})
        + "\nJSON"
    )
    payload = {
        **e,
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": ["/bin/zsh", "-lc", command]},
    }
    assert bridge.hook(payload) == {}
    payload["tool_input"]["command"][-1] += "\ntrue"
    assert bridge.hook(payload)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_existing_imperator_role_uses_twenty_percent(
    setup: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, log, e = setup
    monkeypatch.setenv("CONTEXT_GUARD_ROLE", "IMPERATOR")
    e = {**e, "session_id": "imperator-session-123"}
    seat = bridge.codex_home()
    policy = bridge.load(seat / "nuzantara-context-policy.json")
    policy["thresholds"] = {"imperator": 0.2, "builder": 0.4}
    bridge.save(seat / "nuzantara-context-policy.json", policy)
    bridge.hook(e)
    token(log, 201, 1000)
    assert (
        bridge.hook({**e, "hook_event_name": "PreToolUse"})["hookSpecificOutput"][
            "permissionDecision"
        ]
        == "deny"
    )


def test_handoff_nonce_prevents_foreign_claim(
    setup: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, e = setup
    source = e["session_id"]
    with bridge.locked(source) as (path, state):
        state.update(rollover="starting", launch_nonce="expected")
        bridge.save(path, state)
    monkeypatch.setenv("CODEX_CONTEXT_FROM_SESSION", source)
    monkeypatch.setenv("CODEX_CONTEXT_NONCE", "wrong")
    with pytest.raises(ValueError):
        bridge.hook({**e, "session_id": "foreign-child-123"})
    assert "claimed_by" not in bridge.load(bridge.state_path(source))
    monkeypatch.setenv("CODEX_CONTEXT_NONCE", "expected")
    bridge.hook({**e, "session_id": "correct-child-123"})
    assert bridge.load(bridge.state_path("correct-child-123"))["from_session"] == source
    with pytest.raises(ValueError):
        bridge.hook({**e, "session_id": "second-child-456"})


def test_helper_receipt_transport_does_not_grant_sandbox_writes(setup: tuple) -> None:
    import shlex

    _, _, e = setup
    sid = e["session_id"]
    data = {
        "objective": "Test receipt transport",
        "next_action": "Finish",
        "remaining": [],
        "risks": [],
    }
    command = shlex.join(
        [sys.executable, str(bridge.SELF), "checkpoint", sid, json.dumps(data)]
    )
    bridge.hook(
        {
            **e,
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
        }
    )
    assert bridge.load(bridge.state_path(sid))["checkpoint"] == data
    proof = bridge.verify(
        sid, {"commands": [[sys.executable, "-c", "pass"]]}, persist=False
    )
    assert "verification" not in bridge.load(bridge.state_path(sid))
    verify_command = shlex.join(
        [sys.executable, str(bridge.SELF), "verify", sid, '{"commands":[["true"]]}']
    )
    bridge.hook(
        {
            **e,
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": verify_command},
            "tool_response": {"output": json.dumps(proof)},
        }
    )
    assert bridge.load(bridge.state_path(sid))["verification"]["passed"]


def test_finished_mandate_does_not_spawn_another_session(setup: tuple) -> None:
    _, log, e = setup
    token(log, 401, 1000)
    bridge.hook({**e, "hook_event_name": "PreToolUse"})
    bridge.checkpoint(
        e["session_id"],
        {"objective": "Finished", "next_action": "Return result", "remaining": []},
    )
    with patch.object(bridge, "launch") as launch:
        bridge.hook({**e, "hook_event_name": "Stop"})
    launch.assert_not_called()


def test_unacknowledged_child_cannot_execute_tools(
    setup: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, e = setup
    monkeypatch.setenv("CODEX_CONTEXT_FROM_SESSION", "unclaimed-source-123")
    assert (
        bridge.hook({**e, "hook_event_name": "PreToolUse"})["hookSpecificOutput"][
            "permissionDecision"
        ]
        == "deny"
    )
    assert bridge.hook({**e, "hook_event_name": "Stop"})["continue"] is False
