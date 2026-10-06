"""The hosted workflow's path filter and skip-budget step must keep covering what the suite really reads."""
from __future__ import annotations

import shlex

import yaml

from .fixture_repo import REAL_REPO, runner

WORKFLOW = ".github/workflows/localci-tests.yml"
# Real-repo files read from OUTSIDE scripts/localci: fixture_repo.make_repo copies the classifier files into every fixture repo.
OUTSIDE_INPUTS = list(runner.TRUSTED_CLASSIFIER_FILES)


def _load() -> dict:
    doc = yaml.safe_load((REAL_REPO / WORKFLOW).read_text())
    triggers = doc.get("on", doc.get(True))                                          # PyYAML reads the bare key `on` as the boolean True
    return {"doc": doc, "pull_request": triggers["pull_request"]["paths"], "push": triggers["push"]["paths"]}


def _covered(path: str, patterns: list[str]) -> bool:
    return any(path == p or (p.endswith("/**") and path.startswith(p[:-2])) for p in patterns)


def test_pull_request_and_push_filters_are_the_same_list():
    wf = _load()
    assert wf["pull_request"] == wf["push"]


def test_the_filter_covers_the_suite_the_workflow_and_every_outside_input_it_reads():
    paths = _load()["pull_request"]
    assert "scripts/localci/**" in paths and WORKFLOW in paths
    assert not [f for f in OUTSIDE_INPUTS if not _covered(f, paths)]


def test_the_filter_covers_every_ancestor_pytest_configuration_and_conftest():
    paths = _load()["pull_request"]
    names = ("pytest.ini", ".pytest.ini", "pytest.toml", ".pytest.toml", "pyproject.toml", "tox.ini", "setup.cfg", "conftest.py")
    assert not [prefix + name for prefix in ("", "scripts/") for name in names if not _covered(prefix + name, paths)]
    assert _covered("scripts/__init__.py", paths)                                    # absent today; if added, `import scripts.localci` executes it


def test_the_skip_budget_step_requires_executed_tests_and_a_floor():
    steps = _load()["doc"]["jobs"]["localci-tests"]["steps"]
    command = next(s["run"] for s in steps if "skip_budget.py" in s.get("run", ""))
    assert "--require" in command and "--min-executed" in command
    args = shlex.split(command)
    assert int(args[args.index("--min-executed") + 1]) >= 331


def test_every_test_id_regex_in_the_skip_budget_step_is_anchored_to_the_full_dotted_module_path():
    steps = _load()["doc"]["jobs"]["localci-tests"]["steps"]
    args = shlex.split(next(s["run"] for s in steps if "skip_budget.py" in s.get("run", "")))
    ids = [args[i + 1] for i, a in enumerate(args) if a in ("--allow", "--require")]
    assert len(ids) >= 5 and all(rx.startswith(r"^scripts\.localci\.tests\.") for rx in ids), ids
