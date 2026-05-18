#!/usr/bin/env python3
"""WR3 Lint Runner — execute all 6 enforcers and aggregate findings.

Usage:
  python scripts/lint/wr3_lint_runner.py [--repo-root PATH] [--fail-on WARN|ERROR]

CI integration (GitHub Actions):
  on PR touching scripts/wr3_*.py | docs/wr3/** | ~/.claude/agents/wr3-*.md
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def _load_linters() -> list:
    """Return list of (name, module) for every wr3_lint_*.py in this dir."""
    out = []
    for path in sorted(HERE.glob("wr3_lint_*.py")):
        if path.name == "wr3_lint_runner.py":
            continue
        module_name = path.stem
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out.append((module_name, mod))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="WR3 Symbiosis lint runner")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument(
        "--fail-on",
        choices=("WARN", "ERROR"),
        default="ERROR",
        help="Exit non-zero on findings of this severity or worse (default: ERROR)",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    print(f"[wr3-lint] repo_root = {repo_root}")

    linters = _load_linters()
    print(f"[wr3-lint] loaded {len(linters)} enforcers")

    all_findings = []
    summary: list[tuple[str, int, int, int]] = []  # (name, n_error, n_warn, n_info)

    for name, mod in linters:
        if not hasattr(mod, "check"):
            print(f"[wr3-lint] {name}: SKIPPED (no check() exported)", file=sys.stderr)
            continue
        findings = mod.check(repo_root)
        n_err = sum(1 for f in findings if f.severity == "ERROR")
        n_warn = sum(1 for f in findings if f.severity == "WARN")
        n_info = sum(1 for f in findings if f.severity == "INFO")
        law_name = getattr(mod, "LAW_NAME", "?")
        law_no = getattr(mod, "LAW_NUMBER", 0)
        print(f"\n[wr3-lint] {name} (Law {law_no} {law_name}): {n_err} ERROR, {n_warn} WARN, {n_info} INFO")
        for f in findings:
            print(f"  {f.fmt()}")
        all_findings.extend(findings)
        summary.append((name, n_err, n_warn, n_info))

    print("\n" + "=" * 72)
    total_err = sum(s[1] for s in summary)
    total_warn = sum(s[2] for s in summary)
    print(f"[wr3-lint] TOTAL: {total_err} ERROR, {total_warn} WARN across {len(summary)} enforcers")

    if args.fail_on == "ERROR":
        return 1 if total_err > 0 else 0
    elif args.fail_on == "WARN":
        return 1 if (total_err + total_warn) > 0 else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
