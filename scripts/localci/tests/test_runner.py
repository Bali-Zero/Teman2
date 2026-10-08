"""Runner gate behaviour with the REAL gate code against a real temporary git repo."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from . import fixture_repo as fr
from .fixture_repo import PY, cmd_check, git, pytest_check, runner

pytestmark = pytest.mark.usefixtures("fake_env")


def checks(s):
    return {n: v["status"] for n, v in s["checks"].items()}


# --------------------------------------------------------------- plan / happy path
def test_plan_binds_identity_and_seats(fx):
    fr.plan(fx)
    st, plan = fr.load_state(fx), json.loads((fx["run"] / "state" / "plan.json").read_text())
    assert st["binding"] == {"candidate_sha": fx["candidate"], "tree_sha": fx["tree"], "base_sha": fx["base"], "dirty_at_plan": False}
    assert plan["builder_seat"] == "builder-a" and plan["max_attempts"] == 2 and plan["deadline_s"] == 3600
    assert plan["checks"]["policy.paid_anthropic_ban"]["kind"] == "trusted_pytest"
    assert plan["checks"]["tests.scripts_impacted"]["modules"] == ["scripts/tests/test_sample.py"]
    assert st["checks"]["review.independent"]["status"] == "QUEUED"


def test_green_run_with_full_contexts_is_pass(fx, tmp_path):
    fr.green(fx, tmp_path)
    s = fr.status(fx)
    assert s["overall"] == "PASS", s["checks"]
    assert checks(s)["policy.paid_anthropic_ban"] == "PASS"
    assert s["contexts"]["uncovered"] == [] and s["contexts"]["status"] == "ok"
    receipt = json.loads((fx["run"] / "receipts" / "tests.scripts_impacted.json").read_text())
    assert receipt["env_hash"] == s["env_hash"]
    assert {"candidate_sha", "tree_sha", "base_sha", "plan_hash"} <= set(receipt["binding"])


def test_missing_contexts_file_caps_overall_at_subset_pass(fx, tmp_path):
    fr.green(fx, tmp_path, with_contexts=False)
    s = fr.status(fx)
    assert all(v in ("PASS", "NOT_APPLICABLE") for v in checks(s).values())
    assert s["overall"] == "SUBSET_PASS" and s["contexts"]["status"] == "missing"


def test_nonexistent_contexts_path_is_missing_not_error(fx, tmp_path):
    fr.green(fx, tmp_path, "--contexts-file", str(tmp_path / "nope.yaml"), with_contexts=False)
    assert fr.status(fx)["overall"] == "SUBSET_PASS"


@pytest.mark.parametrize("mapping", ["blocked", "not_implemented"])
def test_blocked_or_not_implemented_context_forces_blocked(fx, tmp_path, mapping):
    ctxs = [{"name": "policy.change_map", "local": {"kind": "rule"}, "mapping": "executed"}, {"name": "e2e.playwright", "local": {"kind": "cmd"}, "mapping": mapping}]
    fr.green(fx, tmp_path, contexts=ctxs)
    s = fr.status(fx)
    assert s["overall"] == "BLOCKED" and s["contexts"]["blocked"] == ["e2e.playwright"]


def test_uncovered_executed_context_is_subset_pass(fx, tmp_path):
    ctxs = [{"name": "policy.change_map", "local": {"kind": "rule"}, "mapping": "executed"}, {"name": "codeql", "local": {"kind": "cmd"}, "mapping": "executed"}]
    fr.green(fx, tmp_path, contexts=ctxs)
    s = fr.status(fx)
    assert s["overall"] == "SUBSET_PASS" and s["contexts"]["uncovered"] == ["codeql"]


@pytest.mark.parametrize("body", ["contexts: []\n", "not: a matrix\n", "contexts: [1]\n", ":\t: bad yaml [", "contexts:\n - {name: a, mapping: executed}\n - {name: a, mapping: executed}\n"])
def test_invalid_contexts_file_is_blocked(fx, tmp_path, body):
    (tmp_path / "c.yaml").write_text(body)
    fr.plan(fx, "--contexts-file", str(tmp_path / "c.yaml"))
    fr.run(fx)
    fr.import_review(fx, tmp_path)
    s = fr.status(fx)
    assert s["contexts"]["status"] == "invalid" and s["overall"] == "BLOCKED"


def test_unknown_mapping_is_treated_as_blocked():
    c = runner.load_contexts(None)
    assert c["status"] == "missing"
    import pathlib
    import tempfile

    p = pathlib.Path(tempfile.mkdtemp()) / "c.yaml"
    p.write_text("contexts:\n - {name: a, mapping: maybe}\n")
    got = runner.load_contexts(str(p))
    assert got["status"] == "ok" and got["map"]["a"]["mapping"] == "blocked"


def test_not_applicable_needs_a_reason(fx, tmp_path):
    fr.green(fx, tmp_path)
    st = fr.load_state(fx)
    st["checks"]["tests.frontend_mouth"]["reason"] = ""
    fr.save_state(fx, st)
    assert fr.status(fx)["overall"] == "BLOCKED"


# --------------------------------------------------- exit-code classification (g)
@pytest.mark.parametrize("name,module,want", [
    ("t.empty", "scripts/tests/test_empty_module.py", "ERROR"),      # rc 5, zero collected
    ("t.allskip", "scripts/tests/test_allskip.py", "ERROR"),          # rc 0, nothing executed
    ("t.failing", "scripts/tests/test_fail.py", "FAIL"),              # rc 1
    ("t.broken", "scripts/tests/test_broken.py", "ERROR"),            # rc 2 collection error
    ("t.usage", "scripts/tests/does_not_exist.py", "ERROR"),          # rc 4 usage error
])
def test_pytest_exit_codes_map_to_verdicts(fx, name, module, want):
    fr.plan(fx, "--extra-check", pytest_check(name, fx["repo"], [module]))
    fr.run(fx, "--only", name)
    assert fr.load_state(fx)["checks"][name]["status"] == want


def test_pytest_with_no_modules_is_error(fx):
    fr.plan(fx, "--extra-check", pytest_check("t.none", fx["repo"], []))
    fr.run(fx, "--only", "t.none")
    c = fr.load_state(fx)["checks"]["t.none"]
    assert c["status"] == "ERROR" and "zero test modules" in c["reason"]


def test_unexecutable_cmd_is_error(fx):
    fr.plan(fx, "--extra-check", cmd_check("c.missing", fx["repo"], ["/nonexistent/tool-xyz"]))
    fr.run(fx, "--only", "c.missing")
    c = fr.load_state(fx)["checks"]["c.missing"]
    assert c["status"] == "ERROR" and "unexecutable" in c["reason"]


def test_crashing_cmd_is_error_and_failing_cmd_is_fail(fx):
    fr.plan(fx, "--extra-check", cmd_check("c.kill", fx["repo"], [PY, "-c", "import os,signal;os.kill(os.getpid(),signal.SIGKILL)"]),
            "--extra-check", cmd_check("c.fail", fx["repo"], [PY, "-c", "raise SystemExit(3)"]))
    fr.run(fx, "--only", "c.kill")
    fr.run(fx, "--only", "c.fail")
    got = fr.load_state(fx)["checks"]
    assert got["c.kill"]["status"] == "ERROR" and got["c.fail"]["status"] == "FAIL"


def test_timeout_is_error(fx):
    fr.plan(fx, "--extra-check", cmd_check("c.slow", fx["repo"], [PY, "-c", "import time;time.sleep(30)"]))
    fr.run(fx, "--only", "c.slow", "--timeout", "1")
    assert fr.load_state(fx)["checks"]["c.slow"]["status"] == "ERROR"


@pytest.mark.parametrize("rc,counts,want", [
    (3, {"collected": 4, "executed": 4, "failures": 0, "errors": 0, "skipped": 0}, "ERROR"),
    (4, {"collected": 1, "executed": 1, "failures": 0, "errors": 0, "skipped": 0}, "ERROR"),
    (-9, {"collected": 4, "executed": 4, "failures": 0, "errors": 0, "skipped": 0}, "ERROR"),
    (7, {"collected": 4, "executed": 4, "failures": 0, "errors": 0, "skipped": 0}, "ERROR"),
    (0, {"collected": 4, "executed": 4, "failures": 1, "errors": 0, "skipped": 0}, "ERROR"),
    (1, {"collected": 4, "executed": 4, "failures": 1, "errors": 0, "skipped": 0}, "FAIL"),
    (0, {"collected": 4, "executed": 4, "failures": 0, "errors": 0, "skipped": 0}, "PASS"),
    (0, {"collected": 0, "executed": 0, "failures": None, "errors": None, "skipped": None, "junit": "missing"}, "ERROR"),
])
def test_classify_pytest_table(rc, counts, want):
    assert runner.classify_pytest(rc, counts)[0] == want


# ------------------------------------------------- trusted_pytest guard (f)
def test_trusted_pytest_runs_base_test_against_candidate_tree(fx):
    fr.plan(fx)
    fr.run(fx, "--only", "policy.paid_anthropic_ban")
    c = fr.load_state(fx)["checks"]["policy.paid_anthropic_ban"]
    assert c["status"] == "PASS" and c["counts"]["executed"] == 2
    assert "overlay" in (fx["run"] / "logs" / "policy.paid_anthropic_ban.log").read_text()


def test_candidate_that_breaks_the_guarded_file_fails_the_trusted_test(tmp_path):
    fx = fr.make_repo(tmp_path, {"scripts/check_ban_predicates.py": "BANNED" + "_LITERAL = 1\n"})
    fr.plan(fx)
    fr.run(fx, "--only", "policy.paid_anthropic_ban")
    assert fr.load_state(fx)["checks"]["policy.paid_anthropic_ban"]["status"] == "FAIL"


def test_candidate_cannot_rewrite_its_own_guard(tmp_path):
    fx = fr.make_repo(tmp_path, {"scripts/check_ban_predicates.py": "BANNED" + "_LITERAL = 1\n", "scripts/tests/test_ban_predicates.py": "def test_ok():\n    pass\n"})
    fr.plan(fx)
    fr.run(fx, "--only", "policy.paid_anthropic_ban")
    assert fr.load_state(fx)["checks"]["policy.paid_anthropic_ban"]["status"] == "FAIL"  # the BASE copy ran, not the candidate's


def test_trusted_pytest_missing_at_base_is_blocked_not_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(fr, "BASE_FILES", {k: v for k, v in fr.BASE_FILES.items() if k != "scripts/tests/test_ban_predicates.py"})
    fx = fr.make_repo(tmp_path)
    fr.plan(fx)
    c = fr.load_state(fx)["checks"]["policy.paid_anthropic_ban"]
    assert c["status"] == "BLOCKED" and "missing at base" in c["reason"]


def test_tampered_trusted_blob_is_error(fx):
    fr.plan(fx)
    (fx["run"] / "state" / "trusted" / "base_files" / "scripts" / "tests" / "test_ban_predicates.py").write_text("def test_x():\n    pass\n")
    fr.run(fx, "--only", "policy.paid_anthropic_ban")
    assert fr.load_state(fx)["checks"]["policy.paid_anthropic_ban"]["status"] == "ERROR"


# ---------------------------------------------------- INTERRUPTED, retries, deadline (a)
def test_running_with_dead_pid_becomes_interrupted_in_status_and_is_persisted(fx):
    fr.plan(fx)
    fr.make_running(fx, "tests.scripts_impacted")
    s = fr.status(fx)
    c = s["checks"]["tests.scripts_impacted"]
    assert c["status"] == "INTERRUPTED" and "dead" in c["reason"] and "2026-01-01T00:00:00Z" in c["reason"]
    assert s["overall"] == "BLOCKED"
    persisted = fr.load_state(fx)["checks"]["tests.scripts_impacted"]
    assert persisted["status"] == "INTERRUPTED" and persisted["history"][-1]["status"] == "INTERRUPTED"


def test_status_does_not_persist_while_the_coordinator_lock_is_held(fx):
    fr.plan(fx)
    fr.make_running(fx, "tests.scripts_impacted")
    with runner.Store(fx["run"]).lock():
        s = fr.status(fx)
    assert s["checks"]["tests.scripts_impacted"]["status"] == "INTERRUPTED"
    assert fr.load_state(fx)["checks"]["tests.scripts_impacted"]["status"] == "RUNNING"


def test_live_pid_stays_running(fx):
    fr.plan(fx)
    st = fr.load_state(fx)
    st["checks"]["tests.scripts_impacted"].update(status="RUNNING", pid=os.getpid(), attempts=1)
    fr.save_state(fx, st)
    assert fr.status(fx)["checks"]["tests.scripts_impacted"]["status"] == "RUNNING"


def test_run_requeues_interrupted_within_budget_and_records_attempts(fx):
    fr.plan(fx)
    fr.make_running(fx, "tests.scripts_impacted", attempts=1)
    fr.run(fx)
    c = fr.load_state(fx)["checks"]["tests.scripts_impacted"]
    assert c["status"] == "PASS" and c["attempts"] == 2
    assert [h["status"] for h in c["history"]] == ["INTERRUPTED", "PASS"]


def test_retry_budget_exhausted_is_error_and_stays_blocking(fx, tmp_path):
    fr.green(fx, tmp_path)
    fr.make_running(fx, "tests.scripts_impacted", attempts=2)  # already used max_attempts=2
    fr.run(fx)
    c = fr.load_state(fx)["checks"]["tests.scripts_impacted"]
    assert c["status"] == "ERROR" and "retry budget exhausted" in c["reason"]
    fr.run(fx)  # a second run must not resurrect it
    assert fr.load_state(fx)["checks"]["tests.scripts_impacted"]["status"] == "ERROR"
    assert fr.status(fx)["overall"] == "BLOCKED"


def test_deadline_exceeded_blocks_the_retry(fx):
    fr.plan(fx, "--deadline-s", "0")
    fr.make_running(fx, "tests.scripts_impacted", attempts=1)
    fr.run(fx)
    c = fr.load_state(fx)["checks"]["tests.scripts_impacted"]
    assert c["status"] == "ERROR" and "deadline_exceeded=True" in c["reason"]


def test_run_deadline_override_is_recorded(fx):
    fr.plan(fx)
    fr.make_running(fx, "tests.scripts_impacted", attempts=1)
    fr.run(fx, "--deadline-s", "-1")
    st = fr.load_state(fx)
    assert st["checks"]["tests.scripts_impacted"]["status"] == "ERROR" and st["deadline_override_s"] == -1


def test_max_attempts_is_a_plan_option(fx):
    fr.plan(fx, "--max-attempts", "1")
    fr.make_running(fx, "tests.scripts_impacted", attempts=1)
    fr.run(fx)
    assert fr.load_state(fx)["checks"]["tests.scripts_impacted"]["status"] == "ERROR"


def test_sigterm_during_a_check_leaves_interrupted_not_running(fx):
    fr.plan(fx, "--extra-check", cmd_check("c.slow", fx["repo"], [PY, "-c", "import time;time.sleep(30)"]))
    import threading

    threading.Timer(1.0, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()
    with pytest.raises(KeyboardInterrupt):
        fr.run(fx, "--only", "c.slow")
    c = fr.load_state(fx)["checks"]["c.slow"]
    assert c["status"] == "INTERRUPTED" and "signal" in c["reason"]


def test_pid_alive_semantics():
    assert runner.pid_alive(os.getpid()) and not runner.pid_alive(fr.dead_pid()) and not runner.pid_alive(0)
    assert not runner.pid_alive(os.getpid(), "definitely not this process's start time")  # recycled pid


# ------------------------------------------------------------- freshness
def test_candidate_moved_makes_everything_stale_and_restore_makes_it_pass_again(fx, tmp_path):
    fr.green(fx, tmp_path)
    assert fr.status(fx)["overall"] == "PASS"
    git(fx["repo"], "commit", "-q", "--allow-empty", "-m", "moved")
    s = fr.status(fx)
    assert s["overall"] == "BLOCKED" and "candidate moved" in s["freshness"]["stale_reason"]
    assert "PASS" not in checks(s).values() and checks(s)["tests.scripts_impacted"] == "STALE"
    git(fx["repo"], "reset", "-q", "--hard", fx["candidate"])
    assert fr.status(fx)["overall"] == "PASS"


def test_dirty_tracked_file_is_stale(fx, tmp_path):
    fr.green(fx, tmp_path)
    (fx["repo"] / "scripts/tests/test_sample.py").write_text("def test_a():\n    assert True\n")
    s = fr.status(fx)
    assert "dirty" in s["freshness"]["stale_reason"] and checks(s)["tests.scripts_impacted"] == "STALE"
    git(fx["repo"], "checkout", "--", "scripts/tests/test_sample.py")
    assert fr.status(fx)["overall"] == "PASS"


def test_env_hash_drift_marks_pass_receipts_stale(fx, tmp_path, fake_env):
    fr.green(fx, tmp_path)
    fake_env.env["deps_lock_sha256"] = "e" * 64
    s = fr.status(fx)
    assert checks(s)["tests.scripts_impacted"] == "STALE" and "env drift" in s["checks"]["tests.scripts_impacted"]["reason"]
    assert s["overall"] == "BLOCKED"
    fake_env.env["deps_lock_sha256"] = "d" * 64
    assert fr.status(fx)["overall"] == "PASS"


def test_pass_without_receipt_is_not_pass(fx, tmp_path):
    fr.green(fx, tmp_path)
    (fx["run"] / "receipts" / "tests.scripts_impacted.json").unlink()
    s = fr.status(fx)
    assert checks(s)["tests.scripts_impacted"] == "ERROR" and s["overall"] == "BLOCKED"


def test_tampered_receipt_is_not_pass(fx, tmp_path):
    fr.green(fx, tmp_path)
    p = fx["run"] / "receipts" / "tests.scripts_impacted.json"
    r = json.loads(p.read_text())
    r["result"]["reason"] = "edited"
    p.write_text(json.dumps(r))
    assert checks(fr.status(fx))["tests.scripts_impacted"] == "ERROR"


def test_run_refuses_to_execute_on_a_moved_worktree(fx):
    fr.plan(fx)
    git(fx["repo"], "commit", "-q", "--allow-empty", "-m", "moved")
    fr.run(fx)
    c = fr.load_state(fx)["checks"]["tests.scripts_impacted"]
    assert c["status"] == "BLOCKED" and "worktree moved" in c["reason"]


def test_dirty_worktree_at_plan_time_blocks_everything(fx):
    (fx["repo"] / "scripts/tests/test_sample.py").write_text("changed\n")
    fr.plan(fx)
    assert {c["status"] for c in fr.load_state(fx)["checks"].values()} == {"BLOCKED"}


# ------------------------------------------------------------------ review (c)
@pytest.mark.parametrize("field", ["reviewed_candidate_sha", "reviewed_tree_sha", "reviewed_base_sha"])
def test_review_bound_to_another_identity_is_blocked(fx, tmp_path, field):
    fr.plan(fx)
    fr.import_review(fx, tmp_path, **{field: "0" * 40})
    c = fr.load_state(fx)["checks"]["review.independent"]
    assert c["status"] == "BLOCKED" and field in c["reason"]


def test_review_missing_base_sha_is_blocked(fx, tmp_path):
    fr.plan(fx)
    p = fr.review_file(fx, tmp_path / "r.json")
    d = json.loads(p.read_text())
    del d["reviewed_base_sha"]
    p.write_text(json.dumps(d))
    runner.main(["review", "--run-dir", str(fx["run"]), "--file", str(p)])
    assert fr.load_state(fx)["checks"]["review.independent"]["status"] == "BLOCKED"


@pytest.mark.parametrize("seat", ["builder-a", "BUILDER-A ", "co-builder", "", None])
def test_reviewer_equal_to_a_builder_seat_or_empty_is_blocked(fx, tmp_path, seat):
    fr.plan(fx, "--builder-seats", "co-builder,other")
    fr.import_review(fx, tmp_path, reviewer_seat=seat)
    assert fr.load_state(fx)["checks"]["review.independent"]["status"] == "BLOCKED"


def test_review_without_a_recorded_builder_seat_cannot_pass(fx, tmp_path):
    runner.main(["plan", "--run-dir", str(fx["run"]), "--worktree", str(fx["repo"]), "--base", fx["base"], "--python", PY])
    fr.import_review(fx, tmp_path)
    c = fr.load_state(fx)["checks"]["review.independent"]
    assert c["status"] == "BLOCKED" and "builder_seat" in c["reason"]


def test_review_verdict_fail_is_fail_and_only_exact_pass_passes(fx, tmp_path):
    fr.plan(fx)
    fr.import_review(fx, tmp_path, verdict="FAIL")
    assert fr.load_state(fx)["checks"]["review.independent"]["status"] == "FAIL"
    for bad in ("pass", "PASS ", "OK", None, True):
        fr.import_review(fx, tmp_path, verdict=bad)
        assert fr.load_state(fx)["checks"]["review.independent"]["status"] == "BLOCKED", bad


def test_matching_review_passes_and_stores_the_file_sha256(fx, tmp_path):
    fr.plan(fx)
    p = fr.review_file(fx, tmp_path / "r.json")
    runner.main(["review", "--run-dir", str(fx["run"]), "--file", str(p)])
    c = fr.load_state(fx)["checks"]["review.independent"]
    assert c["status"] == "PASS" and c["review_sha256"] == runner.sha256_file(p) and len(c["history"]) == 1


def test_review_pass_goes_blocked_if_its_stored_copy_is_edited(fx, tmp_path):
    fr.green(fx, tmp_path)
    (fx["run"] / "receipts" / "review.independent.json").write_text("{}")
    assert checks(fr.status(fx))["review.independent"] == "BLOCKED"


def test_review_that_is_not_json_is_blocked(fx, tmp_path):
    fr.plan(fx)
    (tmp_path / "junk.json").write_text("not json")
    runner.main(["review", "--run-dir", str(fx["run"]), "--file", str(tmp_path / "junk.json")])
    assert fr.load_state(fx)["checks"]["review.independent"]["status"] == "BLOCKED"


# ------------------------------------------------------------------- env evidence (b)
def test_real_env_fingerprint_carries_the_required_evidence(fx, monkeypatch):
    monkeypatch.undo()  # this one uses the REAL fingerprint
    spec = {"c.tool": {"kind": "cmd", "cmd": [PY, "-c", "pass"], "cwd": str(fx["repo"])}, "c.gone": {"kind": "cmd", "cmd": ["/nonexistent/x"], "cwd": str(fx["repo"])}}
    env = runner.env_fingerprint(PY, spec)
    for k in ("python", "pytest", "platform", "hostname", "runner_sha256", "git_version", "deps_lock_sha256", "deps_lock_source", "uv_version", "runner_version"):
        assert k in env
    assert env["python"].startswith(sys.version.split()[0]) and env["runner_version"] == runner.RUNNER_VERSION == "0.6.0"
    assert len(env["deps_lock_sha256"]) == 64 and env["deps_lock_source"] in ("pip", "uv")
    assert env["tools"]["c.tool"]["sha256"] not in ("not-a-file", None) and os.path.isabs(env["tools"]["c.tool"]["path"])
    assert env["tools"]["c.gone"] == {"path": None, "sha256": "not-a-file"}
    assert runner.env_hash(env) == runner.env_hash(json.loads(json.dumps(env)))


def test_env_hash_changes_with_any_field(fake_env):
    a = runner.env_hash(fake_env.env)
    fake_env.env["tools"] = {"x": {"path": "/bin/x", "sha256": "1"}}
    assert runner.env_hash(fake_env.env) != a


def test_atomic_write_leaves_no_temp_files(tmp_path):
    runner.atomic_write(tmp_path / "f.json", "{}")
    runner.atomic_write(tmp_path / "f.json", '{"a": 1}')
    assert sorted(p.name for p in tmp_path.iterdir()) == ["f.json"] and json.loads((tmp_path / "f.json").read_text()) == {"a": 1}


# ------------------------------------------- the real matrix written by the contexts lane
MATRIX = fr.REAL_REPO / "scripts" / "localci" / "contexts_matrix.yaml"


@pytest.mark.skipif(not MATRIX.exists(), reason="contexts_matrix.yaml not present yet")
def test_real_contexts_matrix_loads_and_never_yields_pass_while_it_has_blocked_contexts(fx, tmp_path):
    c = runner.load_contexts(str(MATRIX))
    assert c["status"] == "ok" and len(c["required"]) == len(set(c["required"])) >= 1
    assert all(v["mapping"] in runner.MAPPINGS for v in c["map"].values())
    fr.green(fx, tmp_path, "--contexts-file", str(MATRIX), with_contexts=False)
    s = fr.status(fx)
    blocked = [n for n, v in c["map"].items() if v["mapping"] in ("blocked", "not_implemented")]
    assert s["overall"] == ("BLOCKED" if blocked else "SUBSET_PASS") and s["overall"] != "PASS"
    assert set(blocked) <= set(s["contexts"]["blocked"])


def test_secret_env_rule_is_an_entity_not_a_spelling():
    from scripts.localci import runner as r
    assert r.is_secret_env("FLY_API_TOKEN") and r.is_secret_env("VERCEL_TOKEN")
    assert r.is_secret_env("ANTHROPIC_AUTH_TOKEN") and r.is_secret_env("SOME_VENDOR_API_KEY")
    assert r.is_secret_env("PG_PASSWORD") and r.is_secret_env("REDIS_PASSWORD")
    assert not r.is_secret_env("PATH") and not r.is_secret_env("PYTHONPATH") and not r.is_secret_env("HOME")


# ------------------------------------------- trusted interpreter isolation + plan integrity
def test_sitecustomize_in_the_candidate_path_never_runs_inside_a_trusted_interpreter(tmp_path, monkeypatch):
    planted = tmp_path / "candidate_root"
    planted.mkdir()
    marker = tmp_path / "marker"
    (planted / "sitecustomize.py").write_text(f"open({str(marker)!r}, 'w').write('pwned')\n")
    monkeypatch.setenv("PYTHONPATH", str(planted))
    monkeypatch.setenv("PYTHONSTARTUP", str(planted / "sitecustomize.py"))
    env = runner.trusted_env()
    assert "PYTHONPATH" not in env and "PYTHONSTARTUP" not in env and "PYTHONHOME" not in env
    assert env["PYTHONSAFEPATH"] == "1" and env["PYTHONDONTWRITEBYTECODE"] == "1"
    subprocess.run([sys.executable, "-I", "-c", "pass"], env=env, check=True)
    assert not marker.exists(), "candidate sitecustomize executed inside the trusted interpreter"
    subprocess.run([sys.executable, "-c", "pass"], env=dict(os.environ), check=True)  # control: the inherited env DOES load it
    assert marker.exists(), "control failed: the planted sitecustomize is not effective, the guilt test proves nothing"


def test_trusted_env_strips_secrets_and_injection_variables(monkeypatch):
    for k in ("CLAUDE_CODE_OAUTH_TOKEN", "SOME_SERVICE_TOKEN", "PYTHONHOME", "PYTEST_ADDOPTS", "KEEP_ME"):
        monkeypatch.setenv(k, "v")
    env = runner.trusted_env()
    assert "KEEP_ME" in env and not ({"CLAUDE_CODE_OAUTH_TOKEN", "SOME_SERVICE_TOKEN", "PYTHONHOME", "PYTEST_ADDOPTS"} & set(env))
    assert runner.trusted_env({"PYTHONPATH": "/x", "A": "1"}) == {"A": "1", "PYTHONSAFEPATH": "1", "PYTHONDONTWRITEBYTECODE": "1"}


def test_a_candidate_sitecustomize_at_the_worktree_root_cannot_reach_the_trusted_pytest(tmp_path):
    marker = tmp_path / "marker"
    fx = fr.make_repo(tmp_path, {"sitecustomize.py": f"open({str(marker)!r}, 'w').write('x')\n"})
    fr.plan(fx)
    fr.run(fx, "--only", "policy.paid_anthropic_ban")
    assert fr.load_state(fx)["checks"]["policy.paid_anthropic_ban"]["status"] == "PASS" and not marker.exists()


def test_plan_tampering_is_refused_before_anything_trusts_it(fx, tmp_path):
    fr.plan(fx)
    assert runner.load_plan_verified(fx["run"])["plan_hash"] == fr.load_state(fx)["plan_hash"]
    pp = fx["run"] / "state" / "plan.json"
    plan = json.loads(pp.read_text())
    plan["checks"]["policy.trusted_classifier_corpus"]["cmd"] = [PY, "-c", "pass"]  # a forged, always-green command
    pp.write_text(json.dumps(plan))
    with pytest.raises(SystemExit):
        runner.load_plan_verified(fx["run"])
    for call in (lambda: fr.run(fx), lambda: fr.status(fx), lambda: fr.import_review(fx, tmp_path)):
        with pytest.raises(SystemExit):
            call()


# --------------------------------------------------------------- extra checks cannot forge a verdict
@pytest.mark.parametrize("name", ["policy.paid_anthropic_ban", "policy.brand_new", "tests.scripts_impacted", "review.independent", "trusted.anything"])
def test_extra_check_cannot_take_a_reserved_or_planned_name(fx, name):
    with pytest.raises(SystemExit):
        fr.plan(fx, "--extra-check", fr.cmd_check(name, fx["repo"], [PY, "-c", "pass"]))
    assert not (fx["run"] / "state" / "plan.json").exists()


@pytest.mark.parametrize("spec", [
    json.dumps({"kind": "record", "status": "PASS", "reason": "forged"}),
    json.dumps({"kind": "trusted_pytest", "cwd": ".", "python": PY, "trusted_files": ["x.py"]}),
    json.dumps(["not", "a", "dict"]),
    "{not json",
])
def test_extra_check_must_be_an_executable_spec(fx, spec):
    with pytest.raises(SystemExit):
        fr.plan(fx, "--extra-check", "ctx.x=" + spec)
    assert not (fx["run"] / "state" / "plan.json").exists()


@pytest.mark.parametrize("name", ["ctx.x ", " ctx.x", "security.pysa_python ", "Security.pysa_python", "ctx", "ctx.", ".x", "ctx.a b"])
def test_extra_check_name_twins_and_malformed_names_are_refused(fx, name):
    with pytest.raises(SystemExit):
        fr.plan(fx, "--extra-check", fr.cmd_check(name, fx["repo"], [PY, "-c", "pass"]))
    assert not (fx["run"] / "state" / "plan.json").exists()


def test_extra_check_without_equals_is_refused(fx):
    with pytest.raises(SystemExit):
        fr.plan(fx, "--extra-check", "ctx.x")


def test_extra_check_in_its_own_namespace_is_planned_and_runs(fx):
    fr.plan(fx, "--extra-check", fr.cmd_check("ctx.ok", fx["repo"], [PY, "-c", "pass"]))
    assert checks(fr.load_state(fx))["ctx.ok"] == "QUEUED"


# --------------------------------------------------------------- candidate code runs last, behind a seal the operator keeps
needs_docker = pytest.mark.skipif(not fr.docker_image_ready(), reason="the trusted seal is supported only for contained plans; docker image absent here")


@needs_docker
def test_trusted_checks_run_before_candidate_tests_and_the_seal_catches_a_post_run_forgery(tmp_path, capsys):
    fx = fr.make_repo(tmp_path, {**fr.CANDIDATE_FILES, "t/test_ok.py": "def test_ok():\n    assert True\n"})
    fr.plan(fx, "--isolation", "container", "--isolation-image", fr.ISOLATION_IMAGE, "--extra-check", fr.pytest_check("ctx.aaa_candidate", fx["repo"], ["t/test_ok.py"]))
    fr.run(fx)
    printed = capsys.readouterr().out
    st = fr.load_state(fx)
    ch = st["checks"]
    trusted = "policy.trusted_classifier_corpus"      # runner-planned cmd: an --extra-check cmd is the operator's host command, never a trusted check
    assert ch[trusted]["status"] == "PASS" and ch["ctx.aaa_candidate"]["status"] == "PASS"
    events = [json.loads(line) for line in (fx["run"] / "state" / "journal.jsonl").read_text().splitlines()]
    seals = [e for e in events if e.get("event") == "seal"]
    assert seals and seals[0]["why"].startswith("trusted checks done")
    assert ch[trusted]["history"][0]["ended_at"] <= ch["ctx.aaa_candidate"]["history"][0]["started_at"]   # trusted first, candidate last
    seal = seals[0]["seal"]
    assert f"seal={seal}" in printed and seal == st["seal"]
    assert runner.main(["status", "--run-dir", str(fx["run"]), "--seal", seal[:16]]) in (0, 1)
    assert "seal mismatch" not in (json.loads((fx["run"] / "status.json").read_text())["freshness"].get("stale_reason") or "")
    # the forgery gate 1 reproduced: candidate code rewrites the trusted receipt + state after the run, re-hashing the receipt
    rp = Path(ch[trusted]["receipt"])
    r = json.loads(rp.read_text())
    r.pop("receipt_sha256")
    r["result"]["status"], r["result"]["reason"], r["result"]["rc"] = "PASS", "rc=0 forged", 0
    r["receipt_sha256"] = runner.sha256_json(r)
    rp.write_text(json.dumps(r, indent=2, sort_keys=True))
    st["checks"][trusted].update(status="PASS", reason="rc=0 forged", rc=0)
    (fx["run"] / "state" / "state.json").write_text(json.dumps(st))
    assert fr.status(fx)["checks"][trusted]["reason"] == "rc=0 forged"       # without the seal the forgery is invisible (same-user boundary)
    runner.main(["status", "--run-dir", str(fx["run"]), "--seal", seal])
    out = json.loads((fx["run"] / "status.json").read_text())
    assert out["overall"] == "BLOCKED" and "seal mismatch" in out["freshness"]["stale_reason"]


def test_trusted_pytest_runs_after_the_seal_because_it_executes_candidate_code(tmp_path):
    fx = fr.make_repo(tmp_path, {**fr.CANDIDATE_FILES, "t/test_ok.py": "def test_ok():\n    assert True\n"})
    fr.plan(fx, "--extra-check", fr.cmd_check("ctx.zzz_cmd", fx["repo"], [PY, "-c", "pass"]),
            "--extra-check", fr.pytest_check("ctx.aaa_candidate", fx["repo"], ["t/test_ok.py"]))
    fr.run(fx)
    st = fr.load_state(fx)
    ends = {n: c["history"][0]["ended_at"] for n, c in st["checks"].items() if c.get("history")}
    starts = {n: c["history"][0]["started_at"] for n, c in st["checks"].items() if c.get("history")}
    events = [json.loads(line) for line in (fx["run"] / "state" / "journal.jsonl").read_text().splitlines()]
    boundary = next(e["at"] for e in events if e.get("event") in ("seal", "seal_withheld") and e["why"].startswith("trusted checks done"))
    plan = json.loads((fx["run"] / "state" / "plan.json").read_text())
    for n, spec in plan["checks"].items():
        if spec["kind"] == "cmd" and spec.get("extra"):
            assert starts[n] >= boundary, n                  # an --extra-check cmd is the operator's host command: after the seal, never sealed
        elif spec["kind"] == "cmd":
            assert ends[n] <= boundary, n                    # runner-planned cmd verdicts are sealed
        elif spec["kind"] in ("trusted_pytest", "pytest"):
            assert starts[n] >= boundary, n                  # anything that runs candidate code starts after the seal
    assert runner.TRUSTED_KINDS == ("cmd", "trusted_steps")
    with pytest.raises(SystemExit):
        runner.main(["status", "--run-dir", str(fx["run"]), "--seal", "ab"])   # a 2-char prefix would match almost anything


@needs_docker
def test_a_rewritten_record_verdict_breaks_the_seal(fx):
    fr.plan(fx, "--isolation", "container", "--isolation-image", fr.ISOLATION_IMAGE)
    fr.run(fx)
    st = fr.load_state(fx)
    seal = st["seal"]
    name = next(n for n, c in st["checks"].items() if c["status"] == "NOT_APPLICABLE")   # a plan-time record verdict
    st["checks"][name].update(status="PASS", reason="forged")
    (fx["run"] / "state" / "state.json").write_text(json.dumps(st))
    runner.main(["status", "--run-dir", str(fx["run"]), "--seal", seal])
    out = json.loads((fx["run"] / "status.json").read_text())
    assert out["overall"] == "BLOCKED" and "seal mismatch" in out["freshness"]["stale_reason"]


# --------------------------------------------------------------- change_map verdict parity with GitHub
def test_unclassified_paths_is_not_a_failure(tmp_path):
    """GitHub's `changes` job passes on unclassified paths and runs every job (run_all); a local FAIL here
    would tell the fleet not to arm a PR GitHub accepts. The run_all consequence is carried by the BLOCKED
    test records, so the overall verdict is no signal, never a failure."""
    fx = fr.make_repo(tmp_path, {**fr.CANDIDATE_FILES, "zzz_unmapped_dir/notes.txt": "x\n"})
    fr.plan(fx)
    plan = json.loads((fx["run"] / "state" / "plan.json").read_text())
    cm = plan["checks"]["policy.change_map"]
    assert cm["data"]["reason"] == "unclassified_paths" and cm["data"]["run_all"] is True
    assert cm["status"] == "PASS", cm
    assert plan["checks"]["tests.backend_shards"]["status"] == "BLOCKED"


def test_a_legacy_record_is_superseded_once_the_context_that_runs_its_job_is_planned(tmp_path):
    """tests.backend_shards said "no local backend runner exists"; once ctx.backend-tests is planned, that check carries the job's
    verdict (here BLOCKED: --isolation none), and the legacy record stops claiming one of its own."""
    fx = fr.make_repo(tmp_path, {**fr.CANDIDATE_FILES, "zzz_unmapped_dir/notes.txt": "x\n"})   # run_all: the legacy rule says BLOCKED
    ctx = {"name": "Backend Tests (Python)", "workflow_file": ".github/workflows/tests.yml", "job_id": "backend-tests", "mapping": "executed",
           "local": {"check": "ctx.backend-tests", "where": "container", "expressions": True, "steps": [{"workflow_step": "t"}]}}
    fr.plan(fx, "--contexts-file", str(fr.contexts_file(fx, tmp_path / "contexts.yaml", [ctx])))
    checks = json.loads((fx["run"] / "state" / "plan.json").read_text())["checks"]
    assert checks["ctx.backend-tests"]["status"] == "BLOCKED"
    assert checks["tests.backend_shards"]["status"] == "NOT_APPLICABLE"
    assert checks["tests.backend_shards"]["reason"].startswith("superseded by ctx.backend-tests")
    assert checks["tests.frontend_mouth"]["status"] == "BLOCKED"   # its context is not planned here: the old rule stands


def test_classified_diff_stays_pass(fx):
    fr.plan(fx)
    cm = json.loads((fx["run"] / "state" / "plan.json").read_text())["checks"]["policy.change_map"]
    assert cm["data"]["reason"] == "classified" and cm["status"] == "PASS"


@pytest.mark.parametrize("cm_out", [{"mode": "enforcing", "reason": "enumeration_failed", "run_all": True, "suggested_jobs": []},
                                    {"mode": "shadow", "reason": "classified", "run_all": False, "suggested_jobs": []}])
def test_unjudgeable_classifier_output_is_blocked_not_fail(cm_out):
    assert runner.change_map_status(cm_out) == "BLOCKED"
