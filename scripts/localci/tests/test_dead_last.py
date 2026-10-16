"""B38 guilt + innocence: a key that cannot yield a mergeable row is decided last, never skipped; a read that fails means not dead."""
from __future__ import annotations

import pytest

from .test_merger import REPO, mg, pr
from .test_pr_first import LABEL, labelled
from .test_replay import rw  # noqa: F401 — `rw` is a fixture

BASE, OLD_BASE = "b" * 40, "a" * 40
H = {n: f"{n:040x}" for n in range(1, 9)}
AGREE = {"AGREE": 3, "FALSE_GREEN": 0, "FALSE_RED": 0, "LOCAL_BLIND": 0, "HOSTED_PENDING": 0, "HOSTED_STALE": 0, "HOSTED_ABORTED": 0}


def decision(n, *, overall="OK", ts="2026-10-10T00:00:00Z", base=OLD_BASE, head=None, **over):
    return {"kind": "decision", "ts": ts, "pr": n, "head_sha": head or H[n], "base_sha": base, "overall": overall, **over}


def failed(n, **over):
    return {**decision(n, overall="FAIL", contexts={"ctx-a": "FAIL", "ctx-b": "OK"}, hosted_compare={"counts": AGREE, "agreement": "3/3"}), **over}


def keys(n_list, *, armed_labels=(), recs=(), probes=None, dead=None, **kw):
    prs = [pr(n, H[n], labels=LABEL if n in armed_labels else (), created=f"2026-10-0{n}T00:00:00Z") for n in n_list]
    todo, _ = mg.triage(prs, REPO, list(recs), BASE, dead_probes=probes, dead=dead, **kw)
    return [p["number"] for p in todo]


def probe(**by_name):
    return {name: (lambda n, head, hit=hit: n in hit) for name, hit in by_name.items()}


# ------------------------------------------------------------------ the order
def test_without_probes_the_order_is_b23s_exactly():
    recs = [decision(3, ts="2026-10-01T00:00:00Z"), decision(2, ts="2026-10-02T00:00:00Z")]   # both decided at another base: the older decision first
    assert keys([1, 2, 3, 4], recs=recs) == [1, 4, 3, 2]


def test_mixed_keys_dead_ones_go_behind_their_group_and_labelled_stays_first():
    dead = {}
    got = keys([1, 2, 3, 4, 5, 6], armed_labels=(1, 2, 3), probes=probe(review={1, 4}), recs=[failed(3), failed(6)], dead=dead)
    assert got == [2, 1, 3, 5, 4, 6]   # labelled alive (2), labelled dead (1, 3), unlabelled alive (5), unlabelled dead (4, 6): B23's order inside each class
    assert dead == {(1, H[1]): ["review"], (3, H[3]): ["fail_agreed"], (4, H[4]): ["review"], (6, H[6]): ["fail_agreed"]}


def test_the_rest_tier_classes_a_key_dead_only_up_to_the_first_alive_one():
    dead = {}
    got = keys([1, 2, 3, 4, 5, 6], armed_labels=(1, 2, 3), probes=probe(review={1, 4}, hosted={3, 6}), dead=dead)
    assert got == [2, 3, 1, 5, 6, 4]   # 2 is alive: 3 and 6 are not read, so they keep their normal place; the free review tier still saw 1 and 4
    assert set(dead) == {(1, H[1]), (4, H[4])}


def test_a_dead_labelled_key_is_still_ahead_of_an_unlabelled_alive_one_b28_composition():
    assert keys([1, 2], armed_labels=(1,), probes=probe(review={1})) == [1, 2]


def test_ordering_inside_the_dead_class_is_the_old_one_oldest_last_decision_first():
    recs = [decision(1, ts="2026-10-03T00:00:00Z"), decision(2, ts="2026-10-01T00:00:00Z"), decision(3, ts="2026-10-02T00:00:00Z")]
    assert keys([1, 2, 3, 4], recs=recs, probes=probe(review={1, 2, 3})) == [4, 2, 3, 1]


def test_a_dead_key_is_decided_when_it_is_the_only_selectable_one():
    assert keys([1], probes=probe(review={1})) == [1]
    assert keys([1, 2], recs=[decision(2, base=BASE)], probes=probe(hosted={1})) == [1]   # 2 is decided at this base: not selectable


@pytest.mark.parametrize("name,why", [("review", "review"), ("hosted", "hosted_red")])
def test_each_probe_alone_makes_a_key_dead(name, why):
    dead = {}
    assert keys([1, 2], probes=probe(**{name: {1}}), dead=dead) == [2, 1] and dead == {(1, H[1]): [why]}


def test_c_a_fail_the_hosted_side_agreed_on_makes_the_key_dead_with_no_read():
    dead = {}
    assert keys([1, 2], recs=[failed(1)], probes={}, dead=dead) == [2, 1] and dead == {(1, H[1]): ["fail_agreed"]}


@pytest.mark.parametrize("rec", [
    decision(1, overall="OK"),                                                                        # not a FAIL
    failed(1, overall="BLOCKED"),                                                                      # a failing context under a BLOCKED overall is no FAIL verdict
    failed(1, hosted_compare={"error": "boom", "counts": AGREE}),                                      # the comparison failed
    failed(1, hosted_compare={"counts": {**AGREE, "FALSE_RED": 1}}),                                   # hosted did NOT agree
    failed(1, hosted_compare={"counts": {**AGREE, "HOSTED_PENDING": 1}}),                              # hosted still pending
    failed(1, hosted_compare={"counts": {**AGREE, "LOCAL_BLIND": 1}}),
    failed(1, hosted_compare={}),                                                                      # no counts: unknown
    failed(1, hosted_compare=None),
    failed(1, contexts={"ctx-a": "OK"}),                                                               # a FAIL with no failing context: nothing agreed red
    failed(1, contexts=None),
    failed(1, replay=True),                                                                           # replays are not this PR's decision
    {**failed(1), "head_sha": H[2]},                                                                  # another head
])
def test_c_every_other_shape_is_not_dead(rec):
    dead = {}
    assert keys([1, 2], recs=[rec], probes={}, dead=dead) == keys([1, 2], recs=[rec]) and dead == {}


def test_c_the_newest_decision_at_the_head_decides():
    dead = {}
    keys([1, 2], recs=[failed(1, ts="2026-10-01T00:00:00Z"), decision(1, ts="2026-10-02T00:00:00Z", base="c" * 40)], probes={}, dead=dead)
    assert dead == {}   # the later OK un-deads it
    keys([1, 2], recs=[decision(1, ts="2026-10-01T00:00:00Z"), failed(1, ts="2026-10-02T00:00:00Z", base="c" * 40)], probes={}, dead=dead)
    assert dead == {(1, H[1]): ["fail_agreed"]}


def pending(n, **over):
    return decision(n, overall="BLOCKED", gate_pending=True, gate_pending_contexts=["ctx.harness-floor"], **over)


def test_d_a_pr_that_needed_a_gate_verdict_and_whose_new_head_has_none_is_dead():
    new_head = f"{9:040x}"
    prs = [pr(1, new_head, created="2026-10-01T00:00:00Z"), pr(2, H[2], created="2026-10-02T00:00:00Z")]
    asked = []
    probes = {"gate_missing": lambda n, head: asked.append((n, head)) or True, "hosted": lambda n, head: False}
    todo, _ = mg.triage(prs, REPO, [pending(1, head=H[1])], BASE, dead_probes=probes)
    assert [p["number"] for p in todo] == [2, 1] and asked == [(1, new_head)]   # PR 2 never needed a gate: no gate read for it


def test_d_a_verdict_posted_means_not_dead_and_a_pr_that_never_needed_one_is_never_asked():
    prs = [pr(1, f"{9:040x}", created="2026-10-01T00:00:00Z"), pr(2, H[2], created="2026-10-02T00:00:00Z")]
    asked = []
    probes = {"gate_missing": lambda n, head: asked.append(n) or False}
    todo, _ = mg.triage(prs, REPO, [pending(1, head=H[1])], BASE, dead_probes=probes)
    assert [p["number"] for p in todo] == [1, 2] and asked == [1]


def test_d_a_later_non_pending_decision_clears_the_need():
    recs = [pending(1, head=H[1], ts="2026-10-01T00:00:00Z"), decision(1, head=f"{8:040x}", ts="2026-10-02T00:00:00Z")]
    asked = []
    prs = [pr(1, f"{9:040x}"), pr(2, H[2])]
    mg.triage(prs, REPO, recs, BASE, dead_probes={"gate_missing": lambda n, head: asked.append(n) or True})
    assert asked == []


# ------------------------------------------------------------------ a read that fails or is unknown means not dead
@pytest.mark.parametrize("exc", [mg.hc.CompareError("x"), OSError("net"), mg.GraphQLError("gql"), KeyError("k"), ValueError("v"), RuntimeError("r")])
def test_a_probe_that_raises_means_not_dead_and_the_key_keeps_its_place(exc, capsys):
    def boom(n, head):
        raise exc
    dead = {}
    assert keys([1, 2], probes={"review": boom, "hosted": boom, "gate_missing": boom}, dead=dead, recs=[pending(1, head=f"{9:040x}")]) == [1, 2] and dead == {}
    assert "not read" in capsys.readouterr().err


def test_an_absent_probe_means_not_dead():
    assert keys([1, 2], probes={}) == [1, 2]


def test_the_tick_deadline_and_a_stop_are_never_swallowed_by_a_probe():
    def stop(n, head):
        raise mg.Stopped("sigterm")
    with pytest.raises(mg.Stopped):
        keys([1], probes={"review": stop})


# ------------------------------------------------------------------ (b) the hosted document
def live(*runs, statuses=(), required=("ctx-a",)):
    return {"required_checks": [{"context": c, "app_id": 15368} for c in required], "statuses": list(statuses),
            "check_runs": [{"name": nm, "status": st, "conclusion": cc, "id": i, "completed_at": "2026-10-12T00:00:00Z", "app": {"id": 15368, "slug": "github-actions"}}
                           for i, (nm, st, cc) in enumerate(runs, 1)]}


@pytest.mark.parametrize("conclusion", ["failure", "timed_out", "startup_failure"])
def test_b_a_completed_red_of_a_required_context_is_dead(conclusion):
    assert mg.hosted_dead(live(("ctx-a", "completed", conclusion))) is True


@pytest.mark.parametrize("state", ["failure", "error"])
def test_b_a_failed_commit_status_is_dead(state):
    assert mg.hosted_dead(live(statuses=[{"context": "ctx-a", "state": state, "updated_at": "2026-10-12T00:00:00Z"}])) is True


def test_b_a_pending_commit_status_is_not_dead():
    assert mg.hosted_dead(live(statuses=[{"context": "ctx-a", "state": "pending", "updated_at": "2026-10-12T00:00:00Z"}])) is False


@pytest.mark.parametrize("runs", [
    [("ctx-a", "completed", "cancelled")],                                  # B17/B27 judge a cancel
    [("ctx-a", "in_progress", None)],                                       # pending
    [("ctx-a", "queued", None)],
    [("ctx-a", "completed", "success")],
    [("ctx-a", "completed", "failure"), ("ctx-a", "in_progress", None)],    # a red beside a running attempt is not final
    [("ctx-b", "completed", "failure")],                                    # not a required context
    [("ctx-a", "completed", "action_required")],                            # red on GitHub, but not one of the completed reds named
    [],
])
def test_b_cancelled_pending_green_and_unrequired_are_not_dead(runs):
    assert mg.hosted_dead(live(*runs)) is False


def test_b_a_cancel_answered_by_another_run_is_judged_by_that_run_as_b17_reads_it():
    assert mg.hosted_dead(live(("ctx-a", "completed", "cancelled"), ("ctx-a", "completed", "failure"))) is True    # the cancel is dropped: the failure is the red
    assert mg.hosted_dead(live(("ctx-a", "completed", "cancelled"), ("ctx-a", "completed", "success"))) is False   # the cancel is dropped: green


# ------------------------------------------------------------------ (a) the review, B29's own predicate
def review_pr(decision=None, states=(), total=None):
    return {"reviewDecision": decision, "latestOpinionatedReviews": {"totalCount": len(states) if total is None else total, "nodes": [{"state": s} for s in states]}}


def test_a_changes_requested_is_dead_by_b29s_own_predicate():
    assert mg.review_dead(review_pr("CHANGES_REQUESTED", ["CHANGES_REQUESTED"])) is True
    assert mg.review_dead(review_pr(None, ["APPROVED", "CHANGES_REQUESTED"])) is True
    assert mg.review_block(review_pr("CHANGES_REQUESTED")) is not None   # the same definition: B29 blocks what B38 calls dead


@pytest.mark.parametrize("p", [review_pr(None, ["APPROVED"]), review_pr(), review_pr("APPROVED", ["APPROVED"]),
                               {}, {"reviewDecision": None}, review_pr(None, ["APPROVED"], total=2), review_pr(None, ["WEIRD"]), review_pr(5)])
def test_a_clean_or_unreadable_review_is_not_dead(p):
    assert mg.review_dead(p) is False


def test_the_open_reviews_read_is_one_graphql_query_keyed_by_number_and_head(monkeypatch):
    calls = []

    def gql(query, **variables):
        calls.append((query, variables))
        return {"repository": {"pullRequests": {"nodes": [
            {"number": 1, "headRefOid": H[1], **review_pr("CHANGES_REQUESTED", ["CHANGES_REQUESTED"])},
            {"number": 2, "headRefOid": H[2], **review_pr(None, ["APPROVED"])}, "junk"]}}}
    monkeypatch.setattr(mg, "gh_graphql", gql)
    assert mg.open_review_dead(REPO, "main") == {(1, H[1]): True, (2, H[2]): False}
    assert calls == [(mg.REVIEWS_QUERY, {"owner": REPO.split("/")[0], "name": REPO.split("/")[1], "base": "main"})]


def test_the_reviews_query_reads_only_writers_reviews_like_b29s():
    assert "writersOnly: true" in mg.REVIEWS_QUERY and "writersOnly: true" in mg.PR_QUERY and "first: 100" in mg.REVIEWS_QUERY


def test_an_unreadable_reviews_document_raises_and_the_probe_reads_it_as_not_dead_once(monkeypatch, capsys):
    calls = []

    def gql(query, **variables):
        calls.append(query)
        raise mg.GraphQLError("down")
    monkeypatch.setattr(mg, "gh_graphql", gql)
    a = type("A", (), {"repo": REPO, "base": "main"})()
    review = mg.dead_probes(a, None, BASE)["review"]
    assert review(1, H[1]) is False and review(2, H[2]) is False and calls == [mg.REVIEWS_QUERY]   # one failed read, not one per key
    assert "reviews not read" in capsys.readouterr().err


def test_the_probes_read_what_triage_asks_of_them(monkeypatch):
    seen = []
    monkeypatch.setattr(mg.hc, "fetch_live", lambda repo, base, head, matrix: seen.append((repo, base, head, matrix)) or live(("ctx-a", "completed", "failure")))
    monkeypatch.setattr(mg, "base_matrix", lambda repo_dir, base_sha: ("matrix", repo_dir, base_sha))
    a = type("A", (), {"repo": REPO, "base": "main"})()
    probes = mg.dead_probes(a, "REPO_DIR", BASE)
    assert probes["hosted"](1, H[1]) is True and seen == [(REPO, "main", H[1], ("matrix", "REPO_DIR", BASE))]
    monkeypatch.setattr(mg, "gate_posted_at", lambda repo, head: None)
    assert probes["gate_missing"](1, H[1]) is True
    monkeypatch.setattr(mg, "gate_posted_at", lambda repo, head: "2026-10-12T00:00:00Z")
    assert probes["gate_missing"](1, H[1]) is False


# ------------------------------------------------------------------ cost: the REST reads are bounded and stop at the first alive key
def test_rest_reads_stop_at_the_first_alive_key():
    asked = []
    probes = {"hosted": lambda n, head: asked.append(n) or n in {1, 2}}
    assert keys([1, 2, 3, 4, 5], probes=probes) == [3, 4, 5, 1, 2] and asked == [1, 2, 3]   # 3 is alive: 4 and 5 are not read


def test_rest_reads_are_capped_per_tick():
    asked = []
    n_list = list(range(1, 9))
    probes = {"hosted": lambda n, head: asked.append(n) or True}
    got = keys(n_list, probes=probes)
    assert len(asked) == mg.DEAD_READ_CAP == 5 and got == [6, 7, 8, 1, 2, 3, 4, 5]   # the unread tail keeps its place; nothing is dropped


def test_the_free_tiers_see_every_key_even_after_the_rest_reads_stopped():
    probes = {"hosted": lambda n, head: False, "review": lambda n, head: n == 3}
    assert keys([1, 2, 3, 4], probes=probes, recs=[failed(2)]) == [1, 4, 3, 2]   # 1 is alive and stops the REST reads; 2 (journal) and 3 (review) are dead all the same


# ------------------------------------------------------------------ the tick: the wiring, the journal line and the log line
def test_the_tick_decides_a_live_pr_ahead_of_a_dead_one_and_journals_the_dead_class_once(rw, monkeypatch, capsys):
    labelled(rw, 3, 4)
    monkeypatch.setattr(mg, "dead_probes", lambda a, repo_dir, base_sha: {"review": lambda n, head: n == 3})
    assert rw.tick() == 0
    assert [(bool(d.get("replay")), d["pr"]) for d in rw.decisions()] == [(False, 4)]
    assert rw.tick() == 0 and rw.tick() == 0
    rows = [r for r in mg.read_journal(rw.state) if r["kind"] == "skipped" and r.get("why") == "dead_last"]
    assert len(rows) == 1 and rows[0]["pr"] == 3 and rows[0]["head_sha"] == rw.heads[3] and rows[0]["reasons"] == ["review"]   # once per (pr, head, base)
    assert "merger: B38 1 dead key(s) sorted last: #3(review); first in order #4" in capsys.readouterr().out
    assert [d["pr"] for d in rw.decisions() if not d.get("replay")] == [4, 3]   # the dead key is decided once nothing else is selectable


def test_a_dead_labelled_pr_is_still_a_waiting_labelled_pr_for_b28(rw, monkeypatch):
    monkeypatch.setattr(mg, "dead_probes", lambda a, repo_dir, base_sha: {"review": lambda n, head: True})
    labelled(rw, 3)
    rw.tick()   # PR 3 decided (no replay exists before a first PR decision)
    labelled(rw, 3, 4)
    rw.tick()
    assert [(bool(d.get("replay")), d["pr"]) for d in rw.decisions()] == [(False, 3), (False, 4)]   # 4 is labelled and dead: still decided ahead of a replay
    assert [r["pr"] for r in mg.read_journal(rw.state) if r["kind"] == "replay_deferred"] == [4]
