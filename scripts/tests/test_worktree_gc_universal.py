"""Unit tests for scripts/worktree_gc_universal.py.

Tests the pure logic functions WITHOUT touching real worktrees. The module is
a script (not an importable package member), so it is loaded by path via
``importlib.util``. Git is mocked by monkeypatching ``_run_git``; the real
helper returns a ``subprocess.CompletedProcess`` whose ``.stdout`` callers read,
so the fakes return a small stand-in with a ``stdout`` attribute.

``TestGcIntegration`` is the exception: it exercises ``gc()`` end-to-end
against REAL git repos + REAL ``git worktree`` under ``tmp_path`` (never the
real ~/nuzantara checkout or its worktrees — W96 discipline), to prove the
2026-07-18 fixes empirically: dir-removal of an unpushed-but-clean
named-branch worktree preserves the branch ref (W88 cure, round-1), and
dir-removal of a clean detached-HEAD worktree preserves its commit via a
durable ref (BLOCKER B cure, round-2).
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent
SPEC_PATH = SCRIPT_DIR / "worktree_gc_universal.py"

_spec = importlib.util.spec_from_file_location("worktree_gc_universal", SPEC_PATH)
gc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gc)


class _FakeProc:
    """Stand-in for subprocess.CompletedProcess (only .stdout is consumed)."""

    def __init__(self, stdout: str):
        self.stdout = stdout
        self.returncode = 0


# ---------------------------------------------------------------------------
# _slug  (signature: _slug(path: str) -> str)
# ---------------------------------------------------------------------------


class TestSlug:
    def test_basic_path_becomes_safe_filename(self):
        slug = gc._slug("/Users/nuz/nuzantara/.worktrees/ops-foo")
        assert "/" not in slug
        # Pre-existing bug fixed 2026-07-18: the expected literal had a stray
        # "Desktop_" segment that never matched the input path above (a
        # pure copy-paste artifact, unrelated to the repo's actual
        # out-of-Desktop move — the input never contained "Desktop").
        assert slug == "Users_nuz_nuzantara_.worktrees_ops-foo"

    def test_trailing_slash_stripped(self):
        slug = gc._slug("/tmp/lane/")
        assert not slug.endswith("_")
        assert slug == "tmp_lane"

    def test_truncated_to_80_chars(self):
        long = "/" + "a" * 200
        assert len(gc._slug(long)) <= 80


# ---------------------------------------------------------------------------
# _kill_switch_active  (env WORKTREE_GC_ENABLED)
# ---------------------------------------------------------------------------


class TestKillSwitch:
    def test_false_disables(self, monkeypatch):
        monkeypatch.setenv(gc.KILL_SWITCH_ENV, "false")
        assert gc._kill_switch_active() is True

    def test_zero_disables(self, monkeypatch):
        monkeypatch.setenv(gc.KILL_SWITCH_ENV, "0")
        assert gc._kill_switch_active() is True

    def test_unset_is_enabled(self, monkeypatch):
        # Default value is "true" -> not in the disabled set -> active.
        monkeypatch.delenv(gc.KILL_SWITCH_ENV, raising=False)
        assert gc._kill_switch_active() is False

    def test_true_is_enabled(self, monkeypatch):
        monkeypatch.setenv(gc.KILL_SWITCH_ENV, "true")
        assert gc._kill_switch_active() is False


# ---------------------------------------------------------------------------
# _list_worktrees  (parses `git worktree list --porcelain`)
# ---------------------------------------------------------------------------


SAMPLE_PORCELAIN = """\
worktree /Users/nuz/nuzantara
HEAD a26da9e96aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
branch refs/heads/main

worktree /Users/nuz/nuzantara/.worktrees/ops-foo
HEAD 1111111111111111111111111111111111111111
branch refs/heads/feat/ops-foo

worktree /Users/nuz/nuzantara/.worktrees/detached-lane
HEAD 2222222222222222222222222222222222222222
detached

worktree /Users/nuz/nuzantara/.bare
bare
"""


class TestListWorktrees:
    def _entries(self, monkeypatch):
        monkeypatch.setattr(
            gc, "_run_git", lambda *a, **k: _FakeProc(SAMPLE_PORCELAIN)
        )
        return gc._list_worktrees()

    def test_counts_all_entries(self, monkeypatch):
        assert len(self._entries(monkeypatch)) == 4

    def test_branch_field_strips_refs_heads(self, monkeypatch):
        main = self._entries(monkeypatch)[0]
        assert main["branch"] == "main"
        assert main["detached"] is False
        assert main["bare"] is False
        assert main["head"] == "a26da9e96aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    def test_detached_flag(self, monkeypatch):
        det = self._entries(monkeypatch)[2]
        assert det["detached"] is True
        assert det["branch"] is None

    def test_bare_flag(self, monkeypatch):
        bare = self._entries(monkeypatch)[3]
        assert bare["bare"] is True

    def test_empty_input(self, monkeypatch):
        monkeypatch.setattr(gc, "_run_git", lambda *a, **k: _FakeProc(""))
        assert gc._list_worktrees() == []


# ---------------------------------------------------------------------------
# _has_real_dirty
# ---------------------------------------------------------------------------


class TestHasRealDirty:
    def test_clean_tree_is_not_dirty(self, monkeypatch):
        monkeypatch.setattr(gc, "_run_git", lambda *a, **k: _FakeProc(""))
        assert gc._has_real_dirty(Path("/tmp/wt")) is False

    def test_formatting_noise_is_not_dirty(self, monkeypatch):
        # status non-empty but whitespace-insensitive diff empty -> noise.
        def fake(args, **k):
            if args[0] == "status":
                return _FakeProc(" M scripts/foo.py")
            if args[0] == "diff":
                return _FakeProc("")  # --ignore-all-space yields nothing
            return _FakeProc("")

        monkeypatch.setattr(gc, "_run_git", fake)
        assert gc._has_real_dirty(Path("/tmp/wt")) is False

    def test_untracked_is_dirty(self, monkeypatch):
        def fake(args, **k):
            if args[0] == "status":
                return _FakeProc("?? scripts/new_file.py")
            return _FakeProc("")

        monkeypatch.setattr(gc, "_run_git", fake)
        assert gc._has_real_dirty(Path("/tmp/wt")) is True

    def test_real_tracked_change_is_dirty(self, monkeypatch):
        def fake(args, **k):
            if args[0] == "status":
                return _FakeProc(" M scripts/foo.py")
            if args[0] == "diff":
                return _FakeProc(
                    "diff --git a/scripts/foo.py b/scripts/foo.py\n+real change"
                )
            return _FakeProc("")

        monkeypatch.setattr(gc, "_run_git", fake)
        assert gc._has_real_dirty(Path("/tmp/wt")) is True


# ---------------------------------------------------------------------------
# _unpushed_commits (W88 honesty short-circuit, added 2026-07-18)
# ---------------------------------------------------------------------------


class _FakeProcRC:
    """Like _FakeProc but with an explicit returncode (needed for the
    ``git diff --quiet`` short-circuit, which signals via exit code)."""

    def __init__(self, stdout: str = "", returncode: int = 0):
        self.stdout = stdout
        self.returncode = returncode


class TestUnpushedCommits:
    def test_content_merged_short_circuits_to_zero(self, monkeypatch):
        # `git diff --quiet origin/main...HEAD` exits 0 -> no content diff ->
        # 0 even though a naive rev-list count would be non-zero (W88 cure).
        def fake(args, **k):
            if args[0] == "diff":
                return _FakeProcRC(returncode=0)
            if args[0] == "rev-list":
                return _FakeProcRC("7833")  # would-be inflated proxy count
            return _FakeProcRC()

        monkeypatch.setattr(gc, "_run_git", fake)
        assert gc._unpushed_commits(Path("/tmp/wt"), "feature/x") == 0

    def test_content_diff_falls_through_to_revlist_count(self, monkeypatch):
        # diff --quiet exits 1 (has diff) -> fall through to the raw proxy.
        def fake(args, **k):
            if args[0] == "diff":
                return _FakeProcRC(returncode=1)
            if args[0] == "rev-list":
                return _FakeProcRC("3")
            return _FakeProcRC()

        monkeypatch.setattr(gc, "_run_git", fake)
        assert gc._unpushed_commits(Path("/tmp/wt"), "feature/x") == 3

    def test_git_error_on_diff_falls_through_to_revlist(self, monkeypatch):
        def fake(args, **k):
            if args[0] == "diff":
                raise subprocess.CalledProcessError(1, args)
            if args[0] == "rev-list":
                return _FakeProcRC("2")
            return _FakeProcRC()

        monkeypatch.setattr(gc, "_run_git", fake)
        assert gc._unpushed_commits(Path("/tmp/wt"), "feature/x") == 2

    def test_both_git_calls_fail_returns_conservative_one(self, monkeypatch):
        def fake(args, **k):
            raise subprocess.CalledProcessError(1, args)

        monkeypatch.setattr(gc, "_run_git", fake)
        assert gc._unpushed_commits(Path("/tmp/wt"), "feature/x") == 1


# ---------------------------------------------------------------------------
# _resolve_lsof_path (round-2, 2026-07-18 — BLOCKER A)
#
# The daily cron's plist PATH is /opt/homebrew/bin:/usr/bin:/bin, which does
# NOT contain lsof on either M5 or Pro (it lives at /usr/sbin/lsof — verified
# empirically 2026-07-18: `env -i PATH=/opt/homebrew/bin:/usr/bin:/bin which
# lsof` -> rc=1 on M5). A bare ["lsof", ...] subprocess call under that PATH
# raised FileNotFoundError every single cron run, silently disabling the
# live-cwd guard (scar #2, green-but-not-working).
# ---------------------------------------------------------------------------


class TestResolveLsofPath:
    def test_absolute_fallback_when_path_excludes_lsof(self, monkeypatch):
        # Reproduce the EXACT cron bug on THIS machine, unmocked: set PATH
        # to the cron's real value, confirm shutil.which alone genuinely
        # fails (proving the bug is real, not assumed), then confirm the
        # absolute-path fallback probe (which stats the filesystem directly,
        # ignoring PATH) still resolves lsof.
        monkeypatch.setenv("PATH", "/opt/homebrew/bin:/usr/bin:/bin")
        assert shutil.which("lsof") is None, (
            "PATH must genuinely exclude lsof for this test to be meaningful "
            "— if this fails, the cron bug premise no longer holds on this "
            "machine and the test should be revisited"
        )
        resolved = gc._resolve_lsof_path()
        assert resolved is not None
        assert Path(resolved).exists()

    def test_shutil_which_preferred_when_available(self, monkeypatch, tmp_path):
        fake_lsof = tmp_path / "lsof"
        fake_lsof.write_text("#!/bin/sh\necho fake\n")
        fake_lsof.chmod(0o755)
        monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
        assert gc._resolve_lsof_path() == str(fake_lsof)

    def test_returns_none_when_truly_absent(self, monkeypatch):
        monkeypatch.setattr(gc.shutil, "which", lambda name: None)
        monkeypatch.setattr(gc.Path, "exists", lambda self: False)
        assert gc._resolve_lsof_path() is None


# ---------------------------------------------------------------------------
# _collect_live_cwds (round-2, 2026-07-18)
# ---------------------------------------------------------------------------


class TestCollectLiveCwds:
    def test_lsof_missing_returns_empty_set_and_warns_visibly(self, monkeypatch, caplog):
        monkeypatch.setattr(gc, "_resolve_lsof_path", lambda: None)
        with caplog.at_level("WARNING"):
            result = gc._collect_live_cwds()
        assert result == set()
        assert any("DEGRADED" in r.message for r in caplog.records)

    def test_parses_cwd_lines_from_lsof_output(self, monkeypatch):
        monkeypatch.setattr(gc, "_resolve_lsof_path", lambda: "/usr/sbin/lsof")

        def fake_run(cmd, **k):
            assert cmd[0] == "/usr/sbin/lsof"
            assert cmd[1:] == ["-a", "-d", "cwd", "-Fn"]
            return _FakeProcRC("p123\nfcwd\nn/some/path\np456\nfcwd\nn/other/path\n")

        monkeypatch.setattr(gc.subprocess, "run", fake_run)
        assert gc._collect_live_cwds() == {"/some/path", "/other/path"}

    def test_invocation_error_returns_empty_set_and_warns(self, monkeypatch, caplog):
        monkeypatch.setattr(gc, "_resolve_lsof_path", lambda: "/usr/sbin/lsof")

        def _raise(*a, **k):
            raise subprocess.TimeoutExpired(cmd="lsof", timeout=20)

        monkeypatch.setattr(gc.subprocess, "run", _raise)
        with caplog.at_level("WARNING"):
            result = gc._collect_live_cwds()
        assert result == set()
        assert any("DEGRADED" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# _has_live_cwd (round-2, 2026-07-18 — now a pure in-Python prefix-match
# against a pre-collected set; no subprocess call of its own, see
# _collect_live_cwds above for the single system-wide lsof call per gc() run)
# ---------------------------------------------------------------------------


class TestHasLiveCwd:
    def test_exact_match(self):
        assert gc._has_live_cwd(Path("/a/b/c"), {"/a/b/c"}) is True

    def test_subdirectory_match(self):
        # This is the case the naive `lsof -d cwd -- <dir>` exact-match form
        # misses (empirically verified 2026-07-18) — a shell cd'd into a
        # SUBDIRECTORY of the worktree must still count as active.
        assert gc._has_live_cwd(Path("/a/b"), {"/a/b/deep/sub"}) is True

    def test_unrelated_path_does_not_match(self):
        assert gc._has_live_cwd(Path("/a/b"), {"/some/other/place"}) is False

    def test_empty_set_never_matches(self):
        assert gc._has_live_cwd(Path("/a/b"), set()) is False

    def test_similar_prefix_without_separator_does_not_match(self):
        # /a/bc must NOT match target /a/b — the prefix check requires a
        # trailing separator, not a bare string prefix.
        assert gc._has_live_cwd(Path("/a/b"), {"/a/bc"}) is False


# ---------------------------------------------------------------------------
# Integration: real git repos + real `git worktree` under tmp_path.
#
# Exercises gc() end-to-end (NOT mocked _run_git) to prove the CHANGE B
# invariant empirically: reclaiming an unpushed-but-clean named-branch
# worktree's DIRECTORY never touches the branch REF. Never touches the real
# ~/nuzantara checkout/worktrees (W96 discipline) — everything lives under
# tmp_path with its own bare `origin` remote.
# ---------------------------------------------------------------------------


def _git(args, cwd, env, check=True):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), env=env,
        capture_output=True, text=True, check=check,
    )


def _load_gc_module(repo_root: Path):
    """Fresh module instance with REPO_ROOT/WORKTREES_DIR/ALLOWLIST_PATHS
    repointed at a tmp git repo, so gc() operates entirely inside tmp_path
    (mirrors the reload pattern in test_agent_start.py's _load_module)."""
    spec = importlib.util.spec_from_file_location(
        "worktree_gc_universal_under_test", SPEC_PATH,
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    mod.REPO_ROOT = repo_root
    mod.WORKTREES_DIR = repo_root / ".worktrees"
    mod.ALLOWLIST_PATHS = {str(repo_root.resolve())}
    return mod


def _add_worktree(repo, wt_path, branch, env, *, base="main"):
    _git(["worktree", "add", "-b", branch, str(wt_path), base], cwd=repo, env=env)


def _age_path(path: Path, hours: float):
    """Push mtime of path + path/.git into the past so age gates pass."""
    old = time.time() - hours * 3600 - 60
    os.utime(path, (old, old))
    gitp = path / ".git"
    try:
        os.utime(gitp, (old, old))
    except OSError:
        pass


@pytest.fixture
def gc_git_env():
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "Test"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "Test"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"
    return env


@pytest.fixture
def gc_repo(tmp_path, gc_git_env, monkeypatch):
    """Main repo (bare `origin` remote + pushed main) + a fresh gc module
    scoped to it. Mirrors test_agent_start.py's fake_repo: a bare origin is
    the minimal honest model — without one, EVERY worktree would read as
    unpushed."""
    monkeypatch.delenv("WORKTREE_GC_ENABLED", raising=False)

    origin = tmp_path / "origin.git"
    _git(["init", "--bare", "-b", "main", str(origin)], cwd=tmp_path, env=gc_git_env)

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init", "-b", "main"], cwd=repo, env=gc_git_env)
    (repo / "README.md").write_text("seed\n")
    _git(["add", "README.md"], cwd=repo, env=gc_git_env)
    _git(["commit", "-m", "seed"], cwd=repo, env=gc_git_env)
    _git(["remote", "add", "origin", str(origin)], cwd=repo, env=gc_git_env)
    _git(["push", "-u", "origin", "main"], cwd=repo, env=gc_git_env)

    mod = _load_gc_module(repo)
    return mod, repo, gc_git_env


class TestGcIntegration:
    def test_old_clean_worktree_unpushed_commit_removed_branch_survives(
        self, gc_repo,
    ):
        """(a) An OLD clean worktree on a branch with an unpushed commit is
        REMOVED — and the branch ref still exists afterward. This is the
        core W88 cure: `git worktree remove` never deletes the branch."""
        mod, repo, env = gc_repo
        wt = mod.WORKTREES_DIR / "feature-foo"
        wt.parent.mkdir(parents=True, exist_ok=True)
        _add_worktree(repo, wt, "feature/foo", env)
        (wt / "new.txt").write_text("unpushed work\n")
        _git(["add", "new.txt"], cwd=wt, env=env)
        _git(["commit", "-m", "unpushed commit"], cwd=wt, env=env)

        _age_path(wt, mod.DEFAULT_MAX_AGE_HOURS + 1)

        mod.gc(apply=True, max_age_hours=mod.DEFAULT_MAX_AGE_HOURS)

        assert not wt.exists()
        rev = _git(["rev-parse", "feature/foo"], cwd=repo, env=env, check=False)
        assert rev.returncode == 0, "branch ref must survive dir removal"
        assert rev.stdout.strip()

    def test_detached_head_clean_worktree_removed_commit_preserved_via_ref(
        self, gc_repo,
    ):
        """BLOCKER B anti-orphan proof (round-2, 2026-07-18): a CLEAN
        detached-HEAD worktree with 1 unique commit is REMOVED, but the
        commit is preserved via a refs/agent-quarantine/<slug>-head ref —
        never orphaned. Before the fix, `git stash create` (the only
        preservation mechanism) is EMPTY on a clean tree, so this exact case
        sailed through un-quarantined and the commit became dangling."""
        mod, repo, env = gc_repo
        wt = mod.WORKTREES_DIR / "detached-lane"
        wt.parent.mkdir(parents=True, exist_ok=True)
        # --detach: HEAD is a raw commit, no branch ref anywhere for it.
        _git(["worktree", "add", "--detach", str(wt), "main"], cwd=repo, env=env)
        (wt / "unique.txt").write_text("only reachable from detached HEAD\n")
        _git(["add", "unique.txt"], cwd=wt, env=env)
        _git(["commit", "-m", "unique detached commit"], cwd=wt, env=env)
        commit_sha = _git(["rev-parse", "HEAD"], cwd=wt, env=env).stdout.strip()

        _age_path(wt, mod.DEFAULT_MAX_AGE_HOURS + 1)

        mod.gc(apply=True, max_age_hours=mod.DEFAULT_MAX_AGE_HOURS)

        assert not wt.exists()
        slug = mod._slug(str(wt))
        ref = f"{mod.QUARANTINE_REF_PREFIX}/{slug}-head"
        resolved = _git(["rev-parse", "--verify", ref], cwd=repo, env=env, check=False)
        assert resolved.returncode == 0, "detached HEAD commit must be preserved"
        assert resolved.stdout.strip() == commit_sha

    def test_recent_worktree_kept_active_not_removed(self, gc_repo):
        """(b) A worktree touched within MIN_AGE_MIN is kept (active session)."""
        mod, repo, env = gc_repo
        wt = mod.WORKTREES_DIR / "feature-fresh"
        wt.parent.mkdir(parents=True, exist_ok=True)
        _add_worktree(repo, wt, "feature/fresh", env)
        # Fresh mtime (just created) — no _age_path call.

        mod.gc(apply=True, max_age_hours=mod.DEFAULT_MAX_AGE_HOURS)

        assert wt.exists()

    def test_real_dirty_worktree_quarantined_then_removed(self, gc_repo):
        """(c) A worktree with real (non-formatting) uncommitted changes is
        quarantined onto refs/agent-quarantine/<slug> THEN removed."""
        mod, repo, env = gc_repo
        wt = mod.WORKTREES_DIR / "feature-dirty"
        wt.parent.mkdir(parents=True, exist_ok=True)
        _add_worktree(repo, wt, "feature/dirty", env)
        (wt / "README.md").write_text("seed\nreal uncommitted change\n")

        _age_path(wt, mod.DEFAULT_MAX_AGE_HOURS + 1)

        mod.gc(apply=True, max_age_hours=mod.DEFAULT_MAX_AGE_HOURS)

        assert not wt.exists()
        slug = mod._slug(str(wt))
        ref = _git(
            ["rev-parse", f"{mod.QUARANTINE_REF_PREFIX}/{slug}"],
            cwd=repo, env=env, check=False,
        )
        assert ref.returncode == 0, "quarantine ref must exist before removal"
        assert ref.stdout.strip()

    def test_allowlisted_main_checkout_never_touched(self, gc_repo):
        """(d) The main checkout (in ALLOWLIST_PATHS) is skipped even if old
        and dirty."""
        mod, repo, env = gc_repo
        (repo / "README.md").write_text("seed\ndirty on main\n")
        _age_path(repo, mod.DEFAULT_MAX_AGE_HOURS + 1)

        mod.gc(apply=True, max_age_hours=mod.DEFAULT_MAX_AGE_HOURS)

        assert repo.exists()
        status = _git(["status", "--porcelain"], cwd=repo, env=env)
        assert "README.md" in status.stdout  # untouched, still dirty

    def test_dry_run_removes_nothing(self, gc_repo):
        """(e) Without --apply, gc() is report-only: no dir is removed."""
        mod, repo, env = gc_repo
        wt = mod.WORKTREES_DIR / "feature-dryrun"
        wt.parent.mkdir(parents=True, exist_ok=True)
        _add_worktree(repo, wt, "feature/dryrun", env)
        (wt / "new.txt").write_text("unpushed work\n")
        _git(["add", "new.txt"], cwd=wt, env=env)
        _git(["commit", "-m", "unpushed commit"], cwd=wt, env=env)
        _age_path(wt, mod.DEFAULT_MAX_AGE_HOURS + 1)

        mod.gc(apply=False, max_age_hours=mod.DEFAULT_MAX_AGE_HOURS)

        assert wt.exists()
