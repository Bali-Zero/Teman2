#!/usr/bin/env python3
"""Machine-local attestation of the turn-1 injected context surface.

WHY THIS EXISTS, and what it is honest about
--------------------------------------------
A Claude Code session auto-loads, before the first user turn, the global
``~/.claude/CLAUDE.md``, the repo-root ``CLAUDE.md``, and every ``*.md`` in the
repo's ``.claude/rules/``. On 2026-08-31 that totalled 783,444 bytes — roughly
190-220K tokens paid by every session AND every subagent, for a corpus almost
none of them queried.

There are two different claims one can make about that number, and conflating
them is how this stopped being noticed for a week:

* **structural attestation** — what the harness WOULD load, reconstructed from
  repo state. That is ``scripts/tests/test_injected_surface_budget.py``: it
  runs in CI, and it cannot read a machine-local file.
* **machine-local attestation** — this script. It adds the two things CI is
  blind to: the global ``~/.claude/CLAUDE.md`` (per-machine, HOME-fork,
  superscar family #1) and the machine's own ``claudeMdExcludes`` setting. It
  is what makes the number comparable across Pro / Mini / M5.

Neither is a *delivery* attestation in the strict sense: only a live session's
own transcript witnesses what the harness actually handed over. This script's
job is to put the number into every transcript, so a drift that leaves no repo
diff still becomes visible to the next reader instead of growing in silence.

THE EXCLUSION IS NOT CREDITED, DELIBERATELY
-------------------------------------------
``~/.claude/settings.json`` on all three machines has carried
``claudeMdExcludes`` for the two scar bodies since 2026-06-14. Measured on M5
on 2026-08-31: a session started 4.5 h after that file was last written still
received both files in full. So the setting is armed and does not exclude
(superscar #2). This script therefore counts every loadable file and reports
the exclusion list separately as a claim it does not believe. If someone later
proves the mechanism works, deleting that scepticism is a one-function edit —
crediting it now would hide exactly the regression it is here to catch.

Exit codes: 0 always when run as a hook (never block boot). With ``--strict``
it exits 1 when the total exceeds the budget, for use in a probe.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# INTERIM pending a Zero ruling (wave-2 plan §6.3 default: 120 KB as a NOTICE,
# not a FAIL). Kept as one named constant so the ruled value is a one-line edit.
INTERIM_BYTE_BUDGET = 120_000

PINNED_RULES_MEMBERS = frozenset(
    {
        "cicatrix-superscar.md",
        "doc-generator-blocklist.md",
        "frontend-nextjs.md",
        "infrastructure.md",
        "python-backend.md",
    }
)


def _repo_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    # <repo>/scripts/injected_surface_attest.py -> <repo>
    return Path(__file__).resolve().parents[1]


def measure(repo_root: Path, home: Path) -> dict[str, object]:
    """Every file the harness can load at turn 1, sized on THIS machine."""
    sources: dict[str, int] = {}

    global_md = home / ".claude" / "CLAUDE.md"
    if global_md.is_file():
        sources[f"~/{global_md.relative_to(home)}"] = global_md.stat().st_size

    project_md = repo_root / "CLAUDE.md"
    if project_md.is_file():
        sources["CLAUDE.md"] = project_md.stat().st_size

    rules_dir = repo_root / ".claude" / "rules"
    unpinned: list[str] = []
    if rules_dir.is_dir():
        # rglob, matching the CI guard exactly. Two probes of the same surface
        # that disagree about what counts are worse than one: the smaller number
        # would be the reassuring one, and it would be the wrong one.
        for path in sorted(rules_dir.rglob("*.md")):
            sources[path.relative_to(repo_root).as_posix()] = path.stat().st_size
            rel = path.relative_to(rules_dir).as_posix()
            if rel not in PINNED_RULES_MEMBERS:
                unpinned.append(rel)

    # Read, but do NOT subtract — see the module docstring.
    excludes: list[str] = []
    settings = home / ".claude" / "settings.json"
    if settings.is_file():
        try:
            excludes = json.loads(settings.read_text()).get("claudeMdExcludes", []) or []
        except (json.JSONDecodeError, OSError):
            excludes = ["<settings.json unreadable>"]

    # Judged on the REPO side alone. The global CLAUDE.md is found from HOME and
    # would otherwise mask a completely wrong --repo-root behind a green line —
    # measured 2026-08-31: `--repo-root /definitely/missing` printed
    # "✅ 27,377 B (1 files)". One real file is not evidence that the resolver
    # resolved; it is evidence that a different resolver did.
    repo_side = [k for k in sources if not k.startswith("~/")]
    return {
        "resolver_found_nothing": not repo_side,
        "machine": os.uname().nodename,
        "repo_root": str(repo_root),
        "total_bytes": sum(sources.values()),
        "budget_bytes": INTERIM_BYTE_BUDGET,
        "sources": sources,
        "unpinned_rules_files": unpinned,
        "declared_excludes_not_credited": excludes,
    }


def _human(result: dict[str, object]) -> str:
    total = int(result["total_bytes"])  # type: ignore[arg-type]
    budget = int(result["budget_bytes"])  # type: ignore[arg-type]
    if result["resolver_found_nothing"]:
        # Zero files is never good news: it means the repo root or HOME is wrong,
        # and a green 0 B would read as "budget respected" (superscar #2).
        return (
            f"❌ INJECTED SURFACE: no repo-side files found under "
            f"{result['repo_root']} — a wrong repo root, not a lean surface "
            f"(the {total:,} B counted are machine-local files found from HOME)"
        )
    mark = "✅" if total <= budget else "⚠️"
    line = (
        f"{mark} INJECTED SURFACE {total:,} B / budget {budget:,} B "
        f"({len(result['sources'])} files, {result['machine']})"  # type: ignore[arg-type]
    )
    unpinned = result["unpinned_rules_files"]
    if unpinned:
        line += f" — UNPINNED in .claude/rules/: {', '.join(unpinned)}"  # type: ignore[arg-type]
    if total > budget:
        top = sorted(result["sources"].items(), key=lambda kv: -kv[1])[:4]  # type: ignore[union-attr]
        line += "\n   biggest: " + ", ".join(f"{k} {v:,}B" for k, v in top)
    return line


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="injected_surface_attest")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--repo-root", help="override the repo root (default: this script's repo)")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 when over budget (probe mode); as a SessionStart hook, never pass this",
    )
    args = ap.parse_args(argv)

    result = measure(_repo_root(args.repo_root), Path.home())
    print(json.dumps(result, indent=2) if args.json else _human(result))

    if result["resolver_found_nothing"]:
        return 2  # distinct from "over budget": a broken probe is its own failure
    if args.strict and int(result["total_bytes"]) > int(result["budget_bytes"]):  # type: ignore[arg-type]
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
