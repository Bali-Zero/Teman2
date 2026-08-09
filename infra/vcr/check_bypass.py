#!/usr/bin/env python3
"""infra/vcr/check_bypass.py — R7 bypass-rate tripwire, armed as a real check.

"Bypass rate = 0%" is not a statistic to report — it's a grep that must be run,
with a guilt case (a planted direct-read IS caught) and an innocence case (the
accessor's own internal read is NOT caught). "0 observed bypasses" without a
guilt case is a probe that cannot fail (final-gate-discipline Q4) — this file
is that probe, and test_bypass_tripwire.py is what proves it can say both yes
and no.

A "bypass" is any file OUTSIDE infra/vcr/ that reads
~/.organism/arsenal/last.json directly, or shells out to
`arsenal_probe.py --read-last`, to make a health decision — instead of going
through infra.vcr.accessor / infra/vcr/cli.py. Two classes are pre-existing
and out of THIS pilot's conversion scope (VCR spec §4 — "single pilot, not a
rollout"), and are allowlisted, not exempted-by-omission:
  - scripts/organism_digest.py: a hard-budgeted, non-blocking SessionStart
    receptor (SIGALRM 6s) — the accessor's lazy-probe-on-read semantics
    (R2) would violate that contract if wired in here.
  - infra/healer/healer-run.sh (Mini) and
    infra/launchagents/wrappers/pro-healer.sh (Pro, its twin, "Receptor D"):
    the LIVE REFRESHERS themselves (each WRITES the report via
    `arsenal_probe.py --quiet` when stale, then reads the fresh JSON to
    detect NEW_DEAD transitions for its own Telegram alert) — not a "read
    cached state and decide" consumer bypassing the accessor; orthogonal to
    what this accessor governs.
  - scripts/proprioception.py: converted PARTIALLY, on purpose. Its
    "arsenal_seats" wrap-probe entry (mini+pro, ALL 7 arsenal_probe seats,
    severity P1) is left untouched — this pilot registers only 3 seats
    (VCR spec §4/R8), and swapping that entry's target to the pilot's
    narrower accessor would silently SHRINK a P1 monitoring boundary that is
    out of scope to touch ("single pilot, not a rollout"). A SEPARATE new
    entry, "arsenal_seats_vcr_m5" (m5-only, severity P2 — filling a gap m5
    never had), IS routed through the accessor: that is this pilot's ONE
    real converted consumer (R7). The file legitimately contains both a
    declared pre-existing bypass and a new accessor-routed reader.
  - scripts/arsenal_probe.py and its two test files
    (scripts/tests/test_arsenal_probe.py, scripts/tests/test_organism_digest.py):
    the DEFINITIONAL source of the raw path and the `--read-last` flag, and
    the tests that exercise them directly — these are not a consumer
    reading cached state to make a health decision, they ARE the thing
    check_bypass.py is guarding access to. Declared here (not just in the
    tuple below) so "All are declared here" is actually true of the prose,
    not only the list (GLM red-team, 2026-08-03).
All are declared here so a future session extending the pilot's coverage
edits ONE list, not re-discovers the exemption from scratch.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BYPASS_PATTERN = re.compile(
    r"""
    \.organism/arsenal/last\.json   # direct path to the raw report
    | --read-last                    # the raw-report CLI escape hatch
    """,
    re.VERBOSE,
)

# Codex red-team (2026-08-03) found the substring match trivially evaded by
# non-literal spellings that mean the same thing: Path.home()/".organism"/
# "arsenal"/"last.json" (pathlib join, quotes+whitespace around the same
# path) and "--read" + "-last" (string concatenation). Stripping quotes,
# whitespace and `+` before matching catches both without chasing an
# unbounded arms race of possible obfuscations — this is a dev-discipline
# lint, not a security boundary against an adversarial actor, so "catches
# the two concrete forms found" is the proportionate bar, not "provably
# unevadable".
_NORMALIZE_RE = re.compile(r"""['"]|\s+|\+""")


def _normalized(text: str) -> str:
    return _NORMALIZE_RE.sub("", text)


ALLOWLIST_SUFFIXES = (
    "scripts/organism_digest.py",
    "infra/healer/healer-run.sh",
    "infra/launchagents/wrappers/pro-healer.sh",
    "scripts/proprioception.py",
    "scripts/arsenal_probe.py",
    "scripts/tests/test_arsenal_probe.py",
    "scripts/tests/test_organism_digest.py",
)

# GLM red-team (2026-08-03): scanning only .py/.sh silently missed config
# formats that could carry the same bypass programmatically (a cron/plist
# target, a YAML pipeline step). Verified empirically before adding these
# (2026-08-03): zero pre-existing matches repo-wide in these suffixes.
SCANNED_SUFFIXES = (".py", ".sh", ".yaml", ".yml", ".json", ".plist")
SCANNED_BASENAMES = ("Dockerfile",)


def find_bypass_violations(repo_root: Path, extra_allowlist: tuple[str, ...] = ()) -> list[str]:
    """Scans every tracked-looking file under repo_root for BYPASS_PATTERN,
    excluding infra/vcr/ itself (the accessor's own legitimate internals) and
    the declared allowlist. Returns file paths (relative, posix) with a hit."""
    allow = set(ALLOWLIST_SUFFIXES) | set(extra_allowlist)
    violations: list[str] = []
    # Skip-dir names to exclude *within* the scanned tree — checked against the
    # path RELATIVE to repo_root, never the absolute path. repo_root itself
    # commonly lives under a path containing one of these names (e.g. this
    # very package is built inside .worktrees/infra-vcr-pilot-build/) — an
    # absolute-path check would match every single file via that prefix and
    # silently scan zero of them (caught live: the real-repo test passed with
    # 0 violations even before proprioception.py's bypass was fixed).
    skip_dirs = {".git", "node_modules", ".worktrees", "__pycache__", ".venv"}
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        rel_path = path.relative_to(repo_root)
        if any(part in skip_dirs for part in rel_path.parts[:-1]):
            continue
        rel = rel_path.as_posix()
        if rel.startswith("infra/vcr/"):
            continue  # the accessor's own package: legitimate internal reads
        if rel in allow:
            continue
        if path.suffix not in SCANNED_SUFFIXES and not path.name.startswith(SCANNED_BASENAMES):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if BYPASS_PATTERN.search(text) or BYPASS_PATTERN.search(_normalized(text)):
            violations.append(rel)
    return violations


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parent.parent.parent
    violations = find_bypass_violations(repo_root)
    if violations:
        print("BYPASS TRIPWIRE FAILED — consumers reading arsenal state directly:")
        for v in violations:
            print(f"  {v}")
        return 1
    print("BYPASS TRIPWIRE OK — 0 unaccounted-for direct readers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
