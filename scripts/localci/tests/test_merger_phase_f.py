"""F2 guilt + innocence: the phase F executor is disarmed by construction. Real git repos under tmp, a local bare repo as GitHub's origin,
GitHub's API faked, no network. Every arming condition is broken ALONE with all the others true; the armed path is proven end to end."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess

import pytest

from .test_merger import GIT_ENV, REPO, FakeRunner, g, commit, mg, pr, world  # noqa: F401 — `world` is a fixture

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

    def seed(self, state, n=50, days=14):
        """n merged, compared PRs spanning `days`: exactly phase D's threshold."""
        state.mkdir(parents=True, exist_ok=True)
        lines = []
        for i in range(n):
            head, at = f"{i + 1:040x}", time_at(i * days * 86400 // (n - 1))
            self.pulls[1001 + i] = {"merged": True, "state": "closed", "head": {"sha": head}, "merge_commit_sha": M, "merged_at": at}
            lines.append({"kind": "decision", "ts": at, "pr": 1001 + i, "head_sha": head, "base_sha": OLD_BASE, "candidate_sha": "9" * 40, "overall": "BLOCKED",
                          "contexts_status": "ok", "contexts": dict.fromkeys(CTX, "OK"), "coverage": dict.fromkeys(CTX, "full")})
        (state / "decisions.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in lines))


def time_at(offset_s: int) -> str:
    import calendar
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(calendar.timegm((2026, 10, 1, 0, 0, 0)) + offset_s))


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
    assert env["GIT_SSH_COMMAND"] == f"ssh -i {fw.key} -o IdentitiesOnly=yes -o BatchMode=yes"
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
    assert not any(str(fw.key) in json.dumps(r) for r in fw.journal())   # not even the path: the journal names conditions, not the key


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
    ("head-moved-at-the-moment", lambda w, mp: mp.setattr(mg, "pr_view", lambda a, n: {"headRefOid": "8" * 40, "state": "OPEN"}), "head_unchanged false"),
    ("pr-closed-at-the-moment", lambda w, mp: mp.setattr(mg, "pr_view", lambda a, n: {"headRefOid": w.head1, "state": "CLOSED"}), "PR state CLOSED"),
    ("pr-unreadable-at-the-moment", lambda w, mp: mp.setattr(mg, "pr_view", lambda a, n: (_ for _ in ()).throw(mg.GraphQLError("boom"))), "head re-read failed"),
]


@pytest.mark.parametrize("name,break_it,why", DISARM, ids=[d[0] for d in DISARM])
def test_one_false_condition_alone_means_no_merge_no_push_and_the_line_names_it(fw, monkeypatch, name, break_it, why):
    break_it(fw, monkeypatch)
    tick_with(fw)
    assert_nothing_merged(fw, why)
    others = [x for x in fw.wm()["phase_f"]["why"] if why not in x]
    assert others == [], others   # alone: nothing else is reported false


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
    assert src.count("compared_merges >= 50") == 1 and src.count("compared_days >= 14") == 1
    assert "report(argparse.Namespace(" in src   # the tick calls it; there is no second ready computation


def test_the_push_url_defaults_to_the_deploy_keys_ssh_form_only_on_the_github_fetch_url():
    ns = lambda **kw: argparse.Namespace(repo="Bali-Zero/Teman2", remote_url=None, push_url=None, **kw)   # noqa: E731
    assert mg.push_url_of(ns()) == "git@github.com:Bali-Zero/Teman2.git"
    assert mg.push_url_of(argparse.Namespace(repo="o/r", remote_url="/tmp/origin.git", push_url=None)) is None
    assert mg.push_url_of(argparse.Namespace(repo="o/r", remote_url=None, push_url="ssh://git@host/r.git")) == "ssh://git@host/r.git"


def test_a_push_url_that_carries_a_password_is_refused_and_an_ssh_user_is_not(world):
    assert mg.main(["tick", "--node", mg.HOST, "--state-dir", str(world.state), "--remote-url", str(world.origin), "--push-url", "https://u:p@github.com/o/r.git"]) == 2
    world.gh.prs = []
    assert mg.main(["tick", "--node", mg.HOST, "--repo", REPO, "--state-dir", str(world.state), "--remote-url", str(world.origin),
                    "--push-url", str(world.origin), "--python", "py"]) == 0
    assert g(world.state / "repo.git", "remote", "get-url", "--push", "origin") == str(world.origin)
