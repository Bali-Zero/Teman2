"""B5-2: a context the trusted change_map skips is labelled and compared as a skip, never as `OK (executed)`."""
from __future__ import annotations

import pytest

from . import test_service_contexts as sc
from .fixture_repo import runner
from .test_judge_rewritten import hc

pytestmark = pytest.mark.usefixtures("fake_env")
NAME = "Backend Tests (Python)"
SKIP_REASON = "trusted change_map does not select backend-tests (suggested=[]): the hosted job skips, and a skipped required context is satisfied"


def _status(res: dict) -> dict:
    return {"run_id": "r", "overall": "PASS", "candidate_sha": "a" * 40, "contexts": {"status": "ok", "required": [NAME], "results": {NAME: res}}}


def _res(skipped: str | None = "change_map", verdict: str = "OK", coverage: str = "full") -> dict:
    return {"mapping": "executed", "check": "ctx.backend-tests", "verdict": verdict, "coverage": coverage, **({"skipped": skipped} if skipped else {})}


def _row(res: dict, conclusion: str | None, status: str = "completed") -> dict:
    runs = [{"name": NAME, "status": status, "conclusion": conclusion, "app": {"id": 15368, "slug": "github-actions"}}]
    return hc.compare(_status(res), [{"context": NAME, "app_id": 15368}], runs, [])


def test_the_runner_marks_a_change_map_skip_on_the_plan_and_on_the_context_result(tmp_path, monkeypatch):
    spec = sc.planned_svc(tmp_path, monkeypatch, sc.fr.CANDIDATE_FILES, sc.svc_ctx(runs_when="no-such-job"))
    assert spec["status"] == "NOT_APPLICABLE" and spec["skipped"] == "change_map" and spec["reason"].startswith("trusted change_map does not select")
    plan = {"contexts_status": "ok", "contexts_map": {NAME: {"mapping": "executed", "check": "ctx.backend-tests", "coverage": "full"}},
            "checks": {"ctx.backend-tests": {"kind": "record", "status": "NOT_APPLICABLE", "skipped": "change_map"}}}
    view = {"ctx.backend-tests": {"status": "NOT_APPLICABLE", "reason": SKIP_REASON}}
    ctx = runner.evaluate_contexts(view, plan)
    assert ctx["results"][NAME] == {**_res(), "check": "ctx.backend-tests"}
    runs = [{"name": NAME, "status": "completed", "conclusion": "skipped", "app": {"id": 15368, "slug": "github-actions"}}]
    row = hc.compare({"candidate_sha": "a" * 40, "contexts": ctx}, [{"context": NAME, "app_id": 15368}], runs, [])["rows"][0]
    assert (row["local_detail"], row["skip"]) == ("NOT_APPLICABLE (skip agreed: change_map)", "agreed")   # the runner's own result, compared
    plan["checks"]["ctx.backend-tests"] = {"kind": "record", "status": "NOT_APPLICABLE"}   # innocence: a NOT_APPLICABLE that is no skip
    assert "skipped" not in runner.evaluate_contexts(view, plan)["results"][NAME]


def test_both_sides_skipped_is_a_full_comparison_of_the_decision_labelled_as_a_skip():
    # measured 2026-10-08T09:49:54Z on #8076: this row read `OK (executed)` and was counted in compared_full as an execution
    rep = _row(_res(coverage="partial"), "skipped")   # the matrix's coverage is of an execution; a skip compares the decision
    r = rep["rows"][0]
    assert (r["class"], r["skip"], r["local_detail"], r["coverage"]) == ("AGREE", "agreed", "NOT_APPLICABLE (skip agreed: change_map)", "full")
    assert rep["coverage"] == {"compared_full": 1, "compared_partial": [], "compared_unrecorded": [], "compared_skip_agreed": [NAME]}
    assert f"compared_skip_agreed=1 ['{NAME}']" in hc.render({**rep, "source": "fixture"})


@pytest.mark.parametrize("conclusion,klass", [("success", "AGREE"), ("failure", "FALSE_GREEN")])
def test_skipped_here_while_hosted_ran_is_partial_and_named_and_a_wrong_skip_is_seen(conclusion, klass):
    rep = _row(_res(), conclusion)
    r = rep["rows"][0]
    assert (r["class"], r["skip"], r["local_detail"], r["coverage"]) == (klass, "hosted_ran", "NOT_APPLICABLE (skipped here; hosted ran)", "partial")
    assert rep["coverage"]["compared_full"] == 0 and rep["coverage"]["compared_partial"] == [NAME] and "subset" in r["coverage_note"]


def test_run_here_while_hosted_skipped_is_full_and_says_so():
    r = _row(_res(skipped=None), "skipped")["rows"][0]
    assert (r["class"], r["skip"], r["local_detail"], r["coverage"]) == ("AGREE", "hosted_skipped", "OK (executed; hosted skipped)", "full")


def test_an_executed_agreement_is_unchanged_and_a_pending_hosted_side_labels_no_skip():
    rep = _row(_res(skipped=None), "success")
    r = rep["rows"][0]
    assert (r["class"], r["skip"], r["local_detail"], r["coverage"]) == ("AGREE", None, "OK (executed)", "full")
    assert rep["coverage"]["compared_skip_agreed"] == []
    r = _row(_res(), None, status="in_progress")["rows"][0]
    assert (r["class"], r["skip"], r["local_detail"]) == ("HOSTED_PENDING", None, "NOT_APPLICABLE (skipped here: change_map)")
