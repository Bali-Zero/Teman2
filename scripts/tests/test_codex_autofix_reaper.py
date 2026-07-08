"""Tests for scripts/codex_autofix_reaper.py — the Codex auto-fix backlog reaper.

Module is imported via importlib (scripts/ is a flat bag of standalone tools, not a package).
The reaper's only side-doors to GitHub/git are `_gh` and `_git`; we monkeypatch those to feed
synthetic state, so no test touches the real repo.

The load-bearing test is INNOCENCE (superscar #3): a PR whose title-workflow is green on main
but which STILL has other failing checks must be KEPT, never closed — that PR is real unfinished
work, and the reaper must not decide on the title proxy while the real check state disagrees.
This is exactly the #1820 trap the reaper was born from.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

MODULE_PATH = Path(__file__).resolve().parent.parent / "codex_autofix_reaper.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("codex_autofix_reaper", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


reaper = _load_module()


def _cp(stdout: str = "", returncode: int = 0, stderr: str = "") -> SimpleNamespace:
    """A stand-in for subprocess.CompletedProcess with the fields the reaper reads."""
    return SimpleNamespace(stdout=stdout, returncode=returncode, stderr=stderr)


def _make_gh(pr_rows: list[dict], workflow_conclusion: str = "success"):
    """Fake `_gh` covering the two calls build_report makes: `pr list` and `run list`."""
    def fake_gh(args, check=True):
        if args[:2] == ["pr", "list"]:
            return _cp(json.dumps(pr_rows))
        if args[:2] == ["run", "list"]:
            return _cp(json.dumps([{"conclusion": workflow_conclusion, "status": "completed"}]))
        return _cp("", 0)
    return fake_gh


def _no_branches_git(args, check=True):
    """Fake `_git` that reports zero orphan branches (isolates the PR-side logic)."""
    if args[:1] == ["ls-remote"]:
        return _cp("")  # no codex/auto-fix branches
    return _cp("")


def test_innocence_pr_with_other_failing_checks_is_kept(monkeypatch):
    """#1820 trap: title-workflow 'Root Guard' is green on main, but the PR still fails
    inventory-check + Backend Tests. It MUST be kept, not close-eligible."""
    pr_rows = [{
        "number": 1820,
        "headRefName": "codex/auto-fix-ci-28331068567",
        "title": "fix(ci): auto-fix workflow Root Guard run 28331068567",
        "mergeStateStatus": "DIRTY",
        "updatedAt": "2026-07-02T00:00:00Z",
        "reviewDecision": "",
        "statusCheckRollup": [
            {"name": "Root Guard", "conclusion": "SUCCESS", "status": "COMPLETED"},
            {"name": "inventory-check", "conclusion": "FAILURE", "status": "COMPLETED"},
            {"name": "Backend Tests (Python)", "conclusion": "FAILURE", "status": "COMPLETED"},
        ],
    }]
    monkeypatch.setattr(reaper, "_gh", _make_gh(pr_rows, workflow_conclusion="success"))
    monkeypatch.setattr(reaper, "_git", _no_branches_git)

    report = reaper.build_report("owner/repo", stale_days=14)
    assert report.prs == [], "PR with other failing checks must NOT be close-eligible"
    assert report.kept_prs == 1


def test_guilt_clean_pr_with_green_target_is_close_eligible(monkeypatch):
    """The mirror case: title-workflow green on main AND no other failing checks → close-eligible."""
    pr_rows = [{
        "number": 1894,
        "headRefName": "codex/auto-fix-ci-28493415912",
        "title": "fix(ci): auto-fix workflow Tests & Coverage run 28493415912",
        "mergeStateStatus": "BLOCKED",
        "updatedAt": "2026-07-01T00:00:00Z",
        "reviewDecision": "",
        "statusCheckRollup": [
            {"name": "Tests & Coverage", "conclusion": "SUCCESS", "status": "COMPLETED"},
        ],
    }]
    monkeypatch.setattr(reaper, "_gh", _make_gh(pr_rows, workflow_conclusion="success"))
    monkeypatch.setattr(reaper, "_git", _no_branches_git)

    report = reaper.build_report("owner/repo", stale_days=14)
    assert len(report.prs) == 1
    assert report.prs[0].number == 1894


def test_non_autofix_branch_is_never_touched(monkeypatch):
    """A human branch that isn't codex/auto-fix-ci-* is invisible to the reaper, even if red."""
    pr_rows = [{
        "number": 999,
        "headRefName": "agent/air-m5/backend-rag/real-feature",
        "title": "feat: something real",
        "mergeStateStatus": "DIRTY",
        "updatedAt": "2026-01-01T00:00:00Z",
        "reviewDecision": "",
        "statusCheckRollup": [{"name": "X", "conclusion": "FAILURE", "status": "COMPLETED"}],
    }]
    monkeypatch.setattr(reaper, "_gh", _make_gh(pr_rows))
    monkeypatch.setattr(reaper, "_git", _no_branches_git)

    report = reaper.build_report("owner/repo", stale_days=14)
    assert report.prs == []
    assert report.kept_prs == 0  # not an autofix PR → not even counted as kept


def test_target_still_failing_on_main_keeps_pr(monkeypatch):
    """If the target workflow is NOT green on main, the failure it fixes still stands → keep."""
    pr_rows = [{
        "number": 1500,
        "headRefName": "codex/auto-fix-ci-11111111",
        "title": "fix(ci): auto-fix workflow Some Gate run 11111111",
        "mergeStateStatus": "CLEAN",
        "updatedAt": "2026-07-04T00:00:00Z",
        "reviewDecision": "",
        "statusCheckRollup": [],
    }]
    monkeypatch.setattr(reaper, "_gh", _make_gh(pr_rows, workflow_conclusion="failure"))
    monkeypatch.setattr(reaper, "_git", _no_branches_git)

    report = reaper.build_report("owner/repo", stale_days=14)
    assert report.prs == []
    assert report.kept_prs == 1


def test_branch_regex_anchored():
    """The autofix branch regex is anchored — never a substring match inside a human branch."""
    assert reaper._AUTOFIX_BRANCH_RE.match("codex/auto-fix-ci-123") is not None
    assert reaper._AUTOFIX_BRANCH_RE.match("feature/codex/auto-fix-ci-123") is None
    assert reaper._AUTOFIX_BRANCH_RE.match("codex/auto-fix-ci-123-extra") is None
    assert reaper._AUTOFIX_BRANCH_RE.match("codex/auto-fix-ci-") is None
