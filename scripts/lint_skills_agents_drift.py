#!/usr/bin/env python3
"""lint_skills_agents_drift.py — the immune system for ~/.claude/{skills,agents}.

opus-mythos TAC Skills&Agents organ (2026-06-16). The TAC found the same disease
the hooks vaccine cured: NO pre-flight validation that a skill/agent's hardcoded
assumptions match THIS machine. So drift accumulates silently and only fails at
runtime, inside an agent invocation.

This lint catches two drift classes BEFORE they bite:
  1. HOME-FORK: a literal `/Users/nuzantara` (or any user that isn't the running
     user's home) in a live skill/agent file — dead on a `balizero` box.
  2. STALE MODEL: a deprecated model ID (claude-opus-4-7/4-6, claude-sonnet-4-5,
     deepseek-reasoner, claude-3-*) that no longer resolves or silently degrades.

CRUCIAL — the TAC's own meta-lesson: the discovery subagents counted 931 + 644
"hits" by grepping INSIDE historical .log files. The real count was ~16 + 6.
So this lint EXCLUDES non-live files (.log, .bak*, .pre-*, _archive/, .archive/,
_observations/, _carousels-by-session/) — it lints only files that are actually
loaded/executed. Counting noise is how you cry wolf.

Exit 0 = clean. Exit 1 = drift found (prints offenders). Designed to run as a
local cron / SessionStart check and as the self-verify step of the fixer.

Usage:
  python3 lint_skills_agents_drift.py            # lint ~/.claude/{skills,agents}
  python3 lint_skills_agents_drift.py --root DIR # lint a specific dir
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys

HOME = pathlib.Path(os.path.expanduser("~"))
DEFAULT_ROOTS = [HOME / ".claude" / "skills", HOME / ".claude" / "agents"]

# Path COMPONENTS that mark a file as HISTORY/BACKUP, not live (the cry-wolf fix).
# Matched as a PREFIX so dated variants like `_archive-2026-05-24` are caught too
# (an exact-set match missed them — found by the lint linting itself, 2026-06-16).
EXCLUDE_PREFIXES = (
    "_archive", ".archive", "_observations", "_carousels-by-session",
    "node_modules", ".venv",
)
# Exact component names to exclude (no prefix semantics).
EXCLUDE_EXACT = ("past",)
EXCLUDE_SUFFIX_RE = re.compile(r"\.(log|bak[-.\w]*|pre-[-.\w]*)$|\.bak$|\.pre-", re.IGNORECASE)
# Only lint files that are actually loaded/run by the harness.
LIVE_SUFFIXES = (".md", ".py", ".json", ".sh", ".yaml", ".yml")

# Drift 1: any /Users/<other> that is NOT the running user's home. We flag the
# canonical HOME-fork literal explicitly + any /Users/<name> != current user.
CURRENT_USER = os.environ.get("USER") or HOME.name
HOMEFORK_RE = re.compile(r"/Users/(?!" + re.escape(CURRENT_USER) + r"\b)([A-Za-z0-9._-]+)")

# Drift 2: deprecated model IDs (per CLAUDE.md current roster).
STALE_MODELS = (
    "claude-opus-4-7", "claude-opus-4-6", "claude-sonnet-4-5",
    "claude-opus-4.7", "opus-4-7", "deepseek-reasoner", "deepseek-chat",
    "claude-3-5", "claude-3-opus", "gemini-2.5",
)
STALE_MODEL_RE = re.compile("|".join(re.escape(m) for m in STALE_MODELS))


def _is_live(p: pathlib.Path) -> bool:
    if p.suffix.lower() not in LIVE_SUFFIXES:
        return False
    if EXCLUDE_SUFFIX_RE.search(p.name):
        return False
    for comp in p.parts:
        if comp in EXCLUDE_EXACT:
            return False
        if any(comp.startswith(pre) for pre in EXCLUDE_PREFIXES):
            return False
    return True


def lint(roots: list[pathlib.Path]) -> list[str]:
    findings: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file() or not _is_live(p):
                continue
            try:
                text = p.read_text(errors="replace")
            except Exception:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                for m in HOMEFORK_RE.finditer(line):
                    # ignore /Users/Shared and obviously-generic doc placeholders
                    if m.group(1) in ("Shared", "<user>", "USERNAME", "you"):
                        continue
                    findings.append(f"HOME-FORK {p}:{i}: /Users/{m.group(1)} (running user: {CURRENT_USER}) — {line.strip()[:90]}")
                if STALE_MODEL_RE.search(line):
                    findings.append(f"STALE-MODEL {p}:{i}: {line.strip()[:90]}")
    return findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", help="dir(s) to lint (default ~/.claude/skills + agents)")
    args = ap.parse_args()
    roots = [pathlib.Path(r) for r in args.root] if args.root else DEFAULT_ROOTS

    findings = lint(roots)
    if not findings:
        print(f"✓ skills/agents drift lint CLEAN (user={CURRENT_USER}, roots={[str(r) for r in roots]})")
        return 0
    print(f"✗ {len(findings)} drift finding(s) in live skill/agent files (user={CURRENT_USER}):\n")
    for f in findings:
        print("  " + f)
    print("\nFix: HOST_BOUNDARY_OFF=1 bash scripts/fix_skills_agents_drift.sh")
    print("(HOME-fork → use ~ / $HOME; stale model → current roster opus-4-8 / sonnet-4-6 / deepseek-v4-pro)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
