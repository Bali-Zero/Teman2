#!/usr/bin/env python3
"""observe_visa_oracle_retirement_no_sponsor.py — bites: observation for R3.

# bites-observable — this script takes NO arguments: the program it runs and the
# test file it names are literal strings in this file, so nothing an invoker types
# can name a program to run, a file to write, or a database to reach (the bar
# `scripts/ci/bites_parse.py::_guard_observable_script` sets).

The consumer is the public Visa Oracle retirement interview. The retirement
branch no longer asks "who sponsors your stay" because no rule covering
RETIREMENT in the newest signed pack reads sponsor.type. The observation does two
independent things: (1) it runs ONLY the dedicated guard test file from
`apps/mouth` and requires exactly its tests to pass; (2) it repeats the pack scan
itself in Python, so a guard neutralised into a no-op still turns this red.
Exit 0 only if both hold.
"""

# bites-observable — no arguments; one literal program, one literal test file.

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MOUTH_DIR = REPO_ROOT / "apps" / "mouth"
TEST_FILE = "src/app/(visa-oracle)/visa-oracle/_lib/sponsor-retirement-guard.test.ts"
PACKS_DIR = (
    REPO_ROOT / "apps/backend-rag/backend/services/visa_engine/contracts/packs"
)
ANSI = re.compile(r"\x1b\[[0-9;]*m")

EXPECTED_TESTS = 4
_SUMMARY = re.compile(r"^\s*Tests\s+(\d+) passed \((\d+)\)\s*$")


def summary_ok(line: str | None) -> bool:
    """True only for a Vitest line that is exactly `Tests  4 passed (4)`.

    Anything else (skipped, todo, failed, another count, no line) is False.
    """
    if line is None:
        return False
    match = _SUMMARY.match(line)
    if match is None:
        return False
    passed, total = int(match.group(1)), int(match.group(2))
    return passed == total and passed == EXPECTED_TESTS


def _reads(node: object, fact: str) -> bool:
    if isinstance(node, str):
        return node == fact
    if isinstance(node, list):
        return any(_reads(item, fact) for item in node)
    if isinstance(node, dict):
        return any(_reads(item, fact) for item in node.values())
    return False


def pack_scan_offenders(packs_dir: Path = PACKS_DIR) -> list[str] | None:
    """Rule ids covering RETIREMENT that read sponsor.type in the newest signed pack.

    Returns None when the scan is not trustworthy (no pack, malformed payload,
    sequence != filename N, E33E/E33F missing or not RETIREMENT, no sponsor rule
    at all): the caller treats None as a failure, never as clean.
    """
    found = {}
    for path in packs_dir.glob("rulepack-prod-*.signed.json"):
        m = re.fullmatch(r"rulepack-prod-(\d+)\.signed\.json", path.name)
        if m:
            found[int(m.group(1))] = path
    if not found:
        return None
    newest = max(found)
    try:
        payload = json.loads(found[newest].read_text(encoding="utf-8"))["payload"]
        if payload["sequence"] != newest:
            return None
        products = payload["products"]
        rules = payload["rules"]
    except (KeyError, TypeError, ValueError):
        return None
    versions = set()
    for code in ("E33E", "E33F"):
        match = [p for p in products if p.get("product_code") == code]
        if len(match) != 1 or "RETIREMENT" not in match[0].get("covered_purposes", []):
            return None
    for product in products:
        if "RETIREMENT" in product.get("covered_purposes", []):
            versions.add(product["product_version_id"])
    sponsor_rules = [r for r in rules if _reads(r, "sponsor.type")]
    if not sponsor_rules:
        return None
    return [
        r["rule_id"]
        for r in sponsor_rules
        if r.get("scope") != "PRODUCTS"
        or versions & set(r.get("product_version_ids", []))
    ]


def main() -> int:
    offenders = pack_scan_offenders()
    if offenders is None or offenders:
        print(
            "observe_visa_oracle_retirement_no_sponsor: FAILED (pack scan: "
            f"{'untrustworthy' if offenders is None else offenders})"
        )
        return 1
    result = subprocess.run(
        ["npx", "vitest", "run", TEST_FILE],
        cwd=MOUTH_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    out = ANSI.sub("", result.stdout + result.stderr)
    tests = re.search(r"^\s*Tests\s.*$", out, re.MULTILINE)
    line = tests.group(0) if tests else None
    summary = line.strip() if line else "no Vitest summary"
    if result.returncode != 0 or not summary_ok(line):
        print(
            f"observe_visa_oracle_retirement_no_sponsor: FAILED ({summary})\n{out[-1500:]}"
        )
        return result.returncode or 1
    print(f"observe_visa_oracle_retirement_no_sponsor: {summary}")
    print("observe_visa_oracle_retirement_no_sponsor: retirement never asks sponsor")
    return 0


if __name__ == "__main__":
    sys.exit(main())
