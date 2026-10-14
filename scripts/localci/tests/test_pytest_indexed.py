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


def _leg(tmp_path, monkeypatch, *, pythons=None, history=None, wt_files=None, modules=("scripts/tests/test_a.py", "scripts/tests/test_b.py")):
    """Drive the candidate pytest leg to the container call and hand back what it would ship."""
    seen = {}
    monkeypatch.setattr(runner, "history_delta", lambda wt, base, cand: {"added": [], "base": []} if history is None else history)
    monkeypatch.setattr(runner, "tree_pack_ship_safe", lambda run_dir, plan: (None, {}, None))
    monkeypatch.setattr(runner, "execute_contained", lambda *a, **k: seen.update(inner=a[4], extra=a[6], env=a[7]) or (None, "stopped by the test"))
    wt = tmp_path / "wt"
    wt.mkdir(exist_ok=True)
    for rel, body in (wt_files or {}).items():
        (wt / rel).parent.mkdir(parents=True, exist_ok=True)
        (wt / rel).write_text(body)
    iso = {"pythons": {"3.11.17": "/opt/py311/bin"} if pythons is None else pythons, "docker": "docker", "user": "1:1", "image_id": "sha256:" + "a" * 64}
    spec = {"kind": "pytest", "cwd": str(wt), "modules": list(modules), "isolation": iso}
    plan = {"worktree": str(wt), "base_sha": "b" * 40, "candidate_sha": "c" * 40, "run_id": "r"}
    out = runner._execute_candidate_contained("tests.scripts_impacted", spec, tmp_path, plan, 60, tmp_path / "log", tmp_path / "junit.xml")
    seen["out"], seen["log"] = out, (tmp_path / "log").read_text()
    return seen


def test_the_full_argv_carries_every_module_in_order_and_nothing_else(tmp_path, monkeypatch):
    seen = _leg(tmp_path, monkeypatch)
    cfg = json.loads(seen["extra"]["cfg/pytest_indexed.json"])
    assert cfg["argv"] == ["/opt/py311/bin/python3", "-m", "pytest", "-p", "no:cacheprovider", "-q", "--junitxml=/out/junit.xml",
                           "scripts/tests/test_a.py", "scripts/tests/test_b.py"]
    assert cfg["path_prefix"] == "/opt/py311/bin"


def test_the_wrapper_shipped_is_the_base_runners_even_when_the_candidate_tree_carries_its_own(tmp_path, monkeypatch):
    seen = _leg(tmp_path, monkeypatch, wt_files={"scripts/localci/pytest_indexed.py": "raise SystemExit(0)  # the candidate's own\n",
                                                 "scripts/localci/steps_driver.py": "# the candidate's own\n"})
    assert seen["extra"]["cfg/pytest_indexed.py"] == runner.PYTEST_INDEXED.read_bytes() and b"candidate's own" not in seen["extra"]["cfg/pytest_indexed.py"]
    assert seen["extra"]["cfg/steps_driver.py"] == runner.STEPS_DRIVER.read_bytes()


def _run_wrapper(tmp_path, argv, **extra):
    tree = tmp_path / "w"
    tree.mkdir(exist_ok=True)
    (tree / "marker.txt").write_text("x\n")
    cfg = _cfg_dir(tmp_path) if not (tmp_path / "cfg").exists() else tmp_path / "cfg"
    (cfg / "pytest_indexed.json").write_text(json.dumps({"root": str(tree), "history": None, "argv": argv, **extra}))
    return subprocess.run([sys.executable, "-I", str(cfg / "pytest_indexed.py"), str(cfg / "pytest_indexed.json")], capture_output=True, text=True,
                          env={"PATH": os.environ["PATH"], "HOME": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"})


def test_pytests_exit_code_is_the_containers_exit_code_unchanged(tmp_path):
    for rc in (0, 1, 2, 5):
        assert _run_wrapper(tmp_path, [sys.executable, "-c", f"raise SystemExit({rc})"]).returncode == rc


def test_the_images_311_comes_first_on_the_childs_path(tmp_path):
    fake = tmp_path / "py311bin"
    fake.mkdir()
    (fake / "python3").write_text("#!/bin/sh\necho py311\n")
    (fake / "python3").chmod(0o755)
    res = _run_wrapper(tmp_path, [sys.executable, "-c", "import shutil; print(shutil.which('python3'))"], path_prefix=str(fake))
    assert res.stdout.strip() == str(fake / "python3"), res.stdout + res.stderr
    res = _run_wrapper(tmp_path, [sys.executable, "-c", "import shutil; print(shutil.which('python3'))"])
    assert res.stdout.strip() != str(fake / "python3")


def test_a_base_that_cannot_be_rebuilt_is_indexed_alone_not_an_error_and_the_log_says_so(tmp_path, monkeypatch):
    seen = _leg(tmp_path, monkeypatch, history="more than 3000 paths changed")
    assert json.loads(seen["extra"]["cfg/pytest_indexed.json"])["history"] is None
    assert seen["out"]["status"] == "ERROR" and "stopped by the test" in seen["out"]["reason"]   # reached the container, the test's own stop
    assert "# history: BASE not rebuilt" in seen["log"] and "more than 3000 paths" in seen["log"]


def test_an_image_without_a_311_says_so_in_the_log_and_one_with_it_says_nothing(tmp_path, monkeypatch):
    seen = _leg(tmp_path, monkeypatch, pythons={"3.12.1": "/x/bin"})
    assert json.loads(seen["extra"]["cfg/pytest_indexed.json"])["argv"][0] == "python" and "path_prefix" not in json.loads(seen["extra"]["cfg/pytest_indexed.json"])
    assert "# python: the image carries no 3.11 interpreter" in seen["log"]
    other = tmp_path / "other"
    other.mkdir()
    assert "# python:" not in _leg(other, monkeypatch)["log"]
