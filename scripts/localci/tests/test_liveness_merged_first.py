"""B37: a would_enqueue row GitHub overtook (only ``open`` false, the PR merged at that very head) counts toward liveness."""
from __future__ import annotations

import inspect
import time

import pytest

from .test_liveness import A, B, EXCLUDED, NOW, FakeGH, M, decision, iso, measure, merged, mg, pull, row, run_report, stamped


def gone(head=A, **kw):
    return {**merged(head), **kw}


def test_a_row_failing_on_open_alone_counts_when_github_merged_that_exact_head():
    got = measure([row(false=("open",))], [(1, A)], {1: merged(A)})
    assert (got["mergeable_rows"], got["merged_first"], got["merged_first_unread"]) == (1, 1, 0)
    assert got["coverage_decided"] == 1.0   # the merged-first row is the coverage of that merged head


def test_the_excluded_terms_may_be_false_beside_open_and_a_retry_counts():
    assert measure([row(false=("open", *EXCLUDED), retry=True)], merged_prs={1: merged(A)})["merged_first"] == 1


def test_a_strict_row_is_not_merged_first_even_with_a_merged_pull():
    got = measure([row()], merged_prs={1: merged(A)})
    assert (got["mergeable_rows"], got["merged_first"]) == (1, 0)


@pytest.mark.parametrize("pull_", [
    {"merged": False, "state": "closed", "head": {"sha": A}},   # closed unmerged
    {"merged": True, "head": {"sha": B}},                      # merged at another head
    {"merged": "true", "head": {"sha": A}},                    # not a bool
    {"merged": True},                                          # no head
    {"merged": True, "head": {"sha": "xyz"}},                  # head not a sha
    {"state": "open", "head": {"sha": A}},                     # still open
    "garbage", None, [],
], ids=str)
def test_every_other_pull_fails_closed(pull_):
    got = measure([row(false=("open",))], merged_prs={1: pull_})
    assert (got["mergeable_rows"], got["merged_first"]) == (0, 0)


def test_a_missing_pull_does_not_count_and_is_said():
    got = measure([row(false=("open",)), row(pr=2, false=("open",))], merged_prs={2: merged(A)})
    assert (got["mergeable_rows"], got["merged_first"], got["merged_first_unread"]) == (1, 1, 1)


def test_a_row_without_a_usable_pr_number_is_unread_and_never_raises():
    bad = {**row(false=("open",)), "pr": [1]}
    got = measure([bad, {**row(false=("open",)), "pr": None}], merged_prs={1: merged(A)})
    assert (got["mergeable_rows"], got["merged_first_unread"]) == (0, 2)


@pytest.mark.parametrize("second", [t for t in mg.CRITERION if t not in EXCLUDED and t != "open"])
def test_a_second_false_term_beside_open_does_not_count(second):
    assert measure([row(false=("open", second))], merged_prs={1: merged(A)})["mergeable_rows"] == 0


def test_a_criterion_missing_open_or_not_a_dict_or_another_kind_does_not_count():
    gone_open = row(false=("open",))
    del gone_open["criterion"]["open"]
    rows = [gone_open, {**row(false=("open",)), "criterion": None}, {**row(false=("open",)), "criterion": "x"},
            row(false=("open",), kind="would_merge"), row(false=("open",), kind="enqueue_refused")]
    assert measure(rows, merged_prs={1: merged(A)})["mergeable_rows"] == 0


def test_the_row_head_must_match_not_just_the_pr():
    got = measure([row(head=B, false=("open",))], merged_prs={1: merged(A)})
    assert got["mergeable_rows"] == 0 and got["merged_first_unread"] == 0


def test_ten_merged_first_rows_make_liveness_ok():
    heads = [f"{i + 1:040x}" for i in range(10)]
    rows = [row(pr=i + 1, head=h, false=("open",)) for i, h in enumerate(heads)]
    got = measure(rows, [(i + 1, h) for i, h in enumerate(heads)], {i + 1: merged(h) for i, h in enumerate(heads)})
    assert (got["mergeable_rows"], got["merged_first"], got["liveness_ok"]) == (10, 10, True)


def test_the_old_one_argument_form_of_mergeable_row_is_unchanged():
    assert mg.mergeable_row(row()) is True and mg.mergeable_row(row(false=("open",))) is False


def test_the_report_line_shows_the_split_and_the_json_carries_it(tmp_path, monkeypatch, capsys):
    recs = [decision(1, A, "PASS", ts=stamped(7200)), row(clock=time.time(), pr=1, head=A, false=("open",))]
    gh = FakeGH({1: pull(A, merged=True, merged_at=stamped(3600))}, {A: "success", M: "success"})
    _, rep = run_report(tmp_path, monkeypatch, recs, gh)
    assert rep["liveness"]["mergeable_rows"] == 1 and rep["liveness"]["merged_first"] == 1 and rep["liveness"]["merged_first_unread"] == 0
    assert "mergeable_rows=1 (merged_first=1) (needs >= 10)" in capsys.readouterr().out


def test_a_row_whose_pr_has_no_decision_in_the_report_is_unread_and_the_line_says_so(tmp_path, monkeypatch, capsys):
    recs = [decision(1, A, "PASS", ts=stamped(7200)), row(clock=time.time(), pr=1, head=A, false=("open",)),
            row(clock=time.time(), pr=2, head=B, false=("open",))]
    gh = FakeGH({1: pull(A, merged=True, merged_at=stamped(3600))}, {A: "success", M: "success"})
    _, rep = run_report(tmp_path, monkeypatch, recs, gh)
    assert (rep["liveness"]["mergeable_rows"], rep["liveness"]["merged_first_unread"]) == (1, 1)
    assert "mergeable_rows=1 (merged_first=1, unread_pull=1) (needs >= 10)" in capsys.readouterr().out


def test_a_merged_first_row_never_feeds_ready_or_the_rows(tmp_path, monkeypatch):
    base = [decision(1, A, "PASS", ts=stamped(7200))]
    gh = FakeGH({1: pull(A, merged=True, merged_at=stamped(3600))}, {A: "success", M: "success"})
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    _, plain = run_report(tmp_path / "a", monkeypatch, base, gh)
    _, with_row = run_report(tmp_path / "b", monkeypatch, base + [row(clock=time.time(), pr=1, head=A, false=("open",))], gh)
    assert plain["liveness"]["mergeable_rows"] == 0 and with_row["liveness"]["mergeable_rows"] == 1
    for k in ("phase_e_ready", "counts", "rows", "false_green_breakdown", "hosted_red_merged"):
        assert with_row[k] == plain[k], k


def test_nothing_that_decides_or_arms_reads_liveness():
    for fn in (mg.phase_f_arming, mg.ready_precheck, mg.decide, mg.tick):
        src = inspect.getsource(fn)
        assert "liveness" not in src and "mergeable_row" not in src and "merged_first" not in src, fn.__name__


def test_a_row_head_that_is_no_sha_never_matches_a_pull_whose_head_is_unreadable():
    got = measure([row(head="", false=("open",))], merged_prs={1: {"merged": True, "head": {"sha": "bad"}}})
    assert got["mergeable_rows"] == 0
