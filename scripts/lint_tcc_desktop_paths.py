#!/usr/bin/env python3
"""lint_tcc_desktop_paths.py — executable antidote for superscar #1 (HOME-fork
drift), W84/TCC variant: no tracked *.sh/*.py/*.plist payload may hardcode
`Desktop/nuzantara` (or `Desktop/nuzantara-deploy`).

THE DISEASE: ~/Desktop is one of macOS's three TCC-protected home folders
(Desktop/Documents/Downloads). A payload that reaches into ~/Desktop needs a
TCC grant that launchd can silently lose (scar W84, 4 recidives on M5). The
repo moved out of ~/Desktop to `~/nuzantara` on all three fleet machines
(2026-07-16); the payloads that hardcoded the old path were swept in the same
PR that adds this lint. Without a standing gate, the NEXT PR that copies a
launchd wrapper, forks a script, or pastes an example command re-plants the
same literal — the repo is the regeneration source (proven live: a sync hook
copied `scripts/mini/mini-git-pull.sh`'s Desktop-hardcoded default into
`~/scripts/mini-git-pull.sh` on Mini, undoing a manual HOME-side fix within 15
minutes). This lint is what makes that regeneration a build-blocking fact
instead of a silent leak.

SCOPE (deliberately narrower than the one-time sweep in
scripts/tcc_migrate_desktop_paths.py, which also swept *.json/*.yaml/*.swift/
docs): *.sh, *.py, *.plist — "the ones that bite" per the migration PR body.
Config/data files and docs can still legitimately reference a historical
Desktop path (a dated research capture, a FROZEN snapshot, a scar file) far
more often than a script or plist can — narrowing the STANDING gate to the
three executed-payload extensions keeps false positives near zero without
requiring an allowlist entry for every dated report ever written.

ALLOWLIST: infra/tcc-desktop-paths/allowlist.txt — declared exceptions (guard-
test corpus that deliberately asserts on the old notation, e.g.
infra/claude-hooks/test_tilde_target_resolver.py). An exception must be
DECLARED there, never silently absent from a violation list (scar #3
discipline: no guard ships without its exceptions being explicit).

SYMLINKS: a tracked symlink's raw target string is checked too (never
resolved/followed) — the same W84 gap found live on Pro
(~/Library/LaunchAgents/com.nuzantara.pg-organism-bridge-watchdog.plist was a
symlink whose TARGET crossed Desktop even though the file it pointed at was
fine; launchd resolves the link, not the content).

Usage:
    python3 scripts/lint_tcc_desktop_paths.py [--check] [--json]
Exit: 0 clean · 1 violation(s) found · 2 blind scan (0 files walked — git
      failure or wrong root, NOT a clean result, W84/W97 lesson) ·
      4 allowlist file present but unreadable/malformed (fail-visible, never
      silently treated as empty)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any


def _canonical_repo_root() -> Path:
    """Repo root: the tree THIS FILE physically lives in right now.

    DELIBERATELY NOT worktree-hardened like scripts/lint_home_fork.py (a
    defect shipped 2026-07-16, found by the coordinator's final-gate review
    before merge): lint_home_fork.py compares TWO independent trees (repo vs
    live HOME) — there an ephemeral agent worktree isn't the meaningful side
    to trust, so jumping OUT of .worktrees/ to the main checkout is correct.
    This tool does a SINGLE self-contained tree scan — there is no second
    tree to prefer. Jumping out of .worktrees/ here meant every no-args
    invocation from a dev worktree silently scanned the MAIN checkout
    instead of the tree you were trying to verify: the lint never saw your
    fix, and a canonical "add regression / remove regression" probe against
    main (itself un-swept pre-merge) returned violations no matter what you
    did in the worktree — a guard that can't distinguish clean from dirty
    proves nothing. Fix: resolve to wherever this file itself is checked out
    (worktree root when invoked from a worktree copy, main checkout root
    otherwise, CI checkout root in CI) — deterministic, and always the tree
    the invocation is actually running against.
    """
    return Path(__file__).resolve().parent.parent


REPO_ROOT = _canonical_repo_root()
LINT_EXTENSIONS = {".sh", ".py", ".plist"}


def _default_allowlist(repo_root: Path) -> Path:
    """infra/tcc-desktop-paths/allowlist.txt relative to repo_root — computed
    from whatever --repo-root resolves to (default or overridden), never a
    fixed path baked in at argparse-definition time. A static default bound
    to this module's own REPO_ROOT would silently stop applying the moment
    --repo-root is pointed anywhere else (the same class of bug as the
    REPO_ROOT fix above, just one layer further down) — this makes the
    positive case (declared allowlist entries suppress their violations) and
    the negative case (a malformed allowlist fails loudly) both fully
    testable against synthetic fixtures, not just the real checkout."""
    return repo_root / "infra" / "tcc-desktop-paths" / "allowlist.txt"


DEFAULT_ALLOWLIST = _default_allowlist(REPO_ROOT)


def _load_migrate_module():
    """Reuse the migrator's PATTERN + git/exclude helpers (single implementation
    of the regex + tracked-file-walk logic, same reuse pattern as
    infra/organ-conformance/check_organ_conformance.py importing
    scripts/lint_plist_keepalive.py).

    Deliberately loaded from THIS FILE's own directory, not from --repo-root:
    the two are the same repo in real CI usage, but coupling the import to the
    scan TARGET (rather than to where this tool itself lives) breaks the
    moment repo_root is a synthetic fixture in a test — the migrator is a
    fixed sibling file, not scan-target data."""
    path = Path(__file__).resolve().parent / "tcc_migrate_desktop_paths.py"
    spec = importlib.util.spec_from_file_location("tcc_migrate_desktop_paths", path)
    if spec is None or spec.loader is None:  # pragma: no cover — repo damage
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def scan(repo_root: Path, allowlist_path: Path | None) -> dict[str, Any]:
    """Returns {"violations": [...], "walked": int, "tracked_total": int,
    "git_failed": bool, "allowlist_error": str|None}.

    A violation is (relpath: str, detail: str, kind: "file"|"symlink").

    Three DISTINCT failure classes, never conflated (each earns its own exit
    code in main()):
      - git_failed:        `git ls-files` itself errored — the scan saw nothing
                            because it COULDN'T look, not because there was
                            nothing to find. Blind scan (W84/W97 discipline).
      - tracked_total == 0: git succeeded but the tree has zero tracked files
                            at all — an empty/wrong repo-root. Also blind scan.
      - walked == 0 (but tracked_total > 0): the repo has tracked files, none
                            of them matched the *.sh/*.py/*.plist scope or all
                            matches were allowlisted. This is a LEGITIMATE
                            clean state, not a blind scan — conflating it with
                            the above would make "everything is correctly
                            allowlisted" indistinguishable from "the scan
                            couldn't see the tree" (a real bug caught in this
                            PR's own test-writing: a fixture repo with a single
                            allowlisted .py file was misreported BLIND SCAN
                            before this distinction was added).
      - allowlist_error:    the allowlist file exists but couldn't be read —
                            fail-visible, never silently treated as "no
                            exceptions declared".
    """
    mod = _load_migrate_module()

    exclude: set[Path] = set()
    allowlist_error: str | None = None
    if allowlist_path is not None and allowlist_path.exists():
        try:
            exclude = mod._load_exclude(allowlist_path, repo_root)
        except (OSError, UnicodeDecodeError) as e:
            # UnicodeDecodeError is NOT an OSError subclass — a defect found
            # 2026-07-16 alongside the DEFECT-1 review: a genuinely malformed
            # (invalid-UTF-8) allowlist file crashed main() with an uncaught
            # traceback instead of the documented fail-visible exit 4.
            allowlist_error = f"allowlist unreadable ({type(e).__name__}): {allowlist_path}"
        # absent allowlist is NOT an error — a repo with zero declared
        # exceptions is a valid (if unusual) state.

    tracked = mod._git_tracked_files(repo_root)
    if tracked is None:
        return {
            "violations": [], "walked": 0, "tracked_total": 0,
            "git_failed": True, "allowlist_error": allowlist_error,
        }

    violations: list[tuple[str, str, str]] = []
    walked = 0
    for path in sorted(tracked):
        if path.suffix.lower() not in LINT_EXTENSIONS:
            continue
        if path.resolve() in exclude:
            continue
        relpath = str(path.relative_to(repo_root))

        if path.is_symlink():
            try:
                target = os.readlink(path)
            except OSError:
                continue  # unreadable link — not this lint's failure class to report
            walked += 1
            n = len(mod.PATTERN.findall(target))
            if n:
                violations.append((relpath, f"symlink target crosses Desktop: {target!r}", "symlink"))
            continue

        if not path.is_file():
            continue
        walked += 1
        text = mod._read_text(path)
        if text is None:
            continue  # binary / unreadable — same never-guess discipline as the migrator
        n = len(mod.PATTERN.findall(text))
        if n:
            violations.append((relpath, f"{n} occurrence(s)", "file"))

    return {
        "violations": violations, "walked": walked, "tracked_total": len(tracked),
        "git_failed": False, "allowlist_error": allowlist_error,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="alias for default behavior (kept for CLI symmetry with the migrator)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--repo-root", type=Path, default=REPO_ROOT, help=argparse.SUPPRESS)
    ap.add_argument("--allowlist", type=Path, default=None,
                     help="declared-exception file (default: <repo-root>/infra/tcc-desktop-paths/allowlist.txt, "
                          "computed from the resolved --repo-root — not a fixed path)")
    args = ap.parse_args(argv)
    allowlist_arg = args.allowlist if args.allowlist is not None else _default_allowlist(args.repo_root)

    result = scan(args.repo_root, allowlist_arg)
    violations = result["violations"]
    walked = result["walked"]
    tracked_total = result["tracked_total"]
    git_failed = result["git_failed"]
    allowlist_error = result["allowlist_error"]

    if args.json:
        print(json.dumps({
            "schema": 1,
            "violations": [{"path": p, "detail": d, "kind": k} for p, d, k in violations],
            "walked": walked,
            "tracked_total": tracked_total,
            "git_failed": git_failed,
            "allowlist_error": allowlist_error,
        }, indent=2))
    else:
        print(f"[tcc-desktop-paths] scanned {walked} tracked *.sh/*.py/*.plist file(s) "
              f"(allowlist: {allowlist_arg if allowlist_arg.exists() else 'none'})")
        for p, d, _k in violations:
            print(f"  - {p}: {d}")
        if not violations and not git_failed and not allowlist_error:
            print("  clean — no tracked payload hardcodes Desktop/nuzantara")
        if violations:
            print(
                f"\nTCC-DESKTOP-PATHS LINT FAIL — superscar #1 (W84 variant): a payload "
                f"hardcodes ~/Desktop/nuzantara. Either fix the path (Desktop/nuzantara -> "
                f"nuzantara, the repo's post-migration location) or, if this is a deliberate "
                f"exception (guard-test corpus, historical record), declare it in "
                f"{allowlist_arg.relative_to(args.repo_root) if allowlist_arg.is_relative_to(args.repo_root) else allowlist_arg}."
            )
        if git_failed:
            print("\n[error] git ls-files failed — scan could not see the tree at all.")
        if allowlist_error:
            print(f"\n[error] {allowlist_error}")

    # W84/W97 lesson: a scan that couldn't SEE anything is not a clean scan —
    # but "0 files matched the *.sh/*.py/*.plist scope (or all were
    # allowlisted)" IS a legitimate clean state and must not be confused with
    # it. git_failed / tracked_total==0 mean the scan was blind; walked==0
    # with tracked_total>0 means the scan looked and found nothing IN SCOPE.
    if git_failed or tracked_total == 0:
        print("BLIND SCAN: could not see the tracked tree — wrong repo-root, empty checkout, "
              "or git failure. NOT a clean result.", file=sys.stderr)
        return 2
    if allowlist_error:
        return 4
    if violations:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
