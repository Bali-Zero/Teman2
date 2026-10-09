"""The phase E flip against a fake ``gh``: the plan only reads, and nothing is written unless every precondition holds."""
from __future__ import annotations

import copy
import json
import re
import stat
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from scripts.localci import phase_e_flip as pef

REPO, NOW = "Bali-Zero/Teman2", datetime(2026, 10, 30, 12, 0, 0, tzinfo=timezone.utc)
MERGER_PUB, OTHER_PUB = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAImerger", "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIother"
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
            **{k: dict(off) for k in pef.CLASSIC_FLAGS}}


def _rulesets() -> dict:
    cond = {"ref_name": {"exclude": [], "include": ["refs/heads/main"]}}
    return {MQ: {"id": MQ, "name": "merge-queue-main", "target": "branch", "source_type": "Repository", "enforcement": "active",
                 "conditions": cond, "bypass_actors": [], "_links": {}, "node_id": "n",
                 "rules": [{"type": "merge_queue", "parameters": {"merge_method": "SQUASH", "grouping_strategy": "HEADGREEN",
                                                                  "check_response_timeout_minutes": 90}}]},
            GUARD: {"id": GUARD, "name": "Copilot review for default branch", "target": "branch", "source_type": "Repository",
                    "enforcement": "active", "bypass_actors": [], "conditions": {"ref_name": {"exclude": [], "include": ["~DEFAULT_BRANCH"]}},
                    "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}, {"type": "copilot_code_review", "parameters": {}}]}}


def get_shape(body: dict) -> dict:
    """What GitHub returns for a classic protection created from a PUT body (urls aside)."""
    rsc = body["required_status_checks"]
    doc = {"enforce_admins": {"enabled": body["enforce_admins"]}, "required_signatures": {"enabled": False},
           **{k: {"enabled": body[k]} for k in pef.CLASSIC_FLAGS}}
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
        self.calls: list[tuple[str, str, object]] = []
        self.classic_error: str | None = None
        self.honour_writes, self.fail = True, None
        self.state_dir = tmp_path / "state"
        self.state_files_at_first_write: list | None = None

    def __call__(self, argv, input=None, capture_output=True, text=True):
        assert argv[:2] == ["gh", "api"] and capture_output and text
        args = argv[2:]
        method, path = (args[1], args[2]) if args[0] == "--method" else ("GET", args[0])
        assert len(args) == (1 if method == "GET" else (5 if input is not None else 3)), args
        body = json.loads(input) if input is not None else None
        self.calls.append((method, path, body))
        ok = lambda doc: subprocess.CompletedProcess(argv, 0, json.dumps(doc) if doc is not None else "", "")   # noqa: E731
        if method != "GET":
            if self.state_files_at_first_write is None:
                self.state_files_at_first_write = sorted(p.name for p in self.state_dir.glob("*")) if self.state_dir.exists() else []
            if self.fail and self.fail == (method, path):
                return subprocess.CompletedProcess(argv, 1, "", "gh: Validation Failed (HTTP 422)")
            if self.honour_writes and (method, path) not in self.ignore:
                self._write(method, path, body)
            return ok(self._answer(method, path))
        if path == f"repos/{REPO}/branches/main/protection":
            if self.classic_error:
                return subprocess.CompletedProcess(argv, 1, "", self.classic_error)
            return ok(self.classic) if self.classic is not None else subprocess.CompletedProcess(argv, 1, "", "gh: Branch not protected (HTTP 404)")
        if path == f"repos/{REPO}":
            return ok({"default_branch": "main"})
        if path == f"repos/{REPO}/rulesets?per_page=100":
            return ok([{k: r[k] for k in ("id", "name", "source_type", "target", "enforcement")} for r in self.rulesets.values()])
        if m := re.fullmatch(rf"repos/{REPO}/rulesets/(\d+)", path):
            return ok(self.rulesets[int(m.group(1))])
        if path == f"repos/{REPO}/keys?per_page=100":
            return ok(self.keys)
        raise AssertionError(f"unexpected GET {path}")

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
    return fg


def report(tmp_path, **over) -> str:
    rep = {"repo": REPO, "phase_e_ready": True, "generated_at": (NOW - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "window": {"compared_merges": 52, "compared_days": 14.3}, "counts": {"FALSE_GREEN": 0}, "phase_f": "shadow"}
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


def run(fake, tmp_path, capsys, *extra, rep=None, pub=MERGER_PUB):
    (tmp_path / "deploy_key.pub").write_text(f"{pub} localci-merger@pro\n")
    rc = pef.main(["--report", rep or report(tmp_path), "--state-dir", str(fake.state_dir), "--key-pub", str(tmp_path / "deploy_key.pub"), *extra])
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
    assert rc == pef.EXIT_WRITE_FAILED and "says drifted, not flipped" in err and "--rollback" in err


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
        (tmp_path / name).write_text(json.dumps({**doc, **change}))
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
                    **{k: False for k in pef.CLASSIC_FLAGS}}   # no `contexts` beside `checks`: GitHub refuses both at once


def test_a_failed_ruleset_write_sends_no_delete(fake, tmp_path, capsys):
    fake.fail = ("PUT", f"repos/{REPO}/rulesets/{MQ}")
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_WRITE_FAILED and "write 1/2 failed" in err
    assert [m for m, _, _ in fake.writes()] == ["PUT"] and fake.classic is not None


def test_a_ruleset_write_that_answers_without_taking_sends_no_delete(fake, tmp_path, capsys):
    fake.ignore = {("PUT", f"repos/{REPO}/rulesets/{MQ}")}
    rc, _, err = apply(fake, tmp_path, capsys)
    assert rc == pef.EXIT_WRITE_FAILED and "answered without taking" in err
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
    assert pef.key_fingerprint(MERGER_PUB) in out


def test_a_rollback_that_does_not_take_exits_3(fake, tmp_path, capsys):
    apply(fake, tmp_path, capsys)
    saved = next(fake.state_dir.glob("pre-flip-*.json"))
    dig = plan_digest(fake, tmp_path, capsys, "--rollback", str(saved))
    fake.calls.clear()
    fake.honour_writes = False
    rc, _, err = run(fake, tmp_path, capsys, "--rollback", str(saved), "--apply", "--confirm", dig)
    assert rc == pef.EXIT_WRITE_FAILED and "differs from the saved state" in err


def test_a_merge_queue_ruleset_in_evaluate_mode_is_flipped_to_active(fake, tmp_path, capsys):
    fake.rulesets[MQ]["enforcement"] = "evaluate"
    rc, _, _ = apply(fake, tmp_path, capsys)
    assert rc == 0 and fake.writes()[0][2]["enforcement"] == "active" and fake.rulesets[MQ]["enforcement"] == "active"
