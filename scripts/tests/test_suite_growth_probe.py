"""Tests for scripts/suite_growth_probe.py — Merge-OS v3 step 3 slice 1 (measurement-only).

Module is imported via importlib.util.spec_from_file_location (not a package import)
because scripts/ is a flat bag of standalone tools — same convention as
scripts/tests/test_queue_baseline_probe.py, whose header explains it.

NO network anywhere in this file. Every `gh` invocation is intercepted at the real
subprocess boundary the module crosses (`monkeypatch.setattr(sgp.subprocess, "run",
fake_run)`, W114: the fake belongs at the boundary the real code crosses). The
`tg_notify.py` dispatch is intercepted the same way, at its own separate boundary
(`sgp._run_tg_notify`), so a test cannot accidentally make one fake answer for both.

Scenarios required by the mandate (team-lead message, step 3 slice 1):
  1. guilt: `gh api` denied for the run-listing call -> errors[] non-empty, main()
     returns 1, the record is still written to disk (never a silent empty success).
  2. guilt: current-window p95 crosses the timeout threshold alone -> P1, alert
     dispatch path invoked (tg_notify called with --tier digest).
  3. guilt: week-over-week growth crosses the threshold alone -> P1, alert
     dispatch path invoked.
  4. guilt: both conditions on the same job -> P0, --tier p0, exactly one alert
     for that job (not two).
  5. innocence: both windows comfortably under both thresholds -> severity None,
     alerts_sent == [], tg_notify never invoked.
  6. record is written even on total API failure (schema-shape parity with the
     healthy-empty-day case).
Plus pure-function unit tests for the sub-mechanisms above lean on.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "suite_growth_probe.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("suite_growth_probe", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sgp = _load_module()

NOW = datetime(2026, 8, 14, 0, 0, 0, tzinfo=timezone.utc)
CURRENT_TS = "2026-08-10T00:00:00Z"  # 4 days before NOW -> current window
PREVIOUS_TS = "2026-08-03T00:00:00Z"  # 11 days before NOW -> previous window


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def test_percentile_empty_is_none():
    assert sgp.percentile([], 50) is None


def test_percentile_single_value():
    assert sgp.percentile([42.0], 95) == 42.0


def test_percentile_p50_p95_known_sample():
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert sgp.percentile(values, 50) == 30.0
    assert sgp.percentile(values, 95) == pytest.approx(48.0)


def test_job_window_current_previous_and_out_of_range():
    current = datetime.fromisoformat(CURRENT_TS.replace("Z", "+00:00"))
    previous = datetime.fromisoformat(PREVIOUS_TS.replace("Z", "+00:00"))
    ancient = datetime(2026, 7, 1, tzinfo=timezone.utc)
    assert sgp.job_window(current, NOW, 7) == "current"
    assert sgp.job_window(previous, NOW, 7) == "previous"
    assert sgp.job_window(ancient, NOW, 7) is None


def test_qualifies_as_gate_run():
    assert sgp.qualifies_as_gate_run({"event": "merge_group"}) is True
    assert sgp.qualifies_as_gate_run({"event": "push", "head_branch": "main"}) is True
    assert sgp.qualifies_as_gate_run({"event": "push", "head_branch": "develop"}) is False
    assert sgp.qualifies_as_gate_run({"event": "pull_request", "head_branch": "main"}) is False
    assert sgp.qualifies_as_gate_run({"event": "schedule"}) is False


def test_job_wall_minutes_happy_path():
    job = {
        "status": "completed",
        "started_at": "2026-08-10T00:00:00Z",
        "completed_at": "2026-08-10T00:29:00Z",
    }
    assert sgp.job_wall_minutes(job) == pytest.approx(29.0)


def test_job_wall_minutes_not_completed_is_none():
    job = {"status": "in_progress", "started_at": "2026-08-10T00:00:00Z", "completed_at": None}
    assert sgp.job_wall_minutes(job) is None


def test_job_wall_minutes_missing_timestamp_is_none():
    job = {"status": "completed", "started_at": None, "completed_at": "2026-08-10T00:29:00Z"}
    assert sgp.job_wall_minutes(job) is None


def test_job_wall_minutes_negative_delta_is_none():
    job = {
        "status": "completed",
        "started_at": "2026-08-10T00:29:00Z",
        "completed_at": "2026-08-10T00:00:00Z",
    }
    assert sgp.job_wall_minutes(job) is None


class TestComputeJobVerdict:
    """Guilt + innocence on the two named guards (mutation-checked by hand during
    development: flipping `>=`/`>` to `<`/`<=` or the threshold constants makes
    these red — see PR description)."""

    def test_innocence_both_under_threshold(self):
        # p95=25/30=83.3% < 85% ; growth (25-24)/24=4.2% < 8%
        v = sgp.compute_job_verdict(24.0, 25.0, 24.0, 30)
        assert v["near_timeout"] is False
        assert v["weekly_growth"] is False
        assert v["severity"] is None

    def test_near_timeout_only_is_p1(self):
        # p95=27/30=90% >= 85% ; growth (20-20)/20=0% < 8%
        v = sgp.compute_job_verdict(20.0, 27.0, 20.0, 30)
        assert v["near_timeout"] is True
        assert v["weekly_growth"] is False
        assert v["severity"] == "P1"

    def test_weekly_growth_only_is_p1(self):
        # p95=20/30=66.7% < 85% ; growth (28-19)/19=47.4% > 8%
        v = sgp.compute_job_verdict(28.0, 20.0, 19.0, 30)
        assert v["near_timeout"] is False
        assert v["weekly_growth"] is True
        assert v["severity"] == "P1"

    def test_both_conditions_is_p0(self):
        v = sgp.compute_job_verdict(28.0, 29.0, 19.0, 30)
        assert v["near_timeout"] is True
        assert v["weekly_growth"] is True
        assert v["severity"] == "P0"

    def test_missing_timeout_never_fabricates_near_timeout(self):
        v = sgp.compute_job_verdict(28.0, 29.0, 19.0, None)
        assert v["near_timeout"] is False
        assert v["p95_pct_of_timeout"] is None

    def test_missing_previous_window_never_fabricates_growth(self):
        v = sgp.compute_job_verdict(28.0, 29.0, None, 30)
        assert v["weekly_growth"] is False
        assert v["trend_delta_pct"] is None

    def test_exact_threshold_boundary_is_not_over(self):
        # p95 exactly at threshold pct -> >= triggers (near_timeout uses >=).
        v = sgp.compute_job_verdict(20.0, 25.5, 20.0, 30)  # 25.5/30 = 85.0% exactly
        assert v["near_timeout"] is True
        # growth strictly below the threshold -> does not trigger; strictly above
        # -> does (weekly_growth uses a plain >, tested off the exact float
        # boundary to avoid asserting on binary-float rounding of 8.0%).
        below = sgp.compute_job_verdict(21.5, 20.0, 20.0, 30)  # (21.5-20)/20 = 7.5%
        above = sgp.compute_job_verdict(21.7, 20.0, 20.0, 30)  # (21.7-20)/20 = 8.5%
        assert below["weekly_growth"] is False
        assert above["weekly_growth"] is True


def test_read_job_timeouts_parses_declared_timeout(tmp_path):
    workflow = tmp_path / "tests.yml"
    workflow.write_text(
        "jobs:\n"
        "  backend-tests:\n"
        "    name: Backend Tests (Python)\n"
        "    timeout-minutes: 30\n"
        "  no-timeout-job:\n"
        "    name: No Timeout\n"
    )
    mapping, error = sgp.read_job_timeouts(workflow)
    assert error is None
    assert mapping["backend-tests"] == {"name": "Backend Tests (Python)", "timeout_minutes": 30}
    assert mapping["no-timeout-job"]["timeout_minutes"] is None


def test_read_job_timeouts_missing_pyyaml_degrades_to_declared_error(tmp_path, monkeypatch):
    import builtins

    workflow = tmp_path / "tests.yml"
    workflow.write_text("jobs:\n  x:\n    timeout-minutes: 5\n")

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("simulated: no module named yaml")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    mapping, error = sgp.read_job_timeouts(workflow)
    assert mapping == {}
    assert error is not None and "PyYAML unavailable" in error


def test_count_test_files(tmp_path):
    test_dir = tmp_path / "backend" / "tests"
    (test_dir / "sub").mkdir(parents=True)
    (test_dir / "test_a.py").write_text("")
    (test_dir / "sub" / "test_b.py").write_text("")
    (test_dir / "sub" / "not_a_test.py").write_text("")
    count, error = sgp.count_test_files(tmp_path, "backend/tests")
    assert error is None
    assert count == 2


def test_count_test_files_missing_dir_is_error_not_zero(tmp_path):
    count, error = sgp.count_test_files(tmp_path, "does/not/exist")
    assert count is None
    assert error is not None


# ---------------------------------------------------------------------------
# Fixture builders for the subprocess boundary
# ---------------------------------------------------------------------------


def _proc(cmd, rc: int, out: str, err: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(cmd, rc, out, err)


def _mk_run(run_id: int, event: str, created_at: str, head_branch: str = "main") -> dict:
    return {"id": run_id, "event": event, "head_branch": head_branch, "created_at": created_at}


def _mk_job(name: str, minutes: float, status: str = "completed") -> dict:
    started_dt = datetime(2026, 8, 10, 0, 0, 0, tzinfo=timezone.utc)
    completed_dt = started_dt + timedelta(minutes=minutes)
    return {
        "name": name,
        "status": status,
        "started_at": started_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "completed_at": completed_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _assert_explicit_get(cmd: list[str]) -> None:
    """`gh api` silently switches its default method to POST the instant any
    `-f`/`-F` field is present, unless `-X`/`--method` overrides it — every
    `-f`-bearing call this module makes MUST carry an explicit `-X GET`
    (regression coverage for the real-API 404 this script's own first dry-run
    hit on `fetch_run_jobs()` before this flag was added — see PR description).
    A fake that stayed silent on a missing `-X GET` would never have caught
    that; a real subprocess call did, and this assertion is what keeps it
    caught without needing the network again.
    """
    has_f = "-f" in cmd or "-F" in cmd
    if has_f:
        assert "-X" in cmd, f"gh api call has -f but no explicit -X GET: {cmd}"
        idx = cmd.index("-X")
        assert cmd[idx + 1] == "GET", f"gh api call's -X is not GET: {cmd}"


def _make_fake_gh(repo: str, workflow: str, runs: list[dict], jobs_by_run: dict[int, list[dict]], deny_list_runs: bool = False):
    def fake_run(cmd, **kwargs):  # noqa: ANN001, ANN003
        assert cmd[0] == "gh", f"unexpected non-gh subprocess call: {cmd}"
        _assert_explicit_get(cmd)
        if cmd[1] == "api" and cmd[2] == f"repos/{repo}/actions/workflows/{workflow}/runs":
            if deny_list_runs:
                return _proc(cmd, 1, "", "HTTP 403: denied")
            return _proc(cmd, 0, json.dumps({"total_count": len(runs), "workflow_runs": runs}))
        if cmd[1] == "api" and cmd[2].endswith("/jobs"):
            run_id = int(cmd[2].split("/")[-2])
            return _proc(cmd, 0, json.dumps({"jobs": jobs_by_run.get(run_id, [])}))
        raise AssertionError(f"unexpected gh invocation: {cmd}")

    return fake_run


def _write_workflow(tmp_path: Path, timeout_minutes: int = 30) -> Path:
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    wf_path = wf_dir / "tests.yml"
    wf_path.write_text(
        "jobs:\n"
        "  backend-tests:\n"
        "    name: Backend Tests (Python)\n"
        f"    timeout-minutes: {timeout_minutes}\n"
    )
    # count_test_files() must find a real directory — declared-error-not-zero
    # discipline (module docstring) means an absent test dir lands in errors[],
    # which every build_record() scenario below asserts is empty.
    test_dir = tmp_path / "backend" / "tests"
    test_dir.mkdir(parents=True)
    (test_dir / "test_placeholder.py").write_text("")
    # send_alert() fail-visibly refuses to dispatch through a gateway that does
    # not exist on disk (mirrors the wrapper's own "ALERT NOT SENT: tg_notify.py
    # gateway missing" branch) — every scenario that expects a dispatch needs a
    # real (fake-content) file at the path it passes.
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "tg_notify.py").write_text("# fake gateway for tests\n")
    return wf_path


# ---------------------------------------------------------------------------
# build_record integration scenarios
# ---------------------------------------------------------------------------


def test_build_record_p0_both_conditions_dispatches_one_p0_alert(tmp_path, monkeypatch):
    _write_workflow(tmp_path, timeout_minutes=30)
    repo, workflow = "acme/repo", "tests.yml"

    runs = [
        _mk_run(1, "merge_group", CURRENT_TS),
        _mk_run(2, "merge_group", PREVIOUS_TS),
    ]
    jobs_by_run = {
        1: [_mk_job("Backend Tests (Python)", 29.0)],  # current: p50=p95=29 -> 96.7% of 30min
        2: [_mk_job("Backend Tests (Python)", 19.0)],  # previous: p50=19 -> growth (29-19)/19=52.6%
    }
    monkeypatch.setattr(sgp.subprocess, "run", _make_fake_gh(repo, workflow, runs, jobs_by_run))

    tg_calls: list[list[str]] = []

    def fake_tg_run(cmd, **kwargs):  # noqa: ANN001, ANN003
        tg_calls.append(cmd)
        return _proc(cmd, 0, "tg_notify: sent\n", "")

    monkeypatch.setattr(sgp, "_run_tg_notify", fake_tg_run)

    record = sgp.build_record(
        repo, workflow, tmp_path, "backend/tests", NOW, 7, tmp_path / "scripts" / "tg_notify.py"
    )

    job = record["jobs"]["backend-tests"]
    assert job["severity"] == "P0"
    assert job["near_timeout"] is True
    assert job["weekly_growth"] is True
    assert len(record["alerts_sent"]) == 1
    assert record["alerts_sent"][0]["tier"] == "p0"
    assert record["alerts_sent"][0]["dedup_key"] == "suite-growth:backend-tests"
    assert len(tg_calls) == 1
    assert "--tier" in tg_calls[0] and "p0" in tg_calls[0]
    assert record["errors"] == []


def test_build_record_near_timeout_only_is_p1_digest(tmp_path, monkeypatch):
    _write_workflow(tmp_path, timeout_minutes=30)
    repo, workflow = "acme/repo", "tests.yml"
    runs = [
        _mk_run(1, "merge_group", CURRENT_TS),
        _mk_run(2, "merge_group", PREVIOUS_TS),
    ]
    jobs_by_run = {
        1: [_mk_job("Backend Tests (Python)", 27.0)],  # 90% of timeout -> near_timeout
        2: [_mk_job("Backend Tests (Python)", 27.0)],  # flat growth -> not weekly_growth
    }
    monkeypatch.setattr(sgp.subprocess, "run", _make_fake_gh(repo, workflow, runs, jobs_by_run))
    tg_calls: list[list[str]] = []
    monkeypatch.setattr(
        sgp, "_run_tg_notify", lambda cmd, **kw: (tg_calls.append(cmd), _proc(cmd, 0, "sent", ""))[1]
    )

    record = sgp.build_record(
        repo, workflow, tmp_path, "backend/tests", NOW, 7, tmp_path / "scripts" / "tg_notify.py"
    )

    job = record["jobs"]["backend-tests"]
    assert job["severity"] == "P1"
    assert job["near_timeout"] is True
    assert job["weekly_growth"] is False
    assert len(record["alerts_sent"]) == 1
    assert record["alerts_sent"][0]["tier"] == "digest"
    assert len(tg_calls) == 1


def test_build_record_weekly_growth_only_is_p1_digest(tmp_path, monkeypatch):
    _write_workflow(tmp_path, timeout_minutes=30)
    repo, workflow = "acme/repo", "tests.yml"
    runs = [
        _mk_run(1, "merge_group", CURRENT_TS),
        _mk_run(2, "merge_group", PREVIOUS_TS),
    ]
    jobs_by_run = {
        1: [_mk_job("Backend Tests (Python)", 15.0)],  # 50% of timeout -> not near_timeout
        2: [_mk_job("Backend Tests (Python)", 10.0)],  # growth (15-10)/10=50% -> weekly_growth
    }
    monkeypatch.setattr(sgp.subprocess, "run", _make_fake_gh(repo, workflow, runs, jobs_by_run))
    tg_calls: list[list[str]] = []
    monkeypatch.setattr(
        sgp, "_run_tg_notify", lambda cmd, **kw: (tg_calls.append(cmd), _proc(cmd, 0, "sent", ""))[1]
    )

    record = sgp.build_record(
        repo, workflow, tmp_path, "backend/tests", NOW, 7, tmp_path / "scripts" / "tg_notify.py"
    )

    job = record["jobs"]["backend-tests"]
    assert job["severity"] == "P1"
    assert job["near_timeout"] is False
    assert job["weekly_growth"] is True
    assert len(record["alerts_sent"]) == 1
    assert record["alerts_sent"][0]["tier"] == "digest"


def test_build_record_innocence_no_alert(tmp_path, monkeypatch):
    _write_workflow(tmp_path, timeout_minutes=30)
    repo, workflow = "acme/repo", "tests.yml"
    runs = [
        _mk_run(1, "merge_group", CURRENT_TS),
        _mk_run(2, "merge_group", PREVIOUS_TS),
    ]
    jobs_by_run = {
        1: [_mk_job("Backend Tests (Python)", 18.0)],  # 60% of timeout
        2: [_mk_job("Backend Tests (Python)", 17.5)],  # growth ~2.9% < 8%
    }
    monkeypatch.setattr(sgp.subprocess, "run", _make_fake_gh(repo, workflow, runs, jobs_by_run))

    def fail_if_called(cmd, **kw):
        raise AssertionError("tg_notify must never be invoked when nothing crosses a threshold")

    monkeypatch.setattr(sgp, "_run_tg_notify", fail_if_called)

    record = sgp.build_record(
        repo, workflow, tmp_path, "backend/tests", NOW, 7, tmp_path / "scripts" / "tg_notify.py"
    )

    job = record["jobs"]["backend-tests"]
    assert job["severity"] is None
    assert record["alerts_sent"] == []
    assert record["errors"] == []


def test_build_record_excludes_develop_push_and_pull_request(tmp_path, monkeypatch):
    """Only push:main + merge_group count as gate load (module docstring)."""
    _write_workflow(tmp_path, timeout_minutes=30)
    repo, workflow = "acme/repo", "tests.yml"
    runs = [
        _mk_run(1, "push", CURRENT_TS, head_branch="develop"),
        _mk_run(2, "pull_request", CURRENT_TS, head_branch="main"),
    ]
    jobs_by_run = {
        1: [_mk_job("Backend Tests (Python)", 99.0)],  # would blow every threshold if counted
        2: [_mk_job("Backend Tests (Python)", 99.0)],
    }
    monkeypatch.setattr(sgp.subprocess, "run", _make_fake_gh(repo, workflow, runs, jobs_by_run))
    monkeypatch.setattr(sgp, "_run_tg_notify", lambda cmd, **kw: (_ for _ in ()).throw(AssertionError("unreachable")))

    record = sgp.build_record(
        repo, workflow, tmp_path, "backend/tests", NOW, 7, tmp_path / "scripts" / "tg_notify.py"
    )
    assert record["jobs"] == {}
    assert record["alerts_sent"] == []


def test_main_writes_record_and_exits_nonzero_on_total_api_failure(tmp_path, monkeypatch):
    _write_workflow(tmp_path, timeout_minutes=30)
    repo, workflow = "acme/repo", "tests.yml"
    monkeypatch.setattr(
        sgp.subprocess, "run", _make_fake_gh(repo, workflow, [], {}, deny_list_runs=True)
    )
    out_dir = tmp_path / "out"

    rc = sgp.main(
        [
            "--repo", repo,
            "--workflow", workflow,
            "--repo-root", str(tmp_path),
            "--out-dir", str(out_dir),
            "--test-dir", "backend/tests",
            "--now", "2026-08-14T00:00:00Z",
            "--no-alert",
        ]
    )

    assert rc == 1
    written = [p for p in out_dir.glob("*.json") if p.name != ".last-run-pointer.json"]
    assert written, "record must be written even when every gh call failed"
    payload = json.loads((out_dir / ".last-run-pointer.json").read_text())
    assert payload["errors_count"] >= 1
    record = json.loads(written[0].read_text())
    assert any("list_workflow_runs" in e for e in record["errors"])


def test_main_healthy_day_exits_zero(tmp_path, monkeypatch):
    _write_workflow(tmp_path, timeout_minutes=30)
    repo, workflow = "acme/repo", "tests.yml"
    runs = [
        _mk_run(1, "merge_group", CURRENT_TS),
        _mk_run(2, "merge_group", PREVIOUS_TS),
    ]
    jobs_by_run = {
        1: [_mk_job("Backend Tests (Python)", 18.0)],
        2: [_mk_job("Backend Tests (Python)", 17.5)],
    }
    monkeypatch.setattr(sgp.subprocess, "run", _make_fake_gh(repo, workflow, runs, jobs_by_run))
    out_dir = tmp_path / "out"

    rc = sgp.main(
        [
            "--repo", repo,
            "--workflow", workflow,
            "--repo-root", str(tmp_path),
            "--out-dir", str(out_dir),
            "--test-dir", "backend/tests",
            "--now", "2026-08-14T00:00:00Z",
            "--no-alert",
        ]
    )
    assert rc == 0
    written = [p for p in out_dir.glob("*.json") if p.name != ".last-run-pointer.json"]
    assert len(written) == 1
