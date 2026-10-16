"""B19: a LocalCI PASS refused only for a term that changes with time waits and is retried; it is not spent. Real git, GitHub faked."""
from __future__ import annotations

import argparse
import re

import pytest

from .test_merger import REPO, mg, pr, world  # noqa: F401 — `world` is a fixture
from .test_merger_phase_f import Hub, armed_by_cache, fw, assert_nothing_merged  # noqa: F401 — `fw` is a fixture

@pytest.fixture(autouse=True)
def watchdog_reset():
    mg._WATCHDOG["fired"] = False
    yield
    mg._WATCHDOG["fired"] = False


H1, H2, B0 = "a" * 40, "b" * 40, "c" * 40
T0 = "2026-10-14T00:00:00Z"


def toggle(fw, monkeypatch):
    """Hosted CI of the PR head: in progress until ``state['green']``."""
    state = {"green": False}

    def get(path):
        out = fw.hub(path)
        if not state["green"] and re.fullmatch(rf"repos/{REPO}/commits/{fw.head1}/check-runs\?per_page=100&page=1", path):
            out = {"check_runs": [{**c, "status": "in_progress", "conclusion": None} for c in out["check_runs"]]}
        return out
    monkeypatch.setattr(mg.hc, "gh_get", get)
    monkeypatch.setattr(mg, "PENDING_RETRY_S", 0)
    return state


def args():
    return argparse.Namespace(repo=REPO, base="main")


def retry(fw, *, base=None, prs=None):
    return mg.retry_pending_merges(args(), fw.state, fw.mirror, "lease-r", fw.journal(), base or fw.base, fw.gh.prs if prs is None else prs)


def rows(fw, kind, retry_=True):
    return [r for r in fw.live() if r["kind"] == kind and bool(r.get("retry")) is retry_]


def decided_while_hosted_pends(fw, monkeypatch):
    state = toggle(fw, monkeypatch)
    assert fw.tick() == 0
    assert [k for k in fw.kinds() if k != "replay_deferred"] == ["decision", "would_enqueue", "would_merge"]   # B28 may journal the forfeited replay turn in shadow
    enq = next(r for r in fw.live() if r["kind"] == "would_enqueue")
    assert enq["ok"] is False and "hosted_required_green" in enq["refused"] and fw.wm()["phase_f"]["armed"] is False
    return state


# ------------------------------------------------------------------ the retry itself
def test_a_pass_refused_only_for_pending_hosted_is_retried_next_tick_and_merged_exactly_once_when_phase_f_is_armed(fw, monkeypatch):
    state = decided_while_hosted_pends(fw, monkeypatch)
    state["green"] = True
    assert fw.tick() == 0
    assert fw.kinds() == ["decision", "would_enqueue", "would_merge", "would_enqueue", "would_merge", "merged", "pushed"]
    enq, wm = rows(fw, "would_enqueue")[0], rows(fw, "would_merge")[0]
    decision = next(r for r in fw.live() if r["kind"] == "decision")
    assert enq["ok"] is True and enq["retry"] is True and enq["decision_ts"] == decision["ts"] and "decision" not in [r["kind"] for r in fw.live()][1:]
    assert wm["retry"] is True and armed_by_cache(wm["phase_f"])
    assert len(fw.pushes) == 1 and fw.origin_main() == fw.journal()[-1]["merge_commit"]
    assert fw.journal()[-2]["decision_ts"] == decision["ts"]
    assert fw.runner.calls and len([c for c in fw.runner.calls if c["sub"] == "plan"]) == 1   # no new run for the same key
    assert fw.tick() == 0   # the base moved by the merge: nothing pending, nothing to decide
    assert len(fw.pushes) == 1


def test_in_shadow_the_retry_journals_the_measurement_and_changes_nothing_on_github(fw, monkeypatch):
    monkeypatch.delenv(mg.PHASE_F_ENV)
    state = decided_while_hosted_pends(fw, monkeypatch)
    state["green"] = True
    assert fw.tick() == 0
    assert [k for k in fw.kinds() if k != "replay_deferred"] == ["decision", "would_enqueue", "would_merge", "would_enqueue", "would_merge"]
    enq, wm = rows(fw, "would_enqueue")[0], rows(fw, "would_merge")[0]
    assert enq["ok"] is True and wm["retry"] is True and wm["phase_f"]["armed"] is False and wm["ok"] is True
    assert_nothing_merged(fw)
    assert fw.gql.mutations() == []


def test_a_key_still_hosted_pending_is_retried_each_interval_and_never_decided_again(fw, monkeypatch):
    decided_while_hosted_pends(fw, monkeypatch)
    for _ in range(2):
        assert fw.tick() == 0
    assert fw.kinds().count("decision") == 1 and len(rows(fw, "would_enqueue")) == 2 and not set(fw.kinds()) & {"merged", "pushed"}
    assert len([c for c in fw.runner.calls if c["sub"] == "plan"]) == 1


# ------------------------------------------------------------------ when the key is not pending, or not due
def test_no_retry_when_the_base_moved_the_head_moved_or_the_pr_is_gone(fw, monkeypatch):
    state = decided_while_hosted_pends(fw, monkeypatch)
    state["green"] = True
    n = len(fw.journal())
    assert retry(fw, base="e" * 40) is False
    assert retry(fw, prs=[pr(1, "d" * 40, armed=False, labels=[mg.ARM_LABEL])]) is False
    assert retry(fw, prs=[]) is False
    assert len(fw.journal()) == n


def test_no_retry_once_the_key_has_merged_or_pushed(fw, monkeypatch):
    state = decided_while_hosted_pends(fw, monkeypatch)
    state["green"] = True
    mg.journal(fw.state, {"kind": "merged", "pr": 1, "head_sha": fw.head1, "base_sha": fw.base})
    n = len(fw.journal())
    assert retry(fw) is False and len(fw.journal()) == n


def test_no_retry_within_the_interval(fw, monkeypatch):
    state = decided_while_hosted_pends(fw, monkeypatch)
    monkeypatch.setattr(mg, "PENDING_RETRY_S", 900)
    state["green"] = True
    n = len(fw.journal())
    assert retry(fw) is False and len(fw.journal()) == n


def test_after_the_ttl_the_key_is_journalled_expired_once_and_never_retried(fw, monkeypatch):
    state = decided_while_hosted_pends(fw, monkeypatch)
    state["green"] = True
    real = mg.time.time()
    with monkeypatch.context() as m:
        m.setattr(mg.time, "time", lambda: real + mg.PENDING_TTL_S + 5)
        assert retry(fw) is False and retry(fw) is False
    assert [r["why"] for r in fw.live() if r["kind"] == "skipped"] == ["pending_expired"] and rows(fw, "would_enqueue") == []
    assert retry(fw) is False and rows(fw, "would_enqueue") == []


# ------------------------------------------------------------------ what is never pending
def good(over=None):
    crit = dict.fromkeys(mg.CRITERION, True)
    recs = [{"kind": "decision", "ts": T0, "pr": 1, "head_sha": H1, "base_sha": B0, "overall": "BLOCKED", "candidate_sha": "9" * 40},
            {"kind": "would_enqueue", "ts": T0, "pr": 1, "head_sha": H1, "base_sha": B0, "ok": False, "criterion": {**crit, "hosted_required_green": False},
             "executed_required": "1/1", "non_executed": {}, "partial": {}, "host_no_verdict": {}},
            {"kind": "would_merge", "ts": T0, "pr": 1, "head_sha": H1, "base_sha": B0, "clean": True, "ok": False, "phase_f": {"armed": False, "why": ["x"]}}]
    for i, d in (over or {}).items():
        recs[i] = {**recs[i], **d}
    return recs


def test_the_pending_predicate_has_exactly_the_stated_shape():
    assert list(mg.pending_merges(good())) == [(1, H1, B0)]
    bad = [
        {0: {"overall": "CONFLICT"}}, {0: {"overall": "ERROR"}}, {0: {"overall": "FAIL"}}, {0: {"replay": True}}, {0: {"gate_pending": True}},
        {1: {"criterion": {**dict.fromkeys(mg.CRITERION, True), "local_checks_clean": False}}},
        {1: {"criterion": {**dict.fromkeys(mg.CRITERION, True), "review_independent": False}}},
        {1: {"criterion": {**dict.fromkeys(mg.CRITERION, True), "executed_contexts_ok": False}}},
        {1: {"criterion": {**dict.fromkeys(mg.CRITERION, True), "same_repo": False}}},
        {1: {"kind": "enqueue_refused"}}, {2: {"clean": False}}, {2: {"phase_f": {"armed": True, "why": []}}},
    ]
    for over in bad:
        assert mg.pending_merges(good(over)) == {}, over
    for kind in ("merged", "pushed"):
        assert mg.pending_merges([*good(), {"kind": kind, "pr": 1, "head_sha": H1, "base_sha": B0}]) == {}
    assert list(mg.pending_merges([*good(), {"kind": "would_enqueue", "ts": "2026-10-14T00:10:00Z", "pr": 1, "head_sha": H1, "base_sha": B0, "retry": True}])
                .values())[0]["last"] == mg._epoch("2026-10-14T00:10:00Z")


# ------------------------------------------------------------------ the bounds
def many(fw, monkeypatch, n=5):
    """n pending keys at the current base, the least recently attempted first (a distinct hour each); the gate never runs."""
    recs, prs = [], []
    for i in range(n):
        number, head = 11 + i, f"{i + 1:040x}"
        ts = f"2026-10-14T0{i}:00:00Z"
        r = good()
        recs += [{**x, "pr": number, "head_sha": head, "base_sha": fw.base, "ts": ts} for x in r]
        fw.gh.prs.append(pr(number, head, armed=False, labels=[mg.ARM_LABEL]))
        prs.append(number)
    monkeypatch.setattr(mg, "PENDING_RETRY_S", 0)
    monkeypatch.setattr(mg, "PENDING_TTL_S", 10**9)
    return recs, prs


def test_at_most_three_keys_per_tick_least_recently_attempted_first(fw, monkeypatch):
    recs, nums = many(fw, monkeypatch)
    monkeypatch.setattr(mg, "phase_f_arming", lambda *a, **k: ({}, {"armed": False, "why": ["test"]}))
    assert mg.retry_pending_merges(args(), fw.state, fw.mirror, "L", recs, fw.base, fw.gh.prs) is False
    assert [r["pr"] for r in rows(fw, "would_enqueue")] == nums[:3] and mg.PENDING_RETRY_MAX == 3


def test_at_most_one_merge_per_tick_and_the_tick_then_decides_nothing(fw, monkeypatch):
    recs, nums = many(fw, monkeypatch)
    made = []

    def fake_merge(state, repo_dir, enq, wm, pull, decision, base):
        made.append(enq["pr"])
        mg.journal(state, {"kind": "merged", "pr": enq["pr"], "head_sha": enq["head_sha"], "base_sha": enq["base_sha"]})
    monkeypatch.setattr(mg, "phase_f_arming", lambda *a, **k: ({}, {"armed": True, "why": []}))
    monkeypatch.setattr(mg, "phase_f_merge", fake_merge)
    assert mg.retry_pending_merges(args(), fw.state, fw.mirror, "L", recs, fw.base, fw.gh.prs) is True
    assert made == nums[:1] and len(rows(fw, "would_enqueue")) == 1


# ------------------------------------------------------------------ fail closed
def test_a_failed_hosted_read_or_pr_read_is_a_false_term_with_its_message_and_raises_nothing(fw, monkeypatch):
    state = decided_while_hosted_pends(fw, monkeypatch)
    state["green"] = True

    def boom(*a, **k):
        raise mg.hc.CompareError("hosted exploded")
    monkeypatch.setattr(mg.hc, "fetch_live", boom)
    assert retry(fw) is False
    (enq,) = rows(fw, "would_enqueue")
    assert enq["criterion"]["hosted_required_green"] is False and "hosted exploded" in enq["why"]["hosted_required_green"] and enq["ok"] is False
    monkeypatch.undo()
    monkeypatch.setattr(mg, "PENDING_RETRY_S", 0)
    monkeypatch.setattr(mg, "gh_graphql", lambda *a, **k: (_ for _ in ()).throw(mg.GraphQLError("graphql exploded")))
    assert retry(fw) is False
    assert "graphql exploded" in rows(fw, "would_enqueue")[-1]["why"]["head_unchanged"] and "decision" not in [r["kind"] for r in rows(fw, "would_merge")]
    assert fw.kinds().count("decision") == 1


def test_a_retry_that_raises_inside_never_escapes_the_tick(fw, monkeypatch):
    state = decided_while_hosted_pends(fw, monkeypatch)
    state["green"] = True
    monkeypatch.setattr(mg, "merge_shadow_step", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("shadow exploded")))
    assert retry(fw) is False and fw.kinds().count("decision") == 1


# ------------------------------------------------------------------ the gate's gaps (L1-L4, B21)
import calendar  # noqa: E402
import time as real_time  # noqa: E402

from .test_merger import g  # noqa: E402


class Clock:
    def __init__(self, t):
        self.t = t

    def time(self):
        return self.t

    def __getattr__(self, name):
        return getattr(real_time, name)


def stamp(t):
    return real_time.strftime("%Y-%m-%dT%H:%M:%SZ", real_time.gmtime(t))


def keyed(fw, decision_at, enqueues=(), n=1, head=None):
    """A pending key at the current base, its decision at ``decision_at`` and further would_enqueue rows at ``enqueues`` (epochs)."""
    head = head or fw.head1
    recs = [{**x, "pr": n, "head_sha": head, "base_sha": fw.base, "ts": stamp(decision_at)} for x in good()]
    recs += [{"kind": "would_enqueue", "ts": stamp(t), "pr": n, "head_sha": head, "base_sha": fw.base, "retry": True} for t in enqueues]
    return recs


def run_retry(fw, recs, prs=None):
    return mg.retry_pending_merges(args(), fw.state, fw.mirror, "L", recs, fw.base, fw.gh.prs if prs is None else prs)


def test_the_local_terms_come_from_the_same_key_only():
    bad = {**dict.fromkeys(mg.CRITERION, True), "local_checks_clean": False, "hosted_required_green": False}
    other = [{**r, "head_sha": H2} for r in good({1: {"criterion": bad}})]
    other_base = [{**r, "base_sha": "e" * 40} for r in good({1: {"criterion": bad}})]
    for noise in (other, other_base):
        assert list(mg.pending_merges([*noise, *good()])) == [(1, H1, B0)] and list(mg.pending_merges([*good(), *noise])) == [(1, H1, B0)]


def test_the_retry_reads_the_hosted_side_at_the_decided_base_matrix(fw, monkeypatch):
    state = decided_while_hosted_pends(fw, monkeypatch)
    state["green"] = True
    seen = []
    real = mg.hc.fetch_live
    monkeypatch.setattr(mg.hc, "fetch_live", lambda repo, base, head, matrix=None: seen.append((base, head, matrix)) or real(repo, base, head, matrix))
    retry(fw)
    base, head, matrix = seen[0]   # the retry reads first; READY reads more later
    assert (base, head) == ("main", fw.head1) and matrix is not None and matrix[0] == fw.base
    assert matrix[1]().strip() == g(fw.mirror, "show", f"{fw.base}:{mg.MATRIX}")


def test_the_interval_runs_from_the_last_attempt_not_from_the_decision(fw, monkeypatch):
    now = calendar.timegm(real_time.gmtime())
    monkeypatch.setattr(mg, "time", Clock(now))
    monkeypatch.setattr(mg, "phase_f_arming", lambda *a, **k: ({}, {"armed": False, "why": ["test"]}))
    run_retry(fw, keyed(fw, now - 5000, [now - 100]))
    assert rows(fw, "would_enqueue") == []   # the decision is old, the last attempt is 100 s ago
    run_retry(fw, keyed(fw, now - 5000, [now - 1000]))
    assert len(rows(fw, "would_enqueue")) == 1


def test_the_ttl_runs_from_the_decision_not_from_the_last_attempt(fw, monkeypatch):
    now = calendar.timegm(real_time.gmtime())
    monkeypatch.setattr(mg, "time", Clock(now))
    run_retry(fw, keyed(fw, now - mg.PENDING_TTL_S - 50, [now - 1000]))
    assert [r["why"] for r in fw.live() if r["kind"] == "skipped"] == ["pending_expired"] and rows(fw, "would_enqueue") == []


def test_with_the_enqueue_env_armed_the_retry_does_nothing_at_all(fw, monkeypatch):
    state = decided_while_hosted_pends(fw, monkeypatch)
    state["green"] = True
    monkeypatch.setenv(mg.ARM_ENV, "1")
    n = len(fw.journal())
    assert retry(fw) is False and len(fw.journal()) == n and fw.gql.mutations() == []


def test_a_watchdog_or_a_stop_during_a_retry_ends_the_tick(fw, monkeypatch):
    state = decided_while_hosted_pends(fw, monkeypatch)
    state["green"] = True
    for exc in (mg.TickTimeout("tick exceeded"), mg.Stopped("stopped")):
        for where in ("fetch_live", "merge_shadow_step"):
            with monkeypatch.context() as m:
                m.setattr(mg.hc if where == "fetch_live" else mg, where, lambda *a, _e=exc, **k: (_ for _ in ()).throw(_e))
                with pytest.raises(type(exc)):
                    retry(fw)
    assert issubclass(mg.TickTimeout, mg.MergerError)


def test_the_tick_timeout_is_raised_by_the_alarm_handler_and_by_nothing_else():
    with pytest.raises(mg.TickTimeout):
        mg._raise(mg.TickTimeout, "x")(0, None)


def test_one_merge_attempt_per_tick_even_when_it_fails(fw, monkeypatch):
    recs, nums = many(fw, monkeypatch)
    made = []

    def failing(state, repo_dir, enq, wm, pull, decision, base):
        made.append(enq["pr"])
        mg.journal(state, {"kind": "merge_error", "pr": enq["pr"], "head_sha": enq["head_sha"], "base_sha": enq["base_sha"]})
    monkeypatch.setattr(mg, "phase_f_arming", lambda *a, **k: ({}, {"armed": True, "why": []}))
    monkeypatch.setattr(mg, "phase_f_merge", failing)
    assert run_retry(fw, recs) is True and made == nums[:1]


def test_a_push_unlanded_after_merged_leaves_the_key_pending_and_pushed_always_closes_it():
    k = {"pr": 1, "head_sha": H1, "base_sha": B0}
    assert mg.pending_merges([*good(), {"kind": "merged", **k}]) == {}
    assert list(mg.pending_merges([*good(), {"kind": "merged", **k}, {"kind": "push_unlanded", **k}])) == [(1, H1, B0)]
    assert mg.pending_merges([*good(), {"kind": "merged", **k}, {"kind": "pushed", **k}, {"kind": "push_unlanded", **k}]) == {}
    assert mg.pending_merges([*good(), {"kind": "merged", **k}, {"kind": "push_unlanded", **k}, {"kind": "merged", **k}]) == {}
    assert list(mg.pending_merges([*good(), {"kind": "push_unlanded", **{**k, "head_sha": H2}}, {"kind": "merged", **k}, {"kind": "push_unlanded", **k}])) == [(1, H1, B0)]


def test_the_real_alarm_handler_firing_inside_a_retry_ends_the_tick_with_a_timeout_error_line(fw, monkeypatch):
    import os
    import signal
    state = decided_while_hosted_pends(fw, monkeypatch)
    state["green"] = True
    monkeypatch.setattr(mg, "merge_shadow_step", lambda *a, **k: os.kill(os.getpid(), signal.SIGALRM) or None)
    monkeypatch.setattr(mg, "decide", lambda *a, **k: pytest.fail("the tick decided after the watchdog fired"))
    assert fw.tick() == 1
    assert "tick exceeded" in [r for r in fw.live() if r["kind"] == "error"][-1]["error"]


def test_an_alarm_swallowed_inside_pr_side_during_a_retry_still_ends_the_tick_before_triage(fw, monkeypatch):
    import os
    import signal
    state = decided_while_hosted_pends(fw, monkeypatch)
    state["green"] = True
    real, fired, after = mg.label_arm, [], []

    def label_arm(repo, p):
        if not fired:
            fired.append(1)
            os.kill(os.getpid(), signal.SIGALRM)
        return real(repo, p)
    monkeypatch.setattr(mg, "label_arm", label_arm)
    monkeypatch.setattr(mg, "triage", lambda *a, **k: after.append("triage") or pytest.fail("triage ran after the watchdog"))
    assert fw.tick() == 1 and fired and after == []
    assert "watchdog" in [r for r in fw.live() if r["kind"] == "error"][-1]["error"]
    assert mg._WATCHDOG["fired"] is True


def test_the_flag_is_reset_where_a_tick_arms_the_alarm(fw, monkeypatch):
    mg._WATCHDOG["fired"] = True
    assert fw.tick() == 0 and mg._WATCHDOG["fired"] is False


def test_an_alarm_during_decide_is_still_its_error_decision(fw, monkeypatch):
    import os
    import signal
    monkeypatch.setattr(mg, "hosted_summary", lambda *a, **k: os.kill(os.getpid(), signal.SIGALRM))
    assert fw.tick() == 1
    assert [r["overall"] for r in fw.live() if r["kind"] == "decision"] == ["ERROR"]


def test_the_retry_alone_raises_when_an_alarm_was_swallowed_inside_it(fw, monkeypatch):
    import os
    import signal
    state = decided_while_hosted_pends(fw, monkeypatch)
    state["green"] = True
    real, fired = mg.label_arm, []

    def label_arm(repo, p):
        if not fired:
            fired.append(1)
            os.kill(os.getpid(), signal.SIGALRM)
        return real(repo, p)
    monkeypatch.setattr(mg, "label_arm", label_arm)
    old = signal.signal(signal.SIGALRM, mg._raise(mg.TickTimeout, "tick exceeded"))
    try:
        with pytest.raises(mg.TickTimeout):
            retry(fw)
    finally:
        signal.signal(signal.SIGALRM, old)


def test_an_alarm_swallowed_inside_replay_selection_ends_the_tick_before_any_decision(fw, monkeypatch):
    import os
    import signal

    def swallowing(*a, **k):
        try:
            os.kill(os.getpid(), signal.SIGALRM)
        except Exception:  # noqa: BLE001 — replay_pending's own broad except
            pass
    monkeypatch.setattr(mg, "replay_pending", swallowing)
    monkeypatch.setattr(mg, "decide", lambda *a, **k: pytest.fail("decided after the watchdog fired"))
    assert fw.tick() == 1
    assert "watchdog" in [r for r in fw.live() if r["kind"] == "error"][-1]["error"]


def test_a_retry_whose_push_fails_in_transport_stays_pending_and_the_next_retry_merges_once(fw, monkeypatch):
    """B19 x B21 on B21's real code path: the push times out, the read-back shows main unchanged twice, push_unlanded; the next retry merges."""
    import subprocess
    state = decided_while_hosted_pends(fw, monkeypatch)
    state["green"] = True
    monkeypatch.setattr(mg, "READBACK_SETTLE_S", 0)
    real, broken = mg.git, [True]

    def git_(cwd, *a, **kw):
        if a and a[0] == "push":
            fw.pushes.append((a, dict(kw.get("env") or {})))
            if broken[0]:
                raise subprocess.TimeoutExpired(["git", "push"], kw["timeout"])
        return real(cwd, *a, **kw)
    monkeypatch.setattr(mg, "git", git_)
    assert fw.tick() == 0
    assert fw.kinds()[-3:] == ["would_merge", "merged", "push_unlanded"] and not (fw.state / mg.HALT_FILE).exists()
    assert fw.origin_main() == fw.base and list(mg.pending_merges(fw.journal())) == [(1, fw.head1, fw.base)]
    broken[0] = False
    assert fw.tick() == 0
    assert fw.kinds()[-4:] == ["would_enqueue", "would_merge", "merged", "pushed"] and fw.kinds().count("decision") == 1
    assert fw.origin_main() == fw.journal()[-1]["merge_commit"] and len([c for c in fw.runner.calls if c["sub"] == "plan"]) == 1
    assert mg.pending_merges(fw.journal()) == {}
