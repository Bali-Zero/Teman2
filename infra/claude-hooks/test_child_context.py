"""Regression tests for missing measurements and seat-local capacity calibration."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1] / "codex-hooks"))
import child_context as ctx
import child_workflow as child


def row(used: int = 12, **usage: int) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "version": "2.1.test",
            "message": {
                "id": "message",
                "model": "child-model",
                "usage": {"input_tokens": used, **usage},
            },
        }
    )


@pytest.fixture
def calibrated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "seat"))
    ctx.calibrate(
        {
            "type": "result",
            "is_error": False,
            "session_id": "probe",
            "modelUsage": {"child-model": {"contextWindow": 200000}},
        },
        [ctx.snapshot(row())],
        str(tmp_path),
    )
    return tmp_path


def test_native_request_not_lifetime_or_streaming_sum() -> None:
    tail = "\n".join(
        [
            row(100000),
            row(
                8,
                cache_read_input_tokens=2000,
                cache_creation_input_tokens=500,
                output_tokens=3,
            ),
        ]
        * 2
    )
    assert ctx.snapshot(tail)["used"] == 2511
    missing = json.dumps({"type": "assistant", "message": {"model": "new-model"}})
    assert ctx.snapshot(tail + "\n" + missing)["used"] is None
    assert ctx.snapshot(row(True))["used"] is None
    assert ctx.snapshot(row(-1))["used"] is None


def test_calibration_expires_and_never_crosses_identity(
    calibrated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cwd = str(calibrated)
    assert ctx.capacity("child-model", "2.1.test", cwd) == 200000
    assert ctx.capacity("parent-model", "2.1.test", cwd) is None
    assert ctx.capacity("child-model", "2.2.new", cwd) is None
    path = ctx.calibration_path("child-model", "2.1.test", cwd)
    record = json.loads(path.read_text())
    record["observed_at"] -= ctx.TTL + 1
    path.write_text(json.dumps(record))
    assert ctx.capacity("child-model", "2.1.test", cwd) is None
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(calibrated / "second-seat"))
    assert ctx.capacity("child-model", "2.1.test", cwd) is None


def test_config_routing_and_project_changes_invalidate(
    calibrated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cwd = str(calibrated)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://example.invalid")
    assert ctx.capacity("child-model", "2.1.test", cwd) is None
    monkeypatch.delenv("ANTHROPIC_BASE_URL")
    project = calibrated / ".claude"
    project.mkdir()
    (project / "settings.json").write_text(
        '{"env":{"CLAUDE_CODE_DISABLE_1M_CONTEXT":"1"}}'
    )
    assert ctx.capacity("child-model", "2.1.test", cwd) is None


@pytest.mark.parametrize("reason", ["tokens", "tools", "time", "known"])
def test_budget_returns_checkpoint_without_grace_or_reopening(
    calibrated: Path, reason: str
) -> None:
    transcript = calibrated / "subagents" / "agent-a.jsonl"
    transcript.parent.mkdir()
    transcript.write_text(row(80000 if reason == "known" else 64000))
    payload = {
        "session_id": "parent",
        "agent_id": "a",
        "tool_name": "Read",
        "hook_event_name": "PreToolUse",
        "transcript_path": str(transcript),
        "cwd": str(calibrated),
    }
    key, _ = child.child_identity(payload)
    if reason != "known":
        transcript.write_text("{}")
        with child.child_state(key) as (_, state):
            if reason == "tools":
                state["pretool_count"] = ctx.MAX_TOOL_CALLS
            elif reason == "time":
                state["budget_started_at"] = ctx.time.time() - ctx.MAX_SECONDS - 1
        if reason == "tokens":
            transcript.write_text(row(64000).replace("child-model", "uncalibrated"))
    guard = {"_read_tail": lambda _: transcript.read_text()}
    assert child.context_guard(payload, guard) == 2
    transcript.write_text(row(10))
    assert child.context_guard(payload, guard) == 2
    assert child.context_guard({**payload, "tool_name": "SendMessage"}, guard) == 0
    with child.child_state(key) as (_, state):
        assert state["return_required"] and state["acceptance"] == "unverified"


def test_failed_probe_never_calibrates(calibrated: Path) -> None:
    assert (
        ctx.calibrate(
            {"type": "result", "is_error": True}, [ctx.snapshot(row())], str(calibrated)
        )
        == []
    )


def test_permissions_do_not_invalidate_capacity(calibrated: Path) -> None:
    project = calibrated / ".claude"
    project.mkdir()
    (project / "settings.json").write_text(
        '{"$schema":"fixture","permissions":{"allow":["Read"]}}'
    )
    assert ctx.capacity("child-model", "2.1.test", str(calibrated)) == 200000


def test_missing_tail_allows_short_child_and_idle_does_not_consume_budget(
    calibrated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = calibrated / "subagents" / "agent-a.jsonl"
    transcript.parent.mkdir()
    transcript.write_text("{}")
    payload = {
        "session_id": "parent",
        "agent_id": "a",
        "tool_name": "Read",
        "hook_event_name": "PreToolUse",
        "transcript_path": str(transcript),
        "cwd": str(calibrated),
    }
    guard = {"_read_tail": lambda _: None}
    monkeypatch.setattr(child.time, "time", lambda: 100)
    assert child.context_guard(payload, guard) == 0
    monkeypatch.setattr(child.time, "time", lambda: 110)
    assert (
        child.stop_guard(
            {
                **payload,
                "hook_event_name": "SubagentStop",
                "agent_transcript_path": str(transcript),
            },
            {},
        )
        == 0
    )
    monkeypatch.setattr(child.time, "time", lambda: 10000)
    assert child.context_guard(payload, guard) == 0
    key, _ = child.child_identity(payload)
    with child.child_state(key) as (_, state):
        assert state["budget_elapsed"] == 10
        assert state["pretool_count"] == 2
        assert state["measurement"] == "UNKNOWN"
    monkeypatch.setattr(child.time, "time", lambda: 10900)
    assert child.context_guard(payload, guard) == 2


def test_calibration_uses_hook_environment_not_invoker(
    calibrated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cwd = str(calibrated)
    monkeypatch.setenv("CLAUDE_CODE_DISABLE_1M_CONTEXT", "1")
    fingerprint = ctx.scope(cwd)
    monkeypatch.delenv("CLAUDE_CODE_DISABLE_1M_CONTEXT")
    observed = {**ctx.snapshot(row()), "capacity_scope": fingerprint}
    ctx.calibrate(
        {
            "type": "result",
            "is_error": False,
            "modelUsage": {"child-model": {"contextWindow": 180000}},
        },
        [observed],
        cwd,
    )
    assert ctx.capacity("child-model", "2.1.test", cwd) == 200000
    monkeypatch.setenv("CLAUDE_CODE_DISABLE_1M_CONTEXT", "1")
    assert ctx.capacity("child-model", "2.1.test", cwd) == 180000
