"""Lint: the mata_garuda cron wrapper must live in the REPO, never a HOME-fork.

cicatrix #1 (HOME-fork drift): the split-brain of 2026-06-30 happened because the
live cron wrapper was ~/scripts/matagaruda-cron-tcc-safe.sh — a copy outside git
that hardcoded the Mini Redis host. The repo fix never reached it. This lint makes
that class of drift fail CI:
  1. the canonical wrapper EXISTS in the repo,
  2. it points at the Pro-canonical Redis (not Mini),
  3. it is path-aware (no /Users/<user> hardcode),
  4. no committed installer/plist references the ~/scripts/ HOME-fork path.
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent          # apps/mata-garuda
WRAPPER = ROOT / "scripts" / "matagaruda-cron-tcc-safe.sh"
INFRA = ROOT / "infra" / "launchagents"


def test_wrapper_exists_in_repo():
    assert WRAPPER.is_file(), f"canonical cron wrapper missing from repo: {WRAPPER}"


def test_wrapper_targets_pro_canonical_not_mini():
    # check the EXECUTABLE export line, not comments (which may mention the old Mini IP)
    export_lines = [l for l in WRAPPER.read_text().splitlines()
                    if "export GARUDA_REDIS_HOST" in l and not l.lstrip().startswith("#")]
    assert export_lines, "no GARUDA_REDIS_HOST export found in wrapper"
    line = export_lines[0]
    assert "100.93.236.6" not in line, f"wrapper still defaults to Mini: {line.strip()}"
    assert "127.0.0.1" in line, f"wrapper must default to Pro 127.0.0.1: {line.strip()}"


def test_wrapper_is_path_aware_no_user_hardcode():
    s = WRAPPER.read_text()
    # REPO_ROOT must derive from the script location, not a hardcoded /Users/<user>
    assert "/Users/nuzantara/Desktop/nuzantara" not in s, \
        "wrapper hardcodes /Users/nuzantara — must derive REPO_ROOT from script location"


def test_no_committed_file_references_homefork_wrapper():
    """No installer/script in the repo may invoke the ~/scripts/ HOME-fork copy."""
    # the migration script legitimately NAMES the home-fork path (its job is to
    # migrate crons AWAY from it) — it is the one allowed exception.
    ALLOWED = {"migrate_crons_to_repo_wrapper.sh"}
    offenders = []
    for p in list(INFRA.glob("*.sh")) + list((ROOT / "scripts").glob("*.sh")):
        if p.name in ALLOWED:
            continue
        s = p.read_text()
        # the home-fork path; allow it only inside an explanatory comment line
        for i, line in enumerate(s.splitlines(), 1):
            if "/scripts/matagaruda-" in line and ".sh" in line and not line.lstrip().startswith("#"):
                if "$HOME/scripts" in line or "~/scripts" in line or "/Users/" in line:
                    offenders.append(f"{p.name}:{i}: {line.strip()}")
    assert not offenders, "committed files reference the HOME-fork wrapper:\n" + "\n".join(offenders)


GAP_WRAPPER = ROOT / "scripts" / "matagaruda-gap-consumer.sh"


def test_gap_wrapper_in_repo_and_path_aware():
    assert GAP_WRAPPER.is_file(), f"gap-consumer wrapper missing from repo: {GAP_WRAPPER}"
    s = GAP_WRAPPER.read_text()
    # check EXECUTABLE lines only (comments may explain the old hardcode/bug)
    code = [l for l in s.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    code_s = "\n".join(code)
    assert "/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda" not in code_s, \
        "gap wrapper hardcodes a user path — derive REPO from script location"
    # must NOT default REPO to a .worktrees path (the dead-worktree exit-1 bug)
    assert ".worktrees" not in code_s, "gap wrapper defaults REPO to a .worktrees path (dead-worktree risk)"
