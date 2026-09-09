# ruff: noqa: F811
"""Guilt/innocence and owned continuation lifetime regressions."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1] / "claude-hooks"))
import context_bridge as bridge
import child_workflow as claude
import mandate_budget as budget
from test_context_bridge import setup, token  # noqa: F401


def test_budget_keeps_failed_reservations_and_counts_replacements(
    tmp_path: Path,
) -> None:
    limits = {"max_active": 1, "max_attempts": 2, "max_seconds": 100, "max_depth": 1}
    assert budget.reserve(tmp_path, "root", "one", limits) is None
    assert budget.reserve(tmp_path, "root", "one", limits) is None
    assert "concurrent" in budget.reserve(tmp_path, "root", "two", limits)
    budget.observe(tmp_path, "root", "child-a")
    budget.observe(tmp_path, "root", "child-a", stopped=True)
    assert budget.reserve(tmp_path, "root", "two", limits) is None
    budget.observe(tmp_path, "root", "child-b")
    budget.observe(tmp_path, "root", "child-b", stopped=True)
    assert "total" in budget.reserve(tmp_path, "root", "three", limits)
    with budget.ledger(tmp_path, "root") as state:
        state["deadline"] = 0
    assert "deadline" in budget.reserve(tmp_path, "root", "four", limits)


def test_claude_native_pretool_parent_path_resolves_exact_child(
    claude_env: dict,
) -> None:
    p = claude_env
    exact = Path(p["transcript_path"]).with_suffix("") / "subagents" / "agent-a.jsonl"
    exact.parent.mkdir(parents=True)
    exact.write_text("{}\n")
    event = {**p, "hook_event_name": "PreToolUse"}
    assert claude.child_identity(event)[1] == str(exact)
    exact.unlink()
    assert claude.child_identity(event)[1] == ""


def test_installer_routes_only_reviewed_handlers() -> None:
    from install_claude_children import route_settings

    config = {
        "env": {"EXAMPLE": "preserved"},
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python /home/seat/hooks/context_window_guard.py",
                            "timeout": 7,
                        },
                        {"type": "command", "command": "unrelated"},
                    ],
                }
            ]
        },
    }
    result = route_settings(config, Path("/home/seat/hooks"))
    assert result["env"] == config["env"]
    handlers = result["hooks"]["PreToolUse"][0]["hooks"]
    assert handlers[0]["command"] == "python /home/seat/hooks/child_workflow.py context"
    assert handlers[0]["timeout"] == 7 and handlers[1]["command"] == "unrelated"
    assert "SessionStart" not in result["hooks"]
    assert route_settings(result, Path("/home/seat/hooks")) == result


def child_transcript(path: Path, child: str, parent: str) -> None:
    path.write_text(
        json.dumps(
            {
                "type": "session_meta",
                "payload": {
                    "id": child,
                    "parent_thread_id": parent,
                    "source": {
                        "subagent": {"thread_spawn": {"parent_thread_id": parent}}
                    },
                },
            }
        )
        + "\n"
    )
    # Native forks contain inherited parent metadata and token history.
    with path.open("a") as out:
        out.write(
            json.dumps(
                {"type": "session_meta", "payload": {"id": parent, "source": "exec"}}
            )
            + "\n"
        )
        out.write(
            json.dumps(
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "model_context_window": 1000,
                            "last_token_usage": {"total_tokens": 900},
                        },
                    },
                }
            )
            + "\n"
        )


def test_native_fork_ignores_parent_history_and_role(
    setup: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, log, e = setup
    monkeypatch.setenv("CONTEXT_GUARD_ROLE", "imperator")
    child = "child-session-123"
    child_transcript(log, child, e["session_id"])
    event = {**e, "agent_id": child, "hook_event_name": "SubagentStart"}
    parent_before = bridge.load(bridge.state_path(e["session_id"]))
    bridge.hook(event)
    state = bridge.load(bridge.state_path(child))
    assert state["role"] == "builder" and state["measurement"] == "UNKNOWN"
    assert not state.get("return_required")
    assert bridge.load(bridge.state_path(e["session_id"])) == parent_before
    assert bridge.native_child(event) == (child, e["session_id"], str(log))


def test_native_child_threshold_returns_without_parent_jump(setup: tuple) -> None:
    _, log, e = setup
    child = "child-session-123"
    child_transcript(log, child, e["session_id"])
    bridge.hook({**e, "agent_id": child, "hook_event_name": "SubagentStart"})
    with log.open("a") as out:
        out.write(
            json.dumps(
                {
                    "timestamp": "new",
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "model_context_window": 1000,
                            "last_token_usage": {"total_tokens": 500},
                        },
                    },
                }
            )
            + "\n"
        )
    pre = {**e, "hook_event_name": "PreToolUse", "tool_name": "Bash"}
    for _ in range(3):
        assert bridge.hook(pre)["hookSpecificOutput"]["permissionDecision"] == "deny"
    stop = {
        **e,
        "agent_id": child,
        "hook_event_name": "SubagentStop",
        "agent_transcript_path": str(log),
    }
    with patch.object(
        bridge, "launch", side_effect=AssertionError("child must never launch")
    ):
        assert bridge.hook(stop)["decision"] == "block"
        assert bridge.hook(stop) == {}
    assert (
        bridge.load(bridge.state_path(child))["completion_status"] == "needs_attention"
    )
    assert bridge.load(bridge.state_path(e["session_id"])).get("rollover") is None


def test_acknowledged_parent_authorizes_own_native_child_only(
    setup: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, log, e = setup
    child_transcript(log, "child-session-123", e["session_id"])
    monkeypatch.setenv("CODEX_CONTEXT_FROM_SESSION", "original-session-123")
    pre = {**e, "hook_event_name": "PreToolUse", "tool_name": "Bash"}
    assert bridge.hook(pre)["hookSpecificOutput"]["permissionDecision"] == "deny"
    with bridge.locked(e["session_id"]) as (path, state):
        state["from_session"] = "original-session-123"
        bridge.save(path, state)
    assert bridge.hook(pre) == {}


def test_missing_checkpoint_records_attention_on_second_stop(setup: tuple) -> None:
    _, log, e = setup
    token(log, 500, 1000)
    stop = {**e, "hook_event_name": "Stop"}
    assert bridge.hook(stop)["decision"] == "block"
    bridge.hook({**stop, "stop_hook_active": True})
    assert (
        bridge.load(bridge.state_path(e["session_id"]))["failure"]
        == "checkpoint_missing"
    )


def test_empty_remaining_never_means_independent_acceptance(setup: tuple) -> None:
    _, _, e = setup
    bridge.checkpoint(
        e["session_id"],
        {"objective": "fixture", "next_action": "return", "remaining": []},
    )
    bridge.hook({**e, "hook_event_name": "Stop"})
    assert (
        bridge.load(bridge.state_path(e["session_id"]))["acceptance_status"]
        == "unverified"
    )


@pytest.fixture
def claude_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "seat"))
    child = tmp_path / "subagents" / "agent-a.jsonl"
    child.parent.mkdir()
    child.write_text("{}\n")
    return {
        "session_id": "parent",
        "agent_id": "a",
        "agent_transcript_path": str(child),
        "transcript_path": str(tmp_path / "parent.jsonl"),
        "hook_event_name": "SubagentStop",
    }


def test_claude_siblings_and_parent_intent_are_isolated(claude_env: dict) -> None:
    p = claude_env
    Path(p["transcript_path"]).write_text("checkpoint: parent only")
    legacy = {"_git_dirty_status": lambda _: " M other-worker.py"}
    for agent in ("a", "b"):
        key, _ = claude.child_identity({**p, "agent_id": agent})
        with claude.child_state(key) as (_, state):
            state.update(pretool_count=1, mutation_possible=True)
    assert claude.stop_guard(p, legacy) == 2
    assert claude.stop_guard(p, legacy) == 0
    assert claude.stop_guard({**p, "agent_id": "b"}, legacy) == 2
    assert Path(p["transcript_path"]).read_text() == "checkpoint: parent only"


def test_claude_readonly_child_never_cleans_sibling_dirty_tree(
    claude_env: dict,
) -> None:
    p = claude_env
    key, _ = claude.child_identity(p)
    with claude.child_state(key) as (_, state):
        state.update(pretool_count=1, mutation_possible=False)

    def forbidden(_: str) -> str:
        raise AssertionError(
            "readonly child must not inspect/stage sibling dirty files"
        )

    assert claude.stop_guard(p, {"_git_dirty_status": forbidden}) == 0


def test_claude_child_ignores_parent_window_and_never_weakens_deny(
    claude_env: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NUZANTARA_MANDATE_ID", "strict-test")
    monkeypatch.setenv("CONTEXT_GUARD_ROLE", "imperator")
    monkeypatch.setenv("CONTEXT_WINDOW_TOKENS", "1000")
    p = {
        **claude_env,
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "transcript_path": claude_env["agent_transcript_path"],
    }
    callbacks = {
        "_read_tail": lambda _: json.dumps(
            {
                "type": "assistant",
                "version": "test",
                "message": {"model": "child-model", "usage": {"input_tokens": 500}},
            }
        ),
        "_last_assistant_model": lambda _: "child-model",
        "_estimate_tokens": lambda _: 500,
        "_count_assistant_turns": lambda _: 31,
        "GRACE_TURNS": 30,
    }
    assert claude.context_guard(p, callbacks) == 0
    key, _ = claude.child_identity(p)
    with claude.child_state(key) as (_, state):
        assert state["window"] is None and state["role"] == "builder"
    for _ in range(3):
        assert (
            claude.context_guard(
                {**p, "context_window": {"context_window_size": 1000}}, callbacks
            )
            == 2
        )


@pytest.mark.parametrize("cancelled", [False, True])
def test_owned_continuation_idle_is_not_death_and_cancel_is_bounded(
    setup: tuple, monkeypatch: pytest.MonkeyPatch, cancelled: bool
) -> None:
    _, log, e = setup
    sid = e["session_id"]
    log.write_text(
        json.dumps(
            {
                "type": "turn_context",
                "payload": {
                    "model": "fixture",
                    "approval_policy": "never",
                    "sandbox_policy": {"type": "read-only"},
                },
            }
        )
        + "\n"
    )
    bridge.checkpoint(sid, {"objective": "fixture", "next_action": "return"})
    with bridge.locked(sid) as (path, state):
        state.update(
            rollover="starting",
            launch_nonce="test",
            launch_deadline=time.time() + 5,
            mandate_deadline=time.time() + 5,
        )
        bridge.save(path, state)
    bridge.save(bridge.state_path("target-session-123"), {"from_session": sid})
    code = 'import json,time; print(json.dumps({"type":"thread.started","thread_id":"target-session-123"}),flush=True); print(json.dumps({"type":"item.started","item":{"type":"command_execution"}}),flush=True); time.sleep(0.5); print(json.dumps({"type":"turn.completed"}),flush=True)'
    monkeypatch.setattr(bridge, "POLL_SECONDS", 0.02)
    if cancelled:
        import threading

        timer = threading.Timer(0.25, lambda: bridge.cancel(sid))
        timer.start()
    with (
        patch.object(bridge, "prompts", return_value="fixture"),
        patch.object(
            bridge, "continuation_command", return_value=[sys.executable, "-c", code]
        ),
    ):
        bridge.continue_session(sid)
    state = bridge.load(bridge.state_path(sid))
    assert state["supervisor_finished"] and state["owned_exit_code"] is not None
    if cancelled:
        timer.join()
        assert state["rollover"] == "needs_attention"
    else:
        assert state["transport_status"] == "completed"
        assert state["acceptance_status"] == "unverified"


def test_interactive_ledger_survives_expired_unstarted_and_old_session(
    tmp_path: Path,
) -> None:
    limits = {
        "max_active": 3,
        "max_attempts": 3,
        "max_seconds": 1,
        "strict": False,
        "unstarted_ttl": 1,
    }
    for i in range(3):
        assert budget.reserve(tmp_path, "root", str(i), limits) is None
    with budget.ledger(tmp_path, "root") as state:
        state["deadline"] = 0
        for row in state["reservations"].values():
            row["created"] = 0
    assert budget.reserve(tmp_path, "root", "four", limits) is None
    with budget.ledger(tmp_path, "root") as state:
        assert len(state["reservations"]) == 4
        assert (
            sum(
                r["status"] == "expired_unstarted"
                for r in state["reservations"].values()
            )
            == 3
        )


def test_followup_reactivates_same_actor_and_counts_attempt(tmp_path: Path) -> None:
    limits = {"max_active": 1, "max_attempts": 3}
    assert budget.reserve(tmp_path, "root", "one", limits) is None
    budget.observe(tmp_path, "root", "uuid", alias="/root/native_probe")
    budget.observe(tmp_path, "root", "uuid", stopped=True)
    assert (
        budget.reserve(tmp_path, "root", "two", limits, target="native_probe") is None
    )
    assert budget.reserve(tmp_path, "root", "three", limits, target="uuid") is None
    budget.observe(tmp_path, "root", "uuid", stopped=True)
    assert "total" in budget.reserve(tmp_path, "root", "four", limits, target="uuid")
    with budget.ledger(tmp_path, "root") as state:
        assert all(
            r["status"] == "returned_unverified" for r in state["reservations"].values()
        )
        assert "native_probe" not in json.dumps(state)


def test_child_unknown_window_is_not_a_stop_block(setup: tuple) -> None:
    _, log, event = setup
    child_transcript(log, "child-session-123", event["session_id"])
    bridge.hook(
        {**event, "hook_event_name": "SubagentStart", "agent_id": "child-session-123"}
    )
    assert (
        bridge.hook(
            {
                **event,
                "hook_event_name": "SubagentStop",
                "agent_id": "child-session-123",
                "agent_transcript_path": str(log),
            }
        )
        == {}
    )
    assert (
        bridge.load(bridge.state_path("child-session-123"))["measurement"] == "UNKNOWN"
    )


def test_nested_delegation_is_denied_both_harnesses(
    setup: tuple, claude_env: dict
) -> None:
    _, log, event = setup
    child_transcript(log, "child-session-123", event["session_id"])
    response = bridge.hook(
        {
            **event,
            "hook_event_name": "PreToolUse",
            "tool_name": "collaborationspawn_agent",
        }
    )
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert (
        claude.context_guard(
            {**claude_env, "hook_event_name": "PreToolUse", "tool_name": "Agent"}, {}
        )
        == 2
    )


def test_needs_attention_never_reopens_codex_tools(setup: tuple) -> None:
    _, _, event = setup
    with bridge.locked(event["session_id"]) as (path, state):
        state["rollover"] = "needs_attention"
        bridge.save(path, state)
    for _ in range(3):
        response = bridge.hook(
            {**event, "hook_event_name": "PreToolUse", "tool_name": "Bash"}
        )
        assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_zero_tool_claude_child_returns_without_false_unknown(claude_env: dict) -> None:
    assert claude.stop_guard(claude_env, {}) == 0


@pytest.mark.parametrize("failure", ["deadline", "eof"])
def test_owned_continuation_deadline_and_eof_are_attention(
    setup: tuple, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    _, log, event = setup
    sid = event["session_id"]
    log.write_text(
        json.dumps(
            {
                "type": "turn_context",
                "payload": {
                    "model": "fixture",
                    "approval_policy": "never",
                    "sandbox_policy": {"type": "read-only"},
                },
            }
        )
        + "\n"
    )
    bridge.checkpoint(sid, {"objective": "fixture", "next_action": "return"})
    with bridge.locked(sid) as (path, state):
        state.update(
            rollover="starting",
            launch_nonce="test",
            launch_deadline=time.time() + 5,
            mandate_deadline=time.time() + (0.15 if failure == "deadline" else 5),
        )
        bridge.save(path, state)
    bridge.save(bridge.state_path("target-session-123"), {"from_session": sid})
    code = (
        'import json,time; print(json.dumps({"type":"thread.started","thread_id":"target-session-123"}),flush=True); print(json.dumps({"type":"item.started","item":{"type":"command_execution"}}),flush=True); time.sleep('
        + ("2" if failure == "deadline" else "0.05")
        + ")"
    )
    monkeypatch.setattr(bridge, "POLL_SECONDS", 0.02)
    with (
        patch.object(bridge, "prompts", return_value="fixture"),
        patch.object(
            bridge, "continuation_command", return_value=[sys.executable, "-c", code]
        ),
    ):
        bridge.continue_session(sid)
    state = bridge.load(bridge.state_path(sid))
    assert state["rollover"] == "needs_attention" and state["supervisor_finished"]
    assert state["owned_exit_code"] is not None


def test_stop_reminder_not_reset_by_blocked_child_tool(setup: tuple) -> None:
    _, log, event = setup
    child = "child-session-123"
    child_transcript(log, child, event["session_id"])
    bridge.hook({**event, "hook_event_name": "SubagentStart", "agent_id": child})
    with bridge.locked(child) as (path, state):
        state["return_required"] = True
        bridge.save(path, state)
    stop = {
        **event,
        "hook_event_name": "SubagentStop",
        "agent_id": child,
        "agent_transcript_path": str(log),
    }
    assert bridge.hook(stop)["decision"] == "block"
    assert (
        bridge.hook({**event, "hook_event_name": "PreToolUse", "tool_name": "Bash"})[
            "hookSpecificOutput"
        ]["permissionDecision"]
        == "deny"
    )
    assert bridge.hook(stop) == {}


def test_unknown_resume_is_observed_as_a_new_reservation(tmp_path: Path) -> None:
    assert (
        budget.reserve(tmp_path, "root", "dispatch", {}, target="unmapped-nickname")
        is None
    )
    with budget.ledger(tmp_path, "root") as state:
        assert state["status"] == "needs_attention" and len(state["reservations"]) == 1
    budget.observe(tmp_path, "root", "uuid", nickname="NativeNickname")
    budget.observe(tmp_path, "root", "uuid", stopped=True)
    assert (
        budget.reserve(tmp_path, "root", "resume", {}, target="NativeNickname") is None
    )
    with budget.ledger(tmp_path, "root") as state:
        assert all(r.get("child") == "uuid" for r in state["reservations"].values())


@pytest.mark.parametrize(
    "mode,child", [("context", False), ("context", True), ("stop", True)]
)
def test_claude_router_subprocess_with_repo_legacy(
    tmp_path: Path, mode: str, child: bool
) -> None:
    import subprocess
    import os

    transcript = tmp_path / "subagents" / "agent-a.jsonl"
    transcript.parent.mkdir()
    transcript.write_text("{}\n")
    payload = {
        "hook_event_name": "PreToolUse" if mode == "context" else "SubagentStop",
        "session_id": "probe-session",
        "transcript_path": str(transcript if child else tmp_path / "parent.jsonl"),
        "cwd": str(tmp_path),
        "tool_name": "Read",
        "tool_input": {},
    }
    if child:
        payload.update(agent_id="a", agent_transcript_path=str(transcript))
    env = {
        **os.environ,
        "CLAUDE_CONFIG_DIR": str(tmp_path / "seat"),
        "CONTEXT_JUMP_NO_SPAWN": "1",
    }
    run = subprocess.run(
        [sys.executable, str(Path(claude.__file__)), mode],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        timeout=10,
    )
    assert run.returncode == 0, run.stderr
    assert not run.stdout.strip() or isinstance(json.loads(run.stdout), dict)


def test_broken_router_preserves_parent_and_child_never_jumps(tmp_path: Path) -> None:
    import subprocess
    import shutil
    import os

    shutil.copy2(claude.__file__, tmp_path / "child_workflow.py")
    # Missing budget and orchestrate modules force the router exception path.
    (tmp_path / "context_window_guard.py").write_text(
        "def main():\n    return 2\nif __name__ == '__main__':\n    raise SystemExit(main())\n"
    )
    for child, expected in ((False, 2), (True, 2)):
        payload = {"session_id": "p", "tool_name": "Read", "tool_input": {}}
        if child:
            payload["agent_id"] = "a"
        run = subprocess.run(
            [sys.executable, str(tmp_path / "child_workflow.py"), "context"],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env={**os.environ, "CLAUDE_CONFIG_DIR": str(tmp_path / "seat")},
            timeout=10,
        )
        assert run.returncode == expected and "Traceback" not in run.stderr
        if child:
            assert "no parent jump" in run.stderr


def test_native_child_threshold_follows_the_policy_not_a_literal(
    setup: tuple,
) -> None:
    """The child read 0.4 from its own source while the parent read the policy.

    Raising the wall on the three hosts moved the parent seat and left every
    native child it dispatched at the old number. At 500/1000 under a declared
    builder 0.6 the child must keep working; the hardcoded literal returned it.
    """
    _, log, e = setup
    seat = bridge.codex_home()
    policy = bridge.load(seat / "nuzantara-context-policy.json")
    policy["thresholds"] = {"imperator": 0.6, "builder": 0.6, "dux": 0.6}
    bridge.save(seat / "nuzantara-context-policy.json", policy)
    assert bridge.threshold(policy, "builder") == 0.6
    assert bridge.threshold(policy, "dux") == 0.6
    # An undeclared role keeps the conservative fallback; install.py declares it.
    assert bridge.threshold({}, "dux") == 0.4
    child = "child-session-123"
    child_transcript(log, child, e["session_id"])
    bridge.hook({**e, "agent_id": child, "hook_event_name": "SubagentStart"})
    with log.open("a") as out:
        out.write(
            json.dumps(
                {
                    "timestamp": "new",
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "model_context_window": 1000,
                            "last_token_usage": {"total_tokens": 500},
                        },
                    },
                }
            )
            + "\n"
        )
    bridge.hook(
        {**e, "agent_id": child, "hook_event_name": "PreToolUse", "tool_name": "Read"}
    )
    state = bridge.load(bridge.state_path(child))
    assert state["role"] == "builder" and state["used"] == 500 and state["window"] == 1000
    assert not state.get("return_required")


def test_dux_role_resolves_and_the_declared_key_is_what_moves_its_wall(
    setup: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two seats, same role, same usage, opposite verdicts — the key decides.

    The earlier version of this test asserted only that a declared `dux: 0.6`
    denies at 601/1000, which an UNDECLARED `dux` does too via the 0.4
    fallback: it could not fail on the code it was written to protect. The
    parent-side lookup always honoured an arbitrary role key; what was missing
    was `install.py` declaring one. So the discriminating fact is the CONTRAST
    at a single usage point — 500 of 1000 is over 0.4 and under 0.6 — and that
    is what is asserted here, in both directions.
    """
    _, log, e = setup
    monkeypatch.setenv("CODEX_CONTEXT_ROLE", "DUX")
    seat = bridge.codex_home()

    def verdict(session: str, thresholds: dict, used: int) -> dict:
        policy = bridge.load(seat / "nuzantara-context-policy.json")
        policy["thresholds"] = thresholds
        bridge.save(seat / "nuzantara-context-policy.json", policy)
        event = {**e, "session_id": session}
        bridge.hook(event)
        assert bridge.load(bridge.state_path(session))["role"] == "dux"
        token(log, used, 1000)
        return bridge.hook(
            {**event, "hook_event_name": "PreToolUse", "tool_name": "Bash"}
        )

    undeclared = verdict("dux-undeclared-123", {"builder": 0.6}, 500)
    assert undeclared["hookSpecificOutput"]["permissionDecision"] == "deny"
    declared = verdict("dux-declared-1234", {"builder": 0.6, "dux": 0.6}, 500)
    assert declared == {}
    # And the declared wall is a real wall, not merely a higher number.
    assert (
        verdict("dux-over-the-wall", {"builder": 0.6, "dux": 0.6}, 601)[
            "hookSpecificOutput"
        ]["permissionDecision"]
        == "deny"
    )


def test_installer_adds_dux_without_overwriting_a_tuned_threshold() -> None:
    """A seat installed before `dux` existed must still receive it."""
    from install import THRESHOLD_DEFAULTS, merge_thresholds

    existing = {"thresholds": {"imperator": 0.2, "builder": 0.4}}
    assert merge_thresholds(existing) == {
        "imperator": 0.2,
        "builder": 0.4,
        "dux": 0.6,
    }
    assert merge_thresholds({}) == THRESHOLD_DEFAULTS
def test_one_mission_deadline_is_shared_renewed_explicitly_and_resets_nothing(
    tmp_path: Path,
) -> None:
    """The supervisor and the ledger used to run two clocks for one mission."""
    limits = {"strict": True, "max_seconds": 100}
    assert budget.reserve(tmp_path, "root", "one", limits) is None
    opened = budget.mandate_deadline(tmp_path, "root")
    # A later reader cannot lengthen a mission that is already running, whatever
    # default it happens to carry. This is what context_bridge.launch() now calls.
    assert budget.mandate_deadline(tmp_path, "root", 99999) == opened
    with budget.ledger(tmp_path, "root") as state:
        state["deadline"] = 0
    denial = budget.reserve(tmp_path, "root", "two", limits)
    for field in ("counter=mission_deadline", "overrun=", "mandate_budget.renew()"):
        assert field in denial, field
    with budget.ledger(tmp_path, "root") as state:
        # Its own key, so a renewal cannot silence an attempts alarm by accident.
        assert state["attention_key"] == "mandate_deadline"
        spent = len(state["reservations"])
    record = budget.renew(tmp_path, "root", 3600, "coordinator-test")
    assert record["previous_deadline"] == 0 and record["new_deadline"] > time.time()
    with budget.ledger(tmp_path, "root") as state:
        assert state["renewals"][-1]["who"] == "coordinator-test"
        assert state["renewals"][-1]["previous_deadline"] == 0
        assert len(state["reservations"]) == spent  # only the wall clock moved
        assert state.get("attention_key") != "mandate_deadline"
    assert budget.reserve(tmp_path, "root", "three", limits) is None
    with pytest.raises(ValueError):
        budget.renew(tmp_path, "root", 0, "coordinator-test")


def test_observe_refuses_to_guess_between_two_unbound_reservations(
    tmp_path: Path,
) -> None:
    """`next(reserved)` was a coin flip that the ledger could never show as one."""
    limits = {"strict": True, "max_active": 3}
    assert budget.reserve(tmp_path, "root", "dispatch-a", limits) is None
    assert budget.reserve(tmp_path, "root", "dispatch-b", limits) is None
    assert budget.observe(tmp_path, "root", "child-x") is None
    with budget.ledger(tmp_path, "root") as state:
        assert state["attention_key"] == "binding_unknown"
        assert "candidates=2" in state["reason"]
        # Ambiguity consumed nothing: both slots are still unattributed.
        assert all(not r.get("child") for r in state["reservations"].values())
    with budget.ledger(tmp_path, "root") as state:
        list(state["reservations"].values())[0]["child"] = "child-y"
    # One unbound candidate is not a guess, so it still binds and clears the doubt.
    assert budget.observe(tmp_path, "root", "child-z") is None
    with budget.ledger(tmp_path, "root") as state:
        rows = [r for r in state["reservations"].values() if r.get("child") == "child-z"]
        assert len(rows) == 1 and rows[0]["binding"] == "sole_unbound_reservation"
        assert state.get("attention_key") != "binding_unknown"
