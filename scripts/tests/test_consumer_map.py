"""Tests for scripts/consumer_map.py — enumerate live consumers of DELETED
or RENAMED files by BASENAME.

WHY (2026-08-21, PR #4459): deleting `apps/backend-rag/tests/` (an orphan
tree) went CI-red TWICE because two consumers were invisible to a search
anchored on the deleted PATH: `.github/workflows/sonarqube.yml` named the
files as `tests/...` AFTER a `cd apps/backend-rag` step, and
`apps/backend-rag/scripts/backend_stability_gate.py:41` listed
`tests/test_migrations.py` inside a Python list literal. Both guilt cases
below reproduce those exact two shapes.

Every case operates on a REAL, throwaway git repo (`tmp_path` fixture) with
REAL commits and a REAL `git diff -M` — never a synthetic/mocked target
list — per cicatrix-superscar.md #6 ("anti-hallucination blindness": build
on what you actually executed, not on a re-typed mirror of what you assume
the code does).

Run:
    cd <worktree> && python3 -m pytest scripts/tests/test_consumer_map.py -q
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "consumer_map.py"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True
    )
    assert result.returncode == 0, (
        f"git {' '.join(args)} failed in {repo}: {result.stderr}"
    )
    return result


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    return repo


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


# ---------------------------------------------------------------------------
# GUILT — the two real #4459 shapes.
# ---------------------------------------------------------------------------


def test_guilt_workflow_cd_relative_reference_is_live(tmp_path: Path) -> None:
    """A deleted file referenced by a workflow via a cd-relative path (the
    #4459 sonarqube.yml shape) must be found — LIVE, exit 1."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_migrations.py"
    _write(target, "def test_x(): pass\n")
    _write(
        repo / ".github" / "workflows" / "sonarqube.yml",
        "jobs:\n  test:\n    steps:\n"
        "      - run: cd apps/backend-rag && pytest tests/test_migrations.py\n",
    )
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete orphan tests tree")

    result = _run(repo, "--base", base)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "sonarqube.yml" in result.stdout
    assert "| workflow |" in result.stdout
    assert "| LIVE" in result.stdout
    assert "CONSUMER_MAP_LIVE_COUNT=1" in result.stdout


def test_guilt_python_list_literal_reference_is_live(tmp_path: Path) -> None:
    """A deleted file listed as a bare string inside a Python list literal
    (the #4459 backend_stability_gate.py:41 shape) must be found — LIVE,
    exit 1."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_migrations.py"
    _write(target, "def test_x(): pass\n")
    _write(
        repo / "apps" / "backend-rag" / "scripts" / "backend_stability_gate.py",
        'REQUIRED = [\n    "tests/test_migrations.py",\n]\n',
    )
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete orphan tests tree")

    result = _run(repo, "--base", base)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "backend_stability_gate.py" in result.stdout
    assert "| python |" in result.stdout
    assert "| LIVE" in result.stdout


def test_guilt_two_targets_one_live_one_clean_reports_only_the_live_one(
    tmp_path: Path,
) -> None:
    """Sanity check on multi-target aggregation: deleting two files where
    only one has a real consumer must still exit 1, and the count must
    reflect exactly the live one."""
    repo = _init_repo(tmp_path)
    referenced = repo / "apps" / "backend-rag" / "tests" / "test_ref.py"
    orphan = repo / "apps" / "backend-rag" / "tests" / "test_orphan_clean.py"
    _write(referenced, "def test_x(): pass\n")
    _write(orphan, "def test_y(): pass\n")
    _write(
        repo / "Makefile",
        "test:\n\tpytest apps/backend-rag/tests/test_ref.py\n",
    )
    base = _commit_all(repo, "base")

    referenced.unlink()
    orphan.unlink()
    _commit_all(repo, "delete both")

    result = _run(repo, "--base", base)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "test_ref.py" in result.stdout
    assert "CONSUMER_MAP_LIVE_COUNT=1" in result.stdout


# ---------------------------------------------------------------------------
# INNOCENCE
# ---------------------------------------------------------------------------


def test_innocence_rename_consumer_already_repointed(tmp_path: Path) -> None:
    """A RENAME whose only consumer already references the NEW path must
    exit 0 — the consumer is not stale, it never pointed at the old path in
    the surviving diff."""
    repo = _init_repo(tmp_path)
    old_dir = repo / "apps" / "backend-rag" / "tests"
    new_dir = repo / "apps" / "backend-rag" / "backend" / "tests"
    old_file = old_dir / "test_migrations.py"
    _write(old_file, "def test_x(): pass\n")
    _write(
        repo / ".github" / "workflows" / "tests.yml",
        "jobs:\n  test:\n    steps:\n"
        "      - run: pytest apps/backend-rag/backend/tests/test_migrations.py\n",
    )
    base = _commit_all(repo, "base")

    new_dir.mkdir(parents=True, exist_ok=True)
    _git(repo, "mv", str(old_file.relative_to(repo)), str((new_dir / "test_migrations.py").relative_to(repo)))
    _git(repo, "commit", "-q", "-m", "move test into backend/tests")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CONSUMER_MAP_LIVE_COUNT=0" in result.stdout


def test_innocence_docs_only_mention_is_not_a_finding(tmp_path: Path) -> None:
    """A hit that lives only in a `.md` file is reported as docs-mention,
    never counted as LIVE, and must not fail the push."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_orphan.py"
    _write(target, "def test_x(): pass\n")
    _write(repo / "docs" / "notes.md", "See test_orphan.py for context.\n")
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "docs-mention" in result.stdout
    assert "| LIVE" not in result.stdout
    assert "CONSUMER_MAP_LIVE_COUNT=0" in result.stdout


def test_innocence_no_deleted_or_renamed_files_is_clean(tmp_path: Path) -> None:
    """A push that only ADDS/MODIFIES files (nothing deleted or renamed)
    must be a trivial clean pass — this is the common case, most pushes."""
    repo = _init_repo(tmp_path)
    _write(repo / "README.md", "hello\n")
    base = _commit_all(repo, "base")
    _write(repo / "README.md", "hello world\n")
    _commit_all(repo, "modify only")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "CONSUMER_MAP_LIVE_COUNT=0" in result.stdout


def test_innocence_excluded_tree_research_is_not_reported_even_as_docs_mention(
    tmp_path: Path,
) -> None:
    """research/** is excluded outright — not even surfaced as a
    docs-mention row — per the ad-hoc/non-authoritative status CLAUDE.md
    §15 gives that tree."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_gone.py"
    _write(target, "def test_x(): pass\n")
    _write(repo / "research" / "ops" / "note.md", "test_gone.py was mentioned here\n")
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "research" not in result.stdout


# ---------------------------------------------------------------------------
# Common-basename skip
# ---------------------------------------------------------------------------


def test_common_basename_skipped_by_default_with_a_note(tmp_path: Path) -> None:
    """conftest.py is common enough that a bare-basename search is noise —
    skipped by default, reported with a note, never blocks the push."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "conftest.py"
    _write(target, "import pytest\n")
    _write(
        repo / "apps" / "other" / "tests" / "runner.sh",
        "#!/bin/sh\ncat conftest.py\n",
    )
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete conftest")

    result = _run(repo, "--base", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SKIPPED-common-basename" in result.stdout


def test_common_basename_include_common_forces_the_scan(tmp_path: Path) -> None:
    """--include-common must force the same scenario above to find the real
    (over-matching, by design) hit."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "conftest.py"
    _write(target, "import pytest\n")
    _write(
        repo / "apps" / "other" / "tests" / "runner.sh",
        "#!/bin/sh\ncat conftest.py\n",
    )
    base = _commit_all(repo, "base")

    target.unlink()
    _commit_all(repo, "delete conftest")

    result = _run(repo, "--base", base, "--include-common")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "runner.sh" in result.stdout


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


def test_explicit_paths_mode_bypasses_git_diff(tmp_path: Path) -> None:
    """Positional paths are treated as the deleted-file set directly,
    without computing a git diff at all."""
    repo = _init_repo(tmp_path)
    target = repo / "apps" / "backend-rag" / "tests" / "test_x.py"
    _write(target, "def test_x(): pass\n")
    _write(repo / "Makefile", "test:\n\tpytest apps/backend-rag/tests/test_x.py\n")
    _commit_all(repo, "base")
    target.unlink()
    _commit_all(repo, "delete")

    result = _run(repo, "apps/backend-rag/tests/test_x.py")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Makefile" in result.stdout


def test_usage_error_bad_base_ref_exits_2(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _write(repo / "README.md", "hello\n")
    _commit_all(repo, "base")

    result = _run(repo, "--base", "definitely-not-a-real-ref-xyz")
    assert result.returncode == 2, result.stdout + result.stderr


def test_help_exits_0_and_mentions_the_overmatch_proxy_warning() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "over-match" in result.stdout.lower() or "overmatch" in result.stdout.lower()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
