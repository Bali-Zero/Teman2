"""Guilt + innocence corpus for the shadow merger: real temporary git repos, a local origin, GitHub and the runner faked."""
from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
import time
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
    def __init__(self, overall="BLOCKED", plan_rc=0, run_out=f"policy.change_map: PASS\nseal={SEAL}  # end of run\n", sleep=0, alarm=0,
                 status_rc=0, bind=None):
        self.overall, self.plan_rc, self.run_out, self.sleep, self.alarm, self.calls = overall, plan_rc, run_out, sleep, alarm, []
        self.status_rc, self.bind = status_rc, bind or {}

    def __call__(self, argv, cwd, env, timeout):
        sub, run_dir = argv[3], Path(argv[argv.index("--run-dir") + 1])
        call = {"sub": sub, "argv": list(argv), "cwd": Path(cwd), "env": dict(env), "cwd_head": g(cwd, "rev-parse", "HEAD")}
        if "--contexts-file" in argv:
            call["matrix"] = Path(argv[argv.index("--contexts-file") + 1]).read_text()
        if "--worktree" in argv:
            call["worktree_head"] = g(argv[argv.index("--worktree") + 1], "rev-parse", "HEAD")
        self.calls.append(call)
        if sub == "plan":
            if self.alarm:   # the watchdog fires while the gate runs, whatever the clone and fetch cost before it
                signal.alarm(self.alarm)
            return subprocess.CompletedProcess(argv, self.plan_rc, "{}", "")
        if sub == "run":
            time.sleep(self.sleep)
            return subprocess.CompletedProcess(argv, 0, self.run_out, "")
        plan = self.calls[0]["argv"]
        bind = {"candidate_sha": self.calls[0].get("worktree_head"), "base_sha": plan[plan.index("--base") + 1], "seal": SEAL, **self.bind}
        (run_dir / "status.json").write_text(json.dumps({"overall": self.overall, **bind,
                                                         "contexts": {"status": "ok", "results": {"ctx-a": {"verdict": "OK", "mapping": "executed"}}},
                                                         "checks": {"policy.change_map": {"status": "PASS", "duration_s": 12.5}}}))
        return subprocess.CompletedProcess(argv, self.status_rc, self.overall + "\n", "")


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
    w.base, w.head1, w.head2, w.src = base, head1, head2, src
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


def test_candidate_is_main_plus_head_squashed_and_the_gate_runs_from_base_with_the_base_matrix(world):
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0
    (d,) = [r for r in world.journal() if r["kind"] == "decision"]
    repo = world.state / "repo.git"
    assert g(repo, "rev-list", "--parents", "-n1", d["candidate_sha"]).split()[1:] == [world.base]   # the queue squashes: one parent, main
    files = {f: g(repo, "show", f"{d['candidate_sha']}:{f}") for f in ("b.txt", "c.txt", mg.MATRIX)}
    assert files == {"b.txt": "pr1", "c.txt": "main", mg.MATRIX: "candidate matrix"}
    assert g(repo, "show", "-s", "--format=%an %cn", d["candidate_sha"]) == "localci-merger localci-merger"
    plan, run, status = world.runner.calls
    assert [c["sub"] for c in (plan, run, status)] == ["plan", "run", "status"]
    for c in (plan, run, status):
        assert c["cwd"] == world.state / "base" / world.base and c["cwd_head"] == world.base
        assert c["argv"][:3] == ["py", "-m", "scripts.localci.runner"] and c["env"]["PYTHONPATH"] == str(c["cwd"])
        assert not [k for k in c["env"] if k.endswith(("TOKEN", "_KEY", "SECRET")) or k.startswith("GH_")]
    assert plan["argv"][plan["argv"].index("--base") + 1] == world.base
    assert "--pr-number" not in plan["argv"]   # this base's runner does not take the flag: never break an older runner's plan
    assert plan["argv"][plan["argv"].index("--candidate") + 1] == d["candidate_sha"] == plan["worktree_head"]
    assert plan["matrix"] == "base matrix\n"   # the candidate's rewritten matrix never judges it
    assert status["argv"][-2:] == ["--seal", SEAL]
    assert (d["overall"], d["contexts"], d["seal"], d["base_sha"], d["head_sha"]) == ("BLOCKED", {"ctx-a": "OK"}, SEAL, world.base, world.head1)
    hosted = d["hosted_compare"]
    assert hosted["sha"] == world.head1 and "merge-group" in hosted["note"] and hosted["counts"]["AGREE"] == 1
    assert json.loads((Path(d["run_dir"]) / "hosted_compare.json").read_text())["sha"] == world.head1
    assert {"ts", "host", "lease_id", "elapsed_s", "run_dir", "checks"} <= set(d) and d["host"] == mg.HOST
    assert d["checks"] == {"policy.change_map": "PASS"} and d["durations"] == {"policy.change_map": 12.5}
    assert not (world.state / "cand" / f"pr1-{world.head1[:12]}-{world.base[:12]}").exists()


def test_a_head_on_top_of_main_is_still_a_new_squash_commit_never_the_head_itself(world):
    src = world.state.parent / "src"
    g(src, "checkout", "-q", "-b", "pr3", world.base)
    commit(src, {"d.txt": "pr3\n"}, "pr3 on top of main")
    head3 = commit(src, {"e.txt": "pr3 again\n"}, "pr3 second commit")
    g(world.origin, "fetch", "-q", str(src), "+pr3:refs/pull/3/head")
    world.gh.prs = [pr(3, head3)]
    assert world.tick() == 0
    (d,) = [r for r in world.journal() if r["kind"] == "decision"]
    repo = world.state / "repo.git"
    assert d["candidate_sha"] != head3 and g(repo, "rev-list", "--parents", "-n1", d["candidate_sha"]).split()[1:] == [world.base]
    assert g(repo, "rev-parse", f"{d['candidate_sha']}^{{tree}}") == g(repo, "rev-parse", f"{head3}^{{tree}}")


def test_a_head_already_in_main_is_skipped_once_not_at_every_tick(world):
    src = world.state.parent / "src"
    old = g(src, "rev-parse", "main~1")
    g(world.origin, "update-ref", "refs/pull/4/head", old)
    world.gh.prs = [pr(4, old)]
    assert world.tick() == 0 and world.tick() == 0
    assert [(r["kind"], r.get("why")) for r in world.journal()] == [("skipped", "head_in_base")] and world.runner.calls == []


def test_a_merge_that_fails_without_a_conflict_is_one_error_decision_not_a_loop(world):
    src = world.state.parent / "src"
    g(src, "checkout", "-q", "--orphan", "stray")
    stray = commit(src, {"z.txt": "unrelated\n"}, "unrelated history")
    g(world.origin, "fetch", "-q", str(src), "+stray:refs/pull/5/head")
    world.gh.prs = [pr(5, stray), pr(1, world.head1, created="2026-10-02T00:00:00Z")]
    assert world.tick() == 1 and world.tick() == 0
    decided = [(r["pr"], r["overall"]) for r in world.journal() if r["kind"] == "decision"]
    assert decided == [(5, "ERROR"), (1, "BLOCKED")] and "conflicted path" in world.journal()[0]["error"]


def test_the_watchdog_turns_a_hung_gate_into_an_error_decision_and_frees_the_lease(world, monkeypatch):
    monkeypatch.setattr(mg, "runner_exec", FakeRunner(sleep=10, alarm=1))
    world.gh.prs = [pr(1, world.head1)]
    rc = mg.main(["tick", "--node", mg.HOST, "--repo", REPO, "--state-dir", str(world.state), "--remote-url", str(world.origin),
                  "--python", "py", "--tick-timeout", "120"])   # the fake re-arms 1 s at the gate: a loaded host's clone cannot trip it
    (d,) = [r for r in world.journal() if r["kind"] == "decision"]
    assert rc == 1 and d["overall"] == "ERROR" and "tick-timeout" in d["error"] and not (world.state / "lease.json").exists()


def test_a_runner_past_its_timeout_is_terminated_before_it_is_killed(tmp_path):
    code = "import signal,sys,time\nsignal.signal(signal.SIGTERM, lambda *a: (print('cleaned up', flush=True), sys.exit(3)))\nprint('up', flush=True)\ntime.sleep(30)"
    t0 = time.monotonic()
    res = mg.runner_exec([sys.executable, "-c", code], tmp_path, dict(os.environ), timeout=2)
    assert res.returncode == 124 and "cleaned up" in res.stdout and "timed out" in res.stderr and time.monotonic() - t0 < 20


def test_only_the_seal_printed_before_candidate_code_runs_is_passed_on(world, monkeypatch):
    forged = "cd" * 32
    monkeypatch.setattr(mg, "runner_exec", FakeRunner(run_out=f"seal={SEAL}  # trusted checks done\nctx.x: ERROR — boom\nseal={forged}\n"))
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0
    assert mg.runner_exec.calls[2]["argv"][-2:] == ["--seal", SEAL]


@pytest.mark.parametrize("runner", [dict(status_rc=1), dict(run_out="policy.change_map: PASS\nseal WITHHELD  # no seal\n"),
                                    dict(bind={"candidate_sha": "e" * 40}), dict(bind={"seal": "cd" * 32})],
                         ids=["status-failed", "no-seal", "other-candidate", "other-seal"])
def test_a_status_that_failed_or_is_not_bound_to_this_run_lends_no_verdict(world, monkeypatch, runner):
    monkeypatch.setattr(mg, "runner_exec", FakeRunner(overall="PASS", **runner))
    world.gh.prs = [pr(1, world.head1)]
    world.tick()
    (d,) = [r for r in world.journal() if r["kind"] == "decision"]
    assert (d["overall"], d["contexts"]) == ("ERROR", {}) and d["error"]


@pytest.mark.parametrize("scope", ["global-file", "env-scope", "env-parameters"])
def test_host_git_config_never_reaches_the_candidate(world, monkeypatch, tmp_path, scope):
    marker = tmp_path / "HOST_FILTER_RAN"
    hook = tmp_path / "evil.sh"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\ncat\n")
    hook.chmod(0o755)
    config = {"filter.evil.smudge": str(hook), "filter.evil.clean": str(hook), "filter.evil.required": "true", "merge.evil.driver": f"{hook} %O %A %B"}
    if scope == "global-file":
        evil = tmp_path / "evil.gitconfig"
        evil.write_text('[filter "evil"]\n' + "".join(f"\t{k.split('.')[-1]} = {v}\n" for k, v in config.items() if k.startswith("filter."))
                        + f'[merge "evil"]\n\tdriver = {config["merge.evil.driver"]}\n')
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(evil))
    elif scope == "env-parameters":   # the form `git -c` hands to its children
        monkeypatch.setenv("GIT_CONFIG_PARAMETERS", " ".join(f"'{k}'='{v}'" for k, v in config.items()))
    else:
        monkeypatch.setenv("GIT_CONFIG_COUNT", str(len(config)))
        for i, (k, v) in enumerate(config.items()):
            monkeypatch.setenv(f"GIT_CONFIG_KEY_{i}", k)
            monkeypatch.setenv(f"GIT_CONFIG_VALUE_{i}", v)
    src = world.state.parent / "src"
    g(src, "checkout", "-q", "-b", "pr6", world.base)
    head6 = commit(src, {".gitattributes": "* filter=evil merge=evil\n", "f.txt": "x\n"}, "attributes that name a host filter")
    g(world.origin, "fetch", "-q", str(src), "+pr6:refs/pull/6/head")
    subprocess.run(["git", "-C", str(src), "-c", f"filter.evil.smudge={hook}", "show", "HEAD:f.txt"], check=True, capture_output=True, env=GIT_ENV)
    assert not marker.exists()   # `show` filters nothing: the probe itself leaves no marker
    subprocess.run(["sh", str(hook)], input="", text=True, check=True)
    assert marker.exists()       # ...and the planted filter does run when invoked: the guilt below can go red
    marker.unlink()
    world.gh.prs = [pr(6, head6)]
    assert world.tick() == 0
    assert not marker.exists() and [r["overall"] for r in world.journal() if r["kind"] == "decision"] == ["BLOCKED"]
    for c in world.runner.calls:
        assert (c["env"]["GIT_CONFIG_GLOBAL"], c["env"]["GIT_CONFIG_NOSYSTEM"], c["env"]["GIT_CONFIG_KEY_0"]) == ("/dev/null", "1", "core.hooksPath")



def test_a_mirror_local_fsmonitor_never_runs_during_the_merge(world, tmp_path):
    marker = tmp_path / "FSMONITOR_RAN"
    hook = tmp_path / "fsmon.sh"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\n")
    hook.chmod(0o755)
    probe = tmp_path / "probe"
    probe.mkdir()
    g(probe, "init", "-q")
    subprocess.run(["git", "-C", str(probe), "-c", f"core.fsmonitor={hook}", "status"], capture_output=True, env=GIT_ENV)
    assert marker.exists()   # the planted monitor does run on an index refresh: the guilt below can go red
    marker.unlink()
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0   # the first tick creates the mirror
    g(world.state / "repo.git", "config", "core.fsmonitor", str(hook))
    src = world.state.parent / "src"
    g(src, "checkout", "-q", "-b", "pr7", world.base)
    head7 = commit(src, {"g.txt": "y\n"}, "second")
    g(world.origin, "fetch", "-q", str(src), "+pr7:refs/pull/7/head")
    world.gh.prs = [pr(7, head7)]
    assert world.tick() == 0
    assert not marker.exists() and [r["pr"] for r in world.journal() if r["kind"] == "decision"] == [1, 7]


def test_host_attributes_never_rewrite_the_candidate_the_runner_sees(world, monkeypatch, tmp_path):
    xdg = tmp_path / "xdg"
    (xdg / "git").mkdir(parents=True)
    (xdg / "git" / "attributes").write_text("* text eol=crlf\n")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    probe = tmp_path / "probe"
    probe.mkdir()
    g(probe, "init", "-q")
    commit(probe, {"h.txt": "a\nb\n"}, "lf")
    (probe / "h.txt").unlink()
    subprocess.run(["git", "-C", str(probe), "checkout", "--", "h.txt"], check=True, env={**GIT_ENV, "XDG_CONFIG_HOME": str(xdg)})
    assert (probe / "h.txt").read_bytes() == b"a\r\nb\r\n"   # the host file does rewrite a checkout: the guilt below can go red
    src = world.state.parent / "src"
    g(src, "checkout", "-q", "-b", "pr8", world.base)
    head8 = commit(src, {"h.txt": "a\nb\n"}, "lf file")
    g(world.origin, "fetch", "-q", str(src), "+pr8:refs/pull/8/head")
    seen, inner = {}, mg.runner_exec

    def spy(argv, cwd, env, timeout):
        if "--worktree" in argv:
            seen["h"] = (Path(argv[argv.index("--worktree") + 1]) / "h.txt").read_bytes()
        return inner(argv, cwd, env, timeout)
    monkeypatch.setattr(mg, "runner_exec", spy)
    world.gh.prs = [pr(8, head8)]
    assert world.tick() == 0 and seen["h"] == b"a\nb\n"

def test_a_caller_git_dir_or_index_never_redirects_the_merger(world, monkeypatch, tmp_path):
    decoy = tmp_path / "decoy.git"
    subprocess.run(["git", "init", "-q", "--bare", str(decoy)], check=True, env=GIT_ENV)
    monkeypatch.setenv("GIT_DIR", str(decoy))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "decoy.index"))
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0
    assert [r["overall"] for r in world.journal() if r["kind"] == "decision"] == ["BLOCKED"] and not (tmp_path / "decoy.index").exists()


def test_a_recycled_pid_is_not_the_holder(world):
    world.state.mkdir()
    (world.state / "lease.json").write_text(json.dumps({"host": mg.HOST, "pid": os.getpid(), "pid_start": "Thu Jan  1 00:00:00 1970", "lease_id": "old"}))
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0
    assert [r["kind"] for r in world.journal()] == ["lease_reclaimed", "decision"]


def test_the_journal_is_private_and_a_torn_tail_does_not_swallow_the_next_decision(world):
    world.state.mkdir()
    (world.state / "decisions.jsonl").write_text('{"kind": "decision", "pr": 1, "head_s')
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0
    assert [r["pr"] for r in world.journal() if r["kind"] == "decision"] == [1]
    fresh = world.state.parent / "fresh"
    fresh.mkdir()
    mg.journal(fresh, {"kind": "probe"})
    assert (fresh / "decisions.jsonl").stat().st_mode & 0o777 == 0o600


def test_a_state_dir_bound_to_another_repo_is_refused(world):
    world.state.mkdir()
    (world.state / "repo").write_text("other/repo\n")
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 2 and world.journal() == [] and world.runner.calls == []


def test_a_relative_state_dir_is_resolved_before_any_git_or_runner_path(world, monkeypatch):
    monkeypatch.chdir(world.state.parent)
    world.gh.prs = [pr(1, world.head1)]
    assert mg.main(["tick", "--node", mg.HOST, "--repo", REPO, "--state-dir", "state", "--remote-url", str(world.origin), "--python", "py"]) == 0
    (d,) = [r for r in world.journal() if r["kind"] == "decision"]
    assert Path(d["run_dir"]).is_absolute() and d["overall"] == "BLOCKED"


def test_errors_are_redacted_before_they_reach_the_journal():
    leaky = "fatal: https://x-access-token:ghs_abcdefghijklmnopqrstuv@github.com/o/r.git token ghp_ABCDEFGHIJKLMNOPQRST and github_pat_11AAAAAAAAAAAAAAAAAAAA"
    out = mg.redact(leaky)
    assert "ghs_" not in out and "ghp_" not in out and "github_pat_" not in out and "x-access-token" not in out and "github.com/o/r.git" in out


def test_a_remote_url_carrying_credentials_is_refused(world):
    assert mg.main(["tick", "--node", mg.HOST, "--state-dir", str(world.state), "--remote-url", "https://x:y@github.com/o/r.git"]) == 2
    assert not world.state.exists()


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


def test_a_missing_gh_is_an_error_line_not_a_traceback(world, monkeypatch):
    def no_gh(path):
        raise FileNotFoundError(2, "No such file or directory", "gh")
    monkeypatch.setattr(mg.hc, "gh_get", no_gh)
    assert world.tick() == 1
    assert [r["kind"] for r in world.journal()] == ["error"] and "gh" in world.journal()[0]["error"]
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


def test_a_filesystem_error_after_a_pr_is_picked_is_an_error_decision_not_a_retry_loop(world, monkeypatch):
    def broken(*a, **kw):
        raise PermissionError(13, "Permission denied", "cand")
    monkeypatch.setattr(mg, "fresh_worktree", broken)
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 1 and world.tick() == 0
    assert [(r["kind"], r.get("overall")) for r in world.journal()] == [("decision", "ERROR")]


WRAPPER = _MODULE.parent / "localci_merger_tick.sh"
HB_LIB = _MODULE.parents[1] / "lib" / "heartbeat.sh"
# launchd runs the wrapper with /bin/bash (3.2 on macOS, where a ${VAR:?} error reaches the EXIT trap with status 0); the tests
# run the same interpreter whenever it exists, or a bash 5 would keep that guilt green
BASH = "/bin/bash" if Path("/bin/bash").exists() else "bash"


def wrap(env):
    return subprocess.run([BASH, str(WRAPPER)], env=env, capture_output=True, text=True)


def heartbeat(home):
    return json.loads((home / ".organism" / "last_seen" / "pro.localci_merger.json").read_text())


def mirror_world(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    g(src, "init", "-q", "-b", "main")
    commit(src, {"scripts/localci/merger.py": "v1 --code-sha\n", "scripts/localci/hosted_compare.py": "hc\n",
                 "scripts/lib/heartbeat.sh": HB_LIB.read_text()}, "v1")
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(src), str(origin)], check=True, env=GIT_ENV)
    fake_py = tmp_path / "py"
    fake_py.write_text('#!/bin/sh\necho "$@" > "$OUT_ARGS"\ncat "$2" > "$OUT_CODE"\n')
    fake_py.chmod(0o755)
    env = {"HOME": str(tmp_path), "PATH": os.environ["PATH"], "MERGER_PYTHON": str(fake_py), "MERGER_NODE": "n1", "MERGER_STATE_DIR": str(tmp_path / "state"),
           "MERGER_SEED": str(origin), "MERGER_REMOTE_URL": str(origin),
           "OUT_ARGS": str(tmp_path / "args"), "OUT_CODE": str(tmp_path / "code")}
    return src, origin, fake_py, env


def test_the_launchd_wrapper_runs_main_as_committed_and_survives_a_dead_remote(tmp_path):
    src, origin, fake_py, env = mirror_world(tmp_path)
    env = {**env, "GIT_DIR": str(tmp_path / "decoy"), "GIT_CONFIG_PARAMETERS": "'core.hooksPath'='/nowhere'"}
    first = wrap(env)
    assert first.returncode == 0, first.stderr
    assert (tmp_path / "code").read_text() == "v1 --code-sha\n"
    sha1 = g(origin, "rev-parse", "main")
    args = (tmp_path / "args").read_text().split()
    assert args == ["-I", args[1], "tick", "--node", "n1", "--state-dir", env["MERGER_STATE_DIR"], "--python", str(fake_py), f"--code-sha={sha1}"]
    commit(src, {"scripts/localci/merger.py": "v2 --code-sha\n"}, "v2")
    g(src, "push", "-q", str(origin), "main")
    assert wrap(env).returncode == 0 and (tmp_path / "code").read_text() == "v2 --code-sha\n"
    origin.rename(tmp_path / "gone.git")
    dead = wrap(env)
    assert dead.returncode == 0 and "fetch failed" in dead.stderr and (tmp_path / "code").read_text() == "v2 --code-sha\n"
    assert heartbeat(tmp_path)["status"] == "ok" and heartbeat(tmp_path)["note"].endswith(g(src, "rev-parse", "main")[:12])


def test_the_wrapper_leaves_a_heartbeat_on_every_exit_and_honours_its_kill_switch(tmp_path):
    _, _, fake_py, env = mirror_world(tmp_path)
    first = wrap({**env, "LOCALCI_MERGER_ENABLED": "false"})   # nothing extracted yet: said aloud, no git, no state
    assert first.returncode == 0 and "no heartbeat library" in first.stderr and not (tmp_path / "state").exists()
    assert wrap(env).returncode == 0 and heartbeat(tmp_path)["status"] == "ok"
    off = wrap({**env, "LOCALCI_MERGER_ENABLED": "false"})
    assert off.returncode == 0 and heartbeat(tmp_path)["status"] == "disabled"
    fake_py.write_text("#!/bin/sh\nexit 1\n")
    failed = wrap(env)
    assert failed.returncode == 1 and heartbeat(tmp_path)["status"] == "error"
    no_mirror = wrap({**env, "MERGER_SEED": str(tmp_path / "no-seed.git"), "MERGER_STATE_DIR": str(tmp_path / "state2"),
                      "MERGER_HEARTBEAT_LIB": str(tmp_path / "state" / "heartbeat.sh")})
    assert no_mirror.returncode != 0 and heartbeat(tmp_path)["status"] == "error"


@pytest.mark.parametrize("missing", ["MERGER_PYTHON", "MERGER_NODE"])
def test_a_missing_required_variable_stops_before_any_git_and_says_error(tmp_path, missing):
    _, _, _, env = mirror_world(tmp_path)
    env["MERGER_HEARTBEAT_LIB"] = str(HB_LIB)
    res = wrap({k: v for k, v in env.items() if k != missing})
    assert res.returncode == 2 and "MERGER_PYTHON and MERGER_NODE are required" in res.stderr
    assert not (tmp_path / "state").exists() and heartbeat(tmp_path)["status"] == "error"


def test_the_heartbeat_library_comes_from_the_mirror_at_the_ticks_sha_never_from_a_checkout(tmp_path):
    src, origin, _, env = mirror_world(tmp_path)
    planted = tmp_path / "nuzantara" / "scripts" / "lib" / "heartbeat.sh"   # the working checkout the wrapper used to read
    planted.parent.mkdir(parents=True)
    planted.write_text(f"touch {tmp_path / 'checkout-ran'}\n")
    marked = HB_LIB.read_text() + f"\n[ -n \"${{1:-}}\" ] && echo \"$2\" >> {tmp_path / 'main-v2-ran'}\n"
    commit(src, {"scripts/lib/heartbeat.sh": marked}, "heartbeat v2")
    g(src, "push", "-q", str(origin), "main")
    assert wrap(env).returncode == 0 and heartbeat(tmp_path)["status"] == "ok"
    assert (tmp_path / "state" / "heartbeat.sh").read_text() == marked and (tmp_path / "main-v2-ran").read_text() == "ok\n"
    assert not list((tmp_path / "state").glob(".heartbeat.sh.*"))   # each run's temp copy is moved or removed, never left behind
    assert not (tmp_path / "checkout-ran").exists()
    off = wrap({**env, "LOCALCI_MERGER_ENABLED": "false"})   # an early exit runs the copy the last tick extracted
    assert off.returncode == 0 and (tmp_path / "main-v2-ran").read_text() == "ok\ndisabled\n" and not (tmp_path / "checkout-ran").exists()


@pytest.mark.parametrize("library", ["absent", "empty"])
def test_a_missing_heartbeat_library_is_said_aloud_and_changes_nothing_else(tmp_path, library):
    _, _, _, env = mirror_world(tmp_path)
    lib = tmp_path / "lib.sh"
    if library == "empty":
        lib.write_text("")   # a truncated copy runs as a silent no-op: it is no library
    res = wrap({**env, "MERGER_HEARTBEAT_LIB": str(lib)})
    assert res.returncode == 0 and "no heartbeat library" in res.stderr and (tmp_path / "code").read_text() == "v1 --code-sha\n"
    assert not (tmp_path / ".organism").exists()


def test_an_older_merger_on_main_is_ticked_without_the_flag_it_does_not_know(tmp_path):
    src, origin, fake_py, env = mirror_world(tmp_path)
    commit(src, {"scripts/localci/merger.py": "old merger\n"}, "older")
    g(src, "push", "-q", str(origin), "main")
    res = wrap(env)
    assert res.returncode == 0 and not any(a.startswith("--code-sha") for a in (tmp_path / "args").read_text().split())


def test_the_heartbeat_library_runs_in_its_own_process_and_cannot_end_the_tick(tmp_path):
    _, _, fake_py, env = mirror_world(tmp_path)
    hostile = tmp_path / "hostile.sh"
    hostile.write_text("set +eu\nexit 0\n")
    fake_py.write_text("#!/bin/sh\nexit 1\n")
    res = wrap({**env, "MERGER_HEARTBEAT_LIB": str(hostile)})
    assert res.returncode == 1   # sourced, its `exit 0` would have ended the wrapper green before the tick ran


def test_a_python_that_is_not_executable_stops_before_any_git(tmp_path):
    _, _, _, env = mirror_world(tmp_path)
    res = wrap({**env, "MERGER_PYTHON": str(tmp_path / "no-venv" / "bin" / "python"), "MERGER_HEARTBEAT_LIB": str(HB_LIB)})
    assert res.returncode == 2 and "not an executable interpreter" in res.stderr and not (tmp_path / "state").exists()
    assert heartbeat(tmp_path)["status"] == "error"


def test_every_journal_line_carries_the_code_sha_it_ran(world, monkeypatch):
    world.gh.prs = [pr(1, world.head1)]
    code = "c" * 40
    assert mg.main(["tick", "--node", mg.HOST, "--repo", REPO, "--state-dir", str(world.state), "--remote-url", str(world.origin),
                    "--python", "py", "--code-sha", code]) == 0
    assert [r.get("code_sha") for r in world.journal()] == [code]
    assert mg.main(["tick", "--node", "elsewhere", "--repo", REPO, "--state-dir", str(world.state), "--code-sha", code]) == 0
    assert world.journal()[-1]["code_sha"] == code and world.journal()[-1]["why"] == "node"
    assert mg.main(["tick", "--node", "elsewhere", "--repo", REPO, "--state-dir", str(world.state)]) == 0
    assert "code_sha" not in world.journal()[-1]   # a run without the flag stamps nothing, whatever the last run in this process did
    for bad in ("main", code + "\n", code.upper()):
        assert mg.main(["tick", "--node", mg.HOST, "--repo", REPO, "--state-dir", str(world.state), "--code-sha", bad]) == 2



@pytest.mark.parametrize("source,given", [('p.add_argument("--pr-number", type=int)\n', True),
                                          ("p.add_argument('--pr-number', type=int)\n", True),
                                          ('# "--pr-number" is planned for later\nHELP = "--pr-number"\n', False),
                                          ('p.add_argument("--pr", type=int)\n', False),
                                          ('p.error("--pr-number")\n', False),
                                          ('p.add_argument("--pr-number"\n', False),
                                          (b'p.add_argument("--pr-number")  # \xff\n', False)])
def test_the_pr_number_is_given_only_to_a_base_runner_that_declares_it(world, source, given):
    runner = world.src / "scripts" / "localci" / "runner.py"
    runner.parent.mkdir(parents=True, exist_ok=True)
    runner.write_bytes(source if isinstance(source, bytes) else source.encode())   # bytes: a source that is not UTF-8
    world.base = commit(world.src, {}, "runner as it stands at the base")
    g(world.src, "push", "-q", str(world.origin), "main")
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0
    plan = world.runner.calls[0]["argv"]
    assert plan[plan.index("--base") + 1] == world.base
    assert (plan[plan.index("--pr-number") + 1] == "1") if given else ("--pr-number" not in plan)


def test_gh_graphql_passes_strings_raw_and_integers_typed_and_returns_the_data(monkeypatch):
    seen = []

    def fake_run(argv, **kw):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, '{"data": {"ok": 1}}', "")
    monkeypatch.setattr(mg.subprocess, "run", fake_run)
    assert mg.gh_graphql("Q", number=7, oid="@/etc/passwd") == {"ok": 1}
    assert seen == [["gh", "api", "graphql", "-f", "query=Q", "-F", "number=7", "-f", "oid=@/etc/passwd"]]


@pytest.mark.parametrize("rc,out,err", [(1, json.dumps({"data": None, "errors": [{"message": "Head moved ghp_" + "C" * 20}]}), "gh: Head moved"),
                                        (0, json.dumps({"data": {"x": 1}, "errors": [{"message": "Head moved ghp_" + "C" * 20}]}), ""),
                                        (1, "", "gh: Head moved ghp_" + "C" * 20), (0, "not json", "Head moved ghp_" + "C" * 20)])
def test_gh_graphql_raises_with_githubs_message_redacted(monkeypatch, rc, out, err):
    monkeypatch.setattr(mg.subprocess, "run", lambda argv, **kw: subprocess.CompletedProcess(argv, rc, out, err))
    with pytest.raises(mg.GraphQLError) as exc:
        mg.gh_graphql("Q")
    assert "Head moved" in str(exc.value) and "ghp_" not in str(exc.value) and "[REDACTED]" in str(exc.value)
