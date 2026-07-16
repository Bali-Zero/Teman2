"""Unit tests for scripts/worktree_gc_universal.py.

Tests the pure logic functions WITHOUT touching real worktrees. The module is
a script (not an importable package member), so it is loaded by path via
``importlib.util``. Git is mocked by monkeypatching ``_run_git``; the real
helper returns a ``subprocess.CompletedProcess`` whose ``.stdout`` callers read,
so the fakes return a small stand-in with a ``stdout`` attribute.
"""
import importlib.util
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
        assert slug == "Users_nuz_Desktop_nuzantara_.worktrees_ops-foo"

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
