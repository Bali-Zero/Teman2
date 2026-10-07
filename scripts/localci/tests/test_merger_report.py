"""Guilt + innocence for `merger.py report`, phase D's instrument: journal decisions beside what GitHub did with each head."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_MODULE = Path(__file__).resolve().parent.parent / "merger.py"
_spec = importlib.util.spec_from_file_location("merger_report_under_test", _MODULE)
mg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mg)

REPO = "o/r"
A, B, C, D, E, M = ("a" * 40, "b" * 40, "c" * 40, "d" * 40, "e" * 40, "1" * 40)


def decision(pr, head, overall, ctx="OK", ts="2026-10-07T08:00:00Z"):
    rec = {"kind": "decision", "ts": ts, "pr": pr, "head_sha": head, "base_sha": "f" * 40, "candidate_sha": "9" * 40, "overall": overall}
    if ctx is not None:
        rec.update(contexts_status="ok", contexts={"ctx-a": ctx})
    return rec


class FakeGH:
    def __init__(self, pulls: dict, checks: dict):
        self.pulls, self.checks, self.paths = pulls, checks, []

    def __call__(self, path):
        self.paths.append(path)
        if path.startswith(f"repos/{REPO}/pulls/"):
            return self.pulls[int(path.rsplit("/", 1)[1])]
        if path == f"repos/{REPO}/branches/main/protection/required_status_checks":
            return {"checks": [{"context": "ctx-a", "app_id": 15368}]}
        sha, kind = path.split("/")[4], path.split("/")[5].split("?")[0]
        if kind == "status":
            return {"statuses": []}
        concl = self.checks[sha]
        return {"check_runs": [{"name": "ctx-a", "status": "completed" if concl else "in_progress", "conclusion": concl, "head_sha": sha,
                                "app": {"id": 15368, "slug": "github-actions"}}]}


def pull(head, merged=False, state="open", merge_commit=M):
    return {"merged": merged, "state": "closed" if merged else state, "head": {"sha": head}, "merge_commit_sha": merge_commit if merged else None}


def run_report(tmp_path, monkeypatch, recs, gh, *extra):
    state = tmp_path / "state"
    state.mkdir(exist_ok=True)
    (state / "decisions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    monkeypatch.setattr(mg.hc, "gh_get", gh)
    rc = mg.main(["report", "--repo", REPO, "--state-dir", str(state), *extra])
    return rc, (json.loads((state / "report.json").read_text()) if (state / "report.json").exists() else None)


def test_a_pass_on_a_head_github_closed_red_is_a_false_green_at_both_levels_and_exits_1(tmp_path, monkeypatch, capsys):
    gh = FakeGH({1: pull(A, state="closed")}, {A: "failure"})
    rc, rep = run_report(tmp_path, monkeypatch, [decision(1, A, "PASS")], gh)
    assert rc == 1 and [r["class"] for r in rep["rows"]] == ["FALSE_GREEN"]
    assert rep["counts"]["FALSE_GREEN"] == 1 and rep["context_counts"]["FALSE_GREEN"] == 1
    assert "false_green=1" in capsys.readouterr().out


def test_every_class_on_its_own_fixture(tmp_path, monkeypatch):
    gh = FakeGH({2: pull(B, merged=True), 3: pull(C), 4: pull(D), 5: pull(E, merged=True)},
                {B: "failure", C: "success", D: None, A: "failure", E: "success", M: "success"})
    recs = [decision(2, B, "PASS"),              # merged at this very head: GitHub let it through, whatever a stale red says
            decision(3, C, "FAIL", ctx="FAIL"),  # local red, hosted green
            decision(4, D, "PASS"),              # hosted still running
            decision(5, A, "FAIL", ctx="FAIL"),  # merged later at E: this older head was red on GitHub too
            decision(5, E, "BLOCKED", ctx="BLOCKED")]
    rc, rep = run_report(tmp_path, monkeypatch, recs, gh)
    assert [r["class"] for r in rep["rows"]] == ["AGREE", "FALSE_RED", "PENDING", "AGREE", "BLIND"]
    assert rc == 0 and rep["window"]["merged_prs"] == 2 and rep["window"]["distinct_prs"] == 4
    assert rep["rows"][0]["hosted_sha"] == M and rep["rows"][2]["hosted_sha"] == D   # a merged head is judged where the queue judged it


def test_a_merged_head_is_compared_per_context_with_the_queue_commit_not_the_head(tmp_path, monkeypatch):
    gh = FakeGH({2: pull(B, merged=True)}, {B: "success", M: "failure"})
    rc, rep = run_report(tmp_path, monkeypatch, [decision(2, B, "BLOCKED")], gh)
    assert rc == 1 and rep["context_counts"]["FALSE_GREEN"] == 1 and rep["rows"][0]["class"] == "BLIND"


def test_conflict_and_error_decisions_are_blind_and_add_no_context_counts(tmp_path, monkeypatch):
    gh = FakeGH({6: pull(A), 7: pull(B)}, {A: "failure", B: "success"})
    rc, rep = run_report(tmp_path, monkeypatch, [decision(6, A, "CONFLICT", ctx=None), decision(7, B, "ERROR", ctx=None)], gh)
    assert [r["class"] for r in rep["rows"]] == ["BLIND", "BLIND"] and sum(rep["context_counts"].values()) == 0 and rc == 0


def test_only_decisions_count_and_since_bounds_the_window(tmp_path, monkeypatch):
    gh = FakeGH({1: pull(A, merged=True)}, {A: "success", M: "success"})
    recs = [{"kind": "skipped", "why": "lease", "ts": "2026-10-07T09:00:00Z"}, decision(1, A, "PASS", ts="2026-10-06T00:00:00Z"),
            decision(1, A, "PASS", ts="2026-10-08T00:00:00Z")]
    rc, rep = run_report(tmp_path, monkeypatch, recs, gh, "--since", "2026-10-07")
    assert rc == 0 and rep["window"]["decisions"] == 1 and rep["window"]["first"] == "2026-10-08T00:00:00Z"


def test_the_report_reads_github_only_through_gets(tmp_path, monkeypatch):
    gh = FakeGH({1: pull(A)}, {A: "success"})
    run_report(tmp_path, monkeypatch, [decision(1, A, "PASS"), decision(1, A, "PASS")], gh)
    assert gh.paths[0] == f"repos/{REPO}/pulls/1" and len([p for p in gh.paths if p.endswith("/pulls/1")]) == 1


def test_an_unusable_github_read_is_refused_never_counted(tmp_path, monkeypatch):
    def down(path):
        raise mg.hc.CompareError("gh api down")
    rc, rep = run_report(tmp_path, monkeypatch, [decision(1, A, "PASS")], down)
    assert rc == 2 and rep is None


@pytest.mark.parametrize("overall,expected", [("PASS", "GREEN"), ("FAIL", "RED"), ("SUBSET_PASS", "BLIND"), ("BLOCKED", "BLIND"),
                                              ("CONFLICT", "BLIND"), ("ERROR", "BLIND"), (None, "BLIND")])
def test_only_pass_is_green_and_only_fail_is_red_for_the_merger(overall, expected):
    assert mg.merger_side(overall) == expected


def test_a_pr_merged_at_the_decided_head_is_green_even_before_its_queue_commit_reports(tmp_path, monkeypatch):
    gh = FakeGH({2: pull(B, merged=True)}, {B: "failure", M: None})
    rc, rep = run_report(tmp_path, monkeypatch, [decision(2, B, "FAIL", ctx="FAIL")], gh)
    assert rep["rows"][0]["github"] == "GREEN" and rep["rows"][0]["class"] == "FALSE_RED" and rc == 0


def test_a_missing_gh_is_refused_not_a_traceback(tmp_path, monkeypatch, capsys):
    def no_gh(path):
        raise FileNotFoundError(2, "No such file or directory", "gh")
    rc, rep = run_report(tmp_path, monkeypatch, [decision(1, A, "PASS")], no_gh)
    assert rc == 2 and rep is None and "refusing" in capsys.readouterr().err
