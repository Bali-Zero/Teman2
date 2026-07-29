"""Tests for scripts/prepush_freshness.py (`.husky/pre-push` warn-only
staleness check on a branch's FIRST push).

Mandate (task #27, 2026-07-26): the "zero-check trap" — a branch whose FIRST
push is based on a stale `origin/main` can be conflicting the instant it
lands, and GitHub Actions then never materialises `refs/pull/N/merge` for a
`pull_request`-triggered workflow. No required context is ever created (they
sit ABSENT, not red), auto-merge sits armed and inert, and the only visible
symptom is a workflow-run count of ~1 on the head SHA instead of the healthy
23-35. Four branches hit this in one evening; `scripts/prepush_freshness.py`
is a cheap, deterministic PROXY (merge-base(origin/main, local) !=
origin/main's current tip) surfaced as a warn-only pre-push line — not a
conflict oracle, and not a block (this repo's guard-over-match scar history,
cicatrix-superscar.md #3, is exactly why over-blocking on a proxy is worse
than under-blocking).

This file is the guilt+innocence proof the antidote demands ("nessuna
guardia mergiata senza un test di innocenza E di colpevolezza"). GUILT: a
first push whose fork point has fallen behind origin/main's tip warns.
INNOCENCE: a first push cut from the CURRENT tip does not warn, unknown
git-plumbing state (empty SHA either side) does not warn, and — the case
that matters most in practice, reproduced live tonight fixing
secrets-triage-kbli-gold — merging origin/main into a stale branch BEFORE
its first push clears the warning (merge-base becomes origin/main's tip
itself), so the escape hatch this module recommends in its own WARN_MESSAGE
actually resolves the condition it flags.

Run:  python3 -m pytest scripts/tests/test_prepush_freshness.py -q
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = REPO_ROOT / "scripts" / "prepush_freshness.py"
_spec = importlib.util.spec_from_file_location("prepush_freshness", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
pf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pf)  # type: ignore[union-attr]

# Realistic-looking 40-hex SHAs, distinct from each other. Not real commits —
# the function never touches git, so any distinct hex strings prove the
# comparison logic.
_OLD_SHA = "d5e5f9a755d5e5f9a755d5e5f9a755d5e5f9a755"
_NEWER_SHA = "8096fcd0858096fcd0858096fcd0858096fcd08"


# ---------------------------------------------------------------------------
# GUILT — a real fork-point-behind-tip state must warn.
# ---------------------------------------------------------------------------


def test_guilt_stale_fork_point_behind_current_tip() -> None:
    """The exact shape that produced the trap: the branch's merge-base with
    origin/main is an OLDER commit than origin/main's current tip."""
    assert pf.is_stale_at_first_push(_OLD_SHA, _NEWER_SHA) is True


def test_guilt_still_warns_regardless_of_which_sha_is_lexically_larger() -> None:
    """The comparison is pure inequality, not an ordering/ancestry check (the
    caller already computed merge-base — this function must not silently
    re-derive its own notion of 'behind' from string/lexical order, which
    would be wrong for git SHAs)."""
    assert pf.is_stale_at_first_push(_NEWER_SHA, _OLD_SHA) is True


# ---------------------------------------------------------------------------
# INNOCENCE — the adjacent legitimate cases must NOT warn.
# ---------------------------------------------------------------------------


def test_innocence_fork_point_equals_current_tip() -> None:
    """A branch cut from exactly origin/main's current tip — the common,
    healthy case — must not warn."""
    assert pf.is_stale_at_first_push(_NEWER_SHA, _NEWER_SHA) is False


def test_innocence_merging_main_clears_the_warning() -> None:
    """The case reproduced live tonight (secrets-triage-kbli-gold): after
    `git merge origin/main`, origin/main becomes an ancestor of the local
    branch, so a fresh `git merge-base origin/main HEAD` now equals
    origin/main's tip itself. This is the WARN_MESSAGE's own recommended
    cure — it must actually resolve the condition, not just relabel it, and
    per the mandate this must not trip anything UNRELATED: merging main
    alone, with no other change, must read as fresh."""
    post_merge_merge_base = _NEWER_SHA  # merge-base(origin/main, HEAD) after merge
    assert pf.is_stale_at_first_push(post_merge_merge_base, _NEWER_SHA) is False


def test_innocence_empty_merge_base_does_not_warn() -> None:
    """Unknown state (e.g. the caller's own `git merge-base` failed) must
    never be read as evidence of staleness — the caller's diff-range logic
    already fails closed to the FULL suite on a git-plumbing failure; this
    is an ADDITIONAL, non-blocking signal, and a signal with no data is not
    a signal."""
    assert pf.is_stale_at_first_push("", _NEWER_SHA) is False


def test_innocence_empty_origin_main_sha_does_not_warn() -> None:
    assert pf.is_stale_at_first_push(_NEWER_SHA, "") is False


def test_innocence_both_empty_does_not_warn() -> None:
    assert pf.is_stale_at_first_push("", "") is False


# ---------------------------------------------------------------------------
# Sanity on the module's own constants — belt-and-suspenders against a
# WARN_MESSAGE that silently stops mentioning the actual cure.
# ---------------------------------------------------------------------------


def test_warn_message_names_the_actual_cure() -> None:
    """The escape hatch this file proves (merge origin/main, then push) must
    be the one the printed message tells a human/agent to run — the whole
    point is that this is a warn-only line someone has to act on themselves."""
    assert "merge origin/main" in pf.WARN_MESSAGE
    assert "push" in pf.WARN_MESSAGE


def test_warn_message_is_single_paragraph_no_raw_newlines() -> None:
    """Guards against a future edit reintroducing a bare '\\n' that would
    print as a broken multi-line shell echo instead of one warn line."""
    assert "\n" not in pf.WARN_MESSAGE


# ---------------------------------------------------------------------------
# CLI-level smoke tests — proves the actual argv/stdout/exit-code contract
# `.husky/pre-push` relies on, not just the pure function. Warn-only means
# the hook never captures this command's output or checks its exit code
# (deliberately, to sidestep task #39's bare-`$(...)`-under-`sh -e` class
# entirely) — so what matters here is: stale prints the message, fresh
# prints nothing, and BOTH exit 0, always.
# ---------------------------------------------------------------------------


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_MODULE_PATH), *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_cli_stale_prints_warning_and_exits_zero() -> None:
    result = _run_cli(_OLD_SHA, _NEWER_SHA)
    assert result.returncode == 0
    assert pf.WARN_MESSAGE in result.stdout


def test_cli_fresh_prints_nothing_and_exits_zero() -> None:
    result = _run_cli(_NEWER_SHA, _NEWER_SHA)
    assert result.returncode == 0
    assert result.stdout == ""


def test_cli_missing_args_fails_open_silently() -> None:
    """A malformed invocation (e.g. a future hook edit that forgets an argv
    slot) must never crash or print noise into the push output — warn-only
    fails open to silence, not to an error the caller might mistake for a
    push-blocking signal."""
    result = _run_cli()
    assert result.returncode == 0
    assert result.stdout == ""
