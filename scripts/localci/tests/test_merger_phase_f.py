"""F2 guilt + innocence: the phase F executor is disarmed by construction. Real git repos under tmp, a local bare repo as GitHub's origin,
GitHub's API faked, no network. Every arming condition is broken ALONE with all the others true; the armed path is proven end to end."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess

import pytest

from .test_merger import GIT_ENV, REPO, FakeRunner, g, commit, mg, mirror_world, pr, world, wrap  # noqa: F401 — `world` is a fixture

CTX = tuple(f"ctx-{i:02d}" for i in range(mg.MIN_COMPARED_CONTEXTS))
M, OLD_BASE = "1" * 40, "f" * 40
SENTINEL = "SENTINEL-KEY-MATERIAL-9d41c7e0"
DOC = {"checks": {"policy.change_map": {"status": "PASS", "duration_s": 1}, "review.independent": {"status": "QUEUED"}},
       "contexts": {"status": "ok", "required": ["ctx-a"], "results": {"ctx-a": {"mapping": "executed", "verdict": "OK", "coverage": "full"}}}}
STAMP = "2026-10-%02dT00:00:00Z"


class Hub:
    """GitHub for the tick AND for the report it runs: the world's reads, plus merged PRs 1001.. and a required list the history can meet."""

    def __init__(self, gh, head1):
        self.gh, self.head1, self.pulls = gh, head1, {}
        self.required = (*CTX, "ctx-a")

    def __call__(self, path):
        if path == f"repos/{REPO}/branches/main/protection/required_status_checks":
            return {"checks": [{"context": c, "app_id": 15368} for c in self.required]}
        if (m := re.fullmatch(rf"repos/{REPO}/pulls/(\d+)", path)):
            n = int(m[1])
            return self.pulls.get(n) or {"merged": False, "state": "open", "head": {"sha": self.head1}, "merge_commit_sha": None, "merged_at": None}
        if (m := re.fullmatch(rf"repos/{REPO}/commits/([0-9a-f]{{40}})", path)):
            return {"parents": [{"sha": OLD_BASE}]}
        if (m := re.fullmatch(rf"repos/{REPO}/commits/([0-9a-f]{{40}})/check-runs\?per_page=100&page=1", path)):
            return {"check_runs": [{"name": c, "status": "completed", "conclusion": "success", "head_sha": m[1], "app": {"id": 15368, "slug": "github-actions"},
                                    "completed_at": None} for c in self.required]}
        return self.gh(path)

    def seed(self, state, n=50, days=14, age=20):
        """n merged, compared PRs spanning `days`: exactly phase D's threshold."""
        state.mkdir(parents=True, exist_ok=True)
        lines = []
        for i in range(n):
            head, at = f"{i + 1:040x}", time_at(i * days * 86400 // (n - 1), age)
            self.pulls[1001 + i] = {"merged": True, "state": "closed", "head": {"sha": head}, "merge_commit_sha": M, "merged_at": at}
            lines.append({"kind": "decision", "ts": at, "pr": 1001 + i, "head_sha": head, "base_sha": OLD_BASE, "candidate_sha": "9" * 40, "overall": "BLOCKED",
                          "contexts_status": "ok", "contexts": dict.fromkeys(CTX, "OK"), "coverage": dict.fromkeys(CTX, "full")})
        (state / "decisions.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in lines))


def time_at(offset_s: int, age_days: int = 20) -> str:
    """Seeded history starts `age_days` before the real clock: the tick's precheck reads now."""
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(time.time()) - age_days * 86400 + offset_s))


@pytest.fixture
def fw(world, monkeypatch):  # noqa: F811
    """The world with every arming condition true: env, READY (a seeded journal the real report reads), the key, the criterion, a current base."""
    world.hub = Hub(world.gh, world.head1)
    monkeypatch.setattr(mg.hc, "gh_get", world.hub)
    world.runner = FakeRunner(doc=DOC)
    monkeypatch.setattr(mg, "runner_exec", world.runner)
    world.gh.prs = [pr(1, world.head1, armed=False, labels=[mg.ARM_LABEL])]
    world.gql.over["title"] = "Add b to the tree"
    world.hub.seed(world.state)
    world.key = world.state / mg.KEY_FILE
    world.key.write_text(f"-----BEGIN FAKE KEY-----\n{SENTINEL}\n-----END FAKE KEY-----\n")
    world.key.chmod(0o600)
    monkeypatch.setenv(mg.PHASE_F_ENV, "1")
    world.mirror = world.state / "repo.git"
    world.live = lambda: [r for r in world.journal() if not (r.get("pr") or 0) >= 1001]   # the seeded history is not the tick's
    world.kinds = lambda: [r["kind"] for r in world.live()]
    world.origin_main = lambda: g(world.origin, "rev-parse", "refs/heads/main")
    world.wm = lambda: [r for r in world.journal() if r["kind"] == "would_merge"][-1]
    world.pushes = []
    real = mg.git

    def spy(cwd, *a, **kw):
        if a and a[0] == "push":
            world.pushes.append((a, dict(kw.get("env") or {})))
        return real(cwd, *a, **kw)
    monkeypatch.setattr(mg, "git", spy)
    return world


def SSH_COMMAND(w):
    """The one ssh the push may run: no user config, no agent, the deploy key alone, and only the host key pinned in the state dir."""
    return (f"ssh -F /dev/null -o IdentityAgent=none -i {w.key} -o IdentitiesOnly=yes -o BatchMode=yes -o GlobalKnownHostsFile=/dev/null "
            f"-o UserKnownHostsFile={w.state / mg.KNOWN_HOSTS_FILE} -o StrictHostKeyChecking=yes")


def full_pull(w, **over):
    """The PR as the moment-of-merging re-read sees it when nothing is wrong."""
    return {"headRefOid": w.head1, "state": "OPEN", "isInMergeQueue": False, "isDraft": False, "baseRefName": "main",
            "labels": {"nodes": [{"name": mg.ARM_LABEL}]}, **over}


def assert_nothing_merged(w, why_part=None):
    assert w.pushes == [] and not {"merged", "pushed", "push_refused"} & set(w.kinds())
    assert "localci-merger" not in g(w.origin, "log", "--format=%an|%cn", "refs/heads/main") and g(w.mirror, "rev-parse", "refs/merger/base") == w.base
    line = w.wm()
    assert line["phase_f"]["armed"] is False and line["phase_f"]["why"]
    if why_part:
        assert any(why_part in x for x in line["phase_f"]["why"]), line["phase_f"]["why"]


# ------------------------------------------------------------------ the armed path
def test_every_condition_true_makes_the_merge_commit_pushes_it_and_moves_the_mirror(fw, capsys):
    assert fw.tick() == 0
    assert fw.kinds() == ["decision", "would_enqueue", "would_merge", "merged", "pushed"]
    wm, merged, pushed = fw.wm(), fw.journal()[-2], fw.journal()[-1]
    assert wm["phase_f"] == {"armed": True, "why": []}
    mc = merged["merge_commit"]
    assert g(fw.mirror, "rev-list", "--parents", "-n1", mc).split() == [mc, fw.base, fw.head1]   # first parent = the old base, second = the head
    assert g(fw.mirror, "show", "-s", "--format=%an|%ae|%cn|%ce", mc) == "localci-merger|localci-merger@localhost|localci-merger|localci-merger@localhost"
    subject = g(fw.mirror, "show", "-s", "--format=%s", mc)
    assert subject == "Add b to the tree (#1)" and mg.PR_SUBJECT.search(subject)[1] == "1"   # B11 recognises it
    body = g(fw.mirror, "show", "-s", "--format=%b", mc)
    decision = next(r for r in fw.live() if r["kind"] == "decision")
    assert decision["run_dir"] in body and decision["lease_id"] in body and "Bites: the launchd tick reads the mirror" in body
    assert (merged["pr"], merged["head_sha"], merged["base_sha"], merged["tree"], merged["decision_ts"]) == (1, fw.head1, fw.base, wm["merge_tree"], decision["ts"])
    assert g(fw.mirror, "rev-parse", f"{mc}^{{tree}}") == wm["merge_tree"]
    assert (pushed["merge_commit"], pushed["mirror_updated"]) == (mc, True)
    assert fw.origin_main() == mc and g(fw.mirror, "rev-parse", "refs/merger/base") == mc   # storage and authority agree
    assert subprocess.run(["git", "-C", str(fw.origin), "merge-base", "--is-ancestor", fw.base, mc]).returncode == 0   # a fast-forward
    assert not (fw.state / mg.HALT_FILE).exists()
    ((argv, env),) = fw.pushes
    assert argv == ("push", "origin", f"{mc}:refs/heads/main")   # plain: no force, no lease, no plus
    assert env["GIT_SSH_COMMAND"] == SSH_COMMAND(fw)
    assert "merged" in capsys.readouterr().out


def test_the_key_never_reaches_the_journal_the_output_the_halt_file_or_anything_the_runner_sees(fw, capsys):
    fw.tick()
    out, err = capsys.readouterr()
    journal_text = (fw.state / "decisions.jsonl").read_text()
    for text in (journal_text, out, err):
        assert SENTINEL not in text
    ((_, env),) = fw.pushes
    assert set(env) == {"GIT_SSH_COMMAND"} and "GIT_SSH_COMMAND" not in os.environ
    for call in fw.runner.calls:
        assert not [k for k, v in call["env"].items() if k == "GIT_SSH_COMMAND" or str(fw.key) in str(v)]
    assert not any(str(fw.key) in json.dumps(r) for r in fw.journal())   # the armed path journals conditions, not the key's path; a REFUSED push's error may carry the path (ssh names the identity file), never the content


def test_the_key_content_is_never_opened_by_the_merger(fw, monkeypatch):
    opened = []
    real = open
    monkeypatch.setattr("builtins.open", lambda f, *a, **kw: (opened.append(str(f)), real(f, *a, **kw))[1])
    real_read = mg.Path.read_text
    monkeypatch.setattr(mg.Path, "read_text", lambda self, *a, **kw: (opened.append(str(self)), real_read(self, *a, **kw))[1])
    fw.tick()
    assert str(fw.key) not in opened


# ------------------------------------------------------------------ disarmed: each condition alone
def tick_with(w):
    assert w.tick() == 0


def _key_mode(w):
    w.key.chmod(0o644)


def _key_symlink(w):
    real = w.state / "elsewhere"
    real.write_text(SENTINEL)
    real.chmod(0o600)
    w.key.unlink()
    w.key.symlink_to(real)


def _key_dir(w):
    w.key.unlink()
    w.key.mkdir()
    w.key.chmod(0o600)


def _key_foreign(w, monkeypatch):
    me = os.geteuid()
    monkeypatch.setattr(mg.os, "geteuid", lambda: me + 1)


def _judged_tree_differs(w, monkeypatch):
    """The merge rehearsal yields a tree other than the one the gate judged (what a merge=union attribute can do)."""
    real = mg.git

    def git(cwd, *a, **kw):
        res = real(cwd, *a, **kw)
        if a and a[0] == "merge-tree":
            other = real(cwd, "rev-parse", f"{w.base}^{{tree}}").stdout.strip()
            return subprocess.CompletedProcess(res.args, res.returncode, other + "\0", res.stderr)
        return res
    monkeypatch.setattr(mg, "git", git)


def _halt(w):
    (w.state / mg.HALT_FILE).write_text("an operator put it here\n")


def _main_moves_during_the_gate(w, monkeypatch):
    real = mg.run_gate

    def gate(*a, **kw):
        res = real(*a, **kw)
        g(w.src, "checkout", "-q", "main")
        commit(w.src, {"z.txt": "z\n"}, "main moves during the gate")
        g(w.origin, "fetch", "-q", str(w.src), "+refs/heads/main:refs/heads/main")
        return res
    monkeypatch.setattr(mg, "run_gate", gate)


DISARM = [
    ("env", lambda w, mp: mp.delenv(mg.PHASE_F_ENV), f"{mg.PHASE_F_ENV} unset"),
    ("env-zero", lambda w, mp: mp.setenv(mg.PHASE_F_ENV, "0"), f"{mg.PHASE_F_ENV} unset"),
    ("env-true", lambda w, mp: mp.setenv(mg.PHASE_F_ENV, "true"), f"{mg.PHASE_F_ENV} unset"),
    ("ready-false", lambda w, mp: (w.state / "decisions.jsonl").unlink(), "READY false"),
    ("ready-49", lambda w, mp: w.hub.seed(w.state, n=49), "READY false"),
    ("ready-13-days", lambda w, mp: w.hub.seed(w.state, days=13), "READY false"),
    ("ready-unreadable", lambda w, mp: (w.state / "decisions.jsonl").write_text("{torn\n"), "READY unreadable"),
    ("key-missing", lambda w, mp: w.key.unlink(), "deploy_key missing"),
    ("key-0644", lambda w, mp: _key_mode(w), "mode 0644, not 0600"),
    ("key-0400", lambda w, mp: w.key.chmod(0o400), "mode 0400, not 0600"),
    ("key-0700", lambda w, mp: w.key.chmod(0o700), "mode 0700, not 0600"),
    ("key-symlink", lambda w, mp: _key_symlink(w), "not a regular file"),
    ("key-directory", lambda w, mp: _key_dir(w), "not a regular file"),
    ("key-foreign-owner", _key_foreign, "not owned by the running user"),
    ("criterion-label", lambda w, mp: w.gql.over.update(timelineItems={"nodes": []}), "criterion false: label_privileged"),
    ("halt-file", lambda w, mp: _halt(w), f"{mg.HALT_FILE} present: an operator put it here"),
    ("base-moved-in-the-gate", _main_moves_during_the_gate, "base_current false"),
    ("head-moved-at-the-moment", lambda w, mp: mp.setattr(mg, "pr_view", lambda a, n: full_pull(w, headRefOid="8" * 40)), "head_unchanged false"),
    ("pr-closed-at-the-moment", lambda w, mp: mp.setattr(mg, "pr_view", lambda a, n: full_pull(w, state="CLOSED")), "PR state CLOSED"),
    ("pr-in-the-queue-at-the-moment", lambda w, mp: mp.setattr(mg, "pr_view", lambda a, n: full_pull(w, isInMergeQueue=True)), "in GitHub's merge queue now"),
    ("pr-queue-unknown-at-the-moment", lambda w, mp: mp.setattr(mg, "pr_view", lambda a, n: {k: v for k, v in full_pull(w).items() if k != "isInMergeQueue"}),
     "in GitHub's merge queue now"),
    ("pr-draft-at-the-moment", lambda w, mp: mp.setattr(mg, "pr_view", lambda a, n: full_pull(w, isDraft=True)), "a draft now"),
    ("pr-retargeted-at-the-moment", lambda w, mp: mp.setattr(mg, "pr_view", lambda a, n: full_pull(w, baseRefName="release")), "PR base 'release', not 'main'"),
    ("label-gone-at-the-moment", lambda w, mp: mp.setattr(mg, "pr_view", lambda a, n: full_pull(w, labels={"nodes": []})), f"label {mg.ARM_LABEL} absent at the moment"),
    ("enqueue-step-enqueued", lambda w, mp: mp.setenv(mg.ARM_ENV, "1"), "not 'would_enqueue'"),
    ("halt-file-not-utf8", lambda w, mp: (w.state / mg.HALT_FILE).write_bytes(b"\xff\xfe\x00 not text"), f"{mg.HALT_FILE} present: unreadable"),
    ("halt-file-a-directory", lambda w, mp: (w.state / mg.HALT_FILE).mkdir(), f"{mg.HALT_FILE} present: unreadable"),
    ("tree-differs-from-the-judged-candidate", lambda w, mp: _judged_tree_differs(w, mp), "merged tree differs from the judged candidate tree"),
    ("pr-unreadable-at-the-moment", lambda w, mp: mp.setattr(mg, "pr_view", lambda a, n: (_ for _ in ()).throw(mg.GraphQLError("boom"))), "head re-read failed"),
]


@pytest.mark.parametrize("name,break_it,why", DISARM, ids=[d[0] for d in DISARM])
def test_one_false_condition_alone_means_no_merge_no_push_and_the_line_names_it(fw, monkeypatch, name, break_it, why):
    calls = _spy_report(monkeypatch)
    break_it(fw, monkeypatch)
    tick_with(fw)
    assert_nothing_merged(fw, why)
    others = [x for x in fw.wm()["phase_f"]["why"] if why not in x]
    if name.startswith("ready-"):   # every local condition held, so READY was evaluated and is the one thing false
        assert others == [], others
    elif name.startswith(("pr-", "head-", "label-")):   # READY was evaluated and true; the re-read at the moment of merging is what says no
        assert others == [] and calls == [{"emit": False}], (others, calls)
    else:   # a local condition is false: no minutes of report to learn a no
        assert others == ["READY not evaluated"] and calls == [], (others, calls)


def test_the_default_tick_is_the_f1_shadow_with_one_new_field_naming_why_it_is_disarmed(world, monkeypatch):
    world.gh.prs = [pr(1, world.head1, armed=False, labels=[mg.ARM_LABEL])]
    monkeypatch.delenv(mg.PHASE_F_ENV, raising=False)
    pushes = []
    real = mg.git
    monkeypatch.setattr(mg, "git", lambda cwd, *a, **kw: pushes.append(a) or real(cwd, *a, **kw))
    assert world.tick() == 0
    w = world.journal()[-1]
    assert [r["kind"] for r in world.journal()] == ["decision", "would_enqueue", "would_merge"] and not [a for a in pushes if a[0] == "push"]
    assert w["phase_f"]["armed"] is False
    assert f"{mg.PHASE_F_ENV} unset" in w["phase_f"]["why"] and any(x.startswith("READY") for x in w["phase_f"]["why"])
    assert "deploy_key missing" in w["phase_f"]["why"]


@pytest.mark.parametrize("mutate,why", [({"clean": False}, "merge not clean"), ({"base_current": False}, "base_current false"),
                                        ({"mirror_main": "e" * 40}, "mirror main is not the decided base")])
def test_the_line_facts_alone_disarm_the_step(fw, mutate, why):
    enq = {"kind": "would_enqueue", "pr": 1, "head_sha": fw.head1, "base_sha": fw.base, "criterion": {k: True for k in mg.CRITERION}, "ok": True}
    line = {"base_sha": fw.base, "mirror_main": fw.base, "base_current": True, "clean": True, **mutate}
    a = argparse.Namespace(repo=REPO, base="main")
    _, pf = mg.phase_f_arming(a, fw.state, fw.mirror, enq, line, "main")
    assert not pf["armed"] and any(why in x for x in pf["why"])


def test_a_decision_the_enqueue_criterion_refuses_is_never_merged_and_a_queued_pr_is_left_to_github(fw):
    crit = {k: True for k in mg.CRITERION}
    line = {"base_sha": fw.base, "mirror_main": fw.base, "base_current": True, "clean": True}
    a = argparse.Namespace(repo=REPO, base="main")
    for enq, why in (({"kind": "enqueue_refused", "pr": 1, "head_sha": fw.head1, "criterion": {**crit, "review_independent": False}, "ok": False},
                      "criterion false: review_independent"),
                     ({"kind": "enqueue_refused", "pr": 1, "head_sha": fw.head1, "criterion": {}, "ok": False}, "criterion false: none recorded"),
                     ({"kind": "would_enqueue", "pr": 1, "head_sha": fw.head1, "criterion": {}, "ok": True}, "criterion false: none recorded"),
                     ({"kind": "enqueued", "pr": 1, "head_sha": fw.head1, "criterion": crit, "ok": True}, "merge queue")):
        _, pf = mg.phase_f_arming(a, fw.state, fw.mirror, enq, line, "main")
        assert not pf["armed"] and any(why in x for x in pf["why"]), (why, pf)


# ------------------------------------------------------------------ the push is refused: sticky halt
def _origin_moves_before_the_push(w, monkeypatch):
    real = mg.git
    state = {"done": False}

    def moving(cwd, *a, **kw):
        if a and a[0] == "push" and not state["done"]:
            state["done"] = True
            g(w.src, "checkout", "-q", "main")
            state["sha"] = commit(w.src, {"late.txt": "late\n"}, "someone pushes to main between the read and the push")
            g(w.origin, "fetch", "-q", str(w.src), "+refs/heads/main:refs/heads/main")
        return real(cwd, *a, **kw)
    monkeypatch.setattr(mg, "git", moving)
    return state


def test_a_push_origin_rejects_is_push_refused_halts_for_good_and_the_mirror_keeps_its_main(fw, monkeypatch, capsys):
    moved = _origin_moves_before_the_push(fw, monkeypatch)
    assert fw.tick() == 0
    assert fw.kinds() == ["decision", "would_enqueue", "would_merge", "merged", "push_refused"]
    refused = fw.journal()[-1]
    assert refused["merge_commit"] == fw.journal()[-2]["merge_commit"] and refused["error"].startswith("rc=") and SENTINEL not in refused["error"]
    halt = json.loads((fw.state / mg.HALT_FILE).read_text())
    assert "refused" in halt["why"] and refused["merge_commit"] in halt["why"]
    assert g(fw.mirror, "rev-parse", "refs/merger/base") == fw.base and fw.origin_main() == moved["sha"]   # nothing moved but GitHub's own
    assert "push_refused" in capsys.readouterr().err


def test_after_a_halt_every_later_tick_decides_but_merges_nothing(fw, monkeypatch):
    _origin_moves_before_the_push(fw, monkeypatch)
    fw.tick()
    fw.pushes.clear()
    src = fw.src
    g(src, "checkout", "-q", "pr1")
    head1b = commit(src, {"b.txt": "pr1 again\n"}, "pr1 v2")
    g(fw.origin, "fetch", "-q", str(src), "+pr1:refs/pull/1/head")
    fw.gh.prs = [pr(1, head1b, armed=False, labels=[mg.ARM_LABEL])]
    fw.gql.gh = fw.gh
    before = len(fw.journal())
    assert fw.tick() == 0
    new = fw.journal()[before:]
    assert [r["kind"] for r in new] == ["decision", "would_enqueue", "would_merge"]
    assert new[-1]["phase_f"]["armed"] is False and any(mg.HALT_FILE in x for x in new[-1]["phase_f"]["why"])
    assert not [r for r in new if r["kind"] in ("merged", "pushed")] and not [a for a, _ in fw.pushes if a[0] == "push"]


def test_a_push_that_errors_is_refused_and_halts_like_a_rejection(fw, monkeypatch):
    real = mg.git
    monkeypatch.setattr(mg, "git", lambda cwd, *a, **kw: real(cwd, "push", str(fw.state / "nowhere.git"), *a[2:], **kw) if a and a[0] == "push" else real(cwd, *a, **kw))
    assert fw.tick() == 0
    assert fw.kinds()[-2:] == ["merged", "push_refused"] and (fw.state / mg.HALT_FILE).exists()
    assert g(fw.mirror, "rev-parse", "refs/merger/base") == fw.base and fw.origin_main() == fw.base


def test_a_push_that_times_out_is_a_refusal_not_a_success(fw, monkeypatch):
    real = mg.git

    def slow(cwd, *a, **kw):
        if a and a[0] == "push":
            raise subprocess.TimeoutExpired(["git", "push"], kw["timeout"])
        return real(cwd, *a, **kw)
    monkeypatch.setattr(mg, "git", slow)
    assert fw.tick() == 0
    assert fw.kinds()[-2:] == ["merged", "push_refused"] and "TimeoutExpired" in fw.journal()[-1]["error"] and (fw.state / mg.HALT_FILE).exists()
    assert g(fw.mirror, "rev-parse", "refs/merger/base") == fw.base


def test_a_failure_making_the_merge_commit_is_a_merge_error_with_no_push_and_no_halt(fw, monkeypatch):
    real = mg.git

    def broken(cwd, *a, **kw):
        if a and a[0] == "commit-tree":
            raise mg.MergerError("commit-tree failed")
        return real(cwd, *a, **kw)
    monkeypatch.setattr(mg, "git", broken)
    assert fw.tick() == 0
    assert fw.kinds()[-1] == "merge_error" and "merged" not in fw.kinds() and not (fw.state / mg.HALT_FILE).exists() and fw.origin_main() == fw.base


# ------------------------------------------------------------------ the fetch never rewinds an authoritative main
def test_a_github_main_that_lost_the_last_pushed_merge_is_storage_diverged_and_halts_instead_of_being_taken(fw, capsys):
    assert fw.tick() == 0
    merged = fw.journal()[-1]["merge_commit"]
    g(fw.origin, "update-ref", "refs/heads/main", fw.base)   # GitHub's main rewound to before our merge
    before = len(fw.journal())
    assert fw.tick() == 1
    (line,) = fw.journal()[before:]
    assert (line["kind"], line["last_pushed"], line["github_main"], line["mirror_main"]) == ("storage_diverged", merged, fw.base, merged)
    assert g(fw.mirror, "rev-parse", "refs/merger/base") == merged   # the authority was not rewound
    assert "storage diverged" in json.loads((fw.state / mg.HALT_FILE).read_text())["why"] and "storage_diverged" in capsys.readouterr().err


def test_while_halted_the_fetch_is_the_plain_one_and_the_guard_fires_again_when_the_operator_clears_the_halt(fw):
    fw.tick()
    merged = fw.journal()[-1]["merge_commit"]
    g(fw.origin, "update-ref", "refs/heads/main", fw.base)
    assert fw.tick() == 1 and (fw.state / mg.HALT_FILE).exists()
    fw.gh.prs = []
    assert fw.tick() == 0 and g(fw.mirror, "rev-parse", "refs/merger/base") == fw.base   # halted: the brief's rule, GitHub's main is read as before
    (fw.state / mg.HALT_FILE).unlink()
    assert fw.tick() == 1 and fw.kinds()[-1] == "storage_diverged" and merged not in g(fw.mirror, "rev-list", "refs/merger/base")


def test_a_github_main_that_forked_away_from_the_last_pushed_merge_is_diverged(fw):
    fw.tick()
    merged = fw.journal()[-1]["merge_commit"]
    g(fw.src, "checkout", "-q", "main")
    other = commit(fw.src, {"forked.txt": "x\n"}, "a commit that is not ours")
    g(fw.origin, "fetch", "-q", str(fw.src), "+refs/heads/main:refs/heads/main")
    assert other != merged and fw.tick() == 1 and fw.kinds()[-1] == "storage_diverged"


def test_a_github_main_ahead_of_the_last_pushed_merge_is_taken(fw):
    fw.tick()
    merged = fw.journal()[-1]["merge_commit"]
    g(fw.mirror, "fetch", "-q", "origin", "+refs/heads/main:refs/merger/base")
    g(fw.src, "fetch", "-q", str(fw.origin), "main")
    g(fw.src, "checkout", "-q", "-B", "main", merged)
    ahead = commit(fw.src, {"ahead.txt": "x\n"}, "a later commit on top of our merge")
    g(fw.origin, "fetch", "-q", str(fw.src), "+refs/heads/main:refs/heads/main")
    fw.gh.prs = []
    assert fw.tick() == 0
    assert g(fw.mirror, "rev-parse", "refs/merger/base") == ahead and not (fw.state / mg.HALT_FILE).exists() and "storage_diverged" not in fw.kinds()


def test_a_merge_that_was_never_pushed_is_no_anchor_so_a_rewound_github_main_is_taken_as_before(fw, monkeypatch):
    _origin_moves_before_the_push(fw, monkeypatch)
    fw.tick()
    (fw.state / mg.HALT_FILE).unlink()   # the operator reconciled
    g(fw.origin, "update-ref", "refs/heads/main", fw.base)
    fw.gh.prs = []
    assert fw.tick() == 0 and "storage_diverged" not in fw.kinds()
    assert g(fw.mirror, "rev-parse", "refs/merger/base") == fw.base


def test_before_phase_f_ever_pushed_a_rewritten_github_main_is_still_what_the_mirror_follows(world):
    world.gh.prs = []
    assert world.tick() == 0
    g(world.src, "checkout", "-q", "main")
    new = commit(world.src, {"y.txt": "y\n"}, "main moves")
    g(world.origin, "fetch", "-q", str(world.src), "+refs/heads/main:refs/heads/main")
    assert world.tick() == 0 and g(world.state / "repo.git", "rev-parse", "refs/merger/base") == new
    g(world.origin, "update-ref", "refs/heads/main", world.base)   # a force-push to GitHub's main, nothing of ours on it
    assert world.tick() == 0 and g(world.state / "repo.git", "rev-parse", "refs/merger/base") == world.base


# ------------------------------------------------------------------ the report
def test_the_report_says_shadow_until_phase_f_acts_then_counts_merged_and_refused(fw, tmp_path):
    a = argparse.Namespace(repo=REPO, base="main", state_dir=str(fw.state), since=None)
    assert mg.report(a, emit=False)[1]["phase_f"] == "shadow"
    fw.tick()
    rc, out = mg.report(a, emit=False)
    assert out["phase_f"] == "armed (1 merged, 0 refused)" and out["phase_f_halted"] is False
    mg.journal(fw.state, {"kind": "merged", "pr": 2})
    mg.journal(fw.state, {"kind": "push_refused", "pr": 2})
    halt = fw.state / mg.HALT_FILE
    halt.write_text("{}\n")
    out = mg.report(a, emit=False)[1]
    assert out["phase_f"] == "armed (2 merged, 1 refused)" and out["phase_f_halted"] is True


def test_the_report_prints_the_executor_line_and_the_halt(fw, capsys):
    (fw.state / mg.HALT_FILE).write_text("{}\n")
    mg.journal(fw.state, {"kind": "push_refused", "pr": 3})
    assert mg.main(["report", "--repo", REPO, "--state-dir", str(fw.state)]) == 0
    out = capsys.readouterr().out
    assert "phase F executor: armed (0 merged, 1 refused) — HALTED" in out and "phase E READY" in out


def test_the_quiet_report_writes_no_file_and_prints_nothing(fw, capsys):
    a = argparse.Namespace(repo=REPO, base="main", state_dir=str(fw.state), since=None)
    rc, out = mg.report(a, emit=False)
    assert out["phase_e_ready"] is True and rc == 0 and not (fw.state / "report.json").exists()
    assert capsys.readouterr().out == ""


def test_the_thresholds_exist_once_the_tick_reads_the_reports_own_function():
    src = (mg.Path(mg.__file__)).read_text()
    assert src.count("READY_MIN_MERGES, READY_MIN_DAYS = 50, 14") == 1   # 14 days is defined once
    assert "days + READY_SPAN_SLACK_DAYS < READY_MIN_DAYS" in src and "decided < READY_MIN_MERGES" in src   # the precheck reads the same constants
    assert "compared_merges >= READY_MIN_MERGES and compared_days >= READY_MIN_DAYS" in src
    assert "report(argparse.Namespace(" in src   # the tick calls it; there is no second ready computation


def test_the_push_url_defaults_to_the_deploy_keys_ssh_form_only_on_the_github_fetch_url():
    ns = lambda **kw: argparse.Namespace(repo="Bali-Zero/Teman2", remote_url=None, push_url=None, **kw)   # noqa: E731
    assert mg.push_url_of(ns()) == "git@github.com:Bali-Zero/Teman2.git"
    assert mg.push_url_of(argparse.Namespace(repo="o/r", remote_url="/tmp/origin.git", push_url=None)) is None
    assert mg.push_url_of(argparse.Namespace(repo="o/r", remote_url=None, push_url="ssh://git@host/r.git")) == "ssh://git@host/r.git"


@pytest.mark.parametrize("url", ["https://u:p@github.com/o/r.git", "https://token@github.com/o/r.git", "HTTPS://token@github.com/o/r.git",
                                 "http://u@host/r.git", "git://u:p@host/r.git", "https://:p@github.com/o/r.git"])
def test_a_push_url_that_carries_any_userinfo_on_a_non_ssh_scheme_is_refused(world, url, capsys):
    assert mg.main(["tick", "--node", mg.HOST, "--state-dir", str(world.state), "--remote-url", str(world.origin), "--push-url", url]) == 2
    assert "carries credentials" in capsys.readouterr().err and not (world.state / "repo.git").exists()


@pytest.mark.parametrize("url", ["ssh://git@github.com/o/r.git", "git@github.com:o/r.git", "https://github.com/o/r.git", "ssh://git@host:22/r.git"])
def test_an_ssh_user_or_a_bare_url_is_a_push_url_phase_f_accepts(world, url):
    world.gh.prs = []
    assert mg.main(["tick", "--node", mg.HOST, "--repo", REPO, "--state-dir", str(world.state), "--remote-url", str(world.origin), "--push-url", url,
                    "--python", "py"]) == 0
    assert g(world.state / "repo.git", "remote", "get-url", "--push", "origin") == url


def test_a_push_url_that_carries_a_password_is_refused_and_an_ssh_user_is_not(world):
    assert mg.main(["tick", "--node", mg.HOST, "--state-dir", str(world.state), "--remote-url", str(world.origin), "--push-url", "https://u:p@github.com/o/r.git"]) == 2
    world.gh.prs = []
    assert mg.main(["tick", "--node", mg.HOST, "--repo", REPO, "--state-dir", str(world.state), "--remote-url", str(world.origin),
                    "--push-url", str(world.origin), "--python", "py"]) == 0
    assert g(world.state / "repo.git", "remote", "get-url", "--push", "origin") == str(world.origin)


# ------------------------------------------------------------------ the precheck: a young journal never costs a full report
def _spy_report(monkeypatch):
    calls = []
    real = mg.report
    monkeypatch.setattr(mg, "report", lambda *a, **kw: calls.append(kw) or real(*a, **kw))
    return calls


def test_a_journal_younger_than_the_window_is_not_ready_and_the_full_report_is_not_run(fw, monkeypatch):
    calls = _spy_report(monkeypatch)
    fw.hub.seed(fw.state, age=3)
    assert fw.tick() == 0
    assert calls == []
    (why,) = [x for x in fw.wm()["phase_f"]["why"] if x.startswith("READY")]
    assert re.fullmatch(r"READY false: journal window \d\.\d days \(\+1 of slack\) < 14", why) and why.startswith("READY false: journal window 3.")
    assert_nothing_merged(fw, "journal window")


def test_a_journal_with_fewer_decided_prs_than_the_threshold_is_not_ready_and_the_report_is_not_run(fw, monkeypatch):
    calls = _spy_report(monkeypatch)
    fw.hub.seed(fw.state, n=10)
    assert fw.tick() == 0
    assert calls == [] and "READY false: 11 distinct decided PRs < 50" in fw.wm()["phase_f"]["why"]
    assert_nothing_merged(fw)


def test_an_old_journal_with_enough_prs_runs_the_full_report_and_can_be_ready(fw, monkeypatch):
    calls = _spy_report(monkeypatch)
    assert fw.tick() == 0
    assert calls == [{"emit": False}] and fw.wm()["phase_f"]["armed"] is True


def test_the_precheck_never_says_ready_and_an_unreadable_journal_rules_nothing_out(fw):
    assert mg.ready_precheck(fw.state) is None   # old and wide enough: undecided, the report decides
    (fw.state / "decisions.jsonl").write_text("{torn\n")
    assert mg.ready_precheck(fw.state) is None
    (fw.state / "decisions.jsonl").write_text("")
    assert mg.ready_precheck(fw.state) == "READY false: no decision in the journal"


def test_the_precheck_window_starts_a_day_before_the_first_decision_so_it_never_says_false_while_ready_is_true(fw):
    """merged_at can precede its own decision line by up to one tick: at 13 days of journal the report's span can already be 14."""
    def first_decision_ago(days, delta_s):
        import time
        at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(time.time()) - days * 86400 + delta_s))
        lines = [json.loads(ln) for ln in (fw.state / "decisions.jsonl").read_text().splitlines()]
        lines[0]["ts"] = at
        for r in lines[1:]:
            r["ts"] = max(r["ts"], at)
        (fw.state / "decisions.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in lines))
    fw.hub.seed(fw.state, age=2)
    first_decision_ago(13, -120)   # a hair OVER 13 days: with the day of slack the window is 14: undecided, the report decides
    assert mg.ready_precheck(fw.state) is None
    first_decision_ago(13, 120)    # a hair UNDER 13 days: 13.99 even with the slack: false
    assert mg.ready_precheck(fw.state).startswith("READY false: journal window 12.9 days (+1 of slack) < 14")
    assert mg.READY_SPAN_SLACK_DAYS == 1


def test_a_halt_file_that_is_a_dangling_symlink_is_still_a_halt_in_the_report(fw):
    a = argparse.Namespace(repo=REPO, base="main", state_dir=str(fw.state), since=None)
    (fw.state / mg.HALT_FILE).symlink_to(fw.state / "nowhere")
    assert not (fw.state / mg.HALT_FILE).exists() and mg.halt_reason(fw.state) == "unreadable"
    assert mg.report(a, emit=False)[1]["phase_f_halted"] is True


def test_a_non_utf8_halt_file_halts_and_the_fetch_is_not_the_guarded_one(fw):
    (fw.state / mg.HALT_FILE).write_bytes(b"\xff\xfe not text")
    assert mg.halt_reason(fw.state) == "unreadable"
    assert fw.tick() == 0   # a ValueError out of the halt read must not crash the tick
    assert_nothing_merged(fw, f"{mg.HALT_FILE} present: unreadable")


def test_the_pr_gate_reads_after_the_local_ones_and_a_clean_pull_arms(fw, monkeypatch):
    """Innocence for the re-read: every local condition and every re-read field right means armed."""
    monkeypatch.setattr(mg, "pr_view", lambda a, n: full_pull(fw))
    assert fw.tick() == 0 and fw.wm()["phase_f"] == {"armed": True, "why": []} and fw.kinds()[-1] == "pushed"


def test_ready_is_not_evaluated_when_the_env_half_is_missing_and_the_why_says_so(fw, monkeypatch):
    calls = _spy_report(monkeypatch)
    monkeypatch.delenv(mg.PHASE_F_ENV)
    assert fw.tick() == 0 and calls == []
    assert fw.wm()["phase_f"]["why"] == [f"{mg.PHASE_F_ENV} unset", "READY not evaluated"]


def test_a_missing_judged_candidate_is_a_disarmed_step(fw):
    fw.gh.prs = []
    assert fw.tick() == 0   # the mirror now holds the base
    a = argparse.Namespace(repo=REPO, base="main")
    enq = {"kind": "would_enqueue", "pr": 1, "head_sha": fw.head1, "base_sha": fw.base, "criterion": {k: True for k in mg.CRITERION}, "ok": True}
    line = {"base_sha": fw.base, "mirror_main": fw.base, "base_current": True, "clean": True, "merge_tree": "5" * 40}
    for cand, why in ((None, "judged candidate tree unreadable"), ("7" * 40, "judged candidate tree unreadable"), (fw.base, "merged tree differs from the judged candidate tree")):
        _, pf = mg.phase_f_arming(a, fw.state, fw.mirror, {**enq, "candidate_sha": cand}, line, "main")
        assert not pf["armed"] and why in pf["why"], (cand, pf)


# ------------------------------------------------------------------ the push: halt before the journal, and on any interruption
def test_the_halt_is_written_before_push_refused_is_journalled(fw, monkeypatch):
    _origin_moves_before_the_push(fw, monkeypatch)
    seen = []
    real = mg.journal

    def spy(state, rec):
        if rec.get("kind") == "push_refused":
            seen.append((fw.state / mg.HALT_FILE).exists())
        return real(state, rec)
    monkeypatch.setattr(mg, "journal", spy)
    assert fw.tick() == 0 and seen == [True]


def test_a_journal_that_fails_on_push_refused_still_leaves_the_halt(fw, monkeypatch):
    _origin_moves_before_the_push(fw, monkeypatch)
    real = mg.journal

    def broken(state, rec):
        if rec.get("kind") == "push_refused":
            raise OSError("disk full")
        return real(state, rec)
    monkeypatch.setattr(mg, "journal", broken)
    try:
        fw.tick()
    except OSError:
        pass
    assert (fw.state / mg.HALT_FILE).exists()


@pytest.mark.parametrize("exc", [mg.Stopped("SIGTERM"), KeyboardInterrupt()], ids=["stopped", "keyboard-interrupt"])
def test_a_push_interrupted_halts_first_and_the_interruption_still_propagates(fw, monkeypatch, exc):
    real = mg.git

    def interrupted(cwd, *a, **kw):
        if a and a[0] == "push":
            raise exc
        return real(cwd, *a, **kw)
    monkeypatch.setattr(mg, "git", interrupted)
    try:
        fw.tick()
    except BaseException as caught:  # noqa: BLE001 — what is asserted is that it was not swallowed into a success
        assert caught is exc or isinstance(caught, type(exc))
    assert (fw.state / mg.HALT_FILE).exists() and "interrupted" in json.loads((fw.state / mg.HALT_FILE).read_text())["why"]
    assert {"pushed", "push_refused"}.isdisjoint(fw.kinds()) and g(fw.mirror, "rev-parse", "refs/merger/base") == fw.base


def test_a_stopped_tick_before_the_push_halts_nothing(fw, monkeypatch):
    real = mg.git

    def stopped(cwd, *a, **kw):
        if a and a[0] == "commit-tree":
            raise mg.Stopped("SIGTERM")
        return real(cwd, *a, **kw)
    monkeypatch.setattr(mg, "git", stopped)
    try:
        fw.tick()
    except mg.Stopped:
        pass
    assert not (fw.state / mg.HALT_FILE).exists() and fw.pushes == []


# ------------------------------------------------------------------ the launchd wrapper never moves refs/merger/base
def test_the_wrapper_fetches_into_its_own_ref_and_leaves_the_authoritative_base_alone(tmp_path):
    src, origin, _, env = mirror_world(tmp_path)
    mirror = tmp_path / "state" / "repo.git"
    assert wrap(env).returncode == 0
    v1 = g(origin, "rev-parse", "main")
    assert g(mirror, "rev-parse", "refs/merger/wrapper") == v1
    assert subprocess.run(["git", "-C", str(mirror), "rev-parse", "--verify", "--quiet", "refs/merger/base"], env=GIT_ENV).returncode != 0   # merger.py's, never the wrapper's
    g(src, "checkout", "-q", "-b", "pushed")
    pushed = commit(src, {"pushed.txt": "a merge phase F pushed\n"}, "phase F merge")
    g(mirror, "fetch", "-q", str(src), "+pushed:refs/merger/base")   # the mirror's authority: the last pushed merge
    g(src, "checkout", "-q", "main")
    commit(src, {"scripts/localci/merger.py": "v2 --code-sha\n"}, "github main without our merge")
    g(src, "push", "-q", str(origin), "main")
    v2 = g(origin, "rev-parse", "main")
    assert wrap(env).returncode == 0
    assert g(mirror, "rev-parse", "refs/merger/base") == pushed   # untouched: fetch_base's guard still has its anchor to compare
    assert g(mirror, "rev-parse", "refs/merger/wrapper") == v2 and (tmp_path / "code").read_text() == "v2 --code-sha\n"
    assert f"--code-sha={v2}" in (tmp_path / "args").read_text().split()


def test_a_mirror_from_before_the_wrapper_ref_existed_runs_the_code_the_last_tick_ran(tmp_path):
    src, origin, _, env = mirror_world(tmp_path)
    mirror = tmp_path / "state" / "repo.git"
    assert wrap(env).returncode == 0
    v1 = g(mirror, "rev-parse", "refs/merger/wrapper")
    g(mirror, "update-ref", "refs/merger/base", v1)
    g(mirror, "update-ref", "-d", "refs/merger/wrapper")
    origin.rename(tmp_path / "gone.git")
    res = wrap(env)
    assert res.returncode == 0 and "fetch failed" in res.stderr and (tmp_path / "code").read_text() == "v1 --code-sha\n"
    assert f"--code-sha={v1}" in (tmp_path / "args").read_text().split()


@pytest.mark.parametrize("kind", ["enqueued", "enqueue_error", "enqueue_refused", "enqueue_skipped", None])
def test_only_a_would_enqueue_step_can_be_merged_by_phase_f(fw, kind):
    a = argparse.Namespace(repo=REPO, base="main")
    enq = {"kind": kind, "pr": 1, "head_sha": fw.head1, "base_sha": fw.base, "criterion": {k: True for k in mg.CRITERION}, "ok": True}
    line = {"base_sha": fw.base, "mirror_main": fw.base, "base_current": True, "clean": True}
    _, pf = mg.phase_f_arming(a, fw.state, fw.mirror, enq, line, "main")
    assert not pf["armed"] and any("not 'would_enqueue'" in x and "merge queue" in x for x in pf["why"]), pf
