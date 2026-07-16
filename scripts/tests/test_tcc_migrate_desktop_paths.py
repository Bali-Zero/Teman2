"""Tests for scripts/tcc_migrate_desktop_paths.py (W84 TCC-Desktop-path sweep).

Scar #3 discipline applied to the migrator itself: every detection arm gets a
GUILT case (the disease IS caught/fixed) and an INNOCENCE case (the adjacent
legitimate state is left alone). Two live gaps found AFTER the tool was first
handed off are pinned here as regressions:

  - relparts bug: running the tool from inside a worktree
    (`.worktrees/<lane>/...`) must not archaeology-skip every file just
    because ".worktrees" appears in the scan's own absolute path prefix.
  - symlink gap: a symlink whose raw TARGET STRING crosses Desktop/nuzantara
    is its own finding class — launchd resolves the link, not whatever the
    target file's content says. The tool must never silently skip symlinks,
    and must never follow one to read/rewrite its target as a side effect.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "tcc_migrate_desktop_paths.py"
_spec = importlib.util.spec_from_file_location("tcc_migrate_desktop_paths", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


# ---------------------------------------------------------------- helpers


def make_git_repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    return repo


def git_add(repo: Path, *relpaths: str) -> None:
    subprocess.run(["git", "add", *relpaths], cwd=repo, check=True)


# ---------------------------------------------------------------- pattern anchoring


def test_pattern_guilt_nuzantara_and_deploy() -> None:
    assert mod.PATTERN.sub(mod.REPLACEMENT, "cd ~/Desktop/nuzantara/apps") == "cd ~/nuzantara/apps"
    assert (
        mod.PATTERN.sub(mod.REPLACEMENT, "~/Desktop/nuzantara-deploy/scripts")
        == "~/nuzantara-deploy/scripts"
    )


def test_pattern_innocence_sibling_checkouts_untouched() -> None:
    for sibling in ("Desktop/nuzantara-old", "Desktop/nuzantara2", "Desktop/nuzantara-deploy-bak"):
        text = f"cd ~/{sibling}/apps"
        assert mod.PATTERN.sub(mod.REPLACEMENT, text) == text, sibling


# ---------------------------------------------------------------- git-scope check/apply


def test_git_scope_check_guilt_finds_hit(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "run.sh").write_text("cd ~/Desktop/nuzantara && ./x\n")
    git_add(repo, "run.sh")
    rc = mod.main(["--git-scope", "--repo-root", str(repo), "--check"])
    assert rc == 1


def test_git_scope_innocence_clean_repo_exits_zero(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "run.sh").write_text("cd ~/nuzantara && ./x\n")
    git_add(repo, "run.sh")
    rc = mod.main(["--git-scope", "--repo-root", str(repo), "--check"])
    assert rc == 0


def test_git_scope_apply_rewrites_content(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path)
    (repo / "run.sh").write_text("REPO=$HOME/Desktop/nuzantara\n")
    git_add(repo, "run.sh")
    rc = mod.main(["--git-scope", "--repo-root", str(repo), "--apply"])
    assert rc == 0
    assert (repo / "run.sh").read_text() == "REPO=$HOME/nuzantara\n"
    backups = list(repo.glob("run.sh.bak-tcc-*"))
    assert len(backups) == 1
    assert backups[0].read_text() == "REPO=$HOME/Desktop/nuzantara\n"


def test_exclude_file_guilt_and_innocence(tmp_path: Path) -> None:
    """A file listed in --exclude-file is never touched or reported even
    though it matches; an UNLISTED sibling with the same content still is."""
    repo = make_git_repo(tmp_path)
    (repo / "declared.sh").write_text("cd ~/Desktop/nuzantara\n")
    (repo / "undeclared.sh").write_text("cd ~/Desktop/nuzantara\n")
    git_add(repo, "declared.sh", "undeclared.sh")
    exclude_file = tmp_path / "allow.txt"
    exclude_file.write_text("declared.sh\n# a comment\n\n")

    rc = mod.main([
        "--git-scope", "--repo-root", str(repo),
        "--exclude-file", str(exclude_file), "--check",
    ])
    assert rc == 1  # undeclared.sh still trips the check
    assert (repo / "declared.sh").read_text() == "cd ~/Desktop/nuzantara\n"  # untouched


# ---------------------------------------------------------------- worktree-safety regression


def test_relparts_scan_root_not_archaeology_skipped_when_ancestor_has_worktrees(tmp_path: Path) -> None:
    """Regression: SKIP_DIR_PARTS must be checked against the path RELATIVE to
    the scan root, not the absolute filesystem path. A repo that happens to
    live under a `.worktrees` ancestor (exactly the shape of an agent
    session's own worktree) must not have every file archaeology-skipped just
    because ".worktrees" appears somewhere in the absolute path prefix."""
    fake_worktrees_ancestor = tmp_path / ".worktrees" / "some-lane"
    repo = make_git_repo(fake_worktrees_ancestor, name="repo")
    (repo / "run.sh").write_text("cd ~/Desktop/nuzantara\n")
    git_add(repo, "run.sh")
    rc = mod.main(["--git-scope", "--repo-root", str(repo), "--check"])
    assert rc == 1, "hit must still be found even though '.worktrees' is an ancestor of repo_root"


# ---------------------------------------------------------------- symlink gap (coordinator finding)


def test_symlink_guilt_target_crossing_desktop_is_caught_and_apply_repoints(tmp_path: Path) -> None:
    home = tmp_path / "home"
    agents = home / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    # target need not exist on disk — launchd resolves the link string regardless.
    old_target = str(home / "Desktop" / "nuzantara" / "infra" / "launchagents" / "x.plist")
    link = agents / "com.test.watchdog.plist"
    link.symlink_to(old_target)

    rc = mod.main(["--home", str(home), "--roots", "Library/LaunchAgents", "--check"])
    assert rc == 1, "a symlink whose target crosses Desktop/nuzantara must trip --check"

    rc = mod.main(["--home", str(home), "--roots", "Library/LaunchAgents", "--apply"])
    assert rc == 0
    assert link.is_symlink()
    new_target = os.readlink(link)
    assert new_target == str(home / "nuzantara" / "infra" / "launchagents" / "x.plist")

    # backup is itself a symlink to the OLD target, not a content copy
    backups = list(agents.glob("com.test.watchdog.plist.bak-tcc-*"))
    assert len(backups) == 1
    assert backups[0].is_symlink()
    assert os.readlink(backups[0]) == old_target


def test_symlink_innocence_target_elsewhere_left_alone(tmp_path: Path) -> None:
    home = tmp_path / "home"
    agents = home / "Library" / "LaunchAgents"
    agents.mkdir(parents=True)
    other_target = str(home / "scripts" / "unrelated.sh")
    link = agents / "com.test.unrelated.plist"
    link.symlink_to(other_target)
    (home / "scripts").mkdir(parents=True, exist_ok=True)
    (home / "scripts" / "unrelated.sh").write_text("#!/bin/bash\necho hi\n")

    rc = mod.main(["--home", str(home), "--roots", "Library/LaunchAgents", "--check"])
    assert rc == 0, "a symlink pointing elsewhere must not be flagged"
    assert os.readlink(link) == other_target  # untouched


def test_symlink_never_follows_to_double_write_target(tmp_path: Path) -> None:
    """Walking a symlink whose target crosses Desktop must rewrite the LINK,
    never open/rewrite the file it points at as a side effect."""
    home = tmp_path / "home"
    agents = home / "Library" / "LaunchAgents"
    real_dir = home / "Desktop" / "nuzantara" / "infra" / "launchagents"
    real_dir.mkdir(parents=True)
    agents.mkdir(parents=True)
    real_file = real_dir / "x.plist"
    real_file.write_text("<!-- Desktop/nuzantara content, untouched by link walk -->\n")
    link = agents / "com.test.watchdog.plist"
    link.symlink_to(str(real_file))

    mod.main(["--home", str(home), "--roots", "Library/LaunchAgents", "--apply"])

    # the LINK moved (target string rewritten); the FILE it pointed at is untouched
    # by this walk (Library/LaunchAgents was the only root scanned).
    assert real_file.read_text() == "<!-- Desktop/nuzantara content, untouched by link walk -->\n"


# ---------------------------------------------------------------- blind-scan guard


def test_blind_scan_git_ls_files_failure_returns_two(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    rc = mod.main(["--git-scope", "--repo-root", str(not_a_repo), "--check"])
    assert rc == 2


def test_blind_scan_absent_home_roots_returns_two(tmp_path: Path) -> None:
    empty_home = tmp_path / "empty-home"
    empty_home.mkdir()
    rc = mod.main(["--home", str(empty_home)])
    assert rc == 2
