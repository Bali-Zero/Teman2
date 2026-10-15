"""B30 D1 terms 4-5 end to end through the runner and local_side: a candidate crash in an unmapped check (F1) and a candidate FAIL quoting ENOSPC (F2) are never re-decided."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

from .test_merger import REPO, mg, pr, world  # noqa: F401 — `world` is a fixture
from .test_redecide import dec, run

_spec = importlib.util.spec_from_file_location("runner_b30p", Path(__file__).resolve().parents[1] / "runner.py")
rn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rn)

E2E, BACK = "E2E Tests (Playwright)", "Backend Tests (Python)"
PLAN = {"contexts_status": "ok", "required_contexts": [E2E, BACK],
        "contexts_map": {E2E: {"mapping": "executed", "check": "ctx.e2e-tests"}, BACK: {"mapping": "executed", "check": "ctx.backend-tests"}},
        "checks": {}}
FLOOR = "host_disk_below_floor 3GB<12GB: the docker host has 3 GB free, under LOCALCI_MIN_FREE_GB=12"


def row_from(view: dict) -> dict:
    """The decision row exactly as decide() journals it, from a runner view (status per check, with its reason)."""
    ctx = rn.evaluate_contexts(view, PLAN)
    status = {"overall": rn.overall(view), "checks": view, "contexts": ctx}
    loc = mg.local_side(status)
    return dec(overall=status["overall"], error=None, contexts={k: v.get("verdict") for k, v in ctx["results"].items()},
               checks={k: v.get("status") for k, v in view.items()}, non_executed=loc["non_executed"], host_no_verdict=loc["host_no_verdict"],
               host_checks=mg.host_checks(status))


def test_f1_a_candidate_crash_in_an_unmapped_check_beside_a_host_no_verdict_is_not_transient():
    """tests.scripts_impacted runs CANDIDATE pytest and maps to no context; the runner calls its crash, timeout or empty collection ERROR."""
    crash = rn.classify_pytest(-9, {"collected": 10, "failures": 0, "errors": 0, "executed": 3, "skipped": 0})
    assert crash[0] == "ERROR"
    view = {"ctx.e2e-tests": {"status": "BLOCKED", "reason": FLOOR}, "ctx.backend-tests": {"status": "PASS", "reason": "ok"},
            "tests.scripts_impacted": {"status": crash[0], "reason": crash[1]}, "review.independent": {"status": "QUEUED", "reason": ""}}
    row = row_from(view)
    assert row["host_no_verdict"] and row["checks"]["tests.scripts_impacted"] == "ERROR"
    assert mg.transient_reasons(row) == []
    assert run([row], host_free_gb=150.0, start_floor_gb=100.0)[0] == []


def test_f2_a_failing_test_whose_output_quotes_enospc_is_not_a_host_no_verdict_to_re_decide(tmp_path):
    """The runner reads host_disk_full from the SANDBOX'S OWN OUTPUT before any verdict: a red pytest (rc=1) that quotes or raises ENOSPC."""
    (tmp_path / "test_x.py").write_text('def test_disk_message():\n    msg = "OSError: [Errno 28] No space left on device"\n    assert msg == "disk"\n')
    res = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tmp_path / "test_x.py")], capture_output=True, text=True,
                         cwd=tmp_path)
    assert res.returncode == 1   # the candidate's own FAIL
    log = tmp_path / "log.txt"
    log.write_text(res.stdout + res.stderr)
    reason = rn.host_disk_full([log], "ctx.backend-tests")
    assert reason and reason.startswith("host_disk_full")   # the runner turns that FAIL into ERROR host_disk_full
    view = {"ctx.e2e-tests": {"status": "PASS", "reason": "ok"}, "ctx.backend-tests": {"status": "ERROR", "reason": reason},
            "review.independent": {"status": "QUEUED", "reason": ""}}
    row = row_from(view)
    assert row["host_no_verdict"] == {BACK: "host_disk_full"}
    assert mg.transient_reasons(row) == []
    assert run([row], host_free_gb=150.0, start_floor_gb=100.0)[0] == []


def test_the_floor_row_with_its_own_check_error_still_re_decides():
    view = {"ctx.e2e-tests": {"status": "ERROR", "reason": FLOOR}, "ctx.backend-tests": {"status": "PASS", "reason": "ok"},
            "tests.scripts_impacted": {"status": "ERROR", "reason": FLOOR}, "review.independent": {"status": "QUEUED", "reason": ""}}
    r = row_from(view)
    assert mg.transient_reasons(r) == ["host_disk"]
    assert [p["number"] for p in run([r], host_free_gb=150.0, start_floor_gb=100.0)[0]] == [1]


def test_f1_with_attribution_the_candidate_crash_is_not_named_and_not_re_decided():
    crash = rn.classify_pytest(-9, {"collected": 10, "failures": 0, "errors": 0, "executed": 3, "skipped": 0})
    view = {"ctx.e2e-tests": {"status": "BLOCKED", "reason": FLOOR}, "ctx.backend-tests": {"status": "PASS", "reason": "ok"},
            "tests.scripts_impacted": {"status": crash[0], "reason": crash[1]}, "review.independent": {"status": "QUEUED", "reason": ""}}
    r = row_from(view)
    assert r["host_checks"] == ["ctx.e2e-tests"] and mg.transient_reasons(r) == []


def test_a_host_disk_full_check_is_never_named():
    assert not mg.host_measured("host_disk_full: tests.x: 'msg = \"OSError: [Errno 28] No space left on device\"'")
    assert mg.host_measured(FLOOR) and mg.host_measured("host_disk_unmeasured: docker df failed") and mg.host_measured("host_disk_floor_invalid: x")


def test_host_checks_reads_the_vouched_status_only():
    assert mg.host_checks({}) == [] and mg.host_checks({"checks": "x"}) == [] and mg.host_checks({"checks": {"a": "ERROR"}}) == []
    view = {"a": {"status": "ERROR", "reason": FLOOR}, "b": {"status": "PASS", "reason": FLOOR}, "c": {"status": "BLOCKED", "reason": "host_disk_unmeasured: x"},
            "d": {"status": "ERROR", "reason": "crashed (signal 9)"}, "e": {"status": "FAIL", "reason": FLOOR}}
    assert mg.host_checks({"checks": view}) == ["a", "c"]


def test_host_measured_is_total_and_reads_the_class_before_the_first_space_or_colon():
    assert not mg.host_measured(None) and not mg.host_measured(7) and not mg.host_measured(["host_disk_below_floor"])
    assert mg.host_measured("host_disk_unmeasured: docker df failed") and mg.host_measured("host_disk_below_floor 3GB<12GB")
    assert not mg.host_measured("not host_disk_below_floor") and not mg.host_measured("host_disk_below_floors 1GB")


def test_the_tick_journals_the_checks_the_host_pre_empted_and_never_a_candidate_one(world):  # noqa: F811
    world.gh.prs = [pr(1, world.head1)]
    world.runner.doc = {"checks": {"ctx.e2e-tests": {"status": "BLOCKED", "reason": FLOOR},
                                   "tests.scripts_impacted": {"status": "ERROR", "reason": "crashed (signal 9)"},
                                   "policy.change_map": {"status": "PASS", "reason": "ok"}}}
    assert world.tick() == 0
    rows = [r for r in world.journal() if r["kind"] == "decision"]
    assert len(rows) == 1 and rows[0]["host_checks"] == ["ctx.e2e-tests"]
    assert rows[0]["checks"]["tests.scripts_impacted"] == "ERROR"
