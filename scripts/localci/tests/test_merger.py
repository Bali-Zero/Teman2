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
BODY = "Does a thing.\n\nBites: the launchd tick reads the mirror; observation: the first would_merge line\n"


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
        self.roles = {"maint": "maintain", "boss": "admin"}

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
        m = re.fullmatch(rf"repos/{REPO}/collaborators/([A-Za-z0-9-]+)/permission", path)
        if m:
            return {"role_name": self.roles.get(m[1], "write")}
        raise AssertionError(f"unexpected GitHub read {path}")


class FakeGraphQL:
    """GitHub's GraphQL as the merger may see it: the PR read, built from FakeGH's PRs (``over`` patches it), and the mutation, recorded."""

    def __init__(self, gh):
        self.gh, self.calls, self.over, self.fail = gh, [], {}, None
        self.entry = {"id": "MQE_x", "position": 3, "state": "QUEUED"}

    def __call__(self, query, **variables):
        self.calls.append((query, variables))
        if query == mg.ENQUEUE:
            if self.fail:
                raise mg.GraphQLError(self.fail)
            return {"enqueuePullRequest": {"mergeQueueEntry": self.entry}}
        assert query == mg.PR_QUERY and f"{variables['owner']}/{variables['name']}" == REPO, (query, variables)
        (p,) = [x for x in self.gh.prs if x["number"] == variables["number"]]
        names = [lb["name"] for lb in p["labels"]]
        return {"repository": {"pullRequest": {
            "id": f"PR_node_{p['number']}", "state": "OPEN", "isDraft": p["draft"], "isCrossRepository": False, "baseRefName": "main",
            "headRefOid": p["head"]["sha"], "body": BODY, "isInMergeQueue": False, "mergeQueueEntry": None, "labels": {"nodes": [{"name": n} for n in names]},
            "timelineItems": {"nodes": [labelled(n, "maint") for n in names]}, **self.over}}}

    def mutations(self):
        return [v for q, v in self.calls if q == mg.ENQUEUE]


def labelled(name, login, kind="LabeledEvent", actor="User"):
    return {"__typename": kind, "label": {"name": name}, "actor": {"__typename": actor, "login": login}}


class FakeRunner:
    def __init__(self, overall="BLOCKED", plan_rc=0, run_out=f"policy.change_map: PASS\nseal={SEAL}  # end of run\n", sleep=0, alarm=0,
                 status_rc=0, bind=None, doc=None):
        self.overall, self.plan_rc, self.run_out, self.sleep, self.alarm, self.calls = overall, plan_rc, run_out, sleep, alarm, []
        self.status_rc, self.bind, self.doc = status_rc, bind or {}, doc or {}

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
        first = [c for c in self.calls if c["sub"] == "plan"][-1]   # the decision in progress: a tick may run several in a test
        plan = first["argv"]
        bind = {"candidate_sha": first.get("worktree_head"), "base_sha": plan[plan.index("--base") + 1], "seal": SEAL, **self.bind}
        (run_dir / "status.json").write_text(json.dumps({"overall": self.overall, **bind,
                                                         "contexts": {"status": "ok", "results": {"ctx-a": {"verdict": "OK", "mapping": "executed"}}},
                                                         "checks": {"policy.change_map": {"status": "PASS", "duration_s": 12.5}}, **self.doc}))
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
    gql = FakeGraphQL(gh)
    monkeypatch.setattr(mg.hc, "gh_get", gh)
    monkeypatch.setattr(mg, "gh_graphql", gql)
    monkeypatch.setattr(mg, "runner_exec", runner)
    monkeypatch.delenv(mg.ARM_ENV, raising=False)
    w = type("World", (), {})()
    w.state, w.origin, w.gh, w.gql, w.runner = tmp_path / "state", origin, gh, gql, runner
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
    assert [r["kind"] for r in world.journal()] == ["lease_reclaimed", "decision", "would_enqueue", "would_merge"]


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
    assert kinds == ["lease_reclaimed", "decision", "would_enqueue", "would_merge"] and world.journal()[0]["stale"]["lease_id"] == "stale"
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


def test_every_github_call_is_a_get_or_the_graphql_read_and_unarmed_no_mutation_is_sent(world, monkeypatch):
    real = subprocess.run

    def guarded(argv, *a, **kw):
        assert argv[0] != "gh", f"a GitHub call bypassed hosted_compare.gh_get and gh_graphql: {argv}"
        return real(argv, *a, **kw)
    monkeypatch.setattr(subprocess, "run", guarded)
    world.gh.prs = [pr(1, world.head1, labels=[mg.ARM_LABEL]), pr(9, "9" * 40, fork=True)]
    assert world.tick() == 0
    assert world.gh.paths and all(not re.search(r"/(merge|labels|comments|reviews)\b", p) for p in world.gh.paths)
    assert [q for q, _ in world.gql.calls] == [mg.PR_QUERY] and world.gql.mutations() == []


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
           "OUT_ARGS": str(tmp_path / "args"), "OUT_CODE": str(tmp_path / "code"),
           "MERGER_MIN_HOST_FREE_GB": "0"}   # B6: the host floor is the test machine's otherwise (its own tests below fake df)
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
    assert [(r["kind"], r.get("code_sha")) for r in world.journal()] == [("decision", code), ("would_enqueue", code), ("would_merge", code)]
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


# ------------------------------------------------------------------ the enqueue path (C3a-2)
HEAD7 = "7" * 40
GOOD = {"overall": "BLOCKED",
        "checks": {"ctx.a": {"status": "PASS"}, "tests.frontend_mouth": {"status": "BLOCKED"}, "security.pysa_python": {"status": "NOT_APPLICABLE"},
                   "review.independent": {"status": "QUEUED"}},
        "contexts": {"status": "ok", "required": ["ctx-a", "CodeQL"],
                     "results": {"ctx-a": {"mapping": "executed", "verdict": "OK", "coverage": "full"},
                                 "CodeQL": {"mapping": "blocked", "verdict": "BLOCKED", "coverage": "full"}}}}


def live_doc(**conclusions):
    by = {"ctx-a": "success", "CodeQL": "success", **conclusions}
    return {"required_checks": [{"context": c, "app_id": None} for c in ("ctx-a", "CodeQL")], "statuses": [],
            "check_runs": [{"name": c, "status": "completed" if v else "in_progress", "conclusion": v, "app": {"id": 15368}}
                           for c, v in by.items() if v != "missing"]}


@pytest.fixture
def enq(tmp_path, monkeypatch):
    """Everything holds and both halves are armed: each guilt below breaks exactly one sub-criterion."""
    gh = FakeGH()
    gh.prs = [pr(7, HEAD7, armed=False, labels=[mg.ARM_LABEL])]
    gql = FakeGraphQL(gh)
    monkeypatch.setattr(mg.hc, "gh_get", gh)
    monkeypatch.setattr(mg, "gh_graphql", gql)
    monkeypatch.setenv(mg.ARM_ENV, "1")
    w = type("Enq", (), {})()
    w.gh, w.gql, w.state, w.status, w.live = gh, gql, tmp_path, json.loads(json.dumps(GOOD)), live_doc()
    a = type("A", (), {"repo": REPO, "base": "main"})()
    rec = {"repo": REPO, "pr": 7, "head_sha": HEAD7, "base_sha": "b" * 40, "candidate_sha": "c" * 40, "lease_id": "L"}
    w.run = lambda: mg.enqueue_step(a, tmp_path, rec, mg.local_side(w.status), w.live)
    return w


def _check(name, status):
    return lambda w: w.status["checks"][name].update(status=status)


def _result(name, **kw):
    return lambda w: w.status["contexts"]["results"][name].update(**kw)


def _hosted(**conclusions):
    return lambda w: setattr(w, "live", live_doc(**conclusions))


def _pr(**over):
    return lambda w: w.gql.over.update(over)


def _timeline(*events):
    return _pr(timelineItems={"nodes": list(events)})


GUILT = {
    "local_checks_clean": [_check("ctx.a", "FAIL"), _check("ctx.a", "ERROR"), _check("ctx.a", "STALE"),
                           _check("tests.frontend_mouth", "INTERRUPTED"), _check("ctx.a", "RUNNING"), _check("ctx.a", None),
                           _check("security.pysa_python", "QUEUED")],   # only the review may wait
    "review_independent": [_check("review.independent", "BLOCKED"), _check("review.independent", "FAIL"), _check("review.independent", "STALE")],
    "executed_contexts_ok": [_result("ctx-a", verdict="FAIL"), _result("ctx-a", verdict="BLOCKED"),    # BLOCKED only when NOT executed
                             _result("CodeQL", mapping="executed"), _result("ctx-a", verdict="UNCOVERED"),
                             lambda w: w.status["contexts"]["results"].pop("ctx-a"), lambda w: w.status["contexts"].update(status="invalid")],
    "hosted_required_green": [_hosted(**{"ctx-a": c}) for c in ("failure", "cancelled", "timed_out", "action_required", None, "missing")]
                             + [lambda w: setattr(w, "live", None)],
    "head_unchanged": [_pr(headRefOid="8" * 40)],
    "same_repo": [_pr(isCrossRepository=True)],
    "not_draft": [_pr(isDraft=True)],
    "base_main": [_pr(baseRefName="release")],
    "open": [_pr(state="CLOSED"), _pr(state="MERGED")],
    "not_in_queue": [_pr(isInMergeQueue=True, mergeQueueEntry={"id": "MQE_old", "position": 1, "state": "QUEUED"}),
                     _pr(mergeQueueEntry={"id": "MQE_old", "position": 1, "state": "QUEUED"})],
    "first_enqueue": [lambda w: mg.journal(w.state, {"kind": "enqueued", "pr": 7, "head_sha": HEAD7})],
    "label_privileged": [lambda w: w.gh.prs[0].update(labels=[]), _timeline(labelled(mg.ARM_LABEL, "dev")),
                         _timeline(labelled(mg.ARM_LABEL, "renovate", actor="Bot")),
                         _timeline(labelled(mg.ARM_LABEL, "maint"), labelled(mg.ARM_LABEL, "maint", kind="UnlabeledEvent"),
                                   labelled(mg.ARM_LABEL, "dev")),   # the account that applied it LAST arms, or not
                         _timeline()],
}
CASES = [pytest.param(name, f, id=f"{name}-{i}") for name, fs in GUILT.items() for i, f in enumerate(fs)]


def test_the_guilt_table_breaks_every_sub_criterion():
    assert tuple(GUILT) == mg.CRITERION


@pytest.mark.parametrize("name,guilt", CASES)
def test_each_sub_criterion_alone_refuses_the_enqueue_and_the_line_names_it(enq, name, guilt):
    guilt(enq)
    line = enq.run()
    assert line["refused"] == [name] and line["criterion"] == {k: k != name for k in mg.CRITERION} and line["ok"] is False
    assert isinstance(line["why"][name], str) and list(line["why"]) == [name]
    assert line["kind"] == ("would_enqueue" if name == "label_privileged" else "enqueue_refused") and enq.gql.mutations() == []
    assert mg.read_journal(enq.state)[-1] == line


@pytest.mark.parametrize("tweak", [None, _hosted(CodeQL="skipped"), _hosted(CodeQL="neutral"), _timeline(labelled(mg.ARM_LABEL, "boss")),
                                   _check("review.independent", "PASS")], ids=["all-hold", "skipped", "neutral", "admin", "review-pass"])
def test_when_every_sub_criterion_holds_and_both_halves_are_armed_one_mutation_enqueues_the_decided_head(enq, capsys, tweak):
    if tweak:
        tweak(enq)
    line = enq.run()
    assert enq.gql.mutations() == [{"pr": "PR_node_7", "oid": HEAD7}]
    assert (line["kind"], line["refused"], line["ok"], line["armed_env"]) == ("enqueued", [], True, True) and all(line["criterion"].values())
    assert (line["entry_id"], line["position"], line["entry_state"], line["expected_head_oid"], line["live_head_oid"]) == ("MQE_x", 3, "QUEUED", HEAD7, HEAD7)
    assert (line["executed_required"], line["non_executed"], line["pull_request_id"]) == ("1/2", {"CodeQL": "blocked"}, "PR_node_7")
    assert {"ts", "host", "pr", "head_sha", "base_sha", "candidate_sha", "lease_id", "why", "label_actor"} <= set(line) and line["why"] == {}
    out = capsys.readouterr().out
    assert "#7 enqueued" in out and "executed_required=1/2" in out and "CodeQL (blocked)" in out and "entry=MQE_x position=3" in out


@pytest.mark.parametrize("value", [None, "0", "true", "yes", " 1"])
def test_without_the_env_flag_the_merger_stays_shadow_and_journals_the_same_criterion(enq, monkeypatch, value):
    if value is None:
        monkeypatch.delenv(mg.ARM_ENV)
    else:
        monkeypatch.setenv(mg.ARM_ENV, value)
    line = enq.run()
    assert (line["kind"], line["refused"], line["ok"], line["armed_env"]) == ("would_enqueue", ["armed_env"], True, False)
    assert all(line["criterion"].values()) and line["expected_head_oid"] == HEAD7 and enq.gql.mutations() == []


def test_an_unreadable_pull_request_refuses_every_sub_criterion_it_holds_with_the_read_error(enq, monkeypatch):
    def down(query, **variables):
        raise mg.GraphQLError(mg.redact("gh api graphql rc=1: Something went wrong ghp_" + "A" * 24))
    monkeypatch.setattr(mg, "gh_graphql", down)
    line = enq.run()
    pr_side = ["head_unchanged", "same_repo", "not_draft", "base_main", "open", "not_in_queue", "first_enqueue", "label_privileged"]
    assert line["kind"] == "would_enqueue" and line["refused"] == pr_side and not any(line["criterion"][k] for k in pr_side)
    assert all("Something went wrong" in line["why"][k] and "ghp_" not in line["why"][k] for k in pr_side)


@pytest.mark.parametrize("fail,entry", [("gh api graphql rc=1: Pull request is in an unmergeable state; token ghp_" + "B" * 24, None),
                                        (None, None), (None, {"position": 1})])
def test_a_failed_mutation_is_journalled_redacted_and_sent_once(enq, fail, entry):
    enq.gql.fail, enq.gql.entry = fail, entry
    line = enq.run()
    assert line["kind"] == "enqueue_error" and len(enq.gql.mutations()) == 1 and "entry_id" not in line
    assert ("unmergeable" in line["error"] if fail else "no merge queue entry" in line["error"]) and "ghp_" not in line["error"]


def test_a_tick_journals_would_enqueue_after_its_decision_and_names_the_non_executed_contexts(world, capsys):
    world.runner.doc = {k: GOOD[k] for k in ("checks", "contexts")}
    world.gh.prs = [pr(1, world.head1, armed=False, labels=[mg.ARM_LABEL])]   # the arm label alone puts the PR in front of the merger
    assert world.tick() == 0
    d, w, _ = world.journal()
    assert (d["kind"], d["executed_required"], d["non_executed"]) == ("decision", "1/2", {"CodeQL": "blocked"})
    assert (w["kind"], w["refused"], w["expected_head_oid"], w["candidate_sha"], w["base_sha"]) == ("would_enqueue", ["armed_env"], world.head1,
                                                                                                    d["candidate_sha"], world.base)
    assert all(w["criterion"].values()) and w["lease_id"] == d["lease_id"] and world.gql.mutations() == []
    assert "would_enqueue" in capsys.readouterr().out


def test_an_armed_tick_enqueues_the_decided_head_once_and_a_decision_without_a_verdict_never_enqueues(world, monkeypatch):
    monkeypatch.setenv(mg.ARM_ENV, "1")
    world.runner.doc = {k: GOOD[k] for k in ("checks", "contexts")}
    world.gh.prs = [pr(1, world.head1, labels=[mg.ARM_LABEL]), pr(2, world.head2, labels=[mg.ARM_LABEL])]
    assert world.tick() == 0 and world.tick() == 0   # #1 decided and enqueued; #2 conflicts with main: no verdict, no criterion
    assert [(r["kind"], r["pr"]) for r in world.journal()] == [("decision", 1), ("enqueued", 1), ("would_merge", 1), ("decision", 2)]
    assert world.gql.mutations() == [{"pr": "PR_node_1", "oid": world.head1}]


def test_a_gate_error_vouches_for_nothing_and_never_enqueues(world, monkeypatch):
    monkeypatch.setenv(mg.ARM_ENV, "1")
    monkeypatch.setattr(mg, "runner_exec", FakeRunner(bind={"seal": "cd" * 32}, doc={k: GOOD[k] for k in ("checks", "contexts")}))
    world.gh.prs = [pr(1, world.head1, labels=[mg.ARM_LABEL])]
    assert world.tick() == 0
    d, line, _ = world.journal()
    assert d["error"] and line["kind"] == "enqueue_refused" and {"local_checks_clean", "review_independent", "executed_contexts_ok"} <= set(line["refused"])
    assert world.gql.mutations() == []


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


# ------------------------------------------------------------------ coverage on the decision line (B3)
@pytest.mark.parametrize("coverage,named", [("partial", "1/2 (partial: ctx-a)"), (None, "1/2 (coverage unrecorded: ctx-a)"),
                                            ("whatever", "1/2 (coverage unrecorded: ctx-a)"), ("full", "1/2")])
def test_a_partial_context_is_executed_and_passes_but_the_decision_line_names_it(enq, capsys, coverage, named):
    _result("ctx-a", coverage=coverage)(enq)
    line = enq.run()
    assert line["kind"] == "enqueued" and all(line["criterion"].values()) and line["executed_required"] == named
    assert line["partial"] == ({} if coverage == "full" else {"ctx-a": "partial" if coverage == "partial" else "unrecorded"})
    assert f"executed_required={named} " in capsys.readouterr().out


def test_a_tick_journals_each_contexts_coverage_beside_its_verdict(world):
    doc = json.loads(json.dumps({k: GOOD[k] for k in ("checks", "contexts")}))
    doc["contexts"]["results"]["ctx-a"].update(coverage="partial", coverage_note="secrets empty")
    world.runner.doc = doc
    world.gh.prs = [pr(1, world.head1, armed=False, labels=[mg.ARM_LABEL])]
    assert world.tick() == 0
    d, w, _ = world.journal()
    assert d["contexts"] == {"ctx-a": "OK", "CodeQL": "BLOCKED"} and d["coverage"] == {"ctx-a": "partial", "CodeQL": "full"}
    assert d["executed_required"] == w["executed_required"] == "1/2 (partial: ctx-a)" and d["partial"] == w["partial"] == {"ctx-a": "partial"}


# ------------------------------------------------------------------ a host out of disk: not executed, not a FAIL, never enqueued (B3)
@pytest.mark.parametrize("verdict,code", [("ERROR", "host_disk_full"), ("BLOCKED", "host_disk_below_floor 9.8GB<12GB"),
                                          ("BLOCKED", "host_disk_unmeasured"), ("BLOCKED", "host_disk_floor_invalid")])
def test_a_context_the_host_could_not_judge_is_not_executed_named_and_still_refuses(enq, capsys, verdict, code):
    _result("ctx-a", verdict=verdict, no_verdict=code)(enq)
    line = enq.run()
    assert line["refused"] == ["executed_contexts_ok"] and line["kind"] == "enqueue_refused" and enq.gql.mutations() == []
    assert line["executed_required"] == "0/2" and line["host_no_verdict"] == {"ctx-a": code} and "not executed" in line["why"]["executed_contexts_ok"]
    assert "not OK" not in line["why"]["executed_contexts_ok"] and f"host_no_verdict=['ctx-a ({code})']" in capsys.readouterr().out


def test_a_fail_that_carries_a_host_code_is_still_a_fail_on_the_line(enq):
    _result("ctx-a", verdict="FAIL", no_verdict="host_disk_full")(enq)
    line = enq.run()
    assert line["executed_required"] == "1/2" and line["host_no_verdict"] == {} and "not OK" in line["why"]["executed_contexts_ok"]


def test_the_runner_gets_the_operators_free_space_floor_and_still_no_token(world, monkeypatch):
    monkeypatch.setenv("LOCALCI_MIN_FREE_GB", "30")
    monkeypatch.setenv("GH_TOKEN", "ghp_" + "Z" * 24)
    world.gh.prs = [pr(1, world.head1)]
    assert world.tick() == 0
    env = world.runner.calls[0]["env"]
    assert env["LOCALCI_MIN_FREE_GB"] == "30" and "GH_TOKEN" not in env and all("ghp_" not in v for v in env.values())


def test_a_tick_journals_a_change_map_skip_beside_its_verdict_and_only_there(world):   # B5: the report compares it as a skip
    doc = json.loads(json.dumps({k: GOOD[k] for k in ("checks", "contexts")}))
    doc["contexts"]["results"]["ctx-a"]["skipped"] = "change_map"
    world.runner.doc = doc
    world.gh.prs = [pr(1, world.head1, armed=False, labels=[mg.ARM_LABEL])]
    assert world.tick() == 0
    d, *_ = world.journal()
    assert d["contexts"]["ctx-a"] == "OK" and d["skipped"] == {"ctx-a": "change_map"}


# ------------------------------------------------------------------ B6-3: the tick prunes at its end, never starts a run under the floor
def floor_world(tmp_path, free_gb, merger="v1 --code-sha --host-free-gb \"prune\"\n", prune=True):
    src, origin, fake_py, env = mirror_world(tmp_path)
    commit(src, {"scripts/localci/merger.py": merger, **({"scripts/localci/prune.py": "p\n", "scripts/localci/runner.py": "r\n"} if prune else {})}, "b6")
    g(src, "push", "-q", str(origin), "main")
    fake_py.write_text('#!/bin/sh\necho "$3 $*" >> "$OUT_CALLS"\ncase "$3" in tick) exit "${FAKE_TICK_RC:-0}";; prune) exit "${FAKE_PRUNE_RC:-0}";; esac\n')
    bin_ = tmp_path / "fakebin"
    bin_.mkdir()
    (bin_ / "df").write_text(f'#!/bin/sh\necho "Filesystem 1024-blocks Used Available Capacity Mounted on"\n'
                             f'echo "/dev/disk3s5 482797652 300000000 {-(-int(free_gb * 1e9) // 1024)} 60% /System/Volumes/Data"\n')
    (bin_ / "df").chmod(0o755)
    env = {**env, "PATH": f"{bin_}:{env['PATH']}", "OUT_CALLS": str(tmp_path / "calls"), "MERGER_HOST_PATH": str(tmp_path)}
    env.pop("MERGER_MIN_HOST_FREE_GB")
    return env


def calls_of(tmp_path):
    return [ln.split()[0] for ln in (tmp_path / "calls").read_text().splitlines()] if (tmp_path / "calls").exists() else []


def test_the_tick_decides_first_then_prunes_with_fstrim_and_passes_the_host_reading(tmp_path):
    env = floor_world(tmp_path, 200)
    res = wrap(env)
    assert res.returncode == 0, res.stderr
    lines = (tmp_path / "calls").read_text().splitlines()
    assert calls_of(tmp_path) == ["tick", "prune"]   # never the prune before the decision
    assert lines[0].endswith("--host-free-gb=200 --min-host-free-gb=60")
    assert re.search(rf"prune --state-dir {re.escape(env['MERGER_STATE_DIR'])} --fstrim --code-sha=[0-9a-f]{{40}}$", lines[1])
    assert heartbeat(tmp_path)["status"] == "ok" and "host_free_gb=200" in res.stdout


@pytest.mark.parametrize("free,status", [(59, "warning"), (60, "ok")])
def test_under_the_floor_the_tick_journals_its_skip_the_prune_still_runs_and_the_organ_says_warning(tmp_path, free, status):
    env = floor_world(tmp_path, free)
    assert wrap(env).returncode == 0
    assert calls_of(tmp_path) == ["tick", "prune"] and f"--host-free-gb={free} " in (tmp_path / "calls").read_text()
    hb = heartbeat(tmp_path)
    assert hb["status"] == status and (status == "ok" or hb["note"].startswith("host_below_floor free_gb=59 floor_gb=60: no run started"))


def test_a_merger_that_cannot_journal_the_floor_is_not_started_under_it_and_a_main_without_prune_still_ticks(tmp_path):
    env = floor_world(tmp_path, 10, merger="v1 --code-sha (a main before B6)\n", prune=False)
    res = wrap(env)
    assert res.returncode == 0 and calls_of(tmp_path) == [] and "cannot journal the skip" in res.stderr
    assert heartbeat(tmp_path)["status"] == "warning"
    (tmp_path / "w2").mkdir()
    env = floor_world(tmp_path / "w2", 200, merger="v1 --code-sha (a main before B6)\n", prune=False)
    assert wrap(env).returncode == 0 and calls_of(tmp_path / "w2") == ["tick"] and heartbeat(tmp_path / "w2")["status"] == "ok"


def test_an_unreadable_host_reading_starts_no_run_and_the_organ_says_warning(tmp_path):
    env = floor_world(tmp_path, 200)
    (tmp_path / "fakebin" / "df").write_text("#!/bin/sh\nexit 1\n")
    res = wrap(env)
    assert res.returncode == 0 and calls_of(tmp_path) == ["prune"] and "host_free_gb=unread" in res.stdout
    assert heartbeat(tmp_path)["status"] == "warning" and heartbeat(tmp_path)["note"].startswith("host free space unreadable")


def test_a_failed_prune_is_a_warning_and_a_failed_tick_is_an_error_after_which_the_prune_still_runs(tmp_path):
    env = floor_world(tmp_path, 200)
    assert wrap({**env, "FAKE_PRUNE_RC": "1"}).returncode == 0
    assert heartbeat(tmp_path)["status"] == "warning" and heartbeat(tmp_path)["note"].startswith("prune rc=1")
    res = wrap({**env, "FAKE_TICK_RC": "1"})
    assert res.returncode == 1 and heartbeat(tmp_path)["status"] == "error" and calls_of(tmp_path)[-2:] == ["tick", "prune"]


def test_the_tick_refuses_to_start_a_run_under_the_floor_and_journals_why(world):
    world.gh.prs = [pr(1, world.head1)]
    args = ["tick", "--node", mg.HOST, "--repo", REPO, "--state-dir", str(world.state), "--remote-url", str(world.origin), "--python", "py"]
    assert mg.main([*args, "--host-free-gb", "59.4"]) == 0
    assert world.journal()[-1] == {**world.journal()[-1], "kind": "skipped", "why": "host_below_floor", "free_gb": 59.4, "floor_gb": 60.0}
    assert not [r for r in world.journal() if r["kind"] == "decision"]
    assert mg.main([*args, "--host-free-gb", "60"]) == 0 and [r["kind"] for r in world.journal()][-3:] == ["decision", "would_enqueue", "would_merge"]


# ------------------------------------------------------------------ phase F, shadow: the merge rehearsed, never made (F1)
class Mirror:
    """A bare mirror as the tick leaves it: ``refs/merger/base`` = main, ``refs/merger/pr/7`` = the head under rehearsal."""

    def __init__(self, tmp_path):
        self.src, self.repo, self.state = tmp_path / "msrc", tmp_path / "mirror.git", tmp_path / "mstate"
        self.state.mkdir()
        self.src.mkdir()
        g(self.src, "init", "-q", "-b", "main")
        self.base0 = commit(self.src, {"a.txt": "a\n", "d.txt": "d\n"}, "base")
        g(self.src, "checkout", "-q", "-b", "clean")
        self.clean = commit(self.src, {"b.txt": "b\n"}, "adds b")
        g(self.src, "checkout", "-q", "-b", "clash", self.base0)
        self.clash = commit(self.src, {"a.txt": "clash\n"}, "edits a")
        g(self.src, "checkout", "-q", "main")
        self.base = commit(self.src, {"a.txt": "main\n"}, "main moves")
        subprocess.run(["git", "clone", "-q", "--bare", str(self.src), str(self.repo)], check=True, env=GIT_ENV)
        g(self.repo, "update-ref", "refs/merger/base", self.base)
        for name, sha in (("clean", self.clean), ("clash", self.clash)):
            g(self.repo, "update-ref", f"refs/merger/pr/{name}", sha)

    def refs(self) -> str:
        return g(self.repo, "for-each-ref", "--format=%(refname) %(objectname)")

    def enq(self, head, *, base=None, **crit):
        full = {k: True for k in mg.CRITERION} | crit
        return {"kind": "would_enqueue", "pr": 7, "head_sha": head, "base_sha": base or self.base, "lease_id": "L", "criterion": full,
                "armed_env": True, "bites": True, "ok": all(full.values())}

    def step(self, head, **kw):
        before = self.refs()
        line = mg.merge_shadow_step(self.state, self.repo, self.enq(head, **kw))
        assert self.refs() == before   # the rehearsal writes objects, never a ref: nothing to push either
        assert mg.read_journal(self.state)[-1] == line
        return line


@pytest.fixture
def mirror(tmp_path):
    return Mirror(tmp_path)


def test_a_clean_head_rehearses_to_a_tree_and_the_line_is_ok(mirror, capsys):
    line = mirror.step(mirror.clean)
    assert (line["kind"], line["ok"], line["clean"], line["conflicts"], line["base_current"], line["head_unchanged"]) == ("would_merge", True, True, [], True, True)
    assert mg.is_sha(line["merge_tree"]) and line["mirror_main"] == line["remote_main"] == line["base_sha"] == mirror.base and "error" not in line
    assert g(mirror.repo, "ls-tree", "--name-only", line["merge_tree"]).split() == ["a.txt", "b.txt", "d.txt"]   # main's a.txt plus the head's b.txt
    assert (line["bites"], line["armed_env"], line["lease_id"]) == (True, True, "L") and all(line["criterion"].values())
    assert "would_merge ok=True clean=True" in capsys.readouterr().out


def test_a_head_that_conflicts_with_main_is_not_clean_and_names_the_path(mirror):
    line = mirror.step(mirror.clash)
    assert (line["ok"], line["clean"], line["conflicts"], line["base_current"]) == (False, False, ["a.txt"], True)
    assert mg.is_sha(line["merge_tree"]) and "error" not in line


def test_a_github_main_that_moved_after_the_tick_fetched_is_not_current_though_the_mirror_still_is(mirror):
    g(mirror.src, "checkout", "-q", "main")
    moved = commit(mirror.src, {"e.txt": "e\n"}, "main moves again")   # the mirror is NOT fetched: a gate run outlasted a merge
    line = mirror.step(mirror.clean)
    assert (line["base_current"], line["mirror_main"], line["remote_main"], line["base_sha"]) == (False, mirror.base, moved, mirror.base)
    assert (line["clean"], line["ok"]) == (True, False) and "error" not in line


def test_a_mirror_refetched_after_the_decision_is_rehearsed_on_its_own_main_and_is_not_current(mirror):
    g(mirror.src, "checkout", "-q", "main")
    moved = commit(mirror.src, {"e.txt": "e\n"}, "main moves again")
    g(mirror.repo, "fetch", "-q", str(mirror.src), "+refs/heads/main:refs/merger/base")
    line = mirror.step(mirror.clean)
    assert (line["base_current"], line["mirror_main"], line["remote_main"], line["clean"], line["ok"]) == (False, moved, moved, True, False)
    assert "e.txt" in g(mirror.repo, "ls-tree", "--name-only", line["merge_tree"]).split()   # the rehearsal merges onto the mirror's main as it is NOW


def test_an_unreadable_origin_is_an_error_line_with_no_remote_main_and_never_current(mirror):
    g(mirror.repo, "remote", "set-url", "origin", str(mirror.src / "nowhere"))
    line = mirror.step(mirror.clean)
    assert (line["remote_main"], line["base_current"], line["ok"]) == (None, False, False) and "ls-remote" in line["error"]
    assert mg.is_sha(line["merge_tree"]) and line["clean"] is True   # the rehearsal does not depend on the network


def test_a_slow_origin_times_out_into_an_error_line(mirror, monkeypatch):
    real, seen = mg.git, {}

    def slow(cwd, *args, **kw):
        if args[0] == "ls-remote":
            seen.update(kw)
            raise subprocess.TimeoutExpired(["git", "ls-remote", "ghp_" + "D" * 24], kw["timeout"])
        return real(cwd, *args, **kw)
    monkeypatch.setattr(mg, "git", slow)
    line = mirror.step(mirror.clean)
    assert seen["timeout"] == mg.REMOTE_TIMEOUT_S <= 30 and (line["remote_main"], line["base_current"], line["ok"]) == (None, False, False)
    assert "TimeoutExpired" in line["error"] and "ghp_" not in line["error"]


@pytest.mark.parametrize("name", mg.CRITERION)
def test_a_false_sub_criterion_still_rehearses_the_merge_and_the_line_says_which(mirror, name):
    line = mirror.step(mirror.clean, **{name: False})
    assert (line["ok"], line["clean"], mg.is_sha(line["merge_tree"])) == (False, True, True)
    assert [k for k, v in line["criterion"].items() if not v] == [name]


def test_a_head_the_enqueue_path_saw_move_is_not_ok_even_when_the_merge_is_clean(mirror):
    line = mirror.step(mirror.clean, head_unchanged=False)
    assert (line["head_unchanged"], line["clean"], line["ok"]) == (False, True, False)


@pytest.mark.parametrize("tamper", [None, {}], ids=["no-criterion", "empty-criterion"])
def test_a_line_without_a_criterion_is_never_ok(mirror, tamper):
    enq = {**mirror.enq(mirror.clean), "criterion": tamper}
    assert mg.merge_shadow_step(mirror.state, mirror.repo, enq)["ok"] is False


def test_a_merge_tree_that_raises_is_journalled_redacted_and_not_ok(mirror, monkeypatch):
    real = mg.git

    def boom(cwd, *args, **kw):
        if args[0] == "merge-tree":
            raise OSError("merge-tree ghp_" + "C" * 24)
        return real(cwd, *args, **kw)
    monkeypatch.setattr(mg, "git", boom)
    line = mirror.step(mirror.clean)
    assert (line["ok"], line["merge_tree"], line["clean"]) == (False, None, False) and "OSError" in line["error"] and "ghp_" not in line["error"]


def test_a_head_missing_from_the_mirror_is_an_error_line_not_a_raise(mirror):
    line = mirror.step("9" * 40)
    assert line["ok"] is False and line["merge_tree"] is None and "merge-tree failed" in line["error"]


def test_a_mirror_without_its_base_ref_is_an_error_line_not_a_raise(mirror):
    g(mirror.repo, "update-ref", "-d", "refs/merger/base")
    line = mirror.step(mirror.clean)
    assert line["ok"] is False and line["mirror_main"] is None and "error" in line


def test_the_tick_journals_would_merge_with_a_tree_and_never_moves_a_ref_or_pushes(world, monkeypatch):
    world.gh.prs = [pr(1, world.head1, armed=False, labels=[mg.ARM_LABEL])]
    pushes = []
    real = mg.git
    monkeypatch.setattr(mg, "git", lambda cwd, *a, **kw: pushes.append(a) or real(cwd, *a, **kw))
    assert world.tick() == 0
    w = world.journal()[-1]
    assert w["kind"] == "would_merge" and w["ok"] is False and w["armed_env"] is False   # shadow: the real merge would also wait for the arm
    assert (w["clean"], w["base_current"], w["head_unchanged"], w["mirror_main"], w["bites"]) == (True, True, True, world.base, True)
    assert mg.is_sha(w["merge_tree"]) and w["criterion"]["review_independent"] is False and BODY not in json.dumps(w)
    assert not [a for a in pushes if a[0] in ("push", "update-ref", "branch", "tag")]   # nothing pushed, no ref written by the rehearsal
    refs = g(world.state / "repo.git", "for-each-ref", "--format=%(refname)").split()
    assert not [r for r in refs if not r.startswith(("refs/merger/", "refs/heads/", "refs/remotes/", "refs/pull/"))]


def test_a_merge_tree_failure_inside_a_tick_leaves_the_decision_and_its_exit_code_alone(world, monkeypatch):
    world.gh.prs = [pr(1, world.head1, armed=False, labels=[mg.ARM_LABEL])]
    real = mg.git
    monkeypatch.setattr(mg, "git", lambda cwd, *a, **kw: (_ for _ in ()).throw(OSError("no git")) if a[0] == "merge-tree" else real(cwd, *a, **kw))
    assert world.tick() == 0
    kinds = [r["kind"] for r in world.journal()]
    assert kinds == ["decision", "would_enqueue", "would_merge"] and "no git" in world.journal()[-1]["error"] and world.journal()[0]["overall"] == "BLOCKED"


@pytest.mark.parametrize("body,expected", [("Bites: x", True), ("text\n**Bites:** y", True), ("> bites : z", True), ("- Bites: w", True),
                                           ("no such line", False), ("Bitesize: x", False), ("a Bites: mid-line", False), ("", False), (None, False)])
def test_bites_is_a_flag_read_from_the_pr_body_line(enq, body, expected):
    enq.gql.over["body"] = body
    line = enq.run()
    assert line["bites"] is expected and "body" not in line


def test_a_journal_that_cannot_write_the_shadow_line_leaves_one_decision_and_rc_zero(world, monkeypatch, capsys):
    world.gh.prs = [pr(1, world.head1, armed=False, labels=[mg.ARM_LABEL])]
    real = mg.journal

    def full_disk(state, rec):
        if rec.get("kind") == "would_merge":
            raise OSError("No space left on device")
        return real(state, rec)
    monkeypatch.setattr(mg, "journal", full_disk)
    assert world.tick() == 0
    assert [r["kind"] for r in world.journal()] == ["decision", "would_enqueue"]   # no second, ERROR decision
    assert "would_merge not journalled" in capsys.readouterr().err


def test_a_github_main_that_moves_after_the_tick_fetch_makes_the_tick_line_not_current(world, monkeypatch):
    world.gh.prs = [pr(1, world.head1, armed=False, labels=[mg.ARM_LABEL])]
    moved = {}
    real = mg.run_gate

    def gate_then_main_moves(*a, **kw):
        res = real(*a, **kw)
        g(world.src, "checkout", "-q", "main")
        moved["sha"] = commit(world.src, {"z.txt": "z\n"}, "main moves during the gate")
        g(world.origin, "fetch", "-q", str(world.src), "+refs/heads/main:refs/heads/main")
        return res
    monkeypatch.setattr(mg, "run_gate", gate_then_main_moves)
    assert world.tick() == 0
    w = world.journal()[-1]
    assert (w["kind"], w["base_current"], w["mirror_main"], w["remote_main"], w["ok"]) == ("would_merge", False, world.base, moved["sha"], False)


def test_the_tick_hands_the_stale_judge_the_mirror_and_the_decided_base(world, monkeypatch):
    world.gh.prs = [pr(1, world.head1, armed=False, labels=[mg.ARM_LABEL])]
    seen = []
    real = mg.hosted_summary
    monkeypatch.setattr(mg, "hosted_summary", lambda *a, **kw: seen.append((a, kw)) or real(*a, **kw))
    assert world.tick() == 0
    ((args, kw),) = seen
    judge = kw.get("judge") if "judge" in kw else args[5]
    assert isinstance(judge, mg.StaleJudge) and judge.base == world.base and judge.repo == world.state / "repo.git"


def test_the_tick_hands_the_gate_judge_the_stale_judges_matrix_and_the_runs_own_plan_time(world, monkeypatch):
    world.gh.prs = [pr(1, world.head1, armed=False, labels=[mg.ARM_LABEL])]
    seen, asked = [], []
    real = mg.hosted_summary
    monkeypatch.setattr(mg, "hosted_summary", lambda *a, **kw: seen.append((a, kw)) or real(*a, **kw))
    monkeypatch.setattr(mg, "plan_time", lambda run_dir: asked.append(Path(run_dir)) or "2026-10-10T01:20:00Z")   # unit-tested in test_gate_stale
    assert world.tick() == 0
    ((args, kw),) = seen
    gate = kw.get("gate")
    assert isinstance(gate, mg.GateJudge) and gate.matrix is args[5] and gate.repo == REPO
    assert asked == [Path(args[4])] and gate.plan_at == "2026-10-10T01:20:00Z"   # the plan of THIS decision's run dir
