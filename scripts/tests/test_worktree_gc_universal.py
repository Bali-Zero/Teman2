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
durable ref (BLOCKER B cure, round-2). ``TestHeartbeat`` and
``TestMainHeartbeatWiring`` exercise the G2_heartbeat gene (round-3).
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent
SPEC_PATH = SCRIPT_DIR / "worktree_gc_universal.py"

_spec = importlib.util.spec_from_file_location("worktree_gc_universal", SPEC_PATH)
gc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gc)


@pytest.fixture(autouse=True)
def _heartbeat_sidecar_isolation(tmp_path, monkeypatch):
    """W96: no test in this module may EVER write to the real
    ~/.organism/last_seen/ — autouse means every test gets an isolated
    sidecar dir by default, whether or not it deliberately exercises the
    heartbeat path (defense in depth: a future test that calls main() or
    _heartbeat() without remembering to patch the env var still lands in
    tmp_path). A test that wants to verify ORGANISM_LAST_SEEN_DIR honoring
    specifically can still override this via its own monkeypatch.setenv
    (function-scoped monkeypatch — last call wins within the same test)."""
    monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(tmp_path / "organism-last-seen"))


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
# _quarantine_ttl_disabled  (env QUARANTINE_TTL_ENABLED — its OWN switch,
# independent of WORKTREE_GC_ENABLED, matching the same convention)
# ---------------------------------------------------------------------------


class TestQuarantineTtlKillSwitch:
    def test_false_disables(self, monkeypatch):
        monkeypatch.setenv(gc.QUARANTINE_TTL_ENABLED_ENV, "false")
        assert gc._quarantine_ttl_disabled() is True

    def test_zero_disables(self, monkeypatch):
        monkeypatch.setenv(gc.QUARANTINE_TTL_ENABLED_ENV, "0")
        assert gc._quarantine_ttl_disabled() is True

    def test_unset_is_enabled(self, monkeypatch):
        monkeypatch.delenv(gc.QUARANTINE_TTL_ENABLED_ENV, raising=False)
        assert gc._quarantine_ttl_disabled() is False

    def test_true_is_enabled(self, monkeypatch):
        monkeypatch.setenv(gc.QUARANTINE_TTL_ENABLED_ENV, "true")
        assert gc._quarantine_ttl_disabled() is False


# ---------------------------------------------------------------------------
# _list_quarantine_refs  (parses NUL-delimited `git for-each-ref` output)
# ---------------------------------------------------------------------------


class TestListQuarantineRefs:
    def test_parses_nul_delimited_lines(self, monkeypatch):
        sample = (
            "refs/agent-quarantine/foo\x00" + "a" * 40 +
            "\x002026-01-01T00:00:00+00:00\n" +
            "refs/agent-quarantine/bar\x00" + "b" * 40 +
            "\x002026-02-02T03:04:05+08:00\n"
        )
        monkeypatch.setattr(gc, "_run_git", lambda *a, **k: _FakeProc(sample))
        entries = gc._list_quarantine_refs()
        assert len(entries) == 2
        assert entries[0]["ref"] == "refs/agent-quarantine/foo"
        assert entries[0]["sha"] == "a" * 40
        assert entries[0]["committer_date"].year == 2026
        assert entries[0]["committer_date"].tzinfo is not None

    def test_empty_output(self, monkeypatch):
        monkeypatch.setattr(gc, "_run_git", lambda *a, **k: _FakeProc(""))
        assert gc._list_quarantine_refs() == []

    def test_unparseable_date_kept_as_none_not_dropped(self, monkeypatch, caplog):
        sample = "refs/agent-quarantine/weird\x00" + "c" * 40 + "\x00not-a-date\n"
        monkeypatch.setattr(gc, "_run_git", lambda *a, **k: _FakeProc(sample))
        with caplog.at_level("WARNING"):
            entries = gc._list_quarantine_refs()
        assert len(entries) == 1
        assert entries[0]["committer_date"] is None
        assert any("unparseable" in r.message for r in caplog.records)


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
    # Quarantine TTL sweep writes its receipt log under REPO_ROOT/.agent-receipts/
    # by default; this constant is bound at module-exec time (before REPO_ROOT
    # is repointed above), so it must be repointed explicitly here too — same
    # reasoning as WORKTREES_DIR two lines up. Without this, a test using the
    # DEFAULT log path would append to the real worktree's .agent-receipts/
    # instead of tmp_path (W96 discipline).
    mod.QUARANTINE_EXPIRY_LOG = repo_root / ".agent-receipts" / "quarantine-ttl-expired.log"
    return mod


def _add_worktree(repo, wt_path, branch, env, *, base="main"):
    _git(["worktree", "add", "-b", branch, str(wt_path), base], cwd=repo, env=env)


def _make_quarantine_ref(repo: Path, slug: str, days_old: float, env: dict) -> str:
    """Create refs/agent-quarantine/<slug> pointing at a NEW commit object
    backdated `days_old` days via GIT_COMMITTER_DATE (per the brief: build
    fixtures in the tmp throwaway repo, never against real refs). Returns
    the commit sha."""
    backdated = datetime.now(timezone.utc) - timedelta(days=days_old)
    date_str = backdated.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    commit_env = dict(env)
    commit_env["GIT_COMMITTER_DATE"] = date_str
    commit_env["GIT_AUTHOR_DATE"] = date_str
    tree = _git(["rev-parse", "HEAD^{tree}"], cwd=repo, env=env).stdout.strip()
    parent = _git(["rev-parse", "HEAD"], cwd=repo, env=env).stdout.strip()
    sha = _git(
        ["commit-tree", tree, "-p", parent, "-m", f"quarantine {slug}"],
        cwd=repo, env=commit_env,
    ).stdout.strip()
    ref = f"refs/agent-quarantine/{slug}"
    _git(["update-ref", ref, sha], cwd=repo, env=env)
    return sha


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


# ---------------------------------------------------------------------------
# _expire_stale_quarantine_refs (rule 10, 2026-08-2x quarantine TTL sweep) —
# real git repo under tmp_path, real refs/agent-quarantine/* refs backdated
# via GIT_COMMITTER_DATE (never the real repo's refs, per the brief).
# ---------------------------------------------------------------------------


class TestExpireStaleQuarantineRefs:
    def test_ref_older_than_ttl_is_expired(self, gc_repo):
        """GUILT: a quarantine ref committed 31+ days ago IS expired."""
        mod, repo, env = gc_repo
        _make_quarantine_ref(repo, "old-one", mod.QUARANTINE_TTL_DAYS + 1, env)

        expired = mod._expire_stale_quarantine_refs(apply=True)

        assert expired == 1
        check = _git(
            ["rev-parse", "--verify", "refs/agent-quarantine/old-one"],
            cwd=repo, env=env, check=False,
        )
        assert check.returncode != 0, "expired ref must no longer resolve"

    def test_ref_within_ttl_survives(self, gc_repo):
        """INNOCENCE: a 29-day-old ref (< 30-day TTL) survives."""
        mod, repo, env = gc_repo
        _make_quarantine_ref(repo, "recent-one", mod.QUARANTINE_TTL_DAYS - 1, env)

        expired = mod._expire_stale_quarantine_refs(apply=True)

        assert expired == 0
        check = _git(
            ["rev-parse", "--verify", "refs/agent-quarantine/recent-one"],
            cwd=repo, env=env, check=False,
        )
        assert check.returncode == 0, "a ref inside the TTL must survive"

    def test_refs_outside_namespace_never_touched(self, gc_repo):
        """INNOCENCE: a branch, a tag, and a remote-tracking ref — however
        old — are never touched, no matter what else the sweep expires."""
        mod, repo, env = gc_repo
        old_env = dict(env)
        old_env["GIT_COMMITTER_DATE"] = "2020-01-01T00:00:00+00:00"
        old_env["GIT_AUTHOR_DATE"] = "2020-01-01T00:00:00+00:00"
        _git(["tag", "-a", "ancient-tag", "-m", "old"], cwd=repo, env=old_env)
        before_branch = _git(["rev-parse", "main"], cwd=repo, env=env).stdout.strip()
        before_tag = _git(["rev-parse", "ancient-tag"], cwd=repo, env=env).stdout.strip()
        before_remote = _git(
            ["rev-parse", "origin/main"], cwd=repo, env=env,
        ).stdout.strip()
        # One genuinely guilty quarantine ref alongside them, so the sweep
        # has real work to do while touching neither of the three above.
        _make_quarantine_ref(repo, "guilty", mod.QUARANTINE_TTL_DAYS + 1, env)

        expired = mod._expire_stale_quarantine_refs(apply=True)

        assert expired == 1  # only the quarantine ref
        assert _git(["rev-parse", "main"], cwd=repo, env=env).stdout.strip() == before_branch
        assert _git(["rev-parse", "ancient-tag"], cwd=repo, env=env).stdout.strip() == before_tag
        assert (
            _git(["rev-parse", "origin/main"], cwd=repo, env=env).stdout.strip()
            == before_remote
        )

    def test_dry_run_expires_nothing(self, gc_repo):
        """INNOCENCE: dry-run reports the candidate count but deletes
        nothing and writes no log file."""
        mod, repo, env = gc_repo
        _make_quarantine_ref(repo, "old-dry", mod.QUARANTINE_TTL_DAYS + 1, env)

        would_expire = mod._expire_stale_quarantine_refs(apply=False)

        assert would_expire == 1  # correctly counts the candidate
        check = _git(
            ["rev-parse", "--verify", "refs/agent-quarantine/old-dry"],
            cwd=repo, env=env, check=False,
        )
        assert check.returncode == 0, "dry-run must not delete anything"
        assert not mod.QUARANTINE_EXPIRY_LOG.exists(), (
            "dry-run must not write the receipt log either"
        )

    def test_kill_switch_expires_nothing(self, gc_repo, monkeypatch):
        """INNOCENCE: QUARANTINE_TTL_ENABLED=false disables the sweep end
        to end (through gc()), even though the worktree-reap loop still
        runs."""
        mod, repo, env = gc_repo
        monkeypatch.setenv(mod.QUARANTINE_TTL_ENABLED_ENV, "false")
        _make_quarantine_ref(repo, "old-killswitch", mod.QUARANTINE_TTL_DAYS + 1, env)

        report = mod.gc(apply=True, max_age_hours=mod.DEFAULT_MAX_AGE_HOURS)

        assert report["quarantine_expired"] == 0
        check = _git(
            ["rev-parse", "--verify", "refs/agent-quarantine/old-killswitch"],
            cwd=repo, env=env, check=False,
        )
        assert check.returncode == 0, "kill switch must prevent expiry"

    def test_already_gone_ref_is_not_reported_as_a_failure(
        self, gc_repo, monkeypatch, caplog,
    ):
        """GOTCHA (from the brief): `git update-ref -d` against a ref that
        no longer exists prints 'unable to resolve reference ...' and
        returns 1 — that's 'already gone', not a bug, and must not be
        logged as a failure or crash the sweep."""
        mod, repo, env = gc_repo
        sha = _make_quarantine_ref(repo, "vanishing", mod.QUARANTINE_TTL_DAYS + 1, env)
        # Simulate the ref disappearing between enumeration and deletion.
        _git(
            ["update-ref", "-d", "refs/agent-quarantine/vanishing", sha],
            cwd=repo, env=env,
        )
        stale_entry = {
            "ref": "refs/agent-quarantine/vanishing",
            "sha": sha,
            "committer_date": datetime.now(timezone.utc) - timedelta(days=31),
        }
        monkeypatch.setattr(mod, "_list_quarantine_refs", lambda: [stale_entry])

        with caplog.at_level("ERROR"):
            expired = mod._expire_stale_quarantine_refs(apply=True)

        assert expired == 0  # nothing NEW was deleted — it was already gone
        assert not any("failed to expire" in r.message for r in caplog.records)

    def test_moved_ref_survives_and_is_not_conflated_with_already_gone(
        self, gc_repo, monkeypatch, caplog,
    ):
        """Regression (team-lead review, 2026-08-2x): `git update-ref -d`
        wraps BOTH the absent-ref case and the moved-ref case in "cannot
        lock ref ..." — matching on that wrapper alone silently swallowed
        a ref that MOVED between enumeration and deletion (present, but not
        at the sha the sweep expected) as ordinary "already gone" noise.
        A moved ref means something else wrote to this namespace mid-sweep
        — exactly the event an operator needs to see, not something to
        hide. Prove: the ref survives, it is NOT counted as expired, and it
        is not logged as "already gone"."""
        mod, repo, env = gc_repo
        stale_sha = _make_quarantine_ref(
            repo, "moved", mod.QUARANTINE_TTL_DAYS + 1, env,
        )
        # Simulate the ref moving to a NEW sha between enumeration and
        # deletion (e.g. re-quarantined by a concurrent run) — the sweep's
        # candidate list still carries the OLD (now-stale) sha.
        # A different days_old (still > TTL) yields a different committer
        # date and therefore a different commit sha — `git commit-tree` is
        # otherwise fully deterministic (same tree/parent/message/author),
        # so an identical call here would silently reproduce stale_sha.
        fresh_sha = _make_quarantine_ref(
            repo, "moved", mod.QUARANTINE_TTL_DAYS + 2, env,
        )
        assert fresh_sha != stale_sha
        stale_entry = {
            "ref": "refs/agent-quarantine/moved",
            "sha": stale_sha,  # stale — the ref has already moved past this
            "committer_date": datetime.now(timezone.utc) - timedelta(days=31),
        }
        monkeypatch.setattr(mod, "_list_quarantine_refs", lambda: [stale_entry])

        with caplog.at_level("WARNING"):
            expired = mod._expire_stale_quarantine_refs(apply=True)

        assert expired == 0, "a moved ref must not be counted as expired"
        current = _git(
            ["rev-parse", "--verify", "refs/agent-quarantine/moved"],
            cwd=repo, env=env, check=False,
        )
        assert current.returncode == 0, "the ref must survive"
        assert current.stdout.strip() == fresh_sha, (
            "the ref must still point at its CURRENT (fresh) sha, untouched"
        )
        assert not any(
            "already gone" in r.message for r in caplog.records
        ), "a moved ref must never be reported as already gone"
        assert any(
            "MOVED" in r.message for r in caplog.records
        ), "a moved ref must be logged as its own distinct case"

    def test_expiry_appends_receipt_log_with_refname_sha_date(self, gc_repo):
        """Never silent: every expiry writes (full refname, sha, committer
        date) to the receipt log file."""
        mod, repo, env = gc_repo
        sha = _make_quarantine_ref(repo, "logged-one", mod.QUARANTINE_TTL_DAYS + 1, env)

        mod._expire_stale_quarantine_refs(apply=True)

        log_path = mod.QUARANTINE_EXPIRY_LOG
        assert log_path.exists()
        content = log_path.read_text()
        assert "refs/agent-quarantine/logged-one" in content
        assert sha in content

    def test_large_sweep_alarms_but_proceeds(self, gc_repo, caplog):
        """Alarm, never halt: a run that would expire more than
        QUARANTINE_SWEEP_ALARM refs logs a loud [ALARM] and still expires
        every one of them — it does not stop draining the backlog."""
        mod, repo, env = gc_repo
        n = mod.QUARANTINE_SWEEP_ALARM + 1
        for i in range(n):
            _make_quarantine_ref(repo, f"bulk-{i}", mod.QUARANTINE_TTL_DAYS + 1, env)

        with caplog.at_level("WARNING"):
            expired = mod._expire_stale_quarantine_refs(apply=True)

        assert expired == n
        assert any("[ALARM]" in r.message for r in caplog.records)

    def test_ref_outside_namespace_from_a_compromised_lister_is_refused(
        self, gc_repo, monkeypatch, caplog,
    ):
        """Defense in depth: assert per-ref in CODE, not just in the query.
        Even if _list_quarantine_refs() were to somehow return an
        out-of-namespace entry, the sweep must refuse to touch it — a guard
        that only trusts its own query is not a guard."""
        mod, repo, env = gc_repo
        fake_entries = [{
            "ref": "refs/heads/main",
            "sha": "d" * 40,
            "committer_date": datetime(2000, 1, 1, tzinfo=timezone.utc),
        }]
        monkeypatch.setattr(mod, "_list_quarantine_refs", lambda: fake_entries)
        calls = []
        real_run_git = mod._run_git

        def spy(args, **kw):
            calls.append(args)
            return real_run_git(args, **kw)

        monkeypatch.setattr(mod, "_run_git", spy)

        with caplog.at_level("ERROR"):
            expired = mod._expire_stale_quarantine_refs(apply=True)

        assert expired == 0
        assert not any(
            len(c) >= 2 and c[0] == "update-ref" and "-d" in c for c in calls
        ), "must never call update-ref -d for a ref outside refs/agent-quarantine/"
        assert any("OUTSIDE" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# _heartbeat (G2_heartbeat gene, round-3, 2026-07-18) — direct unit tests.
# The autouse _heartbeat_sidecar_isolation fixture above already redirects
# ORGANISM_LAST_SEEN_DIR to tmp_path for every test in this module; these
# tests exercise the function's own contract on top of that isolation.
# ---------------------------------------------------------------------------


class TestHeartbeat:
    def test_honors_organism_last_seen_dir_env(self, tmp_path, monkeypatch):
        """(d) sidecar path honors ORGANISM_LAST_SEEN_DIR."""
        custom_dir = tmp_path / "custom-sidecar-dir"
        monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(custom_dir))

        gc._heartbeat("ok", "test detail")

        sidecar = custom_dir / f"{gc.ORGAN_ID}.json"
        assert sidecar.exists()
        payload = json.loads(sidecar.read_text())
        assert payload["organ"] == gc.ORGAN_ID
        assert payload["status"] == "ok"
        assert payload["detail"] == "test detail"
        assert payload["ts"].endswith("Z")  # UTC ISO marker

    def test_write_failure_never_raises(self, tmp_path, monkeypatch):
        """(c) heartbeat write failure (mkdir raises) never escapes as an
        exception — the GC's exit code must never depend on liveness-proof
        succeeding."""
        sidecar_dir = tmp_path / "unwritable"
        monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(sidecar_dir))

        def _raise_mkdir(*a, **k):
            raise OSError("simulated disk full")

        monkeypatch.setattr(gc.Path, "mkdir", _raise_mkdir)

        gc._heartbeat("ok", "should be swallowed, not raised")  # must not raise

        # Prove the failure was genuinely swallowed, not silently no-op'd
        # into "success anyway": mkdir never ran, so no sidecar dir exists.
        assert not sidecar_dir.exists()


# ---------------------------------------------------------------------------
# main() heartbeat wiring (G2_heartbeat gene, round-3, 2026-07-18) —
# end-to-end: real gc_repo, real main() call (sys.argv monkeypatched),
# real sidecar file read back.
# ---------------------------------------------------------------------------


class TestMainHeartbeatWiring:
    def test_apply_run_writes_ok_sidecar_with_reap_counters(
        self, gc_repo, monkeypatch, tmp_path,
    ):
        """(a) --apply run -> sidecar written with status ok and detail
        carrying the real reap counters (the anti-blindness payload)."""
        mod, repo, env = gc_repo
        sidecar_dir = tmp_path / "sidecar-main-ok"
        monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(sidecar_dir))

        wt = mod.WORKTREES_DIR / "feature-heartbeat"
        wt.parent.mkdir(parents=True, exist_ok=True)
        _add_worktree(repo, wt, "feature/heartbeat", env)
        (wt / "new.txt").write_text("unpushed work\n")
        _git(["add", "new.txt"], cwd=wt, env=env)
        _git(["commit", "-m", "unpushed commit"], cwd=wt, env=env)
        _age_path(wt, mod.DEFAULT_MAX_AGE_HOURS + 1)

        monkeypatch.setattr(
            sys, "argv",
            ["worktree_gc_universal.py", "--apply",
             "--max-age-hours", str(mod.DEFAULT_MAX_AGE_HOURS)],
        )
        rc = mod.main()
        assert rc == 0
        assert not wt.exists()  # sanity: the reap actually happened

        sidecar = sidecar_dir / f"{mod.ORGAN_ID}.json"
        assert sidecar.exists()
        payload = json.loads(sidecar.read_text())
        assert payload["organ"] == mod.ORGAN_ID
        assert payload["status"] == "ok"
        assert "removed=" in payload["detail"]
        assert "removed=0" not in payload["detail"]  # something was actually reaped

    def test_kill_switch_writes_disabled_sidecar(self, gc_repo, monkeypatch, tmp_path):
        """(b) kill-switch set -> status disabled."""
        mod, repo, env = gc_repo
        sidecar_dir = tmp_path / "sidecar-main-disabled"
        monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(sidecar_dir))
        monkeypatch.setenv("WORKTREE_GC_ENABLED", "false")
        monkeypatch.setattr(sys, "argv", ["worktree_gc_universal.py"])

        rc = mod.main()
        assert rc == 0

        sidecar = sidecar_dir / f"{mod.ORGAN_ID}.json"
        assert sidecar.exists()
        payload = json.loads(sidecar.read_text())
        assert payload["status"] == "disabled"

    def test_heartbeat_failure_does_not_break_main_exit_code(
        self, gc_repo, monkeypatch, tmp_path,
    ):
        """(c, end-to-end) even with the heartbeat write itself broken
        (mkdir raises), main() still returns its normal exit code and no
        exception escapes — liveness-proof failure must never mask (or
        cause) a GC failure."""
        mod, repo, env = gc_repo
        monkeypatch.setenv("ORGANISM_LAST_SEEN_DIR", str(tmp_path / "broken"))
        monkeypatch.setenv("WORKTREE_GC_ENABLED", "false")
        monkeypatch.setattr(sys, "argv", ["worktree_gc_universal.py"])

        def _raise_mkdir(*a, **k):
            raise OSError("simulated failure")

        monkeypatch.setattr(mod.Path, "mkdir", _raise_mkdir)

        rc = mod.main()  # must not raise
        assert rc == 0
