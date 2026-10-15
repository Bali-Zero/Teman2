"""B30: a transient local no-verdict is decided again at the same (pr, head, base); a verdict never is."""
from __future__ import annotations

import pytest

from .test_merger import REPO, mg, pr, world  # noqa: F401 — `world` is a fixture

H1, H2 = "1" * 40, "2" * 40
B1, B2 = "b" * 40, "c" * 40
T0 = "2026-10-09T10:00:00Z"
NOW = mg._epoch("2026-10-09T12:00:00Z")   # two hours after T0: past any backoff of the first three attempts
HOST = {"host_no_verdict": {"ctx.e2e-tests": "host_disk_below_floor"}, "contexts": {"ctx.e2e-tests": "ERROR"}, "overall": "BLOCKED"}


def dec(head=H1, base=B1, ts=T0, **kw):
    return {"kind": "decision", "pr": 1, "head_sha": head, "base_sha": base, "ts": ts, "overall": "ERROR", **kw}


def run(recs, prs=None, **kw):
    capped: list = []
    todo, _ = mg.triage(prs or [pr(1, H1)], REPO, list(recs), B1, now_s=kw.pop("now_s", NOW), redecide_capped=capped, **kw)
    return todo, capped


@pytest.mark.parametrize("rec,reason", [
    (dec(), "error"),                                                                   # overall ERROR
    (dec(overall="INTERRUPTED"), "interrupted"),                                        # the run budget
    (dec(overall="BLOCKED", checks={"x": "INTERRUPTED"}), "interrupted"),
    (dec(**HOST), "host_disk"),
])
def test_each_transient_class_is_decided_again_at_the_same_base(rec, reason):
    todo, capped = run([rec], host_free_gb=120.0, start_floor_gb=100.0)
    assert [p["number"] for p in todo] == [1] and capped == []
    assert todo[0]["_redecide"] == {"reason": reason, "attempt": 2}


@pytest.mark.parametrize("rec", [
    dec(overall="FAIL"),                                                                # a real red
    dec(overall="BLOCKED", contexts={"ctx.a": "FAIL", "ctx.b": "ERROR"}),               # a FAIL beside an ERROR is still a FAIL
    dec(overall="BLOCKED", contexts={"ctx.a": "BLOCKED"}),                              # BLOCKED from policy
    dec(overall="ERROR", contexts={"ctx.a": "BLOCKED"}),
    dec(overall="BLOCKED", non_executed={"ctx.a": "blocked"}),
    dec(overall="BLOCKED", **{"host_no_verdict": {"ctx.a": "host_disk_full"}, "contexts": {"ctx.a": "ERROR", "ctx.b": "BLOCKED"}}),   # host plus a policy BLOCKED
    dec(overall="PASS"),
    dec(overall="BLOCKED", gate_pending=True, gate_pending_contexts=["x"]),            # B12's, not B30's
    dec(overall="BLOCKED", gate_pending=True, contexts={"ctx.a": "ERROR"}),            # gate_pending without a readable name list: still not B30's
    dec(overall="FAIL", **{"host_no_verdict": {"ctx.a": "host_disk_full"}, "contexts": {"ctx.a": "ERROR"}}),   # a FAIL overall outranks any no-verdict
    dec(overall="ERROR", non_executed={"ctx.a": "blocked"}),                            # an ERROR beside a non-executed mapping
    dec(overall="BLOCKED", contexts={"ctx.a": "ERROR", "ctx.b": "OK"}),                 # B2: a context ERROR may be the candidate's crash, hang or collection error
    dec(overall="ERROR", contexts={"ctx.a": "ERROR"}),
    dec(overall="INTERRUPTED", contexts={"ctx.a": "ERROR"}),
    dec(overall="BLOCKED", checks={"x": "INTERRUPTED", "y": "ERROR"}),                  # a candidate timeout beside a run-budget interruption
    dec(overall="ERROR", contexts={"ctx.a": "FAIL"}),                                   # a FAIL context under a transient overall
    dec(overall="INTERRUPTED", contexts={"ctx.a": "FAIL"}),
    dec(overall="BLOCKED", gate_pending=True, gate_pending_contexts=["x"], host_no_verdict={"ctx.e2e-tests": "host_disk_below_floor"}, contexts={"ctx.e2e-tests": "ERROR"}),     # gate_pending beside a host no-verdict
    dec(overall="INTERRUPTED", gate_pending=True),
    dec(overall="ERROR", checks={"x": "FAIL"}),                                         # L1: a FAIL check is a verdict
    dec(overall="INTERRUPTED", checks={"x": "FAIL", "y": "INTERRUPTED"}),
    dec(overall="BLOCKED", **{"host_no_verdict": {"ctx.a": "host_disk_full"}, "contexts": {"ctx.a": "ERROR", "ctx.b": "ERROR"}}),   # host plus a candidate-side ERROR
])
def test_a_verdict_is_never_decided_again(rec):
    todo, capped = run([rec], host_free_gb=120.0, start_floor_gb=100.0)
    assert todo == [] and capped == []


def test_a_replay_row_is_not_a_decision_of_the_key():
    todo, _ = run([dec(replay=True, merge_commit="e" * 40)])
    assert [p["number"] for p in todo] == [1] and "_redecide" not in todo[0]   # the key was never decided: an ordinary pick


def test_the_cap_leaves_the_key_decided_and_is_reported():
    todo, capped = run([dec(), dec(), dec()])
    assert todo == [] and [p["number"] for p in capped] == [1]
    todo, capped = run([dec(), dec()])
    assert [p["number"] for p in todo] == [1] and todo[0]["_redecide"]["attempt"] == 3 and capped == []
    todo, _ = mg.triage([pr(1, H1)], REPO, [dec(), dec(), dec()], B2, now_s=NOW)
    assert [p["number"] for p in todo] == [1] and "_redecide" not in todo[0]   # another base is a fresh key


def test_the_backoff_grows_with_the_count():
    first = mg._epoch(T0)
    assert run([dec()], now_s=first + mg.REDECIDE_BACKOFF_S - 1)[0] == []
    assert len(run([dec()], now_s=first + mg.REDECIDE_BACKOFF_S)[0]) == 1
    assert run([dec(), dec()], now_s=first + mg.REDECIDE_BACKOFF_S * 2 - 1)[0] == []
    assert len(run([dec(), dec()], now_s=first + mg.REDECIDE_BACKOFF_S * 2)[0]) == 1
    assert run([dec(ts="unreadable")])[0] == []   # an unreadable ts is not due


def test_a_host_disk_key_waits_for_the_floor_then_is_decided_again_once_and_the_second_decision_stands():
    recs = [dec(**HOST)]
    assert run(recs, host_free_gb=99.0, start_floor_gb=100.0)[0] == []     # still below the floor: next tick
    assert run(recs, host_free_gb=None, start_floor_gb=100.0)[0] == []     # unmeasured: not due
    assert run(recs, start_floor_gb=100.0)[0] == []
    todo, _ = run(recs, host_free_gb=100.0, start_floor_gb=100.0)
    assert [p["_redecide"]["reason"] for p in todo] == ["host_disk"]
    standing = [*recs, dec(ts="2026-10-09T11:00:00Z", overall="PASS")]
    assert run(standing, host_free_gb=150.0, start_floor_gb=100.0)[0] == []   # the second decision is a verdict: it stands
    standing = [*recs, dec(ts="2026-10-09T11:00:00Z", overall="FAIL")]
    assert run(standing, host_free_gb=150.0, start_floor_gb=100.0)[0] == []


def test_only_the_newest_decision_of_the_key_counts():
    assert run([dec(overall="PASS", ts="2026-10-09T09:00:00Z"), dec()])[0] != []
    assert run([dec(), dec(overall="PASS", ts="2026-10-09T11:00:00Z")])[0] == []


def test_a_key_due_again_sorts_behind_a_head_never_decided_and_does_not_hide_it():
    prs = [pr(1, H1, created="2026-10-01T00:00:00Z"), pr(2, H2, created="2026-10-05T00:00:00Z")]
    todo, _ = mg.triage(prs, REPO, [dec()], B1, now_s=NOW)
    assert [p["number"] for p in todo] == [2, 1]


def test_the_tick_decides_the_key_again_with_the_redecide_row_and_journals_the_cap_once(world):  # noqa: F811
    world.gh.prs = [pr(1, world.head1)]
    world.state.mkdir(parents=True, exist_ok=True)
    mg.journal(world.state, dec(head=world.head1, base=world.base, overall="ERROR"))
    assert world.tick() == 0
    rows = [r for r in world.journal() if r["kind"] == "decision"]
    assert len(rows) == 2 and rows[-1]["redecide"] == {"reason": "error", "attempt": 2} and "redecide" not in rows[0]
    for _ in range(2):
        mg.journal(world.state, dec(head=world.head1, base=world.base, overall="ERROR", ts="2026-10-09T10:01:00Z"))
    assert world.tick() == 0 and world.tick() == 0
    skips = [r for r in world.journal() if r["kind"] == "skipped" and r["why"] == "redecide_cap"]
    assert len(skips) == 1 and skips[0]["pr"] == 1


def test_the_tick_hands_the_measured_host_free_space_to_the_triage(world):  # noqa: F811
    world.gh.prs = [pr(1, world.head1)]
    world.state.mkdir(parents=True, exist_ok=True)
    mg.journal(world.state, dec(head=world.head1, base=world.base, **HOST))
    args = ["tick", "--node", mg.HOST, "--repo", REPO, "--state-dir", str(world.state), "--remote-url", str(world.origin), "--python", "py"]
    assert mg.main([*args, "--host-free-gb=150", "--min-host-free-gb=100"]) == 0
    rows = [r for r in world.journal() if r["kind"] == "decision"]
    assert len(rows) == 2 and rows[-1]["redecide"] == {"reason": "host_disk", "attempt": 2}


def ev(ts, head=H1, base=B1):
    return {"kind": "evicted", "pr": 1, "head_sha": head, "base_sha": base, "ts": ts}


def test_the_eviction_cap_applies_to_a_transient_key_too_within_its_window():
    recs = [dec(**HOST), *[ev("2026-10-09T11:00:00Z")] * mg.EVICT_CAP]
    capped, evict_capped = [], []
    todo, _ = mg.triage([pr(1, H1)], REPO, recs, B1, now_s=NOW, host_free_gb=150.0, start_floor_gb=100.0, redecide_capped=capped, evict_capped=evict_capped)
    assert todo == [] and capped == [] and [p["number"] for p in evict_capped] == [1]
    one_short = [dec(**HOST), *[ev("2026-10-09T11:00:00Z")] * (mg.EVICT_CAP - 1)]
    assert run(one_short, now_s=mg._epoch("2026-10-09T11:00:00Z") + mg.REDECIDE_BACKOFF_S, host_free_gb=150.0, start_floor_gb=100.0)[0] != []
    stale = [dec(**HOST), *[ev("2026-10-01T00:00:00Z")] * mg.EVICT_CAP]   # older than the window: history for ORDER, never a cap
    assert run(stale, host_free_gb=150.0, start_floor_gb=100.0)[0] != []


def test_an_eviction_pushes_the_next_attempt_by_the_backoff():
    ev_ts = "2026-10-09T11:55:00Z"
    recs = [dec(), ev(ev_ts)]
    assert run(recs, now_s=mg._epoch(ev_ts) + mg.REDECIDE_BACKOFF_S - 1)[0] == []    # the decision alone would be long due
    assert len(run(recs, now_s=mg._epoch(ev_ts) + mg.REDECIDE_BACKOFF_S)[0]) == 1
    assert len(run([dec()], now_s=mg._epoch(ev_ts) + 1)[0]) == 1                      # without the eviction it is due


def test_the_newest_eviction_anchors_the_backoff_not_the_oldest():
    recs = [dec(), ev("2026-10-09T11:00:00Z"), ev("2026-10-09T11:50:00Z")]
    assert run(recs, now_s=mg._epoch("2026-10-09T11:50:00Z") + mg.REDECIDE_BACKOFF_S - 1)[0] == []
    assert len(run(recs, now_s=mg._epoch("2026-10-09T11:50:00Z") + mg.REDECIDE_BACKOFF_S)[0]) == 1
