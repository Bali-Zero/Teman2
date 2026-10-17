"""policy.matrix_parity: a PR that changes a step of a workflow the matrix executes must carry its matrix row — guilt, innocence, parse failures.

The fixtures are the REAL workflows and matrix of this tree, mutated into the shape of #8646 (a step added to guard-conformance.yml with no
row in contexts_matrix.yaml): the same drift as the real commit, with no dependency on a deep git history."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from . import fixture_repo as fr
from .fixture_repo import runner

pytestmark = pytest.mark.usefixtures("fake_env")

GUARD = ".github/workflows/guard-conformance.yml"
MATRIX = runner.MATRIX_REL
ZSH = "harness/fable-gate zsh preflight regression"
real_matrix = yaml.safe_load((fr.REAL_REPO / MATRIX).read_text())
WORKFLOWS = sorted({c["workflow_file"] for c in real_matrix["contexts"] if c["mapping"] == "executed"})


def dump(doc: dict) -> str:
    return yaml.safe_dump(doc, sort_keys=False)


def matrix_without_zsh_row() -> str:
    doc = yaml.safe_load((fr.REAL_REPO / MATRIX).read_text())
    hits = 0
    for c in doc["contexts"]:
        steps = (c.get("local") or {}).get("steps")
        if steps:
            kept = [s for s in steps if s.get("workflow_step") != ZSH]
            hits += len(steps) - len(kept)
            c["local"]["steps"] = kept
    assert hits == 1, "the real matrix no longer carries the zsh row this fixture removes"
    return dump(doc)


def guard_with_extra_step(name: str = "brand new step") -> str:
    doc = yaml.safe_load((fr.REAL_REPO / GUARD).read_text())
    jobs = [j for j in doc["jobs"].values() if any(s.get("name") == ZSH for s in j["steps"])]
    assert len(jobs) == 1
    jobs[0]["steps"].append({"name": name, "run": "echo hi"})
    return dump(doc)


def real_files() -> dict:
    return {f: (fr.REAL_REPO / f).read_text() for f in [MATRIX, *WORKFLOWS, *runner.TRUSTED_CLASSIFIER_FILES]}


def build(tmp_path: Path, base_over: dict | None = None, cand_over: dict | None = None, cand_delete: tuple = ()) -> dict:
    """A repo of two commits: BASE = the real files (+ base_over), CANDIDATE = BASE + cand_over (- cand_delete)."""
    root = tmp_path / "r"
    repo = root / "wt"
    repo.mkdir(parents=True)
    fr.git(repo, "init", "-q", "-b", "main")
    fr.write(repo, {**real_files(), **(base_over or {})})
    fr.git(repo, "add", "-A")
    fr.git(repo, "commit", "-q", "-m", "base")
    base = fr.git(repo, "rev-parse", "HEAD")
    fr.write(repo, cand_over or {"docs/unrelated.md": "x\n"})
    for rel in cand_delete:
        (repo / rel).unlink()
    fr.git(repo, "add", "-A")
    fr.git(repo, "commit", "-q", "-m", "candidate")
    return {"repo": repo, "base": base, "candidate": fr.git(repo, "rev-parse", "HEAD"), "scratch": tmp_path / "scratch"}


def verdict(fx: dict) -> dict:
    return runner.matrix_parity_check(fx["repo"], fx["base"], fx["candidate"], fx["scratch"])


def test_the_real_tree_is_in_parity(tmp_path):
    """The tree this test runs in: if a workflow step or a matrix row was added without the other, this names it."""
    fx = build(tmp_path)   # the real files in a temp repo: a gate runs on a `git archive` copy of the tree, which has no .git
    problems = runner.matrix_accounting(fx["repo"], fx["base"], tmp_path / "scratch")
    assert problems == [], problems


# ------------------------------------------------------------------------------ guilt: the drift of #8646
def test_a_candidate_that_drops_the_zsh_row_while_the_workflow_keeps_the_step_fails_naming_it(tmp_path):
    fx = build(tmp_path, cand_over={MATRIX: matrix_without_zsh_row()})
    v = verdict(fx)
    assert v["kind"] == "record" and v["status"] == "FAIL"
    assert "harness/fable-gate zsh preflight regression" in v["reason"] and "not mapped by the matrix" in v["reason"]
    assert "ctx.guard-guilt-innocence" not in v["reason"] and "Every guard proves guilt AND innocence" in v["reason"]


def test_a_candidate_that_adds_a_workflow_step_without_its_row_fails_naming_the_step(tmp_path):
    v = verdict(build(tmp_path, cand_over={GUARD: guard_with_extra_step("brand new step")}))
    assert v["status"] == "FAIL" and "brand new step" in v["reason"]


def test_a_candidate_that_renames_a_step_the_matrix_names_fails(tmp_path):
    text = (fr.REAL_REPO / GUARD).read_text().replace(f"name: {ZSH}", "name: harness/fable-gate zsh preflight (renamed)")
    assert text != (fr.REAL_REPO / GUARD).read_text()
    v = verdict(build(tmp_path, cand_over={GUARD: text}))
    assert v["status"] == "FAIL" and "zsh preflight" in v["reason"]


def test_the_candidate_that_carries_workflow_step_and_row_together_passes(tmp_path):
    wf = yaml.safe_load(guard_with_extra_step("brand new step"))
    mx = yaml.safe_load((fr.REAL_REPO / MATRIX).read_text())
    ctx = next(c for c in mx["contexts"] if c.get("workflow_file") == GUARD and c["mapping"] == "executed" and any(s.get("workflow_step") == ZSH for s in c["local"]["steps"]))
    ctx["local"]["steps"].append({"workflow_step": "brand new step", "not_applicable": "fixture: merge_group runs it hosted"})
    v = verdict(build(tmp_path, cand_over={GUARD: dump(wf), MATRIX: dump(mx)}))
    assert wf and v["status"] == "PASS", v


# ------------------------------------------------------------------------------ innocence
def test_an_unrelated_candidate_on_an_in_parity_base_passes(tmp_path):
    assert verdict(build(tmp_path))["status"] == "PASS"


def test_an_unrelated_candidate_on_a_drifted_base_is_not_blocked_and_the_inherited_drift_is_named(tmp_path):
    fx = build(tmp_path, base_over={MATRIX: matrix_without_zsh_row()})
    v = verdict(fx)
    assert v["status"] == "NOT_APPLICABLE" and "already present at BASE" in v["reason"] and "zsh preflight" in v["reason"]


def test_the_cure_for_a_drifted_base_passes(tmp_path):
    fx = build(tmp_path, base_over={MATRIX: matrix_without_zsh_row()}, cand_over={MATRIX: (fr.REAL_REPO / MATRIX).read_text()})
    assert verdict(fx)["status"] == "PASS"


def test_a_candidate_that_adds_a_second_drift_on_a_drifted_base_still_fails(tmp_path):
    fx = build(tmp_path, base_over={MATRIX: matrix_without_zsh_row()}, cand_over={GUARD: guard_with_extra_step("second drift")})
    v = verdict(fx)
    assert v["status"] == "FAIL" and "second drift" in v["reason"]


def test_a_workflow_with_no_executed_context_changes_nothing(tmp_path):
    only = sorted(f.name for f in (fr.REAL_REPO / ".github/workflows").iterdir() if f".github/workflows/{f.name}" not in WORKFLOWS)
    assert only, "every workflow is executed? then this fixture proves nothing"
    wf = f".github/workflows/{only[0]}"
    assert verdict(build(tmp_path, cand_over={wf: "name: not required\non: push\njobs: {}\n"}))["status"] == "PASS"


# ------------------------------------------------------------------------------ the candidate's files cannot be parsed
@pytest.mark.parametrize("bad,needle", [("contexts: [", "contexts_matrix.yaml"), ("contexts: []\n", "non-empty list")])
def test_a_broken_candidate_matrix_fails_naming_why(tmp_path, bad, needle):
    v = verdict(build(tmp_path, cand_over={MATRIX: bad}))
    assert v["status"] == "FAIL" and needle in v["reason"]


def test_a_candidate_that_deletes_the_matrix_fails(tmp_path):
    v = verdict(build(tmp_path, cand_over={"docs/x.md": "x\n"}, cand_delete=(MATRIX,)))
    assert v["status"] == "FAIL" and "absent" in v["reason"]


def test_a_broken_candidate_workflow_fails_naming_it(tmp_path):
    v = verdict(build(tmp_path, cand_over={GUARD: "jobs: [unclosed\n"}))
    assert v["status"] == "FAIL" and f"workflow {GUARD} is unreadable" in v["reason"]


def test_a_matrix_already_broken_at_base_is_not_the_candidates_fault(tmp_path):
    v = verdict(build(tmp_path, base_over={MATRIX: "contexts: [\n"}))
    assert v["status"] == "NOT_APPLICABLE" and "already present at BASE" in v["reason"]


def test_our_own_crash_is_blocked_never_a_fail(tmp_path, monkeypatch):
    fx = build(tmp_path)
    monkeypatch.setattr(runner, "matrix_accounting", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    v = verdict(fx)
    assert v["status"] == "BLOCKED" and "boom" in v["reason"]


# ------------------------------------------------------------------------------ in the plan
def plan_check(tmp_path: Path, **kw) -> dict:
    fx = build(tmp_path, **kw)
    run = tmp_path / "run"
    runner.main(["plan", "--run-dir", str(run), "--worktree", str(fx["repo"]), "--base", fx["base"], "--python", fr.PY, "--builder-seat", "b",
                 "--isolation", "none", "--contexts-file", str(fr.contexts_file(fx, tmp_path / "c.yaml"))])
    return json.loads((run / "state" / "plan.json").read_text())["checks"]["policy.matrix_parity"]


def test_plan_records_the_check_and_the_drifting_candidate_fails_in_it(tmp_path):
    c = plan_check(tmp_path, cand_over={MATRIX: matrix_without_zsh_row()})
    assert c["kind"] == "record" and c["status"] == "FAIL" and "zsh preflight" in c["reason"]


def test_plan_passes_an_innocent_candidate(tmp_path):
    assert plan_check(tmp_path)["status"] == "PASS"


def test_a_step_added_to_an_upstream_job_of_a_service_context_fails(tmp_path):
    """Backend Tests chains backend-static -> backend-shard: the matrix carries steps for both jobs, so a drift in the upstream one counts."""
    wf = ".github/workflows/tests.yml"
    doc = yaml.safe_load((fr.REAL_REPO / wf).read_text())
    doc["jobs"]["backend-static"]["steps"].append({"name": "upstream drift", "run": "echo hi"})
    v = verdict(build(tmp_path, cand_over={wf: dump(doc)}))
    assert v["status"] == "FAIL" and "upstream drift" in v["reason"] and "backend-static" in v["reason"]


def test_a_candidate_that_renames_the_job_a_context_names_fails(tmp_path):
    doc = yaml.safe_load((fr.REAL_REPO / GUARD).read_text())
    job_id = next(k for k, j in doc["jobs"].items() if any(s.get("name") == ZSH for s in j["steps"]))
    doc["jobs"] = {("renamed-" + k if k == job_id else k): v for k, v in doc["jobs"].items()}
    v = verdict(build(tmp_path, cand_over={GUARD: dump(doc)}))
    assert v["status"] == "FAIL" and f"job {job_id!r} is absent from {GUARD}" in v["reason"]
