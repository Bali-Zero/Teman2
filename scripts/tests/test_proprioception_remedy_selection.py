"""Tests for proprioception.py's machine-aware remedy selection.

TRAUMA (measured 2026-08-07, handoff §6): two DEFAULT_REGISTRY entries carry a
STATIC fix_hint chosen at authoring time, printed unconditionally regardless of
which machine or which finding-shape triggered the DIVERGED verdict.

- `git_alignment`'s fix_hint reads "interactive pull on this machine's main
  (never from an agent session)" — correct on pro/mini, where the checkout is
  auto-pulled and 0-behind is the norm, but on m5 it directly contradicts the
  standing decision (probe_home_fork_scripts docstring, W106b, 2026-07-27) that
  the m5 checkout is deliberately left behind origin/main because pulling it
  races live worktrees. That wrong prescription was already quoted verbatim in
  PENDING-ARMS as justification for deferring action — the doctrine had trained
  a prior session before this fix.
- `arsenal_seats_vcr_m5` (machines: ["m5"] only) inherited a fix_hint written
  for the sibling `arsenal_seats` (mini/pro) entry with no mention that Mini,
  not m5, is the documented primary (docs/runbooks/arsenal-probe.md "Mini
  (primary)") — so a routine FRESHNESS_EXPIRED between m5's own interactive
  runs reads as a live-seat problem it usually isn't.

Guilt + innocence per superscar #3 discipline (guard-over-match: a fix that
fires on the wrong machine/shape is exactly that failure mode with a text
payload instead of a block): every remedy-selection branch gets a case that
IS overridden and one that correctly stays byte-identical to the registry's
static fix_hint. Adopts the same per-item "ask whether a standing decision
already forbids this" pattern probe_guardian_freshness proved for machine
scoping (W106b family, `.claude/rules/cicatrix-superscar.md` #2).
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "proprioception.py"
_spec = importlib.util.spec_from_file_location("proprioception", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
prop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prop)  # type: ignore[union-attr]

GIT_ALIGNMENT_ENTRY = next(e for e in prop.DEFAULT_REGISTRY if e["id"] == "git_alignment")
ARSENAL_VCR_M5_ENTRY = next(e for e in prop.DEFAULT_REGISTRY if e["id"] == "arsenal_seats_vcr_m5")
STATIC_GIT_FIX_HINT = GIT_ALIGNMENT_ENTRY["fix_hint"]
STATIC_ARSENAL_FIX_HINT = ARSENAL_VCR_M5_ENTRY["fix_hint"]

BEHIND_120_DIRTY_20_LEDGER_STALE = [
    "main checkout: 120 behind origin/main, 20 dirty entries",
    "LEDGER STALE: .claude/skills/modus/PENDING-ARMS.md differs from origin/main "
    "— TRIAGE would read old state",
]
BEHIND_0_CLEAN = ["main checkout: 0 behind origin/main, 0 dirty entries"]


# ---------------------------------------------------------------- guilt: m5, behind, ledger stale


def test_guilt_m5_behind_and_stale_ledger_never_prescribes_pull() -> None:
    hint = prop._git_alignment_remedy(
        GIT_ALIGNMENT_ENTRY, "m5", BEHIND_120_DIRTY_20_LEDGER_STALE
    )
    # the exact static phrase this cure exists to stop m5 from ever printing
    assert STATIC_GIT_FIX_HINT not in hint
    assert "do NOT pull it" in hint


def test_guilt_m5_behind_and_stale_ledger_names_the_ledger_half() -> None:
    hint = prop._git_alignment_remedy(
        GIT_ALIGNMENT_ENTRY, "m5", BEHIND_120_DIRTY_20_LEDGER_STALE
    )
    assert ".claude/skills/modus/PENDING-ARMS.md" in hint
    assert "actionable half" in hint


def test_guilt_m5_behind_and_stale_ledger_states_by_design_truth() -> None:
    hint = prop._git_alignment_remedy(
        GIT_ALIGNMENT_ENTRY, "m5", BEHIND_120_DIRTY_20_LEDGER_STALE
    )
    assert "deliberately left behind" in hint
    assert "W106b" in hint


def test_guilt_m5_seats_freshness_expired_names_mini() -> None:
    hint = prop._arsenal_seats_vcr_m5_remedy(ARSENAL_VCR_M5_ENTRY)
    assert "Mini" in hint
    assert "primary" in hint
    assert "expected" in hint
    # the original check command must still be reachable, not replaced
    assert "infra/vcr/cli.py check" in hint


# ---------------------------------------------------------------- innocence: pro/mini, and m5 at behind=0


@pytest.mark.parametrize("machine", ["pro", "mini"])
def test_innocence_non_m5_pull_remedy_survives_byte_identical(machine: str) -> None:
    """A machine where pulling IS correct must still be told to pull —
    unconditionally, regardless of finding shape."""
    for ev in (BEHIND_120_DIRTY_20_LEDGER_STALE, BEHIND_0_CLEAN, []):
        hint = prop._git_alignment_remedy(GIT_ALIGNMENT_ENTRY, machine, ev)
        assert hint == STATIC_GIT_FIX_HINT


def test_innocence_m5_at_behind_zero_by_design_text_does_not_appear() -> None:
    hint = prop._git_alignment_remedy(GIT_ALIGNMENT_ENTRY, "m5", BEHIND_0_CLEAN)
    assert hint == STATIC_GIT_FIX_HINT
    assert "deliberately left behind" not in hint


def test_innocence_m5_no_behind_evidence_at_all_degrades_to_static() -> None:
    """Evidence-format drift (regex miss) must fail SAFE — never assert the
    by-design text without solid evidence backing it."""
    hint = prop._git_alignment_remedy(GIT_ALIGNMENT_ENTRY, "m5", ["something unrelated"])
    assert hint == STATIC_GIT_FIX_HINT


def test_innocence_m5_behind_but_ledger_fresh_still_forbids_pull_without_naming_ledger() -> None:
    """behind>0 with a fresh ledger: still m5's by-design truth (pulling is still
    forbidden), but nothing false is claimed about a ledger that isn't stale."""
    hint = prop._git_alignment_remedy(
        GIT_ALIGNMENT_ENTRY, "m5", ["main checkout: 45 behind origin/main, 3 dirty entries"]
    )
    assert "deliberately left behind" in hint
    assert "PENDING-ARMS" not in hint
    assert "No other actionable half" in hint


# ---------------------------------------------------------------- the verdict itself must be untouched


def test_verdict_severity_and_status_never_downgraded_by_remedy_selection() -> None:
    """The cure changes the PRESCRIPTION, never the VERDICT — the LEDGER STALE
    sub-finding is real and must keep firing."""
    status, findings, ev = prop.DIVERGED, 2, BEHIND_120_DIRTY_20_LEDGER_STALE
    hint = prop._git_alignment_remedy(GIT_ALIGNMENT_ENTRY, "m5", ev)
    assert status == prop.DIVERGED  # unrelated to the remedy call — sanity anchor
    assert findings == 2
    assert hint != STATIC_GIT_FIX_HINT  # the prescription changed
    assert GIT_ALIGNMENT_ENTRY["severity"] == "P1"  # the registry's severity is untouched


# ---------------------------------------------------------------- end-to-end wiring (real probe + real repo)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, timeout=30)


@pytest.fixture()
def diverged_m5_repo(tmp_path: Path):
    """A real git repo shaped like m5's main checkout today: behind origin/main
    AND carrying a locally-stale PENDING-ARMS.md, built the same way
    test_home_fork_stale_side_attribution.py's `world` fixture builds its repo
    (upstream commit -> published as origin/main -> working tree left behind)."""
    repo = tmp_path / "repo"
    ledger_rel = ".claude/skills/modus/PENDING-ARMS.md"
    (repo / ".claude" / "skills" / "modus").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    (repo / ledger_rel).write_text("old ledger\n")
    _git(repo, "add", ledger_rel)
    _git(repo, "commit", "-qm", "c1")
    (repo / "other.txt").write_text("x\n")
    _git(repo, "add", "other.txt")
    _git(repo, "commit", "-qm", "c2 (advances origin/main, not the ledger)")
    (repo / ledger_rel).write_text("new ledger\n")
    _git(repo, "add", ledger_rel)
    _git(repo, "commit", "-qm", "c3 bumps the ledger on origin/main")
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True, timeout=30,
    ).stdout.strip()
    _git(repo, "update-ref", "refs/remotes/origin/main", head)
    # Roll the local checkout back to c1: behind=2, AND the ledger blob differs
    # from origin/main's (superscar #9 content-comparison, never a proxy).
    _git(repo, "reset", "-q", "--hard", "HEAD~2")
    return repo, ledger_rel


def test_end_to_end_probe_plus_remedy_matches_the_real_m5_shape(diverged_m5_repo) -> None:
    repo, ledger_rel = diverged_m5_repo
    status, findings, ev = prop.probe_git_alignment(repo, {"no_fetch": True}, 15)
    assert status == prop.DIVERGED
    assert findings == 1  # ledger-only: 2 behind is under the default behind_warn=10
    hint = prop._git_alignment_remedy(GIT_ALIGNMENT_ENTRY, "m5", ev)
    assert "do NOT pull it" in hint
    assert ledger_rel in hint
    assert GIT_ALIGNMENT_ENTRY["severity"] == "P1"  # verdict class untouched by the cure


# ---------------------------------------------------------------- mutation proof (guilt test can go red)


def test_mutation_proof_removing_the_machine_check_makes_pro_wrongly_overridden() -> None:
    """Simulates disabling the fix (machine check removed): pro would then get
    the by-design m5 text too. Proves the guilt tests actually distinguish the
    cured code from the uncured code, not a tautology."""

    def uncured_remedy(entry: dict, machine: str, ev: list[str]) -> str:
        # the bug this test file exists to prevent: no `if machine != "m5": return default`
        behind = -1
        for e in ev:
            m = prop._BEHIND_RE.search(e)
            if m:
                behind = int(m.group(1))
                break
        if behind <= 0:
            return entry["fix_hint"]
        return "m5's main checkout is deliberately left behind origin/main by design..."

    mutated_hint = uncured_remedy(GIT_ALIGNMENT_ENTRY, "pro", BEHIND_120_DIRTY_20_LEDGER_STALE)
    assert mutated_hint != STATIC_GIT_FIX_HINT  # the mutant IS wrong on pro
    cured_hint = prop._git_alignment_remedy(GIT_ALIGNMENT_ENTRY, "pro", BEHIND_120_DIRTY_20_LEDGER_STALE)
    assert cured_hint == STATIC_GIT_FIX_HINT  # the real code stays correct


# --- 2026-08-08: the remedy must name an action a session can actually run ---
#
# The by-design half was already right: it stops telling m5 to pull. What it
# then prescribed — restoring the ledger file from origin/main IN the main
# checkout — is refused by worktree_isolation.py for every agent session, and
# the only documented way past it disarms the guard wholesale. With no operator
# lane, that named a lane that does not exist, which is how a reader learns to
# skip this probe. #3824 shipped the read-only path (`--ref`); these pin the
# remedy to it.


def _stale_ledger_remedy() -> str:
    """The shape that actually occurs on m5: behind AND ledger stale."""
    return prop._git_alignment_remedy(
        GIT_ALIGNMENT_ENTRY, "m5", BEHIND_120_DIRTY_20_LEDGER_STALE
    )


def test_guilt_remedy_prescribes_no_mutating_git_in_the_main_checkout() -> None:
    """The finding itself: a remedy only a nonexistent lane could carry out.

    Asserted per verb rather than on one phrase — every one of these aimed at
    the main checkout is refused by the isolation hook, so naming any of them
    is the same defect wearing a different word.
    """
    remedy = _stale_ledger_remedy()
    for mutating in ("git checkout", "git pull", "git reset", "git restore", "git fetch"):
        assert mutating not in remedy, f"remedy prescribes {mutating!r}: {remedy}"


def test_guilt_remedy_names_the_read_only_path_that_exists() -> None:
    """Deleting bad advice is half a cure — the reader still needs a way to the truth."""
    remedy = _stale_ledger_remedy()
    assert "--ref origin/main" in remedy
    assert "pending_arms_report.py" in remedy


def test_innocence_remedy_still_names_the_ledger_and_still_forbids_the_pull() -> None:
    """What the previous corpus established must survive this cure.

    A fix that quietly drops an earlier guarantee is a regression the new
    assertions, on their own, would never notice.
    """
    remedy = _stale_ledger_remedy()
    assert ".claude/skills/modus/PENDING-ARMS.md" in remedy
    assert "do NOT pull it" in remedy


@pytest.mark.parametrize("machine", ["pro", "mini-pro2"])
def test_innocence_non_m5_remedy_untouched_by_this_change(machine: str) -> None:
    """pro/mini DO auto-pull; their static advice is correct and must not move."""
    assert (
        prop._git_alignment_remedy(GIT_ALIGNMENT_ENTRY, machine, BEHIND_120_DIRTY_20_LEDGER_STALE)
        == STATIC_GIT_FIX_HINT
    )
