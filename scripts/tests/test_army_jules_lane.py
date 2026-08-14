"""Guilt+innocence corpus for scripts/army/jules_lane.py (Armata H24 lane 2,
2026-08-14). Never hits the network or the real Jules API — `run_jules_dispatch`
and `telegram` are monkeypatched to recorders/fakes, and `credential_present`'s
own Keychain-probe logic is exercised against a monkeypatched `subprocess.run`
so the detection code itself is tested, not bypassed.

W107 discipline: every case proves the behaviour FIRES on the condition it
exists to catch (report written / not written, escalation appended / not,
telegram called with the right dedup key), not merely that the caller
survives.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

SPEC_PATH = Path(__file__).resolve().parent.parent / "army" / "jules_lane.py"
spec = importlib.util.spec_from_file_location("jules_lane", SPEC_PATH)
jl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jl)  # type: ignore[union-attr]


# --------------------------------------------------------------------- utils
def make_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> "jl.Paths":
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    monkeypatch.setenv("ARMY_JULES_REPO", str(repo))
    monkeypatch.setenv("ARMY_JULES_QUEUE_DIR", str(tmp_path / "queue"))
    monkeypatch.setenv("ARMY_JULES_INBOX_DIR", str(tmp_path / "inbox"))
    monkeypatch.setenv("ARMY_JULES_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("ARMY_JULES_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("ARMY_JULES_SIDECAR_DIR", str(tmp_path / "sidecar"))
    monkeypatch.setenv("ARMY_JULES_DISPATCH_SCRIPT", str(repo / "scripts" / "jules_dispatch.py"))
    paths = jl.Paths()
    paths.ensure()
    return paths


def write_task(paths: "jl.Paths", name: str, title: str, body: str = "prompt body") -> Path:
    paths.queue_dir.mkdir(parents=True, exist_ok=True)
    f = paths.queue_dir / name
    f.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    return f


def record_telegram(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(jl, "telegram", lambda paths, tier, key, text: calls.append((tier, key, text)))
    return calls


def heartbeat_status(paths: "jl.Paths") -> str | None:
    p = paths.sidecar_dir / f"{jl.ORGAN_ID}.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text())["status"]


# -------------------------------------------------------------- credential
def test_credential_present_true_via_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JULES_API_KEY", "test-key")
    assert jl.credential_present() is True


def test_credential_present_true_when_keychain_has_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JULES_API_KEY", raising=False)
    monkeypatch.setattr(jl.subprocess, "run",
                         lambda *a, **kw: subprocess.CompletedProcess(a[0], 0))
    assert jl.credential_present() is True


def test_credential_present_false_when_keychain_lacks_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JULES_API_KEY", raising=False)
    monkeypatch.setattr(jl.subprocess, "run",
                         lambda *a, **kw: subprocess.CompletedProcess(a[0], 44))
    assert jl.credential_present() is False


def test_credential_present_never_reads_the_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guilt-adjacent: the probe command must never include -w (which would
    print the secret to stdout)."""
    monkeypatch.delenv("JULES_API_KEY", raising=False)
    seen_cmds = []

    def fake_run(cmd, **kw):
        seen_cmds.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(jl.subprocess, "run", fake_run)
    jl.credential_present()
    assert seen_cmds, "credential_present did not call subprocess.run"
    assert "-w" not in seen_cmds[0]


# -------------------------------------------------------------- node guard
def test_node_ok_true_when_override_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARMY_JULES_NODE_OVERRIDE", "nuzantara")
    ok, node = jl.node_ok()
    assert ok is True
    assert node == "nuzantara"


def test_node_ok_false_when_override_mismatches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARMY_JULES_NODE_OVERRIDE", "some-other-mac")
    ok, node = jl.node_ok()
    assert ok is False
    assert node == "some-other-mac"


# -------------------------------------------------------------- dispatch
def test_dispatch_success_marks_task_done_and_records_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    task = write_task(paths, "task-one.md", "Fix the thing")

    def fake_run(paths_arg, args, timeout_s=120):
        assert args[0] == "new"
        return 0, json.dumps({"name": "sessions/abc123", "state": "PENDING"}), ""

    monkeypatch.setattr(jl, "run_jules_dispatch", fake_run)
    calls = record_telegram(monkeypatch)

    status = jl.cmd_dispatch(paths)

    assert status == "ok"
    sessions = jl.load_jsonl(paths.state_dir / "sessions.jsonl")
    assert len(sessions) == 1
    assert sessions[0]["session"] == "sessions/abc123"
    assert sessions[0]["status"] == "open"
    assert sessions[0]["task_file"] == "task-one.md"
    dispatched = (paths.state_dir / "dispatched-list.txt").read_text()
    assert f"task-one.md:{jl.sha256_of(task)}" in dispatched
    assert not calls, "no telegram alert expected on a clean successful dispatch"


def test_dispatch_dedup_skips_already_dispatched_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    write_task(paths, "task-one.md", "Fix the thing")
    calls_made = []

    def fake_run(paths_arg, args, timeout_s=120):
        calls_made.append(args)
        return 0, json.dumps({"name": f"sessions/run{len(calls_made)}"}), ""

    monkeypatch.setattr(jl, "run_jules_dispatch", fake_run)
    record_telegram(monkeypatch)

    jl.cmd_dispatch(paths)
    assert len(calls_made) == 1
    jl.cmd_dispatch(paths)
    assert len(calls_made) == 1, "second tick redispatched an already-done task"


def test_dispatch_daily_cap_stops_new_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    monkeypatch.setenv("ARMY_JULES_DAILY_CAP", "2")
    for i in range(4):
        write_task(paths, f"task-{i}.md", f"Task {i}")

    call_count = [0]

    def fake_run(paths_arg, args, timeout_s=120):
        call_count[0] += 1
        return 0, json.dumps({"name": f"sessions/s{call_count[0]}"}), ""

    monkeypatch.setattr(jl, "run_jules_dispatch", fake_run)
    record_telegram(monkeypatch)

    jl.cmd_dispatch(paths)
    assert call_count[0] == 2, "daily cap of 2 was not respected"


def test_dispatch_quota_marker_stops_loop_and_sets_backoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    write_task(paths, "task-one.md", "Fix the thing")
    write_task(paths, "task-two.md", "Fix another thing")

    def fake_run(paths_arg, args, timeout_s=120):
        return 1, "", "jules_dispatch: HTTP 429 on POST sessions\nRESOURCE_EXHAUSTED"

    monkeypatch.setattr(jl, "run_jules_dispatch", fake_run)
    calls = record_telegram(monkeypatch)

    status = jl.cmd_dispatch(paths)

    assert status == "degraded"
    assert (paths.state_dir / "backoff-until.txt").is_file()
    assert any(k == "army-jules:quota" for _, k, _ in calls)
    dispatched_list = paths.state_dir / "dispatched-list.txt"
    assert not dispatched_list.is_file() or dispatched_list.read_text().strip() == ""


def test_dispatch_real_failure_alerts_p0_and_leaves_task_undone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    write_task(paths, "task-one.md", "Fix the thing")

    def fake_run(paths_arg, args, timeout_s=120):
        return 1, "", "jules_dispatch: HTTP 500 on POST sessions"

    monkeypatch.setattr(jl, "run_jules_dispatch", fake_run)
    calls = record_telegram(monkeypatch)

    status = jl.cmd_dispatch(paths)

    assert status == "error"
    assert any(tier == "p0" and "dispatch-failed" in key for tier, key, _ in calls)
    dispatched_list = paths.state_dir / "dispatched-list.txt"
    assert not dispatched_list.is_file() or dispatched_list.read_text().strip() == ""


# -------------------------------------------------------------- harvest
def _seed_session(paths: "jl.Paths", session: str, task_file: str = "t.md",
                   title: str = "Some task", status: str = "open") -> None:
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    jl.save_jsonl(paths.state_dir / "sessions.jsonl", [
        {"ts": 1.0, "session": session, "task_file": task_file, "title": title, "status": status}
    ])


def test_harvest_completed_session_writes_inbox_and_escalation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    _seed_session(paths, "sessions/done1", title="Fix the thing")

    def fake_run(paths_arg, args, timeout_s=120):
        if args[0] == "status":
            return 0, json.dumps({"name": "sessions/done1", "state": "SESSION_STATE_COMPLETED",
                                   "title": "Fix the thing"}), ""
        if args[0] == "activities":
            return 0, json.dumps({"activities": [{"kind": "patch"}]}), ""
        raise AssertionError(f"unexpected args {args}")

    monkeypatch.setattr(jl, "run_jules_dispatch", fake_run)
    calls = record_telegram(monkeypatch)
    escalations = []
    monkeypatch.setattr(jl, "write_jules_escalation",
                         lambda paths_, **kw: (escalations.append(kw), True)[1])

    status = jl.cmd_harvest(paths)

    assert status == "ok"
    inbox = paths.inbox_dir / "done1"
    assert (inbox / "status.json").is_file()
    assert (inbox / "activities.json").is_file()
    assert len(escalations) == 1
    assert escalations[0]["title"] == "Fix the thing"
    sessions = jl.load_jsonl(paths.state_dir / "sessions.jsonl")
    assert sessions[0]["status"] == "closed"
    assert sessions[0]["closed_reason"] == "completed"
    assert any(k.startswith("army-jules:completed:") for _, k, _ in calls)


def test_harvest_failed_session_closes_without_escalation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    _seed_session(paths, "sessions/dead1", title="Broken task")

    def fake_run(paths_arg, args, timeout_s=120):
        assert args[0] == "status"
        return 0, json.dumps({"name": "sessions/dead1", "state": "SESSION_STATE_FAILED",
                               "title": "Broken task"}), ""

    monkeypatch.setattr(jl, "run_jules_dispatch", fake_run)
    calls = record_telegram(monkeypatch)
    escalations = []
    monkeypatch.setattr(jl, "write_jules_escalation",
                         lambda paths_, **kw: (escalations.append(kw), True)[1])

    jl.cmd_harvest(paths)

    assert not escalations, "a FAILED session must never produce an escalation"
    sessions = jl.load_jsonl(paths.state_dir / "sessions.jsonl")
    assert sessions[0]["status"] == "closed"
    assert sessions[0]["closed_reason"] == "failed"
    assert any(k.startswith("army-jules:failed:") for _, k, _ in calls)


def test_harvest_still_open_session_stays_open_no_escalation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    _seed_session(paths, "sessions/wip1", title="Still cooking")

    def fake_run(paths_arg, args, timeout_s=120):
        assert args[0] == "status"
        return 0, json.dumps({"name": "sessions/wip1", "state": "SESSION_STATE_IN_PROGRESS"}), ""

    monkeypatch.setattr(jl, "run_jules_dispatch", fake_run)
    record_telegram(monkeypatch)
    escalations = []
    monkeypatch.setattr(jl, "write_jules_escalation",
                         lambda paths_, **kw: (escalations.append(kw), True)[1])

    jl.cmd_harvest(paths)

    assert not escalations
    sessions = jl.load_jsonl(paths.state_dir / "sessions.jsonl")
    assert sessions[0]["status"] == "open", "an in-progress session must not be closed"


def test_harvest_closed_session_is_never_repolled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    _seed_session(paths, "sessions/already-done", title="X", status="closed")

    called = []

    def fake_run(paths_arg, args, timeout_s=120):
        called.append(args)
        raise AssertionError("a closed session must never be polled again")

    monkeypatch.setattr(jl, "run_jules_dispatch", fake_run)
    record_telegram(monkeypatch)

    jl.cmd_harvest(paths)
    assert not called


# -------------------------------------------------------------- escalation shape
def test_write_jules_escalation_field_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    recorded: list[dict] = []
    fake_mod = types.ModuleType("sentinel_lib.escalations")
    fake_mod.write_escalation = lambda entry: recorded.append(entry)  # type: ignore[attr-defined]
    fake_pkg = types.ModuleType("sentinel_lib")
    fake_pkg.escalations = fake_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentinel_lib", fake_pkg)
    monkeypatch.setitem(sys.modules, "sentinel_lib.escalations", fake_mod)

    inbox_path = paths.inbox_dir / "abc123"
    ok = jl.write_jules_escalation(
        paths, session="sessions/abc123", title="Fix the thing",
        task_file="task-one.md", inbox_path=inbox_path,
    )

    assert ok is True
    assert len(recorded) == 1
    entry = recorded[0]
    assert entry["priority"] == "NORMAL"
    assert entry["test_cmd"] is None
    assert entry["job"] == "jules-patch-abc123"
    assert "Jules patch ready for independent verification: Fix the thing" in entry["description"]
    assert str(inbox_path) in entry["description"]
    assert entry["session"] == "sessions/abc123"
    assert entry["task_file"] == "task-one.md"


def test_write_jules_escalation_missing_module_is_non_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """This test file runs from THIS repo's real scripts/ dir, which has a
    REAL sentinel_lib.escalations — pytest's own package-rootdir insertion
    puts scripts/ on sys.path regardless of ARMY_JULES_REPO, so simply
    deleting the two module-cache entries is not enough: the next `import`
    would just re-resolve the real module and silently write a REAL row to
    this repo's shared/escalations_pro.jsonl (caught live once while writing
    this test — the exact "test writes prod state" class, cicatrix-superscar
    orphan W96). Setting sys.modules[name] = None is the documented way to
    force ImportError regardless of what is really importable.
    """
    paths = make_paths(tmp_path, monkeypatch)
    monkeypatch.setitem(sys.modules, "sentinel_lib", None)
    monkeypatch.setitem(sys.modules, "sentinel_lib.escalations", None)
    ok = jl.write_jules_escalation(
        paths, session="sessions/x", title="T", task_file="t.md",
        inbox_path=paths.inbox_dir / "x",
    )
    assert ok is False


# -------------------------------------------------------------- main() gates
def test_main_kill_switch_off_writes_disabled_heartbeat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    monkeypatch.setenv("ARMY_JULES_ENABLED", "false")
    monkeypatch.setattr(jl, "credential_present", lambda: True)
    record_telegram(monkeypatch)

    rc = jl.main(["--dispatch"])

    assert rc == 0
    assert heartbeat_status(paths) == "disabled"


def test_main_blocked_when_credential_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    monkeypatch.setenv("ARMY_JULES_NODE_OVERRIDE", "nuzantara")
    monkeypatch.setattr(jl, "credential_present", lambda: False)
    calls = record_telegram(monkeypatch)

    rc = jl.main(["--dispatch"])

    assert rc == 0
    assert heartbeat_status(paths) == "disabled"
    assert any(k == "army-jules:blocked-no-credential" for _, k, _ in calls)


def test_main_wrong_node_never_checks_credential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    monkeypatch.setenv("ARMY_JULES_NODE_OVERRIDE", "some-other-mac")

    def boom():
        raise AssertionError("credential_present must not run past the node guard")

    monkeypatch.setattr(jl, "credential_present", boom)
    record_telegram(monkeypatch)

    rc = jl.main(["--dispatch"])

    assert rc == 0
    assert heartbeat_status(paths) == "disabled"
