#!/usr/bin/env python3
"""Observe that the visa price ledger places every public visa row exactly once.

# bites-observable: the ledger spec (apps/mouth/src/data/visa-price-ledger.ts)
# must name every exact row of the five public visa categories of the mouth
# mirror exactly once, and nothing the mirror does not carry.

Python-side twin of apps/mouth/src/data/visa-price-ledger.test.ts: CI's harness
job has no node_modules, so the placement is read straight from the two files.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MIRROR = REPO / "apps/mouth/data/bali-zero-prices.json"
SPEC = REPO / "apps/mouth/src/data/visa-price-ledger.ts"
CATEGORIES = (
    "single_entry_visas",
    "multiple_entry_visas",
    "kitas_permits",
    "kitap_permits",
    "other_process",
)
EXACT_IDR = re.compile(r"^(?:\d+|\d{1,3}(?:\.\d{3})+)\s+IDR$", re.I)


def _fail(message: str) -> None:
    print(f"observe_visa_price_ledger: FAIL - {message}")
    sys.exit(1)


def main() -> None:
    mirror = json.loads(MIRROR.read_text(encoding="utf-8"))["services_by_category"]
    keys: list[str] = []
    for category in CATEGORIES:
        for key, row in mirror.get(category, {}).items():
            price = (row.get("price") or "").strip()
            if EXACT_IDR.match(price):
                keys.append(key)
    source = SPEC.read_text(encoding="utf-8")
    spec = source.split("export const VISA_LEDGER_SPEC", 1)[1].split(
        "export const UNPLACED_CHAPTER_ID", 1
    )[0]
    # Only cell / key positions count: a row name may legitimately equal a key.
    spec = "\n".join(
        line
        for line in spec.splitlines()
        if not re.match(r"^\s*(?:id|numeral|title|lede|name|label):", line)
    )
    spec = re.sub(r'name: "[^"\n]*"', "", spec)
    misplaced = {key: spec.count(json.dumps(key)) for key in keys}
    misplaced = {key: n for key, n in misplaced.items() if n != 1}
    if misplaced:
        _fail(f"rows not placed exactly once in the ledger spec: {misplaced}")
    quoted = set(re.findall(r'"([^"\n]+)"', spec))
    dangling = sorted(
        q
        for q in quoted
        if q not in keys
        and re.search(r"\((?:\d|Offshore|Altus|Extend|Under|Up|VOA|Exit)", q)
    )
    if dangling:
        _fail(f"ledger spec names catalogue-shaped keys the mirror lacks: {dangling}")
    print(
        f"observe_visa_price_ledger: {len(keys)} public visa rows placed exactly once"
    )


if __name__ == "__main__":
    main()
