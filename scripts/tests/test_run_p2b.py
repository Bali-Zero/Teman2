"""Tests for scripts/kbli_bench/run_p2b.py's repo_relative() — the manifest-path guilt.

The 2026-09-22 P2b re-judge manifest recorded corpus.path as an absolute worktree
path (/Users/<account>/nuzantara/.worktrees/<lane>/scripts/...), carrying the host
account name into a committed artifact (flagged by claude-sonnet-5, M5 gate session,
code review round). Guilt: an absolute corpus path is not written into the manifest.

Module is imported via importlib.util.spec_from_file_location (not a package import)
because scripts/ is a flat bag of standalone tools, not a Python package (mirrors
scripts/tests/test_score_p2b.py convention).

Run:
    python3 -m pytest scripts/tests/test_run_p2b.py -v
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "kbli_bench" / "run_p2b.py"


@pytest.fixture(scope="module")
def run_mod():
    spec = importlib.util.spec_from_file_location("run_p2b_under_test", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_repo_relative_strips_an_absolute_worktree_path(run_mod):
    corpus = REPO_ROOT / "scripts" / "kbli_bench" / "p2b_corpus.json"
    result = run_mod.repo_relative(corpus)

    assert result == "scripts/kbli_bench/p2b_corpus.json"
    assert not result.startswith("/")
    assert str(REPO_ROOT) not in result


def test_repo_relative_accepts_an_already_relative_path(run_mod):
    rel = Path("scripts/kbli_bench/p2b_corpus.json")
    result = run_mod.repo_relative(rel)

    assert result == "scripts/kbli_bench/p2b_corpus.json"


def test_repo_relative_falls_back_outside_any_repo(run_mod, tmp_path):
    """tmp_path lives under the system tmpdir, never inside a git worktree, so the
    `git rev-parse --show-toplevel` probe exits non-zero and repo_relative must fall
    back to the path as given rather than raise."""
    outside = tmp_path / "not_a_repo" / "corpus.json"
    outside.parent.mkdir(parents=True)
    outside.write_text("{}")

    result = run_mod.repo_relative(outside)
    assert result == str(outside)
