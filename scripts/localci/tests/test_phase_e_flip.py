"""The phase E flip against a fake ``gh``: the plan only reads, and nothing is written unless every precondition holds."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
import stat
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from scripts.localci import phase_e_flip as pef

REPO, NOW = "Bali-Zero/Teman2", datetime(2026, 10, 30, 12, 0, 0, tzinfo=timezone.utc)
_ED = b"\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20"
MERGER_PUB, OTHER_PUB = (f"ssh-ed25519 {base64.b64encode(_ED + bytes([n]) * 32).decode()}" for n in (1, 2))
# the seven classic booleans, written out here and never read from the module under test
FLAGS = ("required_linear_history", "allow_force_pushes", "allow_deletions", "block_creations",
         "required_conversation_resolution", "lock_branch", "allow_fork_syncing")


def ssh_keygen_fingerprint(pub: str) -> str:   # what `ssh-keygen -lf` prints, computed apart from the module
    return "SHA256:" + base64.b64encode(hashlib.sha256(base64.b64decode(pub.split()[1])).digest()).decode().rstrip("=")
MQ, GUARD = 19779175, 20608865


def _classic() -> dict:
    off = {"enabled": False}
    return {"url": "u", "required_status_checks": {"url": "u", "strict": False, "contexts": ["Backend Tests (Python)", "antidotes", "catE-sovereignty-lint"],
                                                   "checks": [{"context": "Backend Tests (Python)", "app_id": None},
                                                              {"context": "antidotes", "app_id": None},
                                                              {"context": "catE-sovereignty-lint", "app_id": 15368}]},
            "required_pull_request_reviews": {"url": "u", "dismiss_stale_reviews": False, "require_code_owner_reviews": False,
                                              "require_last_push_approval": False, "required_approving_review_count": 0},
            "required_signatures": {"url": "u", "enabled": False}, "enforce_admins": {"url": "u", "enabled": True},
            **{k: dict(off) for k in FLAGS}}


# the live merge_queue parameters (GET repos/Bali-Zero/Teman2/rulesets/19779175, 2026-10-10); GitHub requires all seven on PUT
MQ_PARAMS = (("check_response_timeout_minutes", 90), ("grouping_strategy", "HEADGREEN"), ("max_entries_to_build", 5),
             ("max_entries_to_merge", 4), ("merge_method", "SQUASH"), ("min_entries_to_merge", 1), ("min_entries_to_merge_wait_minutes", 2))
REQUIRED_PARAMS = {"merge_queue": {k for k, _ in MQ_PARAMS}, "update": {"update_allows_fetch_and_merge"}}


def _rulesets() -> dict:
    cond = {"ref_name": {"exclude": [], "include": ["refs/heads/main"]}}
    return {MQ: {"id": MQ, "name": "merge-queue-main", "target": "branch", "source_type": "Repository", "enforcement": "active",
                 "conditions": cond, "bypass_actors": [], "_links": {}, "node_id": "n",
                 "rules": [{"type": "merge_queue", "parameters": dict(MQ_PARAMS)}]},
            GUARD: {"id": GUARD, "name": "Copilot review for default branch", "target": "branch", "source_type": "Repository",
                    "enforcement": "active", "bypass_actors": [], "conditions": {"ref_name": {"exclude": [], "include": ["~DEFAULT_BRANCH"]}},
                    "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}, {"type": "copilot_code_review", "parameters": {}}]}}


def get_shape(body: dict) -> dict:
    """What GitHub returns for a classic protection created from a PUT body (urls aside)."""
    rsc = body["required_status_checks"]
    doc = {"enforce_admins": {"enabled": body["enforce_admins"]}, "required_signatures": {"enabled": False},
           **{k: {"enabled": body[k]} for k in FLAGS if k in body}}
    if rsc is not None:
        doc["required_status_checks"] = {"strict": rsc["strict"], "contexts": [c["context"] for c in rsc["checks"]],
                                         "checks": [{"context": c["context"], "app_id": None if c["app_id"] == -1 else c["app_id"]} for c in rsc["checks"]]}
    if body["required_pull_request_reviews"] is not None:
        doc["required_pull_request_reviews"] = dict(body["required_pull_request_reviews"])
    return doc


class FakeGH:
    def __init__(self, tmp_path):
        self.classic, self.rulesets = _classic(), _rulesets()
        self.keys = [{"id": 7, "title": "a person's name", "read_only": False, "created_at": "2026-10-29T00:00:00Z", "key": MERGER_PUB}]
        self.ignore: set[tuple[str, str]] = set()
        self.hidden_from_branch_rules: set[int] = set()   # rulesets whose rules GitHub does not apply to the branch
        self.list_omits: set[str] = set()                  # fields the rulesets list leaves out (its details keep them)
        self.after_write = None          # called after each honoured write: a peer changing GitHub mid-run
        self.answer_override: dict = {}  # (method, path) -> what GitHub answers instead of the resource
        self.calls: list[tuple[str, str, object]] = []
        self.classic_error: str | None = None
        self.pauses: list[float] = []
        self.honour_writes, self.fail = True, None
        self.state_dir = tmp_path / "state"
        self.state_files_at_first_write: list | None = None

    def __call__(self, argv, input=None, capture_output=True, text=True):
        assert argv[:2] == ["gh", "api"] and capture_output and text
        args = argv[2:]
        method, path = (args[1], args[2]) if args[0] == "--method" else ("GET", args[0])
        # the exact argv real gh needs: a GET is one path; a write is --method M path, plus --input - when it carries a body
        expected = [path] if method == "GET" else ["--method", method, path, *(["--input", "-"] if input is not None else [])]
        assert args == expected and (input is None or method != "GET"), args
        body = json.loads(input) if input is not None else None
        self.calls.append((method, path, body))
        ok = lambda doc: subprocess.CompletedProcess(argv, 0, json.dumps(doc) if doc is not None else "", "")   # noqa: E731
        if method != "GET":
            self._validate(method, path, body)
            if self.state_files_at_first_write is None:
                self.state_files_at_first_write = sorted(p.name for p in self.state_dir.glob("*")) if self.state_dir.exists() else []
            if self.fail and self.fail == (method, path):
                return subprocess.CompletedProcess(argv, 1, "", "gh: Validation Failed (HTTP 422)")
            if self.honour_writes and (method, path) not in self.ignore:
                self._write(method, path, body)
                if self.after_write:
                    self.after_write(self, method, path)
            return ok(self.answer_override.get((method, path), self._answer(method, path)))
        if path == f"repos/{REPO}/branches/main/protection":
            if self.classic_error:
                return subprocess.CompletedProcess(argv, 1, "", self.classic_error)
            return ok(self.classic) if self.classic is not None else subprocess.CompletedProcess(argv, 1, "", "gh: Branch not protected (HTTP 404)")
        if path == f"repos/{REPO}":
            return ok({"default_branch": "main"})
        if m := re.fullmatch(rf"repos/{REPO}/(rulesets|keys)\?per_page=100&page=(\d+)", path):
            items = ([{k: r[k] for k in ("id", "name", "source_type", "target", "enforcement") if k not in self.list_omits} for r in self.rulesets.values()]
                     if m.group(1) == "rulesets" else self.keys)
            page = int(m.group(2))
            return ok(items[(page - 1) * 100: page * 100])
        if m := re.fullmatch(rf"repos/{REPO}/rulesets/(\d+)", path):
            return ok(self.rulesets[int(m.group(1))])
        if m := re.fullmatch(rf"repos/{REPO}/rules/branches/main\?per_page=100&page=(\d+)", path):
            applied = [{"type": r["type"], "ruleset_id": rid, "ruleset_source_type": rs.get("source_type", "Repository"),
                        **({"parameters": r["parameters"]} if "parameters" in r else {})}
                       for rid, rs in self.rulesets.items() if rs["enforcement"] == "active" and rs["target"] == "branch"
                       and rid not in self.hidden_from_branch_rules
                       and {"refs/heads/main", "~DEFAULT_BRANCH", "~ALL"} & set(((rs.get("conditions") or {}).get("ref_name") or {}).get("include") or [])
                       for r in rs["rules"]]
            page = int(m.group(1))
            return ok(applied[(page - 1) * 100: page * 100])
        raise AssertionError(f"unexpected GET {path}")

    def _validate(self, method, path, body):
        """What GitHub's REST API refuses: an incomplete ruleset body, a rule without its required parameters, a DeployKey
        actor with an id or a pull-request mode, a classic body without its four required fields or with contexts and checks."""
        if method == "PUT" and "/rulesets/" in path:
            assert set(body) == {"name", "target", "enforcement", "conditions", "rules", "bypass_actors"}, sorted(body)
            # GitHub's schema, types and enums, for every part of the body (an int where a bool belongs passes 1 == True)
            is_int = lambda v: type(v) is int                                     # noqa: E731
            assert type(body["name"]) is str and body["target"] in {"branch", "tag", "push"}, body
            assert body["enforcement"] in {"disabled", "active", "evaluate"}, body["enforcement"]
            ref = body["conditions"]["ref_name"]
            assert all(type(x) is str for k in ("include", "exclude") for x in ref[k]), ref
            for r in body["rules"]:
                assert type(r["type"]) is str and REQUIRED_PARAMS.get(r["type"], set()) <= set(r.get("parameters") or {}), r
                prm = r.get("parameters") or {}
                if r["type"] == "merge_queue":
                    assert all(is_int(prm[k]) for k in ("check_response_timeout_minutes", "max_entries_to_build", "max_entries_to_merge",
                                                          "min_entries_to_merge", "min_entries_to_merge_wait_minutes")), prm
                    assert prm["grouping_strategy"] in {"ALLGREEN", "HEADGREEN"} and prm["merge_method"] in {"MERGE", "SQUASH", "REBASE"}, prm
                if r["type"] == "update":
                    assert type(prm["update_allows_fetch_and_merge"]) is bool, prm
            for b in body["bypass_actors"]:
                assert b["actor_type"] in {"Integration", "OrganizationAdmin", "RepositoryRole", "Team", "DeployKey"}, b
                assert b["bypass_mode"] in {"always", "pull_request", "exempt"} and (b["actor_id"] is None or is_int(b["actor_id"])), b
                assert b["actor_type"] != "DeployKey" or (b["actor_id"] is None and b["bypass_mode"] != "pull_request"), b
        if method == "PUT" and path.endswith("/protection"):
            assert {"required_status_checks", "enforce_admins", "required_pull_request_reviews", "restrictions"} <= set(body), sorted(body)
            assert not (body["required_status_checks"] or {}).get("contexts"), "contexts beside checks"
            # JSON types as GitHub's schema states them: a Python 1 == True would hide an integer where a boolean belongs
            is_bool = lambda v: type(v) is bool                                   # noqa: E731
            is_int = lambda v: type(v) is int                                     # noqa: E731
            assert body["enforce_admins"] is None or is_bool(body["enforce_admins"]), body["enforce_admins"]
            assert all(body.get(k) is None or is_bool(body[k]) for k in FLAGS), {k: body.get(k) for k in FLAGS}
            rsc = body["required_status_checks"]
            if rsc is not None:
                assert is_bool(rsc["strict"]) and all(type(c["context"]) is str and is_int(c["app_id"]) for c in rsc["checks"]), rsc
            rev = body["required_pull_request_reviews"]
            if rev is not None:
                assert is_int(rev["required_approving_review_count"]), rev
                assert all(is_bool(rev[k]) for k in ("dismiss_stale_reviews", "require_code_owner_reviews", "require_last_push_approval") if k in rev), rev
            assert body["restrictions"] is None

    def _write(self, method, path, body):
        if method == "PUT" and (m := re.fullmatch(rf"repos/{REPO}/rulesets/(\d+)", path)):
            self.rulesets[int(m.group(1))].update(copy.deepcopy(body))
        elif method == "DELETE" and path.endswith("/protection"):
            self.classic = None
        elif method == "PUT" and path.endswith("/protection"):
            self.classic = get_shape(body)
        else:
            raise AssertionError(f"unexpected write {method} {path}")

    def _answer(self, method, path):   # what GitHub answers a write with: the resource as it now stands
        if method == "DELETE":
            return None
        if m := re.fullmatch(rf"repos/{REPO}/rulesets/(\d+)", path):
            return self.rulesets[int(m.group(1))]
        return self.classic

    def writes(self):
        return [(m, p, b) for m, p, b in self.calls if m != "GET"]


@pytest.fixture
def fake(tmp_path, monkeypatch):
    fg = FakeGH(tmp_path)
    monkeypatch.setattr(pef.subprocess, "run", fg)
    monkeypatch.setattr(pef, "now", lambda: NOW)
    monkeypatch.setattr(pef, "pause", lambda s: fg.pauses.append(s))
    return fg


def report(tmp_path, **over) -> str:
    rep = {"repo": REPO, "phase_e_ready": True, "generated_at": (NOW - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "window": {"compared_merges": 52, "compared_days": 14.3}, "counts": {"FALSE_GREEN": 0},
           "context_counts": {"FALSE_GREEN": 0}, "recorded_context_false_green": 0, "phase_f": "shadow", "base": "main", "since": None}
    for k, v in over.items():
        if k in ("compared_merges", "compared_days"):
            rep["window"][k] = v
        elif k == "FALSE_GREEN":
            rep["counts"][k] = v
        else:
            rep[k] = v
    path = tmp_path / "report.json"
    path.write_text(json.dumps(rep))
    return str(path)


def run(fake, tmp_path, capsys, *extra, rep=None, pub=MERGER_PUB, quiescent=True):
    (tmp_path / "deploy_key.pub").write_text(f"{pub} localci-merger@pro\n")
    q = ["--quiescent"] if quiescent and "--apply" in extra else []   # the operator's declaration, RULED 2026-10-10
    rc = pef.main(["--report", rep or report(tmp_path), "--state-dir", str(fake.state_dir), "--key-pub", str(tmp_path / "deploy_key.pub"), *extra, *q])
    out = capsys.readouterr()
    return rc, out.out, out.err


def plan_digest(fake, tmp_path, capsys, *extra, rep=None, pub=MERGER_PUB) -> str:
    rc, out, _ = run(fake, tmp_path, capsys, *extra, rep=rep, pub=pub)
    m = re.search(r"plan digest: ([0-9a-f]{16})", out)
    assert rc == 0 and m
    return m.group(1)


def apply(fake, tmp_path, capsys, rep=None, pub=MERGER_PUB):
    dig = plan_digest(fake, tmp_path, capsys, rep=rep, pub=pub)
    return run(fake, tmp_path, capsys, "--apply", "--confirm", dig, rep=rep, pub=pub)


def test_the_plan_reads_only_with_bare_gets_and_names_both_writes_in_order(fake, tmp_path, capsys):
    rc, out, _ = run(fake, tmp_path, capsys)
    assert rc == 0 and fake.writes() == [] and not fake.state_dir.exists()
    assert "DRY RUN" in out and "state: pre-flip" in out and "blockers for --apply: none" in out
    first, second = out.index(f"1. PUT repos/{REPO}/rulesets/{MQ}"), out.index(f"2. DELETE repos/{REPO}/branches/main/protection")
    assert first < second


def test_the_plan_prints_the_live_required_set_with_each_source(fake, tmp_path, capsys):
    _, out, _ = run(fake, tmp_path, capsys)
    assert "required status checks (3, strict False):" in out
    assert "- Backend Tests (Python)  [source: any]" in out and "- catE-sovereignty-lint  [source: app 15368]" in out
    assert "pull request required (0 approvals)" in out and "'Copilot review for default branch' (id 20608865)" in out


def test_the_ruleset_write_drops_the_merge_queue_for_update_with_the_deploy_key_as_only_bypass(fake, tmp_path, capsys):
    rc, _, _ = apply(fake, tmp_path, capsys)
    assert rc == 0
    (m1, p1, b1), (m2, p2, b2) = fake.writes()
    assert (m1, p1, m2, p2, b2) == ("PUT", f"repos/{REPO}/rulesets/{MQ}", "DELETE", f"repos/{REPO}/branches/main/protection", None)
    assert b1 == {"name": "merge-queue-main", "target": "branch", "enforcement": "active",
                  "conditions": {"ref_name": {"exclude": [], "include": ["refs/heads/main"]}},
                  "rules": [{"type": "update", "parameters": {"update_allows_fetch_and_merge": False}}],
                  "bypass_actors": [{"actor_id": None, "actor_type": "DeployKey", "bypass_mode": "always"}]}
    assert fake.rulesets[GUARD]["rules"][:2] == [{"type": "deletion"}, {"type": "non_fast_forward"}]   # untouched


def test_the_flip_saves_the_state_before_its_first_write_and_reads_flipped_after(fake, tmp_path, capsys):
    rc, out, _ = apply(fake, tmp_path, capsys)
    assert rc == 0 and "flipped: the classic protection is gone" in out
    assert fake.state_files_at_first_write and fake.state_files_at_first_write[0].startswith("pre-flip-")
    saved = fake.state_dir / fake.state_files_at_first_write[0]
    assert stat.S_IMODE(saved.stat().st_mode) == 0o600 and stat.S_IMODE(fake.state_dir.stat().st_mode) == 0o700
    assert fake.classic is None and pef.phase(pef.read_state(REPO, "main")) == "flipped"


def test_the_saved_state_restores_the_exact_classic_protection_and_ruleset(fake, tmp_path, capsys):
    before_classic, before_rs = copy.deepcopy(fake.classic), pef.ruleset_body(fake.rulesets[MQ])
    apply(fake, tmp_path, capsys)
    saved = next(fake.state_dir.glob("pre-flip-*.json"))
    assert json.loads(saved.read_text())["classic"]["required_status_checks"]["checks"][0] == {"context": "Backend Tests (Python)", "app_id": -1}
    fake.calls.clear()
    dig = plan_digest(fake, tmp_path, capsys, "--rollback", str(saved))
    rc, out, _ = run(fake, tmp_path, capsys, "--rollback", str(saved), "--apply", "--confirm", dig)
    assert rc == 0 and "rolled back" in out
    assert [(m, p) for m, p, _ in fake.writes()] == [("PUT", f"repos/{REPO}/branches/main/protection"), ("PUT", f"repos/{REPO}/rulesets/{MQ}")]
    assert pef.classic_body(fake.classic) == pef.classic_body(before_classic)
    assert pef.ruleset_body(fake.rulesets[MQ]) == before_rs


def test_apply_without_the_digest_of_this_very_state_writes_nothing(fake, tmp_path, capsys):
    rc, _, err = run(fake, tmp_path, capsys, "--apply")
    assert rc == pef.EXIT_REFUSED and "--confirm does not match" in err and fake.writes() == []
    dig = plan_digest(fake, tmp_path, capsys)
    fake.keys[0]["created_at"] = "2026-10-29T09:00:00Z"   # the key was replaced after the plan was read
    rc, _, err = run(fake, tmp_path, capsys, "--apply", "--confirm", dig)
    assert rc == pef.EXIT_REFUSED and fake.writes() == [] and not fake.state_dir.exists()


@pytest.mark.parametrize("over, says", [
    ({"phase_e_ready": False}, "not READY"),
    ({"phase_e_ready": "true"}, "not READY"),
    ({"generated_at": (NOW - timedelta(hours=2, minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")}, "outside the last"),
    ({"generated_at": (NOW + timedelta(minutes=6)).strftime("%Y-%m-%dT%H:%M:%SZ")}, "outside the last"),
    ({"generated_at": None}, "no readable generated_at"),
    ({"repo": "Bali-Zero/other"}, "is for 'Bali-Zero/other'"),
    ({"compared_merges": 49}, "does not show it"),
    ({"compared_days": 13.9}, "does not show it"),
    ({"FALSE_GREEN": 1}, "does not show it"),
])
def test_a_report_that_does_not_prove_ready_now_writes_nothing(fake, tmp_path, capsys, over, says):
    rc, _, err = apply(fake, tmp_path, capsys, rep=report(tmp_path, **over))
    assert rc == pef.EXIT_REFUSED and says in err and fake.writes() == [] and not fake.state_dir.exists()


def test_an_unreadable_report_writes_nothing(fake, tmp_path, capsys):
    rc, _, err = apply(fake, tmp_path, capsys, rep=str(tmp_path / "absent.json"))
    assert rc == pef.EXIT_REFUSED and "unreadable" in err and fake.writes() == []


@pytest.mark.parametrize("keys", [
    [],
    [{"id": 7, "title": "a", "read_only": True, "created_at": "x", "key": MERGER_PUB}],
    [{"id": 7, "title": "a", "read_only": False, "created_at": "x", "key": MERGER_PUB}, {"id": 8, "title": "b", "read_only": False, "created_at": "y", "key": OTHER_PUB}],
])
def test_anything_but_exactly_one_write_deploy_key_writes_nothing(fake, tmp_path, capsys, keys):
    fake.keys = keys
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_REFUSED and "write deploy keys" in err and fake.writes() == []


@pytest.mark.parametrize("mutate", [
    lambda g: g.update(bypass_actors=[{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]),
    lambda g: g.update(enforcement="evaluate"),
    lambda g: g.update(rules=[{"type": "deletion"}]),
    lambda g: g.update(conditions={"ref_name": {"exclude": ["refs/heads/main"], "include": ["~ALL"]}}),
    lambda g: g.update(conditions={"ref_name": {"exclude": [], "include": ["refs/heads/main-old"]}}),
    lambda g: g.update(conditions={"ref_name": {"exclude": ["refs/heads/m*"], "include": ["~DEFAULT_BRANCH"]}}),
    lambda g: g.pop("bypass_actors"),   # GitHub omits it for a reader without write access: unknown is not "none"
])
def test_without_an_unbypassable_deletion_and_force_push_guard_the_flip_writes_nothing(fake, tmp_path, capsys, mutate):
    mutate(fake.rulesets[GUARD])
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_REFUSED and "forbids deletion AND force-push" in err and fake.writes() == []


def test_a_merge_queue_ruleset_that_does_not_cover_the_branch_is_refused(fake, tmp_path, capsys):
    fake.rulesets[MQ]["conditions"] = {"ref_name": {"exclude": [], "include": ["refs/heads/release"]}}
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_REFUSED and "does not cover main" in err and fake.writes() == []


def test_a_failed_second_write_exits_3_and_names_the_saved_state(fake, tmp_path, capsys):
    fake.fail = ("DELETE", f"repos/{REPO}/branches/main/protection")
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_WRITE_FAILED and "write 2/2 failed" in err and "--rollback" in err
    assert len(fake.writes()) == 2 and list(fake.state_dir.glob("pre-flip-*.json"))


def test_a_delete_that_does_not_take_fails_the_re_read_with_exit_3(fake, tmp_path, capsys):
    fake.ignore = {("DELETE", f"repos/{REPO}/branches/main/protection")}
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_WRITE_FAILED and "after write 2/2: a fresh read differs from the intended state in ['classic protection']" in err
    assert "--rollback" in err and fake.pauses == [pef.READ_DELAY_S] * (pef.READ_RETRIES - 1)   # read again before it counts


def test_an_already_flipped_branch_writes_nothing(fake, tmp_path, capsys):
    apply(fake, tmp_path, capsys)
    fake.calls.clear()
    rc, out, _ = run(fake, tmp_path, capsys, "--apply", "--confirm", "0" * 16)
    assert rc == 0 and "already flipped" in out and fake.writes() == []


def test_a_drifted_state_is_refused(fake, tmp_path, capsys):
    fake.rulesets[MQ]["rules"] = [{"type": "update", "parameters": {"update_allows_fetch_and_merge": False}}]
    rc, out, err = apply(fake, tmp_path, capsys)
    assert "state: drifted" in out and rc == pef.EXIT_REFUSED and "not pre-flip" in err and fake.writes() == []


@pytest.mark.parametrize("mutate, says", [
    (lambda c: c.update(restrictions={"users": [{"login": "x"}], "teams": [], "apps": []}), "restricts who can push"),
    (lambda c: c.update(required_signatures={"enabled": True}), "signed commits"),
    (lambda c: c["required_pull_request_reviews"].update(dismissal_restrictions={"users": [{"login": "x"}], "teams": [], "apps": []}), "dismissal_restrictions"),
    (lambda c: c["required_pull_request_reviews"].update(dismissal_restrictions={"users": [], "teams": [], "apps": []}), "dismissal_restrictions"),
    (lambda c: c["required_pull_request_reviews"].update(bypass_pull_request_allowances={"users": [], "teams": [], "apps": []}), "bypass_pull_request_allowances"),
    (lambda c: c["required_status_checks"].pop("checks"), "no `checks` list"),
])
def test_a_classic_setting_that_cannot_be_restored_is_refused_never_dropped(fake, tmp_path, capsys, mutate, says):
    mutate(fake.classic)
    rc, _, err = run(fake, tmp_path, capsys)
    assert rc == pef.EXIT_REFUSED and says in err and fake.writes() == []


def test_a_state_that_cannot_be_saved_writes_nothing(fake, tmp_path, capsys):
    fake.state_dir.write_text("a file where the directory should be")
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_REFUSED and "pre-flip state not saved" in err and fake.writes() == []


def test_rollback_refuses_a_state_of_another_repo_or_ruleset_and_a_foreign_file(fake, tmp_path, capsys):
    apply(fake, tmp_path, capsys)
    saved = next(fake.state_dir.glob("pre-flip-*.json"))
    doc = json.loads(saved.read_text())
    for name, change in (("other-repo", {"repo": "Bali-Zero/other"}), ("other-ruleset", {"ruleset_id": 1}), ("no-classic", {"classic": None})):
        (tmp_path / name).write_text(json.dumps(reseal({**doc, **change})))   # re-sealed: the checks behind the checksum
        fake.calls.clear()
        rc, out, _ = run(fake, tmp_path, capsys, "--rollback", str(tmp_path / name))   # refused before any digest exists
        assert rc == pef.EXIT_REFUSED and "plan digest" not in out and fake.writes() == [], name
    (tmp_path / "list").write_text("[1, 2]")
    rc, _, _ = run(fake, tmp_path, capsys, "--rollback", str(tmp_path / "list"))
    assert rc == pef.EXIT_REFUSED


def test_rollback_without_the_digest_of_its_plan_writes_nothing(fake, tmp_path, capsys):
    apply(fake, tmp_path, capsys)
    saved = next(fake.state_dir.glob("pre-flip-*.json"))
    fake.calls.clear()
    rc, _, err = run(fake, tmp_path, capsys, "--rollback", str(saved), "--apply", "--confirm", "0" * 16)
    assert rc == pef.EXIT_REFUSED and "--confirm does not match" in err and fake.writes() == []


@pytest.mark.parametrize("error", ["gh: Resource not accessible by integration (HTTP 403)", "gh: Bad credentials (HTTP 401)", "connection reset"])
def test_a_classic_protection_that_cannot_be_read_is_never_read_as_absent(fake, tmp_path, capsys, error):
    fake.classic_error = error
    rc, out, err = run(fake, tmp_path, capsys)
    assert rc == pef.EXIT_REFUSED and "branches/main/protection failed" in err and "absent" not in out and fake.writes() == []


def test_the_rollback_body_recreates_the_live_classic_protection_field_for_field(fake, tmp_path, capsys):
    apply(fake, tmp_path, capsys)
    body = json.loads(next(fake.state_dir.glob("pre-flip-*.json")).read_text())["classic"]
    assert body == {"required_status_checks": {"strict": False, "checks": [{"context": "Backend Tests (Python)", "app_id": -1},
                                                                          {"context": "antidotes", "app_id": -1},
                                                                          {"context": "catE-sovereignty-lint", "app_id": 15368}]},
                    "enforce_admins": True, "restrictions": None,
                    "required_pull_request_reviews": {"dismiss_stale_reviews": False, "require_code_owner_reviews": False,
                                                      "require_last_push_approval": False, "required_approving_review_count": 0},
                    **{k: False for k in FLAGS}}   # no `contexts` beside `checks`: GitHub refuses both at once


def test_a_failed_ruleset_write_sends_no_delete(fake, tmp_path, capsys):
    fake.fail = ("PUT", f"repos/{REPO}/rulesets/{MQ}")
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_WRITE_FAILED and "write 1/2 failed" in err
    assert [m for m, _, _ in fake.writes()] == ["PUT"] and fake.classic is not None


def test_a_ruleset_write_that_answers_without_taking_sends_no_delete(fake, tmp_path, capsys):
    fake.ignore = {("PUT", f"repos/{REPO}/rulesets/{MQ}")}
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_WRITE_FAILED and "did not take" in err
    assert [m for m, _, _ in fake.writes()] == ["PUT"] and fake.classic is not None


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(enforcement="evaluate"),
    lambda r: r.update(enforcement="disabled"),
    lambda r: r["rules"].append({"type": "deletion"}),
    lambda r: r["bypass_actors"].append({"actor_id": 1, "actor_type": "RepositoryRole", "bypass_mode": "always"}),
    lambda r: r.update(conditions={"ref_name": {"exclude": [], "include": ["refs/heads/release"]}}),
])
def test_a_flipped_ruleset_that_no_longer_restricts_the_branch_is_drifted_not_flipped(fake, tmp_path, capsys, mutate):
    apply(fake, tmp_path, capsys)
    mutate(fake.rulesets[MQ])
    fake.calls.clear()
    rc, out, _ = run(fake, tmp_path, capsys)
    assert "state: drifted" in out and "already flipped" not in out and fake.writes() == []


def test_a_flipped_ruleset_reads_flipped_by_meaning_not_by_spelling(fake, tmp_path, capsys):
    apply(fake, tmp_path, capsys)
    fake.rulesets[MQ]["bypass_actors"] = [{"actor_type": "DeployKey", "bypass_mode": "always"}]   # actor_id omitted on read
    rc, out, _ = run(fake, tmp_path, capsys)
    assert rc == 0 and "state: flipped" in out and "already flipped: nothing to write" in out


@pytest.mark.parametrize("mutate, says", [
    (lambda f: f.keys.append({"id": 9, "title": "x", "read_only": False, "created_at": "z", "key": OTHER_PUB}), "2 write deploy keys"),
    (lambda f: f.rulesets[GUARD].update(enforcement="disabled"), "forbids deletion AND force-push"),
])
def test_an_already_flipped_branch_that_lost_a_safety_condition_says_so_and_exits_1(fake, tmp_path, capsys, mutate, says):
    apply(fake, tmp_path, capsys)
    mutate(fake)
    fake.calls.clear()
    rc, _, err = run(fake, tmp_path, capsys)
    assert rc == pef.EXIT_REFUSED and "already flipped, but" in err and says in err and fake.writes() == []


@pytest.mark.parametrize("pub, says", [
    (OTHER_PUB, "is not the merger's"),
    ("", "unreadable"),
])
def test_the_one_write_key_must_be_the_mergers(fake, tmp_path, capsys, pub, says):
    rc, _, err = apply(fake, tmp_path, capsys, pub=pub)
    assert rc == pef.EXIT_REFUSED and says in err and fake.writes() == []


def test_a_merge_queue_ruleset_wider_than_the_branch_is_refused(fake, tmp_path, capsys):
    fake.rulesets[MQ]["conditions"] = {"ref_name": {"exclude": [], "include": ["refs/heads/main", "~ALL"]}}
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_REFUSED and "includes more than main" in err and fake.writes() == []


def test_no_key_title_or_key_material_is_printed_or_saved(fake, tmp_path, capsys):
    rc, out, err = apply(fake, tmp_path, capsys)
    saved = next(fake.state_dir.glob("pre-flip-*.json")).read_text()
    for text in (out, err, saved):
        assert "a person's name" not in text and "AAAAC3Nza" not in text
    assert ssh_keygen_fingerprint(MERGER_PUB) in out


def test_a_rollback_that_does_not_take_exits_3(fake, tmp_path, capsys):
    apply(fake, tmp_path, capsys)
    saved = next(fake.state_dir.glob("pre-flip-*.json"))
    dig = plan_digest(fake, tmp_path, capsys, "--rollback", str(saved))
    fake.calls.clear()
    fake.ignore = {("PUT", f"repos/{REPO}/rulesets/{MQ}")}   # the classic write takes, the ruleset write does not
    rc, _, err = run(fake, tmp_path, capsys, "--rollback", str(saved), "--apply", "--confirm", dig)
    assert rc == pef.EXIT_WRITE_FAILED and "write 2/2 did not take (the ruleset's answer is not as saved)" in err


def test_a_merge_queue_ruleset_in_evaluate_mode_is_flipped_to_active(fake, tmp_path, capsys):
    fake.rulesets[MQ]["enforcement"] = "evaluate"
    rc, _, _ = apply(fake, tmp_path, capsys)
    assert rc == 0 and fake.writes()[0][2]["enforcement"] == "active" and fake.rulesets[MQ]["enforcement"] == "active"


def test_a_second_write_key_on_the_second_page_is_counted(fake, tmp_path, capsys):
    fake.keys += [{"id": 100 + n, "title": "ro", "read_only": True, "created_at": "x", "key": OTHER_PUB} for n in range(99)]
    fake.keys.append({"id": 999, "title": "w2", "read_only": False, "created_at": "y", "key": OTHER_PUB})
    rc, _, err = apply(fake, tmp_path, capsys)
    assert len(fake.keys) == 101 and rc == pef.EXIT_REFUSED and "2 write deploy keys" in err and fake.writes() == []


def test_the_merge_queue_ruleset_on_the_second_page_is_found(fake, tmp_path, capsys):
    others = {1000 + n: {"id": 1000 + n, "name": f"other-{n}", "target": "tag", "source_type": "Repository", "enforcement": "active",
                         "conditions": {}, "rules": [], "bypass_actors": []} for n in range(100)}
    fake.rulesets = {**others, **fake.rulesets}
    rc, out, _ = run(fake, tmp_path, capsys)
    assert rc == 0 and "state: pre-flip" in out and f"rulesets/{MQ}" in out


def test_a_404_that_is_not_branch_not_protected_is_never_read_as_absent(fake, tmp_path, capsys):
    fake.classic_error = "gh: Not Found (HTTP 404)"
    rc, out, err = run(fake, tmp_path, capsys)
    assert rc == pef.EXIT_REFUSED and "absent" not in out and fake.writes() == []


@pytest.mark.parametrize("change, says", [
    (lambda f: f.rulesets[GUARD].update(enforcement="disabled"), "'guards'"),
    (lambda f: f.keys.append({"id": 9, "title": "x", "read_only": False, "created_at": "z", "key": OTHER_PUB}), "'write_keys'"),
    (lambda f: f.classic["required_status_checks"]["checks"].append({"context": "new-security-gate", "app_id": None}), "'classic protection'"),
    (lambda f: f.rulesets.update({77: {"id": 77, "name": "org-wide", "target": "branch", "source_type": "Organization", "enforcement": "active",
                                       "conditions": {"ref_name": {"exclude": [], "include": ["~ALL"]}}, "bypass_actors": [],
                                       "rules": [{"type": "required_signatures"}]}}), "'branch_rules'"),   # an inherited rule only
])
def test_a_guard_or_key_that_changes_after_the_ruleset_write_stops_the_delete(fake, tmp_path, capsys, change, says):
    dig = plan_digest(fake, tmp_path, capsys)
    fake.after_write = lambda f, m, p: change(f) if m == "PUT" else None
    rc, _, err = run(fake, tmp_path, capsys, "--apply", "--confirm", dig)
    assert rc == pef.EXIT_WRITE_FAILED and says in err and [m for m, _, _ in fake.writes()] == ["PUT"] and fake.classic is not None


def test_a_ruleset_answer_on_other_conditions_stops_the_delete(fake, tmp_path, capsys):
    target = {**pef.ruleset_body(fake.rulesets[MQ]), "rules": pef.TARGET_RULES, "bypass_actors": pef.TARGET_BYPASS,
              "conditions": {"ref_name": {"exclude": [], "include": ["refs/heads/other"]}}}
    fake.answer_override = {("PUT", f"repos/{REPO}/rulesets/{MQ}"): target}
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_WRITE_FAILED and "answer is not the target" in err and [m for m, _, _ in fake.writes()] == ["PUT"]


def test_a_rollback_whose_classic_write_does_not_take_never_restores_the_queue(fake, tmp_path, capsys):
    apply(fake, tmp_path, capsys)
    saved = next(fake.state_dir.glob("pre-flip-*.json"))
    dig = plan_digest(fake, tmp_path, capsys, "--rollback", str(saved))
    fake.calls.clear()
    fake.ignore = {("PUT", f"repos/{REPO}/branches/main/protection")}
    rc, _, err = run(fake, tmp_path, capsys, "--rollback", str(saved), "--apply", "--confirm", dig)
    assert rc == pef.EXIT_WRITE_FAILED and "the classic protection's answer is not as saved" in err
    assert [p for _, p, _ in fake.writes()] == [f"repos/{REPO}/branches/main/protection"]
    assert pef.is_target(fake.rulesets[MQ])   # main stays restricted to the key, never the queue without the checks


def test_a_rollback_whose_checks_come_back_in_another_order_is_still_as_saved(fake, tmp_path, capsys):
    apply(fake, tmp_path, capsys)
    saved = next(fake.state_dir.glob("pre-flip-*.json"))
    dig = plan_digest(fake, tmp_path, capsys, "--rollback", str(saved))
    def reverse(f, m, p):
        if m == "PUT" and p.endswith("/protection"):
            f.classic["required_status_checks"]["checks"].reverse()
    fake.after_write = reverse
    rc, out, _ = run(fake, tmp_path, capsys, "--rollback", str(saved), "--apply", "--confirm", dig)
    assert rc == 0 and "re-read as saved" in out


@pytest.mark.parametrize("over", [{"recorded_context_false_green": 1}, {"recorded_context_false_green": False}, {"FALSE_GREEN": False}])
def test_a_false_green_at_any_level_refuses_ready(fake, tmp_path, capsys, over):
    rc, _, err = apply(fake, tmp_path, capsys, rep=report(tmp_path, **over))
    assert rc == pef.EXIT_REFUSED and "does not show it" in err and fake.writes() == []


def test_a_false_green_among_the_contexts_refuses_ready(fake, tmp_path, capsys):
    path = report(tmp_path)
    doc = json.loads(open(path).read())
    doc["context_counts"]["FALSE_GREEN"] = 1
    open(path, "w").write(json.dumps(doc))
    rc, _, err = apply(fake, tmp_path, capsys, rep=path)
    assert rc == pef.EXIT_REFUSED and "does not show it" in err and fake.writes() == []


@pytest.mark.parametrize("text, says", [("[1, 2]", "not a JSON object"), ('{"generated_at": "2026-13-01T00:00:00Z", "repo": "Bali-Zero/Teman2"}', "is no date")])
def test_a_malformed_report_is_refused_never_raised(fake, tmp_path, capsys, text, says):
    (tmp_path / "bad.json").write_text(text)
    rc, _, err = apply(fake, tmp_path, capsys, rep=str(tmp_path / "bad.json"))
    assert rc == pef.EXIT_REFUSED and says in err and fake.writes() == []


def test_enabled_classic_flags_are_saved_and_restored(fake, tmp_path, capsys):
    fake.classic["required_conversation_resolution"] = {"enabled": True}
    fake.classic["required_linear_history"] = {"enabled": True}
    apply(fake, tmp_path, capsys)
    saved = next(fake.state_dir.glob("pre-flip-*.json"))
    body = json.loads(saved.read_text())["classic"]
    assert body["required_conversation_resolution"] is True and body["required_linear_history"] is True
    assert sorted(k for k in body if k in FLAGS) == sorted(FLAGS)
    dig = plan_digest(fake, tmp_path, capsys, "--rollback", str(saved))
    rc, _, _ = run(fake, tmp_path, capsys, "--rollback", str(saved), "--apply", "--confirm", dig)
    assert rc == 0 and fake.classic["required_conversation_resolution"] == {"enabled": True}


def test_an_already_flipped_ruleset_widened_beyond_the_branch_says_so(fake, tmp_path, capsys):
    apply(fake, tmp_path, capsys)
    fake.rulesets[MQ]["conditions"] = {"ref_name": {"exclude": [], "include": ["refs/heads/main", "~ALL"]}}
    rc, _, err = run(fake, tmp_path, capsys)
    assert rc == pef.EXIT_REFUSED and "already flipped, but" in err and "includes more than main" in err


def test_a_ruleset_answer_that_the_re_read_does_not_confirm_stops_the_delete(fake, tmp_path, capsys):
    path = f"repos/{REPO}/rulesets/{MQ}"
    target = {**pef.ruleset_body(fake.rulesets[MQ]), "rules": pef.TARGET_RULES, "bypass_actors": pef.TARGET_BYPASS}
    fake.ignore, fake.answer_override = {("PUT", path)}, {("PUT", path): target}   # the answer says target, GitHub kept the queue
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_WRITE_FAILED and "after write 1/2: a fresh read differs" in err and [m for m, _, _ in fake.writes()] == ["PUT"]


def test_a_key_added_after_the_delete_fails_the_final_re_read(fake, tmp_path, capsys):
    dig = plan_digest(fake, tmp_path, capsys)
    def add_key(f, m, p):
        if m == "DELETE":
            f.keys.append({"id": 9, "title": "x", "read_only": False, "created_at": "z", "key": OTHER_PUB})
    fake.after_write = add_key
    rc, _, err = run(fake, tmp_path, capsys, "--apply", "--confirm", dig)
    assert rc == pef.EXIT_WRITE_FAILED and "after write 2/2: a fresh read differs" in err and "'write_keys'" in err


def test_a_rollback_whose_classic_protection_vanishes_after_its_write_never_restores_the_queue(fake, tmp_path, capsys):
    apply(fake, tmp_path, capsys)
    saved = next(fake.state_dir.glob("pre-flip-*.json"))
    dig = plan_digest(fake, tmp_path, capsys, "--rollback", str(saved))
    fake.calls.clear()
    def vanish(f, m, p):   # GitHub answers the classic write as saved, then a peer deletes it
        if m == "PUT" and p.endswith("/protection"):
            f.answer_override = {("PUT", p): copy.deepcopy(f.classic)}
            f.classic = None
    fake.after_write = vanish
    rc, _, err = run(fake, tmp_path, capsys, "--rollback", str(saved), "--apply", "--confirm", dig)
    assert rc == pef.EXIT_WRITE_FAILED and "after write 1/2: a fresh read differs" in err
    assert [p for _, p, _ in fake.writes()] == [f"repos/{REPO}/branches/main/protection"] and pef.is_target(fake.rulesets[MQ])


@pytest.mark.parametrize("rule", ["update", "pull_request", "required_status_checks", "required_signatures", "required_linear_history", "creation_of_something_new"])
def test_a_rule_beside_the_ruleset_that_would_stop_the_key_refuses_the_flip(fake, tmp_path, capsys, rule):
    fake.rulesets[GUARD]["rules"].append({"type": rule})
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_REFUSED and "would also stop the merger's push" in err and f"{rule} (ruleset {GUARD})" in err and fake.writes() == []


def test_an_inherited_rule_beside_the_ruleset_refuses_the_flip(fake, tmp_path, capsys):
    fake.rulesets[77] = {"id": 77, "name": "org-wide", "target": "branch", "source_type": "Organization", "enforcement": "active",
                         "conditions": {"ref_name": {"exclude": [], "include": ["~ALL"]}}, "bypass_actors": [],
                         "rules": [{"type": "required_signatures"}]}
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_REFUSED and "required_signatures (ruleset 77)" in err and fake.writes() == []


@pytest.mark.parametrize("over, says", [
    ({"base": "release"}, "judged base 'release'"),
    ({"base": None}, "judged base None"),
    ({"since": "2026-10-20"}, "cut at since='2026-10-20'"),
])
def test_ready_must_be_the_branchs_and_the_whole_journals(fake, tmp_path, capsys, over, says):
    rc, _, err = apply(fake, tmp_path, capsys, rep=report(tmp_path, **over))
    assert rc == pef.EXIT_REFUSED and says in err and fake.writes() == []


@pytest.mark.parametrize("days, says", [("Infinity", "non-standard JSON constant Infinity"), ("NaN", "non-standard JSON constant NaN"),
                                        ("1e400", "does not show it")])   # 1e400 is standard JSON that parses to inf
def test_a_non_finite_window_is_refused(fake, tmp_path, capsys, days, says):
    path = report(tmp_path)
    text = open(path).read().replace('"compared_days": 14.3', f'"compared_days": {days}')
    assert days in text
    open(path, "w").write(text)
    rc, _, err = apply(fake, tmp_path, capsys, rep=path)
    assert rc == pef.EXIT_REFUSED and says in err and fake.writes() == []


def test_a_target_ruleset_read_back_in_another_spelling_still_lets_the_flip_finish(fake, tmp_path, capsys):
    def respell(f, m, p):   # GitHub may read the bypass actor back without its null actor_id
        if m == "PUT" and "/rulesets/" in p:
            f.rulesets[MQ]["bypass_actors"] = [{"actor_type": "DeployKey", "bypass_mode": "always"}]
    fake.after_write = respell
    rc, out, _ = apply(fake, tmp_path, capsys)
    assert rc == 0 and "flipped:" in out


def test_an_unexpected_error_after_the_first_write_is_exit_3_with_the_rollback(fake, tmp_path, capsys, monkeypatch):
    dig = plan_digest(fake, tmp_path, capsys)
    real = pef.read_state
    calls = {"n": 0}
    def broken(repo, branch):
        calls["n"] += 1
        if calls["n"] > 2:   # the plan's read and W1's read before write 1 pass; W5's read after it breaks
            raise KeyError("ruleset_id")
        return real(repo, branch)
    monkeypatch.setattr(pef, "read_state", broken)
    rc, _, err = run(fake, tmp_path, capsys, "--apply", "--confirm", dig)
    assert rc == pef.EXIT_WRITE_FAILED and "KeyError" in err and "--rollback" in err and [m for m, _, _ in fake.writes()] == ["PUT"]


def test_a_key_whose_read_only_is_unknown_counts_as_a_write_key(fake, tmp_path, capsys):
    fake.keys.append({"id": 9, "title": "x", "created_at": "z", "key": OTHER_PUB})
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_REFUSED and "2 write deploy keys" in err


@pytest.mark.parametrize("mutate", [
    lambda c: c["required_status_checks"].update(strict=True),
    lambda c: c.update(enforce_admins={"enabled": False}),
])
def test_other_classic_values_are_saved_as_they_are(fake, tmp_path, capsys, mutate):
    mutate(fake.classic)
    expected = {"strict": fake.classic["required_status_checks"]["strict"], "enforce_admins": fake.classic["enforce_admins"]["enabled"]}
    apply(fake, tmp_path, capsys)
    body = json.loads(next(fake.state_dir.glob("pre-flip-*.json")).read_text())["classic"]
    assert {"strict": body["required_status_checks"]["strict"], "enforce_admins": body["enforce_admins"]} == expected


def test_a_branch_that_is_not_the_default_is_covered_only_by_its_own_name(fake, tmp_path, capsys):
    rs = pef.ruleset_body(fake.rulesets[GUARD])   # the guard names ~DEFAULT_BRANCH: it covers main, never a release branch
    assert pef.covers(rs, "main", "main") and not pef.covers(rs, "release", "main")


def test_a_merge_queue_ruleset_that_also_forbids_deletion_is_not_its_own_guard(fake, tmp_path, capsys):
    fake.rulesets[MQ]["rules"] += [{"type": "deletion"}, {"type": "non_fast_forward"}]
    del fake.rulesets[GUARD]
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_REFUSED and "forbids deletion AND force-push" in err and fake.writes() == []


def test_apply_without_the_quiescence_declaration_writes_nothing(fake, tmp_path, capsys):
    dig = plan_digest(fake, tmp_path, capsys)
    rc, out, err = run(fake, tmp_path, capsys, "--apply", "--confirm", dig, quiescent=False)
    assert rc == pef.EXIT_REFUSED and "--quiescent" in err and "RULED 2026-10-10" in err and fake.writes() == []
    assert not fake.state_dir.exists()


def test_the_plan_states_the_quiescence_precondition(fake, tmp_path, capsys):
    _, out, _ = run(fake, tmp_path, capsys)
    assert "no session, peer or cron writes rulesets or branch protection" in out


@pytest.mark.parametrize("change, says", [
    (lambda f: f.rulesets[MQ]["conditions"]["ref_name"]["include"].append("refs/heads/release"), "ruleset 'merge-queue-main'"),
    (lambda f: f.keys.append({"id": 9, "title": "x", "read_only": False, "created_at": "z", "key": OTHER_PUB}), "'write_keys'"),
    (lambda f: f.classic["required_status_checks"]["checks"].append({"context": "late", "app_id": None}), "'classic protection'"),
])
def test_a_change_between_the_plan_and_the_first_write_writes_nothing(fake, tmp_path, capsys, monkeypatch, change, says):
    dig = plan_digest(fake, tmp_path, capsys)
    real_save = pef.save_state
    def save_then_change(*args):   # a peer writes while the state file is being saved: W1 reads again before write 1
        path = real_save(*args)
        change(fake)
        return path
    monkeypatch.setattr(pef, "save_state", save_then_change)
    rc, _, err = run(fake, tmp_path, capsys, "--apply", "--confirm", dig)
    assert rc == pef.EXIT_REFUSED and "before write 1/2: changed since plan" in err and says in err
    assert "nothing was written" in err and fake.writes() == []


def test_a_rollback_whose_state_changes_before_its_first_write_writes_nothing(fake, tmp_path, capsys, monkeypatch):
    apply(fake, tmp_path, capsys)
    saved = next(fake.state_dir.glob("pre-flip-*.json"))
    dig = plan_digest(fake, tmp_path, capsys, "--rollback", str(saved))
    fake.calls.clear()
    real_read = pef.read_state
    calls = {"n": 0}
    def read_then_change(repo, branch):
        calls["n"] += 1
        if calls["n"] == 2:   # the rollback's plan read is 1; before W1's read a peer adds a key
            fake.keys.append({"id": 9, "title": "x", "read_only": False, "created_at": "z", "key": OTHER_PUB})
        return real_read(repo, branch)
    monkeypatch.setattr(pef, "read_state", read_then_change)
    rc, _, err = run(fake, tmp_path, capsys, "--rollback", str(saved), "--apply", "--confirm", dig)
    assert rc == pef.EXIT_REFUSED and "before write 1/2: changed since plan" in err and fake.writes() == []


def test_an_error_on_the_read_before_the_first_write_writes_nothing(fake, tmp_path, capsys, monkeypatch):
    dig = plan_digest(fake, tmp_path, capsys)
    real = pef.read_state
    calls = {"n": 0}
    def broken(repo, branch):
        calls["n"] += 1
        if calls["n"] == 2:
            raise pef.FlipError("gh api repos/x failed (rc=1): HTTP 502")
        return real(repo, branch)
    monkeypatch.setattr(pef, "read_state", broken)
    rc, _, err = run(fake, tmp_path, capsys, "--apply", "--confirm", dig)
    assert rc == pef.EXIT_REFUSED and "could not be read again" in err and fake.writes() == []


def test_a_read_that_fails_once_after_a_write_is_read_again(fake, tmp_path, capsys, monkeypatch):
    dig = plan_digest(fake, tmp_path, capsys)
    real = pef.read_state
    calls = {"n": 0}
    def flaky(repo, branch):
        calls["n"] += 1
        if calls["n"] == 3:   # W5's first read after write 1 fails once
            raise pef.FlipError("gh api repos/x failed (rc=1): HTTP 502")
        return real(repo, branch)
    monkeypatch.setattr(pef, "read_state", flaky)
    rc, out, _ = run(fake, tmp_path, capsys, "--apply", "--confirm", dig)
    assert rc == 0 and "flipped:" in out and fake.pauses == [pef.READ_DELAY_S]


def test_ctrl_c_after_the_first_write_is_exit_3_with_the_rollback(fake, tmp_path, capsys, monkeypatch):
    dig = plan_digest(fake, tmp_path, capsys)
    def interrupt(f, m, p):
        if m == "PUT":
            raise KeyboardInterrupt
    fake.after_write = interrupt
    try:
        rc, _, err = run(fake, tmp_path, capsys, "--apply", "--confirm", dig)
    except KeyboardInterrupt:   # caught here so an escape fails this test instead of interrupting pytest
        pytest.fail("Ctrl-C after the first write escaped W4")
    assert rc == pef.EXIT_WRITE_FAILED and "KeyboardInterrupt" in err and "--rollback" in err and "--repo Bali-Zero/Teman2 --branch main" in err


def test_a_guard_that_github_does_not_apply_to_the_branch_is_no_guard(fake, tmp_path, capsys):
    fake.hidden_from_branch_rules = {GUARD}
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_REFUSED and "as GitHub applies it" in err and fake.writes() == []


def test_a_rulesets_list_without_target_is_read_through_the_details(fake, tmp_path, capsys):
    fake.list_omits = {"target"}
    rc, out, _ = run(fake, tmp_path, capsys)
    assert rc == 0 and "state: pre-flip" in out and "blockers for --apply: none" in out


def test_the_rollback_ruleset_body_is_the_live_one_field_for_field(fake, tmp_path, capsys):
    apply(fake, tmp_path, capsys)
    saved = next(fake.state_dir.glob("pre-flip-*.json"))
    dig = plan_digest(fake, tmp_path, capsys, "--rollback", str(saved))
    fake.calls.clear()
    run(fake, tmp_path, capsys, "--rollback", str(saved), "--apply", "--confirm", dig)
    body = [b for m, p, b in fake.writes() if "/rulesets/" in p][0]
    assert body == {"name": "merge-queue-main", "target": "branch", "enforcement": "active", "bypass_actors": [],
                    "conditions": {"ref_name": {"exclude": [], "include": ["refs/heads/main"]}},
                    "rules": [{"type": "merge_queue", "parameters": dict(MQ_PARAMS)}]}   # written out here, never from the module


def test_a_key_swapped_for_a_foreign_one_after_the_ruleset_write_stops_the_delete(fake, tmp_path, capsys):
    dig = plan_digest(fake, tmp_path, capsys)
    def swap(f, m, p):
        if m == "PUT":
            f.keys[0]["key"] = OTHER_PUB
    fake.after_write = swap
    rc, _, err = run(fake, tmp_path, capsys, "--apply", "--confirm", dig)
    assert rc == pef.EXIT_WRITE_FAILED and "'write_keys'" in err and [m for m, _, _ in fake.writes()] == ["PUT"]


def test_a_saved_ruleset_in_evaluate_mode_rolls_back(fake, tmp_path, capsys):
    fake.rulesets[MQ]["enforcement"] = "evaluate"
    apply(fake, tmp_path, capsys)
    saved = next(fake.state_dir.glob("pre-flip-*.json"))
    assert json.loads(saved.read_text())["ruleset"]["enforcement"] == "evaluate"
    dig = plan_digest(fake, tmp_path, capsys, "--rollback", str(saved))
    rc, out, _ = run(fake, tmp_path, capsys, "--rollback", str(saved), "--apply", "--confirm", dig)
    assert rc == 0 and fake.rulesets[MQ]["enforcement"] == "evaluate"


def test_a_target_read_back_on_pull_requests_only_is_not_the_target(fake, tmp_path, capsys):
    dig = plan_digest(fake, tmp_path, capsys)
    def weaken(f, m, p):   # the answer reads as the target; the ruleset GitHub keeps bypasses on pull requests only
        if m == "PUT" and "/rulesets/" in p:
            f.answer_override = {(m, p): copy.deepcopy(f.rulesets[MQ])}
            f.rulesets[MQ]["bypass_actors"] = [{"actor_id": None, "actor_type": "DeployKey", "bypass_mode": "pull_request"}]
    fake.after_write = weaken
    rc, _, err = run(fake, tmp_path, capsys, "--apply", "--confirm", dig)
    assert rc == pef.EXIT_WRITE_FAILED and "after write 1/2" in err and [m for m, _, _ in fake.writes()] == ["PUT"]


def test_a_report_without_a_since_key_is_refused(fake, tmp_path, capsys):
    path = report(tmp_path)
    doc = json.loads(open(path).read())
    del doc["since"]
    open(path, "w").write(json.dumps(doc))
    rc, _, err = apply(fake, tmp_path, capsys, rep=path)
    assert rc == pef.EXIT_REFUSED and "carries no `since`" in err and fake.writes() == []


def test_a_huge_integer_window_is_read_without_a_crash(fake, tmp_path, capsys):
    path = report(tmp_path)
    text = open(path).read().replace('"compared_days": 14.3', '"compared_days": ' + "1" + "0" * 400)
    assert "0" * 400 in text
    open(path, "w").write(text)
    rc, out, _ = run(fake, tmp_path, capsys, rep=path)
    assert rc == 0 and "compared_days 1" + "0" * 400 in out and "blockers for --apply: none" in out


def test_a_parameter_of_an_inherited_rule_changed_before_the_first_write_writes_nothing(fake, tmp_path, capsys, monkeypatch):
    fake.rulesets[88] = {"id": 88, "name": "org-copilot", "target": "branch", "source_type": "Organization", "enforcement": "active",
                         "conditions": {"ref_name": {"exclude": [], "include": ["~ALL"]}}, "bypass_actors": [],
                         "rules": [{"type": "copilot_code_review", "parameters": {"review_on_push": False}}]}
    dig = plan_digest(fake, tmp_path, capsys)
    real_save = pef.save_state
    def save_then_change(*args):
        path = real_save(*args)
        fake.rulesets[88]["rules"][0]["parameters"]["review_on_push"] = True
        return path
    monkeypatch.setattr(pef, "save_state", save_then_change)
    rc, _, err = run(fake, tmp_path, capsys, "--apply", "--confirm", dig)
    assert rc == pef.EXIT_REFUSED and "changed since plan" in err and "'branch_rules'" in err and fake.writes() == []


def reseal(doc: dict) -> dict:
    """A deliberately re-sealed state file: sha256 of canonical JSON without the checksum, computed here, not by the module."""
    body = {k: v for k, v in doc.items() if k != "checksum"}
    return {**body, "checksum": hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def flipped_with_saved(fake, tmp_path, capsys):
    apply(fake, tmp_path, capsys)
    saved = next(fake.state_dir.glob("pre-flip-*.json"))
    return saved, plan_digest(fake, tmp_path, capsys, "--rollback", str(saved))


def test_a_rollback_without_the_quiescence_declaration_writes_nothing(fake, tmp_path, capsys):
    saved, dig = flipped_with_saved(fake, tmp_path, capsys)
    fake.calls.clear()
    rc, _, err = run(fake, tmp_path, capsys, "--rollback", str(saved), "--apply", "--confirm", dig, quiescent=False)
    assert rc == pef.EXIT_REFUSED and "--quiescent" in err and fake.writes() == []


def test_ctrl_c_after_the_rollbacks_first_write_is_exit_3_with_the_state_file(fake, tmp_path, capsys):
    saved, dig = flipped_with_saved(fake, tmp_path, capsys)
    fake.calls.clear()
    def interrupt(f, m, p):
        if m == "PUT":
            raise KeyboardInterrupt
    fake.after_write = interrupt
    try:
        rc, _, err = run(fake, tmp_path, capsys, "--rollback", str(saved), "--apply", "--confirm", dig)
    except KeyboardInterrupt:
        pytest.fail("Ctrl-C after the rollback's first write escaped W4")
    assert rc == pef.EXIT_WRITE_FAILED and "KeyboardInterrupt" in err and [m for m, _, _ in fake.writes()] == ["PUT"]
    assert str(saved) in err and "--repo Bali-Zero/Teman2 --branch main --rollback" in err and "--quiescent" in err


@pytest.mark.parametrize("damage, says", [
    (lambda d: d["ruleset"].pop("rules"), "lacks ['rules']"),
    (lambda d: d["ruleset"].update(rules="update"), "not a whole ruleset body"),
    (lambda d: d["ruleset"].update(extra=1), "not a whole ruleset body"),
    (lambda d: d["classic"].pop("restrictions"), "lacks ['restrictions']"),
])
def test_a_hand_edited_state_file_is_refused_before_any_write(fake, tmp_path, capsys, damage, says):
    apply(fake, tmp_path, capsys)
    saved = next(fake.state_dir.glob("pre-flip-*.json"))
    doc = json.loads(saved.read_text())
    damage(doc)
    edited = tmp_path / "edited.json"
    edited.write_text(json.dumps(reseal(doc)))   # re-sealed, so the shape checks behind the checksum are what refuses
    fake.calls.clear()
    rc, out, err = run(fake, tmp_path, capsys, "--rollback", str(edited))   # the plan itself refuses: no digest to confirm
    assert rc == pef.EXIT_REFUSED and says in err and "plan digest" not in out
    live = pef.read_state("Bali-Zero/Teman2", "main")
    dig = pef.digest(live, pef.rollback_writes(doc))   # the digest an unchecked plan would have printed
    rc, _, err = run(fake, tmp_path, capsys, "--rollback", str(edited), "--apply", "--confirm", dig)
    assert rc == pef.EXIT_REFUSED and says in err and fake.writes() == []


def test_a_ruleset_recreated_under_a_new_id_before_the_first_write_writes_nothing(fake, tmp_path, capsys, monkeypatch):
    fake.rulesets[MQ]["enforcement"] = "evaluate"   # no rule applied to the branch: only the id tells the two apart
    dig = plan_digest(fake, tmp_path, capsys)
    real_save = pef.save_state
    def save_then_recreate(*args):
        path = real_save(*args)
        rs = fake.rulesets.pop(MQ)
        fake.rulesets[777] = {**rs, "id": 777}
        return path
    monkeypatch.setattr(pef, "save_state", save_then_recreate)
    rc, _, err = run(fake, tmp_path, capsys, "--apply", "--confirm", dig)
    assert rc == pef.EXIT_REFUSED and "before write 1/2: changed since plan" in err and fake.writes() == []


@pytest.mark.parametrize("edit", [
    lambda d: d["ruleset"]["rules"][0].pop("parameters"),                      # Codex round 6: passed the shape checks
    lambda d: d["classic"].pop("required_linear_history", None) or d["classic"].update(enforce_admins=False),
    lambda d: d["ruleset"].update(conditions="refs/heads/main"),               # Opus round 6: AttributeError at the plan
    lambda d: d.update(saved_at="2020-01-01T00:00:00Z"),
    lambda d: d.pop("checksum"),
])
def test_a_state_file_edited_since_the_flip_saved_it_is_refused_before_any_plan(fake, tmp_path, capsys, edit):
    apply(fake, tmp_path, capsys)
    saved = next(fake.state_dir.glob("pre-flip-*.json"))
    doc = json.loads(saved.read_text())
    edit(doc)
    edited = tmp_path / "edited.json"
    edited.write_text(json.dumps(doc))
    fake.calls.clear()
    rc, out, err = run(fake, tmp_path, capsys, "--rollback", str(edited))
    assert rc == pef.EXIT_REFUSED and "its checksum does not match its content" in err and "plan digest" not in out
    assert fake.writes() == []


def test_the_flip_seals_the_state_it_saves(fake, tmp_path, capsys):
    apply(fake, tmp_path, capsys)
    doc = json.loads(next(fake.state_dir.glob("pre-flip-*.json")).read_text())
    assert doc["checksum"] == reseal(doc)["checksum"] and len(doc["checksum"]) == 64


def test_a_key_file_that_is_not_text_is_no_key(fake, tmp_path, capsys):
    run(fake, tmp_path, capsys)   # writes deploy_key.pub; overwrite it with a non-UTF-8 byte
    (tmp_path / "deploy_key.pub").write_bytes(b"\xff\xfe not a key\n")
    rc, out, err = pef.main(["--report", report(tmp_path), "--state-dir", str(fake.state_dir), "--key-pub", str(tmp_path / "deploy_key.pub")]), *capsys.readouterr()
    assert rc == 0 and "merger key (--key-pub): unreadable" in out and "Traceback" not in err


def test_an_error_before_any_write_is_refused_without_a_traceback(fake, tmp_path, capsys, monkeypatch):
    def no_gh(*a, **k):
        raise FileNotFoundError("gh")
    monkeypatch.setattr(pef.subprocess, "run", no_gh)
    rc, _, err = run(fake, tmp_path, capsys)
    assert rc == pef.EXIT_REFUSED and "REFUSED: FileNotFoundError" in err and "nothing was written" in err


def test_a_parameter_of_the_wrong_json_type_never_reaches_github(fake, tmp_path, capsys):
    fake.rulesets[MQ]["rules"][0]["parameters"]["min_entries_to_merge"] = True   # what a bool-for-int bug would send
    apply(fake, tmp_path, capsys)
    saved = next(fake.state_dir.glob("pre-flip-*.json"))
    dig = plan_digest(fake, tmp_path, capsys, "--rollback", str(saved))
    fake.calls.clear()
    rc, _, err = run(fake, tmp_path, capsys, "--rollback", str(saved), "--apply", "--confirm", dig)
    # the fake refuses the ruleset PUT as GitHub's schema would (an AssertionError from the fake gh, owned by W4: exit 3)
    assert rc == pef.EXIT_WRITE_FAILED and "FAILED: AssertionError" in err
    assert [p for m, p, _ in fake.writes()] == ["repos/Bali-Zero/Teman2/branches/main/protection", "repos/Bali-Zero/Teman2/rulesets/19779175"]
    assert fake.rulesets[MQ]["rules"][0]["type"] == "update"   # refused: the ruleset is still the key-only one
