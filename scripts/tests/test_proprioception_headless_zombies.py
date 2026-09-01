"""Tests for proprioception.py's `headless_zombies` receptor (2026-09-01).

THE MINI INCIDENT this receptor exists to catch: a headless `claude` pid was up
3d11h, its task's PR had merged 2.5 days earlier, the parent session had ended
cleanly, and the worktree reaper had deleted the worktree it was launched in
WHILE THE PROCESS KEPT RUNNING -- `lsof`'s cwd for that pid named a path `stat`
could no longer find. The reaper reaps DIRECTORIES; nothing reaps the PROCESS
still holding one open, and CPU sat at an idle heartbeat throughout.

TESTABILITY SPLIT (by design, per the mandate): `classify_headless_zombies` is a
pure function -- no subprocess, no filesystem access beyond a caller-supplied
`cwd_exists` -- and is exercised directly here with synthetic process lists, no
live process ever spawned. `_is_claude_headless_argv` is likewise pure (a string
test). Only the "tool failure -> UNPROBEABLE" cases drive the thin collector,
and even those stub `prop.sh` rather than touching a real process, following the
same pattern scripts/tests/test_proprioception_tri_state_exit.py already uses.

Each test names the mutation it would survive (superscar #6 discipline: a test
that only asserts the happy path is satisfied by a classifier that ignores the
signal it claims to check).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parents[1] / "proprioception.py"
_spec = importlib.util.spec_from_file_location("proprioception", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
prop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prop)  # type: ignore[union-attr]


def _proc(pid="111", etime="3-11:22:33", argv="claude --print hello",
          cwd="/repo/.worktrees/lane-x", cwd_exists=True) -> dict:
    return {"pid": pid, "etime": etime, "argv": argv, "cwd": cwd, "cwd_exists": cwd_exists}


# ------------------------------------------------------------------ _is_claude_headless_argv


def test_argv_bare_claude_matches() -> None:
    """Mutation it survives: a matcher requiring a path separator in argv[0]."""
    assert prop._is_claude_headless_argv("claude") is True
    assert prop._is_claude_headless_argv("claude interactive --resume") is True


def test_argv_bin_claude_exe_matches() -> None:
    """The npm-installed CLI shape named in the design."""
    assert prop._is_claude_headless_argv(
        "/opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe --agent-id x"
    ) is True


def test_argv_desktop_app_helper_is_excluded() -> None:
    """GUILT+INNOCENCE pair for the desktop-app exclusion. Mutation it survives:
    a substring test (`"claude" in argv.lower()`) instead of a basename test --
    that mutant would match every one of these."""
    assert prop._is_claude_headless_argv("/Applications/Claude.app/Contents/MacOS/Claude") is False
    assert prop._is_claude_headless_argv(
        "/Applications/Claude.app/Contents/Frameworks/Claude Helper (Renderer).app/"
        "Contents/MacOS/Claude Helper (Renderer)"
    ) is False
    assert prop._is_claude_headless_argv(
        "/Applications/Claude.app/Contents/Frameworks/Electron Framework.framework/Helpers/"
        "chrome_crashpad_handler --monitor-self-annotation=ptype=crashpad-handler"
    ) is False


def test_argv_unrelated_and_lookalike_commands_are_excluded() -> None:
    """Innocence beyond the desktop app: a substring-only matcher would also
    over-match `claude-science`, `not-claude`, and any tool whose argv merely
    mentions a path under ~/.claude/."""
    assert prop._is_claude_headless_argv("/Users/x/.claude-science/bin/claude-science serve") is False
    assert prop._is_claude_headless_argv("tmux -L claude-swarm-42327 new-session") is False
    assert prop._is_claude_headless_argv(
        "python /Users/nuzantara/.claude/daemons/guardrails.py"
    ) is False
    assert prop._is_claude_headless_argv("") is False
    assert prop._is_claude_headless_argv("   ") is False


# ------------------------------------------------------------------ classify_headless_zombies: P1


def test_dead_cwd_process_is_flagged_p1() -> None:
    """THE CORE SIGNAL. Mutation it survives: a classifier that only checks
    `cwd is None` and never actually reads `cwd_exists`."""
    procs = [_proc(pid="13767", etime="3-11:22:33", cwd="/repo/.worktrees/gone", cwd_exists=False)]
    status, n, ev = prop.classify_headless_zombies(procs, registered_worktrees=set())
    assert status == prop.DIVERGED
    assert n == 1
    assert any("P1" in e and "13767" in e and "/repo/.worktrees/gone" in e for e in ev), ev


def test_live_cwd_headless_process_is_not_flagged() -> None:
    """INNOCENCE for P1. A live, registered cwd must never be reported as a
    finding. Mutation it survives: a classifier that flags every headless
    process regardless of cwd_exists."""
    procs = [_proc(cwd="/repo/.worktrees/lane-x", cwd_exists=True)]
    status, n, ev = prop.classify_headless_zombies(procs, registered_worktrees={"/repo/.worktrees/lane-x"})
    assert status == prop.RECONCILED
    assert n == 0
    assert not any("P1" in e or "P2" in e for e in ev), ev


def test_unknown_cwd_is_neither_flagged_nor_crashes() -> None:
    """A cwd lsof never attributed (cwd=None) or whose existence could not be
    checked (cwd_exists=None) must be silently skipped, never coerced into
    True or False. This is the calm-liar guard (W84): asserting "dead" about
    something never actually observed."""
    procs = [
        _proc(pid="1", cwd=None, cwd_exists=None),
        _proc(pid="2", cwd="/somewhere", cwd_exists=None),
    ]
    status, n, ev = prop.classify_headless_zombies(procs, registered_worktrees=set())
    assert status == prop.RECONCILED
    assert n == 0


# ------------------------------------------------------------------ classify_headless_zombies: P2


def test_unregistered_worktree_cwd_is_the_secondary_notice() -> None:
    """P2, lower severity, distinct wording from P1. Mutation it survives: a
    classifier that reuses the P1 code path (same severity tag) for this case."""
    procs = [_proc(pid="222", cwd="/repo/.worktrees/reaped-lane", cwd_exists=True)]
    status, n, ev = prop.classify_headless_zombies(procs, registered_worktrees={"/repo/.worktrees/other-lane"})
    assert status == prop.DIVERGED
    assert n == 1
    assert any("P2" in e and "notice" in e and "222" in e for e in ev), ev
    assert not any(e.startswith("P1") for e in ev), ev


def test_unregistered_but_not_a_worktree_path_is_not_flagged() -> None:
    """INNOCENCE for P2: a live cwd outside `.worktrees/` (e.g. the main
    checkout itself) must never be judged against the worktree registry at
    all, even if it happens not to be a member of it."""
    procs = [_proc(cwd="/repo", cwd_exists=True)]
    status, n, ev = prop.classify_headless_zombies(procs, registered_worktrees=set())
    assert status == prop.RECONCILED
    assert n == 0


def test_registered_worktrees_none_suppresses_p2_but_not_p1() -> None:
    """When `git worktree list` itself failed this run, registered_worktrees is
    None -- P2 coverage is unavailable and must not silently read as "every
    worktree is orphaned" (that would be `set()`, a different and wrong
    signal). P1 needs no worktree registry at all and must still fire."""
    procs = [
        _proc(pid="1", cwd="/repo/.worktrees/would-be-p2", cwd_exists=True),
        _proc(pid="2", cwd="/repo/.worktrees/dead", cwd_exists=False),
    ]
    status, n, ev = prop.classify_headless_zombies(procs, registered_worktrees=None)
    assert status == prop.DIVERGED
    assert n == 1  # only the P1, the P2 candidate is skipped for lack of coverage
    assert any("P1" in e and "2" in e for e in ev), ev
    assert not any("P2" in e for e in ev), ev


def test_no_processes_reconciles_with_honest_evidence() -> None:
    status, n, ev = prop.classify_headless_zombies([], registered_worktrees=set())
    assert status == prop.RECONCILED
    assert n == 0
    assert ev == ["no headless claude CLI process found"]


# ------------------------------------------------------------------ _parse_lsof_cwd_by_pid


def test_parse_lsof_cwd_by_pid() -> None:
    text = "p111\nfcwd\nn/repo/.worktrees/lane-x\np222\nfcwd\nn/repo\n"
    pid_cwd = prop._parse_lsof_cwd_by_pid(text)
    assert pid_cwd == {"111": "/repo/.worktrees/lane-x", "222": "/repo"}


def test_parse_lsof_cwd_by_pid_ignores_n_lines_before_any_p_line() -> None:
    """Mutation it survives: dropping the `current_pid is not None` guard,
    which would attribute a stray `n` line to no pid instead of skipping it."""
    text = "n/orphan\np111\nfcwd\nn/repo\n"
    pid_cwd = prop._parse_lsof_cwd_by_pid(text)
    assert pid_cwd == {"111": "/repo"}


# ------------------------------------------------------------------ probe_headless_zombies: tool failure -> UNPROBEABLE


def _patched(monkeypatch_calls):
    """Install a fake `prop.sh` keyed by the first argv token; restore on exit."""
    original_sh = prop.sh

    def fake_sh(argv, timeout=None, cwd=None):  # noqa: ARG001
        key = argv[0]
        if key not in monkeypatch_calls:
            raise AssertionError(f"unexpected sh() call: {argv}")
        result = monkeypatch_calls[key]
        if isinstance(result, Exception):
            raise result
        return result

    prop.sh = fake_sh  # type: ignore[assignment]
    return original_sh


def test_ps_failure_is_unprobeable_not_a_crash() -> None:
    """Mutation it survives: letting the OSError propagate out of main()'s
    generic except (that would still not crash the ORGAN, but this receptor's
    own contract is to degrade to UNPROBEABLE with a legible reason, not lean
    on a caller's safety net)."""
    original_sh = _patched({"ps": FileNotFoundError("no such file: ps")})
    try:
        status, n, ev = prop.probe_headless_zombies(Path("/repo"), {}, timeout=5)
    finally:
        prop.sh = original_sh  # type: ignore[assignment]
    assert status == prop.UNPROBEABLE
    assert n == 0
    assert any("ps" in e.lower() for e in ev), ev


def test_lsof_failure_is_unprobeable_not_a_crash() -> None:
    """THE NAMED FAILURE MODE in the mandate. ps finds a real candidate, lsof
    (the tool that would attribute its cwd) is unavailable -- the whole probe
    must degrade to UNPROBEABLE, never raise, and never silently report
    RECONCILED as if it had actually looked at that pid's cwd."""
    original_sh = _patched({
        "ps": (0, "  111 3-11:22:33 claude --print hi\n", ""),
        "lsof": FileNotFoundError("no such file: lsof"),
    })
    try:
        status, n, ev = prop.probe_headless_zombies(Path("/repo"), {}, timeout=5)
    finally:
        prop.sh = original_sh  # type: ignore[assignment]
    assert status == prop.UNPROBEABLE
    assert n == 0
    assert any("lsof" in e.lower() for e in ev), ev


def test_ps_nonzero_exit_is_unprobeable() -> None:
    original_sh = _patched({"ps": (1, "", "ps: illegal option")})
    try:
        status, n, ev = prop.probe_headless_zombies(Path("/repo"), {}, timeout=5)
    finally:
        prop.sh = original_sh  # type: ignore[assignment]
    assert status == prop.UNPROBEABLE
    assert n == 0


def test_no_claude_candidates_reconciles_without_calling_lsof() -> None:
    """Innocence: when ps finds nothing claude-shaped, lsof must never be
    invoked at all (there is nothing to ask it about) -- calling it anyway
    with an empty pid list is either a no-op or an error depending on lsof's
    own argument parsing, and this receptor must not depend on either."""
    original_sh = _patched({"ps": (0, "  999 00:01 /usr/bin/vim\n", "")})
    try:
        status, n, ev = prop.probe_headless_zombies(Path("/repo"), {}, timeout=5)
    finally:
        prop.sh = original_sh  # type: ignore[assignment]
    assert status == prop.RECONCILED
    assert n == 0
    assert ev == ["no headless claude CLI process found"]


def test_git_worktree_list_failure_still_catches_p1() -> None:
    """End-to-end through probe_headless_zombies (not just the classifier):
    ps+lsof succeed and name a DEAD cwd, git worktree list fails -- P1 must
    still fire. This is the collector-level counterpart of
    test_registered_worktrees_none_suppresses_p2_but_not_p1."""
    original_sh = _patched({
        "ps": (0, "  111 3-11:22:33 claude --print hi\n", ""),
        "lsof": (0, "p111\nfcwd\nn/repo/.worktrees/gone\n", ""),
        "git": FileNotFoundError("no such file: git"),
    })
    try:
        status, n, ev = prop.probe_headless_zombies(Path("/repo"), {}, timeout=5)
    finally:
        prop.sh = original_sh  # type: ignore[assignment]
    assert status == prop.DIVERGED
    assert n == 1
    assert any("P1" in e and "111" in e for e in ev), ev


# ------------------------------------------------------------------ registry integrity


def test_selftest_still_passes_with_the_new_receptor_registered() -> None:
    """The registry validator must accept the new entry; a receptor the
    validator rejects would be dead on arrival."""
    errs = prop.validate_registry(prop.DEFAULT_REGISTRY)
    assert errs == [], errs


def test_headless_zombies_is_registered_as_builtin() -> None:
    ids = {e["id"] for e in prop.DEFAULT_REGISTRY}
    assert "headless_zombies" in ids
    entry = next(e for e in prop.DEFAULT_REGISTRY if e["id"] == "headless_zombies")
    assert entry["type"] == "builtin"
    assert entry["target"] == "headless_zombies"
    assert prop.BUILTINS[entry["target"]] is prop.probe_headless_zombies
    assert entry["class"] in prop.KNOWN_BOUNDARY_CLASSES
