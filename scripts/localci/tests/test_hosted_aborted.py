"""B27 guilt + innocence: a hosted check run cancelled by the job timeout in a SETUP step, with no logic step run, is HOSTED_ABORTED — no
hosted verdict, never compared. Every other cancelled or red run keeps its class."""
from __future__ import annotations

import json
import subprocess
import textwrap

import pytest

from .test_merger_report import BASE, CTX, K, FakeGH, decision, mg, pull, run_report

hc = mg.hc
REPO, NAME, APP = "o/r", "Backend Tests (Python)", 15368
TIMEOUT = "The job has exceeded the maximum execution time of 15m0s"
WORKFLOW = textwrap.dedent("""\
    name: Tests
    on: [pull_request]
    jobs:
      backend:
        name: Backend Tests (Python)
        runs-on: ubuntu-latest
        steps:
          - name: Checkout code
            uses: actions/checkout@v4
            with: {fetch-depth: 0}
          - name: Set up Python
            uses: actions/setup-python@v5
          - name: Run unit tests
            run: pytest
    """)
POST = [("Post Checkout code", "success"), ("Complete job", "success")]
HUNG = [("Set up job", "success"), ("Checkout code", "cancelled"), ("Set up Python", "skipped"), ("Run unit tests", "skipped"), *POST]
ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"}


def mirror(path, workflow=WORKFLOW) -> tuple:
    """A real repository holding ``workflow`` at ``.github/workflows/tests.yml`` (None: no workflow file): ``(path, commit sha)``."""
    path.mkdir(parents=True, exist_ok=True)
    git = lambda *a: subprocess.run(["git", "-C", str(path), *a], check=True, capture_output=True, text=True, env=ENV).stdout.strip()
    git("init", "-q", "-b", "main")
    (path / "README").write_text("x\n")
    if workflow is not None:
        (path / ".github" / "workflows").mkdir(parents=True)
        (path / ".github" / "workflows" / "tests.yml").write_text(workflow)
    git("add", "-A")
    git("commit", "-q", "-m", "c")
    return path, git("rev-parse", "HEAD")


class Hub:
    """GET actions/jobs/{id} and check-runs/{id}/annotations for one cancelled check run."""
    def __init__(self, sha, steps=HUNG, annotations=(TIMEOUT,), rid=11, wname="Tests", jname=NAME):
        self.sha, self.steps, self.annotations, self.rid, self.wname, self.jname = sha, steps, annotations, rid, wname, jname

    def __call__(self, path):
        if "/annotations" in path:
            return [{"annotation_level": "failure", "message": m} for m in self.annotations]
        if f"/actions/jobs/{self.rid}" in path:
            return {"id": self.rid, "check_run_url": f"https://api.github.com/repos/{REPO}/check-runs/{self.rid}", "head_sha": self.sha,
                    "workflow_name": self.wname, "name": self.jname,
                    "steps": [{"name": n, "status": "completed", "conclusion": c, "number": i} for i, (n, c) in enumerate(self.steps, 1)]}
        raise AssertionError(path)


RED = {"verdict": "RED", "red": [{"id": 11, "conclusion": "cancelled", "completed_at": "2026-10-14T18:50:08Z"}]}


def judge(tmp_path, monkeypatch, workflow=WORKFLOW, **hub):
    path, sha = mirror(tmp_path / f"repo{len(list(tmp_path.glob('repo*')))}.git", workflow)
    monkeypatch.setattr(hc, "gh_get", Hub(sha, **hub))
    return mg.AbortJudge(REPO, path, {})


def test_the_8514_shape_a_checkout_that_hung_to_the_timeout_with_every_later_step_skipped_is_aborted(tmp_path, monkeypatch):
    got = judge(tmp_path, monkeypatch)(NAME, RED)
    assert got == {"aborted": True, "runs": [{"check_run_id": 11, "step": "Checkout code"}]}


def test_the_runners_own_cancel_line_beside_the_timeout_is_still_a_timeout(tmp_path, monkeypatch):
    assert judge(tmp_path, monkeypatch, annotations=(TIMEOUT, "The operation was canceled."))(NAME, RED)["aborted"] is True


ASSERT = "      - name: Assert every upstream job succeeded\n        run: test \"$RESULT\" = success\n"
WITH_ASSERT = WORKFLOW.replace("    steps:\n", "    steps:\n" + ASSERT)
ASSERT_HUNG = [HUNG[0], ("Assert every upstream job succeeded", "success"), *HUNG[1:]]


def test_a_run_step_before_the_first_checkout_judged_no_repository_code_the_real_8514_shape(tmp_path, monkeypatch):
    got = judge(tmp_path, monkeypatch, workflow=WITH_ASSERT, steps=ASSERT_HUNG)(NAME, RED)
    assert got == {"aborted": True, "runs": [{"check_run_id": 11, "step": "Checkout code"}]}


ALWAYS = "      - name: Report\n        if: always()\n        run: echo balance\n      - name: Upload test results\n        uses: actions/upload-artifact@v4\n        if: ${{ always() }}\n"
WITH_ALWAYS = WORKFLOW + ALWAYS
ALWAYS_HUNG = [*HUNG[:4], ("Report", "success"), ("Upload test results", "success"), *POST]


def test_reporting_steps_declared_always_that_ran_after_the_hang_do_not_stop_the_abort_the_real_8514_tail(tmp_path, monkeypatch):
    assert judge(tmp_path, monkeypatch, workflow=WITH_ALWAYS, steps=ALWAYS_HUNG)(NAME, RED)["aborted"] is True


def test_a_step_after_the_hang_that_ran_without_a_status_function_or_failed_or_hides_the_call_in_a_string_stays_a_false_green(tmp_path, monkeypatch):
    plain = WITH_ALWAYS.replace("        if: always()\n        run: echo balance", "        run: echo balance")
    quoted = WITH_ALWAYS.replace("        if: always()\n        run: echo balance", "        if: github.ref == 'always()'\n        run: echo balance")
    for wf, steps in ((plain, ALWAYS_HUNG), (quoted, ALWAYS_HUNG), (WITH_ALWAYS, [*HUNG[:4], ("Report", "failure"), ("Upload test results", "success"), *POST]),
                      (WITH_ALWAYS, [*HUNG[:4], ("Report", "success"), ("Upload test results", "cancelled"), *POST])):
        assert judge(tmp_path, monkeypatch, workflow=wf, steps=steps)(NAME, RED)["aborted"] is False


@pytest.mark.parametrize("cond", ["always()", "${{ always() }}", "cancelled()", "${{ !cancelled() }}", "failure()", "always() && github.event_name == 'push'"])
def test_each_status_function_in_the_if_lets_a_reporting_step_run_after_the_hang(tmp_path, monkeypatch, cond):
    wf = WITH_ALWAYS.replace("        if: always()\n        run: echo balance", f"        if: {cond}\n        run: echo balance")
    assert judge(tmp_path, monkeypatch, workflow=wf, steps=ALWAYS_HUNG)(NAME, RED)["aborted"] is True


def test_a_run_step_before_the_cancelled_one_that_ran_after_a_checkout_stays_a_false_green(tmp_path, monkeypatch):
    wf = WORKFLOW.replace("      - name: Set up Python\n", "      - name: Probe\n        run: pytest --collect-only\n      - name: Set up Python\n")
    steps = [("Set up job", "success"), ("Checkout code", "success"), ("Probe", "success"), ("Set up Python", "cancelled"), ("Run unit tests", "skipped"), *POST]
    assert judge(tmp_path, monkeypatch, workflow=wf, steps=steps)(NAME, RED)["aborted"] is False


def test_a_run_step_before_a_checkout_that_was_skipped_does_not_count_as_before_the_checkout(tmp_path, monkeypatch):
    wf = WITH_ASSERT.replace("      - name: Set up Python\n", "      - name: Probe\n        run: pytest --collect-only\n      - name: Set up Python\n")
    steps = [("Set up job", "success"), ("Assert every upstream job succeeded", "success"), ("Checkout code", "skipped"), ("Probe", "success"),
             ("Set up Python", "cancelled"), ("Run unit tests", "skipped"), *POST]
    assert judge(tmp_path, monkeypatch, workflow=wf, steps=steps)(NAME, RED)["aborted"] is True   # nothing was checked out: the probe ran on an empty workspace


def test_a_third_party_or_local_action_before_the_checkout_is_not_an_empty_workspace_step(tmp_path, monkeypatch):
    for uses in ("someone/else@v1", "./.github/actions/prepare"):
        wf = WORKFLOW.replace("    steps:\n", f"    steps:\n      - name: Prepare\n        uses: {uses}\n")
        steps = [HUNG[0], ("Prepare", "success"), *HUNG[1:]]
        assert judge(tmp_path, monkeypatch, workflow=wf, steps=steps)(NAME, RED)["aborted"] is False, uses


def test_a_timeout_in_a_logic_step_stays_a_false_green(tmp_path, monkeypatch):
    steps = [("Set up job", "success"), ("Checkout code", "success"), ("Set up Python", "success"), ("Run unit tests", "cancelled"), *POST]
    assert judge(tmp_path, monkeypatch, steps=steps)(NAME, RED)["aborted"] is False


def test_a_cancel_by_concurrency_or_with_no_annotation_or_with_another_failure_stays_a_false_green(tmp_path, monkeypatch):
    for notes in (("Canceling since a higher priority waiting request for 'Tests' exists",), (), (TIMEOUT, "Process completed with exit code 1."),
                  ("Canceling since a higher priority waiting request exists", "The operation was canceled.")):
        assert judge(tmp_path, monkeypatch, annotations=notes)(NAME, RED)["aborted"] is False, notes


def test_a_step_named_checkout_that_runs_a_command_is_not_a_setup_step(tmp_path, monkeypatch):
    wf = WORKFLOW.replace("uses: actions/checkout@v4\n        with: {fetch-depth: 0}", "run: git clone https://example.invalid/x .")
    assert judge(tmp_path, monkeypatch, workflow=wf)(NAME, RED)["aborted"] is False


@pytest.mark.parametrize("uses", ["actions/checkout-evil@v1", "someone/actions/checkout@v4", "./.github/actions/checkout", "docker://actions/checkout:1"])
def test_only_the_five_setup_repositories_are_setup_steps_by_their_uses_entity(tmp_path, monkeypatch, uses):
    wf = WORKFLOW.replace("actions/checkout@v4", uses)
    assert judge(tmp_path, monkeypatch, workflow=wf)(NAME, RED)["aborted"] is False


@pytest.mark.parametrize("uses", ["actions/setup-python@v5", "actions/setup-node@abc", "actions/cache/restore@v4", "actions/download-artifact@v4"])
def test_each_allowlisted_repository_at_any_path_or_ref_is_a_setup_step(tmp_path, monkeypatch, uses):
    wf = WORKFLOW.replace("actions/checkout@v4", uses)
    assert judge(tmp_path, monkeypatch, workflow=wf)(NAME, RED)["aborted"] is True


def test_a_setup_step_that_timed_out_after_a_logic_step_ran_stays_a_false_green(tmp_path, monkeypatch):
    wf = WORKFLOW.replace("      - name: Set up Python\n        uses: actions/setup-python@v5\n      - name: Run unit tests\n        run: pytest\n",
                          "      - name: Run unit tests\n        run: pytest\n      - name: Set up Python\n        uses: actions/setup-python@v5\n")
    steps = [("Set up job", "success"), ("Checkout code", "success"), ("Run unit tests", "success"), ("Set up Python", "cancelled"), *POST]
    assert judge(tmp_path, monkeypatch, workflow=wf, steps=steps)(NAME, RED)["aborted"] is False


def test_a_step_after_the_cancelled_one_that_ran_stays_a_false_green(tmp_path, monkeypatch):
    steps = [("Set up job", "success"), ("Checkout code", "cancelled"), ("Set up Python", "success"), ("Run unit tests", "skipped"), *POST]
    assert judge(tmp_path, monkeypatch, steps=steps)(NAME, RED)["aborted"] is False


def test_a_setup_step_before_the_cancelled_one_that_failed_stays_a_false_green(tmp_path, monkeypatch):
    steps = [("Set up job", "success"), ("Checkout code", "failure"), ("Set up Python", "cancelled"), ("Run unit tests", "skipped"), *POST]
    assert judge(tmp_path, monkeypatch, steps=steps)(NAME, RED)["aborted"] is False


def test_a_red_that_is_not_a_cancelled_check_run_or_any_unqualified_red_beside_it_stays_a_false_green(tmp_path, monkeypatch):
    j = judge(tmp_path, monkeypatch)
    assert j(NAME, {"verdict": "RED", "red": [{"id": 11, "conclusion": "timed_out"}]})["aborted"] is False
    assert j(NAME, {"verdict": "RED", "red": [{"id": None, "conclusion": "cancelled"}]})["aborted"] is False
    assert j(NAME, {"verdict": "RED", "red": [*RED["red"], {"id": 12, "conclusion": "failure"}]})["aborted"] is False
    assert j(NAME, {"verdict": "GREEN", "red": []}) is None


@pytest.mark.parametrize("case", ["no-workflow", "matrix", "reusable", "two-jobs", "renamed-step", "extra-step", "no-set-up-job", "other-workflow"])
def test_an_ambiguous_mapping_raises_so_the_row_keeps_its_class(tmp_path, monkeypatch, case):
    wf, hub = WORKFLOW, {}
    if case == "no-workflow":
        wf = None
    elif case == "matrix":
        wf = WORKFLOW.replace("    runs-on: ubuntu-latest", "    runs-on: ubuntu-latest\n    strategy: {matrix: {x: [1]}}")
    elif case == "reusable":
        wf = "name: Tests\non: [pull_request]\njobs:\n  backend:\n    name: Backend Tests (Python)\n    uses: ./.github/workflows/x.yml\n"
    elif case == "two-jobs":
        wf = WORKFLOW + "  other:\n    name: Backend Tests (Python)\n    runs-on: x\n    steps:\n      - run: echo\n"
    elif case == "renamed-step":
        wf = WORKFLOW.replace("name: Checkout code", "name: Get the code")
    elif case == "extra-step":
        hub["steps"] = [*HUNG[:4], ("Surprise", "skipped"), *POST]
    elif case == "no-set-up-job":
        hub["steps"] = HUNG[1:]
    elif case == "other-workflow":
        hub["wname"] = "Lint"
    with pytest.raises(mg.MergerError):
        judge(tmp_path, monkeypatch, workflow=wf, **hub)(NAME, RED)


def check_run(rid, name, concl, at="2026-10-14T18:50:08Z"):
    return {"id": rid, "name": name, "status": "completed", "conclusion": concl, "completed_at": at, "app": {"id": APP, "slug": "github-actions"},
            "head_sha": "9" * 40}


def compare_one(abort_judge, concl="cancelled", local="OK"):
    status = {"candidate_sha": "9" * 40, "overall": "PASS", "contexts": {"status": "ok", "results": {NAME: {"verdict": local, "coverage": "full"}}}}
    return hc.compare(status, [{"context": NAME, "app_id": APP}], [check_run(11, NAME, concl)], [], abort_judge=abort_judge)


def test_compare_names_the_row_aborted_and_counts_it_in_no_compared_class(tmp_path, monkeypatch):
    rep = compare_one(judge(tmp_path, monkeypatch))
    (row,) = rep["rows"]
    assert row["class"] == "HOSTED_ABORTED" and row["class_before"] == "FALSE_GREEN" and row["abort_check"] == "aborted"
    assert row["aborted_runs"] == [{"check_run_id": 11, "step": "Checkout code"}]
    assert rep["counts"]["HOSTED_ABORTED"] == 1 and rep["counts"]["FALSE_GREEN"] == 0 and rep["counts"]["AGREE"] == 0
    assert rep["coverage"]["compared_full"] == 0 and hc.exit_code(rep) == hc.EXIT_OK and "HOSTED_ABORTED" not in hc.COMPARED


def test_compare_keeps_the_class_without_a_judge_or_when_the_judge_cannot_read_or_answers_wrong(tmp_path, monkeypatch):
    assert compare_one(None)["rows"][0]["class"] == "FALSE_GREEN"
    def broken(name, hosted):
        raise mg.MergerError("no workflow at that sha")
    row = compare_one(broken)["rows"][0]
    assert row["class"] == "FALSE_GREEN" and row["abort_check"].startswith("unknown (MergerError")
    assert compare_one(lambda n, h: {"aborted": "yes"})["rows"][0]["class"] == "FALSE_GREEN"
    assert compare_one(lambda n, h: {"aborted": True})["rows"][0]["class"] == "FALSE_GREEN"   # an abort that names no run proves nothing
    assert compare_one(lambda n, h: {"aborted": False, "why": "x"})["rows"][0]["abort_check"] == "fresh (x)"


def test_compare_never_asks_the_judge_about_a_green_or_a_red_that_is_not_in_a_compared_class(tmp_path, monkeypatch):
    asked = []
    def spy(name, hosted):
        asked.append(name)
        return {"aborted": True, "runs": [{"check_run_id": 1, "step": "x"}]}
    assert compare_one(spy, concl="success")["rows"][0]["class"] == "AGREE"
    assert compare_one(spy, local="BLIND")["rows"][0]["class"] == "LOCAL_BLIND"
    assert asked == [] or asked == [NAME]   # only the BLIND (local-blind) row is outside COMPARED, and it is never asked either
    assert len(asked) == 0


class AbortGH(FakeGH):
    """FakeGH plus what the abort judge and the recorded row's re-read GET: ids on the check runs, every attempt of a name, the job and its annotations."""
    def __init__(self, pulls, checks, hub, attempts):
        super().__init__(pulls, checks)
        self.hub, self.attempts = hub, attempts

    def __call__(self, path):
        if "/annotations" in path or "/actions/jobs/" in path:
            return self.hub(path)
        if "filter=all" in path:
            return {"check_runs": self.attempts}
        got = super().__call__(path)
        if isinstance(got, dict) and "check_runs" in got:
            got["check_runs"] = [{**r, "id": 11 if r["conclusion"] == "cancelled" else 100 + i} for i, r in enumerate(got["check_runs"])]
        return got


def incident(tmp_path, monkeypatch, workflow=WORKFLOW, **hub):
    """#8514's shape: one context hosted-cancelled in checkout, seen twice by the report (the live row and the recorded false green)."""
    state = tmp_path / "state"
    _, sha = mirror(state / "repo.git", workflow)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    ctx = CTX[0]
    red = [{"id": 11, "conclusion": "cancelled", "completed_at": "2026-10-14T18:50:08Z"}]
    (run_dir / "hosted_compare.json").write_text(json.dumps({"rows": [{"context": ctx, "class": "FALSE_GREEN", "app_id": APP, "hosted_red": red,
                                                                      "hosted_completed_at": red[0]["completed_at"]}]}))
    d = {**decision(1, sha, "PASS", ts="2026-10-14T20:06:37Z"), "run_dir": str(run_dir), "hosted_compare": {"counts": {"FALSE_GREEN": 1}}}
    attempts = [{**check_run(11, ctx, "cancelled"), "app": {"id": APP}}, {**check_run(12, ctx, "success", "2026-10-14T21:00:00Z"), "app": {"id": APP}}]
    gh = AbortGH({1: pull(sha)}, {sha: {ctx: "cancelled"}}, Hub(sha, jname=ctx, **hub), attempts)
    return d, gh


def test_the_incident_counted_twice_is_zero_false_greens_and_one_listed_abort(tmp_path, monkeypatch, capsys):
    tail = [*ASSERT_HUNG[:5], ("Report", "success"), ("Upload test results", "success"), *POST]
    d, gh = incident(tmp_path, monkeypatch, (WITH_ASSERT + ALWAYS).replace("Backend Tests (Python)", CTX[0]), steps=tail)
    rc, rep = run_report(tmp_path, monkeypatch, [d], gh)
    assert rc == 0 and rep["context_counts"]["FALSE_GREEN"] == 0 and rep["context_counts"]["HOSTED_ABORTED"] == 1 and rep["counts"]["FALSE_GREEN"] == 0
    assert rep["recorded_context_false_green"] == 0 and rep["recorded_false_green_as_journalled"] == 1 and rep["recorded_reclassified_hosted_stale"] == []
    assert rep["false_green_breakdown"] == {"pr": 0, "context": 0, "recorded": 0}
    assert rep["hosted_aborted"] == {"count": 1, "list": [{"pr": 1, "head_sha": d["head_sha"], "context": CTX[0], "check_run_id": 11, "step": "Checkout code"}]}
    out = capsys.readouterr().out
    assert "false_green=0 = pr-level 0 + context-level 0 + recorded 0" in out and "hosted_aborted (B27" in out and "phase E READY: false liveness_ok: false:" in out


def test_the_same_incident_with_a_logic_step_cancelled_stays_a_false_green_at_every_level_named_by_level(tmp_path, monkeypatch, capsys):
    steps = [("Set up job", "success"), ("Checkout code", "success"), ("Set up Python", "success"), ("Run unit tests", "cancelled"), *POST]
    d, gh = incident(tmp_path, monkeypatch, WORKFLOW.replace("Backend Tests (Python)", CTX[0]), steps=steps)
    rc, rep = run_report(tmp_path, monkeypatch, [d], gh)
    assert rc == 1 and rep["false_green_breakdown"] == {"pr": 1, "context": 1, "recorded": 1} and rep["hosted_aborted"]["count"] == 0
    assert "false_green=3 = pr-level 1 + context-level 1 + recorded 1" in capsys.readouterr().out


def test_an_unreadable_workflow_keeps_both_false_greens(tmp_path, monkeypatch):
    d, gh = incident(tmp_path, monkeypatch, None)
    rc, rep = run_report(tmp_path, monkeypatch, [d], gh)
    assert rc == 1 and rep["context_counts"]["FALSE_GREEN"] == 1 and rep["recorded_context_false_green"] == 1 and rep["hosted_aborted"]["count"] == 0


def test_a_recorded_row_whose_reds_are_not_all_cancelled_runs_still_listed_is_kept(tmp_path, monkeypatch):
    path, sha = mirror(tmp_path / "repo.git")
    monkeypatch.setattr(hc, "gh_get", AbortGH({}, {}, Hub(sha), [check_run(11, NAME, "cancelled")]))
    j = mg.AbortJudge(REPO, path, {})
    a = type("A", (), {"repo": REPO})
    row = {"context": NAME, "hosted_red": [{"id": 11, "conclusion": "cancelled"}]}
    assert mg.recorded_abort(a, j, sha, row)["aborted"] is True
    assert mg.recorded_abort(a, j, sha, {**row, "hosted_red": [{"id": 11, "conclusion": "failure"}]}) == {}
    assert mg.recorded_abort(a, j, sha, {**row, "hosted_red": None}) == {}
    assert "no longer listed cancelled" in mg.recorded_abort(a, j, sha, {**row, "hosted_red": [{"id": 99, "conclusion": "cancelled"}]})["abort_check"]


def test_one_red_context_that_is_not_an_abort_keeps_the_pr_level_false_green(tmp_path, monkeypatch):
    d, gh = incident(tmp_path, monkeypatch, WORKFLOW.replace("Backend Tests (Python)", CTX[0]))
    gh.checks = {d["head_sha"]: {CTX[0]: "cancelled", CTX[1]: "failure"}}
    rc, rep = run_report(tmp_path, monkeypatch, [d], gh)
    assert rc == 1 and rep["counts"]["FALSE_GREEN"] == 1 and rep["context_counts"]["HOSTED_ABORTED"] == 1 and rep["context_counts"]["FALSE_GREEN"] == 1


@pytest.mark.parametrize("pre", [("failure", "cancelled", "skipped"), ("cancelled", "skipped", "skipped"), ("skipped", "cancelled", "skipped")])
def test_a_pre_checkout_run_step_must_have_succeeded_and_the_hang_must_be_in_the_setup_action(tmp_path, monkeypatch, pre):
    assert_c, checkout_c, setup_c = pre
    steps = [HUNG[0], ("Assert every upstream job succeeded", assert_c), ("Checkout code", checkout_c), ("Set up Python", setup_c), ("Run unit tests", "skipped"), *POST]
    assert judge(tmp_path, monkeypatch, workflow=WITH_ASSERT, steps=steps)(NAME, RED)["aborted"] is False   # failed + later hang; hang in the run step; run step skipped


def test_the_tick_path_reads_the_same_live_data_as_not_green_so_hosted_required_green_stays_false():
    live = {"required_checks": [{"context": NAME, "app_id": APP}], "check_runs": [check_run(11, NAME, "cancelled")], "statuses": []}
    assert "RED" in mg.hosted_side(live) and mg.required_verdicts(live) == {NAME: "RED"}
    assert "hosted_required_green" in mg.GATE and mg.enqueue_step is not None


def test_a_memo_served_row_classifies_exactly_like_the_live_one(tmp_path, monkeypatch):
    """B20's hosted_memo.json keeps a projection of the hosted reads: everything B27 reads of it (the run's id and conclusion) survives it, and
    the reads B27 adds (history, job, annotations, workflow) are made outside the memo."""
    import argparse
    tail = [*ASSERT_HUNG[:5], ("Report", "success"), ("Upload test results", "success"), *POST]
    d, gh = incident(tmp_path, monkeypatch, (WITH_ASSERT + ALWAYS).replace("Backend Tests (Python)", CTX[0]), steps=tail)
    gh.pulls = {1: pull(d["head_sha"], state="closed")}   # closed and old: final, so the memo keeps its reads
    d = {**d, "ts": "2026-10-01T00:00:00Z"}
    state = tmp_path / "state"
    (state / "decisions.jsonl").write_text(json.dumps(d) + "\n")
    monkeypatch.setattr(hc, "gh_get", gh)
    args = argparse.Namespace(repo=REPO, base="main", state_dir=str(state), since=None)
    live_memo = mg.ReadMemo(state / mg.MEMO_FILE)
    _, live = mg.report(args, emit=False, memo=live_memo)
    live_memo.save()
    assert live_memo.misses > 0 and live["hosted_aborted"]["count"] == 1
    gh.paths.clear()
    served_memo = mg.ReadMemo(state / mg.MEMO_FILE)
    _, served = mg.report(args, emit=False, memo=served_memo)
    assert served_memo.hits > 0 and not [p for p in gh.paths if "/pulls/" in p]   # the pull came from the memo
    for key in ("counts", "context_counts", "hosted_aborted", "false_green_breakdown", "recorded_context_false_green", "phase_e_ready"):
        assert served[key] == live[key], key
