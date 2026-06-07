#!/usr/bin/env python3
"""brand_token_lint.py — P8 FASE-5 gate G2 (token-compliance, binary).

A generated module/tool that hardcodes a color literal (`#hex`, `rgb()`,
`rgba()`, `hsl()`, `hsla()`) instead of a brand token FAILS this lint. Only
brand tokens (CSS custom properties `var(--bz-…)` or the named token scale)
are allowed in generated UI.

This is deliberately scoped to the *generated* surface — the agent-authored
modules and the brand-api artifact dir — NOT the whole repo (the existing
12+ source components and third-party code are out of scope; they predate the
gate and are reviewed by humans). The gate exists to stop the *generator* from
emitting raw color literals, which is the falsifiable G2 promise.

Scope (relative to repo root), all optional — missing dirs are simply skipped:
    packages/design-system/brand-api/**     (the build-artifact surface)
    apps/admin-dashboard/app/tools/**       (where generated modules will live)
    apps/admin-dashboard/src/tools/**

You can extend the scope with --path <dir> (repeatable). Files are matched by
extension: .ts .tsx .css .scss .json (json scanned as text).

Exit codes:
    0 — clean (no hardcoded color literals in scope)
    1 — violations found (printed file:line:match)
    2 — usage/internal error

Standard library only. No network, no PII.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve()
REPO_ROOT = _SCRIPT.parent.parent

DEFAULT_SCOPE = [
    "packages/design-system/brand-api",
    "apps/admin-dashboard/app/tools",
    "apps/admin-dashboard/src/tools",
]

SCAN_EXT = {".ts", ".tsx", ".css", ".scss", ".json", ".md"}

# Color literals we forbid in generated UI. Hex must be a real color length
# (3/4/6/8 hex digits) to avoid matching e.g. git shas in comments by accident
# — but to stay strict we anchor on `#` followed by exactly those lengths at a
# word boundary.
_HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b")
_FUNC = re.compile(r"\b(?:rgba?|hsla?)\s*\(", re.IGNORECASE)

# Lines explicitly allowing a literal (escape hatch, audited).
_ALLOW = re.compile(r"brand-token-lint:\s*allow", re.IGNORECASE)


def _iter_files(scope_dirs: list[Path]) -> list[Path]:
    out: list[Path] = []
    for d in scope_dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if p.is_file() and p.suffix in SCAN_EXT:
                out.append(p)
    return out


def scan(scope_dirs: list[Path]) -> list[tuple[Path, int, str]]:
    violations: list[tuple[Path, int, str]] = []
    for path in _iter_files(scope_dirs):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _ALLOW.search(line):
                continue
            hit = _HEX.search(line) or _FUNC.search(line)
            if hit:
                violations.append((path, lineno, hit.group(0)))
    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Lint generated UI for hardcoded colors.")
    ap.add_argument(
        "--path",
        action="append",
        default=[],
        help="extra scope dir (repo-relative or absolute); repeatable",
    )
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="run an internal positive/negative assertion and exit",
    )
    args = ap.parse_args(argv)

    if args.self_test:
        return _self_test()

    scope = [REPO_ROOT / p for p in DEFAULT_SCOPE]
    for extra in args.path:
        ep = Path(extra)
        scope.append(ep if ep.is_absolute() else (REPO_ROOT / ep))

    violations = scan(scope)
    if violations:
        print(
            "brand-token-lint: FAIL — hardcoded color literals found:", file=sys.stderr
        )
        for path, lineno, match in violations:
            rel = path.relative_to(REPO_ROOT) if REPO_ROOT in path.parents else path
            print(f"  {rel}:{lineno}: {match}", file=sys.stderr)
        print(
            "\nUse brand tokens (var(--bz-…)) instead, or add "
            "`/* brand-token-lint: allow */` with justification.",
            file=sys.stderr,
        )
        return 1
    print("brand-token-lint: OK — no hardcoded color literals in scope")
    return 0


def _self_test() -> int:
    """Falsifiable self-check: the regexes must catch the bad and pass the good."""
    bad = [
        "#fff",
        "#FFFFFF",
        "#12ab34cd",
        "rgb(0,0,0)",
        "rgba(1,2,3,.5)",
        "hsl(1,2%,3%)",
    ]
    good = [
        "var(--bz-color-bg)",
        "color: token('accent')",
        "https://x/abcdef0",
        "#nothex",
    ]
    ok = True
    for s in bad:
        if not (_HEX.search(s) or _FUNC.search(s)):
            print(f"SELF-TEST FAIL: did not catch bad literal {s!r}", file=sys.stderr)
            ok = False
    for s in good:
        if _HEX.search(s) or _FUNC.search(s):
            print(f"SELF-TEST FAIL: false-positive on {s!r}", file=sys.stderr)
            ok = False
    if ok:
        print("brand-token-lint self-test: OK")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
