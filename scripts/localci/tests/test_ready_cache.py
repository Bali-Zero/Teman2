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
    assert set(doc) == {"computed_at", "completed_at", "phase_e_ready", "phase_e_ready_ex_false_green", "false_green_keys", "refused", "reason", "compared_merges", "false_green", "compared_days", "journal_rows"}
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


# ------------------------------------------------------------------ C2 soundness: what the memo may serve, and under which key
def fill_memo(w, monkeypatch):
    memo = mg.ReadMemo(w.state / mg.MEMO_FILE)
    out, _ = run_report(w, monkeypatch, memo)
    memo.save()
    return out


def edit_memo(w, change):
    doc = json.loads((w.state / mg.MEMO_FILE).read_text())
    change(doc)
    (w.state / mg.MEMO_FILE).write_text(json.dumps(doc))


def test_a_stored_entry_of_a_pull_that_is_open_is_read_again(fw, monkeypatch):
    plain = fill_memo(fw, monkeypatch)
    edit_memo(fw, lambda d: d["pulls"][f"{REPO}#1001"].update(state="open", merged=False))   # a planted or damaged entry
    again, reads = run_report(fw, monkeypatch, mg.ReadMemo(fw.state / mg.MEMO_FILE))
    assert f"repos/{REPO}/pulls/1001" in reads and f"repos/{REPO}/pulls/1002" not in reads and again == plain


def test_a_stored_hosted_document_with_a_pending_required_context_is_read_again(fw, monkeypatch):
    plain = fill_memo(fw, monkeypatch)
    key = f"{REPO}@main:{M}:{'f' * 40}"
    edit_memo(fw, lambda d: d["lives"][key]["check_runs"][0].update(status="in_progress", conclusion=None))
    again, reads = run_report(fw, monkeypatch, mg.ReadMemo(fw.state / mg.MEMO_FILE))
    assert any(r.startswith(f"repos/{REPO}/commits/{M}/check-runs") for r in reads) and again == plain


@pytest.mark.parametrize("age_h,final", [(49, True), (48, True), (47, False), (1, False)])
def test_the_final_age_boundary_is_48_hours_from_the_newest_decision_of_the_pr(monkeypatch, age_h, final):
    monkeypatch.setattr(mg.time, "time", lambda: 1_800_000_000.0)
    closed = {"state": "closed", "merged": True}
    assert mg.FINAL_AFTER_S == 48 * 3600
    assert mg.memo_final_pr(closed, 1_800_000_000.0 - age_h * 3600) is final


def test_a_pull_is_final_only_when_closed_and_known(monkeypatch):
    monkeypatch.setattr(mg.time, "time", lambda: 1_800_000_000.0)
    old = 1_800_000_000.0 - mg.FINAL_AFTER_S - 1
    assert mg.memo_final_pr({"state": "closed"}, old) and not mg.memo_final_pr({"state": "open"}, old)
    assert not mg.memo_final_pr(None, old) and not mg.memo_final_pr({"state": "closed"}, None) and not mg.memo_final_pr({}, old)


def test_the_memo_key_names_repo_branch_sha_and_base_and_one_head_on_two_bases_is_two_entries(fw, monkeypatch):
    head, a_base, b_base = "7" * 40, "e" * 40, "d" * 40
    fw.hub.pulls[2001] = {"merged": False, "state": "closed", "head": {"sha": head}, "merge_commit_sha": None, "merged_at": None}
    with (fw.state / "decisions.jsonl").open("a") as fh:
        for at, base in ((60, a_base), (120, b_base)):   # the same head decided on two bases
            fh.write(json.dumps({"kind": "decision", "ts": mg.time.strftime("%Y-%m-%dT%H:%M:%SZ", mg.time.gmtime(time.time() - 20 * 86400 + at)),
                                 "pr": 2001, "head_sha": head, "base_sha": base, "overall": "BLOCKED"}, sort_keys=True) + "\n")
    memo = mg.ReadMemo(fw.state / mg.MEMO_FILE)
    run_report(fw, monkeypatch, memo)
    assert sorted(k for k in memo.data["lives"] if head in k) == [f"{REPO}@main:{head}:{b_base}", f"{REPO}@main:{head}:{a_base}"]
    assert all(k.startswith(f"{REPO}@main:") for k in memo.data["lives"]) and all(k.startswith(f"{REPO}#") for k in memo.data["pulls"])
    assert all(k.startswith(f"{REPO}@") for k in memo.data["parents"]) and memo.hits == 0


# ------------------------------------------------------------------ the memo stores the projection, not the payload
def test_the_memo_keeps_only_what_the_report_reads_and_the_report_is_unchanged(fw, monkeypatch):
    real = fw.hub.__call__
    bulk = {"output": {"title": "t", "summary": "s" * 4000, "text": "x" * 4000}, "html_url": "u" * 200, "details_url": "d" * 200,
            "check_suite": {"id": 1}, "app": {"id": 15368, "slug": "github-actions", "owner": {"login": "o" * 50}, "description": "D" * 500}}

    def fat(path):
        got = real(path)
        if "/check-runs" in path:
            got = {"check_runs": [{**r, **bulk, "app": {**r["app"], **bulk["app"]}, "started_at": "2026-10-01T00:00:00Z"} for r in got["check_runs"]]}
        elif re_pull.fullmatch(path):
            got = {**got, "body": "b" * 3000, "user": {"login": "u"}, "base": {"repo": {"description": "r" * 1000}}}
        return got
    re_pull = re.compile(rf"repos/{REPO}/pulls/\d+")
    monkeypatch.setattr(mg.hc, "gh_get", fat)
    fat_plain, _ = run_report(fw, monkeypatch, None)
    memo = mg.ReadMemo(fw.state / mg.MEMO_FILE)
    first, _ = run_report(fw, monkeypatch, memo)
    memo.save()
    full, reads = run_report(fw, monkeypatch, mg.ReadMemo(fw.state / mg.MEMO_FILE))
    assert fat_plain == first == full and reads == []
    raw = (fw.state / mg.MEMO_FILE).read_text()
    assert "summary" not in raw and "html_url" not in raw and "owner" not in raw and '"body"' not in raw
    doc = json.loads(raw)
    assert {tuple(sorted(v)) for v in doc["pulls"].values()} == {("closed_at", "head", "merge_commit_sha", "merged", "merged_at", "state")}
    run0 = next(iter(doc["lives"].values()))["check_runs"][0]
    assert set(run0) == {"id", "name", "status", "conclusion", "head_sha", "completed_at", "app"} and set(run0["app"]) == {"id", "slug"}
    assert len(raw) < 20 * 1024 * (len(doc["lives"]) + len(doc["pulls"]))


# ------------------------------------------------------------------ B19 beside the refresh tick
def test_a_merge_disarmed_by_a_stale_ready_waits_a_refresh_tick_then_the_retry_reads_the_new_cache_and_merges(fw, monkeypatch):
    monkeypatch.setattr(mg, "PENDING_RETRY_S", 0)
    age_cache(fw, mg.READY_MAX_AGE_S + 100)   # the decision started late in a cycle: READY has aged out meanwhile
    assert fw.tick() == 0   # the refresh is off in the world fixture: this is the decision tick
    assert live_kinds(fw) == ["decision", "would_enqueue", "would_merge"] and any(x.startswith("READY stale") for x in fw.wm()["phase_f"]["why"])
    refresh_on(monkeypatch)
    assert fw.tick() == 0   # the refresh tick ends after the refresh: the retry waits one tick
    assert live_kinds(fw)[3:] == ["ready_refreshed"] and fw.pushes == [] and cache(fw)["phase_e_ready"] is True
    assert fw.tick() == 0   # the retry goes through phase_f_arming, which reads the refreshed cache
    assert live_kinds(fw)[4:] == ["would_enqueue", "would_merge", "merged", "pushed"]
    assert [r for r in fw.live() if r["kind"] == "would_merge"][-1]["retry"] is True and armed_by_cache(fw.wm()["phase_f"])


# ------------------------------------------------------------------ the guards of the hosted-document path (gate round)
def test_a_hosted_document_is_read_live_for_a_row_whose_pr_is_not_settled_even_when_the_memo_holds_it(fw, monkeypatch):
    """The lives guard itself: a young row (a B11 replay of a merged PR shares its key with the original compared row) must be re-read, not
    served, however final the stored document looks. The pull is read live too (young), so only the lives guard can stop the stored copy."""
    head, base = "6" * 40, "c" * 40
    fw.hub.pulls[3001] = {"merged": False, "state": "closed", "head": {"sha": head}, "merge_commit_sha": None, "merged_at": None}
    with (fw.state / "decisions.jsonl").open("a") as fh:
        fh.write(json.dumps({"kind": "decision", "ts": mg.time.strftime("%Y-%m-%dT%H:%M:%SZ", mg.time.gmtime(time.time() - 3600)), "pr": 3001,
                             "head_sha": head, "base_sha": base, "overall": "BLOCKED"}, sort_keys=True) + "\n")
    fill_memo(fw, monkeypatch)
    donor = f"{REPO}@main:{M}:{'f' * 40}"
    edit_memo(fw, lambda d: d["lives"].__setitem__(f"{REPO}@main:{head}:{base}", {**d["lives"][donor], "sha": head}))   # a stored, final-looking document
    assert mg.live_is_final(json.loads((fw.state / mg.MEMO_FILE).read_text())["lives"][f"{REPO}@main:{head}:{base}"])
    _, reads = run_report(fw, monkeypatch, mg.ReadMemo(fw.state / mg.MEMO_FILE))
    assert f"repos/{REPO}/pulls/3001" in reads
    assert any(r.startswith(f"repos/{REPO}/commits/{head}/check-runs") for r in reads)


def test_the_projection_keeps_the_status_updated_at_and_the_entries_built_from_it_are_the_same(fw):
    live = {"repo": REPO, "branch": "main", "sha": M, "required_checks": [{"context": "st-ctx", "app_id": None}], "required_source": "protection", "pins": None,
            "check_runs": [], "statuses": [{"context": "st-ctx", "state": "failure", "updated_at": "2026-10-01T00:00:00Z", "description": "d" * 50, "target_url": "u",
                                            "id": 7, "creator": {"login": "x"}}]}
    kept = mg.project_live(live)
    assert kept["statuses"] == [{"context": "st-ctx", "state": "failure", "updated_at": "2026-10-01T00:00:00Z"}]
    before, after = mg.hc.hosted_entries(live["check_runs"], live["statuses"]), mg.hc.hosted_entries(kept["check_runs"], kept["statuses"])
    assert before == after and after["st-ctx"][0]["completed_at"] == "2026-10-01T00:00:00Z"   # the completed_at the reclassifications read
    assert mg.hc.hosted_verdict(before["st-ctx"], None) == mg.hc.hosted_verdict(after["st-ctx"], None)
    assert mg.hc.hosted_verdict(after["st-ctx"], None)["completed_at"] == "2026-10-01T00:00:00Z"


def test_a_young_replay_of_a_merged_pr_reads_the_shared_hosted_document_live_though_the_original_row_is_old(fw, monkeypatch):
    """B11: a replay row shares its key (merge commit, first parent) with the PR's original compared row. The PR's age counts its replays,
    so the stored final document of the old row is not served to the young one."""
    from .test_merger_phase_f import OLD_BASE, time_at
    head, m2 = "4" * 40, "2" * 40
    fw.hub.pulls[4001] = {"merged": True, "state": "closed", "head": {"sha": head}, "merge_commit_sha": m2, "merged_at": time_at(0, 19)}
    original = {"kind": "decision", "ts": time_at(0, 19), "pr": 4001, "head_sha": head, "base_sha": OLD_BASE, "overall": "BLOCKED"}
    replay = {"kind": "decision", "ts": mg.time.strftime("%Y-%m-%dT%H:%M:%SZ", mg.time.gmtime(time.time() - 3600)), "pr": 4001, "head_sha": head,
              "base_sha": OLD_BASE, "overall": "BLOCKED", "replay": True, "merge_commit": m2}

    def add(row):
        with (fw.state / "decisions.jsonl").open("a") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")
    add(original)
    fill_memo(fw, monkeypatch)   # the old row alone: (m2, OLD_BASE) is stored as final
    key = f"{REPO}@main:{m2}:{OLD_BASE}"
    assert key in json.loads((fw.state / mg.MEMO_FILE).read_text())["lives"]
    add(replay)
    _, reads = run_report(fw, monkeypatch, mg.ReadMemo(fw.state / mg.MEMO_FILE))
    assert any(r.startswith(f"repos/{REPO}/commits/{m2}/check-runs") for r in reads)
    assert f"repos/{REPO}/pulls/4001" in reads
