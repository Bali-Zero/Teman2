#!/usr/bin/env python3
"""scar_test for superscar #1 — HOME-fork drift (deploy-path desync).

THE FAMILY THIS GUARDS (the single dominant disease, ~30% of all 86 scars):
  A launchd/cron job executes a COPY of a script under $HOME (~/scripts/,
  ~/.openclaw/bin/, ~/bin/) that silently DIVERGES from the git-tracked source
  of truth. The fix lands in the repo but the live copy never sees it — or worse,
  live work in the HOME copy never returns to the repo. Members: W50/51/52
  (wrapper/plist fork), W68/W70/W72/W73, W76, W81, and — 2026-06-27 — the
  wr2-deploy-pull.sh puller itself: PRs #1766/#1777 cured the repo while launchd
  kept running a stale 7-giu ~/scripts/ copy (EXPECTED_BRANCH=deploy/main),
  leaving the -deploy clone STERILE. The cure that the rings were supposed to
  prevent hid inside the cure.

THE STRUCTURAL ANTIDOTE (verbatim, cicatrix-superscar.md #1):
  "lint CI che fallisce se un file eseguito-live diverge (cmp -s) dalla versione
   tracciata su git, o se una config live punta a un path-HOME invece che al repo."
  This gate IS that lint, in executable form.

WHY THIS TEST PASSES (exit 0) WHILE THE FAMILY STILL EXISTS — read carefully:
  A scar_test is GREEN = "the disease is captured / under control", NOT "the
  disease is impossible". This gate proves the DETECTOR works (the antidote is
  armed), via the W82 guilt+innocence discipline:
    - GUILT  (a divergent HOME-fork IS detected):   two non-identical files →
              divergence reported TRUE.
    - INNOCENCE (an aligned copy is NOT a false alarm): a symlink-to-repo or a
              byte-identical copy → divergence reported FALSE.
  If both hold, the cmp-based detector is faithful and CI-runnable everywhere
  (no network, no host). That is the deterministic core — always green, always
  honest.

THE REAL TRIPWIRE (opt-in, where launchd actually lives — the Pro/Mini):
  Run with SCAR_HOMEFORK_LIVE=1 to ALSO scan the live launchd-executed scripts
  under $HOME and FAIL (exit 1) if any diverges from its git-tracked twin. This
  is the check that would have caught the puller weeks ago. It is env-gated so
  the deterministic core never depends on a host — CI stays green on the core,
  the operator/cron arms the live arm where it matters.

    python3 infra/scar-gates/test_W_homefork_live_vs_tracked.py            # core (CI)
    SCAR_HOMEFORK_LIVE=1 python3 infra/scar-gates/test_W_homefork_live_vs_tracked.py   # + live scan (Pro)

Exit 0 = detector faithful (core) AND no live HOME-fork divergence (if LIVE).
Exit 1 = detector broke (core regressed) OR a live script diverges from git (LIVE).

Reference: .claude/rules/cicatrix-superscar.md #1 · cicatrix-scars.md W50/W81 ·
           discovery 2026-06-27 (puller HOME-fork cured via symlink, pattern #1710)
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile


# --- The detector under test: byte-faithful divergence check (mirrors `cmp -s`).
def diverges(path_a: pathlib.Path, path_b: pathlib.Path) -> bool:
    """True iff the two files differ in content (the antidote's `cmp -s`).

    A symlink whose target IS path_b reads identical bytes → NOT divergent. A
    stale real-file copy with different bytes → divergent. This is exactly the
    decision the HOME-fork lint must make on (live ~/scripts copy) vs (repo).
    """
    try:
        return path_a.read_bytes() != path_b.read_bytes()
    except OSError:
        # An unreadable / missing live copy is itself a fork breach.
        return True


# --- GUILT + INNOCENCE: prove the detector is faithful (deterministic, CI-safe).
def _core_self_test() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        d = pathlib.Path(td)
        repo = d / "repo_script.sh"
        repo.write_text("#!/usr/bin/env bash\nEXPECTED_BRANCH=main\n")

        # INNOCENCE 1: a byte-identical copy must NOT be flagged.
        twin = d / "aligned_copy.sh"
        twin.write_text(repo.read_text())
        if diverges(twin, repo):
            failures.append("INNOCENCE(identical-copy): false alarm — identical bytes flagged as fork")

        # INNOCENCE 2: a symlink-to-repo (the actual cure we shipped) must NOT be flagged.
        link = d / "live_symlink.sh"
        try:
            link.symlink_to(repo)
            if diverges(link, repo):
                failures.append("INNOCENCE(symlink-to-repo): false alarm — the #1710 cure flagged as fork")
        except OSError:
            pass  # platform without symlink support — skip, not a failure

        # GUILT: a stale divergent copy (the real bug: EXPECTED_BRANCH=deploy/main) MUST be flagged.
        stale = d / "homefork_stale.sh"
        stale.write_text("#!/usr/bin/env bash\nEXPECTED_BRANCH=deploy/main\n")
        if not diverges(stale, repo):
            failures.append("GUILT(stale-fork): MISS — a divergent HOME-fork copy was NOT detected")

    return failures


# --- The live tripwire (opt-in): scan launchd-executed HOME scripts vs git.
# Map: live HOME path  ->  repo-relative tracked twin. Extend as forks are found.
_LIVE_FORK_MAP = {
    "~/scripts/wr2-deploy-pull.sh": "scripts/wr2-deploy-pull.sh",
}


def _repo_root() -> pathlib.Path:
    here = pathlib.Path(__file__).resolve()
    # infra/scar-gates/<this> -> repo root is two parents up.
    return here.parent.parent.parent


def _live_scan() -> list[str]:
    breaches: list[str] = []
    root = _repo_root()
    for live_rel, tracked_rel in _LIVE_FORK_MAP.items():
        live = pathlib.Path(os.path.expanduser(live_rel))
        tracked = root / tracked_rel
        if not live.exists():
            continue  # not present on this host — not a breach (e.g. M5 has no puller)
        if not tracked.exists():
            breaches.append(f"LIVE: tracked twin missing for {live_rel} -> {tracked_rel}")
            continue
        # A symlink resolving into the repo is the cured state — read_bytes follows it.
        if diverges(live, tracked):
            real = os.path.realpath(live)
            breaches.append(
                f"LIVE HOME-FORK: {live_rel} diverges from git {tracked_rel} "
                f"(realpath={real}) — fix #1 lint: symlink live -> repo (pattern #1710)"
            )
    return breaches


def main() -> int:
    core_failures = _core_self_test()
    if core_failures:
        print("DISARMED — HOME-fork detector REGRESSED (core self-test failed):")
        for f in core_failures:
            print(f"  - {f}")
        return 1

    if os.getenv("SCAR_HOMEFORK_LIVE") == "1":
        breaches = _live_scan()
        if breaches:
            print("SCAR RE-BIT (#1 HOME-fork) — live launchd script diverges from git:")
            for b in breaches:
                print(f"  - {b}")
            return 1
        print("OK (#1 HOME-fork) — detector faithful AND no live divergence (LIVE scan clean).")
        return 0

    print("OK (#1 HOME-fork) — detector faithful (core). Run with SCAR_HOMEFORK_LIVE=1 on Pro for the live scan.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
