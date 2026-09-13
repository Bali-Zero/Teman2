"""Live Fable counterexamples: interactive fanout, Stop recovery and Opus routing."""

import io
import os
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1] / "codex-hooks"))
import child_context as ctx
import child_workflow as child
import mandate_budget as budget


@pytest.fixture
def event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "seat"))
    monkeypatch.delenv("NUZANTARA_MANDATE_ID", raising=False)
    transcript = tmp_path / "subagents" / "agent-a.jsonl"
    transcript.parent.mkdir()
    transcript.write_text(
        json.dumps(
            {
                "type": "assistant",
                "version": "test",
                "message": {"model": "claude-opus-5", "usage": {"input_tokens": 1000}},
            }
        )
    )
    return {
        "session_id": "parent",
        "agent_id": "a",
        "tool_name": "Read",
        "hook_event_name": "PreToolUse",
        "transcript_path": str(transcript),
        "agent_transcript_path": str(transcript),
        "cwd": str(tmp_path),
    }


def test_interactive_nine_children_and_strict_eight(tmp_path: Path) -> None:
    for strict in (False, True):
        mandate = str(strict)
        limits = {"strict": strict, "max_active": 8}
        for i in range(8):
            assert budget.reserve(tmp_path, mandate, str(i), limits) is None
            budget.observe(tmp_path, mandate, str(i))
        reason = budget.reserve(tmp_path, mandate, "ninth", limits)
        assert (reason is not None) == strict
        with budget.ledger(tmp_path, mandate) as state:
            assert len(state["reservations"]) == (8 if strict else 9)


@pytest.mark.parametrize(
    "flag", ["STOP_VERIFY_ALLOW_DIRTY", "SUBAGENT_STOP_VERIFY_OFF", "broken_legacy"]
)
def test_stop_releases_and_pauses_before_verification(
    event: dict, monkeypatch: pytest.MonkeyPatch, flag: str
) -> None:
    monkeypatch.setattr(child.time, "time", lambda: 100)
    budget.reserve(child.budget_dir(), "parent", "dispatch", {})
    child.context_guard(event, {"_read_tail": lambda _: "{}"})
    monkeypatch.setattr(child.time, "time", lambda: 1300)
    if flag != "broken_legacy":
        monkeypatch.setenv(flag, "1")
    else:
        monkeypatch.setattr(
            child.importlib.util, "spec_from_file_location", lambda *a: None
        )
    monkeypatch.setattr(sys, "argv", ["child_workflow.py", "stop"])
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps({**event, "hook_event_name": "SubagentStop"})),
    )
    with pytest.raises(SystemExit) as exit_info:
        child.entrypoint()
    assert exit_info.value.code == 0
    with budget.ledger(child.budget_dir(), "parent") as state:
        assert all(
            r["status"] == "returned_unverified" for r in state["reservations"].values()
        )
    key, _ = child.child_identity(event)
    with child.child_state(key) as (_, state):
        assert state["budget_elapsed"] == 1200
        assert "budget_started_at" not in state
    # Idle time is excluded; spent time survives a resume even with recovery set.
    monkeypatch.setattr(child.time, "time", lambda: 10000)
    assert child.context_guard(event, {"_read_tail": lambda _: "{}"}) == 0
    with child.child_state(key) as (_, state):
        assert state["budget_elapsed"] == 1200 and state["budget_started_at"] == 10000


def test_transcript_silence_reclaims_without_refunding_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    limits = {"strict": True, "max_active": 1, "active_ttl": 1800, "max_seconds": 20000}
    transcript = tmp_path / "agent-a.jsonl"
    transcript.write_text("{}")
    os.utime(transcript, (100, 100))
    monkeypatch.setattr(budget.time, "time", lambda: 100)
    budget.reserve(tmp_path, "root", "one", limits)
    budget.observe(tmp_path, "root", "a", transcript=str(transcript))
    monkeypatch.setattr(budget.time, "time", lambda: 3500)
    budget.observe(tmp_path, "root", "a")
    monkeypatch.setattr(budget.time, "time", lambda: 4000)
    assert "concurrent" in budget.reserve(tmp_path, "root", "two", limits)
    monkeypatch.setattr(budget.time, "time", lambda: 7200)
    assert budget.reserve(tmp_path, "root", "two", limits) is None
    budget.observe(tmp_path, "root", "b")
    assert "cannot resume" in budget.observe(tmp_path, "root", "a")
    with budget.ledger(tmp_path, "root") as state:
        assert len(state["reservations"]) == 2
        assert list(state["reservations"].values())[0]["status"] == "suspect_zombie"
    budget.observe(tmp_path, "root", "b", stopped=True)
    assert budget.observe(tmp_path, "root", "a") is None


@pytest.mark.parametrize("strict", [False, True])
def test_twenty_minutes_is_allowed_and_hour_cap_is_strict_only(
    event: dict, monkeypatch: pytest.MonkeyPatch, strict: bool
) -> None:
    if strict:
        monkeypatch.setenv("NUZANTARA_MANDATE_ID", "autonomous")
    monkeypatch.setattr(child.time, "time", lambda: 100)
    guard = {"_read_tail": lambda _: Path(event["transcript_path"]).read_text()}
    assert child.context_guard(event, guard) == 0
    monkeypatch.setattr(child.time, "time", lambda: 1301)
    assert child.context_guard(event, guard) == 0
    monkeypatch.setattr(child.time, "time", lambda: 3701)
    assert child.context_guard(event, guard) == (2 if strict else 0)
    key, _ = child.child_identity(event)
    with child.child_state(key) as (_, state):
        assert state["time_budget_exceeded"]
        assert bool(state.get("return_required")) == strict
        assert state["status"] == "needs_attention"


def test_opus_canonical_calibration_rejects_expiry_scope_and_version(
    event: dict,
) -> None:
    observed = ctx.snapshot(Path(event["transcript_path"]).read_text())
    result = {
        "type": "result",
        "is_error": False,
        "modelUsage": {
            "claude-opus-5[1m]": {
                "canonicalModel": "claude-opus-5",
                "contextWindow": 1000000,
            }
        },
    }
    cwd = event["cwd"]
    assert ctx.capacity("claude-opus-5", "test", cwd) is None
    assert len(ctx.calibrate(result, [observed], cwd)) == 1
    assert ctx.capacity("claude-opus-5", "test", cwd) == 1000000
    assert ctx.capacity("claude-opus-5", "new", cwd) is None
    path = ctx.calibration_path("claude-opus-5", "test", cwd)
    data = json.loads(path.read_text())
    data["observed_at"] -= ctx.TTL + 1
    path.write_text(json.dumps(data))
    assert ctx.capacity("claude-opus-5", "test", cwd) is None
    ctx.calibrate(result, [observed], cwd)
    data = json.loads(path.read_text())
    data["scope"] = "wrong"
    path.write_text(json.dumps(data))
    assert ctx.capacity("claude-opus-5", "test", cwd) is None


def test_routing_suffix_without_native_canonical_binding_never_calibrates(
    event: dict,
) -> None:
    observed = ctx.snapshot(Path(event["transcript_path"]).read_text())
    result = {
        "type": "result",
        "is_error": False,
        "modelUsage": {"claude-opus-5[1m]": {"contextWindow": 1000000}},
    }
    assert ctx.calibrate(result, [observed], event["cwd"]) == []


def test_recent_transcript_keeps_slot_despite_silent_hook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    limits = {"strict": True, "max_active": 1, "active_ttl": 1800, "max_seconds": 10000}
    transcript = tmp_path / "agent-a.jsonl"
    transcript.write_text("{}")
    monkeypatch.setattr(budget.time, "time", lambda: 100)
    budget.reserve(tmp_path, "root", "one", limits)
    budget.observe(tmp_path, "root", "a", transcript=str(transcript))
    monkeypatch.setattr(budget.time, "time", lambda: 2500)
    os.utime(transcript, (2400, 2400))
    assert "concurrent" in budget.reserve(tmp_path, "root", "two", limits)
    transcript.unlink()
    assert "concurrent" in budget.reserve(tmp_path, "root", "two", limits)
    with budget.ledger(tmp_path, "root") as state:
        assert next(iter(state["reservations"].values()))["status"] == "active"


@pytest.mark.parametrize("calibrated", [False, True])
def test_interactive_observes_every_budget_and_retains_attention_after_stop(
    event: dict,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    calibrated: bool,
) -> None:
    transcript = Path(event["transcript_path"])
    row = json.loads(transcript.read_text())
    row["message"]["usage"]["input_tokens"] = 500000
    transcript.write_text(json.dumps(row))
    if calibrated:
        event["context_window"] = {"context_window_size": 1000000}
    key, _ = child.child_identity(event)
    with child.child_state(key) as (_, state):
        state.update(pretool_count=120, budget_started_at=1, return_required=True)
    monkeypatch.setattr(child.time, "time", lambda: 4001)
    guard = {"_read_tail": lambda _: transcript.read_text()}
    assert child.context_guard(event, guard) == 0
    output = json.loads(capsys.readouterr().out)
    assert (
        "needs_attention, no denial"
        in output["hookSpecificOutput"]["additionalContext"]
    )
    assert child.stop_guard({**event, "hook_event_name": "SubagentStop"}, {}) == 0
    with child.child_state(key) as (_, state):
        assert state["status"] == "needs_attention" and not state.get("denials")
        assert state["budget_elapsed"] == 4000 and "budget_started_at" not in state


def test_unknown_warns_each_tool_and_strict_emergency_boundary(
    event: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("NUZANTARA_MANDATE_ID", "strict")
    path = Path(event["transcript_path"])
    row = json.loads(path.read_text())
    row["message"]["usage"]["input_tokens"] = 399999
    path.write_text(json.dumps(row))
    guard = {"_read_tail": lambda _: path.read_text()}
    for _ in range(2):
        assert child.context_guard(event, guard) == 0
        assert (
            "UNKNOWN"
            in json.loads(capsys.readouterr().out)["hookSpecificOutput"][
                "additionalContext"
            ]
        )
    row["message"]["usage"]["input_tokens"] = 400000
    path.write_text(json.dumps(row))
    assert child.context_guard(event, guard) == 2


def test_stale_child_cannot_execute_after_replacement_but_can_report(
    event: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NUZANTARA_MANDATE_ID", "strict")
    monkeypatch.setattr(budget.time, "time", lambda: 100)
    path = Path(event["transcript_path"])
    os.utime(path, (100, 100))
    limits = {"strict": True, "max_active": 1, "active_ttl": 1800}
    budget.reserve(child.budget_dir(), "strict", "one", limits)
    guard = {"_read_tail": lambda _: path.read_text()}
    child.context_guard(event, guard)
    monkeypatch.setattr(budget.time, "time", lambda: 2001)
    assert budget.reserve(child.budget_dir(), "strict", "two", limits) is None
    budget.observe(child.budget_dir(), "strict", "replacement")
    assert child.context_guard(event, guard) == 2
    assert child.context_guard({**event, "tool_name": "SendMessage"}, guard) == 0


def test_installer_canary_retargets_existing_adapter_without_changing_timeout() -> None:
    from install_claude_children import route_settings

    config = {
        "hooks": {
            "PreToolUse": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python /home/old/child_workflow.py context",
                            "timeout": 17,
                        }
                    ]
                }
            ]
        }
    }
    output = route_settings(config, Path("/tmp/candidate"))
    hook = output["hooks"]["PreToolUse"][0]["hooks"][0]
    assert (
        hook["command"] == "python /tmp/candidate/child_workflow.py context"
        and hook["timeout"] == 17
    )


def test_capped_child_names_the_counter_and_keeps_its_report_path(
    event: dict, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The deny must be readable, and the report path must survive the deny.

    Two defects in one gesture: the denial recited the contract without naming
    which counter fired or by how much, and it denied `ToolSearch` -- so in a
    harness that defers tool schemas, the child was told to SendMessage while
    the only way to load SendMessage's schema was blocked.
    """
    monkeypatch.setenv("NUZANTARA_MANDATE_ID", "strict-mandate-42")
    path = Path(event["transcript_path"])
    guard = {"_read_tail": lambda _: path.read_text()}
    key, _ = child.child_identity(event)
    with child.child_state(key) as (_, state):
        state["pretool_count"] = ctx.MAX_TOOL_CALLS
    assert child.context_guard(event, guard) == 2
    denial = capsys.readouterr().err
    for field in (
        "counter=tool_calls",
        "used=" + str(ctx.MAX_TOOL_CALLS + 1),
        "limit=" + str(ctx.MAX_TOOL_CALLS),
        "role=builder",
        "mandate=strict-mandate-42",
        "SendMessage",
        "TaskStop",
    ):
        assert field in denial, field
    with child.child_state(key) as (_, state):
        assert state["budget_used"] == ctx.MAX_TOOL_CALLS + 1
        assert state["budget_limit"] == ctx.MAX_TOOL_CALLS
    search = {**event, "tool_name": "ToolSearch"}
    # Readable query naming a report tool: allowed. No query at all: allowed as a
    # whole rather than trapping the child. Any other query: denied like the rest.
    assert child.context_guard({**search, "tool_input": {"query": "select:SendMessage"}}, guard) == 0
    assert child.context_guard({**search, "tool_input": {"query": "+taskstop return"}}, guard) == 0
    assert child.context_guard(search, guard) == 0
    assert child.context_guard({**search, "tool_input": {"query": "select:Bash"}}, guard) == 2
    assert child.context_guard({**event, "tool_name": "SendMessage"}, guard) == 0
