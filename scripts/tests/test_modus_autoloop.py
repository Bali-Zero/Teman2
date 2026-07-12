"""Tests for Unit 3 — modus_autoloop.py (autonomous nightly consumer).

Covers the 5 required proofs:
  (a) kill-switch-off => no-op exit
  (b) K-cap respected and overflow counted (never silently truncated)
  (c) dry-run never spawns
  (d) defer_task writes a 'deferred' not 'resolved' record
  (e) wrong-machine guard exits gracefully

All queue/gate access is monkeypatched — no real file I/O against the
shared escalations JSONL, and no dependency on modus_green_gate actually
existing on disk (Unit 2 is a sibling task).
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import modus_autoloop  # noqa: E402


def _make_fake_escalations_module(
    pending: list[dict[str, Any]] | None = None,
    current_machine: str = "pro",
) -> types.ModuleType:
    """Build a fake sentinel_lib.escalations module for monkeypatching."""
    mod = types.ModuleType("sentinel_lib.escalations")
    written: list[dict[str, Any]] = []

    def read_all_escalations(include_resolved: bool = False) -> list[dict[str, Any]]:
        return list(pending or [])

    def write_escalation(entry: dict[str, Any]) -> None:
        written.append(entry)

    def _current_machine() -> str:
        return current_machine

    mod.read_all_escalations = read_all_escalations  # type: ignore[attr-defined]
    mod.write_escalation = write_escalation  # type: ignore[attr-defined]
    mod._current_machine = _current_machine  # type: ignore[attr-defined]
    mod._written = written  # type: ignore[attr-defined]  # test introspection hook
    return mod


def _install_fake_sentinel_lib(monkeypatch: pytest.MonkeyPatch, escalations_mod: types.ModuleType) -> None:
    pkg = types.ModuleType("sentinel_lib")
    pkg.escalations = escalations_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentinel_lib", pkg)
    monkeypatch.setitem(sys.modules, "sentinel_lib.escalations", escalations_mod)


def _install_fake_green_gate(monkeypatch: pytest.MonkeyPatch, verdict: bool = True) -> None:
    mod = types.ModuleType("modus_green_gate")

    def is_green(task: dict[str, Any]) -> tuple[bool, str]:
        return (verdict, "test-stub")

    mod.is_green = is_green  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "modus_green_gate", mod)


def _green_task(job: str) -> dict[str, Any]:
    return {"job": job, "status": "pending", "class": "green", "mandate": f"do {job}"}


# ---------------------------------------------------------------------------
# (a) kill-switch-off => no-op exit
# ---------------------------------------------------------------------------


def test_kill_switch_off_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODUS_AUTOLOOP_ENABLED", raising=False)

    calls: list[str] = []
    escalations_mod = _make_fake_escalations_module(pending=[_green_task("j1")])

    def _tracking_read(include_resolved: bool = False) -> list[dict[str, Any]]:
        calls.append("read")
        return []

    escalations_mod.read_all_escalations = _tracking_read  # type: ignore[attr-defined]
    _install_fake_sentinel_lib(monkeypatch, escalations_mod)
    _install_fake_green_gate(monkeypatch, verdict=True)

    rc = modus_autoloop.run()

    assert rc == 0
    assert calls == []  # queue was never even read — true no-op


def test_kill_switch_explicit_false_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODUS_AUTOLOOP_ENABLED", "false")
    escalations_mod = _make_fake_escalations_module(pending=[_green_task("j1")])
    _install_fake_sentinel_lib(monkeypatch, escalations_mod)
    _install_fake_green_gate(monkeypatch, verdict=True)

    assert modus_autoloop.run() == 0
    assert escalations_mod._written == []  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# (b) K-cap respected and overflow counted
# ---------------------------------------------------------------------------


def test_k_cap_respected_and_overflow_logged(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setenv("MODUS_AUTOLOOP_ENABLED", "true")
    monkeypatch.setenv("MODUS_AUTOLOOP_MAX", "2")
    monkeypatch.setenv("MODUS_AUTOLOOP_DRYRUN", "true")
    monkeypatch.delenv("MODUS_AUTOLOOP_MACHINE", raising=False)

    tasks = [_green_task(f"job-{i}") for i in range(5)]
    escalations_mod = _make_fake_escalations_module(pending=tasks)
    _install_fake_sentinel_lib(monkeypatch, escalations_mod)
    _install_fake_green_gate(monkeypatch, verdict=True)

    with caplog.at_level("INFO"):
        rc = modus_autoloop.run()

    assert rc == 0
    # cap=2 -> exactly 2 processed
    launched = [r.message for r in caplog.records if "would launch" in r.message]
    assert len(launched) == 2
    # overflow of 3 must be explicitly logged, never silently dropped
    assert any("skipped_by_cap=3" in r.message for r in caplog.records)
    assert any("3 green task(s) skipped by cap" in r.message for r in caplog.records)


def test_get_cap_defaults_to_5(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODUS_AUTOLOOP_MAX", raising=False)
    assert modus_autoloop.get_cap() == 5


def test_get_cap_invalid_falls_back_to_5(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODUS_AUTOLOOP_MAX", "not-a-number")
    assert modus_autoloop.get_cap() == 5


# ---------------------------------------------------------------------------
# (c) dry-run never spawns
# ---------------------------------------------------------------------------


def test_dry_run_default_never_spawns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODUS_AUTOLOOP_ENABLED", "true")
    monkeypatch.delenv("MODUS_AUTOLOOP_DRYRUN", raising=False)  # defaults true
    monkeypatch.delenv("MODUS_AUTOLOOP_MACHINE", raising=False)

    spawned: list[Any] = []
    monkeypatch.setattr(modus_autoloop, "_spawn_session", lambda task: spawned.append(task) or [])

    escalations_mod = _make_fake_escalations_module(pending=[_green_task("j1")])
    _install_fake_sentinel_lib(monkeypatch, escalations_mod)
    _install_fake_green_gate(monkeypatch, verdict=True)

    assert modus_autoloop.is_dry_run() is True
    rc = modus_autoloop.run()

    assert rc == 0
    assert spawned == []  # _spawn_session must never be called in dry-run


def test_dry_run_false_builds_argv_without_executing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODUS_AUTOLOOP_ENABLED", "true")
    monkeypatch.setenv("MODUS_AUTOLOOP_DRYRUN", "false")
    monkeypatch.delenv("MODUS_AUTOLOOP_MACHINE", raising=False)

    escalations_mod = _make_fake_escalations_module(pending=[_green_task("j1")])
    _install_fake_sentinel_lib(monkeypatch, escalations_mod)
    _install_fake_green_gate(monkeypatch, verdict=True)

    argv = modus_autoloop._spawn_session(_green_task("j1"))
    assert argv[0] == "claude"
    assert "opus" in argv
    # builder must not touch subprocess/os.exec — sanity: it's a plain list
    assert isinstance(argv, list)

    rc = modus_autoloop.run()
    assert rc == 0  # run() logs the built argv but does not exec anything


# ---------------------------------------------------------------------------
# (d) defer_task writes a 'deferred' not 'resolved' record
# ---------------------------------------------------------------------------


def test_defer_task_writes_deferred_status(monkeypatch: pytest.MonkeyPatch) -> None:
    escalations_mod = _make_fake_escalations_module(pending=[])
    _install_fake_sentinel_lib(monkeypatch, escalations_mod)

    modus_autoloop.defer_task({"job": "job-xyz"})

    written = escalations_mod._written  # type: ignore[attr-defined]
    assert len(written) == 1
    record = written[0]
    assert record["job"] == "job-xyz"
    assert record["status"] == "deferred"
    assert record["status"] != "resolved"
    assert record["reason"] == "final_gate_quota_dead"


def test_defer_task_accepts_bare_job_id_string(monkeypatch: pytest.MonkeyPatch) -> None:
    escalations_mod = _make_fake_escalations_module(pending=[])
    _install_fake_sentinel_lib(monkeypatch, escalations_mod)

    modus_autoloop.defer_task("job-abc")

    written = escalations_mod._written  # type: ignore[attr-defined]
    assert written[0]["job"] == "job-abc"
    assert written[0]["status"] == "deferred"


# ---------------------------------------------------------------------------
# (e) wrong-machine guard exits
# ---------------------------------------------------------------------------


def test_wrong_machine_guard_exits_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODUS_AUTOLOOP_ENABLED", "true")
    monkeypatch.setenv("MODUS_AUTOLOOP_MACHINE", "air")  # pin to a machine that is NOT current

    calls: list[str] = []
    escalations_mod = _make_fake_escalations_module(pending=[_green_task("j1")], current_machine="pro")

    def _tracking_read(include_resolved: bool = False) -> list[dict[str, Any]]:
        calls.append("read")
        return []

    escalations_mod.read_all_escalations = _tracking_read  # type: ignore[attr-defined]
    _install_fake_sentinel_lib(monkeypatch, escalations_mod)
    _install_fake_green_gate(monkeypatch, verdict=True)

    rc = modus_autoloop.run()

    assert rc == 0
    assert calls == []  # never reached the queue read — exited at the machine guard


def test_matching_machine_guard_proceeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODUS_AUTOLOOP_ENABLED", "true")
    monkeypatch.setenv("MODUS_AUTOLOOP_MACHINE", "pro")  # matches current

    escalations_mod = _make_fake_escalations_module(pending=[_green_task("j1")], current_machine="pro")
    _install_fake_sentinel_lib(monkeypatch, escalations_mod)
    _install_fake_green_gate(monkeypatch, verdict=True)

    assert modus_autoloop._machine_guard_ok() is True


# ---------------------------------------------------------------------------
# Extra: is_green filtering + not-green module missing => fail-closed
# ---------------------------------------------------------------------------


def test_not_green_tasks_are_filtered_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODUS_AUTOLOOP_ENABLED", "true")
    monkeypatch.delenv("MODUS_AUTOLOOP_MACHINE", raising=False)

    escalations_mod = _make_fake_escalations_module(pending=[_green_task("j1")])
    _install_fake_sentinel_lib(monkeypatch, escalations_mod)
    _install_fake_green_gate(monkeypatch, verdict=False)  # NOT green

    tasks = modus_autoloop._read_pending_green_tasks()
    assert tasks == []


def test_missing_green_gate_module_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "modus_green_gate", raising=False)
    # ensure no real modus_green_gate.py is importable from sys.path either
    monkeypatch.setattr(sys, "path", [p for p in sys.path if "modus_green_gate" not in p])

    result = modus_autoloop._is_green({"job": "j1"})
    assert result is False


def test_non_pending_or_non_green_class_excluded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODUS_AUTOLOOP_ENABLED", "true")
    monkeypatch.delenv("MODUS_AUTOLOOP_MACHINE", raising=False)

    tasks = [
        {"job": "resolved-one", "status": "resolved", "class": "green"},
        {"job": "proposal-one", "status": "pending", "class": "proposal"},
        {"job": "good-one", "status": "pending", "class": "green"},
    ]
    escalations_mod = _make_fake_escalations_module(pending=tasks)
    _install_fake_sentinel_lib(monkeypatch, escalations_mod)
    _install_fake_green_gate(monkeypatch, verdict=True)

    result = modus_autoloop._read_pending_green_tasks()
    assert [t["job"] for t in result] == ["good-one"]


def test_read_error_fails_open_to_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    escalations_mod = _make_fake_escalations_module(pending=[])

    def _broken_read(include_resolved: bool = False) -> list[dict[str, Any]]:
        raise OSError("disk full")

    escalations_mod.read_all_escalations = _broken_read  # type: ignore[attr-defined]
    _install_fake_sentinel_lib(monkeypatch, escalations_mod)
    _install_fake_green_gate(monkeypatch, verdict=True)

    result = modus_autoloop._read_pending_green_tasks()
    assert result == []


# ---------------------------------------------------------------------------
# collapse-by-job: an append-only pending+resolved pair must NOT re-process
# (scar family #2 — blind heal-loop; the smoke-test that exposed it live 2026-07-12)
# ---------------------------------------------------------------------------

def test_collapse_by_job_excludes_resolved_job(monkeypatch: pytest.MonkeyPatch) -> None:
    # newest-first: the resolved record is newer than the pending one for job "done".
    records = [
        {"job": "done", "status": "resolved", "ts": 200.0},
        {"job": "done", "status": "pending", "class": "green", "ts": 100.0, "mandate": "x"},
        {"job": "live", "status": "pending", "class": "green", "ts": 150.0, "mandate": "y"},
    ]
    escalations_mod = _make_fake_escalations_module(pending=records)
    _install_fake_sentinel_lib(monkeypatch, escalations_mod)
    _install_fake_green_gate(monkeypatch, verdict=True)

    result = modus_autoloop._read_pending_green_tasks()
    jobs = [t["job"] for t in result]
    assert jobs == ["live"], f"resolved job leaked back as pending: {jobs}"


def test_collapse_by_job_keeps_deferred_out(monkeypatch: pytest.MonkeyPatch) -> None:
    records = [
        {"job": "waiting", "status": "deferred", "ts": 300.0},
        {"job": "waiting", "status": "pending", "class": "green", "ts": 100.0, "mandate": "z"},
    ]
    escalations_mod = _make_fake_escalations_module(pending=records)
    _install_fake_sentinel_lib(monkeypatch, escalations_mod)
    _install_fake_green_gate(monkeypatch, verdict=True)

    assert modus_autoloop._read_pending_green_tasks() == []


def test_collapse_by_job_unit() -> None:
    recs = [
        {"job": "a", "status": "resolved", "ts": 2},
        {"job": "a", "status": "pending", "ts": 1},
        {"job": "b", "status": "pending", "ts": 3},
        {"status": "pending", "ts": 4},  # no job — kept as singleton
    ]
    out = modus_autoloop._collapse_by_job(recs)
    # 'a' collapses to its newest (resolved); 'b' pending; the job-less row kept.
    a = [r for r in out if r.get("job") == "a"]
    assert len(a) == 1 and a[0]["status"] == "resolved"
    assert any(r.get("job") == "b" for r in out)
    assert any("job" not in r for r in out)
