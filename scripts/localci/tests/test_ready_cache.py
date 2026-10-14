"""B20: READY is computed apart by the tick (``refresh_ready``) and only read by phase F (``read_ready``). The real report runs against the
seeded journal of test_merger_phase_f; the counting spy sits on ``report``."""
from __future__ import annotations

import argparse
import json
import re
import stat
import time

import pytest

from .test_merger import mg, world  # noqa: F401 — `world` is a fixture
from .test_merger import REPO
from .test_merger_phase_f import M, _spy_report, armed_by_cache, fw, write_ready  # noqa: F401 — `fw` is a fixture

REAL_DUE = mg.ready_refresh_due   # the world fixture switches the refresh off; these tests turn it back on


def cache_path(w):
    return w.state / mg.READY_CACHE_FILE


def cache(w):
    return json.loads(cache_path(w).read_text())


def refresh_on(monkeypatch):
    monkeypatch.setattr(mg, "ready_refresh_due", REAL_DUE)


def age_cache(w, seconds):
    write_ready(w.state, computed_at=time.time() - seconds)


def refusing(monkeypatch, how):
    calls = []

    def fake(*a, **kw):
        calls.append(kw)
        if how == "refuse":
            return 2, {"phase_e_ready": False, "refused": "CompareError: unexpected end of JSON input"}
        raise how
    monkeypatch.setattr(mg, "report", fake)
    return calls


def live_kinds(w):
    return [r["kind"] for r in w.live()]


# ------------------------------------------------------------------ the read: phase F never runs the report
def test_a_fresh_true_cache_arms_the_merge_right_after_the_tick_journalled_its_own_decision_and_the_report_is_never_called(fw, monkeypatch):
    calls = _spy_report(monkeypatch)
    refresh_on(monkeypatch)
    assert fw.tick() == 0
    assert live_kinds(fw)[:3] == ["decision", "would_enqueue", "would_merge"] and calls == []   # the gate's scenario: a new decision, still no report
    assert armed_by_cache(fw.wm()["phase_f"]) and live_kinds(fw)[-1] == "pushed"


@pytest.mark.parametrize("over,why", [({"phase_e_ready": False}, "READY false (cache)"),
                                      ({"refused": "CompareError: boom"}, "READY unreadable: CompareError: boom (cache)"),
                                      ({"computed_at": time.time() - mg.READY_MAX_AGE_S - 1}, "READY stale: computed "),
                                      ({"phase_e_ready": "yes"}, "READY false (cache)"),
                                      ({"computed_at": time.time() + 5000}, "READY stale: computed -")])
def test_read_ready_refuses_what_is_not_a_fresh_true_cache(fw, over, why):
    write_ready(fw.state, **over)
    reason, facts = mg.read_ready(fw.state)
    assert reason is not None and reason.startswith(why) and facts["ready_source"] == "cache"


def test_read_ready_accepts_a_cache_just_under_the_max_age_and_refuses_it_at_the_max_age(fw):
    age_cache(fw, mg.READY_MAX_AGE_S - 30)
    assert mg.read_ready(fw.state)[0] is None
    age_cache(fw, mg.READY_MAX_AGE_S + 1)
    assert mg.read_ready(fw.state)[0].startswith("READY stale")


@pytest.mark.parametrize("junk", ["{torn", "[]", "null", '{"phase_e_ready": true}', '{"computed_at": "now", "phase_e_ready": true}', ""])
def test_a_missing_or_corrupt_cache_is_unknown_never_an_error(fw, junk):
    cache_path(fw).write_text(junk)
    assert mg.read_ready(fw.state) == ("READY unknown: no cache", {"ready_source": "cache"})
    cache_path(fw).unlink()
    assert mg.read_ready(fw.state)[0] == "READY unknown: no cache"


# ------------------------------------------------------------------ the refresh: the tick's own work, once an hour
def test_a_tick_with_a_cache_older_than_the_refresh_interval_refreshes_and_decides_nothing_else(fw, monkeypatch):
    calls = _spy_report(monkeypatch)
    refresh_on(monkeypatch)
    age_cache(fw, mg.READY_REFRESH_S + 60)
    assert fw.tick() == 0
    assert [c["emit"] for c in calls] == [False] and live_kinds(fw) == ["ready_refreshed"] and fw.pushes == []   # a refresh is its own tick
    doc = cache(fw)
    assert doc["phase_e_ready"] is True and doc["refused"] is None and doc["compared_merges"] >= mg.READY_MIN_MERGES and doc["false_green"] == 0
    assert set(doc) == {"computed_at", "completed_at", "phase_e_ready", "refused", "reason", "compared_merges", "false_green", "compared_days", "journal_rows"}
    (row,) = fw.live()
    assert row["result"] == "true" and row["memo_misses"] > 0 and row["memo_hits"] == 0 and row["duration_s"] >= 0 and row["lease_id"]
    assert stat.S_IMODE(cache_path(fw).stat().st_mode) == 0o600 and time.time() - doc["computed_at"] < 600
    assert [p.name for p in fw.state.iterdir() if p.name.startswith(mg.READY_CACHE_FILE)] == [mg.READY_CACHE_FILE]


def test_the_tick_after_a_refresh_merges_on_the_cache_it_wrote(fw, monkeypatch):
    calls = _spy_report(monkeypatch)
    refresh_on(monkeypatch)
    cache_path(fw).unlink()
    assert fw.tick() == 0 and len(calls) == 1 and live_kinds(fw) == ["ready_refreshed"]
    assert fw.tick() == 0 and len(calls) == 1
    assert armed_by_cache(fw.wm()["phase_f"]) and live_kinds(fw)[-1] == "pushed"


def test_a_tick_with_a_cache_younger_than_the_refresh_interval_does_not_refresh(fw, monkeypatch):
    calls = _spy_report(monkeypatch)
    refresh_on(monkeypatch)
    age_cache(fw, mg.READY_REFRESH_S - 60)
    assert fw.tick() == 0 and calls == [] and live_kinds(fw)[:1] == ["decision"]


def test_a_false_result_is_stored_and_a_later_merge_is_refused_on_it(fw, monkeypatch):
    refresh_on(monkeypatch)
    fw.hub.seed(fw.state, n=50, days=4)   # a 4-day span of compared merges: the precheck cannot rule it out, the report says false
    age_cache(fw, mg.READY_REFRESH_S + 60)
    assert fw.tick() == 0 and cache(fw)["phase_e_ready"] is False
    assert fw.tick() == 0 and "READY false (cache)" in fw.wm()["phase_f"]["why"] and "pushed" not in live_kinds(fw)


@pytest.mark.parametrize("how", ["refuse", RuntimeError("boom")], ids=["refused", "raised"])
def test_a_failed_refresh_keeps_the_old_cache_journals_it_and_ends_its_tick(fw, monkeypatch, how):
    refresh_on(monkeypatch)
    age_cache(fw, mg.READY_REFRESH_S + 60)
    before = cache_path(fw).read_text()
    calls = refusing(monkeypatch, how)
    assert fw.tick() == 0
    assert cache_path(fw).read_text() == before and len(calls) == 1
    assert live_kinds(fw) == ["ready_refresh_failed"] and fw.pushes == []   # a decision never shares a refresh's tick
    (failed,) = fw.live()
    assert failed["error"] and failed["result"] == "failed" and {"duration_s", "memo_hits", "memo_misses"} <= set(failed)
    assert fw.tick() == 0 and len(calls) == 1 and live_kinds(fw)[1:2] == ["decision"]   # the next tick decides; the retry interval holds the next refresh off
    assert fw.tick() == 0 and len(calls) == 1


def test_a_failed_refresh_is_tried_again_once_the_retry_interval_has_passed(fw, monkeypatch):
    refresh_on(monkeypatch)
    age_cache(fw, mg.READY_REFRESH_S + 60)
    calls = refusing(monkeypatch, "refuse")
    fw.tick()
    fw.tick()   # the decision tick the mark guarantees
    real = time.time
    monkeypatch.setattr(mg.time, "time", lambda: real() + mg.READY_RETRY_S + 5)
    fw.tick()
    assert len(calls) == 2


@pytest.mark.parametrize("exc", [mg.MergerError("tick exceeded --tick-timeout (signal 14)"), mg.Stopped("stopped (signal 15)")], ids=["watchdog", "stop"])
def test_a_watchdog_or_a_stop_during_a_refresh_ends_the_tick(fw, monkeypatch, exc):
    refresh_on(monkeypatch)
    age_cache(fw, mg.READY_REFRESH_S + 60)
    before = cache_path(fw).read_text()
    refusing(monkeypatch, exc)
    assert fw.tick() == 1
    assert live_kinds(fw) == ["error"] and cache_path(fw).read_text() == before and fw.pushes == []   # not ready_refresh_failed: it ended the tick
    assert fw.live()[0]["error"].startswith(str(exc)[:20])


# ------------------------------------------------------------------ C1: the cadence cannot starve the decisions
class Clock:
    """A host clock the tests move: ``mg.time.time`` is the real one plus ``offset``."""

    def __init__(self, monkeypatch):
        self.offset, real = 0.0, time.time
        monkeypatch.setattr(mg.time, "time", lambda: real() + self.offset)


def slow_report(clock, monkeypatch, takes_s):
    calls = []

    def fake(a, emit=True, memo=None):
        calls.append(1)
        clock.offset += takes_s
        return 0, {"phase_e_ready": True, "window": {"compared_merges": 50, "compared_days": 5.0}}
    monkeypatch.setattr(mg, "report", fake)
    return calls


def test_a_report_longer_than_the_refresh_interval_still_leaves_a_decision_tick_between_two_refreshes(fw, monkeypatch):
    refresh_on(monkeypatch)
    clock = Clock(monkeypatch)
    calls = slow_report(clock, monkeypatch, mg.READY_REFRESH_S + 500)
    seen = []
    for _ in range(6):
        clock.offset += mg.READY_REFRESH_S + 100   # every tick finds the cache due by the clock
        before = len(calls)
        assert fw.tick() == 0
        seen.append(len(calls) - before)
    assert seen == [1, 0, 1, 0, 1, 0] and "decision" in live_kinds(fw)   # alternate ticks decide


def test_a_refresh_killed_by_the_watchdog_still_leaves_the_next_tick_free_to_decide(fw, monkeypatch):
    refresh_on(monkeypatch)
    age_cache(fw, mg.READY_REFRESH_S + 60)
    calls = refusing(monkeypatch, mg.MergerError("tick exceeded --tick-timeout (signal 14)"))
    assert fw.tick() == 1 and (fw.state / mg.READY_MARK_FILE).exists()
    assert fw.tick() == 0 and len(calls) == 1 and "decision" in live_kinds(fw)


def test_the_cadence_is_measured_from_the_completion_of_a_refresh_not_its_start(fw, monkeypatch):
    refresh_on(monkeypatch)
    clock = Clock(monkeypatch)
    cache_path(fw).unlink()
    calls = slow_report(clock, monkeypatch, 1000)
    fw.tick()   # reads 1000 s: computed_at is its start, completed_at its end
    assert len(calls) == 1 and cache(fw)["completed_at"] - cache(fw)["computed_at"] >= 999
    fw.tick()   # the decision tick
    clock.offset += mg.READY_REFRESH_S - 500   # 3100 s after completion, 4100 s after the start
    fw.tick()
    assert len(calls) == 1
    clock.offset += 600
    fw.tick()
    assert len(calls) == 2


# ------------------------------------------------------------------ C3: the precheck's no skips the report
@pytest.mark.parametrize("seed,why", [({"age": 3}, "READY false: journal window 3."), ({"n": 10}, "READY false: 1[01] distinct decided PRs < 50")],
                         ids=["journal-younger-than-the-window", "fewer-decided-prs-than-the-threshold"])
def test_with_the_refresh_on_a_precheck_no_skips_the_report_and_keeps_the_merge_refused(fw, monkeypatch, seed, why):
    calls = _spy_report(monkeypatch)
    refresh_on(monkeypatch)
    fw.hub.seed(fw.state, **seed)
    cache_path(fw).unlink()
    assert fw.tick() == 0 and calls == []
    doc = cache(fw)
    assert doc["phase_e_ready"] is False and re.match(why, doc["reason"]) and live_kinds(fw) == ["ready_refreshed"]
    assert fw.live()[0]["result"] == "precheck_false"
    assert fw.tick() == 0 and calls == []
    assert any(re.match(why, x) for x in fw.wm()["phase_f"]["why"]) and "pushed" not in live_kinds(fw)


def test_a_false_cache_with_the_prechecks_reason_is_refused_with_that_reason(fw):
    write_ready(fw.state, phase_e_ready=False, reason="READY false: 11 distinct decided PRs < 50")
    assert mg.read_ready(fw.state)[0] == "READY false: 11 distinct decided PRs < 50 (cache)"


# ------------------------------------------------------------------ C2: the memo
def ask():
    return argparse.Namespace(repo=REPO, base="main", state_dir=None, since=None)


def run_report(w, monkeypatch, memo):
    a = ask()
    a.state_dir = str(w.state)
    reads = []
    real = mg.hc.gh_get
    monkeypatch.setattr(mg.hc, "gh_get", lambda path: reads.append(path) or real(path))
    try:
        _, out = mg.report(a, emit=False, memo=memo)
    finally:
        monkeypatch.setattr(mg.hc, "gh_get", real)
    return {k: v for k, v in out.items() if k != "generated_at"}, reads


def test_a_memoized_report_equals_an_unmemoized_one_on_every_field_and_reads_nothing_final_again(fw, monkeypatch):
    plain, plain_reads = run_report(fw, monkeypatch, None)
    first_memo = mg.ReadMemo(fw.state / mg.MEMO_FILE)
    empty, empty_reads = run_report(fw, monkeypatch, first_memo)
    first_memo.save()
    assert stat.S_IMODE((fw.state / mg.MEMO_FILE).stat().st_mode) == 0o600
    full_memo = mg.ReadMemo(fw.state / mg.MEMO_FILE)
    full, full_reads = run_report(fw, monkeypatch, full_memo)
    assert plain["phase_e_ready"] is True
    assert plain == empty == full   # every READY field and every other output of the report
    assert len(empty_reads) == len(plain_reads) > 40 and first_memo.hits == 0
    assert full_reads == [] and full_memo.hits > 40 and full_memo.misses == 0


def test_rows_that_are_not_final_are_read_every_time(fw, monkeypatch):
    def second_run(prepare):
        memo = mg.ReadMemo(fw.state / mg.MEMO_FILE)
        prepare()
        run_report(fw, monkeypatch, memo)
        memo.save()
        again = mg.ReadMemo(fw.state / mg.MEMO_FILE)
        _, reads = run_report(fw, monkeypatch, again)
        return again, reads

    def open_pr():   # an open PR is read again: its pulls/{n}, and the sha's check runs with it
        fw.hub.pulls[1001] = {**fw.hub.pulls[1001], "state": "open", "merged": False, "merge_commit_sha": None, "merged_at": None}
    memo, reads = second_run(open_pr)
    assert f"repos/{REPO}/pulls/1001" in reads and f"repos/{REPO}/pulls/1002" not in reads and memo.misses >= 1

    (fw.state / mg.MEMO_FILE).unlink()
    fw.hub.pulls[1001] = {**fw.hub.pulls[1001], "state": "closed", "merged": True, "merge_commit_sha": M, "merged_at": fw.hub.pulls[1002]["merged_at"]}
    real = fw.hub.__call__

    def pending(path):   # one required context of every sha is still running
        got = real(path)
        if "/check-runs" in path:
            got = {"check_runs": [{**r, "status": "in_progress", "conclusion": None} if r["name"] == "ctx-a" else r for r in got["check_runs"]]}
        return got
    monkeypatch.setattr(mg.hc, "gh_get", pending)
    memo = mg.ReadMemo(fw.state / mg.MEMO_FILE)
    mg.report(argparse.Namespace(repo=REPO, base="main", state_dir=str(fw.state), since=None), emit=False, memo=memo)
    memo.save()
    assert mg.ReadMemo(fw.state / mg.MEMO_FILE).data["lives"] == {}   # an incomplete run is never final
    monkeypatch.setattr(mg.hc, "gh_get", real)

    (fw.state / mg.MEMO_FILE).unlink()
    fw.hub.seed(fw.state, age=1)   # decisions younger than FINAL_AFTER_S
    memo = mg.ReadMemo(fw.state / mg.MEMO_FILE)
    run_report(fw, monkeypatch, memo)
    memo.save()
    stored = mg.ReadMemo(fw.state / mg.MEMO_FILE).data   # a commit's parents never change, so they are the one thing kept
    assert stored["pulls"] == {} and stored["lives"] == {}


@pytest.mark.parametrize("junk", ["{torn", "[]", "null", '{"v": 2, "pulls": {"x": 1}}', '{"v": 1, "pulls": [], "lives": 3}', ""])
def test_a_corrupt_or_foreign_memo_is_empty_never_an_error(fw, monkeypatch, junk):
    (fw.state / mg.MEMO_FILE).write_text(junk)
    memo = mg.ReadMemo(fw.state / mg.MEMO_FILE)
    assert memo.data == {"pulls": {}, "lives": {}, "parents": {}}
    out, _ = run_report(fw, monkeypatch, memo)
    assert out["phase_e_ready"] is True and memo.hits == 0


def test_a_memo_without_a_path_remembers_nothing(fw, monkeypatch):
    memo = mg.ReadMemo(None)
    memo.put("pulls", "k", {"a": 1})
    assert memo.get("pulls", "k") is None
    memo.save()


def test_the_memo_never_serves_an_entry_younger_than_the_final_age(fw, monkeypatch):
    memo = mg.ReadMemo(fw.state / mg.MEMO_FILE)
    run_report(fw, monkeypatch, memo)
    memo.save()
    fw.hub.seed(fw.state, age=1)   # same PRs, decisions of the last day: the stored entries are not to be served
    again = mg.ReadMemo(fw.state / mg.MEMO_FILE)
    _, reads = run_report(fw, monkeypatch, again)
    assert f"repos/{REPO}/pulls/1001" in reads and any("/check-runs" in r for r in reads)


# ------------------------------------------------------------------ C5
def test_a_torn_journal_line_refuses_to_arm_even_with_a_fresh_true_cache(fw, monkeypatch):
    refresh_on(monkeypatch)
    with (fw.state / "decisions.jsonl").open("a") as fh:
        fh.write("{torn\n")
    assert fw.tick() == 0
    assert any(x.startswith("READY unreadable: decisions.jsonl line") for x in fw.wm()["phase_f"]["why"]) and "pushed" not in live_kinds(fw)
