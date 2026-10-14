"""B23: the lane goes to PRs that can merge — labelled first, nothing unlabelled under phase F, a gate-pending head waits for its gate."""
from __future__ import annotations

import pytest

from .test_merger import REPO, mg, pr, world  # noqa: F401 — `world` is a fixture
from .test_merger_phase_f import Hub, fw  # noqa: F401 — `fw` is a fixture

H1, H2, H3 = "1" * 40, "2" * 40, "3" * 40
B1, B2 = "b" * 40, "c" * 40
GATE = "Harness floor recompute"


def labelled(n, head, created):
    return pr(n, head, armed=False, labels=[mg.ARM_LABEL], created=created)


def plain(n, head, created):
    return pr(n, head, armed=True, created=created)


def order(prs, recs=(), gate=lambda n, h, names: True, **kw):
    todo, _ = mg.triage(prs, REPO, list(recs), B1, gate, **kw)
    return [p["number"] for p in todo]


def test_a_labelled_pr_is_picked_before_an_older_unlabelled_one():
    assert order([plain(1, H1, "2026-10-01T00:00:00Z"), labelled(2, H2, "2026-10-05T00:00:00Z")]) == [2, 1]


def test_the_old_order_holds_inside_each_group():
    prs = [plain(1, H1, "2026-10-03T00:00:00Z"), labelled(2, H2, "2026-10-04T00:00:00Z"), plain(3, H3, "2026-10-01T00:00:00Z"),
           labelled(4, "4" * 40, "2026-10-02T00:00:00Z")]
    assert order(prs) == [4, 2, 3, 1]   # created_at inside each group
    seen = [{"kind": "decision", "pr": 4, "head_sha": "4" * 40, "base_sha": "a" * 40, "ts": "2026-10-09T00:00:00Z", "overall": "PASS"}]
    assert order(prs, seen) == [2, 4, 3, 1]   # a head never decided first, then the oldest last decision


def test_under_phase_f_an_unlabelled_pr_is_never_picked(monkeypatch):
    prs = [plain(1, H1, "2026-10-01T00:00:00Z"), labelled(2, H2, "2026-10-05T00:00:00Z")]
    monkeypatch.setenv(mg.PHASE_F_ENV, "1")
    assert order(prs) == [2]
    monkeypatch.delenv(mg.PHASE_F_ENV)
    assert order(prs) == [2, 1]
    monkeypatch.setenv(mg.PHASE_F_ENV, "0")
    assert order(prs) == [2, 1]


def test_a_fork_pr_is_still_journalled_under_phase_f_even_unlabelled(monkeypatch):
    monkeypatch.setenv(mg.PHASE_F_ENV, "1")
    _, forks = mg.triage([pr(9, H1, fork=True)], REPO, [], B1, None)
    assert [p["number"] for p in forks] == [9]


def dec(base=B1, pending=True, **kw):
    mark = {"gate_pending": True, "gate_pending_contexts": [GATE]} if pending else {}
    return {"kind": "decision", "pr": 1, "head_sha": H1, "base_sha": base, "ts": "2026-10-09T10:00:00Z", "overall": "BLOCKED", **mark, **kw}


def test_a_gate_pending_head_is_not_decided_at_a_new_base_until_its_gate_is_ready():
    seen, deferred = [], []
    ready = {"v": False}

    def gate(n, head, names):
        seen.append((n, head, tuple(names)))
        return ready["v"]
    prs = [plain(1, H1, "2026-10-01T00:00:00Z")]
    assert order(prs, [dec(base=B2)], gate, deferred=deferred) == [] and [p["number"] for p in deferred] == [1] and seen == [(1, H1, (GATE,))]
    ready["v"] = True
    assert order(prs, [dec(base=B2)], gate) == [1]


def test_a_failed_gate_read_means_deferred(capsys):
    def gate(n, head, names):
        raise mg.hc.CompareError("gh down")
    deferred: list = []
    assert order([plain(1, H1, "2026-10-01T00:00:00Z")], [dec(base=B2)], gate, deferred=deferred) == [] and len(deferred) == 1
    assert "not read" in capsys.readouterr().err
    assert order([plain(1, H1, "2026-10-01T00:00:00Z")], [dec(base=B2)], None) == []   # no callable: deferred too


def test_only_the_newest_decision_of_the_head_defers_and_a_replay_does_not_count():
    prs = [plain(1, H1, "2026-10-01T00:00:00Z")]
    never = lambda n, h, names: False  # noqa: E731
    assert order(prs, [dec(base=B2), dec(base="d" * 40, pending=False)], never) == [1]
    assert order(prs, [dec(base=B2), dec(base="d" * 40, pending=False, replay=True, merge_commit="e" * 40)], never) == []
    assert order(prs, [dec(base=B2, overall="FAIL")], never) == [1]
    assert order([plain(1, H2, "2026-10-01T00:00:00Z")], [dec(base=B2)], never) == [1]   # another head is another key


def test_b12s_own_same_key_redecision_and_cap_are_unchanged():
    capped: list = []
    assert order([plain(1, H1, "2026-10-01T00:00:00Z")], [dec()], lambda n, h, names: True) == [1]
    assert order([plain(1, H1, "2026-10-01T00:00:00Z")], [dec(), dec(), dec()], lambda n, h, names: True, capped=capped) == [] and len(capped) == 1


def test_the_skip_is_journalled_once_per_head_across_ticks_and_bases(fw, monkeypatch):
    monkeypatch.delenv(mg.PHASE_F_ENV)
    fw.gh.prs = [pr(1, fw.head1, armed=False, labels=[mg.ARM_LABEL])]
    mg.journal(fw.state, dec(base="a" * 40) | {"head_sha": fw.head1})
    monkeypatch.setattr(mg, "gate_ready", lambda repo, head, names: False)
    for _ in range(3):
        assert fw.tick() == 0
    skips = [r for r in fw.live() if r.get("why") == "gate_pending_deferred"]
    assert len(skips) == 1 and skips[0]["pr"] == 1 and skips[0]["head_sha"] == fw.head1
    assert [r for r in fw.live() if r["kind"] == "decision"] == [r for r in fw.live() if r["kind"] == "decision" and r["base_sha"] == "a" * 40]
    assert fw.runner.calls == []
