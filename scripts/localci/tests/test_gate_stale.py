"""B12b guilt + innocence: a hosted RED of a gate-reading context that was its reader's PENDING read, given before the gate verdict the
local run read, is HOSTED_STALE (``stale_why: gate_posted_after_hosted``), only on that evidence; every other red stays a disagreement."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

from . import stale_fixture as sf

_MODULE = Path(__file__).resolve().parent.parent / "merger.py"
_spec = importlib.util.spec_from_file_location("merger_gate_stale_under_test", _MODULE)
mg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mg)
hc = mg.hc

REPO, HEAD = "o/r", "a" * 40
PEND = "::error::harness_gate_read: PENDING"
CTX_GATE, CTX_JOB, CTX_NAMED = "Gate Reading Check", "Job Gate Check", "Harness floor recompute"   # the last one reads NO gate here
MATRIX_YAML = f"""contexts:
  - name: "{CTX_GATE}"
    local: {{check: ctx.gate, steps: [{{workflow_step: Kill switch}}, {{workflow_step: Read the gate, side: host, pending_when: "{PEND}"}},
                                     {{workflow_step: Bites}}]}}
  - name: "{CTX_JOB}"
    local: {{check: ctx.job, jobs: [{{job_id: j, steps: [{{workflow_step: Read, side: host, pending_when: "{PEND}"}}]}}]}}
  - name: "{CTX_NAMED}"
    local: {{check: ctx.harness-floor, steps: [{{workflow_step: Read the gate, side: host}}]}}
"""
HOSTED_AT = "2026-10-10T01:00:00Z"   # the pull_request run failed on the PENDING read
POSTED = "2026-10-10T01:10:00Z"      # the session posts harness/fable-gate
PLAN = "2026-10-10T01:20:00Z"        # the local run is planned: its reader reads the post
LATER = "2026-10-10T01:30:00Z"       # after the plan: a re-post, or the hosted re-run
EXIT1 = "Process completed with exit code 1."
GEAR = "Gear >= 2 — read the real gate verdict"   # the real matrix's reader step of CTX_NAMED
READS = {CTX_GATE: {"Read the gate": [0]}, CTX_JOB: {"Read": [0]}, CTX_NAMED: {GEAR: [0]}}   # what the plan froze: each reader read a success
GATE_STEPS = [("Set up job", "success"), ("Kill switch", "success"), ("Read the gate", "failure"), ("Bites", "skipped"),
              ("Post Run actions/checkout@v4", "success"), ("Complete job", "success")]   # the runner's own steps run after a failure


def job(rid=11, steps=GATE_STEPS) -> dict:
    """What GET actions/jobs/{id} answers for the job behind check run ``rid``."""
    return {"id": rid, "check_run_url": f"https://api.github.com/repos/{REPO}/check-runs/{rid}",
            "steps": [{"name": n, "status": "completed", "conclusion": c, "number": i} for i, (n, c) in enumerate(steps, 1)]}


def reader_line(state) -> str:
    """The BASE harness_gate_read.py's own ::error:: stderr line for a head whose harness/fable-gate state is ``state``."""
    spec = importlib.util.spec_from_file_location("b12b_harness_gate_read", Path(__file__).resolve().parents[2] / "ci" / "harness_gate_read.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.resolve_real_head_sha = lambda **kw: (HEAD, "fixture")
    mod.read_fable_gate_state = lambda **kw: (state, None)
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        assert mod.main(["--event-name", "pull_request", "--repo", REPO, "--pr-head-sha", HEAD]) == 1
    (line,) = [ln for ln in err.getvalue().splitlines() if ln.startswith("::error::")]
    return line


def annotation(line: str) -> dict:
    """What GitHub makes of a workflow command ``::error::msg``: a failure annotation whose message is ``msg``."""
    assert line.startswith("::error::")
    return {"annotation_level": "failure", "message": line.removeprefix("::error::"), "title": "", "path": ".github"}


PENDING_ANNS = [annotation(reader_line(None)), {"annotation_level": "failure", "message": EXIT1, "title": "", "path": ".github"}]


def make_mirror(path: Path, matrix: str = MATRIX_YAML) -> str:
    (path / "scripts" / "localci").mkdir(parents=True)
    sf.git(path, "init", "-q", "-b", "main")
    (path / sf.MATRIX).write_text(matrix)
    sf.git(path, "add", "-A")
    sf.git(path, "commit", "-qm", "c0", when=sf.T0)
    return sf.git(path, "rev-parse", "HEAD")


class GH:
    """Read-only GETs: the annotations and the job of a check run (each a document, or an exception to raise) and every attempt of the
    head's check runs."""
    def __init__(self):
        self.ann: dict = {11: PENDING_ANNS}
        self.jobs: dict = {11: job()}
        self.all_runs: list = []
        self.paths: list = []
        self.extra: dict = {}

    def __call__(self, path):
        self.paths.append(path)
        if "/annotations" in path:
            got = self.ann[int(path.split("/")[4])]
            if isinstance(got, Exception):
                raise got
            return got
        if "/actions/jobs/" in path:
            got = self.jobs[int(path.rsplit("/", 1)[1])]
            if isinstance(got, Exception):
                raise got
            return got
        if "filter=all" in path:
            return {"check_runs": self.all_runs}
        for prefix, doc in self.extra.items():
            if path.startswith(prefix):
                return doc
        raise AssertionError(f"unexpected GET {path}")


@pytest.fixture
def m(tmp_path, monkeypatch):
    repo = tmp_path / "mirror"
    base = make_mirror(repo)
    gh = GH()
    monkeypatch.setattr(hc, "gh_get", gh)
    return {"repo": repo, "base": base, "gh": gh, "matrix": mg.StaleJudge(repo, base)}


def run(rid=11, ctx=CTX_GATE, conclusion="failure", at=HOSTED_AT):
    return {"id": rid, "name": ctx, "head_sha": HEAD, "status": "completed", "conclusion": conclusion, "completed_at": at,
            "app": {"id": 15368, "slug": "github-actions"}}


def gate_status(at, state):
    return {"context": mg.GATE_CONTEXT, "state": state, "updated_at": at}


def judged(m, *, ctx=CTX_GATE, conclusion="failure", at=HOSTED_AT, posted=((POSTED, "success"),), plan_at=PLAN, reads=READS, runs=None,
           statuses=None, local="OK", stale_judge=None):
    gate = mg.GateJudge(REPO, m["matrix"], plan_at, reads)
    status = {"candidate_sha": "c" * 40, "contexts": {"status": "ok", "results": {ctx: {"verdict": local, "coverage": "full"}}}}
    rep = hc.compare(status, [{"context": ctx, "app_id": 15368}], [run(ctx=ctx, conclusion=conclusion, at=at)] if runs is None else runs,
                     [gate_status(*x) for x in posted] + list(statuses or []), stale_judge=stale_judge, gate_judge=gate)
    (row,) = rep["rows"]
    return rep, row


ANN_PATH = f"repos/{REPO}/check-runs/11/annotations?per_page=100&page=1"
JOB_PATH = f"repos/{REPO}/actions/jobs/11"


# ------------------------------------------------------------------ guilt: the race, and only the race
@pytest.mark.parametrize("with_b10", [False, True], ids=["gate-judge-alone", "beside-the-b10-judge"])
def test_a_pre_post_pending_red_beside_a_local_green_is_hosted_stale(m, with_b10):
    rep, row = judged(m, stale_judge=m["matrix"] if with_b10 else None)
    assert (row["class"], row["class_before"], row["stale_check"], row["gate_check"], row["stale_why"]) == (
        "HOSTED_STALE", "FALSE_GREEN", "stale", "stale", "gate_posted_after_hosted")
    assert (row["hosted_completed_at"], row["gate_posted_at"], row["plan_at"]) == (HOSTED_AT, POSTED, PLAN)
    assert rep["counts"]["FALSE_GREEN"] == 0 and rep["counts"]["HOSTED_STALE"] == 1 and rep["coverage"]["compared_full"] == 0
    assert hc.exit_code(rep) == 0 and m["gh"].paths == [ANN_PATH, JOB_PATH]   # bounded, read-only GETs of the red run's annotations and job


def test_a_pre_post_pending_red_beside_a_local_red_is_no_agreement_either(m):
    assert judged(m, local="FAIL")[1]["class_before"] == "AGREE" and judged(m, local="FAIL")[1]["class"] == "HOSTED_STALE"


def test_a_gate_reading_step_inside_a_job_makes_the_context_gate_reading(m):
    m["gh"].jobs[11] = job(steps=[("Set up job", "success"), ("Read", "failure"), ("Complete job", "success")])
    assert judged(m, ctx=CTX_JOB)[1]["class"] == "HOSTED_STALE"


def test_warnings_and_notices_beside_the_pending_read_are_no_other_failure(m):
    m["gh"].ann[11] = PENDING_ANNS + [{"annotation_level": "warning", "message": "Node 16 is deprecated"},
                                      {"annotation_level": "notice", "message": "harness_gate_read: real head sha"}]
    assert judged(m)[1]["class"] == "HOSTED_STALE"


@pytest.mark.parametrize("anns", [
    PENDING_ANNS + [{"annotation_level": "failure", "message": "Hot-zone list may only grow below floor 3"}],
    PENDING_ANNS + [{"annotation_level": "failure", "message": EXIT1}],                  # a second step failed too
    [{"annotation_level": "failure", "message": EXIT1}],                                  # red, but not on the PENDING read
    [annotation(reader_line("failure")), {"annotation_level": "failure", "message": EXIT1}],   # a posted REWORK/BLOCK verdict
    PENDING_ANNS + [{"annotation_level": None, "message": "an annotation of no known level"}],
    []], ids=["extra-failure", "two-failed-steps", "exit-code-only", "posted-failure-verdict", "unknown-level", "no-annotation"])
def test_a_red_that_is_not_the_pending_read_alone_stays_a_false_green(m, anns):
    m["gh"].ann[11] = anns
    _, row = judged(m)
    assert row["class"] == "FALSE_GREEN" and row["gate_check"].startswith("fresh (check run 11 failed on more than the PENDING read")
    assert "class_before" not in row and "stale_why" not in row


@pytest.mark.parametrize("at", [POSTED, "2026-10-10T01:15:00Z", LATER], ids=["same-second", "after-the-post", "after-the-plan"])
def test_a_red_completed_at_or_after_the_post_stays_a_false_green_and_no_annotation_is_read(m, at):
    _, row = judged(m, at=at)
    assert row["class"] == "FALSE_GREEN" and row["gate_check"].startswith(f"fresh (hosted completed at {at}, not before")
    assert m["gh"].paths == []


def test_two_red_runs_are_judged_on_the_newest_and_each_must_be_the_pending_read(m):
    runs = [run(11, at="2026-10-10T00:40:00Z"), run(12, at=HOSTED_AT)]
    m["gh"].ann[12], m["gh"].jobs[12] = PENDING_ANNS, job(12)
    assert judged(m, runs=runs)[1]["class"] == "HOSTED_STALE"
    m["gh"].ann[12] = PENDING_ANNS + [{"annotation_level": "failure", "message": "boom"}]
    assert judged(m, runs=runs)[1]["class"] == "FALSE_GREEN"


def test_a_red_commit_status_of_the_same_name_is_no_check_run_and_keeps_the_false_green(m):
    _, row = judged(m, statuses=[{"context": CTX_GATE, "state": "failure", "updated_at": HOSTED_AT}])
    assert row["class"] == "FALSE_GREEN" and "no check run" in row["gate_check"]


# ------------------------------------------------------------------ innocence: what the ground never touches
def test_a_hosted_green_is_unaffected_and_nothing_is_read(m):
    _, row = judged(m, conclusion="success")
    assert row["class"] == "AGREE" and not [k for k in row if k.startswith(("stale", "gate_", "class_before"))] and m["gh"].paths == []


@pytest.mark.parametrize("ctx", [CTX_NAMED, "Not In The Base Matrix"])
def test_a_context_that_reads_no_gate_is_unaffected_whatever_its_name(m, ctx):
    _, row = judged(m, ctx=ctx)
    assert row["class"] == "FALSE_GREEN" and not [k for k in row if k.startswith(("stale", "gate_"))] and m["gh"].paths == []


def test_without_a_gate_judge_the_rows_are_what_they_were(m):
    status = {"candidate_sha": "c" * 40, "contexts": {"status": "ok", "results": {CTX_GATE: {"verdict": "OK", "coverage": "full"}}}}
    (row,) = hc.compare(status, [{"context": CTX_GATE, "app_id": 15368}], [run()], [gate_status(POSTED, "success")])["rows"]
    assert row["class"] == "FALSE_GREEN" and "gate_check" not in row


# ------------------------------------------------------------------ unknown: the class is kept and the row says why
def test_an_annotation_read_failure_keeps_the_class_and_says_unknown(m):
    m["gh"].ann[11] = hc.CompareError("gh api check-runs/11/annotations failed (rc=1)")
    _, row = judged(m)
    assert row["class"] == "FALSE_GREEN" and row["stale_check"].startswith("unknown (CompareError")
    assert row["gate_check"] == row["stale_check"] and "class_before" not in row


@pytest.mark.parametrize("plan_at", [None, "yesterday", "2026-10-10 01:20:00"])
def test_a_plan_time_that_cannot_be_read_keeps_the_class(m, plan_at):
    _, row = judged(m, plan_at=plan_at)
    assert row["class"] == "FALSE_GREEN" and row["stale_check"].startswith("unknown (") and "plan time" in row["stale_check"]


def test_the_plan_time_is_the_plans_created_at_and_nothing_else(tmp_path):
    (tmp_path / "state").mkdir()
    assert mg.plan_time(tmp_path) is None and mg.plan_time(None) is None
    (tmp_path / "state" / "plan.json").write_text("{not json")
    assert mg.plan_time(tmp_path) is None
    (tmp_path / "state" / "plan.json").write_text(json.dumps({"created_at": "2026-10-10 01:20"}))
    assert mg.plan_time(tmp_path) is None
    (tmp_path / "state" / "plan.json").write_text(json.dumps({"created_at": PLAN, "created_epoch": 1.0}))
    assert mg.plan_time(tmp_path) == PLAN


def test_an_unreadable_base_matrix_keeps_the_class(tmp_path, monkeypatch):
    monkeypatch.setattr(hc, "gh_get", GH())
    gate = mg.GateJudge(REPO, mg.StaleJudge(tmp_path / "nowhere.git", "f" * 40), PLAN, READS)
    status = {"candidate_sha": "c" * 40, "contexts": {"status": "ok", "results": {CTX_GATE: {"verdict": "OK", "coverage": "full"}}}}
    (row,) = hc.compare(status, [{"context": CTX_GATE, "app_id": 15368}], [run()], [gate_status(POSTED, "success")], gate_judge=gate)["rows"]
    assert row["class"] == "FALSE_GREEN" and row["stale_check"].startswith("unknown (")


# ------------------------------------------------------------------ which post the local run read
@pytest.mark.parametrize("posted,klass,why", [
    (((LATER, "success"),), "FALSE_GREEN", f"fresh (no {mg.GATE_CONTEXT} status dated at or before the plan time {PLAN})"),
    (((POSTED, "success"), (LATER, "failure")), "HOSTED_STALE", None),        # the newest at or before the plan is the one read
    ((("2026-10-10T00:50:00Z", "success"), (LATER, "success")), "FALSE_GREEN", "fresh (hosted completed at"),   # that one predates the red
    ((), "FALSE_GREEN", "fresh (no ")], ids=["only-after-the-plan", "one-before-one-after", "before-the-hosted-run", "never-posted"])
def test_the_gate_post_is_the_newest_at_or_before_the_plan_time(m, posted, klass, why):
    _, row = judged(m, posted=posted)
    assert row["class"] == klass and (why is None and row["gate_posted_at"] == POSTED or why is not None and row["gate_check"].startswith(why))


def test_a_gate_status_without_a_readable_time_keeps_the_class(m):
    _, row = judged(m, posted=(), statuses=[{"context": mg.GATE_CONTEXT, "state": "success", "updated_at": None}])
    assert row["class"] == "FALSE_GREEN" and row["stale_check"].startswith("unknown (")


# ------------------------------------------------------------------ the real reader, the real matrix
@pytest.mark.parametrize("state,klass", [(None, "HOSTED_STALE"), ("failure", "FALSE_GREEN"), ("pending", "FALSE_GREEN")])
def test_the_base_readers_own_line_as_github_annotates_it_is_what_the_real_matrix_reads(tmp_path, monkeypatch, state, klass):
    real = (Path(__file__).resolve().parents[1] / "contexts_matrix.yaml").read_text()
    repo = tmp_path / "real"
    base = make_mirror(repo, real)
    matrix = mg.StaleJudge(repo, base)
    (p,) = matrix.pending_of(CTX_NAMED)
    assert (p["step"], p["line"]) == (GEAR, PEND) and "Bites contract — parse this PR's evidence pack" in p["later"]
    assert matrix.pending_of("Backend Tests (Python)") == []
    gh = GH()
    gh.ann[11] = [annotation(reader_line(state)), {"annotation_level": "failure", "message": EXIT1}]
    gh.jobs[11] = job(steps=[("Set up job", "success"), ("Kill switch", "success"), (GEAR, "failure"),
                             ("Bites contract — parse this PR's evidence pack", "skipped"), ("Complete job", "success")])
    monkeypatch.setattr(hc, "gh_get", gh)
    status = {"candidate_sha": "c" * 40, "contexts": {"status": "ok", "results": {CTX_NAMED: {"verdict": "OK", "coverage": "full"}}}}
    (row,) = hc.compare(status, [{"context": CTX_NAMED, "app_id": 15368}], [run(ctx=CTX_NAMED)], [gate_status(POSTED, "success")],
                        gate_judge=mg.GateJudge(REPO, matrix, PLAN, READS))["rows"]
    assert row["class"] == klass


# ------------------------------------------------------------------ the tick journals it
def test_the_tick_journals_the_gate_stale_row_and_the_run_dir_keeps_its_evidence(m, tmp_path, monkeypatch):
    monkeypatch.setattr(hc, "fetch_live", lambda *a: {"required_checks": [{"context": CTX_GATE, "app_id": 15368}], "check_runs": [run()],
                                                      "statuses": [gate_status(POSTED, "success")]})
    run_dir = tmp_path / "run"
    (run_dir / "state").mkdir(parents=True)
    status = {"candidate_sha": "c" * 40, "contexts": {"status": "ok", "results": {CTX_GATE: {"verdict": "OK", "coverage": "full"}}}}
    summary, live = mg.hosted_summary(REPO, "main", status, HEAD, run_dir, m["matrix"], gate=mg.GateJudge(REPO, m["matrix"], PLAN, READS))
    assert summary["counts"]["HOSTED_STALE"] == 1 and summary["counts"]["FALSE_GREEN"] == 0 and summary["exit"] == 0 and live is not None
    assert summary["stale"] == [{"context": CTX_GATE, "class_before": "FALSE_GREEN", "hosted_completed_at": HOSTED_AT, "hosted_main": None,
                                 "main_moved_paths": [], "main_moved_count": 0, "stale_why": "gate_posted_after_hosted",
                                 "gate_posted_at": POSTED, "plan_at": PLAN}]
    (row,) = json.loads((run_dir / "hosted_compare.json").read_text())["rows"]
    assert row["class"] == "HOSTED_STALE" and row["stale_why"] == "gate_posted_after_hosted"
    assert row["hosted_red"] == [{"id": 11, "conclusion": "failure", "completed_at": HOSTED_AT}]   # the reds the report finds again by id
    assert mg.recorded_false_green({"hosted_compare": summary}) == 0


# ------------------------------------------------------------------ the report re-judges what the tick recorded
A = HEAD


def plan_doc(rc=0) -> dict:
    """A plan.json as the runner writes it for CTX_GATE: the reader step's answer frozen under ``precomputed``."""
    return {"created_at": PLAN, "checks": {"ctx.gate": {"kind": "contained_jobs", "context": CTX_GATE, "jobs": [{"job_id": "j", "steps": [
        {"name": "Kill switch"}, {"name": "Read the gate", "side": {"where": "host"}, "precomputed": {"rc": rc, "reason": "host, at plan"}}]}]}}}


def report_world(tmp_path, monkeypatch, *, anns=None, rerun=True, recorded_at=HOSTED_AT, plan=True, recorded_red=None):
    """pr1, open: the tick recorded one FALSE_GREEN on CTX_GATE beside the pre-post PENDING red (run 11); the session then re-ran the job
    (run 12, green, after the post) unless ``rerun`` is False."""
    state = tmp_path / "state"
    state.mkdir()
    base = make_mirror(state / "repo.git")
    run_dir = tmp_path / "run"
    (run_dir / "state").mkdir(parents=True)
    if plan:
        (run_dir / "state" / "plan.json").write_text(json.dumps(plan_doc()))
    red = [{"id": 11, "conclusion": "failure", "completed_at": recorded_at}] if recorded_red is None else recorded_red
    row = {"context": CTX_GATE, "class": "FALSE_GREEN", "app_id": 15368, **({"hosted_completed_at": recorded_at} if recorded_at else {}),
           **({"hosted_red": red} if red != "absent" else {})}
    (run_dir / "hosted_compare.json").write_text(json.dumps({"rows": [row]}))
    d = {"kind": "decision", "ts": "2026-10-10T01:25:00Z", "pr": 1, "head_sha": A, "base_sha": base, "candidate_sha": "9" * 40, "overall": "PASS",
         "contexts_status": "ok", "contexts": {CTX_GATE: "OK"}, "coverage": {CTX_GATE: "full"}, "run_dir": str(run_dir),
         "hosted_compare": {"counts": {"FALSE_GREEN": 1}}}
    (state / "decisions.jsonl").write_text(json.dumps(d) + "\n")
    gh = GH()
    if anns is not None:
        gh.ann[11] = anns
    latest = [run(12, conclusion="success", at=LATER)] if rerun else [run()]
    gh.all_runs = [run(), *latest] if rerun else [run()]
    gh.extra = {f"repos/{REPO}/pulls/1": {"merged": False, "state": "open", "head": {"sha": A}, "merge_commit_sha": None, "merged_at": None},
                f"repos/{REPO}/branches/main/protection/required_status_checks": {"checks": [{"context": CTX_GATE, "app_id": 15368}]},
                f"repos/{REPO}/commits/{A}/check-runs?": {"check_runs": latest},
                f"repos/{REPO}/commits/{A}/status?": {"statuses": [gate_status(POSTED, "success")]}}
    monkeypatch.setattr(hc, "gh_get", gh)
    rc = mg.main(["report", "--repo", REPO, "--state-dir", str(state)])
    return rc, json.loads((state / "report.json").read_text())


def test_the_report_reclassifies_a_recorded_false_green_of_this_shape_after_the_rerun(tmp_path, monkeypatch, capsys):
    rc, rep = report_world(tmp_path, monkeypatch)
    assert rc == 0 and rep["recorded_false_green_as_journalled"] == 1 and rep["recorded_context_false_green"] == 0
    assert rep["recorded_reclassified_hosted_stale"] == [{"pr": 1, "context": CTX_GATE, "head_sha": A, "stale_why": "gate_posted_after_hosted",
                                                          "hosted_completed_at": HOSTED_AT, "gate_posted_at": POSTED, "plan_at": PLAN}]
    assert rep["recorded_kept_false_green"] == [] and rep["context_counts"]["AGREE"] == 1   # the re-run green agrees now
    assert (f"reclassified HOSTED_STALE=1: [pr1 {CTX_GATE}: hosted ran {HOSTED_AT}, before the gate post at {POSTED} the local run read "
            "(gate_posted_after_hosted)], kept=0: []") in capsys.readouterr().out


def test_the_reports_own_comparison_judges_a_pre_post_red_not_yet_rerun(tmp_path, monkeypatch):
    rc, rep = report_world(tmp_path, monkeypatch, rerun=False)
    assert rep["context_counts"]["HOSTED_STALE"] == 1 and rep["context_counts"]["FALSE_GREEN"] == 0
    assert len(rep["recorded_reclassified_hosted_stale"]) == 1 and rep["recorded_context_false_green"] == 0
    assert rc == 1 and rep["counts"]["FALSE_GREEN"] == 1   # the PR-level class is not judged for staleness (B10's residual, unchanged)


@pytest.mark.parametrize("kw,gate_why", [
    ({"anns": PENDING_ANNS + [{"annotation_level": "failure", "message": "boom"}]}, "fresh (check run 11 failed on more than the PENDING read"),
    ({"recorded_at": None}, "unknown (MergerError: the recorded row journals no hosted_completed_at or no hosted_red"),
    ({"recorded_red": "absent"}, "unknown (MergerError: the recorded row journals no hosted_completed_at or no hosted_red"),
    ({"recorded_red": [{"id": 11, "conclusion": "failure", "completed_at": HOSTED_AT}, {"id": 13, "conclusion": "failure",
                                                                                         "completed_at": "2026-10-10T00:50:00Z"}]},
     "unknown (a red Gate Reading Check run the tick recorded is no longer listed red on the head)"),
    ({"recorded_red": [{"id": 11, "conclusion": "failure", "completed_at": HOSTED_AT}, {"id": None, "conclusion": "failure",
                                                                                         "completed_at": HOSTED_AT}]},
     "fresh (a red that is no check run (a commit status)"),
    ({"recorded_at": "2026-10-10T00:59:00Z"}, "unknown (no red Gate Reading Check run completed at the recorded"),
    ({"plan": False}, "unknown (MergerError: the run's plan time"),
    ({"anns": hc.CompareError("annotations unreadable")}, "unknown (CompareError: annotations unreadable")],
    ids=["another-failure", "pre-b10-row", "pre-fix-row", "a-recorded-run-gone", "a-recorded-status", "red-not-found", "no-plan",
         "annotations-unreadable"])
def test_the_report_keeps_a_recorded_false_green_of_another_shape_and_says_why(tmp_path, monkeypatch, capsys, kw, gate_why):
    rc, rep = report_world(tmp_path, monkeypatch, **kw)
    assert rc == 1 and rep["recorded_context_false_green"] == 1 and rep["recorded_reclassified_hosted_stale"] == []
    (k,) = rep["recorded_kept_false_green"]
    assert k["why"] == "the hosted verdict is now GREEN, not the red the tick recorded" and k["gate"].startswith(gate_why)
    assert f"(gate: {gate_why}" in capsys.readouterr().out


def test_the_report_reads_every_attempt_only_for_a_gate_reading_context(tmp_path, monkeypatch):
    report_world(tmp_path, monkeypatch)
    paths = hc.gh_get.paths
    assert sum("filter=all" in p for p in paths) == 1 and all(p.startswith("repos/") for p in paths)
    assert f"check_name={CTX_GATE.replace(' ', '%20')}" in next(p for p in paths if "filter=all" in p)


# ------------------------------------------------------------------ fix round: the local run read a success, and the plan froze it
@pytest.mark.parametrize("state", ["failure", "error", "pending"])
def test_a_posted_verdict_that_is_no_success_beside_a_local_green_stays_a_false_green(m, state):
    _, row = judged(m, posted=((POSTED, state),))
    assert row["class"] == "FALSE_GREEN" and m["gh"].paths == []
    assert row["gate_check"].startswith(f"fresh (the {mg.GATE_CONTEXT} status the local run read ({POSTED}) is {state}, not success")


def test_the_anchor_is_the_newest_post_at_or_before_the_plan_whatever_an_older_one_said(m):
    assert judged(m, posted=(("2026-10-10T01:05:00Z", "success"), (POSTED, "failure")))[1]["class"] == "FALSE_GREEN"
    assert judged(m, posted=(("2026-10-10T01:05:00Z", "failure"), (POSTED, "success")))[1]["class"] == "HOSTED_STALE"


@pytest.mark.parametrize("reads", [{CTX_GATE: {"Read the gate": [1]}}, {CTX_GATE: {"Read the gate": [None]}}, {CTX_GATE: {"Read the gate": [0, 1]}},
                                   {CTX_GATE: {"Read the gate": [False]}}, {CTX_GATE: {"Another step": [0]}}, {}],
                         ids=["rc-1", "no-verdict", "one-answer-red", "a-bool", "another-step", "absent"])
def test_a_success_anchor_whose_frozen_reader_answer_is_not_rc_0_stays_a_false_green(m, reads):
    _, row = judged(m, reads=reads)
    assert row["class"] == "FALSE_GREEN" and row["gate_check"].startswith("fresh (the plan froze") and m["gh"].paths == []


def test_frozen_reads_that_cannot_be_read_keep_the_class_and_say_unknown(m):
    _, row = judged(m, reads=None)
    assert row["class"] == "FALSE_GREEN" and row["stale_check"].startswith("unknown (MergerError: the reader answers the run's plan froze")


def test_frozen_reads_are_the_plans_host_reader_answers_and_nothing_else(tmp_path):
    (tmp_path / "state").mkdir()
    assert mg.frozen_reads(tmp_path) is None and mg.frozen_reads(None) is None
    for bad in ("{not json", json.dumps({"created_at": PLAN}), json.dumps({"checks": {"c": {"context": CTX_GATE, "jobs": [{}]}}})):
        (tmp_path / "state" / "plan.json").write_text(bad)
        assert mg.frozen_reads(tmp_path) is None
    doc = plan_doc()
    doc["checks"]["ctx.gate"]["jobs"][0]["steps"].append({"name": "pip-audit", "side": {"where": "egress"}, "precomputed": {"rc": 0}})
    doc["checks"]["ctx.other"] = {"kind": "record", "status": "NOT_APPLICABLE", "reason": "change_map"}
    (tmp_path / "state" / "plan.json").write_text(json.dumps(doc))
    assert mg.frozen_reads(tmp_path) == {CTX_GATE: {"Read the gate": [0]}}


@pytest.mark.usefixtures("fake_env")
def test_frozen_reads_read_the_runners_own_plan_of_a_host_reader(tmp_path, monkeypatch):
    from . import fixture_repo as fr
    from .test_service_contexts import HOST_BASE, READER, host_ctx, planned_svc
    spec = planned_svc(tmp_path, monkeypatch, fr.CANDIDATE_FILES, host_ctx(["$PY", READER]), {**HOST_BASE, READER: "raise SystemExit(0)\n"})
    run_dir = tmp_path / "b12b-run"
    (run_dir / "state").mkdir(parents=True)
    (run_dir / "state" / "plan.json").write_text(json.dumps({"created_at": PLAN, "checks": {"ctx.svc": spec}}))
    assert mg.frozen_reads(run_dir) == {spec["context"]: {"verdict": [0]}}


# ------------------------------------------------------------------ fix round: the job failed on the reader step alone
@pytest.mark.parametrize("steps", [
    [("Kill switch", "failure"), ("Read the gate", "failure"), ("Bites", "skipped")],
    [("Kill switch", "success"), ("Read the gate", "failure"), ("Bites", "skipped"), ("Complete job", "failure")],
    [("Kill switch", "cancelled"), ("Read the gate", "failure"), ("Bites", "skipped")],
    [("Kill switch", "success"), ("Read the gate", "success"), ("Bites", "failure")]],
    ids=["an-earlier-step-failed", "a-runner-step-failed", "a-step-cancelled", "another-step-is-the-failure"])
def test_a_job_that_failed_on_another_step_stays_a_false_green(m, steps):
    m["gh"].jobs[11] = job(steps=steps)
    _, row = judged(m)
    assert row["class"] == "FALSE_GREEN" and row["gate_check"].startswith("fresh (actions job 11 did not fail on the reader step alone")


def test_a_step_the_matrix_lists_after_the_reader_that_ran_stays_a_false_green(m):
    m["gh"].jobs[11] = job(steps=[("Kill switch", "success"), ("Read the gate", "failure"), ("Bites", "success")])
    _, row = judged(m)
    assert row["class"] == "FALSE_GREEN" and row["gate_check"].endswith("failed ['Read the gate'], ran after it ['Bites'])")


@pytest.mark.parametrize("doc,why", [
    (hc.CompareError("gh api actions/jobs/11 failed (rc=1)"), "unknown (CompareError: gh api actions/jobs/11"),
    ({**job(), "check_run_url": f"https://api.github.com/repos/{REPO}/check-runs/99"}, "unknown (MergerError: actions job 11 does not name check run 11"),
    ({k: v for k, v in job().items() if k != "steps"}, "unknown (MergerError: actions job 11 carries no steps"),
    (job(steps=[("Kill switch", "success"), ("Read the real gate", "failure")]),
     "unknown (MergerError: actions job 11 lists the reader step 'Read the gate' 0 time(s)")],
    ids=["read-fails", "another-check-run", "no-steps", "step-renamed"])
def test_a_job_that_cannot_be_read_or_matched_keeps_the_class_and_says_unknown(m, doc, why):
    m["gh"].jobs[11] = doc
    _, row = judged(m)
    assert row["class"] == "FALSE_GREEN" and row["stale_check"].startswith(why) and "class_before" not in row


@pytest.mark.parametrize("extra,klass", [(47, "HOSTED_STALE"), (48, "FALSE_GREEN")], ids=["49-under-the-cap", "50-at-the-cap"])
def test_an_annotation_list_at_githubs_per_job_cap_proves_nothing(m, extra, klass):
    m["gh"].ann[11] = PENDING_ANNS + [{"annotation_level": "warning", "message": f"w{i}"} for i in range(extra)]
    _, row = judged(m)
    assert row["class"] == klass
    assert klass == "HOSTED_STALE" or row["stale_check"].startswith("unknown (MergerError: check run 11 carries 50 annotations")


# ------------------------------------------------------------------ fix round: the conclusion, and what the row says ran
@pytest.mark.parametrize("conclusion", ["cancelled", "timed_out", "startup_failure"])
def test_a_red_that_is_no_failure_conclusion_stays_a_false_green(m, conclusion):
    _, row = judged(m, conclusion=conclusion)
    assert row["class"] == "FALSE_GREEN" and m["gh"].paths == []
    assert row["gate_check"].startswith(f"fresh (a red concluded ['{conclusion}'], not failure")


def test_without_a_b10_judge_the_rows_stale_check_is_what_the_gate_judge_said(m):
    _, row = judged(m, posted=((POSTED, "failure"),))
    assert row["stale_check"] == row["gate_check"] and row["stale_check"].startswith(f"fresh (the {mg.GATE_CONTEXT} status")


def test_a_b10_stale_row_missing_a_key_is_refused_and_a_b12b_row_needs_only_its_own():
    b10 = {"context": "X", "class_before": "FALSE_GREEN", "hosted_completed_at": HOSTED_AT, "main_moved_paths": [], "main_moved_count": 0}
    with pytest.raises(KeyError):
        mg.stale_entry(b10)
    b12b = {"context": "X", "class_before": "FALSE_GREEN", "hosted_completed_at": HOSTED_AT, "stale_why": "gate_posted_after_hosted",
            "gate_posted_at": POSTED, "plan_at": PLAN}
    assert mg.stale_entry(b12b) == b12b and mg.stale_entry({**b10, "hosted_main": None}) == {**b10, "hosted_main": None}
