"""B11 guilt + innocence: the merger also judges the exact commit GitHub merged (a replay), BASE = its first parent, alternating with PR decisions."""
from __future__ import annotations

import subprocess
import time

import pytest

from .test_merger import FakeGH, FakeGraphQL, FakeRunner, GIT_ENV, REPO, g, mg, pr

BASE_MATRIX, REWRITTEN, SIDE_MATRIX = "base matrix\n", "rewritten by the merged PR\n", "the second parent's matrix\n"


def _commit(wt, files: dict, msg: str, when: int) -> str:
    for rel, body in files.items():
        (wt / rel).parent.mkdir(parents=True, exist_ok=True)
        (wt / rel).write_text(body)
    g(wt, "add", "-A")
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(when))
    subprocess.run(["git", "-C", str(wt), "commit", "-qm", msg], check=True, capture_output=True, env={**GIT_ENV, "GIT_COMMITTER_DATE": stamp, "GIT_AUTHOR_DATE": stamp})
    return g(wt, "rev-parse", "HEAD")


class Hub:
    """GitHub's pulls for the merged PRs, on top of FakeGH; a number mapped to None raises (a failed read)."""

    def __init__(self, gh: FakeGH):
        self.gh, self.pulls, self.reads = gh, {}, []

    def __call__(self, path):
        if path.startswith(f"repos/{REPO}/pulls/"):
            n = int(path.rsplit("/", 1)[1])
            self.reads.append(n)
            if self.pulls[n] is None:
                raise mg.hc.CompareError("gh api failed")
            return self.pulls[n]
        return self.gh(path)


def merged_pull(sha, head):
    return {"merged": True, "state": "closed", "merge_commit_sha": sha, "head": {"sha": head, "repo": {"full_name": REPO}},
            "base": {"repo": {"full_name": REPO}}, "merged_at": "2026-10-09T01:00:00Z"}


@pytest.fixture
def rw(tmp_path, monkeypatch):
    """main: base0, then three merge commits dated after the first decision: M0 `(#13)` GitHub does not confirm, M1 `(#11)` rewrites the
    matrix, M2 `(#12)`; plus a commit with no PR number. M1 has TWO parents: M0 first, then a side commit `(#14)` GitHub confirms, with
    yet another matrix, on main only through that second parent. Two open PRs (#3, #4) branch from base0."""
    src = tmp_path / "src"
    src.mkdir()
    g(src, "init", "-q", "-b", "main")
    t = int(time.time()) + 3600
    base0 = _commit(src, {"a.txt": "a\n", mg.MATRIX: BASE_MATRIX}, "base", t - 7200)
    heads = {}
    for n in (3, 4, 11, 12):
        g(src, "checkout", "-q", "-b", f"pr{n}", base0)
        heads[n] = _commit(src, {f"f{n}.txt": f"{n}\n"}, f"pr{n}", t - 7000)
    g(src, "checkout", "-q", "-b", "side", base0)
    side = _commit(src, {"side.txt": "s\n", mg.MATRIX: SIDE_MATRIX}, "side (#14)", t + 90)
    g(src, "checkout", "-q", "main")
    m = {"plain": _commit(src, {"plain.txt": "p\n"}, "no pull request number here", t),
         "m0": _commit(src, {"m0.txt": "0\n"}, "bogus (#13)", t + 60), "side": side}
    g(src, "merge", "--no-ff", "--no-commit", "-q", "side")   # M1 is committed below with MERGE_HEAD set: two parents
    m["m1"] = _commit(src, {mg.MATRIX: REWRITTEN, "m1.txt": "1\n"}, "one (#11)", t + 120)
    m["m2"] = _commit(src, {"m2.txt": "2\n"}, "two (#12)", t + 180)
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(src), str(origin)], check=True, env=GIT_ENV)
    for n in (3, 4):
        g(origin, "update-ref", f"refs/pull/{n}/head", heads[n])
    gh, runner = FakeGH(), FakeRunner()
    hub = Hub(gh)
    hub.pulls = {11: merged_pull(m["m1"], heads[11]), 12: merged_pull(m["m2"], heads[12]),
                 14: merged_pull(side, "8" * 40),   # confirmed, but never on the first-parent line: never replayed, never asked
                 13: {"merged": True, "merge_commit_sha": "7" * 40, "head": {"sha": "9" * 40}}}   # #13 was merged, but as another commit
    gql = FakeGraphQL(gh)
    monkeypatch.setattr(mg.hc, "gh_get", hub)
    monkeypatch.setattr(mg, "gh_graphql", gql)
    monkeypatch.setattr(mg, "runner_exec", runner)
    monkeypatch.delenv(mg.ARM_ENV, raising=False)
    w = type("RWorld", (), {})()
    w.state, w.gh, w.hub, w.gql, w.runner, w.base0, w.heads, w.m = tmp_path / "state", gh, hub, gql, runner, base0, heads, m
    gh.prs = [pr(3, heads[3], created="2026-10-01T00:00:00Z"), pr(4, heads[4], created="2026-10-02T00:00:00Z")]
    w.tick = lambda: mg.main(["tick", "--node", mg.HOST, "--repo", REPO, "--state-dir", str(w.state), "--remote-url", str(origin), "--python", "py"])
    w.decisions = lambda: [r for r in mg.read_journal(w.state) if r["kind"] == "decision"]
    return w


def test_replays_and_pr_decisions_alternate_oldest_merge_first_and_a_replayed_commit_is_not_asked_again(rw):
    for _ in range(5):
        assert rw.tick() == 0
    ds = rw.decisions()
    assert [(bool(d.get("replay")), d["pr"]) for d in ds] == [(False, 3), (True, 11), (False, 4), (True, 12)]   # then nothing is left to do
    assert [d["merge_commit"] for d in ds if d.get("replay")] == [rw.m["m1"], rw.m["m2"]]
    assert [d["schedule"] for d in ds if d.get("replay")] == ["alternation: the previous decision was not a replay"] * 2


def test_a_replay_turn_with_no_pull_request_to_decide_still_replays_and_says_why(rw):
    rw.gh.prs = rw.gh.prs[:1]
    for _ in range(3):
        assert rw.tick() == 0
    ds = rw.decisions()
    assert [bool(d.get("replay")) for d in ds] == [False, True, True] and ds[2]["schedule"] == "no pull request to decide"


def test_the_replay_judges_the_merge_commit_with_its_first_parent_as_the_base_never_the_commits_own_matrix(rw):
    rw.tick()
    rw.tick()
    plan = [c for c in rw.runner.calls if c["sub"] == "plan"][1]
    first_parent = rw.m["m0"]
    assert g(rw.state / "repo.git", "rev-list", "--parents", "-n1", rw.m["m1"]).split()[1:] == [first_parent, rw.m["side"]]   # M1 is a real merge
    assert plan["cwd"] == rw.state / "base" / first_parent and plan["cwd_head"] == first_parent and plan["worktree_head"] == rw.m["m1"]
    assert plan["argv"][plan["argv"].index("--base") + 1] == first_parent and plan["argv"][plan["argv"].index("--candidate") + 1] == rw.m["m1"]
    assert plan["matrix"] == BASE_MATRIX   # the merged PR rewrote the matrix and the second parent holds another: the first parent's judges
    assert g(rw.state / "repo.git", "show", f"{rw.m['m1']}:{mg.MATRIX}") == REWRITTEN.strip()


def test_the_replay_line_carries_the_decision_fields_and_enqueues_and_rehearses_nothing(rw):
    rw.tick()
    mutations = len(rw.gql.mutations())
    rw.tick()
    kinds_after = [r["kind"] for r in mg.read_journal(rw.state)]
    d = rw.decisions()[1]
    assert d["replay"] is True and (d["pr"], d["merge_commit"], d["base_sha"], d["candidate_sha"], d["head_sha"]) == (
        11, rw.m["m1"], rw.m["m0"], rw.m["m1"], rw.heads[11])
    assert {"contexts", "coverage", "skipped", "hosted_compare", "run_dir", "seal", "lease_id", "elapsed_s"} <= set(d)
    assert d["hosted_compare"]["sha"] == rw.m["m1"] and d["hosted_compare"]["note"].startswith("B11 replay")
    assert "stale" not in d["hosted_compare"] and "stale_unknown" not in d["hosted_compare"]   # the same tree: nothing to judge
    assert kinds_after[-1] == "decision"
    assert not [k for k in kinds_after[kinds_after.index("skipped"):] if k in ("would_enqueue", "would_merge", "enqueued")]
    assert len(rw.gql.mutations()) == mutations and not any(c[0] == mg.ENQUEUE for c in rw.gql.calls[-1:])


def test_a_commit_github_does_not_confirm_is_journalled_once_and_never_asked_again(rw):
    for _ in range(5):
        rw.tick()
    skipped = [r for r in mg.read_journal(rw.state) if r["kind"] == "skipped" and r.get("why") == "replay_unmapped"]
    assert [(r["merge_commit"], r["pr"]) for r in skipped] == [(rw.m["m0"], 13)] and rw.hub.reads.count(13) == 1
    assert rw.m["plain"] not in {r.get("merge_commit") for r in mg.read_journal(rw.state)} and rw.hub.reads.count(11) == 1
    assert 14 not in rw.hub.reads   # the side commit is reachable only through M1's second parent: off the first-parent line


def test_a_pull_that_cannot_be_read_falls_back_to_a_pr_decision(rw, capsys):
    rw.tick()
    rw.hub.pulls[13] = rw.hub.pulls[11] = None
    assert rw.tick() == 0
    ds = rw.decisions()
    assert [bool(d.get("replay")) for d in ds] == [False, False] and ds[1]["pr"] == 4
    assert "replay selection failed" in capsys.readouterr().err


def test_an_errored_replay_is_retried_once_and_then_left(rw, monkeypatch):
    rw.runner.plan_rc = 1   # the gate cannot plan: every decision is ERROR
    for _ in range(8):
        rw.tick()
    replays = [d for d in rw.decisions() if d.get("replay")]
    assert [d["overall"] for d in replays] == ["ERROR"] * len(replays) and replays.count(replays[0]) == 1
    assert max(sum(1 for d in replays if d["merge_commit"] == m) for m in {d["merge_commit"] for d in replays}) <= 2


def test_pr_triage_ignores_replay_lines(rw):
    recs = [{"kind": "decision", "replay": True, "pr": 3, "head_sha": rw.heads[3], "base_sha": "b" * 40, "ts": "2026-10-09T00:00:00Z"}]
    todo, _ = mg.triage([pr(3, rw.heads[3])], REPO, recs, "b" * 40)
    assert [p["number"] for p in todo] == [3]


def _next_second():
    """A run dir is named to the second: the same key decided again within one second would meet the last attempt's (EEXIST)."""
    now = int(time.time())
    while int(time.time()) == now:
        time.sleep(0.05)


def _runner_that_raises(monkeypatch, rw, exc, when):
    """The gate's runner raises ``exc`` on every candidate ``when(candidate)`` holds for, and runs as before on the others."""
    def run(argv, cwd, env, timeout):
        if "--candidate" in argv and when(argv[argv.index("--candidate") + 1]):
            raise exc
        return rw.runner(argv, cwd, env, timeout)
    monkeypatch.setattr(mg, "runner_exec", run)


@pytest.mark.parametrize("exc", [RuntimeError("boom ghp_" + "E" * 36), subprocess.TimeoutExpired(["git"], 5)], ids=["runtime-error", "timeout"])
def test_a_replay_that_crashes_is_an_error_line_so_the_alternation_advances_and_the_retry_bound_holds(rw, monkeypatch, exc):
    _runner_that_raises(monkeypatch, rw, exc, lambda cand: cand == rw.m["m1"])
    rcs = []
    for _ in range(7):
        rcs.append(rw.tick())
        if rcs[-1]:   # the failed key is decided again two ticks later
            _next_second()
    ds = rw.decisions()
    # each failed replay is a decision line, so the next tick decides a PR; after two the commit is left and M2 is reached
    assert [(bool(d.get("replay")), d["pr"], d["overall"] == "ERROR") for d in ds] == [
        (False, 3, False), (True, 11, True), (False, 4, False), (True, 11, True), (True, 12, False)]
    assert rcs == [0, 1, 0, 1, 0, 0, 0] and not [r for r in mg.read_journal(rw.state) if r["kind"] == "error"]
    crashed = [d for d in ds if d["overall"] == "ERROR"]
    assert {d["merge_commit"] for d in crashed} == {rw.m["m1"]} and all(d["error"].startswith(type(exc).__name__ + ": ") for d in crashed)
    assert all("ghp_" not in d["error"] and d["candidate_sha"] is None for d in crashed)


def test_a_stop_during_a_replay_is_no_verdict_and_the_same_replay_is_decided_next(rw, monkeypatch):
    rw.tick()
    _runner_that_raises(monkeypatch, rw, mg.Stopped("stopped (signal 15)"), lambda cand: cand == rw.m["m1"])
    assert rw.tick() == 1
    assert [bool(d.get("replay")) for d in rw.decisions()] == [False]   # a stop is never an ERROR replay: it does not spend a retry
    assert [r["error"] for r in mg.read_journal(rw.state) if r["kind"] == "error"] == ["stopped (signal 15)"]
    monkeypatch.setattr(mg, "runner_exec", rw.runner)
    _next_second()
    assert rw.tick() == 0
    d = rw.decisions()[-1]
    assert (d.get("replay"), d["merge_commit"], d["overall"] != "ERROR") == (True, rw.m["m1"], True)


def test_a_pr_decision_that_crashes_outside_the_gate_errors_is_no_decision_as_before(rw, monkeypatch):
    replayed = set(rw.m.values())
    _runner_that_raises(monkeypatch, rw, subprocess.TimeoutExpired(["git"], 5), lambda cand: cand not in replayed)
    assert rw.tick() == 1
    assert rw.decisions() == [] and [r["kind"] for r in mg.read_journal(rw.state)][-1] == "error"   # the tick's error line, its key kept
    _runner_that_raises(monkeypatch, rw, RuntimeError("boom"), lambda cand: cand not in replayed)
    _next_second()
    with pytest.raises(RuntimeError, match="boom"):
        rw.tick()
    assert rw.decisions() == []
