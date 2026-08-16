"""Guilt+innocence corpus for scripts/army/jules_lane.py (Armata H24 lane 2,
2026-08-14, amended same day after a cross-family Kimi K3 refutation of the
design closed 12 numbered defects — see the module docstring and
research/operations/2026-08-14-armata-h24-standing-lanes.md). Never hits the
network or the real Jules API — `run_jules_dispatch` and `telegram` are
monkeypatched to recorders/fakes, and `credential_present`'s own
Keychain-probe logic is exercised against a monkeypatched `subprocess.run`
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
import time
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


def _seed_session(paths: "jl.Paths", session: str, task_file: str = "t.md",
                   title: str = "Some task", status: str = "open",
                   ts: float | None = None) -> None:
    """Default ts is "now" — fresh, well within the 72h TTL — so ordinary
    harvest tests are not accidentally exercising the TTL path. Tests that
    need an aged session pass ts explicitly."""
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    jl.save_jsonl(paths.state_dir / "sessions.jsonl", [
        {"ts": ts if ts is not None else time.time(), "session": session,
         "task_file": task_file, "title": title, "status": status}
    ])


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
    monkeypatch.setattr(jl, "_origin_main_head", lambda paths_: "deadbeef")

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
    assert sessions[0]["base_commit"] == "deadbeef", "item 10: base commit not recorded"
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


# --------------------------------------------------- dispatch: backpressure (item 9)
def test_dispatch_backpressure_skips_when_inbox_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    write_task(paths, "task-one.md", "Fix the thing")
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    jl.save_jsonl(paths.state_dir / "sessions.jsonl", [
        {"ts": time.time(), "session": f"sessions/done{i}", "task_file": f"t{i}.md",
         "title": f"Done {i}", "status": "closed", "closed_reason": "completed", "outcome": None}
        for i in range(6)
    ])
    called = []

    def fake_run(paths_arg, args, timeout_s=120):
        called.append(args)
        raise AssertionError("dispatch must not run while backpressured")

    monkeypatch.setattr(jl, "run_jules_dispatch", fake_run)
    record_telegram(monkeypatch)

    status = jl.cmd_dispatch(paths)

    assert status == "ok"
    assert not called, "dispatch called run_jules_dispatch despite 6 pending-verification patches"


def test_dispatch_proceeds_when_inbox_below_backpressure_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    write_task(paths, "task-one.md", "Fix the thing")
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    jl.save_jsonl(paths.state_dir / "sessions.jsonl", [
        {"ts": time.time(), "session": f"sessions/done{i}", "task_file": f"t{i}.md",
         "title": f"Done {i}", "status": "closed", "closed_reason": "completed", "outcome": None}
        for i in range(5)
    ])
    monkeypatch.setattr(jl, "_origin_main_head", lambda paths_: "")

    def fake_run(paths_arg, args, timeout_s=120):
        return 0, json.dumps({"name": "sessions/new1"}), ""

    monkeypatch.setattr(jl, "run_jules_dispatch", fake_run)
    record_telegram(monkeypatch)

    status = jl.cmd_dispatch(paths)
    assert status == "ok"
    sessions = jl.load_jsonl(paths.state_dir / "sessions.jsonl")
    assert any(s.get("session") == "sessions/new1" for s in sessions), \
        "innocence: 5 pending (below the default limit of 6) must not block dispatch"


def test_count_pending_verification_ignores_verified_and_non_completed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    jl.save_jsonl(paths.state_dir / "sessions.jsonl", [
        {"session": "s1", "status": "closed", "closed_reason": "completed", "outcome": None},
        {"session": "s2", "status": "closed", "closed_reason": "completed", "outcome": "applied"},
        {"session": "s3", "status": "closed", "closed_reason": "failed"},
        {"session": "s4", "status": "open"},
    ])
    assert jl.count_pending_verification(paths) == 1


# -------------------------------------------------------------- harvest
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
    monkeypatch.setattr(jl, "escalation_already_exists", lambda paths_, job_key: False)
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
    assert sessions[0]["outcome"] is None, "item 12: outcome starts unset, a verification session sets it later"
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
    _seed_session(paths, "sessions/wip1", title="Still cooking")  # fresh ts, well within TTL

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
    assert sessions[0]["status"] == "open", "an in-progress session well within TTL must not be closed"


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


# --------------------------------------------------- harvest: TTL (item 7)
def test_harvest_pending_past_ttl_marked_stale_with_one_escalation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    old_ts = time.time() - (73 * 3600)  # 73h ago, past the 72h default TTL
    _seed_session(paths, "sessions/stuck1", title="Stuck task", ts=old_ts)

    def fake_run(paths_arg, args, timeout_s=120):
        assert args[0] == "status"
        return 0, json.dumps({"name": "sessions/stuck1", "state": "SESSION_STATE_IN_PROGRESS"}), ""

    monkeypatch.setattr(jl, "run_jules_dispatch", fake_run)
    monkeypatch.setattr(jl, "escalation_already_exists", lambda paths_, job_key: False)
    calls = record_telegram(monkeypatch)
    stale_escalations = []
    monkeypatch.setattr(jl, "write_jules_stale_escalation",
                         lambda paths_, **kw: (stale_escalations.append(kw), True)[1])

    jl.cmd_harvest(paths)

    sessions = jl.load_jsonl(paths.state_dir / "sessions.jsonl")
    assert sessions[0]["status"] == "closed"
    assert sessions[0]["closed_reason"] == "stale"
    assert len(stale_escalations) == 1
    assert any(k.startswith("army-jules:stale:") for _, k, _ in calls)


def test_harvest_within_ttl_not_marked_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    recent_ts = time.time() - (71 * 3600)  # 71h ago, still under the 72h TTL
    _seed_session(paths, "sessions/almost1", title="Almost stuck", ts=recent_ts)

    def fake_run(paths_arg, args, timeout_s=120):
        return 0, json.dumps({"name": "sessions/almost1", "state": "SESSION_STATE_IN_PROGRESS"}), ""

    monkeypatch.setattr(jl, "run_jules_dispatch", fake_run)
    record_telegram(monkeypatch)
    stale_escalations = []
    monkeypatch.setattr(jl, "write_jules_stale_escalation",
                         lambda paths_, **kw: (stale_escalations.append(kw), True)[1])

    jl.cmd_harvest(paths)

    assert not stale_escalations, "innocence: 71h < 72h TTL must not mark stale"
    sessions = jl.load_jsonl(paths.state_dir / "sessions.jsonl")
    assert sessions[0]["status"] == "open"


def test_harvest_stale_session_is_never_repolled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    jl.save_jsonl(paths.state_dir / "sessions.jsonl", [
        {"ts": time.time() - 999999, "session": "sessions/gone", "task_file": "t.md",
         "title": "Gone", "status": "closed", "closed_reason": "stale"}
    ])
    called = []

    def fake_run(paths_arg, args, timeout_s=120):
        called.append(args)
        raise AssertionError("a stale-closed session must never be polled again")

    monkeypatch.setattr(jl, "run_jules_dispatch", fake_run)
    record_telegram(monkeypatch)

    jl.cmd_harvest(paths)
    assert not called


# --------------------------------------------------- escalation dedup (item 8)
def test_escalation_already_exists_true_on_matching_job_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    shared = paths.repo / "shared"
    shared.mkdir(parents=True)
    (shared / "escalations_pro.jsonl").write_text(
        json.dumps({"job": "jules-patch-abc123", "type": "jules_dispatch_completed"}) + "\n",
        encoding="utf-8",
    )
    assert jl.escalation_already_exists(paths, "jules-patch-abc123") is True


def test_escalation_already_exists_false_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    shared = paths.repo / "shared"
    shared.mkdir(parents=True)
    (shared / "escalations_pro.jsonl").write_text(
        json.dumps({"job": "some-other-job"}) + "\n", encoding="utf-8",
    )
    assert jl.escalation_already_exists(paths, "jules-patch-abc123") is False


def test_escalation_already_exists_false_when_file_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    assert jl.escalation_already_exists(paths, "jules-patch-abc123") is False


def test_harvest_skips_write_when_escalation_already_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The crash-consistency gap this guards: an escalation was already
    written (found by the grep) but the session-state save that would have
    prevented a repeat did not land — the next harvest tick must not write
    a SECOND escalation row for the same session."""
    paths = make_paths(tmp_path, monkeypatch)
    _seed_session(paths, "sessions/done1", title="Fix the thing")

    def fake_run(paths_arg, args, timeout_s=120):
        if args[0] == "status":
            return 0, json.dumps({"name": "sessions/done1", "state": "SESSION_STATE_COMPLETED",
                                   "title": "Fix the thing"}), ""
        return 0, json.dumps({"activities": []}), ""

    monkeypatch.setattr(jl, "run_jules_dispatch", fake_run)
    monkeypatch.setattr(jl, "escalation_already_exists", lambda paths_, job_key: True)
    record_telegram(monkeypatch)
    write_calls = []
    monkeypatch.setattr(jl, "write_jules_escalation",
                         lambda paths_, **kw: (write_calls.append(kw), True)[1])

    jl.cmd_harvest(paths)

    assert not write_calls, "escalation_already_exists=True must skip the write, not duplicate it"
    sessions = jl.load_jsonl(paths.state_dir / "sessions.jsonl")
    assert sessions[0]["status"] == "closed", "the session still closes even when the escalation was pre-existing"


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


def test_write_jules_stale_escalation_field_shape(
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

    ok = jl.write_jules_stale_escalation(
        paths, session="sessions/stuck1", title="Stuck task", task_file="task-one.md",
        age_hours=73.4,
    )

    assert ok is True
    assert len(recorded) == 1
    entry = recorded[0]
    assert entry["job"] == "jules-stale-stuck1"
    assert entry["type"] == "jules_session_stale"
    assert entry["priority"] == "NORMAL"
    assert "73h" in entry["description"]
    assert "investigate or cancel" in entry["description"]


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


# -------------------------------------------------------------- weekly rollup (item 12)
def test_count_produced_and_consumed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    jl.save_jsonl(paths.state_dir / "sessions.jsonl", [
        {"session": "s1", "status": "closed", "closed_reason": "completed", "outcome": "applied"},
        {"session": "s2", "status": "closed", "closed_reason": "completed", "outcome": "rejected"},
        {"session": "s3", "status": "closed", "closed_reason": "completed", "outcome": None},
        {"session": "s4", "status": "closed", "closed_reason": "failed"},
        {"session": "s5", "status": "open"},
    ])
    produced, consumed = jl.count_produced_and_consumed(paths)
    assert produced == 3
    assert consumed == 2


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


def test_main_kill_switch_off_past_digest_hour_still_sends_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Item 11: a forgotten kill switch must stay visible — the digest
    check must not be skipped by the kill-switch early return."""
    paths = make_paths(tmp_path, monkeypatch)
    monkeypatch.setenv("ARMY_JULES_NODE_OVERRIDE", "nuzantara")
    monkeypatch.setenv("ARMY_JULES_ENABLED", "false")
    monkeypatch.setenv("ARMY_JULES_DIGEST_HOUR", "0")
    calls = record_telegram(monkeypatch)

    rc = jl.main(["--dispatch"])

    assert rc == 0
    assert any("ARMY_JULES_ENABLED=false" in text for _, _, text in calls), \
        f"expected a digest line naming the kill switch, got: {calls}"


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
    calls = record_telegram(monkeypatch)

    rc = jl.main(["--dispatch"])

    assert rc == 0
    assert heartbeat_status(paths) == "disabled"
    assert not calls, "wrong node must not send a digest either — not my machine, not my report"


# ------------------------------------------------- main(): blocked streak (item 10)
def test_main_blocked_streak_fires_distinct_alarm_on_second_consecutive_tick(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    monkeypatch.setenv("ARMY_JULES_NODE_OVERRIDE", "nuzantara")
    monkeypatch.setattr(jl, "credential_present", lambda: False)
    calls = record_telegram(monkeypatch)

    jl.main(["--dispatch"])
    assert not any(k == "army-jules:blocked-streak" for _, k, _ in calls), \
        "innocence: a single blocked tick must not yet fire the streak alarm"

    calls.clear()
    jl.main(["--harvest"])
    assert any(k == "army-jules:blocked-streak" for _, k, _ in calls), \
        "guilt: a SECOND consecutive blocked tick must fire the distinct streak alarm"


def test_main_credential_present_resets_blocked_streak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    monkeypatch.setenv("ARMY_JULES_NODE_OVERRIDE", "nuzantara")
    monkeypatch.setattr(jl, "credential_present", lambda: False)
    record_telegram(monkeypatch)
    jl.main(["--dispatch"])  # blocked tick 1

    monkeypatch.setattr(jl, "credential_present", lambda: True)
    monkeypatch.setattr(jl, "cmd_dispatch", lambda paths_: "ok")
    jl.main(["--dispatch"])  # credential now present — streak must reset

    assert jl._blocked_streak(paths) == 0


def test_main_previous_run_alive_skips_with_overlap_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = make_paths(tmp_path, monkeypatch)
    monkeypatch.setenv("ARMY_JULES_NODE_OVERRIDE", "nuzantara")
    monkeypatch.setattr(jl, "credential_present", lambda: True)
    pidfile = paths.state_dir / "dispatch.pid"
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(__import__("os").getpid()))  # this test process: guaranteed alive

    def boom(paths_):
        raise AssertionError("cmd_dispatch must not run while a live lock is held")

    monkeypatch.setattr(jl, "cmd_dispatch", boom)
    record_telegram(monkeypatch)

    rc = jl.main(["--dispatch"])

    assert rc == 0
    assert heartbeat_status(paths) == "ok"
