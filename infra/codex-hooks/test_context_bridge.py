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


# --- 1.2.0: acknowledgement is the destination's claim, not its first model event ---

FAKE_DESTINATION = """
import json, sys, time
sys.stdin.read()
thread, delay = sys.argv[-2], float(sys.argv[-1])
print(json.dumps({"type": "thread.started", "thread_id": thread}), flush=True)
time.sleep(delay)
print(json.dumps({"type": "item.started", "item": {"type": "reasoning"}}), flush=True)
print(json.dumps({"type": "turn.completed"}), flush=True)
"""


def mandate_transcript(log: Path, used: int, window: int) -> None:
    rows = [
        {
            "type": "turn_context",
            "payload": {
                "model": "gpt-test",
                "effort": "low",
                "approval_policy": "never",
                "sandbox_policy": {"type": "read-only"},
            },
        },
        {
            "type": "event_msg",
            "payload": {"type": "user_message", "message": "Reply READY and stop."},
        },
        {
            "type": "event_msg",
            "timestamp": "2026-09-09T05:00:00Z",
            "payload": {
                "type": "token_count",
                "info": {
                    "model_context_window": window,
                    "last_token_usage": {"total_tokens": used},
                },
            },
        },
    ]
    log.write_text("".join(json.dumps(r) + "\n" for r in rows))


def parked_source(setup: tuple, failure: str, attempts: int) -> str:
    _, log, e = setup
    sid = e["session_id"]
    mandate_transcript(log, 401, 1000)
    bridge.hook({**e, "hook_event_name": "PreToolUse"})
    bridge.checkpoint(sid, {"objective": "o", "next_action": "n", "remaining": ["x"]})
    with bridge.locked(sid) as (path, state):
        state.update(rollover="needs_attention", failure=failure, launch_attempts=attempts)
        bridge.save(path, state)
    return sid


def test_destination_claim_accepts_before_first_model_event(
    setup: tuple, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading
    import time

    repo, log, e = setup
    sid = e["session_id"]
    mandate_transcript(log, 401, 1000)
    bridge.hook({**e, "hook_event_name": "PreToolUse"})
    bridge.checkpoint(sid, {"objective": "o", "next_action": "n", "remaining": ["x"]})
    with bridge.locked(sid) as (path, state):
        state.update(
            rollover="starting",
            launch_nonce="nonce-1",
            launch_deadline=time.time() + 60,
            launch_attempts=1,
        )
        bridge.save(path, state)
    fake = tmp_path / "fake_codex.py"
    fake.write_text(FAKE_DESTINATION)
    dest_log = tmp_path / "dest.jsonl"
    dest_log.write_text("")
    started = time.time()
    with patch.object(
        bridge,
        "continuation_command",
        return_value=[sys.executable, str(fake), "dest-session-1", "6"],
    ):
        worker = threading.Thread(target=bridge.continue_session, args=(sid,))
        worker.start()
        time.sleep(0.5)
        # The destination's own SessionStart hook claims the exact source under the nonce.
        monkeypatch.setenv("CODEX_CONTEXT_FROM_SESSION", sid)
        monkeypatch.setenv("CODEX_CONTEXT_NONCE", "nonce-1")
        bridge.hook(
            {
                "session_id": "dest-session-1",
                "cwd": str(repo),
                "transcript_path": str(dest_log),
                "hook_event_name": "SessionStart",
            }
        )
        monkeypatch.delenv("CODEX_CONTEXT_FROM_SESSION")
        monkeypatch.delenv("CODEX_CONTEXT_NONCE")
        for _ in range(40):
            if bridge.load(bridge.state_path(sid)).get("rollover") == "accepted":
                break
            time.sleep(0.1)
        accepted = bridge.load(bridge.state_path(sid))
        assert accepted["rollover"] == "accepted"
        assert accepted["to_session"] == "dest-session-1"
        assert accepted["accepted_at"] - started < 5  # before the 6 s first model event
        worker.join(timeout=15)
    final = bridge.load(bridge.state_path(sid))
    assert final["destination_status"] == "completed"
    assert final["owned_exit_code"] == 0  # the accepted destination was never terminated


def test_stop_wait_expiry_keeps_launch_starting(
    setup: tuple, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    _, log, e = setup
    sid = e["session_id"]
    mandate_transcript(log, 401, 1000)
    bridge.hook({**e, "hook_event_name": "PreToolUse"})
    bridge.checkpoint(sid, {"objective": "o", "next_action": "n", "remaining": ["x"]})
    fake = tmp_path / "fake_codex.py"
    # thread.started, then 3 s of silence, then exit: no claim ever arrives.
    fake.write_text(
        "#!" + sys.executable + "\n"
        "import json, sys, time\n"
        "sys.stdin.read()\n"
        'print(json.dumps({"type": "thread.started", "thread_id": "silent-dest-1"}), flush=True)\n'
        "time.sleep(3)\n"
    )
    fake.chmod(0o755)
    monkeypatch.setenv("CODEX_CONTEXT_BINARY", str(fake))
    monkeypatch.setattr(bridge, "HANDSHAKE_SECONDS", 0.5)
    result = bridge.launch(sid, 3)
    assert "still launching" in result["systemMessage"]
    state = bridge.load(bridge.state_path(sid))
    assert state["rollover"] == "starting"  # the Stop wait expired; nothing was cancelled
    assert state["launch_attempts"] == 1
    for _ in range(100):
        state = bridge.load(bridge.state_path(sid))
        if state.get("rollover") == "needs_attention":
            break
        time.sleep(0.1)
    assert state["rollover"] == "needs_attention"
    assert state["failure"] == "destination_failed"  # the supervisor's verdict, not the Stop hook's
    assert "to_session" not in state


def test_stop_retries_transient_failure_bounded(setup: tuple) -> None:
    _, _, e = setup
    sid = parked_source(setup, "TimeoutError", 1)
    calls: list[str] = []

    def fake_launch(session: str, max_hops: int) -> dict:
        calls.append(bridge.load(bridge.state_path(session))["rollover"])
        return {"systemMessage": "launched"}

    with patch.object(bridge, "launch", side_effect=fake_launch):
        assert bridge.hook({**e, "hook_event_name": "Stop"}) == {"systemMessage": "launched"}
    assert calls == ["requested"]
    with bridge.locked(sid) as (path, state):
        state.update(rollover="needs_attention", failure="TimeoutError", launch_attempts=3)
        bridge.save(path, state)
    with patch.object(bridge, "launch", side_effect=fake_launch):
        bridge.hook({**e, "hook_event_name": "Stop"})
    assert calls == ["requested"]  # attempt cap reached: no fourth launch
    assert bridge.load(bridge.state_path(sid))["rollover"] == "needs_attention"
    with bridge.locked(sid) as (path, state):
        state.update(failure="mandate_dispatch_budget", launch_attempts=1)
        bridge.save(path, state)
    with patch.object(bridge, "launch", side_effect=fake_launch):
        bridge.hook({**e, "hook_event_name": "Stop"})
    assert calls == ["requested"]  # a non-transient failure is never retried on its own


def test_frozen_source_names_its_phase(setup: tuple) -> None:
    _, _, e = setup
    sid = parked_source(setup, "TimeoutError", 1)
    tool = {**e, "hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}}
    out = bridge.hook(tool)["hookSpecificOutput"]
    assert out["permissionDecision"] == "deny"
    assert "attempt 1 failed (TimeoutError)" in out["permissionDecisionReason"]
    assert "retries the handoff automatically" in out["permissionDecisionReason"]
    with bridge.locked(sid) as (path, state):
        state.update(rollover="accepted", to_session="dest-session-9")
        bridge.save(path, state)
    reason = bridge.hook(tool)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "Codex task dest-session-9" in reason
    with bridge.locked(sid) as (path, state):
        state.update(rollover="needs_attention", failure="ValueError", launch_attempts=1)
        bridge.save(path, state)
    reason = bridge.hook(tool)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "Operator decision needed" in reason and " retry " in reason


def test_retry_and_release_verbs(setup: tuple) -> None:
    _, _, e = setup
    sid = parked_source(setup, "ValueError", 3)
    assert bridge.retry(sid)["retry_armed"] is True
    assert bridge.load(bridge.state_path(sid))["rollover"] == "requested"
    with pytest.raises(ValueError):
        bridge.retry(sid)  # only a parked source re-arms
    assert bridge.release(sid)["released"] is True
    state = bridge.load(bridge.state_path(sid))
    assert "rollover" not in state and state["threshold_released"] is True
    tool = {**e, "hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}}
    assert bridge.hook(tool) == {}  # still over threshold, but the owner released it
    with bridge.locked(sid) as (path, state):
        state.update(rollover="starting")
        bridge.save(path, state)
    with pytest.raises(ValueError):
        bridge.release(sid)  # an in-flight launch must be cancelled first
