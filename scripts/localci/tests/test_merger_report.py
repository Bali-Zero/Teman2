"""Guilt + innocence for `merger.py report`, phase D's instrument: journal decisions beside what GitHub did with each head."""
from __future__ import annotations

import calendar
import importlib.util
import json
import time
from pathlib import Path

import pytest

_MODULE = Path(__file__).resolve().parent.parent / "merger.py"
_spec = importlib.util.spec_from_file_location("merger_report_under_test", _MODULE)
mg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mg)

REPO = "o/r"
A, B, C, D, E, M = ("a" * 40, "b" * 40, "c" * 40, "d" * 40, "e" * 40, "1" * 40)


def decision(pr, head, overall, ctx="OK", ts="2026-10-07T08:00:00Z"):
    rec = {"kind": "decision", "ts": ts, "pr": pr, "head_sha": head, "base_sha": BASE, "candidate_sha": "9" * 40, "overall": overall}
    if ctx is not None:
        rec.update(contexts_status="ok", contexts={"ctx-a": ctx})
    return rec


BASE = "f" * 40


class FakeGH:
    def __init__(self, pulls: dict, checks: dict, parents: dict | None = None):
        self.pulls, self.checks, self.paths, self.parents = pulls, checks, [], {M: [BASE], **(parents or {})}

    def __call__(self, path):
        self.paths.append(path)
        if path.startswith(f"repos/{REPO}/pulls/"):
            return self.pulls[int(path.rsplit("/", 1)[1])]
        if path.count("/") == 4 and path.startswith(f"repos/{REPO}/commits/"):
            return {"parents": [{"sha": s} for s in self.parents[path.rsplit("/", 1)[1]]]}
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
    assert rc == 0 and rep["window"]["merged_prs"] == 2 and rep["window"]["distinct_prs"] == 4 and rep["window"]["compared_merges"] == 2
    assert rep["context_counts"] == {"AGREE": 2, "FALSE_GREEN": 0, "FALSE_RED": 1, "LOCAL_BLIND": 1, "HOSTED_PENDING": 1}
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


def test_a_false_green_seen_at_tick_time_is_never_erased_by_a_later_green(tmp_path, monkeypatch, capsys):
    gh = FakeGH({1: pull(A)}, {A: "success"})   # GitHub re-ran the red check green since
    d = {**decision(1, A, "BLOCKED"), "hosted_compare": {"counts": {"FALSE_GREEN": 1, "AGREE": 3}}}
    rc, rep = run_report(tmp_path, monkeypatch, [d], gh)
    assert rc == 1 and rep["recorded_context_false_green"] == 1 and "false_green=1" in capsys.readouterr().out


def test_a_merge_at_another_head_or_without_a_usable_gate_is_not_a_compared_merge(tmp_path, monkeypatch):
    gh = FakeGH({1: pull(B, merged=True), 2: pull(C, merged=True)}, {A: "success", C: "success", M: "success"})
    rc, rep = run_report(tmp_path, monkeypatch, [decision(1, A, "BLOCKED"), {**decision(2, C, "BLOCKED"), "contexts_status": "invalid"}], gh)
    assert rc == 0 and rep["window"]["merged_prs"] == 2 and rep["window"]["compared_merges"] == 0


def test_the_queue_commit_judges_only_a_decision_on_the_base_it_was_built_on(tmp_path, monkeypatch):
    gh = FakeGH({2: pull(B, merged=True)}, {B: "failure", M: "success"}, parents={M: ["7" * 40]})
    rc, rep = run_report(tmp_path, monkeypatch, [decision(2, B, "BLOCKED")], gh)
    assert rep["rows"][0]["hosted_sha"] == B and rep["context_counts"]["FALSE_GREEN"] == 1 and rc == 1


@pytest.mark.parametrize("case", ["state-bound-elsewhere", "decision-of-another-repo", "unreadable-line", "merged-without-merge-sha", "bad-since"])
def test_unusable_inputs_are_refused_never_counted(tmp_path, monkeypatch, case):
    recs, gh, extra = [decision(1, A, "PASS")], FakeGH({1: pull(A)}, {A: "failure"}), []
    state = tmp_path / "state"
    state.mkdir()
    if case == "state-bound-elsewhere":
        (state / "repo").write_text("other/repo\n")
    elif case == "decision-of-another-repo":
        recs = [{**recs[0], "repo": "other/repo"}]
    elif case == "merged-without-merge-sha":
        gh.pulls[1] = {**pull(A, merged=True), "merge_commit_sha": None}
    elif case == "bad-since":
        extra = ["--since", "2026-10-07Z"]
    if case == "unreadable-line":
        (state / "decisions.jsonl").write_text(json.dumps(recs[0]) + "\n" + '{"kind": "decision", "pr": 2, "head_s' + "\n")
        monkeypatch.setattr(mg.hc, "gh_get", gh)
        rc = mg.main(["report", "--repo", REPO, "--state-dir", str(state)])
        assert rc == 2 and not (state / "report.json").exists()
        return
    rc, rep = run_report(tmp_path, monkeypatch, recs, gh, *extra)
    assert rc == 2 and rep is None


def test_days_are_floored_and_the_longest_silence_is_reported(tmp_path, monkeypatch):
    gh = FakeGH({1: pull(A)}, {A: "success"})
    recs = [decision(1, A, "BLOCKED", ts="2026-10-01T00:00:00Z"), {"kind": "skipped", "why": "lease", "ts": "2026-10-01T06:00:00Z"},
            decision(1, A, "BLOCKED", ts="2026-10-14T23:59:59Z")]
    rc, rep = run_report(tmp_path, monkeypatch, recs, gh)
    assert rep["window"]["days"] == 13.999 and rep["window"]["longest_silence_h"] == 330.0 and rc == 0


def test_a_merge_commit_with_the_base_among_two_parents_is_not_the_decided_candidate(tmp_path, monkeypatch):
    gh = FakeGH({2: pull(B, merged=True)}, {B: "failure", M: "success"}, parents={M: [BASE, B]})
    rc, rep = run_report(tmp_path, monkeypatch, [decision(2, B, "BLOCKED")], gh)
    assert rep["rows"][0]["hosted_sha"] == B and rep["context_counts"]["FALSE_GREEN"] == 1 and rc == 1


@pytest.mark.parametrize("recorded", ["1", True, -1, 1.5, [1]])
def test_a_recorded_false_green_that_is_not_a_count_is_refused(tmp_path, monkeypatch, recorded):
    d = {**decision(1, A, "BLOCKED"), "hosted_compare": {"counts": {"FALSE_GREEN": recorded}}}
    rc, rep = run_report(tmp_path, monkeypatch, [d], FakeGH({1: pull(A)}, {A: "success"}))
    assert rc == 2 and rep is None


def test_errors_and_skips_are_counted_and_only_decisions_measure_the_gap(tmp_path, monkeypatch, capsys):
    recs = [decision(1, A, "BLOCKED", ts="2026-10-01T00:00:00Z"), {"kind": "error", "error": "x", "ts": "2026-10-01T06:00:00Z"},
            {"kind": "skipped", "why": "lease", "ts": "2026-10-01T12:00:00Z"}, {"kind": "skipped", "why": "lease", "ts": "2026-10-01T18:00:00Z"},
            {"kind": "skipped", "why": "node", "ts": "2026-10-01T23:00:00Z"}, decision(1, A, "BLOCKED", ts="2026-10-02T00:00:00Z")]
    rc, rep = run_report(tmp_path, monkeypatch, recs, FakeGH({1: pull(A)}, {A: "success"}))
    w = rep["window"]
    assert (w["errors"], w["skipped"], w["longest_decision_gap_h"], w["longest_silence_h"]) == (1, {"lease": 2, "node": 1}, 24.0, 6.0)
    assert "errors=1" in capsys.readouterr().out and rc == 0


def merged_world(n_prs, days_apart=0.0):
    pulls, checks, recs = {}, {M: "success"}, []
    for i in range(n_prs):
        head = f"{i + 1:040x}"
        pulls[i + 1], checks[head] = pull(head, merged=True), "success"
        t = time.gmtime(calendar.timegm((2026, 10, 1, 0, 0, 0)) + int(i * days_apart * 86400))
        recs.append(decision(i + 1, head, "BLOCKED", ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", t)))
    return recs, FakeGH(pulls, checks)


@pytest.mark.parametrize("n_prs,days_apart,ready", [(50, 0.0, True), (49, 0.0, False), (2, 14.0, True), (2, 13.99, False)])
def test_phase_e_readiness_counts_compared_merges_and_days_only_between_them(tmp_path, monkeypatch, capsys, n_prs, days_apart, ready):
    recs, gh = merged_world(n_prs, days_apart)
    rc, rep = run_report(tmp_path, monkeypatch, recs, gh)
    assert rep["window"]["compared_merges"] == n_prs and rep["phase_e_ready"] is ready and rc == 0
    assert ("phase E READY" if ready else "phase E NOT READY") in capsys.readouterr().out


def test_fourteen_days_of_decisions_without_a_compared_merge_are_not_ready(tmp_path, monkeypatch):
    recs = [decision(1, A, "BLOCKED", ts="2026-10-01T00:00:00Z"), decision(1, A, "BLOCKED", ts="2026-10-20T00:00:00Z")]
    rc, rep = run_report(tmp_path, monkeypatch, recs, FakeGH({1: pull(A)}, {A: "success"}))
    assert rep["window"]["days"] >= 14 and rep["window"]["compared_merges"] == 0 and rep["phase_e_ready"] is False and rc == 0


def test_a_single_false_green_keeps_fifty_compared_merges_not_ready(tmp_path, monkeypatch):
    recs, gh = merged_world(50)
    recs[7] = {**recs[7], "hosted_compare": {"counts": {"FALSE_GREEN": 1}}}
    rc, rep = run_report(tmp_path, monkeypatch, recs, gh)
    assert rep["window"]["compared_merges"] == 50 and rep["phase_e_ready"] is False and rc == 1
