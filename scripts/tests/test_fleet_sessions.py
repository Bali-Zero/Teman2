"""
Tests for fleet_sessions.py — protect the phantom organ death detector,
the JSON contract, alive-ladder honesty, PII boundary, and all classifier
boundaries.  NO live network, no ssh, no real ~/.claude access anywhere in this
file.  All remote probes are monkeypatched; the local probe is driven by
HOME=tmp_path and mocked subprocess calls.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from datetime import datetime, timezone, timedelta

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "fleet_sessions.py"

def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fleet_sessions", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

fs = _load_module()

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _write_transcript(
    tmp_path: Path,
    encoded_dir: str,
    session_id: str,
    lines: list[dict],
    mtime_epoch: float,
    *,
    cwd: str | None = None,
    symlink_target: Path | None = None,
) -> Path:
    """Create a session transcript under a project dir, set its mtime.

    Returns the path to the .jsonl file.
    """
    projects = tmp_path / ".claude" / "projects"
    if symlink_target is not None:
        # symlink the encoded_dir to the target
        projects.mkdir(parents=True, exist_ok=True)
        dest = projects / encoded_dir
        dest.symlink_to(symlink_target)
    else:
        dir_path = projects / encoded_dir
        dir_path.mkdir(parents=True)
    file_path = projects / encoded_dir / f"{session_id}.jsonl"
    if symlink_target is None:
        file_path.write_text(
            "\n".join(json.dumps(line) for line in lines) + "\n",
            encoding="utf-8",
        )
    os.utime(file_path, (mtime_epoch, mtime_epoch))
    return file_path


def _make_mock_check_output(ps_text: str, lsof_text: str):
    """Return a function that mimics subprocess.check_output for ps/lsof."""
    def _mock(cmd, *args, **kwargs):
        if isinstance(cmd, list) and cmd[0] == "ps":
            return ps_text
        if isinstance(cmd, list) and cmd[0] == "lsof":
            return lsof_text
        raise RuntimeError(f"unexpected command: {cmd}")
    return _mock


def _mock_run_host_probe(return_code=0, stdout="{}", stderr="", exc=None):
    """Return a mock for fs.run_host_probe."""
    def _mock(host, argv, timeout):
        if exc is not None:
            raise exc
        return return_code, stdout, stderr
    return _mock


# ---------------------------------------------------------------------------
# 1. GUILT — canonical dead-but-declared-long
# ---------------------------------------------------------------------------

def test_guilt_declared_span_unmet(tmp_path, monkeypatch, capsys):
    """
    A session whose first user message declares a long run ("loop 4h"),
    NO live process, transcript 193 minutes stale, span 6.5 minutes
    => DECLARED-SPAN-UNMET.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    NOW = 1690000000.0
    monkeypatch.setattr(time, "time", lambda: NOW)

    # build transcript
    lines = [
        {"type": "user", "message": {"content": "Sei il GUARITORE ... Giri in loop 4h ..."}},
        {"type": "assistant", "message": {"content": "ok"}},
    ]
    # timestamps: first at 0, last at 6.5 min later
    t0 = datetime(2026, 8, 23, 6, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=6.5)
    for line in lines:
        line["timestamp"] = (t0 if line["type"] == "user" else t1).isoformat()

    _write_transcript(
        tmp_path,
        "-Users-nuzantara-nuzantara",
        "f9dd23da-8d36-4b7b-957d-077091090fec",
        lines,
        NOW - 193 * 60,  # 193 min stale
    )

    # no live processes
    monkeypatch.setattr(subprocess, "check_output", _make_mock_check_output("", ""))

    # run the probe
    from io import StringIO
    import sys
    hold = sys.stdout
    sys.stdout = StringIO()
    try:
        report = fs.probe_local(lookback_min=360, quiet_min=5, stale_min=45)
    finally:
        sys.stdout = hold

    assert report["status"] == "OK"
    sessions = report["sessions"]
    assert len(sessions) == 1
    s = sessions[0]
    assert s["session_id"] == "f9dd23da-8d36-4b7b-957d-077091090fec"
    assert s["verdict"] == fs.DECLARED_SPAN_UNMET
    assert s["declared_long"] is True
    assert s["declared_span_min"] == 240
    assert s["transcript_span_min"] == 6.5
    assert s["alive"] == fs.NO_PROCESS


# ---------------------------------------------------------------------------
# 2. INNOCENCE — same long declaration, but session is alive
# ---------------------------------------------------------------------------

def test_innocence_alive_same_long_declaration(tmp_path, monkeypatch):
    """Same declared-long first message, but a live process names the session id."""
    monkeypatch.setenv("HOME", str(tmp_path))
    NOW = 1690000000.0
    monkeypatch.setattr(time, "time", lambda: NOW)

    lines = [
        {"type": "user", "message": {"content": "Sei il GUARITORE ... Giri in loop 4h ..."}},
        {"type": "assistant", "message": {"content": "ok"}},
    ]
    t0 = datetime(2026, 8, 23, 6, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=6.5)
    for line in lines:
        line["timestamp"] = (t0 if line["type"] == "user" else t1).isoformat()

    _write_transcript(
        tmp_path,
        "-Users-nuzantara-nuzantara",
        "f9dd23da-8d36-4b7b-957d-077091090fec",
        lines,
        NOW - 1 * 60,  # 1 min old, fresh
    )

    # ps output showing a live session process with parent-session-id
    ps_text = (
        "1234 claude --agent-id p0recheck@session-c03d6208 "
        "--parent-session-id f9dd23da-8d36-4b7b-957d-077091090fec "
        "--agent-type general-purpose --model sonnet\n"
    )
    # lsof mapping the pid to the cwd that matches the encoded dir
    lsof_text = (
        "p1234\n"
        "fcwd\n"
        "n/Users/nuzantara/nuzantara\n"
    )
    monkeypatch.setattr(subprocess, "check_output", _make_mock_check_output(ps_text, lsof_text))

    report = fs.probe_local(lookback_min=360, quiet_min=5, stale_min=45)
    sessions = report["sessions"]
    assert len(sessions) == 1
    s = sessions[0]
    assert s["alive"] == fs.ALIVE
    assert s["verdict"] == fs.PRODUCING   # fresh, so PRODUCING
    assert s["declared_long"] is True
    # not flagged as DECLARED-SPAN-UNMET
    assert s["verdict"] != fs.DECLARED_SPAN_UNMET


# ---------------------------------------------------------------------------
# 3. INNOCENCE — short one-shot, no long-run phrase
# ---------------------------------------------------------------------------

def test_innocence_short_oneshot_stale(tmp_path, monkeypatch):
    """A short, no-long-run session that finished 200 min ago => STALE."""
    monkeypatch.setenv("HOME", str(tmp_path))
    NOW = 1690000000.0
    monkeypatch.setattr(time, "time", lambda: NOW)

    lines = [
        {"type": "user", "message": {"content": "Fix the failing test and wait until the tests pass, then stop."}},
        {"type": "assistant", "message": {"content": "done"}},
    ]
    t0 = datetime(2026, 8, 23, 5, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=10)
    for line in lines:
        line["timestamp"] = (t0 if line["type"] == "user" else t1).isoformat()

    _write_transcript(
        tmp_path,
        "-Users-nuzantara-nuzantara",
        "some-id",
        lines,
        NOW - 200 * 60,
    )

    monkeypatch.setattr(subprocess, "check_output", _make_mock_check_output("", ""))

    report = fs.probe_local(lookback_min=360, quiet_min=5, stale_min=45)
    sessions = report["sessions"]
    assert len(sessions) == 1
    s = sessions[0]
    assert s["verdict"] == fs.STALE
    assert s["declared_long"] is False


def test_innocence_until_not_long():
    """The word 'until' is NOT a long-run phrase by itself."""
    text = "Fix the failing test and wait until the tests pass, then stop."
    is_long, span = fs.declared_long(text)
    assert is_long is False
    assert span is None


# ---------------------------------------------------------------------------
# 4. UNREACHABLE host degrades cleanly
# ---------------------------------------------------------------------------

def test_unreachable_host_rc_failure(tmp_path, monkeypatch, capsys):
    """run_host_probe returns non-zero => host UNREACHABLE, other hosts still reported."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # local host is OK, so we mock run_host_probe for remote
    monkeypatch.setattr(
        fs, "run_host_probe",
        _mock_run_host_probe(return_code=1, stdout="", stderr="connection refused"),
    )
    # local probe should succeed (no sessions)
    monkeypatch.setattr(subprocess, "check_output", _make_mock_check_output("", ""))

    import sys as _sys
    exit_code = fs.main(["--hosts", "local,remote", "--json"])
    captured = capsys.readouterr().out
    data = json.loads(captured)
    # remote host should be unreachable
    remote_entry = next(h for h in data["hosts"] if h["host"] == "remote")
    assert remote_entry["status"] == fs.UNREACHABLE
    assert "reason" in remote_entry
    assert "connection refused" in remote_entry["reason"]
    # local host should be present
    assert any(h["host"] == "local" for h in data["hosts"])
    assert exit_code == 1  # unreachable counts as finding


def test_unreachable_host_exception(tmp_path, monkeypatch, capsys):
    """run_host_probe raises subprocess.TimeoutExpired => host UNREACHABLE."""
    monkeypatch.setenv("HOME", str(tmp_path))
    exc = subprocess.TimeoutExpired(cmd="ssh", timeout=45)
    monkeypatch.setattr(
        fs, "run_host_probe",
        _mock_run_host_probe(exc=exc),
    )
    monkeypatch.setattr(subprocess, "check_output", _make_mock_check_output("", ""))

    exit_code = fs.main(["--hosts", "local,remote", "--json"])
    captured = capsys.readouterr().out
    data = json.loads(captured)
    remote_entry = [h for h in data["hosts"] if h["host"] == "remote"][0]
    assert remote_entry["status"] == fs.UNREACHABLE
    assert "reason" in remote_entry
    assert "TimeoutExpired" in remote_entry["reason"]
    assert exit_code == 1


# ---------------------------------------------------------------------------
# 5. Malformed JSON lines in transcript
# ---------------------------------------------------------------------------

def test_malformed_json_lines(tmp_path, monkeypatch):
    """Transcript with truncated/malformed lines still yields a row from good lines."""
    monkeypatch.setenv("HOME", str(tmp_path))
    NOW = 1690000000.0
    monkeypatch.setattr(time, "time", lambda: NOW)

    lines = [
        "bad line\n",
        '{"type": "user", "message": {"content": "hello"}, "timestamp": "2026-08-23T06:00:00Z"}\n',
        "another broken\n",
        '{"type": "assistant", "message": {"content": "world"}, "timestamp": "2026-08-23T06:01:00Z"}\n',
    ]
    encoded_dir = "-tmp"
    projects = tmp_path / ".claude" / "projects"
    (projects / encoded_dir).mkdir(parents=True)
    file_path = projects / encoded_dir / "session.jsonl"
    file_path.write_text("".join(lines), encoding="utf-8")
    os.utime(file_path, (NOW - 10 * 60, NOW - 10 * 60))

    monkeypatch.setattr(subprocess, "check_output", _make_mock_check_output("", ""))

    report = fs.probe_local(lookback_min=360, quiet_min=5, stale_min=45)
    sessions = report["sessions"]
    assert len(sessions) == 1
    s = sessions[0]
    assert s["identity"] == "hello"


# ---------------------------------------------------------------------------
# 6. Identity slice — PII boundary
# ---------------------------------------------------------------------------

def test_identity_slice_pii_boundary(tmp_path, monkeypatch, capsys):
    """
    A long multi-line first user message produces an identity <= 90 chars
    and a sentinel deep inside the message does NOT appear in the full JSON.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    NOW = 1690000000.0
    monkeypatch.setattr(time, "time", lambda: NOW)

    sentinel = "S3CR3T-D0-N0T-LEAK"
    # The sentinel MUST sit past character 90: the identity slice is PII-BOUNDED,
    # not PII-free — the first 90 characters of the first message are emitted by
    # design. This test proves the 91st onward never are.
    long_msg = (
        "Line 1: " + ("padding " * 20) + "\n"
        "Line 2: The sentinel is {sentinel} and must not be in output.\n"
        "Line 3: Ending with more text.\n"
    ).format(sentinel=sentinel)

    lines = [
        {"type": "user", "message": {"content": long_msg}, "timestamp": "2026-08-23T06:00:00Z"},
        {"type": "assistant", "message": {"content": "ok"}, "timestamp": "2026-08-23T06:01:00Z"},
    ]
    _write_transcript(
        tmp_path, "-tmp", "sid", lines, NOW - 10 * 60,
    )

    monkeypatch.setattr(subprocess, "check_output", _make_mock_check_output("", ""))

    exit_code = fs.main(["--hosts", "local", "--json"])  # host-explicit: a bare main() would ssh to pro/air for real
    captured = capsys.readouterr().out
    data = json.loads(captured)
    sessions = data["hosts"][0]["sessions"]
    assert len(sessions) == 1
    ident = sessions[0]["identity"]
    assert len(ident) <= 90
    assert "\n" not in ident
    # The sentinel must NOT appear anywhere in the entire JSON output
    assert sentinel not in captured


# ---------------------------------------------------------------------------
# 7. is_session_process — guilt and innocence
# ---------------------------------------------------------------------------

def test_is_session_process_guilt():
    """Exact argv strings that ARE sessions."""
    assert fs.is_session_process("claude") is True
    assert fs.is_session_process("claude interactive") is True
    assert fs.is_session_process(
        "/opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe --agent-id p0recheck@session-c03d6208 --parent-session-id c03d6208-a9fa-4db2-a78a-638b4f5f8122 --agent-type general-purpose --model sonnet"
    ) is True
    assert fs.is_session_process(
        "/Users/balizero/.local/share/mise/installs/node/22/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe"
    ) is True


def test_is_session_process_innocence():
    """Exact argv strings that are NOT sessions."""
    assert fs.is_session_process("/Applications/Claude.app/Contents/MacOS/Claude") is False
    assert fs.is_session_process(
        "/Applications/Claude.app/Contents/Helpers/chrome-native-host chrome-extension://fcoeoabgfenejglbffodgkkbkcdhcgfn/"
    ) is False
    assert fs.is_session_process(
        "/Users/balizero/.claude-science/bin/claude-science serve --app"
    ) is False
    assert fs.is_session_process(
        "tmux -L claude-swarm-42327 new-session -d -s claude-swarm -n swarm-view -P -F #{pane_id} -- cat"
    ) is False
    assert fs.is_session_process(
        "/opt/homebrew/.../Python /Users/nuzantara/.claude/daemons/guardrails.py"
    ) is False
    assert fs.is_session_process(
        "/opt/homebrew/.../Python /Users/nuzantara/.claude/skills/bali-zero-brand/_damar-queue-server.py"
    ) is False
    assert fs.is_session_process(
        "/bin/zsh -c source /Users/nuzantara/.claude/shell-snapshots/snapshot-zsh-1787465441094-ahf7td.sh 2>/dev/null || true && eval 'fly logs -a nuzantara-rag'"
    ) is False
    assert fs.is_session_process("grep -i claude") is False
    # Additional regression from semantics correction (a): basename "not-claude"
    assert fs.is_session_process("not-claude") is False


# ---------------------------------------------------------------------------
# 8. encode_project_dir
# ---------------------------------------------------------------------------

def test_encode_project_dir():
    assert fs.encode_project_dir("/Users/nuzantara/nuzantara/.worktrees/backend-rag-seq8") == "-Users-nuzantara-nuzantara--worktrees-backend-rag-seq8"
    assert fs.encode_project_dir("/private/tmp") == "-private-tmp"
    assert fs.encode_project_dir("/Users/nuzantara") == "-Users-nuzantara"


# ---------------------------------------------------------------------------
# 9. parse_ps_output
# ---------------------------------------------------------------------------

def test_parse_ps_output():
    ps_text = (
        "1234 claude\n"
        "1235 claude interactive\n"
        "1236 /opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe "
        "--agent-id X@session-c03d6208 --agent-name X --team-name session-c03d6208 "
        "--parent-session-id c03d6208-a9fa-4db2-a78a-638b4f5f8122 --agent-type ... --model sonnet\n"
        "1237 /Applications/Claude.app/Contents/MacOS/Claude\n"
    )
    parent_sids, counts, session_pids = fs.parse_ps_output(ps_text)
    assert "c03d6208-a9fa-4db2-a78a-638b4f5f8122" in parent_sids
    assert counts["c03d6208-a9fa-4db2-a78a-638b4f5f8122"] == 1
    assert session_pids == {"1234", "1235", "1236"}


def test_parse_ps_output_no_parent_sid():
    """Processes without --parent-session-id contribute neither to alive set nor counts."""
    ps_text = "1234 claude\n"
    parent_sids, counts, session_pids = fs.parse_ps_output(ps_text)
    assert parent_sids == set()
    assert counts == {}
    assert session_pids == {"1234"}


def test_parse_ps_output_multiple_subagents():
    """Two subagents with same parent-session-id count as 2 under that sid."""
    ps_text = (
        "100 claude --parent-session-id sid1\n"
        "101 claude --parent-session-id sid1\n"
    )
    parent_sids, counts, _ = fs.parse_ps_output(ps_text)
    assert parent_sids == {"sid1"}
    assert counts["sid1"] == 2


# ---------------------------------------------------------------------------
# 10. parse_lsof_cwd
# ---------------------------------------------------------------------------

def test_parse_lsof_cwd():
    lsof_text = (
        "p36463\n"
        "fcwd\n"
        "n/Users/nuzantara/nuzantara\n"
        "p99766\n"
        "fcwd\n"
        "n/Users/nuzantara/nuzantara/.worktrees/backend-rag-p0-invite-capability\n"
    )
    pid_cwd = fs.parse_lsof_cwd(lsof_text)
    assert pid_cwd == {
        36463: "/Users/nuzantara/nuzantara",
        99766: "/Users/nuzantara/nuzantara/.worktrees/backend-rag-p0-invite-capability",
    }


# ---------------------------------------------------------------------------
# 11. Alive ladder honesty
# ---------------------------------------------------------------------------

def test_alive_unmapped_when_mapping_unavailable(tmp_path, monkeypatch):
    """
    Session processes exist but lsof returns nothing => mapping_available=False,
    any session in a project dir with live processes is UNMAPPED, never NO-PROCESS.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    NOW = 1690000000.0
    monkeypatch.setattr(time, "time", lambda: NOW)

    # a transcript in a project dir
    lines = [{"type": "user", "message": {"content": "hello"}, "timestamp": "2026-08-23T06:00:00Z"}]
    _write_transcript(tmp_path, "-Users-nuzantara-nuzantara", "sid", lines, NOW - 10 * 60)

    # ps shows a live session process, but lsof returns nothing
    ps_text = "1234 claude\n"
    monkeypatch.setattr(subprocess, "check_output", _make_mock_check_output(ps_text, ""))

    report = fs.probe_local(lookback_min=360, quiet_min=5, stale_min=45)
    sessions = report["sessions"]
    assert len(sessions) == 1
    s = sessions[0]
    assert s["alive"] == fs.UNMAPPED
    assert s["verdict"] != fs.NO_PROCESS  # must not claim absence


def test_alive_no_process_mapping_available(tmp_path, monkeypatch):
    """
    mapping_available=True, no matching cwd => NO_PROCESS.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    NOW = 1690000000.0
    monkeypatch.setattr(time, "time", lambda: NOW)

    lines = [{"type": "user", "message": {"content": "hello"}, "timestamp": "2026-08-23T06:00:00Z"}]
    _write_transcript(tmp_path, "-Users-nuzantara-nuzantara", "sid", lines, NOW - 10 * 60)

    # ps empty -> session_pids empty, mapping_available is True
    monkeypatch.setattr(subprocess, "check_output", _make_mock_check_output("", ""))

    report = fs.probe_local(lookback_min=360, quiet_min=5, stale_min=45)
    sessions = report["sessions"]
    assert len(sessions) == 1
    s = sessions[0]
    assert s["alive"] == fs.NO_PROCESS


def test_alive_unmapped_matching_cwd(tmp_path, monkeypatch):
    """
    mapping_available=True, a cwd matches the encoded project dir => UNMAPPED.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    NOW = 1690000000.0
    monkeypatch.setattr(time, "time", lambda: NOW)

    lines = [{"type": "user", "message": {"content": "hello"}, "timestamp": "2026-08-23T06:00:00Z"}]
    _write_transcript(tmp_path, "-Users-nuzantara-nuzantara", "sid", lines, NOW - 10 * 60)

    # ps shows a session process, lsof maps it to the cwd that matches
    ps_text = "1234 claude\n"
    lsof_text = "p1234\nfcwd\nn/Users/nuzantara/nuzantara\n"
    monkeypatch.setattr(subprocess, "check_output", _make_mock_check_output(ps_text, lsof_text))

    report = fs.probe_local(lookback_min=360, quiet_min=5, stale_min=45)
    sessions = report["sessions"]
    assert len(sessions) == 1
    s = sessions[0]
    assert s["alive"] == fs.UNMAPPED  # because the session pid exists but not a subagent naming it
    # But the session_id is not in alive_parent_sids; we are in the else branch after checking alive_parent_sids.
    # The logic: if session_id in alive_parent_sids -> ALIVE; else if not mapping_available -> UNMAPPED; else -> NO_PROCESS, then check cwd loop.
    # Here mapping_available=True, session_id not in alive_parent_sids, so goes to NO_PROCESS initially, then the loop over cwd_to_encoded finds a match and sets alive = UNMAPPED.
    # So it should be UNMAPPED.
    assert s["alive"] == fs.UNMAPPED


# ---------------------------------------------------------------------------
# 12. Exit codes
# ---------------------------------------------------------------------------

def test_exit_code_zero_no_findings(tmp_path, monkeypatch, capsys):
    """All hosts ok, no DECLARED-SPAN-UNMET => exit 0."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(time, "time", lambda: 1690000000.0)
    monkeypatch.setattr(subprocess, "check_output", _make_mock_check_output("", ""))
    monkeypatch.setattr(fs, "run_host_probe", _mock_run_host_probe(stdout=json.dumps({"machine": "remote", "sessions": [], "status": "OK"})))
    exit_code = fs.main(["--hosts", "local,remote", "--json"])
    assert exit_code == 0


def test_exit_code_declared_span_unmet_is_reported_but_not_actionable():
    """A DECLARED-SPAN-UNMET row is REPORTED and does NOT move the exit code.

    Measured on the live fleet 2026-08-23: 10 of 10 such rows were HEALTHY
    healer ticks -- `com.nuzantara.healer.4h.plist` has StartInterval 14400, so
    "loop 4h" in a mandate's TITLE is the cron cadence, not the session's
    runtime. The exit code is reserved for coverage loss (1) and blindness (2);
    an exit code that cries "finding" when nothing is actionable trains its only
    consumer to stop reading it.
    """
    monkeypatch = pytest.MonkeyPatch()
    try:
        report = {
            "host": "remote", "machine": "R", "status": "OK", "skipped_unreadable": 0,
            "skipped_stale": 0,
            "sessions": [{
                "session_id": "sid", "project_dir": "-tmp", "cwd": "-tmp",
                "mtime_epoch": 1.0, "mtime_iso": "2026-08-23T00:00:00Z",
                "stale_min": 193.0, "size_bytes": 10, "identity": "loop 4h",
                "declared_long": True, "declared_span_min": 240,
                "transcript_span_min": 5.0, "subagents": 0,
                "alive": fs.NO_PROCESS, "verdict": fs.DECLARED_SPAN_UNMET,
            }],
        }
        monkeypatch.setattr(
            fs, "run_host_probe",
            _mock_run_host_probe(return_code=0, stdout=json.dumps(report)),
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exit_code = fs.main(["--hosts", "remote", "--json"])
        data = json.loads(buf.getvalue())
        # the row IS reported ...
        assert data["summary"]["declared_span_unmet"] == 1
        assert data["hosts"][0]["sessions"][0]["verdict"] == fs.DECLARED_SPAN_UNMET
        # ... and the run is still clean, because nothing was lost
        assert exit_code == 0
        assert data["summary"]["hosts_unreachable"] == 0
    finally:
        monkeypatch.undo()

def test_exit_code_one_unreachable(tmp_path, monkeypatch, capsys):
    """A host unreachable => exit 1."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(subprocess, "check_output", _make_mock_check_output("", ""))
    monkeypatch.setattr(
        fs, "run_host_probe",
        _mock_run_host_probe(return_code=1, stdout="", stderr="down"),
    )
    # local probes fine, remote is down => we DID probe something => 1, not BLIND
    exit_code = fs.main(["--hosts", "local,remote", "--json"])
    assert exit_code == 1


def test_exit_code_blind_all_unreachable(tmp_path, monkeypatch, capsys):
    """No host produced a successful probe => exit 2."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        fs, "run_host_probe",
        _mock_run_host_probe(return_code=1, stdout="", stderr="down"),
    )
    # local probe will also fail because we don't set up HOME properly? Actually we set HOME, but we can make local probe raise. Simpler: run only remote hosts.
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("fail")))
    exit_code = fs.main(["--hosts", "remote", "--json"])
    assert exit_code == 2


# ---------------------------------------------------------------------------
# 13. JSON contract
# ---------------------------------------------------------------------------

def test_json_output_contract(tmp_path, monkeypatch, capsys):
    """--json emits the pinned contract with summary.declared_span_unmet etc."""
    monkeypatch.setenv("HOME", str(tmp_path))
    NOW = 1690000000.0
    monkeypatch.setattr(time, "time", lambda: NOW)
    # create a dead-but-declared-long session
    lines = [
        {"type": "user", "message": {"content": "loop 4h"}, "timestamp": "2026-08-23T06:00:00Z"},
        {"type": "assistant", "message": {"content": "ok"}, "timestamp": "2026-08-23T06:05:00Z"},
    ]
    _write_transcript(tmp_path, "-tmp", "sid", lines, NOW - 193 * 60)
    monkeypatch.setattr(subprocess, "check_output", _make_mock_check_output("", ""))

    # remote host ok with no sessions
    monkeypatch.setattr(
        fs, "run_host_probe",
        _mock_run_host_probe(stdout=json.dumps({"machine": "pro", "sessions": [], "status": "OK"})),
    )

    exit_code = fs.main(["--hosts", "local,pro", "--json"])
    captured = capsys.readouterr().out
    data = json.loads(captured)
    summary = data["summary"]
    assert summary["declared_span_unmet"] == 1
    assert summary["hosts_unreachable"] == 0
    assert summary["unreachable_hosts"] == []
    assert "findings" in summary
    assert len(summary["findings"]) == 1
    assert summary["findings"][0]["session_id"] == "sid"


# ---------------------------------------------------------------------------
# 14. Selftest
# ---------------------------------------------------------------------------

def test_selftest():
    """fs._selftest() should complete without raising."""
    with pytest.raises(SystemExit) as e:
        fs._selftest()
    assert e.value.code == 0


# ---------------------------------------------------------------------------
# Semantics corrections (a) basename discrimination
# ---------------------------------------------------------------------------

def test_is_session_process_basename_not_claude():
    """'not-claude' is not a session (basename check)."""
    assert fs.is_session_process("not-claude") is False


# ---------------------------------------------------------------------------
# Semantics corrections (b) declared_long innocence real texts
# ---------------------------------------------------------------------------

DEATH_INNOCENT_TEXTS = [
    "READ-ONLY audit. A LaunchDaemon on Pro crash-looped for 73.5 hours with every health indicator reading green.",
    "Mechanical task: write one memory file. (2) non fermarti al primo verdetto verde; il log silenzioso 43h non prova nulla.",
    "You are the IMPLEMENTER. Run pytest and iterate until GREEN. WA_INBOUND_STALE_MIN default 180 (3h, business-adjusted) -> P1.",
    "~3512 restarts (~29 h) predate the 0.149.0 upgrade — not the ~10 h the merged text claims.",
    "Fix the failing test and wait until the tests pass, then stop.",
]

def test_declared_long_innocence_real_texts():
    for text in DEATH_INNOCENT_TEXTS:
        is_long, span = fs.declared_long(text)
        assert is_long is False, f"should be innocent: {text[:60]}"
        assert span is None


GUILT_SPANS = [
    ("# HEALER-MANDATE — sessione autonoma di cura (Mini-Pro2, loop 4h) ...", 240),
    ("# HEALER-PRO-MANDATE — sessione autonoma di cura runtime (Pro, loop 6h)", 360),
    ("Questa lane gira H24 sul Mini.", 1440),
    # Refuter kimi-code/k3 named these as MISSED by a <=3-char adjacency, and
    # "loop di 4 ore" is exactly how Zero writes it. Short filler words between
    # the run word and its duration are now allowed.
    ("loop di 4 ore", 240),
    ("Gira in loop di 6 ore e non fermarti.", 360),
    ("Run autonomously for the next 4 hours", 240),
    ("lavora in modo autonomo per le prossime 6 ore", 360),
    ("run continuously for 90 minutes", 90),
]

# The match is DELIBERATELY asymmetric: run-word THEN duration, never the
# reverse. "48h nonstop" / "a 2h continuous integration run" are noun phrases in
# which the duration modifies something else, and they fired on plain narrative.
# Losing "4h loop" is the accepted price -- no real mandate on this fleet writes
# it that way.
REVERSE_ORDER_INNOCENCE = [
    "the CI was green after a 2h continuous integration run",
    "the daemon ran 48h nonstop before crashing",
    "after 3h continuous failures we gave up",
    "Run this as a 90m loop and report.",
]


def test_declared_long_reverse_order_does_not_fire():
    """Duration-then-run-word is narrative, not a declaration (guard-over-match)."""
    for text in REVERSE_ORDER_INNOCENCE:
        is_long, span = fs.declared_long(text)
        assert is_long is False, (text, span)
        assert span is None


def test_declared_long_only_reads_the_declaration_zone():
    """A duration deep in the BODY is subject matter, not a declaration.

    Measured: every false accusation on the live fleet came from body prose --
    "crash-looped for 73.5 hours", "~3512 restarts (~29 h) predate the upgrade",
    "inbound stale 3h during business hours".
    """
    body_only = "READ-ONLY audit. " + ("padding " * 80) + " it crash-looped for 73 hours."
    assert len(body_only) > fs.DECLARATION_ZONE_CHARS
    assert fs.declared_long(body_only) == (False, None)
    # the SAME phrase inside the zone is still refused, because `crash-loop` is
    # a hyphen compound naming a failure mode, not an instruction
    assert fs.declared_long("it crash-looped for 73 hours.") == (False, None)

def test_declared_long_guilt_spans():
    for text, expected in GUILT_SPANS:
        is_long, span = fs.declared_long(text)
        assert is_long is True
        assert span == expected


def test_declared_long_sanity_bounds():
    """Span under 10 minutes or over 7 days is rejected."""
    # 9 minutes
    assert fs.declared_long("loop 9m") == (False, None)
    # 8 minutes (under 10)
    assert fs.declared_long("9m loop") == (False, None)
    # 7 days + 1 minute = 10081 minutes
    assert fs.declared_long("loop 10081m") == (False, None)
    assert fs.declared_long("loop 7d") == (False, None)  # "d" not in unit_min


# ---------------------------------------------------------------------------
# Semantics corrections (c) mapping_available and UNMAPPED
# (covered in test_alive_unmapped_when_mapping_unavailable above)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Semantics corrections (d) inode dedup (symlink)
# ---------------------------------------------------------------------------

def test_inode_dedup_symlink(tmp_path, monkeypatch):
    """Two project dirs where one is a symlink: each session appears exactly once."""
    monkeypatch.setenv("HOME", str(tmp_path))
    NOW = 1690000000.0
    monkeypatch.setattr(time, "time", lambda: NOW)

    # create a real directory
    real_dir = tmp_path / ".claude" / "projects" / "-Users-nuzantara-nuzantara"
    real_dir.mkdir(parents=True)
    # create transcript in the real dir
    lines = [
        {"type": "user", "message": {"content": "hello"}, "timestamp": "2026-08-23T06:00:00Z"},
        {"type": "assistant", "message": {"content": "world"}, "timestamp": "2026-08-23T06:01:00Z"},
    ]
    file_path = real_dir / "sid.jsonl"
    file_path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
    mtime = NOW - 10 * 60
    os.utime(file_path, (mtime, mtime))

    # create a symlink dir that points to the same real dir
    link_dir = tmp_path / ".claude" / "projects" / "-Users-nuzantara-Desktop-nuzantara"
    link_dir.symlink_to(real_dir.resolve())

    # no processes
    monkeypatch.setattr(subprocess, "check_output", _make_mock_check_output("", ""))

    report = fs.probe_local(lookback_min=360, quiet_min=5, stale_min=45)
    sessions = report["sessions"]
    # Should see exactly one session, not two
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "sid"


# ---------------------------------------------------------------------------
# run_host_probe retry logic
# ---------------------------------------------------------------------------

def test_run_host_probe_retry_on_timeout(monkeypatch):
    """One TimeoutExpired, then success => should return success."""
    attempts = [0]
    def mock_run(cmd, **kwargs):
        attempts[0] += 1
        if attempts[0] == 1:
            raise subprocess.TimeoutExpired(cmd="ssh", timeout=45)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok", stderr="")
    monkeypatch.setattr(subprocess, "run", mock_run)
    rc, stdout, stderr = fs.run_host_probe("host", ["--arg"], timeout=45)
    assert rc == 0
    assert stdout == "ok"
    assert attempts[0] == 2


def test_run_host_probe_double_timeout_raises(monkeypatch):
    """Two consecutive TimeoutExpired => should propagate."""
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(subprocess.TimeoutExpired(cmd="ssh", timeout=45)))
    with pytest.raises(subprocess.TimeoutExpired):
        fs.run_host_probe("host", ["--arg"], timeout=45)


# ---------------------------------------------------------------------------
# edge: classification when alive but stale with long declaration
# ---------------------------------------------------------------------------

def test_classify_verdict_alive_not_dead_despite_long(tmp_path, monkeypatch):
    """A session that is alive but stale (past quiet threshold) with long declaration is NOT dead-but-declared-long."""
    # This is covered by test_innocence_alive_same_long_declaration, but we explicitly test the classify_verdict function.
    v = fs.classify_verdict(
        stale_min=50.0,
        alive=fs.ALIVE,
        declared_long=True,
        declared_span_min=240,
        transcript_span_min=6.5,
        quiet_min=5,
        stale_min_threshold=45,
    )
    assert v == fs.STALE  # stale, but NOT accused: alive sessions are never flagged
    assert v != fs.DECLARED_SPAN_UNMET


# ---------------------------------------------------------------------------
# identity slice: the wrapper-tag strip (measured usability defect, 2026-08-23)
# ---------------------------------------------------------------------------

def test_identity_slice_strips_leading_harness_wrapper_tag():
    """`<teammate-message ...>` ate 42 of the 90 characters on every dispatched lane."""
    raw = '<teammate-message teammate_id="team-lead"> Build five canonical contract kinds for Research OS'
    ident = fs.identity_slice(raw)
    assert not ident.startswith("<teammate-message")
    assert ident.startswith("Build five canonical")
    assert len(ident) <= 90


def test_identity_slice_does_not_strip_a_mid_text_angle_bracket():
    """Innocence twin: only a LEADING wrapper tag goes; real content is untouched."""
    raw = "Fix the parser so <div> tags survive the sanitiser"
    assert fs.identity_slice(raw) == raw
    # and a non-wrapper leading tag is left alone
    raw2 = "<important> read this first"
    assert fs.identity_slice(raw2) == raw2
