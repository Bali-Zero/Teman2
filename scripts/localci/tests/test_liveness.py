"""B24: liveness is measured before the flip — mergeable rows and coverage over the trailing 48 h, apart from phase E's READY."""
from __future__ import annotations

import time

import pytest

from .test_merger_report import A, B, C, M, FakeGH, decision, merged_world, mg, pull, run_report

NOW = 1_800_000_000.0
EXCLUDED = ("label_privileged", "not_in_queue", "first_enqueue")
REQUIRED = tuple(k for k in mg.CRITERION if k not in EXCLUDED)


def iso(clock: float, ago_s: float = 0) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(clock - ago_s))


def row(pr=1, head=A, ago_s=3600, kind="would_enqueue", false=(), clock=NOW, **extra):
    criterion = {k: k not in false for k in mg.CRITERION}
    return {"kind": kind, "ts": iso(clock, ago_s), "pr": pr, "head_sha": head, "criterion": criterion, "ok": all(criterion.values()), **extra}


def merged(head, ago_s=1800, clock=NOW, n=None):
    return {"merged": True, "merged_at": iso(clock, ago_s), "head": {"sha": head}, "number": n}


def measure(rows, decided=(), merged_prs=None, listing=None, clock=NOW):
    decisions = [{"kind": "decision", "pr": n, "head_sha": h} for n, h in decided]
    return mg.liveness(rows, decisions, merged_prs or {}, listing, clock)


def test_the_four_terms_that_cannot_be_true_before_the_flip_are_excluded_and_every_other_term_counts():
    assert measure([row(false=EXCLUDED)])["mergeable_rows"] == 1   # a shadow row: unlabelled, unqueued... and still mergeable
    for term in REQUIRED:
        assert measure([row(false=(term,))])["mergeable_rows"] == 0, term
    assert "hosted_required_green" in REQUIRED and "label_privileged" not in REQUIRED


def test_armed_env_is_no_criterion_term_a_row_refused_by_it_alone_is_mergeable():
    assert "armed_env" not in mg.CRITERION
    assert measure([row(armed_env=False)])["mergeable_rows"] == 1


def test_a_retry_counts_and_other_kinds_or_a_missing_or_unreadable_criterion_do_not():
    bad_term = row()
    del bad_term["criterion"]["open"]
    rows = [row(retry=True), row(kind="enqueue_refused"), row(kind="would_merge"), {**row(), "criterion": None}, {**row(), "criterion": "x"}, bad_term]
    assert measure(rows)["mergeable_rows"] == 1   # only the retry; a term not journalled true is not true


def test_the_window_is_forty_eight_hours_of_the_clock():
    h = mg.LIVENESS_WINDOW_S
    got = measure([row(ago_s=h), row(ago_s=h + 1), row(ago_s=h - 1), {**row(), "ts": "garbage"}])
    assert got["mergeable_rows"] == 2 and got["window_h"] == 48


def test_a_merged_pr_outside_the_window_is_not_in_the_coverage():
    got = measure([row()], [(1, A), (2, B)], {1: merged(A), 2: merged(B, ago_s=mg.LIVENESS_WINDOW_S + 1)})
    assert got["merged_decided"] == 1 and got["coverage_decided"] == 1.0


def test_coverage_decided_counts_only_prs_localci_decided_at_the_merged_head_and_coverage_all_counts_every_merged_pr():
    rows = [row(pr=1, head=A)]
    prs = {1: merged(A), 2: merged(B), 3: merged(C)}
    listing = [merged(A, n=1), merged(B, n=2), merged(C, n=3), {**merged(A, n=4), "merged_at": None}]
    got = measure(rows, [(1, A), (2, B), (3, "d" * 40)], prs, listing)   # PR 3 was decided at another head than the one merged
    assert (got["merged_decided"], got["coverage_decided"]) == (2, 0.5)
    assert (got["merged_all_approx"], got["coverage_all_approx"]) == (3, pytest.approx(1 / 3))


def test_a_replay_decision_is_not_a_decided_head():
    replay = {"kind": "decision", "pr": 1, "head_sha": A, "replay": True}
    got = mg.liveness([row(pr=2, head=B)], [replay, {"kind": "decision", "pr": 2, "head_sha": B}], {1: merged(A), 2: merged(B)}, None, NOW)
    assert got["merged_decided"] == 1 and got["coverage_decided"] == 1.0   # PR 1 was only replayed: it never had a would_enqueue to be covered by


def test_label_ok_rows_counts_the_mergeable_rows_that_also_carry_the_label():
    got = measure([row(pr=1), row(pr=2, false=("label_privileged",)), row(pr=3, false=("label_privileged",)), row(pr=4, false=("open",))])
    assert got["mergeable_rows"] == 3 and got["label_ok_rows"] == 1


def test_the_ticks_report_never_reads_the_merged_listing(tmp_path, monkeypatch):
    recs, gh = ready_world()
    state = tmp_path / "state"
    state.mkdir()
    (state / "decisions.jsonl").write_text("".join(__import__("json").dumps(r) + "\n" for r in recs))
    monkeypatch.setattr(mg.hc, "gh_get", gh)
    monkeypatch.setattr(mg, "merged_listing", lambda a: pytest.fail("the tick's report read the closed-PR listing"))
    _, out = mg.report(__import__("argparse").Namespace(repo="o/r", base="main", state_dir=str(state), since=None), emit=False)
    assert out["liveness"]["coverage_all_approx"] is None and out["liveness"]["merged_all_approx"] is None


def test_a_row_at_another_head_of_the_same_pr_is_no_coverage():
    got = measure([row(pr=1, head=B)], [(1, A)], {1: merged(A)})
    assert got["coverage_decided"] == 0.0


def test_an_unreadable_listing_leaves_coverage_all_null_and_never_touches_the_decided_view():
    got = measure([row()], [(1, A)], {1: merged(A)}, listing=None)
    assert got["coverage_all_approx"] is None and got["merged_all_approx"] is None and got["coverage_decided"] == 1.0


@pytest.mark.parametrize(("n_rows", "covered", "of", "ok"), [(10, 4, 5, True), (9, 4, 5, False), (10, 3, 4, False), (10, 0, 0, False), (10, 1, 1, True)])
def test_liveness_ok_needs_ten_mergeable_rows_and_four_fifths_coverage_of_the_decided(n_rows, covered, of, ok):
    assert (mg.LIVENESS_MIN_ROWS, mg.LIVENESS_MIN_COVERAGE) == (10, 0.8)
    heads = [chr(ord("a") + i) * 40 for i in range(of)]
    rows = [row(pr=100 + i, head=chr(ord("p") + i % 10) * 40) for i in range(n_rows - covered)] + [row(pr=i + 1, head=heads[i]) for i in range(covered)]
    prs = {i + 1: merged(heads[i]) for i in range(of)}
    assert measure(rows, [(i + 1, heads[i]) for i in range(of)], prs)["liveness_ok"] is ok


def stamped(ago_s: float) -> str:
    return iso(time.time(), ago_s)


def test_the_report_carries_the_block_and_prints_ready_and_liveness_ok_explicitly(tmp_path, monkeypatch, capsys):
    recs = [decision(1, A, "PASS", ts=stamped(7200)), row(clock=time.time(), pr=1, head=A, false=EXCLUDED)]
    gh = FakeGH({1: pull(A, merged=True, merged_at=stamped(3600))}, {A: "success", M: "success"})
    rc, rep = run_report(tmp_path, monkeypatch, recs, gh)
    lv = rep["liveness"]
    assert lv["mergeable_rows"] == 1 and lv["merged_decided"] == 1 and lv["coverage_decided"] == 1.0 and lv["liveness_ok"] is False   # one row of ten
    assert lv["coverage_all_approx"] is None   # FakeGH has no listing: reported, not refused
    out = capsys.readouterr().out
    assert "phase E READY: false liveness_ok: false:" in out and "liveness (B24, last 48 h): mergeable_rows=1" in out


def ready_world():
    """50 compared merges 5 days apart (READY true); none inside the last 48 h, so liveness has nothing to read."""
    recs, gh = merged_world(50, 5.0)
    return recs, gh


def test_phase_e_ready_stays_true_with_liveness_false(tmp_path, monkeypatch, capsys):
    recs, gh = ready_world()
    rc, rep = run_report(tmp_path, monkeypatch, recs, gh)
    assert rep["phase_e_ready"] is True and rep["liveness"]["liveness_ok"] is False and rc == 0
    assert "phase E READY: true liveness_ok: false:" in capsys.readouterr().out


def test_phase_e_ready_stays_false_with_liveness_true(tmp_path, monkeypatch):
    head = "9" * 40
    recs = [decision(1, head, "BLOCKED", ts=stamped(7200))] + [row(clock=time.time(), pr=100 + i, head=chr(ord("a") + i) * 40) for i in range(11)]
    recs.append(row(clock=time.time(), pr=1, head=head))
    gh = FakeGH({1: pull(head, merged=True, merged_at=stamped(3600))}, {head: "success", M: "success"})
    _, rep = run_report(tmp_path, monkeypatch, recs, gh)
    assert rep["liveness"]["liveness_ok"] is True and rep["phase_e_ready"] is False


def test_liveness_rows_leave_phase_e_ready_and_the_counts_untouched(tmp_path, monkeypatch):
    recs, gh = ready_world()
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    _, plain = run_report(tmp_path / "a", monkeypatch, recs, gh)
    extra = [row(clock=time.time(), pr=500 + i, head=f"{500 + i:040x}") for i in range(12)]
    _, with_rows = run_report(tmp_path / "b", monkeypatch, recs + extra, gh)
    assert with_rows["phase_e_ready"] is plain["phase_e_ready"] is True and with_rows["counts"] == plain["counts"]
    assert with_rows["window"]["compared_merges"] == plain["window"]["compared_merges"]
