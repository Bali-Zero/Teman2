#!/usr/bin/env python3
"""probe_filters.py — acceptance probe for guard-ci-wiring, criterion "both relevance filters".

Extracts BOTH relevance filters from .github/workflows/guard-conformance.yml rather than
retyping them, then asserts the expected outcome for 7 paths: 4 positives that must match
in both filters, 3 negatives that must match in neither.

Why this file is committed instead of left in /tmp: the brief's `probe:` field has to name
a command a reader (or the ship gate) can actually run. A /tmp path is not reproducible.

Run from the repo root:
    python3 evidence/2026-09/agent-air-m5-infra-guard-ci-wiring-a2d8aefa/probe_filters.py
Exits 0 when every one of the 7 expectations holds, 1 otherwise.
"""
from __future__ import annotations

import fnmatch
import re
import sys

import yaml

WF = ".github/workflows/guard-conformance.yml"

POSITIVE = [
    "docs/specs/2026-09-18-secret-expansion-guard-shapes-spec.md",
    "infra/claude-hooks/secret_expansion_guard.py",
    "infra/claude-hooks/install_qwen_secret_guard.py",
    # The file that REGISTERS the hook. Missing from both filters before this PR, which is
    # what round 2 of the council returned BLOCKING on: a PR editing only this file could
    # unregister the guard and every required check would stay green.
    ".claude/settings.json",
]
NEGATIVE = [
    "docs/specs/2026-09-10-some-other-spec.md",
    "apps/mouth/src/lib/x.ts",
    # The near-miss: the grep regex is unanchored at the tail, so a settings-LOCAL edit
    # must NOT be mistaken for the hook wiring.
    ".claude/settings.local.json",
]


def main() -> int:
    raw = open(WF).read()
    doc = yaml.safe_load(raw)
    steps = [s for j in doc["jobs"].values() for s in j["steps"]]
    print("steps:", len(steps))

    # YAML parses the `on:` key as boolean True.
    trig = doc[True] if True in doc else doc.get("on")
    push_paths: set[str] = set()
    for cfg in trig.values():
        if isinstance(cfg, dict) and "paths" in cfg:
            push_paths |= set(cfg["paths"])
    print(
        "push_paths entries:",
        len(push_paths),
        "| has .claude/settings.json:",
        ".claude/settings.json" in push_paths,
    )

    rel = next(s for s in steps if s.get("id") == "relevant")["run"]
    # The regex lives on its own single-quoted line after `grep -qE \`.
    m = re.search(r"^\s*'(\^\(.*\))';\s*then\s*$", rel, re.M)
    if not m:
        print("FAIL: could not extract the `relevant` step's regex — its shape changed")
        return 1
    rx = m.group(1)
    print("regex extracted, chars:", len(rx))

    ok = True
    for path in POSITIVE:
        a = any(fnmatch.fnmatch(path, pat) for pat in push_paths)
        b = re.search(rx, path) is not None
        ok &= a and b
        print(f"POS {path:68s} push={a} regex={b}")
    for path in NEGATIVE:
        a = any(fnmatch.fnmatch(path, pat) for pat in push_paths)
        b = re.search(rx, path) is not None
        ok &= (not a) and (not b)
        print(f"NEG {path:68s} push={a} regex={b}")

    print("ALL_EXPECTED:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
