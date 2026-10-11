#!/usr/bin/env python3
"""Version sentinel for the two CodeQL contexts: does the newest hosted CodeQL analysis of a language on main report the CLI the
matrix pins? Run by the localci runner at PLAN time on the host, from BASE, with the operator's gh (a read): hosted picks its CLI per
run by feature flag (2.27.1 -> 2.27.2 around 2026-10-09), and a local analysis on another CLI is not the hosted check.

    codeql_version_read.py --repo OWNER/NAME --language python|javascript --pin 2.27.2

Exit 0 = the newest analysis of that language on refs/heads/main reports the pin. Every other exit is "no verdict", never green:
3 = it reports another version (the line names both) · 4 = no analysis of that language in the newest page · 1 = the read itself failed
(its stderr line starts with the CANNOT-VERIFY marker, which the runner asks again on, then gives up) · 2 = bad arguments.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

CANNOT = "::error::codeql_version_read: CANNOT-VERIFY"
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
LANG_RE = re.compile(r"^[a-z][a-z-]*$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
PAGE = 100


def fail(marker: str, msg: str, rc: int) -> int:
    print(f"{marker} {msg}", file=sys.stderr)
    return rc


def newest(analyses: list, category: str) -> dict | None:
    """The newest analysis (by created_at) whose category is exactly `category`; None when the page holds none."""
    mine = [a for a in analyses if isinstance(a, dict) and a.get("category") == category and isinstance(a.get("created_at"), str)]
    return max(mine, key=lambda a: a["created_at"]) if mine else None


def main(argv: list[str] | None = None, run=subprocess.run) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", required=True)
    ap.add_argument("--language", required=True)
    ap.add_argument("--pin", required=True)
    args = ap.parse_args(argv)
    if not (REPO_RE.match(args.repo) and LANG_RE.match(args.language) and VERSION_RE.match(args.pin)):
        return fail("::error::codeql_version_read:", "repo, language or pin is not in its plain shape", 2)
    path = f"repos/{args.repo}/code-scanning/analyses?ref=refs/heads/main&per_page={PAGE}"
    try:
        res = run(["gh", "api", path], capture_output=True, text=True, timeout=120)
        if res.returncode != 0:
            return fail(CANNOT, f"(read failed) gh api rc={res.returncode}: {res.stderr.strip()[-200:]}", 1)
        doc = json.loads(res.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as e:
        return fail(CANNOT, f"(read failed) {type(e).__name__}", 1)
    if not isinstance(doc, list):
        return fail(CANNOT, "(read failed) the analyses answer is not a list", 1)
    category = f"/language:{args.language}"
    top = newest(doc, category)
    if top is None:
        return fail("::error::codeql_version_read: NO-ANALYSIS", f"none of the newest {PAGE} analyses on main has category {category}", 4)
    tool = top.get("tool") if isinstance(top.get("tool"), dict) else {}
    seen = tool.get("version")
    if seen != args.pin:
        return fail("::error::codeql_version_read: MISMATCH",
                    f"hosted CodeQL for {args.language} reports {seen!r} (analysis {top.get('id')}, {top['created_at']}); the matrix pins {args.pin!r}", 3)
    print(f"codeql_version_read: {args.language}: newest analysis {top.get('id')} ({top['created_at']}) reports {seen} == the pin")
    return 0


if __name__ == "__main__":
    sys.exit(main())
