"""SOTA L1 (2026-05-24) — tests for scripts/agent_start.py (Worktree Broker).

Coverage matrix:
- create worktree happy path (branch + metadata + symlinks + stdout contract)
- list shows entries with WIP detection
- cleanup skips worktree with uncommitted WIP and emits WARN
- cleanup removes worktree past TTL when clean
- release fails gracefully when branch is not merged into base
- release succeeds when branch is merged
- kill-switch (AGENT_BROKER_ENABLED=false) blocks create/cleanup/release but not list
- input validation rejects malformed lane / task-id

Tests use a temporary git repo + temporary HOME via monkeypatch, so they never
touch the real ~/Desktop/nuzantara checkout or ~/logs/.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "agent_start.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _load_module(repo_root: Path):
    """Reload agent_start under a fresh REPO_ROOT (overrides module constants)."""
    spec = importlib.util.spec_from_file_location("agent_start_under_test", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Register before exec_module so dataclass __module__ lookups succeed
    # (the @dataclass decorator does sys.modules[cls.__module__] in 3.11).
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    mod.REPO_ROOT = repo_root
    mod.WORKTREES_DIR = repo_root / ".worktrees"
    return mod


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Redirect HOME so log handler init writes inside tmp."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_BROKER_ENABLED", raising=False)
    return home


@pytest.fixture
def fake_repo(tmp_path, fake_home, monkeypatch):
    """Create a fresh git repo with a main branch + 1 commit, return module + path."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # git init + commit (need identity for the commit to work).
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "Test"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "Test"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"

    def git(*args):
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

    git("init", "-b", "main")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (repo / "README.md").write_text("seed\n")
    git("add", "README.md")
    git("commit", "-m", "seed")

    mod = _load_module(repo)
    # Patch the module's subprocess git wrapper cwd default to point at our repo.
    return mod, repo


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_create_happy_path_writes_metadata_and_branch(fake_repo):
    mod, repo = fake_repo
    out = mod.cmd_create("wr2", "happy-001", ttl_minutes=30)
    assert out.is_dir()
    assert out == repo / ".worktrees" / "wr2-happy-001"

    meta_path = out / mod.TASK_METADATA_FILENAME
    assert meta_path.is_file()
    data = json.loads(meta_path.read_text())
    assert data["task_id"] == "happy-001"
    assert data["lane"] == "wr2"
    assert data["branch"].endswith("/wr2/happy-001")
    assert data["branch"].startswith("agent/")
    assert data["ttl_minutes"] == 30
    assert data["base_branch"] == "main"

    # Branch exists.
    branches = subprocess.run(
        ["git", "branch", "--list"], cwd=repo, capture_output=True, text=True
    ).stdout
    assert data["branch"] in branches


def test_create_symlinks_only_when_targets_exist(fake_repo):
    mod, repo = fake_repo
    # Create one of the SYMLINK_TARGETS in main so the symlink is exercised.
    (repo / "apps" / "backend-rag").mkdir(parents=True)
    (repo / "apps" / "backend-rag" / ".env").write_text("FAKE=1\n")
    out = mod.cmd_create("infra", "sym-test")
    link = out / "apps" / "backend-rag" / ".env"
    assert link.is_symlink()
    # Resolves back to source.
    assert link.resolve() == (repo / "apps" / "backend-rag" / ".env").resolve()
    # Non-existent target (node_modules) is silently skipped (no broken link).
    assert not (out / "node_modules").exists()


def test_create_rejects_unknown_lane_by_default(fake_repo):
    mod, _ = fake_repo
    with pytest.raises(SystemExit) as exc:
        mod.cmd_create("notreal", "x")
    assert "unknown lane" in str(exc.value).lower()


def test_create_allows_unknown_lane_when_flagged(fake_repo):
    mod, _ = fake_repo
    out = mod.cmd_create("notreal", "x", allow_unknown_lane=True)
    assert out.is_dir()


def test_create_rejects_invalid_chars_in_task_id(fake_repo):
    mod, _ = fake_repo
    with pytest.raises(SystemExit):
        mod.cmd_create("wr2", "BAD/SLASH")
    with pytest.raises(SystemExit):
        mod.cmd_create("wr2", "_underscore")
    with pytest.raises(SystemExit):
        mod.cmd_create("wr2", "")


def test_create_refuses_duplicate_task_id(fake_repo):
    mod, _ = fake_repo
    mod.cmd_create("wr2", "dup-001")
    with pytest.raises(SystemExit) as exc:
        mod.cmd_create("wr2", "dup-001")
    assert "already exists" in str(exc.value).lower()


def test_create_blocked_by_kill_switch(fake_repo, monkeypatch):
    mod, _ = fake_repo
    monkeypatch.setenv("AGENT_BROKER_ENABLED", "false")
    with pytest.raises(SystemExit) as exc:
        mod.cmd_create("wr2", "killed")
    assert "disabled" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_empty(fake_repo, capsys):
    mod, _ = fake_repo
    rc = mod.cmd_list()
    assert rc == 0
    out = capsys.readouterr().out
    assert "no active worktrees" in out.lower()


def test_list_shows_created_entries(fake_repo, capsys):
    mod, _ = fake_repo
    mod.cmd_create("wr2", "list-001")
    mod.cmd_create("infra", "list-002")
    rc = mod.cmd_list()
    assert rc == 0
    out = capsys.readouterr().out
    assert "list-001" in out
    assert "list-002" in out
    assert "wr2" in out
    assert "infra" in out
    # Fresh worktree has only the metadata file (filtered) → WIP=no.
    assert "no" in out


def test_list_flags_wip(fake_repo, capsys):
    mod, _ = fake_repo
    out = mod.cmd_create("wr2", "wip-001")
    (out / "dirty.txt").write_text("uncommitted\n")
    mod.cmd_list()
    captured = capsys.readouterr().out
    assert "wip-001" in captured
    assert "yes" in captured  # WIP column


# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------


def _backdate_metadata(worktree: Path, mod, minutes: int) -> None:
    """Rewrite created_at to push the worktree past TTL."""
    meta_path = worktree / mod.TASK_METADATA_FILENAME
    data = json.loads(meta_path.read_text())
    backdated = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    data["created_at"] = backdated.strftime("%Y-%m-%dT%H:%M:%SZ")
    meta_path.write_text(json.dumps(data, indent=2, sort_keys=True))


def test_cleanup_removes_expired_clean_worktree(fake_repo, capsys):
    mod, repo = fake_repo
    wt = mod.cmd_create("wr2", "expired-001", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    rc = mod.cmd_cleanup()
    assert rc == 0
    assert not wt.exists()
    out = capsys.readouterr().out
    assert "expired-001" in out


def test_cleanup_skips_wip_with_warning(fake_repo, capsys):
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "wip-keep", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    (wt / "wip.txt").write_text("not committed\n")
    rc = mod.cmd_cleanup()
    assert rc == 1  # signals at least one skip
    assert wt.exists()  # WIP-safe
    out = capsys.readouterr().out
    assert "wip-keep" in out
    assert "WIP" in out or "wip" in out.lower()


def test_cleanup_force_removes_wip(fake_repo):
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "wip-force", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    (wt / "wip.txt").write_text("not committed\n")
    rc = mod.cmd_cleanup(force=True)
    assert rc == 0
    assert not wt.exists()


def test_cleanup_leaves_fresh_worktrees_alone(fake_repo):
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "fresh-001", ttl_minutes=60)
    rc = mod.cmd_cleanup()
    assert rc == 0
    assert wt.exists()


def test_cleanup_blocked_by_kill_switch(fake_repo, monkeypatch):
    mod, _ = fake_repo
    monkeypatch.setenv("AGENT_BROKER_ENABLED", "0")
    with pytest.raises(SystemExit):
        mod.cmd_cleanup()


# ---------------------------------------------------------------------------
# release
# ---------------------------------------------------------------------------


def test_release_fails_when_branch_not_merged(fake_repo):
    mod, repo = fake_repo
    wt = mod.cmd_create("wr2", "rel-001")
    # Add a commit on the new branch so it diverges from main.
    (wt / "new.txt").write_text("on branch\n")
    subprocess.run(["git", "add", "new.txt"], cwd=wt, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", "div"],
        cwd=wt,
        check=True,
    )
    with pytest.raises(SystemExit) as exc:
        mod.cmd_release("rel-001")
    msg = str(exc.value).lower()
    assert "not merged" in msg
    assert wt.exists()  # untouched


def test_release_succeeds_when_branch_merged(fake_repo):
    mod, repo = fake_repo
    wt = mod.cmd_create("wr2", "rel-002")
    # No new commits → branch is already at HEAD of main → considered merged.
    rc = mod.cmd_release("rel-002")
    assert rc == 0
    assert not wt.exists()


def test_release_force_overrides_unmerged(fake_repo):
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "rel-force")
    (wt / "new.txt").write_text("on branch\n")
    subprocess.run(["git", "add", "new.txt"], cwd=wt, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@e", "-c", "user.name=T", "commit", "-m", "div"],
        cwd=wt,
        check=True,
    )
    rc = mod.cmd_release("rel-force", force=True)
    assert rc == 0
    assert not wt.exists()


def test_release_unknown_task_errors(fake_repo):
    mod, _ = fake_repo
    with pytest.raises(SystemExit) as exc:
        mod.cmd_release("does-not-exist")
    assert "no worktree metadata" in str(exc.value).lower()


def test_release_blocked_by_kill_switch(fake_repo, monkeypatch):
    mod, _ = fake_repo
    mod.cmd_create("wr2", "rel-killed")
    monkeypatch.setenv("AGENT_BROKER_ENABLED", "off")
    with pytest.raises(SystemExit):
        mod.cmd_release("rel-killed")


# ---------------------------------------------------------------------------
# kill-switch + list still works
# ---------------------------------------------------------------------------


def test_list_works_under_kill_switch(fake_repo, monkeypatch, capsys):
    """--list is observational, must keep working when broker is disabled."""
    mod, _ = fake_repo
    mod.cmd_create("wr2", "ks-list")
    monkeypatch.setenv("AGENT_BROKER_ENABLED", "false")
    rc = mod.cmd_list()
    assert rc == 0
    out = capsys.readouterr().out
    assert "ks-list" in out


# ---------------------------------------------------------------------------
# Smoke: main() CLI entry
# ---------------------------------------------------------------------------


def test_main_create_writes_worktree_ready_line(fake_repo, capsys):
    mod, _ = fake_repo
    rc = mod.main(["--lane", "wr2", "--task-id", "main-smoke"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("WORKTREE_READY ")
    assert "wr2-main-smoke" in out


def test_main_missing_args_returns_nonzero(fake_repo, capsys):
    mod, _ = fake_repo
    rc = mod.main([])
    assert rc != 0


def test_main_conflicting_ops_rejected(fake_repo, capsys):
    mod, _ = fake_repo
    rc = mod.main(["--list", "--cleanup"])
    assert rc != 0
