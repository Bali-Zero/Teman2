"""B3: a docker host out of disk is no verdict on the candidate — the disk-full rule and the free-space floor."""
from __future__ import annotations

from pathlib import Path

import pytest

from .fixture_repo import runner

# the error lines the tools print when a write hits ENOSPC (npm and asyncpg as measured on Pro, 2026-10-08)
DISK_FULL = [
    "npm warn tar TAR_ENTRY_ERROR ENOSPC: no space left on device, write",
    "Error: ENOSPC: no space left on device, open '/w/apps/mouth/.next/cache/x'",
    "npm error code ENOSPC",
    'E   asyncpg.exceptions.DiskFullError: could not extend file "base/16384/2619": No space left on device',
    'FAILED tests/api/test_x.py::test_y - asyncpg.exceptions.DiskFullError: could not extend file "base/16384/2619": No spa...',
    "ERROR: Could not install packages due to an OSError: [Errno 28] No space left on device",
    'psycopg.errors.DiskFull: could not extend file "base/1/2": wrote only 4096 of 8192 bytes at block 9',
    "sqlalchemy.exc.DBAPIError: (sqlalchemy.dialects.postgresql.asyncpg.Error) <class 'asyncpg.exceptions.DiskFullError'>: could not "
    'extend file "base/1/3": No space left on device',
    'ERROR:  could not extend file "base/16384/16397": No space left on device',
    "tar: node_modules/x/index.js: Cannot write: No space left on device",
    "fatal: write error: No space left on device",
]
# a genuine failure that merely MENTIONS the words keeps its verdict: test names, fixtures, assertions, echoed source
MENTIONS = [
    "FAILED tests/test_disk.py::test_enospc_no_space_left_on_device_is_retried - assert 1 == 2",
    "tests/test_db.py::test_DiskFullError_maps_to_503 FAILED",
    "test_storage[ENOSPC] PASSED",
    'E       OSError: no space left on device',                  # apps/backend-rag/backend/tests/llm/test_codex_exec_client.py's fixture
    '>           raise OSError("no space left on device")',
    "E        +  where False = _is_transient(DiskFullError('disk full'))",   # tests/scripts/test_wa_mirror_intake_sweeper_watermark.py
    "FAILED tests/x.py::test_y - AssertionError: assert 'No space left on device' in ''",
    "    except asyncpg.exceptions.DiskFullError:",
    "E   RuntimeError: cache: No space left on device",
    "asyncpg.exceptions.CannotConnectNowError: the database system is in recovery mode",
]


def _log(tmp_path: Path, name: str, *lines: str) -> Path:
    p = tmp_path / name
    p.write_text("##[localci] step 1: Run tests\n" + "".join(f"{x}\n" for x in lines) + "##[localci] step 1 rc=1\n")
    return p


@pytest.mark.parametrize("line", DISK_FULL)
def test_each_disk_full_error_line_is_no_verdict(tmp_path, line):
    why = runner.host_disk_full([_log(tmp_path, "a.log", "collected 11376 items", line, "1 failed")], "backend-tests[2]")
    assert why and why.startswith("host_disk_full: backend-tests[2]: ") and "never FAIL, never OK" in why and "1 disk-full line(s)" in why


@pytest.mark.parametrize("line", MENTIONS)
def test_a_line_that_merely_mentions_the_words_keeps_the_verdict(tmp_path, line):
    assert runner.host_disk_full([_log(tmp_path, "a.log", "collected 3 items", line, "1 failed")], "unit") is None


def test_recovery_mode_counts_only_after_a_disk_full_line(tmp_path):
    recovery = "asyncpg.exceptions.CannotConnectNowError: the database system is in recovery mode"
    assert runner.host_disk_full([_log(tmp_path, "a.log", recovery, recovery)], "shard") is None   # alone: the service's own failure
    before = runner.host_disk_full([_log(tmp_path, "b.log", recovery, DISK_FULL[3])], "shard")
    after = runner.host_disk_full([_log(tmp_path, "c.log", DISK_FULL[3], recovery, recovery)], "shard")
    assert "0 postgres recovery-mode line(s) after it" in before and "2 postgres recovery-mode line(s) after it" in after
    across = runner.host_disk_full([_log(tmp_path, "d.log", DISK_FULL[0]), _log(tmp_path, "e.log", recovery)], "shard")
    assert "1 disk-full line(s), 1 postgres recovery-mode line(s) after it" in across   # the egress log after the leg's own


def test_missing_or_empty_log_paths_read_as_no_line(tmp_path):
    assert runner.host_disk_full(["", None, str(tmp_path / "absent.log"), str(tmp_path)], "unit") is None


# ------------------------------------------------------------------ the context: ERROR host_disk_full, never FAIL, never OK
SPEC = {"jobs": [{"job_id": "backend-shard", "legs": [{"n": 1}, {"n": 2}]}, {"job_id": "fanin", "legs": [{}]}], "needs": {}, "judge_modified": []}


def _legs(monkeypatch, tmp_path, by_n: dict):
    ran = []

    def leg(name, spec, job, leg, run_dir, plan, needs, arts, X):
        n = leg.get("n", 0)
        ran.append(n)
        rc, lines = by_n.get(n, (0, ["1 passed"]))
        log = _log(tmp_path, f"leg{n}.log", *lines)
        return {"label": f"{job['job_id']}[{n}]", "rc": rc, "steps": [{"name": "s", "status": "FAIL" if rc else "PASS", "reason": f"rc={rc}"}],
                "seconds": 1, "cpu": 1, "infra": None, "log": str(log), "logs": [str(log)]}
    monkeypatch.setattr(runner, "_run_leg", leg)
    return ran


def test_a_shard_that_failed_on_a_full_disk_is_error_host_disk_full_and_the_chain_stops(monkeypatch, tmp_path):
    # guilt: before B3 this context read FAIL and hosted_compare called it FALSE_RED (B2 final head, Backend Tests on Pro)
    ran = _legs(monkeypatch, tmp_path, {1: (1, ["11376 passed", DISK_FULL[3], "2 errors"])})
    out = runner._execute_jobs("ctx.backend-tests", SPEC, tmp_path, {}, tmp_path / "ctx.log")
    assert out["status"] == "ERROR" and out["reason"].startswith("host_disk_full: backend-shard[1]: ") and ran == [1]
    assert runner.HOST_NO_VERDICT.match(out["reason"])


def test_npm_that_printed_enospc_and_exited_0_is_never_ok(monkeypatch, tmp_path):
    _legs(monkeypatch, tmp_path, {2: (0, [DISK_FULL[0]] * 3 + ["added 1520 packages"])})
    out = runner._execute_jobs("ctx.e2e-tests", SPEC, tmp_path, {}, tmp_path / "ctx.log")
    assert out["status"] == "ERROR" and "host_disk_full: backend-shard[2]: " in out["reason"] and "3 disk-full line(s)" in out["reason"]


def test_a_genuine_failure_that_names_enospc_in_a_test_stays_fail(monkeypatch, tmp_path):
    _legs(monkeypatch, tmp_path, {1: (1, MENTIONS)})
    out = runner._execute_jobs("ctx.backend-tests", SPEC, tmp_path, {}, tmp_path / "ctx.log")
    assert out["status"] == "FAIL" and "host_disk_full" not in out["reason"]


def test_a_disk_full_line_in_the_egress_log_of_a_leg_is_read_too(monkeypatch, tmp_path):
    egress = _log(tmp_path, "leg1.egress.log", DISK_FULL[5])

    def leg(name, spec, job, leg, run_dir, plan, needs, arts, X):
        log = _log(tmp_path, "leg.log", "1 passed")
        return {"label": job["job_id"], "rc": 0, "steps": [{"name": "s", "status": "PASS", "reason": "rc=0"}], "seconds": 1, "cpu": 1,
                "infra": None, "log": str(log), "logs": [str(log), str(egress)]}
    monkeypatch.setattr(runner, "_run_leg", leg)
    assert runner._execute_jobs("ctx.backend-tests", SPEC, tmp_path, {}, tmp_path / "ctx.log")["status"] == "ERROR"


def test_a_contained_steps_context_that_hit_a_full_disk_is_error_and_one_that_failed_stays_fail(monkeypatch, tmp_path):
    spec = {"kind": "contained_steps", "context": "organ", "steps": [{"name": "s"}], "env": {}, "driver_sha256": runner.sha256_bytes(runner.STEPS_DRIVER.read_bytes()),
            "isolation": {"mode": "container"}}
    plan = {"worktree": str(tmp_path), "trusted_files_sha256": {}}

    def contained(lines):
        def fake(name, spec, run_dir, plan, inner, overrides, extra, env, log, junit, timeout, workdir="/w", **kw):
            log.write_text(log.read_text() + "".join(f"{x}\n" for x in lines))
            junit.write_text('<testsuite><testcase name="s"><failure message="rc=1"/></testcase></testsuite>')
            return 1, None
        return fake
    for lines, status in (([DISK_FULL[6]], "ERROR"), (MENTIONS, "FAIL")):
        monkeypatch.setattr(runner, "execute_contained", contained(lines))
        res = runner._execute_candidate_contained("ctx.organ", spec, tmp_path, plan, 60, tmp_path / "organ.log", tmp_path / "organ.junit.xml")
        assert res["status"] == status and res["reason"].startswith("host_disk_full: ctx.organ: ") == (status == "ERROR"), res["reason"]


def test_the_status_names_a_host_condition_on_the_context_and_only_the_runners_own_reason_counts():
    plan = {"contexts_status": "ok", "required_contexts": ["A", "B", "C"], "contexts_map": {
        n: {"mapping": "executed", "check": f"ctx.{n.lower()}", "coverage": "full"} for n in ("A", "B", "C")}}
    view = {"ctx.a": {"status": "ERROR", "reason": "host_disk_full: shard[2]: 'E   asyncpg...' (1 disk-full line(s), ...)"},
            "ctx.b": {"status": "FAIL", "reason": "host_disk_full: forged by a step name"},   # a FAIL stays a FAIL whatever its text says
            "ctx.c": {"status": "ERROR", "reason": "1 step(s) ERROR: s (host_disk_full: echoed)"}}
    res = runner.evaluate_contexts(view, plan)["results"]
    assert (res["A"]["verdict"], res["A"]["no_verdict"]) == ("ERROR", "host_disk_full")
    assert "no_verdict" not in res["B"] and res["B"]["verdict"] == "FAIL" and "no_verdict" not in res["C"]
