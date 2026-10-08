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
BASE = "f" * 40
CTX = tuple(f"ctx-{i:02d}" for i in range(mg.MIN_COMPARED_CONTEXTS))   # a merge counts only when this many contexts were compared
K = len(CTX)


def decision(pr, head, overall, ctx="OK", ts="2026-10-07T08:00:00Z", contexts=None, coverage="full"):
    """``coverage``: one value for every context, a {context: value} map (``full`` for the rest), or None for a line journalled before
    the merger recorded coverage."""
    rec = {"kind": "decision", "ts": ts, "pr": pr, "head_sha": head, "base_sha": BASE, "candidate_sha": "9" * 40, "overall": overall}
    if ctx is not None:
        rec.update(contexts_status="ok", contexts=contexts if contexts is not None else dict.fromkeys(CTX, ctx))
        if coverage is not None:
            rec["coverage"] = {k: (coverage.get(k, "full") if isinstance(coverage, dict) else coverage) for k in rec["contexts"]}
    return rec


class FakeGH:
    def __init__(self, pulls: dict, checks: dict, parents: dict | None = None):
        self.pulls, self.checks, self.paths, self.parents = pulls, checks, [], {M: [BASE], **(parents or {})}
        self.required = CTX

    def __call__(self, path):
        self.paths.append(path)
        if path.startswith(f"repos/{REPO}/pulls/"):
            return self.pulls[int(path.rsplit("/", 1)[1])]
        if path.count("/") == 4 and path.startswith(f"repos/{REPO}/commits/"):
            return {"parents": [{"sha": s} for s in self.parents[path.rsplit("/", 1)[1]]]}
        if path == f"repos/{REPO}/branches/main/protection/required_status_checks":
            return {"checks": [{"context": c, "app_id": 15368} for c in self.required]}
        sha, kind = path.split("/")[4], path.split("/")[5].split("?")[0]
        if kind == "status":
            return {"statuses": []}
        concl = self.checks[sha]   # one conclusion for every context, or {context: conclusion} with "success" for the rest
        by = concl if isinstance(concl, dict) else dict.fromkeys(self.required, concl)
        return {"check_runs": [{"name": c, "status": "completed" if by.get(c, "success") else "in_progress", "conclusion": by.get(c, "success"),
                                "head_sha": sha, "app": {"id": 15368, "slug": "github-actions"}} for c in self.required]}


def pull(head, merged=False, state="open", merge_commit=M, merged_at="2026-10-07T09:00:00Z"):
    return {"merged": merged, "state": "closed" if merged else state, "head": {"sha": head}, "merge_commit_sha": merge_commit if merged else None,
            "merged_at": merged_at if merged else None}


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
    assert rep["counts"]["FALSE_GREEN"] == 1 and rep["context_counts"]["FALSE_GREEN"] == K
    assert rep["hosted_red_merged"] == []   # closed red, never merged: not a hosted merge
    assert f"false_green={K + 1}" in capsys.readouterr().out


def test_every_class_on_its_own_fixture(tmp_path, monkeypatch):
    gh = FakeGH({2: pull(B, merged=True), 3: pull(C), 4: pull(D), 5: pull(E, merged=True)},
                {B: "failure", C: "success", D: None, A: "failure", E: "success", M: "success"})
    recs = [decision(2, B, "PASS"),              # merged: judged on its queue commit (green), whatever a stale red on the head says
            decision(3, C, "FAIL", ctx="FAIL"),  # local red, hosted green
            decision(4, D, "PASS"),              # hosted still running
            decision(5, A, "FAIL", ctx="FAIL"),  # merged later at E: this older head was red on GitHub too
            decision(5, E, "BLOCKED", ctx="BLOCKED")]   # merged, but nothing compared locally: not evidence for phase E
    rc, rep = run_report(tmp_path, monkeypatch, recs, gh)
    assert [r["class"] for r in rep["rows"]] == ["AGREE", "FALSE_RED", "PENDING", "AGREE", "BLIND"]
    assert rc == 0 and rep["window"]["merged_prs"] == 2 and rep["window"]["distinct_prs"] == 4 and rep["window"]["compared_merges"] == 1
    assert rep["context_counts"] == {"AGREE": 2 * K, "FALSE_GREEN": 0, "FALSE_RED": K, "LOCAL_BLIND": K, "HOSTED_PENDING": K}
    assert rep["rows"][0]["hosted_sha"] == M and rep["rows"][2]["hosted_sha"] == D   # a merged candidate is judged where the queue judged it


def test_a_merged_head_is_compared_per_context_with_the_queue_commit_not_the_head(tmp_path, monkeypatch):
    gh = FakeGH({2: pull(B, merged=True)}, {B: "success", M: "failure"})
    rc, rep = run_report(tmp_path, monkeypatch, [decision(2, B, "BLOCKED")], gh)
    assert rc == 1 and rep["context_counts"]["FALSE_GREEN"] == K and rep["rows"][0]["class"] == "BLIND"
    assert rep["hosted_red_merged"] == [{"pr": 2, "merge_commit_sha": M, "red": list(CTX)}]


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


def test_a_merged_candidate_whose_queue_commit_has_not_reported_is_pending_never_green(tmp_path, monkeypatch):
    # the queue merges an entry once a later entry of its group passes (HEADGREEN): merging is no verdict
    gh = FakeGH({2: pull(B, merged=True)}, {B: "failure", M: None})
    rc, rep = run_report(tmp_path, monkeypatch, [decision(2, B, "FAIL", ctx="FAIL")], gh)
    assert (rep["rows"][0]["class"], rep["rows"][0]["github"], rep["hosted_red_merged"]) == ("PENDING", "PENDING", [])
    assert rep["context_counts"]["HOSTED_PENDING"] == K and rep["window"]["compared_merges"] == 0 and rc == 0


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
    row = rep["rows"][0]
    assert row["hosted_sha"] == B and row["github"] == "RED" and rep["context_counts"]["FALSE_GREEN"] == K and rc == 1
    assert rep["window"]["compared_merges"] == 0   # GitHub merged another candidate (same head, another base)


@pytest.mark.parametrize("case", ["state-bound-elsewhere", "decision-of-another-repo", "unreadable-line", "merged-without-merge-sha",
                                  "merged-without-merged-at", "bad-since", "ts-with-newline"])
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
    elif case == "merged-without-merged-at":
        gh.pulls[1], gh.checks[M] = {**pull(A, merged=True), "merged_at": None}, "success"
    elif case == "bad-since":
        extra = ["--since", "2026-10-07Z"]
    elif case == "ts-with-newline":
        recs = [{**recs[0], "ts": "2026-10-07T08:00:00Z\n"}]
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
    recs = [decision(1, A, "BLOCKED", ts="2026-09-01T00:00:00Z"), {"kind": "skipped", "why": "lease", "ts": "2026-09-01T06:00:00Z"},
            decision(1, A, "BLOCKED", ts="2026-09-14T23:59:59Z")]
    rc, rep = run_report(tmp_path, monkeypatch, recs, gh)
    assert rep["window"]["days"] == 13.999 and rep["window"]["longest_silence_h"] == 330.0 and rc == 0
    assert rep["window"]["last_line_age_h"] > 24   # the silence since the last line, measured against the clock


def test_a_merge_commit_with_the_base_among_two_parents_is_not_the_decided_candidate(tmp_path, monkeypatch):
    gh = FakeGH({2: pull(B, merged=True)}, {B: "failure", M: "success"}, parents={M: [BASE, B]})
    rc, rep = run_report(tmp_path, monkeypatch, [decision(2, B, "BLOCKED")], gh)
    assert rep["rows"][0]["hosted_sha"] == B and rep["context_counts"]["FALSE_GREEN"] == K and rc == 1


@pytest.mark.parametrize("counts", [{"FALSE_GREEN": "1"}, {"FALSE_GREEN": True}, {"FALSE_GREEN": False}, {"FALSE_GREEN": -1},
                                    {"FALSE_GREEN": 1.5}, {"FALSE_GREEN": 0.0}, {"FALSE_GREEN": None}, {"FALSE_GREEN": ""},
                                    {"FALSE_GREEN": [1]}, {"FALSE_GREEN": {}}, {"AGREE": 3}, [], "x"])
def test_a_recorded_false_green_that_is_not_a_count_is_refused(tmp_path, monkeypatch, counts):
    d = {**decision(1, A, "BLOCKED"), "hosted_compare": {"counts": counts}}
    rc, rep = run_report(tmp_path, monkeypatch, [d], FakeGH({1: pull(A)}, {A: "success"}))
    assert rc == 2 and rep is None


def test_a_comparison_that_failed_at_tick_time_recorded_no_false_green(tmp_path, monkeypatch):
    d = {**decision(1, A, "BLOCKED"), "hosted_compare": {"error": "gh api down"}}
    rc, rep = run_report(tmp_path, monkeypatch, [d], FakeGH({1: pull(A)}, {A: "success"}))
    assert rc == 0 and rep["recorded_context_false_green"] == 0


def test_errors_and_skips_are_counted_and_only_decisions_measure_the_gap(tmp_path, monkeypatch, capsys):
    recs = [decision(1, A, "BLOCKED", ts="2026-10-01T00:00:00Z"), {"kind": "error", "error": "x", "ts": "2026-10-01T06:00:00Z"},
            {"kind": "skipped", "why": "lease", "ts": "2026-10-01T12:00:00Z"}, {"kind": "skipped", "why": "lease", "ts": "2026-10-01T18:00:00Z"},
            {"kind": "skipped", "why": "node", "ts": "2026-10-01T23:00:00Z"}, decision(1, A, "BLOCKED", ts="2026-10-02T00:00:00Z")]
    rc, rep = run_report(tmp_path, monkeypatch, recs, FakeGH({1: pull(A)}, {A: "success"}))
    w = rep["window"]
    assert (w["errors"], w["skipped"], w["longest_decision_gap_h"], w["longest_silence_h"]) == (1, {"lease": 2, "node": 1}, 24.0, 6.0)
    assert "errors=1" in capsys.readouterr().out and rc == 0


def test_the_report_names_the_code_each_decision_was_written_by(tmp_path, monkeypatch):
    recs = [{**decision(1, A, "BLOCKED"), "code_sha": "c" * 40}, decision(1, A, "BLOCKED", ts="2026-10-07T09:00:00Z")]
    rc, rep = run_report(tmp_path, monkeypatch, recs, FakeGH({1: pull(A)}, {A: "success"}))
    assert [r["code_sha"] for r in rep["rows"]] == ["c" * 40, None] and rep["window"]["code_shas"] == ["c" * 40] and rc == 0


def stamp(day: float, seconds: int = 0) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(calendar.timegm((2026, 10, 1, 0, 0, 0)) + int(day * 86400) + seconds))


def merged_world(n_prs, span_days=0.0, contexts=None):
    """n merged PRs, each decided and merged at the same moment, the first and the last span_days apart (whole seconds)."""
    pulls, checks, recs = {}, {M: "success"}, []
    for i in range(n_prs):
        head, at = f"{i + 1:040x}", stamp(0, round(i * span_days * 86400 / max(n_prs - 1, 1)))
        pulls[i + 1], checks[head] = pull(head, merged=True, merged_at=at), "success"
        recs.append(decision(i + 1, head, "BLOCKED", ts=at, contexts=contexts))
    return recs, FakeGH(pulls, checks)


# lead's ruling 2026-10-07: READY needs >= 50 compared merges AND >= 14 days between the first and the last AND 0 FALSE_GREEN
@pytest.mark.parametrize("n_prs,span_days,ready", [(50, 14.0, True), (49, 14.0, False), (50, 14 - 1 / 86400, False), (50, 0.0, False),
                                                   (2, 14.0, False)])
def test_phase_e_readiness_needs_fifty_compared_merges_and_fourteen_days_between_them(tmp_path, monkeypatch, capsys, n_prs, span_days,
                                                                                      ready):
    recs, gh = merged_world(n_prs, span_days)
    rc, rep = run_report(tmp_path, monkeypatch, recs, gh)
    assert rep["window"]["compared_merges"] == n_prs and rep["phase_e_ready"] is ready and rc == 0
    assert ("phase E READY" if ready else "phase E NOT READY") in capsys.readouterr().out


def test_the_journal_order_does_not_change_readiness(tmp_path, monkeypatch):
    recs, gh = merged_world(50, 14.0)
    rc, rep = run_report(tmp_path, monkeypatch, recs[::-1], gh)
    assert rep["window"]["compared_days"] == 14.0 and rep["phase_e_ready"] is True and rc == 0


def test_one_merge_decided_twice_fourteen_days_apart_is_one_merge_and_no_span(tmp_path, monkeypatch):
    gh = FakeGH({1: pull(A, merged=True, merged_at=stamp(14))}, {A: "success", M: "success"})
    recs = [decision(1, A, "BLOCKED", ts=stamp(0)), decision(1, A, "BLOCKED", ts=stamp(14))]
    rc, rep = run_report(tmp_path, monkeypatch, recs, gh)
    assert (rep["window"]["compared_merges"], rep["window"]["compared_days"], rep["phase_e_ready"]) == (1, 0.0, False) and rc == 0


@pytest.mark.parametrize("blind", [K, 1])
def test_merges_compared_on_fewer_contexts_than_phase_b_are_not_evidence(tmp_path, monkeypatch, blind):
    contexts = {c: ("BLOCKED" if i < blind else "OK") for i, c in enumerate(CTX)}
    recs, gh = merged_world(50, contexts=contexts)
    rc, rep = run_report(tmp_path, monkeypatch, recs, gh)
    assert rep["window"]["merged_prs"] == 50 and rep["window"]["compared_merges"] == 0 and rep["phase_e_ready"] is False and rc == 0


def test_fourteen_days_of_decisions_without_a_compared_merge_are_not_ready(tmp_path, monkeypatch):
    recs = [decision(1, A, "BLOCKED", ts="2026-10-01T00:00:00Z"), decision(1, A, "BLOCKED", ts="2026-10-20T00:00:00Z")]
    rc, rep = run_report(tmp_path, monkeypatch, recs, FakeGH({1: pull(A)}, {A: "success"}))
    assert rep["window"]["days"] >= 14 and rep["window"]["compared_merges"] == 0 and rep["phase_e_ready"] is False and rc == 0


@pytest.mark.parametrize("source", ["recorded", "context-now", "decision"])
def test_any_one_false_green_keeps_fifty_compared_merges_not_ready(tmp_path, monkeypatch, source):
    recs, gh = merged_world(50, 14.0)   # ready on counts and days: only the false green stands in the way
    if source == "recorded":
        recs[7] = {**recs[7], "hosted_compare": {"counts": {"FALSE_GREEN": 1}}}
    else:   # an open PR whose head GitHub has red: the local gate said OK on its contexts (and, for "decision", PASS overall)
        gh.pulls[99], gh.checks[A] = pull(A), "failure"
        recs.append(decision(99, A, "PASS" if source == "decision" else "BLOCKED"))
    rc, rep = run_report(tmp_path, monkeypatch, recs, gh)
    assert rep["window"]["compared_merges"] == 50 and rep["phase_e_ready"] is False and rc == 1


def test_the_report_names_the_longest_tick_and_where_the_time_went(tmp_path, monkeypatch, capsys):
    gh = FakeGH({1: pull(A), 2: pull(B), 3: pull(C)}, {A: "success", B: "success", C: "success"})
    recs = [{**decision(1, A, "BLOCKED"), "elapsed_s": 100, "durations": {"ctx.a": 600.0, "ctx.b": 650}},
            {**decision(2, B, "BLOCKED"), "elapsed_s": 900.5, "durations": {"ctx.a": 40.0, "ctx.b": None, "ctx.c": "slow"}},
            {**decision(3, C, "BLOCKED"), "elapsed_s": 300.04, "durations": ["ctx.a", 9999]},
            {**decision(3, C, "BLOCKED"), "elapsed_s": "x"}, {**decision(3, C, "BLOCKED"), "elapsed_s": True},
            {**decision(3, C, "BLOCKED"), "elapsed_s": -1}]
    rc, rep = run_report(tmp_path, monkeypatch, recs, gh)
    assert rep["window"]["ticks"] == {"timed": 3, "longest_s": 900.5, "longest_pr": 2, "median_s": 300.0,
                                      "check_max_s": {"ctx.b": 650, "ctx.a": 600.0}} and rc == 0
    assert list(rep["window"]["ticks"]["check_max_s"]) == ["ctx.b", "ctx.a"]
    assert "longest 900.5s (#2), median 300.0s; slowest checks: ctx.b=650s, ctx.a=600.0s" in capsys.readouterr().out


def test_decisions_without_provenance_are_counted_never_refused(tmp_path, monkeypatch, capsys):
    odd = ["not-a-sha", ["c" * 40], {"sha": "c" * 40}, 123, True, "C" * 40]
    recs = [{**decision(1, A, "BLOCKED"), "code_sha": "c" * 40}, decision(1, A, "BLOCKED", ts="2026-10-07T09:00:00Z")]
    recs += [{**decision(1, A, "BLOCKED", ts=f"2026-10-07T1{i}:00:00Z"), "code_sha": v} for i, v in enumerate(odd)]
    rc, rep = run_report(tmp_path, monkeypatch, recs, FakeGH({1: pull(A)}, {A: "success"}))
    assert rc == 0 and rep["window"]["decisions_without_code_sha"] == 1 + len(odd) and rep["window"]["code_shas"] == ["c" * 40]
    assert f"{1 + len(odd)} decision(s) without a valid code_sha" in capsys.readouterr().out


def test_a_line_dated_in_the_future_is_flagged_and_never_ages_the_window_negative(tmp_path, monkeypatch, capsys):
    recs = [decision(1, A, "BLOCKED"), {"kind": "skipped", "why": "lease", "ts": "2099-01-01T00:00:00Z"}]
    rc, rep = run_report(tmp_path, monkeypatch, recs, FakeGH({1: pull(A)}, {A: "success"}))
    assert rc == 0 and rep["window"]["future_lines"] == 1 and rep["window"]["last_line_age_h"] == 0.0
    assert "1 line(s) dated in the future" in capsys.readouterr().out



@pytest.mark.parametrize("local,ready", [("FAIL", True), ("OK", False)])
def test_github_merging_a_red_required_check_is_flagged_apart_and_only_a_local_false_green_on_it_blocks(tmp_path, monkeypatch, capsys,
                                                                                                       local, ready):
    recs, gh = merged_world(50, 14.0)
    red_mc = "2" * 40   # #8026's shape: its own queue commit red, merged because a later entry of the group went green
    gh.pulls[7] = {**gh.pulls[7], "merge_commit_sha": red_mc}
    gh.parents[red_mc], gh.checks[red_mc] = [BASE], "failure"
    recs[6] = {**recs[6], "overall": local if local == "FAIL" else "BLOCKED", "contexts": dict.fromkeys(CTX, local)}
    rc, rep = run_report(tmp_path, monkeypatch, recs, gh)
    row = rep["rows"][6]
    assert (row["class"], row["github"], row["hosted_sha"]) == ("AGREE" if ready else "BLIND", "RED", red_mc)
    assert rep["hosted_red_merged"] == [{"pr": 7, "merge_commit_sha": red_mc, "red": list(CTX)}] and rep["counts"]["FALSE_GREEN"] == 0 and rep["context_counts"]["FALSE_GREEN"] == (0 if ready else K)
    assert rep["window"]["compared_merges"] == 50 and rep["phase_e_ready"] is ready and rc == (0 if ready else 1)
    out = capsys.readouterr().out
    assert "hosted_red_merged=1" in out and f"hosted_red_merged: #7 merged at {red_mc[:12]} with required red: ctx-00, ctx-01" in out



def test_a_pr_merged_red_on_another_base_than_the_decided_one_is_still_listed_as_a_hosted_red_merge(tmp_path, monkeypatch):
    # #8026's exact shape: decided on an older base, so judged on its green head; the queue built it on a newer main, red, and merged it
    red_mc, newer_main = "2" * 40, "3" * 40
    gh = FakeGH({2: pull(B, merged=True, merge_commit=red_mc)}, {B: "success", red_mc: "failure"}, parents={red_mc: [newer_main]})
    rc, rep = run_report(tmp_path, monkeypatch, [decision(2, B, "FAIL", ctx="FAIL")], gh)
    row = rep["rows"][0]
    assert (row["hosted_sha"], row["github"], row["class"], row["compared_merge"]) == (B, "GREEN", "FALSE_RED", False)
    assert rep["hosted_red_merged"] == [{"pr": 2, "merge_commit_sha": red_mc, "red": list(CTX)}] and rc == 0


def test_a_pr_merged_at_a_later_head_without_a_merge_commit_sha_is_refused(tmp_path, monkeypatch, capsys):
    gh = FakeGH({2: {**pull(B, merged=True), "merge_commit_sha": None}}, {A: "success"})
    rc, rep = run_report(tmp_path, monkeypatch, [decision(2, A, "FAIL", ctx="FAIL")], gh)   # an older head: judged on itself
    assert rc == 2 and rep is None and "#2 is merged but carries no merge commit sha" in capsys.readouterr().err


@pytest.mark.parametrize("mixed,github,red", [({"ctx-03": "failure", "ctx-05": None}, "RED", ["ctx-03"]),
                                              ({"ctx-05": None}, "PENDING", []),
                                              ({"ctx-03": "failure", "ctx-07": "timed_out"}, "RED", ["ctx-03", "ctx-07"])])
def test_one_red_or_pending_required_context_decides_a_merge_commit_and_only_the_red_ones_are_listed(tmp_path, monkeypatch, mixed, github,
                                                                                                       red):
    gh = FakeGH({2: pull(B, merged=True)}, {B: "success", M: mixed})
    rc, rep = run_report(tmp_path, monkeypatch, [decision(2, B, "BLOCKED")], gh)
    assert rep["rows"][0]["github"] == github
    assert rep["hosted_red_merged"] == ([{"pr": 2, "merge_commit_sha": M, "red": red}] if red else [])


def test_every_red_merge_is_listed_once_however_many_decisions_its_pr_had(tmp_path, monkeypatch, capsys):
    red1, red3 = "2" * 40, "4" * 40
    gh = FakeGH({1: pull(A, merged=True, merge_commit=red1), 2: pull(B, merged=True), 3: pull(C, merged=True, merge_commit=red3)},
                {A: "success", B: "success", C: "success", M: "success", red1: "failure", red3: {"ctx-00": "failure"}},
                parents={red1: [BASE], red3: [BASE]})
    recs = [decision(1, A, "BLOCKED"), decision(2, B, "BLOCKED"), decision(1, A, "BLOCKED", ts="2026-10-07T09:00:00Z"),
            decision(3, C, "BLOCKED")]
    rc, rep = run_report(tmp_path, monkeypatch, recs, gh)
    assert rep["hosted_red_merged"] == [{"pr": 1, "merge_commit_sha": red1, "red": list(CTX)}, {"pr": 3, "merge_commit_sha": red3, "red": ["ctx-00"]}]
    out = capsys.readouterr().out
    assert out.count("hosted_red_merged: #") == 2 and "hosted_red_merged=2" in out


@pytest.mark.parametrize("late,counted", [(None, 0), ("success", 1), ("failure", 1)])
def test_a_merge_with_a_hosted_context_still_pending_is_not_a_compared_merge(tmp_path, monkeypatch, late, counted):
    required = (*CTX, "ctx-late")   # K contexts agree on the queue commit and one more is required: pending, it holds the merge out
    gh = FakeGH({2: pull(B, merged=True)}, {B: "success", M: {"ctx-late": late}})
    gh.required = required
    rc, rep = run_report(tmp_path, monkeypatch, [decision(2, B, "BLOCKED", contexts=dict.fromkeys(required, "OK"))], gh)
    assert rep["rows"][0]["github"] == {None: "PENDING", "success": "GREEN", "failure": "RED"}[late]
    assert rep["rows"][0]["compared_contexts"] == (K if late is None else K + 1)   # the per-context count was never the hole
    assert rep["window"]["compared_merges"] == counted and rep["rows"][0]["compared_merge"] is bool(counted)


def test_the_phase_e_line_counts_enqueued_and_would_enqueue_apart_and_neither_is_a_decision(tmp_path, monkeypatch, capsys):
    t = "2026-10-08T01:00:00Z"
    kinds = [("enqueued", True), ("would_enqueue", True), ("would_enqueue", True), ("would_enqueue", False), ("enqueue_refused", False),
             ("enqueue_error", True)]
    recs = [decision(1, A, "BLOCKED", ts=t)] + [{"kind": k, "ts": t, "pr": 1, "head_sha": A, "ok": ok} for k, ok in kinds]
    rc, rep = run_report(tmp_path, monkeypatch, recs, FakeGH({1: pull(A)}, {A: "success"}))
    assert rep["window"]["enqueue"] == {"enqueued": 1, "enqueue_refused": 1, "enqueue_error": 1, "would_enqueue": 2}   # only every-true counts
    assert rep["window"]["decisions"] == 1 and rc == 0
    (line,) = [x for x in capsys.readouterr().out.splitlines() if x.startswith("phase E")]
    assert line.endswith("; enqueued=1 would_enqueue=2 enqueue_refused=1 enqueue_error=1")


def test_a_journal_older_than_the_enqueue_path_reports_zero_enqueues(tmp_path, monkeypatch):
    rc, rep = run_report(tmp_path, monkeypatch, [decision(1, A, "BLOCKED")], FakeGH({1: pull(A)}, {A: "success"}))
    assert rep["window"]["enqueue"] == {"enqueued": 0, "enqueue_refused": 0, "enqueue_error": 0, "would_enqueue": 0} and rc == 0


# ------------------------------------------------------------------ coverage: only a full context counts toward the >= 12 (B3)
def _merged_once(tmp_path, monkeypatch, n_ctx, coverage, blind=()):
    """One decision of a PR GitHub merged at the decided candidate: n_ctx contexts, all OK and hosted green, ``blind`` of them BLOCKED."""
    gh = FakeGH({1: pull(A, merged=True)}, {A: "success", M: "success"})
    gh.required = tuple(f"ctx-{i:02d}" for i in range(n_ctx))
    contexts = {c: ("BLOCKED" if c in blind else "OK") for c in gh.required}
    return run_report(tmp_path, monkeypatch, [decision(1, A, "PASS", contexts=contexts, coverage=coverage)], gh)


def test_eleven_full_and_one_named_partial_make_a_compared_merge(tmp_path, monkeypatch, capsys):
    # innocence: the real matrix's best case (14 - 2 CodeQL - E2E partial = 11 full) must be able to count, E2E named
    rc, rep = _merged_once(tmp_path, monkeypatch, 12, {"ctx-00": "partial"})
    row, w = rep["rows"][0], rep["window"]
    assert rc == 0 and (row["compared_contexts"], row["compared_partial"], row["compared_merge"]) == (11, ["ctx-00"], True)
    assert (w["compared_merges"], w["compared_merges_full_only"], w["compared_merges_with_partial"], w["compared_merges_partial_contexts"]) == (1, 0, 1, ["ctx-00"])
    out = capsys.readouterr().out
    assert "compared_merges=1 (full_only=0, with_partial=1) compared_partial=1 compared_unrecorded=0 " in out
    assert w["compared_partial"] == 1 and w["partial_contexts"] == ["ctx-00"] and "of the contexts compared, 1 were partial ['ctx-00']" in out
    assert "compared_merges=1 (full_only=0, with_partial=1: ['ctx-00'])" in out and ">= 12 contexts were compared, >= 11 of them full and at most 1 partial" in out


@pytest.mark.parametrize("n_ctx,coverage,blind,why", [
    (12, {"ctx-00": "partial", "ctx-01": "partial"}, (), "12 compared, 2 partial"),
    (12, {"ctx-00": "partial"}, ("ctx-01",), "11 compared: 10 full + 1 partial"),
    (12, "full", ("ctx-00",), "11 compared, all full"),
    (13, {"ctx-00": "partial", "ctx-01": "partial"}, (), "13 compared: 11 full + 2 partial"),
    (12, {"ctx-00": "whatever"}, (), "11 full + 1 unrecorded"),
])
def test_a_merge_short_of_the_ruled_threshold_is_not_a_compared_merge(tmp_path, monkeypatch, n_ctx, coverage, blind, why):
    rc, rep = _merged_once(tmp_path, monkeypatch, n_ctx, coverage, blind)
    assert rc == 0 and rep["rows"][0]["compared_merge"] is False and rep["window"]["compared_merges"] == 0, why
    assert rep["context_counts"]["FALSE_GREEN"] == 0


def test_twelve_full_contexts_are_a_compared_merge_with_no_partial(tmp_path, monkeypatch, capsys):
    rc, rep = _merged_once(tmp_path, monkeypatch, 12, "full")
    assert rc == 0 and rep["window"]["compared_merges"] == 1 and rep["window"]["compared_merges_full_only"] == 1
    assert "compared_merges=1 (full_only=1, with_partial=0) " in capsys.readouterr().out


def test_twelve_full_contexts_make_a_compared_merge_and_a_thirteenth_partial_one_does_not_spoil_it(tmp_path, monkeypatch):
    gh = FakeGH({1: pull(A, merged=True)}, {A: "success", M: "success"})
    rc, rep = run_report(tmp_path, monkeypatch, [decision(1, A, "PASS")], gh)
    assert rc == 0 and (rep["rows"][0]["compared_contexts"], rep["rows"][0]["compared_merge"], rep["window"]["compared_merges"]) == (K, True, 1)
    gh = FakeGH({1: pull(A, merged=True)}, {A: "success", M: "success"})
    gh.required = (*CTX, "E2E")
    rc, rep = run_report(tmp_path, monkeypatch, [decision(1, A, "PASS", contexts=dict.fromkeys(gh.required, "OK"), coverage={"E2E": "partial"})], gh)
    assert rc == 0 and (rep["rows"][0]["compared_contexts"], rep["rows"][0]["compared_partial"], rep["window"]["compared_merges"]) == (K, ["E2E"], 1)


def test_a_line_journalled_before_coverage_was_recorded_counts_no_context_as_full(tmp_path, monkeypatch, capsys):
    gh = FakeGH({1: pull(A, merged=True)}, {A: "success", M: "success"})
    rc, rep = run_report(tmp_path, monkeypatch, [decision(1, A, "PASS", coverage=None)], gh)
    row = rep["rows"][0]
    assert rc == 0 and (row["compared_contexts"], len(row["compared_unrecorded"]), row["compared_merge"]) == (0, K, False)
    assert rep["window"]["compared_unrecorded"] == K and f"compared_unrecorded={K}" in capsys.readouterr().out


def test_a_partial_false_green_still_blocks_ready(tmp_path, monkeypatch):
    gh = FakeGH({1: pull(A, merged=True)}, {A: "success", M: {CTX[0]: "failure"}})
    rc, rep = run_report(tmp_path, monkeypatch, [decision(1, A, "PASS", coverage={CTX[0]: "partial"})], gh)
    assert rc == 1 and rep["context_counts"]["FALSE_GREEN"] == 1 and rep["phase_e_ready"] is False
