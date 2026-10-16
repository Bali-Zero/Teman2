"""B30 D2's window is a bounded RATE, never a stall and never an unbounded loop; transient_reasons is total."""
from __future__ import annotations

import itertools

import pytest

from .test_merger import REPO, mg, pr, world  # noqa: F401 — `world` is a fixture
from .test_redecide import B1, H1, T0, dec, ev

HOSTCTX = {"ctx.e2e-tests": "host_disk_below_floor 80GB<100GB"}
H = 3600


def host_row(ts):
    return dec(ts=ts, overall="BLOCKED", error=None, host_no_verdict=dict(HOSTCTX), contexts={"ctx.e2e-tests": "ERROR", "ctx.a": "OK"},
               checks={"e2e": "ERROR", "a": "PASS"}, host_checks=["e2e"])


def iso(t):
    return mg.time.strftime("%Y-%m-%dT%H:%M:%SZ", mg.time.gmtime(t))


def simulate(first, horizon_h=72, durations=(600, 3600, 5400, 300, 4200), evict_every=0, free=150.0, floor=100.0, then=None):
    """Ticks every 300 s; a selected key runs for the next duration and journals a transient decision (or an eviction) at its END."""
    t0 = mg._epoch(T0)
    recs, now, runs, dur = [first], t0 + 1, [], itertools.cycle(durations)
    end = t0 + horizon_h * H
    while now < end:
        todo, _ = mg.triage([pr(1, H1)], REPO, recs, B1, now_s=now, host_free_gb=free, start_floor_gb=floor, evict_capped=[], redecide_capped=[])
        if todo:
            d = next(dur)
            runs.append((now, todo[0]["_redecide"]["attempt"]))
            if evict_every and len(runs) % evict_every == 0:
                recs.append(ev(iso(now + d)))
            else:
                recs.append((then or host_row)(iso(now + d)))
            now += d
        now += 300
    return recs, runs


def per_window(ts_list, window):
    return max((sum(1 for u in ts_list if t - window < u <= t) for t in ts_list), default=0)


@pytest.mark.parametrize("evict_every", [0, 2, 3])
def test_the_window_bounds_the_rate_and_never_stalls(evict_every):
    recs, runs = simulate(host_row(T0), evict_every=evict_every)
    decs = [mg._epoch(r["ts"]) for r in recs if r["kind"] == "decision"]
    evs = [mg._epoch(r["ts"]) for r in recs if r["kind"] == "evicted"]
    assert per_window(decs, mg.REDECIDE_WINDOW_S) <= mg.REDECIDE_CAP
    assert per_window(evs, mg.EVICT_WINDOW_S) <= mg.EVICT_CAP
    assert len(decs) <= mg.REDECIDE_CAP * (72 // 6 + 1)
    assert len(runs) >= 72 // 6   # an outage never caps the key for good: at least one attempt per window


@pytest.mark.parametrize("free,floor", [(None, 100.0), (99.9, 100.0), (0.0, 0.1)])
def test_a_host_disk_key_never_runs_below_or_without_a_measured_floor(free, floor):
    _, runs = simulate(host_row(T0), free=free, floor=floor)
    assert runs == []


def test_a_verdict_after_the_window_stands_for_good():
    fail = lambda ts: dec(ts=ts, overall="FAIL", error=None, contexts={"ctx.a": "FAIL"}, checks={"a": "FAIL"})  # noqa: E731
    recs, runs = simulate(host_row(T0), then=fail)
    assert len(runs) == 1 and recs[-1]["overall"] == "FAIL"


@pytest.mark.parametrize("err", ["status.json is bound to ('a', 'b', None), not to this candidate, base and seal", "tick exceeded --tick-timeout 14400s"])
def test_a_seal_mismatch_or_tick_timeout_is_never_run_again_over_three_days(err):
    _, runs = simulate(dec(ts=T0, overall="ERROR", error=err, contexts={}, checks={}))
    assert runs == []


VOCAB = ["OK", "UNCOVERED", "QUEUED", "FAIL", "BLOCKED", "ERROR", "STALE", "INTERRUPTED", "RUNNING", "PASS", "NOT_APPLICABLE", "SUBSET_PASS", "", None, 7]


def test_transient_reasons_is_total_and_never_admits_a_candidate_status():
    """Every overall x context x check status of the vocabulary, with and without a host no-verdict and its attribution: never raises, never admits FAIL, INTERRUPTED, RUNNING, STALE."""
    for overall, cv, kv, host, named in itertools.product(VOCAB, VOCAB, VOCAB, (None, {"c": "host_disk_below_floor 1GB<2GB"}), (None, ["k"])):
        r = {"overall": overall, "error": "runner plan failed (x)" if overall == "ERROR" else None, "contexts": {"c": cv, "d": cv}, "checks": {"k": kv},
             "host_no_verdict": host, "host_checks": named}
        why = mg.transient_reasons(r)   # triage calls it on every journal row
        if why:
            assert overall in ("BLOCKED", "ERROR")
            assert not {cv, kv} & {"FAIL", "INTERRUPTED", "RUNNING", "STALE"}
            assert isinstance(cv, str) and isinstance(kv, str)
            assert kv != "ERROR" or (host and named and "k" in named)
