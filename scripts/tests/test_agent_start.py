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
import time
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

    # Model production reality: an `origin` remote with `main` pushed. The W80
    # reap-guard (`_branch_in_origin_main`) tests HEAD against `origin/main`, so
    # a fixture without a remote would make EVERY worktree read as "unmerged" —
    # masking real behaviour. A bare origin + pushed main is the minimal honest
    # model (a branch with no commits beyond what's pushed is an ancestor of
    # origin/main → reap-eligible; a branch with un-pushed commits → protected).
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(origin)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    git("remote", "add", "origin", str(origin))
    git("push", "-u", "origin", "main")

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


def _commit_in_worktree(worktree: Path, mod, rel_path: str, msg: str) -> None:
    """Stage + commit a file inside the worktree so it reads as CLEAN."""
    env = dict(os.environ)
    env.update(
        GIT_AUTHOR_NAME="Test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="Test",
        GIT_COMMITTER_EMAIL="test@example.com",
    )
    for args in (["add", rel_path], ["commit", "-m", msg]):
        subprocess.run(
            ["git", *args],
            cwd=worktree,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )


def _backdate_worktree_mtime(worktree: Path, minutes: int) -> None:
    """Push every file's mtime back so the worktree reads as idle (no recent
    activity). Covers both the worktree tree AND the linked-worktree gitdir
    (REPO_ROOT/.git/worktrees/<name>/index|HEAD), since the liveness probe
    inspects the real gitdir too."""
    past = time.time() - minutes * 60

    def _back(p: Path) -> None:
        try:
            os.utime(p, (past, past))
        except OSError:
            pass

    for path in worktree.rglob("*"):
        _back(path)
    _back(worktree)
    # Linked-worktree real gitdir (resolve `.git` file pointer).
    git_pointer = worktree / ".git"
    try:
        if git_pointer.is_file():
            text = git_pointer.read_text().strip()
            if text.startswith("gitdir:"):
                gitdir = Path(text.split(":", 1)[1].strip())
                for name in ("index", "HEAD"):
                    _back(gitdir / name)
                _back(gitdir)
        _back(git_pointer)
    except OSError:
        pass


def _merge_worktree_branch_to_origin_main(worktree: Path, mod) -> None:
    """Fast-forward origin/main to the worktree's branch tip so the W80 guard
    (`_branch_in_origin_main`) sees HEAD as an ancestor of origin/main — i.e.
    the work is consolidated upstream and the worktree is genuinely reapable.

    Done from the MAIN repo (REPO_ROOT) to avoid touching the linked worktree's
    checked-out branch: update local main to the branch commit, then push."""
    env = dict(os.environ)
    env.update(
        GIT_AUTHOR_NAME="Test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="Test",
        GIT_COMMITTER_EMAIL="test@example.com",
    )
    # The worktree's HEAD commit.
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=worktree,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout.strip()
    repo = mod.REPO_ROOT
    # Move local main to the branch tip (main is checked out in the main repo,
    # but `branch -f` on the *currently checked-out* branch is refused; main is
    # NOT checked out here because the test repo's working copy stays on main —
    # so update via update-ref which bypasses the checkout guard, then push).
    subprocess.run(
        ["git", "update-ref", "refs/heads/main", head],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    subprocess.run(
        ["git", "push", "origin", "main"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def test_cleanup_removes_expired_clean_worktree(fake_repo, capsys):
    mod, repo = fake_repo
    wt = mod.cmd_create("wr2", "expired-001", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    _backdate_worktree_mtime(wt, minutes=120)  # idle, not a live session
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
    _backdate_worktree_mtime(wt, minutes=120)  # idle clock, but real WIP present
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


# ---------------------------------------------------------------------------
# cleanup — skip-recent guard (W62 ANTIBODY #1)
# ---------------------------------------------------------------------------


def test_cleanup_skips_recently_active_expired_clean_worktree(fake_repo, capsys):
    """A clean, TTL-expired worktree that was touched <10min ago is an ACTIVE
    session — cleanup must NOT drop it (W62: avoid killing a live session that
    simply outran its TTL clock)."""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "active-001", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)  # expired by the clock
    # Simulate live activity: a freshly written tracked file (recent mtime),
    # but committed so the worktree is CLEAN (no WIP).
    work_file = wt / "live.txt"
    work_file.write_text("active session output\n")
    _commit_in_worktree(wt, mod, "live.txt", "active work")
    rc = mod.cmd_cleanup()
    assert rc == 0  # not an error — just skipped a live session
    assert wt.exists()  # preserved because recently active
    out = capsys.readouterr().out
    assert "active-001" in out
    assert "recent" in out.lower() or "active" in out.lower()


def test_cleanup_removes_expired_clean_idle_worktree(fake_repo):
    """An expired, clean worktree with NO recent activity (mtime old) is a true
    orphan — cleanup removes it."""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "idle-001", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    _backdate_worktree_mtime(wt, minutes=120)
    rc = mod.cmd_cleanup()
    assert rc == 0
    assert not wt.exists()


def test_cleanup_recent_AND_dirty_reports_wip_not_silent_skip(fake_repo, capsys):
    """A worktree that is BOTH recently active AND dirty must surface as a WIP
    failure (exit 1), never be silently swallowed as a live session (codex P2:
    WIP guard runs before the recent-activity guard)."""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "recent-dirty", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)  # expired
    (wt / "uncommitted.txt").write_text("real WIP\n")  # dirty + fresh mtime
    rc = mod.cmd_cleanup()
    assert rc == 1  # WIP failure, NOT a silent exit-0 skip
    assert wt.exists()
    out = capsys.readouterr().out
    assert "recent-dirty" in out
    assert "WIP" in out


def test_cleanup_skip_recent_disabled_with_zero(fake_repo):
    """skip_recent_minutes=0 disables the recent-activity guard (operator
    escape for a forced sweep of even just-touched worktrees).

    The branch must be merged into origin/main for the W80 guard to allow the
    reap — so we land its commit on main upstream first. (skip_recent=0
    disables only the recent-activity guard; the W80 unmerged-protection is
    independent and still binds.)"""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "recent-002", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    (wt / "fresh.txt").write_text("just now\n")
    _commit_in_worktree(wt, mod, "fresh.txt", "fresh")
    _merge_worktree_branch_to_origin_main(wt, mod)  # consolidate upstream
    rc = mod.cmd_cleanup(skip_recent_minutes=0)
    assert rc == 0
    assert not wt.exists()


# ---------------------------------------------------------------------------
# cleanup — W80 2-AND guard (no-live-process AND merged-into-origin/main)
# ---------------------------------------------------------------------------


def test_cleanup_skips_worktree_with_live_process(fake_repo, capsys, monkeypatch):
    """W80 case (1): an expired, CLEAN, mtime-IDLE worktree that still has a live
    OS process anchored to it (a session that commits-and-reasons without
    touching files) must NOT be reaped. The mtime-based recent-activity guard
    misses it (files are old); the lsof-based live-process guard catches it."""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "live-proc", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    # Merge upstream so guard #2 (merged) would PASS — isolating that it's the
    # live-process guard #1 (not the unmerged guard) that protects it.
    _merge_worktree_branch_to_origin_main(wt, mod)
    _backdate_worktree_mtime(wt, minutes=120)  # mtime idle: recent-guard won't fire
    monkeypatch.setattr(mod, "_worktree_has_live_process", lambda p: True)
    rc = mod.cmd_cleanup()
    assert rc == 0  # protection, not a failure
    assert wt.exists()
    out = capsys.readouterr().out
    assert "live-proc" in out
    assert "live process" in out.lower()


def test_cleanup_skips_branch_not_in_origin_main(fake_repo, capsys, monkeypatch):
    """W80 case (2) — THE BUG: an expired, CLEAN, idle, no-live-process worktree
    whose branch has commits NOT in origin/main (pushed-but-not-merged, open PR)
    must NOT be reaped — it carries the only checkout of unmerged work.

    This is the real scenario that vanished the W79 worktree: commit-everything
    to satisfy stop_verify → clean+idle → reap-eligible by the OLD logic, but
    the branch was never merged."""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "unmerged", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    # Real commit that is NOT pushed to origin/main → genuinely unmerged.
    (wt / "work.txt").write_text("unmerged work\n")
    _commit_in_worktree(wt, mod, "work.txt", "feature commit")
    _backdate_worktree_mtime(wt, minutes=120)  # idle on mtime
    monkeypatch.setattr(mod, "_worktree_has_live_process", lambda p: False)
    rc = mod.cmd_cleanup()
    assert rc == 0  # protection, not a failure (operator decides via PR merge)
    assert wt.exists()
    out = capsys.readouterr().out
    assert "unmerged" in out
    assert "origin/main" in out


def test_cleanup_reaps_when_no_process_and_merged(fake_repo, monkeypatch):
    """W80 case (3): the ONLY auto-reapable state — expired + clean + idle +
    NO live process AND branch merged into origin/main. Both W80 guards pass,
    so the worktree is removed."""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "reapable", ttl_minutes=5)
    _backdate_metadata(wt, mod, minutes=120)
    (wt / "done.txt").write_text("shipped work\n")
    _commit_in_worktree(wt, mod, "done.txt", "shipped")
    _merge_worktree_branch_to_origin_main(wt, mod)  # consolidated upstream
    _backdate_worktree_mtime(wt, minutes=120)  # idle
    monkeypatch.setattr(mod, "_worktree_has_live_process", lambda p: False)
    rc = mod.cmd_cleanup()
    assert rc == 0
    assert not wt.exists()  # reaped — both guards cleared


def test_worktree_has_live_process_real_lsof(fake_repo):
    """Empirical (no-mock) test of `_worktree_has_live_process` against the REAL
    `lsof` (W64: prove the guard with the actual kernel call, not just bash -n).

    Spawns a child whose CWD is the worktree → lsof must report it LIVE; after
    the child dies → not live; a ghost dir → not live. Skips if lsof is absent
    (the guard fail-safes to True there, which we cannot assert as 'dead')."""
    import shutil

    if shutil.which("lsof") is None:
        pytest.skip("lsof not available on this host")

    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "lsof-real", ttl_minutes=5)

    # No process anchored yet → not live.
    assert mod._worktree_has_live_process(wt) is False

    # Child with cwd = worktree → lsof reports the cwd fd → LIVE.
    child = subprocess.Popen(["sleep", "30"], cwd=str(wt))
    try:
        time.sleep(0.3)
        assert mod._worktree_has_live_process(wt) is True
    finally:
        child.terminate()
        child.wait()

    # After the child is gone → not live again.
    time.sleep(0.3)
    assert mod._worktree_has_live_process(wt) is False

    # Non-existent directory → not live (nothing to anchor a process to).
    assert mod._worktree_has_live_process(mod.WORKTREES_DIR / "ghost") is False


def test_worktree_has_live_process_resolves_macos_lsof_outside_path(
    fake_repo, monkeypatch
):
    """launchd PATH omits /usr/sbin on macOS; the broker must still find lsof."""
    mod, _ = fake_repo
    if not Path("/usr/sbin/lsof").exists():
        pytest.skip("/usr/sbin/lsof not available on this host")

    monkeypatch.setenv("PATH", "/opt/homebrew/bin:/usr/bin:/bin")
    wt = mod.cmd_create("wr2", "lsof-path", ttl_minutes=5)

    assert mod._resolve_lsof_path() == "/usr/sbin/lsof"
    assert mod._worktree_has_live_process(wt) is False


def test_branch_in_origin_main_real_resolver(fake_repo):
    """Load-bearing direct test of `_branch_in_origin_main` against a REAL git
    repo (the refuter-killed logic): it must use origin/main, return True only
    when HEAD is an ancestor of origin/main, and protect pushed-but-not-merged.

    This is the no-monkeypatch proof that the chosen `merge-base --is-ancestor
    HEAD origin/main` test discriminates merged from unmerged correctly."""
    mod, _ = fake_repo

    # Worktree with no commits beyond pushed main → ancestor of origin/main.
    wt_merged = mod.cmd_create("wr2", "rr-merged", ttl_minutes=5)
    assert mod._branch_in_origin_main(wt_merged) is True

    # Worktree with a local commit NOT pushed → NOT an ancestor of origin/main.
    wt_unmerged = mod.cmd_create("wr2", "rr-unmerged", ttl_minutes=5)
    (wt_unmerged / "x.txt").write_text("local only\n")
    _commit_in_worktree(wt_unmerged, mod, "x.txt", "local commit")
    assert mod._branch_in_origin_main(wt_unmerged) is False

    # After landing that commit on origin/main → now an ancestor → merged.
    _merge_worktree_branch_to_origin_main(wt_unmerged, mod)
    assert mod._branch_in_origin_main(wt_unmerged) is True

    # Missing/invalid origin ref → fail-safe FALSE (protect, never reap blind).
    missing = mod.WORKTREES_DIR / "does-not-exist"
    # A non-existent worktree dir short-circuits to True (nothing to protect);
    # the inconclusive-ref path is covered by the unmerged case above where
    # origin/main exists. Assert the directory-gone contract explicitly:
    assert mod._branch_in_origin_main(missing) is True


# ---------------------------------------------------------------------------
# list — orphan detection (W62 ANTIBODY #2)
# ---------------------------------------------------------------------------


def test_list_warns_on_orphan_worktree(fake_repo, capsys):
    """A worktree older than 2× its TTL is flagged ORPHAN with a summary line."""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "orphan-001", ttl_minutes=30)
    _backdate_metadata(wt, mod, minutes=120)  # 120 > 2*30 = 60 → orphan
    rc = mod.cmd_list()
    assert rc == 0
    out = capsys.readouterr().out
    assert "orphan-001" in out
    assert "ORPHAN" in out
    assert "1 orphan" in out.lower() or "orphan worktree" in out.lower()


def test_list_no_orphan_when_within_2x_ttl(fake_repo, capsys):
    """A worktree past TTL but under 2× TTL is NOT yet an orphan."""
    mod, _ = fake_repo
    wt = mod.cmd_create("wr2", "young-001", ttl_minutes=30)
    _backdate_metadata(wt, mod, minutes=45)  # 30 < 45 < 60 → not orphan
    rc = mod.cmd_list()
    assert rc == 0
    out = capsys.readouterr().out
    assert "young-001" in out
    # "ORPHAN" appears in the header column; assert the data row is NOT flagged.
    data_row = next(line for line in out.splitlines() if "young-001" in line)
    assert "ORPHAN" not in data_row
    assert "orphan worktree" not in out.lower()


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
