"""Tests for the tracked and physical-workspace root guards."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_GUARD = REPO_ROOT / "scripts" / "root_guard.py"
PRE_COMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / "README.md").write_text("# fixture\n", encoding="utf-8")
    (repo / "apps").mkdir()
    (repo / "apps" / ".gitkeep").write_text("", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo), "add", "README.md", "apps/.gitkeep"],
        check=True,
    )
    return repo


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT_GUARD), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )


def test_workspace_allows_tracked_entries_and_local_dependencies(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "node_modules").mkdir()
    (repo / ".venv").mkdir()
    (repo / ".mcp.json").write_text("{}\n", encoding="utf-8")

    result = _run(repo, "--workspace")

    assert result.returncode == 0, result.stderr


def test_workspace_blocks_untracked_root_file(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "HANDOFF-task.md").write_text("temporary\n", encoding="utf-8")

    result = _run(repo, "--workspace")

    assert result.returncode == 1
    assert "HANDOFF-task.md" in result.stderr


def test_workspace_blocks_untracked_root_directory(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "drafts").mkdir()

    result = _run(repo, "--workspace")

    assert result.returncode == 1
    assert "drafts/" in result.stderr


def test_workspace_blocks_ignored_root_artifact(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / ".gitignore").write_text("export.zip\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", ".gitignore"], check=True)
    (repo / "export.zip").write_text("generated\n", encoding="utf-8")

    result = _run(repo, "--workspace")

    assert result.returncode == 1
    assert "export.zip" in result.stderr


def test_tracked_check_remains_independent_of_local_state(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "scratch.txt").write_text("ignored by tracked-only mode\n", encoding="utf-8")

    result = _run(repo, "--check")

    assert result.returncode == 0, result.stderr


def test_workspace_guard_is_armed_in_pre_commit() -> None:
    config = PRE_COMMIT_CONFIG.read_text(encoding="utf-8")

    assert "entry: python scripts/root_guard.py --workspace" in config
    assert "id: root-workspace-guard" in config
