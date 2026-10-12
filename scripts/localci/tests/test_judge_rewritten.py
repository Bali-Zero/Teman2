"""B5-1: a red read with a BASE judge the candidate rewrites is no verdict, scoped to the step that reads it."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from . import test_contexts_exec as ce
from .fixture_repo import runner

pytestmark = pytest.mark.usefixtures("fake_env")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_b5_under_test", Path(runner.__file__).with_name(f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hc, mg = _load("hosted_compare"), _load("merger")
LINT = "scripts/lint.py"
SPEC = {"judge_modified": [ce.JUDGE], "steps": [{"name": "selftest", "trusted": [ce.JUDGE]}, {"name": "judge", "trusted": [ce.JUDGE]},
                                                {"name": "lint", "trusted": [LINT]}]}
TAIL = "; hosted judges with the candidate's copy, which this run did not execute — no verdict (never FAIL, never OK)"


def st(name: str, status: str = "PASS", reason: str = "rc=0") -> dict:
    return {"name": name, "status": status, "reason": reason}


@pytest.mark.parametrize("red", ["FAIL", "ERROR"])
def test_a_red_step_whose_own_judge_is_rewritten_is_blocked_judge_rewritten_never_fail(red):
    got = runner.steps_verdict([st("selftest"), st("judge", red, "rc=1"), st("lint")], SPEC)
    assert got == ("BLOCKED", f"judge_rewritten: judge read red with the BASE judge while the candidate rewrites ['{ce.JUDGE}']{TAIL}")


def test_a_red_step_whose_judge_is_not_rewritten_stays_fail_beside_a_rewritten_one():
    assert runner.steps_verdict([st("selftest"), st("judge"), st("lint", "FAIL", "rc=1")], SPEC) == ("FAIL", "1 step(s) FAIL: lint (rc=1)")
    # both red: the genuine one decides, and only it is named
    assert runner.steps_verdict([st("selftest"), st("judge", "FAIL", "rc=1"), st("lint", "FAIL", "rc=1")], SPEC) == ("FAIL", "1 step(s) FAIL: lint (rc=1)")


def test_without_a_rewritten_judge_a_red_is_a_fail_and_a_green_with_one_is_blocked_as_before():
    clean = {**SPEC, "judge_modified": []}
    assert runner.steps_verdict([st("selftest"), st("judge", "FAIL", "rc=1"), st("lint")], clean) == ("FAIL", "1 step(s) FAIL: judge (rc=1)")
    status, reason = runner.steps_verdict([st("selftest"), st("judge"), st("lint")], SPEC)
    assert status == "BLOCKED" and reason.startswith("3 step(s) rc=0 with the BASE judge") and "no green claimed" in reason


def test_a_rewritten_file_no_step_names_reaches_every_step_and_says_context_scope():
    wf = {**SPEC, "judge_modified": [ce.WF]}   # the workflow itself: every step is defined by it
    assert runner.steps_verdict([st("selftest"), st("judge"), st("lint", "FAIL", "rc=1")], wf) == (
        "BLOCKED", f"judge_rewritten: lint read red with the BASE judge while the candidate rewrites ['{ce.WF}'] "
                   f"(context scope: ['{ce.WF}'] named by no step){TAIL}")
    jobs = {"judge_modified": [ce.WF], "jobs": []}   # a service context's job steps carry no per-step attribution
    status, reason = runner.steps_verdict([st("backend-shard[1] › Run unit tests (sharded)", "FAIL", "rc=1")], jobs)
    assert status == "BLOCKED" and "(context scope: the plan attributes no judge to this step)" in reason


def test_the_plan_names_the_judges_of_each_step(tmp_path):
    spec = ce.plan_spec(ce.planned(tmp_path, {"docs/new.md": "x\n"}, ce.host_ctx()))
    assert [(s["name"], s.get("trusted")) for s in spec["steps"]] == [("selftest", [ce.JUDGE]), ("judge", [ce.JUDGE]), ("guilt control", []),
                                                                       ("pr sentinel", [])]


GH_SUCCESS = [{"name": "Gate", "status": "completed", "conclusion": "success", "app": {"id": 15368, "slug": "github-actions"}}]


@pytest.mark.parametrize("rewrite,klass", [(True, "LOCAL_BLIND"), (False, "FALSE_RED")])
def test_end_to_end_a_red_with_a_rewritten_judge_is_local_blind_and_refused_never_false_red(tmp_path, rewrite, klass):
    # #8076's shape: the candidate rewrites the judge and the surface it judges; the BASE judge reads red, hosted ran the candidate's: green
    cand = {"docs/bad.md": "VIOLATION\n", **({ce.JUDGE: ce.JUDGE_SRC + "# the candidate's contract\n"} if rewrite else {})}
    _, s = ce.ran(tmp_path, cand, ce.host_ctx())
    res = s["contexts"]["results"]["Gate"]
    rep = hc.compare(s, [{"context": "Gate", "app_id": 15368}], GH_SUCCESS, [])
    assert rep["rows"][0]["class"] == klass and rep["counts"]["FALSE_RED"] == (0 if rewrite else 1)
    why = mg.local_side(s)["why"]["executed_contexts_ok"]
    assert why and "Gate" in why   # the C3a-2 criterion refuses both: a no-verdict is not OK, a FAIL is not OK
    if rewrite:
        assert s["checks"]["ctx.judge"]["status"] == "BLOCKED" and res["verdict"] == "BLOCKED" and res["no_verdict"] == "judge_rewritten"
        assert rep["rows"][0]["local_detail"] == "BLOCKED (executed) judge_rewritten" and "Gate" not in s["contexts"]["red"]
    else:
        assert s["checks"]["ctx.judge"]["status"] == "FAIL" and "no_verdict" not in res
