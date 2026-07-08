#!/usr/bin/env python3
"""check_baseline_ratchet.py — the grandfather baseline is a ONE-WAY ratchet.

Panel round-2 (Codex 3, Grok 8, GLM S6): nothing stopped `--update-baseline`
from quietly re-growing the allowed-missing set — a careless regen after a
regression would bake the regression in as the new floor, and the convergence
metric could ratchet BACKWARD invisibly.

This check compares genes.json's `grandfathered` in the working tree against
the version on a base ref (origin/main in CI):

  FAIL if any organ appears in the baseline that was not there before
       (a NEW organ must be born conformant, never grandfathered), or
  FAIL if any organ's missing-set GREW (a gene once present may never be
       un-required).

Shrinking and disappearing entries are the only allowed direction. Exit 0 ok,
1 ratchet violated, 2 cannot compare (fail-visible: an uncomparable ratchet is
not a passing ratchet).

Usage: python3 infra/organ-conformance/check_baseline_ratchet.py [--base origin/main]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GENES_REL = "infra/organ-conformance/genes.json"


def load_grandfathered_at(ref: str, repo_root: Path) -> dict[str, list[str]] | None:
    out = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{ref}:{GENES_REL}"],
        capture_output=True, text=True, check=False,
    )
    if out.returncode != 0:
        return None
    try:
        return json.loads(out.stdout).get("grandfathered", {})
    except json.JSONDecodeError:
        return None


def compare(base: dict[str, list[str]], current: dict[str, list[str]]) -> list[str]:
    violations: list[str] = []
    for path, missing in current.items():
        if path not in base:
            violations.append(
                f"NEW grandfathered entry: {path} (missing {sorted(missing)}) — "
                f"new organs must be born conformant, never grandfathered"
            )
            continue
        grew = set(missing) - set(base[path])
        if grew:
            violations.append(
                f"RATCHET violated: {path} missing-set grew by {sorted(grew)} "
                f"(a gene once present may never be un-required)"
            )
    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Baseline one-way ratchet check")
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--repo", default=None)
    args = ap.parse_args(argv)

    repo_root = Path(args.repo).resolve() if args.repo else Path(
        subprocess.run(["git", "-C", str(HERE), "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True, check=False).stdout.strip() or "."
    ).resolve()

    base = load_grandfathered_at(args.base, repo_root)
    if base is None:
        # base ref has no genes.json yet (gate younger than ref) — vacuous pass
        # is only acceptable when the FILE is new, not when git itself failed
        probe = subprocess.run(["git", "-C", str(repo_root), "rev-parse", args.base],
                               capture_output=True, text=True, check=False)
        if probe.returncode != 0:
            print(f"✗ cannot resolve base ref {args.base}", file=sys.stderr)
            return 2
        print(f"✓ ratchet: no genes.json at {args.base} (gate is newborn) — vacuous pass")
        return 0

    try:
        current = json.loads((repo_root / GENES_REL).read_text(encoding="utf-8")).get(
            "grandfathered", {})
    except Exception as exc:  # noqa: BLE001
        print(f"✗ current genes.json unreadable: {exc}", file=sys.stderr)
        return 2

    violations = compare(base, current)
    if violations:
        for v in violations:
            print(f"✗ {v}")
        return 1

    shrunk = len(base) - len(current)
    print(f"✓ ratchet holds: {len(current)} grandfathered (was {len(base)}"
          f"{f', −{shrunk}' if shrunk > 0 else ''}), no growth")
    return 0


if __name__ == "__main__":
    sys.exit(main())
