"""B28: a waiting labelled PR is decided before a replay; a replay runs on a tick with no labelled PR selectable, and a starvation bound
makes sure replays are not starved. The B11 fixture (real git, GitHub faked) is reused."""
from __future__ import annotations

import json
import time

import pytest

from .test_merger import mg, pr
from .test_replay import rw  # noqa: F401 — `rw` is a fixture

LABEL = [mg.ARM_LABEL]


def labelled(w, *ns):
    w.gh.prs = [pr(n, w.heads[n], labels=LABEL, created=f"2026-10-0{n % 9 + 1}T00:00:00Z") for n in ns]


def shape(w):
    return [(bool(d.get("replay")), d["pr"]) for d in w.decisions()]


def kinds(w, kind):
    return [r for r in mg.read_journal(w.state) if r["kind"] == kind]


def add_deferrals(w, n, ago_s=0):
    with (w.state / "decisions.jsonl").open("a") as fh:
        for i in range(n):
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - ago_s))
            fh.write(json.dumps({"kind": "replay_deferred", "ts": ts, "reason": "a labelled PR is waiting", "skipped_n": i + 1, "pr": 3}, sort_keys=True) + "\n")


def test_a_selectable_labelled_pr_is_decided_before_a_replay_and_the_deferral_is_journalled(rw):
    labelled(rw, 3, 4)
    for _ in range(5):
        assert rw.tick() == 0
    assert shape(rw) == [(False, 3), (False, 4), (True, 12), (True, 11)]   # both PRs first, the replays in the gap, nothing left to do
    assert [(r["skipped_n"], r["pr"]) for r in kinds(rw, "replay_deferred")] == [(1, 4)]   # before the first PR decision there is no replay to forfeit
    assert [d["schedule"] for d in rw.decisions() if d.get("replay")] == ["alternation: the previous decision was not a replay", "no pull request to decide"]


def test_without_a_labelled_pr_the_alternation_is_what_it_was(rw):
    for _ in range(5):
        assert rw.tick() == 0
    assert shape(rw) == [(False, 3), (True, 12), (False, 4), (True, 11)] and kinds(rw, "replay_deferred") == []


def test_a_labelled_pr_the_gate_defers_does_not_block_the_replay(rw, monkeypatch):
    labelled(rw, 3)
    rw.state.mkdir(parents=True)
    with (rw.state / "decisions.jsonl").open("a") as fh:   # PR 3 was decided at another base while the gate verdict was not posted
        fh.write(json.dumps({"kind": "decision", "ts": mg.now(), "pr": 3, "head_sha": rw.heads[3], "base_sha": "e" * 40, "overall": "BLOCKED",
                             "gate_pending": True, "gate_pending_contexts": ["ctx.harness-floor"]}, sort_keys=True) + "\n")
    monkeypatch.setattr(mg, "gate_ready", lambda *a, **kw: False)
    assert rw.tick() == 0
    assert shape(rw)[-1] == (True, 12) and kinds(rw, "replay_deferred") == [] and [r for r in kinds(rw, "skipped") if r["why"] == "gate_pending_deferred"]


def test_after_the_skip_bound_one_replay_runs_though_a_labelled_pr_waits_and_the_count_starts_again(rw):
    labelled(rw, 3)
    assert rw.tick() == 0   # PR 3 decided: no replay exists before a first PR decision
    add_deferrals(rw, mg.REPLAY_MAX_SKIP)   # six forfeited replay turns
    labelled(rw, 4)
    assert rw.tick() == 0   # six deferred: the bound's replay runs, PR 4 still waits
    ds = rw.decisions()
    assert ds[-1].get("replay") and ds[-1]["schedule"].startswith(f"starvation bound: {mg.REPLAY_MAX_SKIP}") and ds[-1]["pr"] == 12
    assert len(kinds(rw, "replay_deferred")) == mg.REPLAY_MAX_SKIP   # the forced turn defers nothing
    assert mg.replay_skips(mg.read_journal(rw.state)) == (0, None)   # the replay put the count back to zero
    assert rw.tick() == 0 and shape(rw)[-1] == (False, 4)   # the PR is decided on the turn after the replay


def test_one_deferral_short_of_the_skip_bound_still_defers(rw):
    labelled(rw, 3)
    assert rw.tick() == 0
    add_deferrals(rw, mg.REPLAY_MAX_SKIP - 1)   # five
    labelled(rw, 4)
    assert rw.tick() == 0 and shape(rw)[-1] == (False, 4) and kinds(rw, "replay_deferred")[-1]["skipped_n"] == mg.REPLAY_MAX_SKIP


def test_after_the_skip_age_one_replay_runs_though_few_were_deferred(rw):
    labelled(rw, 3)
    assert rw.tick() == 0
    add_deferrals(rw, 1, ago_s=mg.REPLAY_MAX_SKIP_S + 60)
    labelled(rw, 4)
    assert rw.tick() == 0
    assert shape(rw)[-1] == (True, 12) and rw.decisions()[-1]["schedule"].startswith("starvation bound")
    assert mg.replay_skips(mg.read_journal(rw.state)) == (0, None)


def test_the_age_bound_does_not_fire_early(rw):
    labelled(rw, 3)
    assert rw.tick() == 0
    add_deferrals(rw, 1, ago_s=mg.REPLAY_MAX_SKIP_S - 600)
    labelled(rw, 4)
    assert rw.tick() == 0 and shape(rw)[-1] == (False, 4)


def test_a_bound_turn_with_nothing_to_replay_resets_the_count_and_the_pr_is_decided(rw, monkeypatch):
    labelled(rw, 3)
    assert rw.tick() == 0
    add_deferrals(rw, mg.REPLAY_MAX_SKIP)
    monkeypatch.setattr(mg, "replay_pending", lambda *a, **kw: None)
    labelled(rw, 4)
    assert rw.tick() == 0
    assert shape(rw)[-1] == (False, 4) and [r["why"] for r in kinds(rw, "skipped")][-1] == "replay_none"
    assert mg.replay_skips(mg.read_journal(rw.state)) == (0, None)


def test_with_phase_f_armed_nothing_changes_replays_stay_off_and_no_deferral_is_journalled(rw, monkeypatch):
    monkeypatch.setenv(mg.PHASE_F_ENV, "1")
    labelled(rw, 3, 4)
    for _ in range(4):
        assert rw.tick() == 0
    assert shape(rw) == [(False, 3), (False, 4)] and kinds(rw, "replay_deferred") == []


def test_replay_skips_counts_since_the_newest_replay_or_replay_none():
    base = {"ts": "2026-10-15T00:00:00Z"}
    rows = [{**base, "kind": "replay_deferred"}, {**base, "kind": "replay_deferred"}, {**base, "kind": "decision", "replay": True}, {**base, "kind": "replay_deferred"}]
    assert mg.replay_skips(rows) == (1, mg._epoch("2026-10-15T00:00:00Z"))
    assert mg.replay_skips(rows + [{**base, "kind": "skipped", "why": "replay_none"}]) == (0, None)
    assert mg.replay_skips([{**base, "kind": "decision"}]) == (0, None)
