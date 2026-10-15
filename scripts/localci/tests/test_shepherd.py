"""B34 P1 guilt + innocence: the shepherd observes and never writes; its budget, its lease and its NEVER predicates hold."""
from __future__ import annotations

import ast
import json
import os
import plistlib
import platform
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from . import fixture_repo  # noqa: F401 - the package import path the other localci tests use
from .. import shepherd as sh

ROOT = Path(__file__).resolve().parents[3]
REPO = "Bali-Zero/Teman2"
HEAD = "a" * 40
CHECKS = "scripts/localci/shepherd.py"


def pr(n=1, *, author=("alice", "User"), branch="agent/x/y", draft=False, fork=False, base="main", labels=(), files=("a.py",),
       contexts=(), review=None, total=None, files_total=None, labels_total=None):
    nodes = [{"__typename": "StatusContext", "context": c, "state": "SUCCESS"} if isinstance(c, str) else c for c in contexts]
    return {"number": n, "isDraft": draft, "isCrossRepository": fork, "baseRefName": base, "headRefName": branch, "headRefOid": HEAD,
            "reviewDecision": review, "author": {"login": author[0], "__typename": author[1]},
            "labels": {"totalCount": labels_total if labels_total is not None else len(labels), "nodes": [{"name": x} for x in labels]},
            "files": {"totalCount": files_total if files_total is not None else len(files), "nodes": [{"path": f} for f in files]},
            "commits": {"nodes": [{"commit": {"statusCheckRollup": {"contexts": {"totalCount": total if total is not None else len(nodes), "nodes": nodes}}}}]}}


def brief(gear=2, gate_class="opus"):
    return {"gear": gear, "gate_class": gate_class}


def row(p, b=None, role=None):
    return sh.classify(p, b, role)


# ------------------------------------------------------------------ budget
@pytest.mark.parametrize("core,gql,mode", [(1499, 5000, "observe"), (1500, 5000, "act"), (799, 5000, "skip"), (800, 5000, "observe"),
                                           (5000, 999, "skip"), (5000, 1000, "act"), (0, 0, "skip")])
def test_the_budget_floors_are_exact(core, gql, mode):
    assert sh.budget_mode(core, gql) == mode


def test_the_sixty_first_rest_call_is_never_made():
    made = []
    rest = sh.Rest(REPO, lambda path: made.append(path) or {}, sh.CallCap())
    for i in range(60):
        rest(f"p{i}")
    with pytest.raises(sh.BudgetCap):
        rest("p60")
    assert len(made) == 60 and rest.cap.used == 60


def test_a_fixed_charge_that_would_cross_the_cap_is_refused_whole():
    cap = sh.CallCap()
    cap.charge(59)
    with pytest.raises(sh.BudgetCap):
        cap.charge(2)
    assert cap.used == 59


# ------------------------------------------------------------------ the off-limits entities
@pytest.mark.parametrize("path", ["zantara_core.py", "apps/x/fly.toml", "fly.toml", ".env", ".env.example", "apps/x/.env.local",
                                  "apps/bali-intel-scraper/backend/db/migrations/env.py"])
def test_off_limits_guilt(path):
    assert sh.off_limits(path)


@pytest.mark.parametrize("path", ["docs/environment.md", "scripts/env.py", "apps/other/db/migrations/env.py", "src/zantara_core_utils.py",
                                  "fly.toml.md", "apps/x/envelope.py", "README.md", "config/app.env", "docs/dot.env.md"])
def test_off_limits_innocence(path):
    assert not sh.off_limits(path)


def test_the_off_limits_entities_are_the_line_in_rulings():
    line = next(x for x in (ROOT / "docs/rules/RULINGS.md").read_text().splitlines() if x.startswith("**Off-limits files**"))
    named = re.findall(r"`([^`]+)`", line)
    assert set(named) == {"zantara_core.py", "fly.toml", ".env*", sh.OFF_LIMITS_PATH}
    assert set(sh.OFF_LIMITS_BASENAMES) | {sh.OFF_LIMITS_ENV_PREFIX + "*", sh.OFF_LIMITS_PATH} == set(named)


# ------------------------------------------------------------------ the classifier, per class
def test_class4_gate_missing_guilt_and_innocence():
    assert "gate_missing" in row(pr(), brief())["classes"]
    assert row(pr(), brief())["actions"][0] == "would_gate"
    assert row(pr(), brief(gate_class=None))["actions"][0] == "would_gate"
    assert row(pr(), brief(gate_class="fable"))["actions"][0] == "would_gate_manual"
    assert "gate_missing" not in row(pr(contexts=[sh.GATE_CONTEXT]), brief())["classes"]
    assert "gate_missing" not in row(pr(), brief(gear=1))["classes"]
    assert "gate_missing" not in row(pr(), brief(gear=True))["classes"]   # bool is not an int gear
    assert "gate_missing" not in row(pr(), brief(gear="2"))["classes"]
    assert "gate_missing" not in row(pr(), None)["classes"]
    assert "gate_missing" not in row(pr(contexts=["x"], total=150), brief())["classes"]   # a truncated rollup cannot show the gate is absent


def test_class7_label_candidates_by_author_class():
    assert row(pr(author=("dependabot", "Bot")))["author_class"] == "dependabot"
    assert row(pr(author=("renovate", "Bot")))["author_class"] == "bot"
    assert row(pr(author=("alice", "User"), branch="codex/x"), role="admin")["author_class"] == "codex"
    assert row(pr(author=("bob", "User")), role="write")["author_class"] == "collaborator"
    assert row(pr(author=("bob", "User")), role=None)["author_class"] == "unknown_role"
    assert row(pr(author=("bob", "User")), role="write")["actions"] == ["would_label"]
    admin = row(pr(), role="admin")
    assert admin["classes"] == ["own_lane"] and admin["actions"] == []
    assert "label_candidate" not in row(pr(author=("dependabot", "Bot"), labels=[sh.mg.ARM_LABEL]))["classes"]
    assert row(pr(author=("dependabot", "Bot"), labels=["other"]))["actions"] == ["would_label"]


def test_never_predicates_win_over_every_would_action():
    r = row(pr(fork=True, author=("dependabot", "Bot")), brief())
    assert (r["actions"], r["reason"], r["classes"]) == (["never_auto"], "fork", [])
    r = row(pr(files=["apps/x/fly.toml"], author=("dependabot", "Bot")), brief())
    assert (r["actions"], r["reason"]) == (["never_auto"], "off_limits")
    assert row(pr(files=[".env.example"]), brief())["reason"] == "off_limits"
    assert row(pr(files=["docs/environment.md"]), brief())["actions"][0] == "would_gate"
    assert row(pr(review="CHANGES_REQUESTED", author=("dependabot", "Bot")))["reason"] == "changes_requested"
    assert row(pr(draft=True), brief())["reason"] == "draft"
    assert row(pr(base="release"), brief())["reason"] == "base_not_main"


# ------------------------------------------------------------------ the tick
class World:
    def __init__(self, core=5000, gql=5000, prs=(), briefs=None, roles=None):
        self.core, self.gql, self.prs, self.briefs, self.roles = core, gql, list(prs), briefs or {}, roles or {}
        self.rest_paths: list[str] = []
        self.all_calls: list[str] = []   # every GET, rate_limit included: the account's real REST spend of the tick

    def get(self, path):
        self.all_calls.append(path)
        if path == "rate_limit":
            return {"resources": {"core": {"remaining": self.core, "reset": 1}, "graphql": {"remaining": self.gql}}}
        self.rest_paths.append(path)
        m = re.fullmatch(r"repos/[^/]+/[^/]+/collaborators/([^/]+)/permission", path)
        if m:
            return {"role_name": self.roles.get(m.group(1), "read")}
        raise sh.hc.CompareError(f"unexpected {path}")

    def graphql(self, query, **variables):
        if "pullRequests" in query:
            return {"repository": {"pullRequests": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": self.prs}}}
        return {"repository": {f"b{n}": {"text": yaml.safe_dump(b)} for n, b in self.briefs.items() if f"b{n}:" in query}}


def run_tick(tmp_path, world, monkeypatch, node=None):
    return sh.tick(tmp_path / "state", REPO, node or platform.node(), get=world.get, gql=world.graphql)


def rows(tmp_path):
    return [json.loads(x) for x in (tmp_path / "state/journal.jsonl").read_text().splitlines()]


def prs_world(**kw):
    b = ["evidence/2026-10/t/brief.yml"]
    return World(prs=[pr(1, files=b), pr(2, author=("dependabot", "Bot")), pr(3, author=("bob", "User"), files=b), pr(4, fork=True), pr(5, files=["fly.toml"])],
                 briefs={1: brief(), 3: brief(gate_class="fable")}, roles={"alice": "admin", "bob": "write"}, **kw)


def test_below_1500_the_tick_only_observes_and_makes_no_rest_call(tmp_path, monkeypatch):
    w = prs_world(core=1499)
    out = run_tick(tmp_path, w, monkeypatch)
    assert out["status"] == "ok" and w.rest_paths == []
    assert [r["event"] for r in rows(tmp_path)] == ["observe"]
    assert rows(tmp_path)[0]["mode"] == "observe" and rows(tmp_path)[0]["rest_calls"] == 1   # the rate_limit read, counted


def test_at_1500_the_tick_is_act_eligible_and_journals_would_rows_without_writing(tmp_path, monkeypatch):
    w = prs_world(core=1500)
    run_tick(tmp_path, w, monkeypatch)
    ev = [r["event"] for r in rows(tmp_path)]
    assert "would_gate" in ev and "would_label" in ev and "never_auto" in ev and ev[-1] == "observe"
    last = rows(tmp_path)[-1]
    assert last["mode"] == "act" and last["classes"]["gate_missing"] == 2 and last["classes"]["never:fork"] == 1 and last["classes"]["never:off_limits"] == 1
    assert last["fork"] == 1 and last["rest_calls"] == len(w.all_calls) == len(w.rest_paths) + 1 == 3   # rate_limit, alice and bob, one counted call each; the real count
    assert all(p.startswith("repos/") and "collaborators" in p for p in w.rest_paths)
    assert (tmp_path / "state/journal.jsonl").stat().st_mode & 0o777 == 0o600


def test_below_800_or_graphql_below_1000_the_tick_skips_with_a_warning(tmp_path, monkeypatch):
    for core, gql in ((799, 5000), (5000, 999)):
        out = run_tick(tmp_path, prs_world(core=core, gql=gql), monkeypatch)
        assert out["status"] == "warning" and "skipped_quota" in out["note"]
    assert [r["event"] for r in rows(tmp_path)] == ["skipped_quota", "skipped_quota"]


def test_a_second_live_tick_exits_on_the_lease(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    fh, lease = sh.mg.take_lease(state, REPO)
    assert fh is not None
    try:
        w = prs_world()
        out = run_tick(tmp_path, w, monkeypatch)
        assert out["status"] == "ok" and "lease" in out["note"] and w.rest_paths == []
        assert [r["event"] for r in rows(tmp_path)] == ["skipped_lease"]
    finally:
        sh.mg.drop_lease(state, fh, lease)
    run_tick(tmp_path, prs_world(core=1499), monkeypatch)   # the lease is released: the next tick runs
    assert rows(tmp_path)[-1]["event"] == "observe"


def test_a_host_that_is_not_the_node_is_disabled_and_touches_nothing(tmp_path, monkeypatch):
    out = run_tick(tmp_path, prs_world(), monkeypatch, node="Not-This-Host")
    assert out["status"] == "disabled" and not (tmp_path / "state").exists()


def test_the_cap_ends_the_role_reads_cleanly(tmp_path, monkeypatch):
    monkeypatch.setattr(sh, "REST_CAP", 2)   # rate_limit and one role read
    run_tick(tmp_path, World(prs=[pr(1, author=("a1", "User")), pr(2, author=("a2", "User"))], briefs={}), monkeypatch)
    ev = [r["event"] for r in rows(tmp_path)]
    assert "budget_cap" in ev and ev[-1] == "observe"


def test_a_truncated_queue_is_refused(tmp_path):
    def endless(query, **v):
        return {"repository": {"pullRequests": {"pageInfo": {"hasNextPage": True, "endCursor": "c"}, "nodes": [pr(1)]}}}
    with pytest.raises(sh.mg.MergerError):
        sh.list_open(REPO, endless)


# ------------------------------------------------------------------ no write verb, and the packaging
ALLOWED_ATTRS = {   # every attribute of a module name that shepherd.py may touch: reads, the lease, the redactor, the journal's fsync
    "mg": {"hc", "ARM_LABEL", "ARM_ROLES", "_LOGIN_RE", "is_sha", "now", "HOST", "take_lease", "drop_lease", "gh_graphql", "redact",
           "MergerError", "DEFAULT_STATE"},
    "hc": {"gh_get", "CompareError", "DEFAULT_REPO"},
    "os": {"open", "write", "fsync", "close", "O_WRONLY", "O_APPEND", "O_CREAT"},
    "sys": {"modules", "stdout", "exit"},
    "platform": {"node"},
    "time": set(),
    "json": {"dumps"},
    "re": {"compile"},
}
ALLOWED_IMPORTS = {"argparse", "importlib.util", "json", "os", "platform", "re", "sys", "time", "pathlib", "yaml", "__future__"}
WRITE_WORDS = ("pr comment", "pr edit", "pr merge", "pr review", "pr close", "run rerun", "statuses", "mutation", "--method", "git push", "-X")


def test_shepherd_py_can_only_reach_the_allowlisted_attributes_and_holds_no_write_verb_even_assembled():
    text = (ROOT / CHECKS).read_text()
    tree = ast.parse(text)
    seen: dict[str, set] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in ALLOWED_ATTRS:
            seen.setdefault(node.value.id, set()).add(node.attr)
        if isinstance(node, ast.Import):
            assert {a.name for a in node.names} <= ALLOWED_IMPORTS, [a.name for a in node.names]
        if isinstance(node, ast.ImportFrom):
            assert node.module in ALLOWED_IMPORTS, node.module
        assert not (isinstance(node, ast.Name) and node.id in ("subprocess", "eval", "exec", "__import__")), node.id
    for mod, attrs in seen.items():
        assert attrs <= ALLOWED_ATTRS[mod], (mod, attrs - ALLOWED_ATTRS[mod])
    consts, todo = [], [compile(text, CHECKS, "exec")]   # the compiler folds "mut" + "ation" into one constant: scan what it holds
    while todo:
        code = todo.pop()
        for c in code.co_consts:
            if hasattr(c, "co_consts"):
                todo.append(c)
            elif isinstance(c, str):
                consts.append(c)
    for word in WRITE_WORDS:
        assert not any(word.lower() in c.lower() for c in consts), word
    assert not any(re.search(r"\b(POST|PATCH|PUT|DELETE)\b", c) for c in consts)


def test_the_allowlist_test_itself_catches_a_merger_write_and_an_assembled_mutation(tmp_path):
    for bad in ("def f():\n    return mg.enqueue_step(1)\n", 'Q = "mut" + "ation{x}"\n', "def f():\n    return subprocess.run([])\n"):
        text = (ROOT / CHECKS).read_text() + "\n" + bad
        (tmp_path / "x.py").write_text(text)
        probe = tmp_path / "probe.py"
        probe.write_text("import ast,sys\nt=open(sys.argv[1]).read()\ntree=ast.parse(t)\nbad=0\n"
                         "for n in ast.walk(tree):\n    if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Name) and n.value.id=='mg' and n.attr=='enqueue_step': bad=1\n"
                         "    if isinstance(n,ast.Name) and n.id=='subprocess': bad=1\n"
                         "import re\nbad |= 'mutation' in ''.join(c for c in compile(t,'x','exec').co_consts if isinstance(c,str)).lower()\nprint(bad)\n")
        assert subprocess.run([sys.executable, str(probe), str(tmp_path / "x.py")], capture_output=True, text=True).stdout.strip() == "1", bad


def test_the_plist_has_no_keepalive_and_ticks_every_600s_through_the_declared_wrapper():
    doc = plistlib.loads((ROOT / "infra/launchagents/com.balizero.localci-shepherd.plist").read_bytes())
    assert doc["StartInterval"] == 600 and "KeepAlive" not in doc and doc["Label"] == "com.balizero.localci-shepherd"
    assert doc["ProgramArguments"][-1].endswith("/.nuzantara-cron/localci_shepherd_tick.sh")
    pairs = json.loads((ROOT / "infra/home-fork/declared-pairs.json").read_text())["pairs"]
    assert any(p["repo"] == "scripts/localci/localci_shepherd_tick.sh" and p["machines"] == ["pro"] for p in pairs)


def test_the_organ_is_registered_like_the_merger():
    organs = yaml.safe_load((ROOT / "apps/organism/organism/organs_registry.yaml").read_text())
    organs = organs["organs"] if isinstance(organs, dict) else organs
    o = next(x for x in organs if x["id"] == "pro.localci_shepherd")
    assert (o["runtime"], o["type"], o["expected_hb_seconds"]) == ("pro_launchd", "cron", 1200)
    assert o["owner_module"] == "scripts/localci/localci_shepherd_tick.sh" and o["recovery_params"]["label"] == "com.balizero.localci-shepherd"
    assert o["bridge_source"]["path"] == "~/.organism/last_seen/pro.localci_shepherd.json"


# ------------------------------------------------------------------ F1/F2 and the LOWs
def test_the_real_rest_calls_equal_the_counted_ones_for_every_author_mix(tmp_path, monkeypatch):
    w = World(prs=[pr(i, author=(f"u{i % 4}", "User")) for i in range(1, 9)], roles={f"u{i}": "write" for i in range(4)})
    run_tick(tmp_path, w, monkeypatch)
    assert rows(tmp_path)[-1]["rest_calls"] == len(w.all_calls) == len(w.rest_paths) + 1 == 5   # rate_limit and one per distinct login, cached across the eight PRs


def test_a_failed_role_read_is_remembered_and_not_retried_for_the_logins_other_prs(tmp_path, monkeypatch):
    w = World(prs=[pr(i, author=("flaky", "User")) for i in range(1, 4)])
    w.get_orig = w.get
    w.get = lambda path: (w.rest_paths.append(path), (_ for _ in ()).throw(sh.hc.CompareError("503")))[1] if "collaborators" in path else w.get_orig(path)
    run_tick(tmp_path, w, monkeypatch)
    assert len(w.rest_paths) == 1 and rows(tmp_path)[-1]["classes"]["label_candidate"] == 3


def test_labelled_codex_and_draft_prs_cost_no_role_read(tmp_path, monkeypatch):
    w = World(prs=[pr(1, labels=[sh.mg.ARM_LABEL]), pr(2, branch="codex/x"), pr(3, draft=True), pr(4, author=("ghost", "Bot"))])
    run_tick(tmp_path, w, monkeypatch)
    assert w.rest_paths == []


def test_more_than_a_hundred_files_is_never_auto_whatever_the_first_hundred_say():
    guilt = row(pr(files=["a.py"] * 100, files_total=150, author=("dependabot", "Bot")), brief())
    assert (guilt["actions"], guilt["reason"], guilt["classes"]) == (["never_auto"], "files_truncated", [])
    assert row(pr(files=["a.py"] * 100, files_total=100, author=("dependabot", "Bot")))["actions"] == ["would_label"]   # exactly 100: complete
    assert row(pr(files=["a.py"] * 100, files_total=101), brief())["reason"] == "files_truncated"


def test_a_brief_in_a_truncated_file_list_is_not_read():
    p = pr(files=["evidence/2026-10/t/brief.yml"], files_total=101)
    assert sh.brief_path(p) is None
    asked = []
    assert sh.read_briefs(REPO, [p], lambda q, **v: asked.append(q)) == {} and asked == []
    assert sh.brief_path(pr(files=["evidence/2026-10/t/brief.yml"])) == "evidence/2026-10/t/brief.yml"
    assert sh.brief_path(pr(files=["evidence/2026-10/t/brief.yml", "evidence/2026-10/u/brief.yml"])) is None   # two briefs: none


@pytest.mark.parametrize("resources", [{}, {"core": {"remaining": 5000}}, {"core": {"remaining": 5000}, "graphql": {}},
                                       {"core": {"remaining": "5000"}, "graphql": {"remaining": 5000}}, {"core": {"remaining": True}, "graphql": {"remaining": 5000}}])
def test_an_unreadable_rate_limit_is_no_tick_never_a_full_budget(tmp_path, monkeypatch, resources):
    w = prs_world()
    w.get_orig = w.get
    w.get = lambda path: {"resources": resources} if path == "rate_limit" else w.get_orig(path)
    with pytest.raises(sh.mg.MergerError):
        run_tick(tmp_path, w, monkeypatch)
    assert w.rest_paths == [] and not (tmp_path / "state/journal.jsonl").exists()


def test_a_rate_limit_that_fails_to_read_raises_and_main_journals_an_error(tmp_path, monkeypatch, capsys):
    def boom(path):
        raise sh.hc.CompareError("rate_limit 502")
    monkeypatch.setattr(sh.hc, "gh_get", boom)
    assert sh.main(["tick", "--node", platform.node(), "--state-dir", str(tmp_path / "s")]) == 1
    assert capsys.readouterr().out.startswith("status=error")
    assert [json.loads(x)["event"] for x in (tmp_path / "s/journal.jsonl").read_text().splitlines()] == ["error"]


def test_every_journal_row_says_armed_false_and_the_state_is_not_the_mergers(tmp_path, monkeypatch):
    run_tick(tmp_path, prs_world(core=1500), monkeypatch)
    run_tick(tmp_path, prs_world(core=799), monkeypatch)
    assert rows(tmp_path) and all(r["armed"] is False and r["organ"] == "pro.localci_shepherd" for r in rows(tmp_path))
    assert sh.DEFAULT_STATE != sh.mg.DEFAULT_STATE and sh.DEFAULT_STATE.name == "shepherd" and sh.mg.DEFAULT_STATE.name == "merger"


# ------------------------------------------------------------------ the wrapper, run for real against a throw-away mirror
def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True,
                          env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


@pytest.fixture
def wrap(tmp_path):
    work, mirror = tmp_path / "work", tmp_path / "home/.nuzantara-pilots/local-ci/merger/repo.git"
    (work / "scripts/localci").mkdir(parents=True)
    (work / "scripts/lib").mkdir(parents=True)
    for f in ("shepherd.py", "merger.py", "hosted_compare.py"):
        (work / "scripts/localci" / f).write_text("import os, sys\nprint(os.environ.get('FAKE_OUT', 'status=ok fake'))\nraise SystemExit(int(os.environ.get('FAKE_RC', '0')))\n")
    (work / "scripts/lib/heartbeat.sh").write_text('echo "$1|$2|$3" >> "$HB_LOG"\n')
    git("init", "-q", "-b", "main", cwd=work)
    git("add", "-A", cwd=work)
    git("commit", "-q", "-m", "x", cwd=work)
    mirror.parent.mkdir(parents=True)
    git("clone", "-q", "--bare", str(work), str(mirror))
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path / "home"), "SHEPHERD_PYTHON": sys.executable, "SHEPHERD_NODE": "n",
           "SHEPHERD_REMOTE_URL": str(mirror), "HB_LOG": str(tmp_path / "hb.log"), "TMPDIR": str(tmp_path)}

    def run(**extra):
        res = subprocess.run(["bash", str(ROOT / "scripts/localci/localci_shepherd_tick.sh")], capture_output=True, text=True, env={**env, **extra})
        hb = (tmp_path / "hb.log").read_text().splitlines() if (tmp_path / "hb.log").exists() else []
        return res, hb
    run.mirror, run.home = mirror, tmp_path / "home"
    return run


def test_the_wrapper_borrows_the_mergers_objects_and_writes_nothing_into_its_repo(wrap):
    before = sorted(str(p.relative_to(wrap.mirror)) for p in wrap.mirror.rglob("*"))
    res, hb = wrap()
    assert res.returncode == 0, res.stderr
    state = wrap.home / ".nuzantara-pilots/local-ci/shepherd"
    assert (state / "repo.git/objects/info/alternates").read_text().strip() == str(wrap.mirror / "objects")
    assert sorted(str(p.relative_to(wrap.mirror)) for p in wrap.mirror.rglob("*")) == before   # the merger's mirror is untouched
    assert not (wrap.home / ".nuzantara-pilots/local-ci/merger/heartbeat.sh").exists()
    assert hb == ["pro.localci_shepherd|ok|tick rc=0 fake code=" + git("rev-parse", "--short=12", "main", cwd=wrap.mirror).stdout.strip()]


def test_the_wrapper_state_is_the_shepherds_own_directory_0700(wrap):
    wrap()
    state = wrap.home / ".nuzantara-pilots/local-ci/shepherd"
    assert state.is_dir() and state.stat().st_mode & 0o777 == 0o700


def test_a_skipped_quota_tick_is_a_warning_heartbeat(wrap):
    res, hb = wrap(FAKE_OUT="status=warning skipped_quota core=700 graphql=5000")
    assert res.returncode == 0 and len(hb) == 1 and hb[0].startswith("pro.localci_shepherd|warning|skipped_quota core=700")


def test_a_host_that_is_not_the_node_is_a_disabled_heartbeat(wrap):
    res, hb = wrap(FAKE_OUT="status=disabled host x is not n")
    assert res.returncode == 0 and hb == ["pro.localci_shepherd|disabled|host x is not n"]


def test_the_kill_switch_writes_a_disabled_heartbeat_and_runs_nothing(wrap):
    (wrap.home / "hb.sh").write_text('echo "$1|$2|$3" >> "$HB_LOG"\n')
    res, hb = wrap(LOCALCI_SHEPHERD_ENABLED="false", SHEPHERD_HEARTBEAT_LIB=str(wrap.home / "hb.sh"))
    assert res.returncode == 0 and hb and hb[-1].startswith("pro.localci_shepherd|disabled|kill switch") and not (wrap.home / ".nuzantara-pilots/local-ci/shepherd").exists()


def test_a_failing_tick_is_an_error_heartbeat_and_a_failing_exit(wrap):
    res, hb = wrap(FAKE_RC="1", FAKE_OUT="status=error boom")
    assert res.returncode != 0 and len(hb) == 1 and hb[0].startswith("pro.localci_shepherd|error|tick rc=")


# ------------------------------------------------------------------ gate round 1 (codex gpt-5.6-sol, 2026-10-15): the cures
def test_the_rate_limit_read_is_counted_so_a_tick_never_makes_a_61st_rest_call(tmp_path, monkeypatch):
    w = World(prs=[pr(i, author=(f"u{i}", "User")) for i in range(1, 71)], roles={})
    run_tick(tmp_path, w, monkeypatch)
    last = rows(tmp_path)[-1]
    assert len(w.all_calls) == 60 and w.all_calls[0] == "rate_limit" and len(w.rest_paths) == 59
    assert last["rest_calls"] == 60 and "budget_cap" in [r["event"] for r in rows(tmp_path)]


def test_an_arm_label_beyond_the_first_thirty_is_never_missed_and_never_a_would_label():
    thirty = [f"l{i}" for i in range(30)]
    cut = row(pr(labels=thirty, labels_total=31, author=("dependabot", "Bot")))
    assert "label_candidate" not in cut["classes"] and "labels_truncated" in cut["classes"] and "would_label" not in cut["actions"]
    seen = row(pr(labels=thirty[:29] + [sh.mg.ARM_LABEL], labels_total=31, author=("dependabot", "Bot")))
    assert seen["classes"] == [] and seen["actions"] == []   # the arm label is in the page: decided, nothing truncated that matters
    whole = row(pr(labels=thirty, labels_total=30, author=("dependabot", "Bot")))
    assert "label_candidate" in whole["classes"] and whole["actions"] == ["would_label"]


def test_a_truncated_label_set_costs_no_role_read(tmp_path, monkeypatch):
    w = World(prs=[pr(1, labels=[f"l{i}" for i in range(30)], labels_total=45, author=("bob", "User"))])
    run_tick(tmp_path, w, monkeypatch)
    assert w.rest_paths == [] and rows(tmp_path)[-1]["classes"]["labels_truncated"] == 1


def test_a_pr_in_both_classes_carries_and_journals_both_would_actions(tmp_path, monkeypatch):
    both = row(pr(author=("dependabot", "Bot")), brief())
    assert both["classes"] == ["gate_missing", "label_candidate"] and both["actions"] == ["would_gate", "would_label"]
    assert row(pr(author=("dependabot", "Bot")), brief(gate_class="fable"))["actions"] == ["would_gate_manual", "would_label"]
    assert row(pr(fork=True), brief())["actions"] == ["never_auto"] and row(pr(), role="admin")["actions"] == []
    w = World(prs=[pr(7, author=("dependabot", "Bot"), files=["evidence/2026-10/t/brief.yml"])], briefs={7: brief()})
    run_tick(tmp_path, w, monkeypatch)
    ev = [(r["event"], r.get("pr")) for r in rows(tmp_path)]
    assert ("would_gate", 7) in ev and ("would_label", 7) in ev


def test_the_wrapper_cleanup_failing_never_suppresses_the_heartbeat(wrap, tmp_path):
    fake = tmp_path / "fakebin"
    fake.mkdir()
    (fake / "rm").write_text("#!/bin/sh\nexit 1\n")
    (fake / "rm").chmod(0o755)
    res, hb = wrap(PATH=f"{fake}:{os.environ['PATH']}")
    assert res.returncode == 0 and len(hb) == 1 and hb[0].startswith("pro.localci_shepherd|ok|tick rc=0")


def test_a_wrapper_killed_while_extracting_its_heartbeat_library_leaves_no_temp_file(wrap, tmp_path):
    import shutil
    fake = tmp_path / "fakebin"
    fake.mkdir()
    real = shutil.which("git")
    (fake / "git").write_text(f'#!/bin/bash\nfor a in "$@"; do case "$a" in *:scripts/lib/heartbeat.sh) echo partial; kill -TERM $PPID; sleep 5; exit 1;; esac; done\nexec {real} "$@"\n')
    (fake / "git").chmod(0o755)
    res, hb = wrap(PATH=f"{fake}:{os.environ['PATH']}")
    state = wrap.home / ".nuzantara-pilots/local-ci/shepherd"
    assert res.returncode != 0 and not list(state.glob(".heartbeat.sh.*"))
