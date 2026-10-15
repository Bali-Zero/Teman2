"""B30 D1 (an ALLOW-LIST) and D2 (the retry window): a row is re-decidable only when every term is named; the r1/r2/r3 counterexamples never are."""
from __future__ import annotations

import pytest

from .test_merger import REPO, mg, pr, world  # noqa: F401 — `world` is a fixture
from .test_redecide import B1, B2, H1, H2, NOW, T0, dec, ev, fresh, run

HOSTCTX = {"ctx.e2e-tests": "host_disk_below_floor 80GB<100GB"}


def host_row(**kw):
    base = {"overall": "BLOCKED", "error": None, "host_no_verdict": dict(HOSTCTX),
            "contexts": {"ctx.e2e-tests": "ERROR", "ctx.a": "OK"}, "checks": {"e2e": "ERROR", "a": "PASS"}}
    for k, v in kw.items():
        base[k] = {**base[k], **v} if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return dec(**base)


def driver_row(**kw):
    return dec(overall="ERROR", error="runner plan failed (merger.log)", **kw)


def at(back_s: float) -> str:
    return mg.time.strftime("%Y-%m-%dT%H:%M:%SZ", mg.time.gmtime(NOW - back_s))


# ---- the rows that MUST never re-decide: gate-b30 r1 (EVICT_CAP), r2 (a candidate crash or hang), r3 (a hang beside a host no-verdict)

def test_r1_run_evict_rerun_is_bounded_by_evict_cap_inside_the_window():
    recs, now, runs = [host_row()], mg._epoch(T0) + mg.REDECIDE_BACKOFF_S, []
    end = now + mg.EVICT_WINDOW_S
    while now < end:
        todo, _ = mg.triage([pr(1, H1)], REPO, recs, B1, now_s=now, host_free_gb=150.0, start_floor_gb=100.0, evict_capped=[], redecide_capped=[])
        if todo:
            runs.append(now)
            recs.append(ev(mg.time.strftime("%Y-%m-%dT%H:%M:%SZ", mg.time.gmtime(now))))
        now += 300
    assert len(runs) == mg.EVICT_CAP


def test_r1_host_disk_baseline_cannot_bypass_evict_cap_with_a_fresh_transient_decision_count():
    recs = [host_row(), *[ev("2026-10-09T11:00:00Z")] * mg.EVICT_CAP]
    ec: list = []
    todo, _ = mg.triage([pr(1, H1)], REPO, recs, B1, now_s=NOW, host_free_gb=500.0, start_floor_gb=0.0, evict_capped=ec, redecide_capped=[])
    assert todo == [] and [p["number"] for p in ec] == [1]


@pytest.mark.parametrize("row", [
    host_row(contexts={"ctx.a": "ERROR"}, checks={"a": "ERROR"}),
    dec(overall="BLOCKED", error=None, contexts={"ctx.a": "INTERRUPTED"}, checks={"a": "INTERRUPTED"}),
    dec(overall="BLOCKED", error=None, contexts={"ctx.a": "ERROR"}, checks={"a": "ERROR"}),
])
def test_r2_a_candidate_error_or_hang_alone_is_not_transient(row):
    assert mg.transient_reasons(row) == []


@pytest.mark.parametrize("err", [
    f"status.json is bound to {('a' * 40, 'b' * 40, 'c' * 64)}, not to this candidate, base and seal",
    "tick exceeded --tick-timeout 14400s",
    "tick exceeded its watchdog (the alarm fired inside a handler that swallowed it)",
])
def test_r2_seal_mismatch_and_tick_timeout_are_not_transient(err):
    row = dec(overall="ERROR", error=err, contexts={}, checks={})
    assert mg.transient_reasons(row) == []
    assert run([row])[0] == []


@pytest.mark.parametrize("row", [
    host_row(contexts={"ctx.smoke": "INTERRUPTED"}, checks={"smoke": "INTERRUPTED"}),   # a late check SIGTERMed at the run budget
    host_row(checks={"late": "INTERRUPTED"}),                                           # the same hang in a check no required context maps
    host_row(contexts={"ctx.smoke": "RUNNING"}, checks={"smoke": "RUNNING"}),           # SIGKILLed 60 s after the SIGTERM: never marked
    host_row(contexts={"ctx.a": "STALE"}, checks={"a": "STALE"}),                       # the candidate dirtied its worktree: a FAIL turns STALE
    host_row(overall="INTERRUPTED"),
])
def test_r3_a_hang_beside_a_host_no_verdict_is_not_transient(row):
    assert mg.transient_reasons(row) == []
    assert run([row], host_free_gb=150.0, start_floor_gb=100.0)[0] == []


# ---- the allow-list itself: every term names its set, and a status outside it is never re-decidable

@pytest.mark.parametrize("status", ["FAIL", "BLOCKED", "ERROR", "INTERRUPTED", "RUNNING", "STALE", "PASS", "NOT_APPLICABLE", "SOMETHING_NEW"])
def test_a_context_status_the_host_did_not_name_must_be_listed(status):
    assert mg.transient_reasons(host_row(contexts={"ctx.b": status})) == []
    assert mg.transient_reasons(driver_row(contexts={"ctx.b": status})) == []


@pytest.mark.parametrize("status", ["OK", "UNCOVERED", "QUEUED"])
def test_a_listed_context_status_keeps_the_row_re_decidable(status):
    assert mg.transient_reasons(host_row(contexts={"ctx.b": status})) == ["host_disk"]
    assert mg.transient_reasons(driver_row(contexts={"ctx.b": status})) == ["error"]


@pytest.mark.parametrize("status", ["FAIL", "OK", "INTERRUPTED", "RUNNING", "STALE", "PASS", "SOMETHING_NEW"])
def test_a_host_named_context_must_read_error_or_blocked(status):
    assert mg.transient_reasons(host_row(contexts={"ctx.e2e-tests": status})) == []


@pytest.mark.parametrize("status", ["ERROR", "BLOCKED"])
def test_a_host_named_context_reading_error_or_blocked_is_the_class(status):
    assert mg.transient_reasons(host_row(contexts={"ctx.e2e-tests": status})) == ["host_disk"]


@pytest.mark.parametrize("status", ["FAIL", "INTERRUPTED", "RUNNING", "STALE", "SOMETHING_NEW"])
def test_a_check_status_must_be_listed(status):
    assert mg.transient_reasons(host_row(checks={"x": status})) == []
    assert mg.transient_reasons(driver_row(checks={"x": status})) == []


@pytest.mark.parametrize("status", ["PASS", "NOT_APPLICABLE", "BLOCKED", "QUEUED"])
def test_a_listed_check_status_keeps_the_row_re_decidable(status):
    assert mg.transient_reasons(host_row(checks={"x": status})) == ["host_disk"]
    assert mg.transient_reasons(driver_row(checks={"x": status})) == ["error"]


def test_a_check_error_is_admitted_only_beside_a_host_no_verdict():
    assert mg.transient_reasons(host_row(checks={"x": "ERROR"})) == ["host_disk"]
    assert mg.transient_reasons(driver_row(checks={"x": "ERROR"})) == []
    assert mg.transient_reasons(dec(overall="BLOCKED", error=None, checks={"x": "ERROR"})) == []


@pytest.mark.parametrize("overall", ["PASS", "FAIL", "INTERRUPTED", "RUNNING", "STALE", "QUEUED", "SOMETHING_NEW", None])
def test_an_overall_outside_blocked_and_error_is_never_re_decidable(overall):
    assert mg.transient_reasons(host_row(overall=overall)) == []
    assert mg.transient_reasons(dec(overall=overall, error="runner plan failed (merger.log)")) == []


def test_an_overall_error_needs_a_driver_text_even_beside_a_host_no_verdict():
    assert mg.transient_reasons(host_row(overall="ERROR", error="runner plan failed (merger.log)")) == ["host_disk", "error"]
    assert mg.transient_reasons(host_row(overall="ERROR", error=None)) == []
    assert mg.transient_reasons(host_row(overall="ERROR", error="status.json is bound to ('a', 'b', 'c'), not to this candidate, base and seal")) == []


@pytest.mark.parametrize("field", ["contexts", "checks", "host_no_verdict"])
@pytest.mark.parametrize("shape", [["x"], "x", 7, True])
def test_a_malformed_section_is_never_re_decidable(field, shape):
    row = host_row()
    row[field] = shape
    assert mg.transient_reasons(row) == []
    assert mg.transient_reasons({**driver_row(), field: shape}) == []


def test_an_absent_or_null_section_is_an_empty_one():
    assert mg.transient_reasons(driver_row(contexts=None, checks=None, host_no_verdict=None)) == ["error"]
    assert mg.transient_reasons(host_row(contexts=None, checks=None)) == ["host_disk"]


def test_a_blocked_row_with_no_class_is_not_transient():
    assert mg.transient_reasons(dec(overall="BLOCKED", error=None, contexts={"ctx.a": "OK"}, checks={"a": "PASS"})) == []


# ---- the four LOW gaps of gate-b30 r3

def test_the_backoff_counts_from_the_newest_decision_not_the_oldest():
    later = "2026-10-09T11:30:00Z"
    recs = [dec(ts=T0), dec(ts=later)]
    assert run(recs, now_s=mg._epoch(later) + mg.REDECIDE_BACKOFF_S * 2 - 1)[0] == []
    assert len(run(recs, now_s=mg._epoch(later) + mg.REDECIDE_BACKOFF_S * 2)[0]) == 1


def test_an_unreadable_decision_ts_is_not_made_due_by_an_eviction():
    assert run([dec(ts="unreadable")])[0] == []
    assert run([dec(ts="unreadable"), ev("2026-10-09T09:00:00Z")])[0] == []


def test_a_re_decide_key_sorts_behind_an_older_attempted_head():
    older = dec(pr=2, head=H2, base=B2, ts="2026-10-09T09:00:00Z", overall="PASS")   # H2 was decided at another base: attempted, oldest
    newer = dec(ts="2026-10-09T11:00:00Z")
    todo, _ = mg.triage([pr(1, H1), pr(2, H2)], REPO, [older, newer], B1, now_s=NOW)
    assert [p["number"] for p in todo] == [2, 1] and "_redecide" in todo[1] and "_redecide" not in todo[0]


def test_an_eviction_at_another_base_does_not_move_this_keys_backoff():
    recs = [dec(), ev("2026-10-09T11:55:00Z", base=B2)]
    assert len(run(recs)[0]) == 1


# ---- D2, the window: the cap is a RATE, an outage cannot cap every head for good, and it cannot become retry-until-green

def test_transient_decisions_inside_the_window_hit_the_cap():
    recs = [dec(ts=at(3600)), dec(ts=at(3000)), dec(ts=at(2400))]
    todo, capped = run(recs)
    assert todo == [] and [p["number"] for p in capped] == [1]


def test_a_transient_decision_older_than_the_window_stops_counting():
    recs = [dec(ts=at(mg.REDECIDE_WINDOW_S + 1)), dec(ts=at(3000)), dec(ts=at(2400))]
    todo, capped = run(recs)
    assert capped == [] and [p["_redecide"]["attempt"] for p in todo] == [3]


def test_a_decision_exactly_at_the_window_edge_still_counts():
    recs = [dec(ts=at(mg.REDECIDE_WINDOW_S)), dec(ts=at(3000)), dec(ts=at(2400))]
    assert run(recs)[1] != []


def test_a_key_whose_every_transient_decision_left_the_window_is_due_again():
    recs = [dec(ts=at(mg.REDECIDE_WINDOW_S + 7200 + i)) for i in range(5)]
    todo, capped = run(recs)
    assert capped == [] and [p["_redecide"]["attempt"] for p in todo] == [1]


def test_an_unreadable_decision_ts_counts_toward_the_cap():
    todo, capped = run([dec(ts="unreadable")] * mg.REDECIDE_CAP)
    assert todo == [] and [p["number"] for p in capped] == [1]


def test_the_backoff_counts_the_window_not_the_history():
    old = [dec(ts=at(mg.REDECIDE_WINDOW_S + 100 + i)) for i in range(2)]
    recent = dec(ts=at(mg.REDECIDE_BACKOFF_S))
    assert len(run([*old, recent])[0]) == 1   # one decision in the window: backoff 1 x 600, long due


def test_a_host_outage_retries_at_a_bounded_rate_and_never_stalls_for_good():
    recs, now, runs = [host_row(ts=T0)], mg._epoch(T0), []
    end = now + 4 * mg.REDECIDE_WINDOW_S
    while now < end:
        todo, _ = mg.triage([pr(1, H1)], REPO, recs, B1, now_s=now, host_free_gb=150.0, start_floor_gb=100.0, evict_capped=[], redecide_capped=[])
        if todo:
            runs.append(now)
            recs.append(host_row(ts=mg.time.strftime("%Y-%m-%dT%H:%M:%SZ", mg.time.gmtime(now))))
        now += 300
    assert len(runs) > mg.REDECIDE_CAP   # the queue heals after the window
    for i, t in enumerate(runs):
        assert sum(1 for u in runs if t - mg.REDECIDE_WINDOW_S < u <= t) <= mg.REDECIDE_CAP   # never more than the cap per window


def test_a_verdict_after_transient_decisions_stands_whatever_the_window():
    recs = [dec(ts=at(mg.REDECIDE_WINDOW_S + 1)), dec(ts=at(7200), overall="FAIL")]
    assert run(recs)[0] == []


def test_the_window_is_six_hours():
    assert mg.REDECIDE_WINDOW_S == 6 * 3600
    assert run([dec(ts=at(h * 3600)) for h in (5.5, 5, 4.5)])[1] != []
    todo, capped = run([dec(ts=at(h * 3600)) for h in (7, 6.5, 6.2)])
    assert capped == [] and [p["_redecide"]["attempt"] for p in todo] == [1]


def test_a_replay_row_is_never_transient_on_its_own():
    assert mg.transient_reasons(host_row(replay=True)) == []
    assert mg.transient_reasons(driver_row(replay=True)) == []
