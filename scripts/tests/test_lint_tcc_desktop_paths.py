"""Tests for scripts/lint_tcc_desktop_paths.py (superscar #1, W84/TCC variant).

Scar #3 discipline: the standing CI guard ships with its own guilt AND
innocence proof.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "lint_tcc_desktop_paths.py"
_spec = importlib.util.spec_from_file_location("lint_tcc_desktop_paths", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint)


# ---------------------------------------------------------------- helpers


def make_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    return repo


def git_add(repo: Path, *relpaths: str) -> None:
    subprocess.run(["git", "add", *relpaths], cwd=repo, check=True)


# ---------------------------------------------------------------- guilt/innocence


def test_guilt_tracked_shell_payload_with_desktop_path_is_caught(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "wrapper.sh").write_text("REPO=\"$HOME/Desktop/nuzantara\"\n")
    git_add(repo, "wrapper.sh")
    rc = lint.main(["--repo-root", str(repo), "--allowlist", str(tmp_path / "absent-allowlist.txt")])
    assert rc == 1


def test_innocence_clean_payload_exits_zero(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "wrapper.sh").write_text("REPO=\"$HOME/nuzantara\"\n")
    git_add(repo, "wrapper.sh")
    rc = lint.main(["--repo-root", str(repo), "--allowlist", str(tmp_path / "absent-allowlist.txt")])
    assert rc == 0


def test_innocence_allowlisted_path_never_flagged(tmp_path: Path) -> None:
    """A file with a genuine hit is silent when declared in the allowlist —
    the guard-test-corpus / historical-record exception mechanism."""
    repo = make_git_repo(tmp_path)
    (repo / "legacy_test.py").write_text('MARKER = "/Users/x/Desktop/nuzantara/scripts/x.sh"\n')
    git_add(repo, "legacy_test.py")
    allowlist = tmp_path / "allowlist.txt"
    allowlist.write_text("# deliberate exception\nlegacy_test.py\n")
    rc = lint.main(["--repo-root", str(repo), "--allowlist", str(allowlist)])
    assert rc == 0


def test_innocence_out_of_scope_extension_not_flagged(tmp_path: Path) -> None:
    """A .md/.json file citing the old path is NOT in this lint's scope
    (deliberately narrower than the one-time sweep) — only *.sh/*.py/*.plist."""
    repo = make_git_repo(tmp_path)
    (repo / "notes.md").write_text("cd ~/Desktop/nuzantara\n")
    (repo / "data.json").write_text('{"path": "~/Desktop/nuzantara"}\n')
    git_add(repo, "notes.md", "data.json")
    rc = lint.main(["--repo-root", str(repo), "--allowlist", str(tmp_path / "absent-allowlist.txt")])
    assert rc == 0


def test_guilt_plist_payload_caught() -> None:
    assert ".plist" in lint.LINT_EXTENSIONS
    assert ".sh" in lint.LINT_EXTENSIONS
    assert ".py" in lint.LINT_EXTENSIONS
    assert ".md" not in lint.LINT_EXTENSIONS
    assert ".json" not in lint.LINT_EXTENSIONS


# ---------------------------------------------------------------- symlinks


def test_symlink_guilt_target_crossing_desktop_is_caught(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path)
    real = repo / "infra" / "launchagents"
    real.mkdir(parents=True)
    (real / "x.plist").write_text("<plist/>\n")
    link_target = "/Users/nuzantara/Desktop/nuzantara/infra/launchagents/x.plist"
    link = repo / "linked.plist"
    link.symlink_to(link_target)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    rc = lint.main(["--repo-root", str(repo), "--allowlist", str(tmp_path / "absent-allowlist.txt")])
    assert rc == 1


def test_symlink_innocence_target_elsewhere_not_flagged(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path)
    real = repo / "infra" / "launchagents"
    real.mkdir(parents=True)
    (real / "x.plist").write_text("<plist/>\n")
    link = repo / "linked.plist"
    link.symlink_to(str((real / "x.plist").resolve()))
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    rc = lint.main(["--repo-root", str(repo), "--allowlist", str(tmp_path / "absent-allowlist.txt")])
    assert rc == 0


# ---------------------------------------------------------------- exit contract


def test_blind_scan_git_failure_returns_two(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    rc = lint.main(["--repo-root", str(not_a_repo), "--allowlist", str(tmp_path / "absent-allowlist.txt")])
    assert rc == 2


def test_allowlist_unreadable_returns_four(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "wrapper.sh").write_text("REPO=\"$HOME/nuzantara\"\n")
    git_add(repo, "wrapper.sh")
    bad_allowlist = tmp_path / "allowlist-dir-not-file"
    bad_allowlist.mkdir()  # a directory where a file is expected -> OSError on read
    rc = lint.main(["--repo-root", str(repo), "--allowlist", str(bad_allowlist)])
    assert rc == 4


# ---------------------------------------------------------------- real repo smoke (documents current state)


def test_real_repo_allowlist_file_parses_and_scan_is_clean() -> None:
    """The actual allowlist shipped in this PR: every declared path must exist
    (no phantom entries — scar #6 discipline) and the real repo tree must be
    clean under it (this test doubles as CI's own dogfood check when run from
    a checkout that has the allowlist committed)."""
    repo_root = _MODULE_PATH.resolve().parents[2]
    allowlist_path = repo_root / "infra" / "tcc-desktop-paths" / "allowlist.txt"
    if not allowlist_path.exists():
        return  # nothing to dogfood yet in this checkout (pre-merge worktree without the file)
    result = lint.scan(repo_root, allowlist_path)
    assert result["errors"] == []
    assert result["violations"] == [], result["violations"]
