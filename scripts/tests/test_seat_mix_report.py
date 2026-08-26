"""Tests for scripts/seat_mix_report.py -- A7/R12 daily seat-mix telemetry.

Module is imported via importlib.util.spec_from_file_location (not a package
import) because scripts/ is a flat bag of standalone tools, not a Python
package -- same convention as test_pending_arms_report.py.
"""

from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path
from types import ModuleType

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "seat_mix_report.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seat_mix_report", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


smr = _load_module()


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _agent_line(model=None, subagent_type="general-purpose", branch="main"):
    inp = {"description": "task", "prompt": "do the thing"}
    if model is not None:
        inp["model"] = model
    if subagent_type is not None:
        inp["subagent_type"] = subagent_type
    return {
        "type": "assistant",
        "gitBranch": branch,
        "message": {
            "model": "claude-sonnet-5",
            "content": [{"type": "tool_use", "id": "t1", "name": "Agent", "input": inp}],
        },
    }


def _bash_line(command, branch="main"):
    return {
        "type": "assistant",
        "gitBranch": branch,
        "message": {
            "model": "claude-sonnet-5",
            "content": [
                {"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": command}}
            ],
        },
    }


def _workflow_line(branch="main"):
    return {
        "type": "assistant",
        "gitBranch": branch,
        "message": {
            "model": "claude-sonnet-5",
            "content": [{"type": "tool_use", "id": "t3", "name": "Workflow", "input": {"script": "..."}}],
        },
    }


def _tool_result_line(text, branch="main"):
    """Shape of a captured tool_result -- must NEVER be read by the scanner."""
    return {
        "type": "user",
        "gitBranch": branch,
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "content": text}],
        },
    }


def _write_jsonl(path: Path, records) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


def _touch_recent(path: Path, minutes_ago: float = 1.0) -> None:
    ts = time.time() - minutes_ago * 60
    os.utime(path, (ts, ts))


def _touch_old(path: Path, hours_ago: float = 999.0) -> None:
    ts = time.time() - hours_ago * 3600
    os.utime(path, (ts, ts))


# ---------------------------------------------------------------------------
# The mandate's combined fixture: 3 Agent (2 sonnet, 1 haiku),
# 2 Bash seat calls (codex-sol, kimi-k3), 1 Workflow.
# ---------------------------------------------------------------------------


def test_end_to_end_exact_counts(tmp_path):
    root = tmp_path / "projects"
    fp = root / "proj1" / "session1.jsonl"
    records = [
        _agent_line(model="sonnet"),
        _agent_line(model="sonnet"),
        _agent_line(model="haiku"),
        _bash_line('codex exec -m gpt-5.6-sol -c model_reasoning_effort="ultra" --sandbox workspace-write "review"'),
        _bash_line('kimi -p "review this" -m kimi-code/k3 < /dev/null'),
        _workflow_line(),
    ]
    _write_jsonl(fp, records)
    _touch_recent(fp)

    report = smr.build_report(root, since_epoch=time.time() - 3600)

    assert report["sessions_scanned"] == 1
    assert report["files_skipped"] == 0

    ad = report["agent_dispatches"]
    assert ad["total"] == 3
    assert ad["by_model"] == {"sonnet": 2, "haiku": 1}
    assert ad["by_model_pct"]["sonnet"] == 66.7
    assert ad["by_model_pct"]["haiku"] == 33.3
    assert ad["cheap_seat_share_pct"] == 33.3

    nac = report["non_anthropic_seat_calls"]
    assert nac["total"] == 2
    assert nac["by_seat"] == {"codex:sol": 1, "kimi:k3": 1}
    assert nac["per_anthropic_dispatch"] == round(2 / 3, 2)

    assert report["workflow_runs"] == 1


def test_unspecified_model_becomes_inherit(tmp_path):
    root = tmp_path / "projects"
    fp = root / "p" / "s.jsonl"
    _write_jsonl(fp, [_agent_line(model=None, subagent_type=None)])
    _touch_recent(fp)

    report = smr.build_report(root, since_epoch=time.time() - 3600)
    assert report["agent_dispatches"]["by_model"] == {"inherit": 1}
    assert report["agent_dispatches"]["by_subagent_type"] == {"unspecified": 1}


# ---------------------------------------------------------------------------
# Window filtering + large-file skip
# ---------------------------------------------------------------------------


def test_out_of_window_file_is_ignored_not_skipped(tmp_path):
    root = tmp_path / "projects"
    fp = root / "p" / "old.jsonl"
    _write_jsonl(fp, [_agent_line(model="sonnet")])
    _touch_old(fp, hours_ago=200)

    report = smr.build_report(root, since_epoch=time.time() - 3600)  # 1h window
    assert report["sessions_scanned"] == 0
    assert report["files_skipped"] == 0
    assert report["agent_dispatches"]["total"] == 0


def test_oversized_file_is_skipped_and_counted(tmp_path):
    root = tmp_path / "projects"
    fp = root / "p" / "huge.jsonl"
    _write_jsonl(fp, [_agent_line(model="sonnet")])
    _touch_recent(fp)

    # Use a tiny max_file_bytes instead of writing a literal 200MB fixture.
    tiny_cap = 4  # our fixture file is far bigger than 4 bytes
    report = smr.build_report(root, since_epoch=time.time() - 3600, max_file_bytes=tiny_cap)

    assert report["files_skipped"] == 1
    assert report["sessions_scanned"] == 0
    assert report["agent_dispatches"]["total"] == 0


# ---------------------------------------------------------------------------
# PII boundary
# ---------------------------------------------------------------------------


SECRET_EMAIL = "john.doe@example.com"
SECRET_PHONE = "+1-555-123-4567"
SECRET_KEY = "sk-abc123secretvalue"


def test_pii_in_tool_result_and_command_text_never_leaks(tmp_path):
    root = tmp_path / "projects"
    fp = root / "p" / "s.jsonl"
    leaking_text = f"contact {SECRET_EMAIL} or {SECRET_PHONE}, key {SECRET_KEY}"
    records = [
        # A tool_result block: the scanner must never even look at "content"
        # on a non tool_use block.
        _tool_result_line(leaking_text),
        # A Bash command that does NOT match the seat vocabulary but whose
        # argument text carries the same secrets -- classify_bash_seat must
        # return None and the raw command must never be retained.
        _bash_line(f"echo '{leaking_text}'"),
        # A matching seat call whose flag value happens to carry the email --
        # only the narrow-charset capture may survive, never the full string.
        _bash_line(f"agy -p 'hi' --model {SECRET_EMAIL}"),
        _agent_line(model="sonnet"),
    ]
    _write_jsonl(fp, records)
    _touch_recent(fp)

    report = smr.build_report(root, since_epoch=time.time() - 3600)
    smr.assert_all_strings_safe(report)  # must not raise

    blob_json = json.dumps(report)
    blob_md = smr.render_markdown(report)

    for secret in (SECRET_EMAIL, SECRET_PHONE, SECRET_KEY, leaking_text):
        assert secret not in blob_json
        assert secret not in blob_md

    # the non-matching echo command contributed nothing to seat_calls
    assert report["non_anthropic_seat_calls"]["total"] == 1  # only the agy call
    # the agy call's --model value could not have survived whole (it fails
    # the safe charset because of '@' and '.') -- confirm it was sanitized,
    # not silently included verbatim.
    seat_keys = list(report["non_anthropic_seat_calls"]["by_seat"].keys())
    assert len(seat_keys) == 1
    assert SECRET_EMAIL not in seat_keys[0]


def test_guard_rejects_unsafe_strings():
    with pytest.raises(ValueError):
        smr.assert_all_strings_safe({"x": "has an @ sign which is not allowed"})
    with pytest.raises(ValueError):
        smr.assert_all_strings_safe({"x": "y" * 121})
    # compliant input must pass silently
    smr.assert_all_strings_safe({"x": "codex:sol", "y": ["a-b_c.d/e:f%g(h)i=j,k 1"]})


def test_sanitize_str_strips_disallowed_chars_and_truncates():
    assert smr.sanitize_str(None) == "unknown"
    assert smr.sanitize_str("plain-ok_1.2") == "plain-ok_1.2"
    out = smr.sanitize_str("bad@chars#here!")
    assert smr.SAFE_STRING_RE.match(out)
    assert "@" not in out and "#" not in out and "!" not in out
    long_out = smr.sanitize_str("x" * 500, maxlen=10)
    assert len(long_out) <= 10


# ---------------------------------------------------------------------------
# classify_bash_seat -- guilt AND innocence (cicatrix family #3 discipline)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command,expected",
    [
        ('codex exec -m gpt-5.6-sol --sandbox workspace-write "x"', "codex:sol"),
        ('codex exec -m gpt-5.6-terra --sandbox workspace-write "x"', "codex:terra"),
        ('codex exec -m gpt-5.6-luna --sandbox workspace-write "x"', "codex:luna"),
        ("codex exec --sandbox read-only ping", "codex:default"),
        ('kimi -p "x" -m kimi-code/k3', "kimi:k3"),
        ('kimi -p "x" -m kimi-code/kimi-for-coding', "kimi:kimi-for-coding"),
        ('kimi -p "x" -m kimi-code/kimi-for-coding-highspeed', "kimi:kimi-for-coding-highspeed"),
        ('kimi -p "x" < /dev/null', "kimi:default"),
        ("agy -p 'hi' --model gemini-3.1-pro", "agy:gemini-3.1-pro"),
        ("agy -p 'hi'", "agy:default"),
        ("scripts/seat_build.sh --seat A2 --tier gold", "seat_build:A2/gold"),
        ("scripts/seat_build.sh", "seat_build:default"),
        ("ollama run qwen3.5:9b", "ollama:qwen3.5:9b"),
        ("echo hi && nlm query foo", "nlm"),
        ("python3 notebooklm_bridge.py", "nlm"),
        ("python3 scripts/jules_dispatch.py --task x", "jules_dispatch"),
        ("python3 scripts/tp1_call.py --model x", "tp1"),
        ("curl http://localhost/review_routes", "tp1"),
    ],
)
def test_classify_bash_seat_guilt(command, expected):
    assert smr.classify_bash_seat(command) == expected


@pytest.mark.parametrize(
    "command",
    [
        "ls -la",
        "git status",
        "pytest -q",
        "echo the codex executable path",  # "codex exec" must not over-match "executable"
        "codexy exec foo",  # word-boundary: not the literal token "codex"
        "echo mykimi -m kimi-code/k3",  # "kimi" must be its own token, not a substring
        "echo my-agy-wrapper --model x",  # "agy" must be its own token
        "",
        None,
    ],
)
def test_classify_bash_seat_innocence(command):
    assert smr.classify_bash_seat(command) is None


# ---------------------------------------------------------------------------
# PR join (dependency-injected, no real gh/network in tests)
# ---------------------------------------------------------------------------


def test_pr_join_maps_session_activity_to_pr(tmp_path):
    root = tmp_path / "projects"
    fp = root / "p" / "s.jsonl"
    _write_jsonl(
        fp,
        [
            _agent_line(model="sonnet", branch="agent/pro/infra/seat-mix"),
            _bash_line("codex exec -m gpt-5.6-terra ping", branch="agent/pro/infra/seat-mix"),
        ],
    )
    _touch_recent(fp)

    calls = []

    def fake_lookup(branch):
        calls.append(branch)
        return "5099" if branch == "agent/pro/infra/seat-mix" else None

    report = smr.build_report(root, since_epoch=time.time() - 3600, pr_lookup=fake_lookup)

    assert calls == ["agent/pro/infra/seat-mix"]  # called once, cached per branch
    assert report["per_pr"] == {"5099": {"agent_dispatches": 1, "seat_calls": 1, "sessions": 1}}
    assert report["unmapped_sessions_with_activity"] == 0


def test_pr_join_unmapped_when_lookup_returns_none(tmp_path):
    root = tmp_path / "projects"
    fp = root / "p" / "s.jsonl"
    _write_jsonl(fp, [_agent_line(model="sonnet", branch="scratch/nobody")])
    _touch_recent(fp)

    report = smr.build_report(root, since_epoch=time.time() - 3600, pr_lookup=lambda b: None)
    assert report["per_pr"] == {}
    assert report["unmapped_sessions_with_activity"] == 1


def test_no_pr_lookup_means_all_unmapped_and_no_calls(tmp_path):
    root = tmp_path / "projects"
    fp = root / "p" / "s.jsonl"
    _write_jsonl(fp, [_agent_line(model="sonnet", branch="whatever")])
    _touch_recent(fp)

    report = smr.build_report(root, since_epoch=time.time() - 3600, pr_lookup=None)
    assert report["per_pr"] == {}
    assert report["unmapped_sessions_with_activity"] == 1


def test_session_with_no_dispatch_activity_is_scanned_but_not_pr_accounted(tmp_path):
    root = tmp_path / "projects"
    fp = root / "p" / "s.jsonl"
    _write_jsonl(fp, [_tool_result_line("just chatter, no tools")])
    _touch_recent(fp)

    calls = []
    report = smr.build_report(
        root, since_epoch=time.time() - 3600, pr_lookup=lambda b: calls.append(b) or "999"
    )
    assert report["sessions_scanned"] == 1
    assert calls == []  # never even attempted a lookup for a session with no activity
    assert report["unmapped_sessions_with_activity"] == 0
    assert report["per_pr"] == {}


# ---------------------------------------------------------------------------
# Markdown rendering sanity
# ---------------------------------------------------------------------------


def test_render_markdown_is_nonempty_and_contains_headline_numbers(tmp_path):
    root = tmp_path / "projects"
    fp = root / "p" / "s.jsonl"
    _write_jsonl(fp, [_agent_line(model="sonnet"), _workflow_line()])
    _touch_recent(fp)

    report = smr.build_report(root, since_epoch=time.time() - 3600)
    report["window_hours"] = 24
    md = smr.render_markdown(report)
    assert "# Seat-mix daily report" in md
    assert "Total Agent dispatches: 1" in md
    assert "workflow_runs: 1" in md


def test_empty_root_returns_zeroed_report(tmp_path):
    root = tmp_path / "does-not-exist"
    report = smr.build_report(root, since_epoch=time.time() - 3600)
    assert report["sessions_scanned"] == 0
    assert report["agent_dispatches"]["total"] == 0
    assert report["non_anthropic_seat_calls"]["total"] == 0
    assert report["agent_dispatches"]["cheap_seat_share_pct"] is None
    assert report["non_anthropic_seat_calls"]["per_anthropic_dispatch"] is None
