"""The sandbox of kind "pytest" (tests.scripts_impacted) sees what hosted sees: a git repository, hosted's interpreter, and a parent process
that is not the container's init. Seven decisions of Pro's journal were red on those three differences, not on the candidate."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .fixture_repo import runner

LOCALCI = Path(runner.__file__).resolve().parent
ENV_TESTS = '''
import os, subprocess


def test_git_answers_from_inside_the_tree():
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], check=True, capture_output=True, text=True).stdout.strip()
    assert os.path.realpath(top) == os.path.realpath(os.getcwd())
    assert "marker.txt" in subprocess.run(["git", "ls-files"], check=True, capture_output=True, text=True).stdout.split()


def test_the_parent_is_not_init():
    assert os.getppid() > 1
'''


def _cfg_dir(tmp_path: Path) -> Path:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    shutil.copy(LOCALCI / "steps_driver.py", cfg)
    shutil.copy(LOCALCI / "pytest_indexed.py", cfg)
    return cfg


def test_the_tree_is_indexed_as_a_commit_and_pytest_runs_as_a_child_of_the_wrapper(tmp_path):
    tree = tmp_path / "w"
    tree.mkdir()
    (tree / "marker.txt").write_text("x\n")
    (tree / "test_env.py").write_text(ENV_TESTS)
    cfg = _cfg_dir(tmp_path)
    (cfg / "pytest_indexed.json").write_text(json.dumps({"root": str(tree), "history": None,
                                                         "argv": [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "test_env.py"]}))
    res = subprocess.run([sys.executable, "-I", str(cfg / "pytest_indexed.py"), str(cfg / "pytest_indexed.json")], capture_output=True, text=True,
                         env={"PATH": os.environ["PATH"], "HOME": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"})
    assert res.returncode == 0 and "2 passed" in res.stdout, res.stdout + res.stderr


def test_without_the_wrapper_the_same_tests_are_red_in_a_tree_with_no_git(tmp_path):
    tree = tmp_path / "w"
    tree.mkdir()
    (tree / "marker.txt").write_text("x\n")
    (tree / "test_env.py").write_text(ENV_TESTS)
    res = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "test_env.py"], cwd=tree, capture_output=True, text=True,
                         env={"PATH": os.environ["PATH"], "HOME": str(tmp_path), "GIT_CEILING_DIRECTORIES": str(tmp_path)})
    assert res.returncode != 0 and "test_git_answers_from_inside_the_tree" in res.stdout


def test_hosted_python_is_the_3_11_of_the_image_and_the_default_without_one():
    assert runner.hosted_python({"pythons": {"3.11.17": "/opt/py311/bin"}}) == "/opt/py311/bin/python3"
    assert runner.hosted_python({"pythons": {"3.12.1": "/x/bin", "3.11": "/y/bin"}}) == "/y/bin/python3"
    assert runner.hosted_python({"pythons": {"3.12.1": "/x/bin"}}) == "python"
    assert runner.hosted_python({}) == "python"


def test_the_candidate_pytest_leg_ships_the_wrapper_runs_hosteds_python_and_the_tree_pack(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(runner, "history_delta", lambda wt, base, cand: {"added": ["new.py"], "base": []})
    monkeypatch.setattr(runner, "tree_pack_ship_safe", lambda run_dir, plan: ({"path": "/cfg/tree.pack", "tree": "t" * 40}, {}, None))
    monkeypatch.setattr(runner, "execute_contained", lambda *a, **k: seen.update(inner=a[4], extra=a[6], env=a[7], workdir=a[11]) or (None, "stopped by the test"))
    wt = tmp_path / "wt"
    wt.mkdir()
    spec = {"kind": "pytest", "cwd": str(wt), "modules": ["scripts/tests/test_a.py"],
            "isolation": {"pythons": {"3.11.17": "/opt/py311/bin"}, "docker": "docker", "user": "1:1", "image_id": "sha256:" + "a" * 64}}
    plan = {"worktree": str(wt), "base_sha": "b" * 40, "candidate_sha": "c" * 40, "run_id": "r"}
    out = runner._execute_candidate_contained("tests.scripts_impacted", spec, tmp_path, plan, 60, tmp_path / "log", tmp_path / "junit.xml")
    assert out["status"] == "ERROR"
    assert seen["inner"] == ["python", "-I", "/cfg/pytest_indexed.py", "/cfg/pytest_indexed.json"] and seen["workdir"] == "/w"
    cfg = json.loads(seen["extra"]["cfg/pytest_indexed.json"])
    assert cfg["argv"][:3] == ["/opt/py311/bin/python3", "-m", "pytest"] and cfg["argv"][-1] == "scripts/tests/test_a.py"
    assert cfg["root"] == "/w" and cfg["history"]["added"] == ["new.py"] and cfg["tree_pack"]["tree"] == "t" * 40
    assert seen["extra"]["cfg/steps_driver.py"] == runner.STEPS_DRIVER.read_bytes() and seen["extra"]["cfg/pytest_indexed.py"] == runner.PYTEST_INDEXED.read_bytes()
    assert seen["env"]["PYTHONPATH"] == "/w"
