"""The sandbox of kind "pytest" (tests.scripts_impacted) has hosted's sweep environment: the lock + cell-core + the four test packages from the Backend
Tests deps image, installed offline by the sweep's own lines, HOME=/home/runner, ~/logs as the whole-directory collection leaves it. #8648's two
modules were 11 red in a bare 3.11 (pydantic, numpy, ~/logs/dlq_autopilot.log) and green in the sweep, so every PR touching such a module needed a human."""
from __future__ import annotations

import importlib.util
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from . import fixture_repo as fr
from .fixture_repo import runner
from .test_service_contexts import fake_docker

ROOT = Path(runner.__file__).resolve().parents[2]
SWEEP = ROOT / ".github" / "workflows" / "scripts-tests-sweep.yml"
IMAGE = "sha256:" + "d" * 64
DEPS = {"requirements": ["apps/backend-rag/requirements.lock.txt"], "packages": ["pytest"]}


def sweep_step(text: str) -> dict:
    return next(s for s in yaml.safe_load(text)["jobs"]["sweep"]["steps"] if str(s.get("name", "")).startswith("Install dependencies"))


def sweep_lines(text: str) -> list[tuple[str, list[str]]]:
    """(cwd, argv) of every command of the sweep's install step; `cd` sets the cwd of the lines after it."""
    out, cwd = [], "."
    for ln in sweep_step(text)["run"].splitlines():
        argv = shlex.split(ln)
        if argv and argv[0] == "cd":
            cwd = argv[1]
        elif argv:
            out.append((cwd, argv))
    return out


def sweep_env(text: str) -> dict:
    return next(s for s in yaml.safe_load(text)["jobs"]["sweep"]["steps"] if s.get("id") == "sweep")["env"]


def test_the_install_lines_are_the_sweeps_own_and_a_drifted_workflow_is_seen():
    assert [(c, a) for c, a in runner.SWEEP_INSTALL] == [(c, a) for c, a in sweep_lines(SWEEP.read_text())]
    drifted = SWEEP.read_text().replace("pytest pytest-asyncio pytest-mock fakeredis", "pytest pytest-asyncio pytest-mock fakeredis hypothesis")
    assert sweep_lines(drifted) != [(c, a) for c, a in runner.SWEEP_INSTALL]
    assert sweep_lines(SWEEP.read_text().replace("requirements.lock.txt", "requirements.txt")) != [(c, a) for c, a in runner.SWEEP_INSTALL]


def test_the_sweeps_constants_are_set_and_its_services_are_not_faked():
    env = sweep_env(SWEEP.read_text())
    assert {k: runner.SWEEP_ENV[k] for k in ("JWT_SECRET_KEY", "API_KEYS")} == {k: env[k] for k in ("JWT_SECRET_KEY", "API_KEYS")}
    assert not {"DATABASE_URL", "TEST_DATABASE_URL", "REDIS_URL"} & set(runner.SWEEP_ENV)
    assert runner.SWEEP_ENV["HOME"] == "/home/runner" and runner.SWEEP_ENV["UV_OFFLINE"] == "1" and runner.SWEEP_ENV["PIP_NO_INDEX"] == "1"
    assert runner.SWEEP_ENV["USER"] == runner.SWEEP_ENV["LOGNAME"] == "runner"   # the runner's login: test_queue_doctor compares USER with getpass.getuser(), uid 65534 has two names


def test_the_install_exit_code_is_one_literal_in_both_files_and_is_no_verdict():
    spec = importlib.util.spec_from_file_location("pytest_indexed_under_test", runner.PYTEST_INDEXED)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(runner.PYTEST_INDEXED.parent))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(runner.PYTEST_INDEXED.parent))
    assert mod.INSTALL_RC == runner.INSTALL_RC
    status, reason = runner.classify_pytest(runner.INSTALL_RC, {"collected": 0, "executed": 0, "failures": None, "errors": None, "skipped": None})
    assert status == "ERROR" and "install failed" in reason
    assert runner.classify_pytest(1, {"collected": 3, "executed": 3, "failures": 1, "errors": 0, "skipped": 0})[0] == "FAIL"   # a red test is still red


def test_a_deps_image_and_the_runner_owned_keys_cannot_be_claimed_by_an_extra_check():
    assert {"deps_image", "deps_note"} <= runner.RUNNER_OWNED_KEYS


def _run_wrapper(tmp_path, **cfg_extra):
    tree = tmp_path / "w"
    tree.mkdir(exist_ok=True)
    (tree / "marker.txt").write_text("x\n")
    cfg = tmp_path / "cfg"
    cfg.mkdir(exist_ok=True)
    for f in ("steps_driver.py", "pytest_indexed.py"):
        (cfg / f).write_bytes((runner.PYTEST_INDEXED.parent / f).read_bytes())
    argv = [sys.executable, "-c", "open('pytest-ran', 'w').close()"]
    (cfg / "c.json").write_text(json.dumps({"root": str(tree), "history": None, "argv": argv, **cfg_extra}))
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    res = subprocess.run([sys.executable, "-I", str(cfg / "pytest_indexed.py"), str(cfg / "c.json")], capture_output=True, text=True,
                         env={"PATH": os.environ["PATH"], "HOME": str(home), "PYTHONDONTWRITEBYTECODE": "1"})
    return res, tree, home


def test_the_wrapper_installs_in_order_makes_home_dirs_and_then_runs_pytest(tmp_path):
    ins = [["sub", [sys.executable, "-c", "open('first', 'w').close()"]], ["sub", [sys.executable, "-c", "import os; assert os.path.exists('first'); open('second', 'w').close()"]]]
    (tmp_path / "w" / "sub").mkdir(parents=True)
    res, tree, home = _run_wrapper(tmp_path, install=ins, home_dirs=["logs"])
    assert res.returncode == 0, res.stdout + res.stderr
    assert (tree / "sub" / "second").exists() and (tree / "pytest-ran").exists() and (home / "logs").is_dir()


def test_a_failed_install_ends_the_run_with_the_install_code_and_pytest_never_starts(tmp_path):
    (tmp_path / "w" / "sub").mkdir(parents=True)
    ins = [["sub", [sys.executable, "-c", "raise SystemExit(7)"]], ["sub", [sys.executable, "-c", "open('later', 'w').close()"]]]
    res, tree, _ = _run_wrapper(tmp_path, install=ins)
    assert res.returncode == runner.INSTALL_RC and "env install failed rc=7" in res.stdout
    assert not (tree / "pytest-ran").exists() and not (tree / "sub" / "later").exists()


def test_without_install_or_home_dirs_the_wrapper_is_what_it_was(tmp_path):
    res, tree, home = _run_wrapper(tmp_path)
    assert res.returncode == 0 and (tree / "pytest-ran").exists() and not (home / "logs").exists()


def _leg(tmp_path, monkeypatch, **spec_extra):
    seen = {}
    monkeypatch.setattr(runner, "history_delta", lambda wt, base, cand: {"added": [], "base": []})
    monkeypatch.setattr(runner, "tree_pack_ship_safe", lambda run_dir, plan: (None, {}, None))
    monkeypatch.setattr(runner, "execute_contained", lambda *a, **k: seen.update(extra=a[6], env=a[7], image=k.get("image_id")) or (None, "stopped by the test"))
    wt = tmp_path / "wt"
    wt.mkdir()
    iso = {"pythons": {"3.11.17": "/opt/py311/bin"}, "docker": "docker", "user": "1:1", "image_id": "sha256:" + "a" * 64}
    spec = {"kind": "pytest", "cwd": str(wt), "modules": ["scripts/tests/test_a.py"], "isolation": iso, **spec_extra}
    plan = {"worktree": str(wt), "base_sha": "b" * 40, "candidate_sha": "c" * 40, "run_id": "r"}
    runner._execute_candidate_contained("tests.scripts_impacted", spec, tmp_path, plan, 60, tmp_path / "log", tmp_path / "junit.xml")
    seen["cfg"], seen["log"] = json.loads(seen["extra"]["cfg/pytest_indexed.json"]), (tmp_path / "log").read_text()
    return seen


def test_a_leg_with_a_deps_image_runs_in_it_with_hosteds_home_the_sweeps_install_and_names_it_in_the_log(tmp_path, monkeypatch):
    seen = _leg(tmp_path, monkeypatch, deps_image=IMAGE, deps_note="deps localci-deps:x (5 pins)")
    assert seen["image"] == IMAGE
    assert seen["env"]["HOME"] == "/home/runner" and seen["env"]["UV_OFFLINE"] == "1" and seen["env"]["PYTHONPATH"] == "/w"
    assert seen["cfg"]["install"] == [[c, a] for c, a in runner.SWEEP_INSTALL] and seen["cfg"]["home_dirs"] == ["logs"]
    assert f"# env: deps image {IMAGE[:19]}" in seen["log"] and "deps localci-deps:x" in seen["log"]


def test_a_leg_without_one_is_the_old_bare_sandbox_and_ships_no_install(tmp_path, monkeypatch):
    seen = _leg(tmp_path, monkeypatch)
    assert seen["image"] is None and seen["env"]["HOME"] == "/tmp" and "UV_OFFLINE" not in seen["env"]
    assert "install" not in seen["cfg"] and "home_dirs" not in seen["cfg"] and "# env:" not in seen["log"]


def _planned(tmp_path, monkeypatch, *, ctxs, deps_result=(IMAGE, "deps note"), candidate=None, pythons="3.11=/opt/py311/bin"):
    exe = fake_docker(tmp_path)
    exe.write_text(exe.read_text().replace('"image inspect") for a', '"image inspect") case "$4" in *Config.Env*) '
                                           f'printf "sha256:%064d\\nLOCALCI_PYTHONS={pythons}\\n" 1; exit 0;; esac; for a'))
    monkeypatch.setenv("PATH", f"{exe.parent}{os.pathsep}{os.environ['PATH']}")
    calls = []
    monkeypatch.setattr(runner, "plan_deps_image", lambda *a: calls.append(a) or deps_result)
    fx = fr.make_repo(tmp_path, candidate or fr.CANDIDATE_FILES, {"README.md": "base\n"})
    fr.plan(fx, "--isolation", "container", "--contexts-file", str(fr.contexts_file(fx, tmp_path / "contexts.yaml", ctxs)))
    return json.loads((fx["run"] / "state" / "plan.json").read_text())["checks"]["tests.scripts_impacted"], calls


BACKEND = {"name": runner.SWEEP_DEPS_CONTEXT, "mapping": "executed", "local": {"check": "ctx.backend-tests", "deps": DEPS}}


def test_the_plan_hands_the_check_the_backend_tests_deps_image_built_from_its_own_recipe(tmp_path, monkeypatch):
    spec, calls = _planned(tmp_path, monkeypatch, ctxs=[BACKEND])
    assert spec["kind"] == "pytest" and spec["deps_image"] == IMAGE and spec["deps_note"] == "deps note"
    (wt, cand, iso, deps, prefix, _run, slug), = calls
    assert deps == DEPS and prefix == "/opt/py311/bin" and slug == "backend-tests"   # the recipe Backend Tests is planned with: one digest, one image
    assert len(cand) == 40 and iso["mode"] == "container"   # the candidate's own sha, as Backend Tests reads its lock


def test_an_image_that_cannot_be_had_blocks_the_check_and_never_falls_back_to_the_bare_sandbox(tmp_path, monkeypatch):
    spec, _ = _planned(tmp_path, monkeypatch, ctxs=[BACKEND], deps_result=(None, "deps image build failed (logs/deps-backend-tests.log)"))
    assert spec["kind"] == "record" and spec["status"] == "BLOCKED" and "deps image build failed" in spec["reason"] and "not available offline" in spec["reason"]


def test_a_matrix_without_the_backend_recipe_blocks_the_check_by_name(tmp_path, monkeypatch):
    spec, calls = _planned(tmp_path, monkeypatch, ctxs=[{**BACKEND, "local": {"check": "ctx.backend-tests"}}])
    assert spec["status"] == "BLOCKED" and runner.SWEEP_DEPS_CONTEXT in spec["reason"] and not calls


def test_no_changed_scripts_test_builds_no_image(tmp_path, monkeypatch):
    spec, calls = _planned(tmp_path, monkeypatch, ctxs=[BACKEND], candidate={"docs/x.md": "x\n"})
    assert spec["kind"] == "record" and spec["status"] == "NOT_APPLICABLE" and not calls


def test_a_plan_without_a_readable_matrix_keeps_the_bare_sandbox_and_builds_nothing(tmp_path, monkeypatch):
    exe = fake_docker(tmp_path)
    exe.write_text(exe.read_text().replace('"image inspect") for a', '"image inspect") case "$4" in *Config.Env*) printf "sha256:%064d\\n" 1; exit 0;; esac; for a'))
    monkeypatch.setenv("PATH", f"{exe.parent}{os.pathsep}{os.environ['PATH']}")
    calls = []
    monkeypatch.setattr(runner, "plan_deps_image", lambda *a: calls.append(a) or (IMAGE, "x"))
    fx = fr.make_repo(tmp_path, fr.CANDIDATE_FILES, {"README.md": "base\n"})
    fr.plan(fx, "--isolation", "container")   # no --contexts-file: every required context is BLOCKED anyway, the check keeps its shape
    spec = json.loads((fx["run"] / "state" / "plan.json").read_text())["checks"]["tests.scripts_impacted"]
    assert spec["kind"] == "pytest" and "deps_image" not in spec and not calls
