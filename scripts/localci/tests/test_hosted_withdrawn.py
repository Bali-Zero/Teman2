"""B43 guilt + innocence: a hosted check run cancelled by an actor AFTER its PR was closed unmerged, with no step failed, is no hosted verdict
(listed under ``hosted_withdrawn``, never compared). Every other cancelled run keeps its class. Fixture: #8640's shape (closed 00:03:36Z, E2E
cancelled 00:04:32Z, annotation "The run was canceled by @<actor>.", every step success)."""
from __future__ import annotations

import pytest

from .test_hosted_aborted import APP, CTX, NAME, REPO, AbortGH, Hub, check_run, hc, incident, mg
from .test_merger_report import decision, pull, run_report

CLOSED, DONE = "2026-10-17T00:03:36Z", "2026-10-17T00:04:32Z"
ACTOR = "The run was canceled by @some-actor."
STEPS = [("Set up job", "success"), ("Checkout code", "success"), ("Run E2E tests", "success"), ("Post Checkout code", "success"), ("Complete job", "cancelled")]
PULL = {"state": "closed", "merged": False, "closed_at": CLOSED}
ROW = {"context": NAME, "app_id": APP, "hosted_red": [{"id": 11, "conclusion": "cancelled"}]}


def clear(tmp_path, monkeypatch, pr=PULL, at=DONE, annotations=(ACTOR,), steps=STEPS, extra=()):
    runs = [check_run(11, NAME, "cancelled", at), *extra]
    monkeypatch.setattr(hc, "gh_get", Hub("9" * 40, steps=steps, annotations=annotations, attempts=runs))
    j = mg.AbortJudge(REPO, tmp_path / "none.git", {})
    j.pull = pr
    return mg.recorded_clearance(j, j, lambda: runs, [], ROW)


def test_innocence_the_8640_shape_a_cancel_by_an_actor_after_an_unmerged_close_is_withdrawn(tmp_path, monkeypatch):
    assert clear(tmp_path, monkeypatch) == {"stale_why": "hosted_aborted", "aborted_runs": [{"check_run_id": 11, "step": mg.WITHDRAWN}]}


def test_innocence_the_runners_own_cancel_line_beside_the_actors_is_still_withdrawn(tmp_path, monkeypatch):
    assert clear(tmp_path, monkeypatch, annotations=(ACTOR, mg.ABORT_CANCELED))["stale_why"] == "hosted_aborted"


def test_guilt_a_cancel_before_the_close_stays_red(tmp_path, monkeypatch):
    assert clear(tmp_path, monkeypatch, at="2026-10-17T00:03:00Z") == {}


def test_guilt_a_merged_pr_stays_red(tmp_path, monkeypatch):
    assert clear(tmp_path, monkeypatch, pr={**PULL, "merged": True}) == {}


@pytest.mark.parametrize("pr", [None, {}, {**PULL, "state": "open"}, {**PULL, "closed_at": None}, {**PULL, "merged": None}])
def test_guilt_a_pr_not_known_closed_and_unmerged_stays_red(tmp_path, monkeypatch, pr):
    assert clear(tmp_path, monkeypatch, pr=pr) == {}


@pytest.mark.parametrize("bad", ["failure", "timed_out"])
def test_guilt_a_failed_step_stays_red(tmp_path, monkeypatch, bad):
    steps = [(n, bad if n == "Run E2E tests" else c) for n, c in STEPS]
    assert clear(tmp_path, monkeypatch, steps=steps) == {}


@pytest.mark.parametrize("ann", [(), ("Process completed with exit code 1.",), (ACTOR, "Process completed with exit code 1."),
                                 (ACTOR, "The job has exceeded the maximum execution time of 15m0s"), ("canceled by someone",)])
def test_guilt_no_annotation_or_any_other_failure_stays_red(tmp_path, monkeypatch, ann):
    assert clear(tmp_path, monkeypatch, annotations=ann) == {}


def test_guilt_another_red_attempt_beside_the_withdrawn_one_stays_red(tmp_path, monkeypatch):
    assert clear(tmp_path, monkeypatch, extra=[check_run(12, NAME, "failure", DONE)]) == {}


def test_a_concurrency_answered_cancel_is_still_superseded_not_withdrawn(tmp_path, monkeypatch):
    green = {**check_run(12, NAME, "success", "2026-10-17T00:10:00Z"), "app": {"id": APP, "slug": "x"}}
    assert clear(tmp_path, monkeypatch, extra=[green]) == {"stale_why": "cancelled_superseded", "superseded_cancelled": [11]}


def withdrawn_incident(tmp_path, monkeypatch, **kw):
    d, gh = incident(tmp_path, monkeypatch)
    d["ts"] = "2026-10-17T00:47:51Z"
    gh.pulls = {1: {**pull(d["head_sha"], state="closed"), "closed_at": CLOSED, **kw.pop("pull", {})}}
    gh.attempts = [{**check_run(11, CTX[0], "cancelled", kw.pop("at", DONE)), "app": {"id": APP}}]
    gh.hub = Hub(d["head_sha"], jname=CTX[0], steps=kw.pop("steps", STEPS), annotations=kw.pop("annotations", (ACTOR,)), attempts=gh.attempts)
    return d, gh


def test_the_report_counts_the_8640_event_as_zero_false_greens_and_one_withdrawn_context(tmp_path, monkeypatch, capsys):
    d, gh = withdrawn_incident(tmp_path, monkeypatch)
    rc, rep = run_report(tmp_path, monkeypatch, [d], gh)
    assert rep["false_green_breakdown"] == {"pr": 0, "context": 0, "recorded": 0} and rep["context_counts"]["HOSTED_ABORTED"] == 1
    assert rep["hosted_aborted"]["count"] == 0
    assert rep["hosted_withdrawn"] == {"count": 1, "list": [{"pr": 1, "head_sha": d["head_sha"], "context": CTX[0], "check_run_id": 11}]}
    assert "hosted_withdrawn (B43" in capsys.readouterr().out


def test_the_report_keeps_the_false_green_when_the_cancel_came_before_the_close_or_a_step_failed(tmp_path, monkeypatch):
    d, gh = withdrawn_incident(tmp_path, monkeypatch, at="2026-10-17T00:01:00Z")
    rc, rep = run_report(tmp_path, monkeypatch, [d], gh)
    assert rc == 1 and rep["false_green_breakdown"] == {"pr": 1, "context": 1, "recorded": 1} and rep["hosted_withdrawn"]["count"] == 0
    d, gh = withdrawn_incident(tmp_path / "b", monkeypatch, steps=[(n, "failure" if n == "Run E2E tests" else c) for n, c in STEPS])
    rc, rep = run_report(tmp_path / "b", monkeypatch, [d], gh)
    assert rc == 1 and rep["hosted_withdrawn"]["count"] == 0 and rep["false_green_breakdown"]["context"] == 1


def test_a_memoed_pull_without_closed_at_is_not_final_so_it_is_read_again():
    old = {"merged": False, "state": "closed", "merge_commit_sha": None, "merged_at": None, "head": {"sha": "a"}}
    assert not mg.memo_final_pr(old, 0.0)
    assert mg.memo_final_pr({**old, "closed_at": CLOSED}, 0.0)
    assert mg.project_pull({**old, "closed_at": CLOSED})["closed_at"] == CLOSED


@pytest.mark.parametrize("pr", [{**PULL, "closed_at": None}, {"state": "closed", "merged": False}])
def test_guilt_a_pull_without_closed_at_answers_no_and_never_raises(tmp_path, pr):
    j = mg.AbortJudge(REPO, tmp_path / "none.git", {})
    j.pull = pr
    ok, why = j.withdrawn(11, DONE)
    assert ok is False and "closed and unmerged" in why
