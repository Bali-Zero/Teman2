"""Guilt + innocence corpus for the shadow merger: real temporary git repos, a local origin, GitHub and the runner faked."""
from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

_MODULE = Path(__file__).resolve().parent.parent / "merger.py"
_spec = importlib.util.spec_from_file_location("merger_under_test", _MODULE)
mg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mg)

REPO = "o/r"
GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
SEAL = "ab" * 32


def g(cwd, *args) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True, env=GIT_ENV).stdout.strip()


def commit(wt: Path, files: dict, msg: str) -> str:
    for rel, body in files.items():
        (wt / rel).parent.mkdir(parents=True, exist_ok=True)
        (wt / rel).write_text(body)
    g(wt, "add", "-A")
    g(wt, "commit", "-qm", msg)
    return g(wt, "rev-parse", "HEAD")


def pr(n, sha, *, armed=True, draft=False, labels=(), fork=False, created="2026-10-01T00:00:00Z"):
    return {"number": n, "draft": draft, "auto_merge": {"merge_method": "merge"} if armed else None, "created_at": created,
            "labels": [{"name": lb} for lb in labels], "head": {"sha": sha, "repo": {"full_name": "stranger/r" if fork else REPO}},
            "base": {"repo": {"full_name": REPO}}}


class FakeGH:
    """GitHub as the merger may see it: every call is a path for hosted_compare.gh_get, i.e. a bare GET."""

    def __init__(self):
        self.prs: list = []
        self.paths: list = []
        self.conclusion = "success"

    def __call__(self, path):
        self.paths.append(path)
        if path.startswith(f"repos/{REPO}/pulls?"):
            return self.prs if path.endswith("page=1") else []
        if path == f"repos/{REPO}/branches/main/protection/required_status_checks":
            return {"checks": [{"context": "ctx-a", "app_id": 15368}]}
        m = re.fullmatch(rf"repos/{REPO}/commits/([0-9a-f]{{40}})/(check-runs|status)\?per_page=100&page=1", path)
        if m and m[2] == "check-runs":
            return {"check_runs": [{"name": "ctx-a", "status": "completed", "conclusion": self.conclusion, "head_sha": m[1],
                                    "app": {"id": 15368, "slug": "github-actions"}}]}
        if m:
            return {"statuses": []}
        raise AssertionError(f"unexpected GitHub read {path}")


class FakeRunner:
    def __init__(self, overall="BLOCKED", plan_rc=0):
        self.overall, self.plan_rc, self.calls = overall, plan_rc, []

    def __call__(self, argv, cwd, env, timeout):
        sub, run_dir = argv[3], Path(argv[argv.index("--run-dir") + 1])
        call = {"sub": sub, "argv": list(argv), "cwd": Path(cwd), "env": dict(env), "cwd_head": g(cwd, "rev-parse", "HEAD")}
        if "--contexts-file" in argv:
            call["matrix"] = Path(argv[argv.index("--contexts-file") + 1]).read_text()
        if "--worktree" in argv:
            call["worktree_head"] = g(argv[argv.index("--worktree") + 1], "rev-parse", "HEAD")
        self.calls.append(call)
        if sub == "plan":
            return subprocess.CompletedProcess(argv, self.plan_rc, "{}", "")
        if sub == "run":
            return subprocess.CompletedProcess(argv, 0, f"policy.change_map: PASS\nseal={SEAL}  # end of run\n", "")
        (run_dir / "status.json").write_text(json.dumps({"overall": self.overall, "candidate_sha": self.calls[0].get("worktree_head"),
                                                         "contexts": {"status": "ok", "results": {"ctx-a": {"verdict": "OK", "mapping": "executed"}}},
                                                         "checks": {"policy.change_map": {"status": "PASS"}}}))
        return subprocess.CompletedProcess(argv, 0, self.overall + "\n", "")


@pytest.fixture
def world(tmp_path, monkeypatch):
    """origin: main moved past two PRs; #1 merges clean and rewrites the contexts matrix, #2 conflicts with main."""
    src = tmp_path / "src"
    src.mkdir()
    g(src, "init", "-q", "-b", "main")
    base0 = commit(src, {"a.txt": "a\n", "c.txt": "c\n", mg.MATRIX: "base matrix\n"}, "base")
    g(src, "checkout", "-q", "-b", "pr1")
    head1 = commit(src, {"b.txt": "pr1\n", mg.MATRIX: "candidate matrix\n"}, "pr1")
    g(src, "checkout", "-q", "-b", "pr2", base0)
    head2 = commit(src, {"c.txt": "pr2\n"}, "pr2")
    g(src, "checkout", "-q", "main")
    base = commit(src, {"c.txt": "main\n"}, "main moves")
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(src), str(origin)], check=True, env=GIT_ENV)
    g(origin, "update-ref", "refs/pull/1/head", head1)
    g(origin, "update-ref", "refs/pull/2/head", head2)
    gh, runner = FakeGH(), FakeRunner()
    monkeypatch.setattr(mg.hc, "gh_get", gh)
    monkeypatch.setattr(mg, "runner_exec", runner)
    w = type("World", (), {})()
    w.state, w.origin, w.gh, w.runner = tmp_path / "state", origin, gh, runner
    w.base, w.head1, w.head2 = base, head1, head2
    w.tick = lambda node=mg.HOST: mg.main(["tick", "--node", node, "--repo", REPO, "--state-dir", str(w.state), "--remote-url", str(origin), "--python", "py"])
    w.journal = lambda: mg.read_journal(w.state)
    return w


def test_fork_pr_is_refused_journalled_once_and_never_fetched_or_run(world):
    world.gh.prs = [pr(9, "9" * 40, fork=True)]
    assert world.tick() == 0 and world.tick() == 0
    refused = [r for r in world.journal() if r["kind"] == "refused"]
    assert [(r["pr"], r["why"]) for r in refused] == [(9, "fork")]
    assert world.runner.calls == []
    assert "refs/merger/pr/9" not in g(world.state / "repo.git", "for-each-ref", "--format=%(refname)")


def test_draft_and_unarmed_prs_are_ignored_and_a_labelled_one_is_taken(world):
    world.gh.prs = [pr(1, world.head1, draft=True), pr(2, world.head2, armed=False)]
    assert world.tick() == 0
    assert world.runner.calls == [] and [r for r in world.journal() if r["kind"] == "decision"] == []
    world.gh.prs = [pr(1, world.head1, armed=False, labels=[mg.LABEL])]
    assert world.tick() == 0
    assert [r["pr"] for r in world.journal() if r["kind"] == "decision"] == [1]


def test_conflict_is_a_decision_with_no_run(world):
    world.gh.prs = [pr(2, world.head2)]
    assert world.tick() == 0
    (d,) = [r for r in world.journal() if r["kind"] == "decision"]
    assert (d["overall"], d["conflicts"], d["candidate_sha"], d["run_dir"]) == ("CONFLICT", ["c.txt"], None, None)
    assert world.runner.calls == []
    assert not (world.state / "cand").exists() or not any((world.state / "cand").iterdir())


def test_candidate_is_main_plus_head_and_the_gate_runs_from_base_with_the_base_matrix(world):
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0
    (d,) = [r for r in world.journal() if r["kind"] == "decision"]
    repo = world.state / "repo.git"
    assert g(repo, "rev-list", "--parents", "-n1", d["candidate_sha"]).split()[1:] == [world.base, world.head1]
    assert g(repo, "show", "-s", "--format=%an %cn", d["candidate_sha"]) == "localci-merger localci-merger"
    plan, run, status = world.runner.calls
    assert [c["sub"] for c in (plan, run, status)] == ["plan", "run", "status"]
    for c in (plan, run, status):
        assert c["cwd"] == world.state / "base" / world.base and c["cwd_head"] == world.base
        assert c["argv"][:3] == ["py", "-m", "scripts.localci.runner"] and c["env"]["PYTHONPATH"] == str(c["cwd"])
        assert not [k for k in c["env"] if k.endswith(("TOKEN", "_KEY", "SECRET")) or k.startswith("GH_")]
    assert plan["argv"][plan["argv"].index("--base") + 1] == world.base
    assert plan["argv"][plan["argv"].index("--candidate") + 1] == d["candidate_sha"] == plan["worktree_head"]
    assert plan["matrix"] == "base matrix\n"   # the candidate's rewritten matrix never judges it
    assert status["argv"][-2:] == ["--seal", SEAL]
    assert (d["overall"], d["contexts"], d["seal"], d["base_sha"], d["head_sha"]) == ("BLOCKED", {"ctx-a": "OK"}, SEAL, world.base, world.head1)
    hosted = d["hosted_compare"]
    assert hosted["sha"] == world.head1 and "merge-group" in hosted["note"] and hosted["counts"]["AGREE"] == 1
    assert json.loads((Path(d["run_dir"]) / "hosted_compare.json").read_text())["sha"] == world.head1
    assert {"ts", "host", "lease_id", "elapsed_s", "run_dir", "checks"} <= set(d) and d["host"] == mg.HOST
    assert not (world.state / "cand" / f"pr1-{world.head1[:12]}-{world.base[:12]}").exists()


def test_a_head_that_could_fast_forward_still_gets_a_merge_commit(world):
    src = world.state.parent / "src"
    g(src, "checkout", "-q", "-b", "pr3", world.base)
    head3 = commit(src, {"d.txt": "pr3\n"}, "pr3 on top of main")
    g(world.origin, "fetch", "-q", str(src), "+pr3:refs/pull/3/head")
    world.gh.prs = [pr(3, head3)]
    assert world.tick() == 0
    (d,) = [r for r in world.journal() if r["kind"] == "decision"]
    assert g(world.state / "repo.git", "rev-list", "--parents", "-n1", d["candidate_sha"]).split()[1:] == [world.base, head3]


def test_the_same_pr_head_and_base_is_never_run_twice_but_a_new_head_is(world):
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0 and world.tick() == 0
    assert len([r for r in world.journal() if r["kind"] == "decision"]) == 1 and len(world.runner.calls) == 3
    src = world.state.parent / "src"
    g(src, "checkout", "-q", "pr1")
    head1b = commit(src, {"b.txt": "pr1 again\n"}, "pr1 v2")
    g(world.origin, "fetch", "-q", str(src), "+pr1:refs/pull/1/head")
    world.gh.prs = [pr(1, head1b)]
    assert world.tick() == 0
    assert [r["head_sha"] for r in world.journal() if r["kind"] == "decision"] == [world.head1, head1b]


def test_a_head_never_decided_goes_before_one_decided_at_an_older_base(world):
    recs = [{"kind": "decision", "pr": 1, "head_sha": world.head1, "base_sha": "c" * 40, "ts": "2026-10-07T00:00:00Z"}]
    todo, _ = mg.triage([pr(1, world.head1, created="2026-01-01"), pr(3, "3" * 40, created="2026-10-01")], REPO, recs, world.base)
    assert [p["number"] for p in todo] == [3, 1]


def test_a_head_that_moved_between_the_list_and_the_fetch_is_skipped_not_decided(world):
    world.gh.prs = [pr(1, world.head2)]   # the API says one head, refs/pull/1/head holds another
    assert world.tick() == 0
    assert [(r["kind"], r.get("why")) for r in world.journal()] == [("skipped", "head_moved")] and world.runner.calls == []


def test_node_mismatch_exits_0_and_leaves_the_lease_alone(world):
    world.state.mkdir()
    (world.state / "lease.json").write_text('{"host": "x", "pid": 1}')
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick(node="not-" + mg.HOST) == 0
    assert (world.state / "lease.json").read_text() == '{"host": "x", "pid": 1}' and not (world.state / "lease.lock").exists()
    assert [(r["kind"], r["why"]) for r in world.journal()] == [("skipped", "node")] and world.runner.calls == []


def test_a_live_lease_is_respected(world):
    world.state.mkdir()
    live = {"host": mg.HOST, "pid": os.getpid(), "pid_start": mg.proc_start(os.getpid()), "lease_id": "live"}
    (world.state / "lease.json").write_text(json.dumps(live))
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0
    assert json.loads((world.state / "lease.json").read_text()) == live and world.runner.calls == []
    assert [(r["kind"], r["holder"]["lease_id"]) for r in world.journal()] == [("skipped", "live")]


def test_a_held_lease_lock_is_respected(world):
    world.state.mkdir()
    with open(world.state / "lease.lock", "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        world.gh.prs = [pr(1, world.head1)]
        assert world.tick() == 0
    assert world.runner.calls == [] and [r["why"] for r in world.journal()] == ["lease"]


def test_a_dead_holders_lease_is_reclaimed_journalled_and_released(world):
    world.state.mkdir()
    dead = subprocess.Popen(["true"])
    dead.wait()
    (world.state / "lease.json").write_text(json.dumps({"host": mg.HOST, "pid": dead.pid, "pid_start": "then", "lease_id": "stale"}))
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0
    kinds = [r["kind"] for r in world.journal()]
    assert kinds == ["lease_reclaimed", "decision"] and world.journal()[0]["stale"]["lease_id"] == "stale"
    assert world.journal()[0]["lease_id"] == world.journal()[1]["lease_id"] != "stale"
    assert not (world.state / "lease.json").exists()


def test_a_failed_github_read_is_an_error_line_and_the_lease_is_released(world, monkeypatch):
    def down(path):
        raise mg.hc.CompareError("gh api down")
    monkeypatch.setattr(mg.hc, "gh_get", down)
    assert world.tick() == 1
    assert [(r["kind"], r["error"]) for r in world.journal()] == [("error", "gh api down")]
    assert not (world.state / "lease.json").exists()


def test_a_runner_plan_failure_is_an_error_decision_never_a_verdict(world, monkeypatch):
    monkeypatch.setattr(mg, "runner_exec", FakeRunner(plan_rc=1))
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0
    (d,) = [r for r in world.journal() if r["kind"] == "decision"]
    assert d["overall"] == "ERROR" and "plan" in d["error"] and d["runner_rc"] == {"plan_rc": 1}


def test_every_github_call_is_a_get_through_hosted_compare(world, monkeypatch):
    real = subprocess.run

    def guarded(argv, *a, **kw):
        assert argv[0] != "gh", f"a GitHub call bypassed hosted_compare.gh_get: {argv}"
        return real(argv, *a, **kw)
    monkeypatch.setattr(subprocess, "run", guarded)
    world.gh.prs = [pr(1, world.head1), pr(9, "9" * 40, fork=True)]
    assert world.tick() == 0
    assert world.gh.paths and all(not re.search(r"/(merge|labels|comments|reviews)\b", p) for p in world.gh.paths)


def test_merge_refuses_with_exit_2_whatever_it_is_given(capsys):
    assert mg.main(["merge"]) == 2 and mg.main(["merge", "--pr", "1", "--force"]) == 2
    assert mg.PHASE_E in capsys.readouterr().err


def test_selftest_passes(capsys):
    assert mg.main(["--selftest"]) == 0
    assert "FAIL" not in capsys.readouterr().out
