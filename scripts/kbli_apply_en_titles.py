#!/usr/bin/env python3
"""Apply W3 English titles to apps/mouth/src/lib/kbli-english-generated.ts (2026-07-07).

Input: JSON file [{"code": "01116", "title": "Mixed Bean Farming"}, ...] from the
W3 wave (verifier-rejected codes excluded via --exclude).

Gates (refuse, never silently fix):
  - code exists in the dataset and is NOT already in the curated map
  - title 2..9 words, non-empty, has latin letters, not byte-equal to the judul
  - no duplicate title across DIFFERENT judul (collision report; colliding codes
    are refused so the wave can requalify them)

Writes the full sorted map; idempotent for identical input.
Usage: python3 scripts/kbli_apply_en_titles.py --titles FILE [--exclude 01111,...]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
CURATED = ROOT / "apps/mouth/src/lib/kbli-english.ts"
TARGET = ROOT / "apps/mouth/src/lib/kbli-english-generated.ts"

HEADER = '''// =============================================================================
// KBLI 2025 English Titles — GENERATED tier (full-catalogue coverage)
//
// Produced by the KBLI perfection factory (W3 wave, 2026-07-07): Sonnet batch
// translation of the official judul, style-anchored on the curated map in
// kbli-english.ts, then adversarially verified batch-by-batch and re-linted
// deterministically (scripts/kbli_dataset_lint.py L2).
//
// PRECEDENCE: kbli-english.ts (curated) ALWAYS wins over this map — see
// kbli-data.ts. Edit curated titles there; regenerate this file via
// scripts/kbli_apply_en_titles.py, never by hand.
//
// SEO NOTE (firebreak PR #1967): these titles feed the page BODY (h1, cards,
// FAQ). <title>/meta keep using the curated-legacy map until the GSC crawl
// window recovers and Zero flips NEXT_PUBLIC_KBLI_META_EN=1.
// =============================================================================

export const ENGLISH_TITLES_GENERATED: Record<string, string> = {
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--titles", required=True)
    ap.add_argument("--exclude", default="")
    args = ap.parse_args()
    excluded = {c.strip() for c in args.exclude.split(",") if c.strip()}

    data = json.loads(DATASET.read_text(encoding="utf-8"))["data"]
    recs = {r["kode_kbli_2025"]: r for r in data}
    curated = set(re.findall(r'^\s*"(\d{5})":', CURATED.read_text(encoding="utf-8"), re.M))

    items = json.loads(Path(args.titles).read_text(encoding="utf-8"))
    ok: dict[str, str] = {}
    refused: list[tuple[str, str]] = []

    for it in items:
        code, title = str(it.get("code", "")), str(it.get("title", "")).strip()
        if code in excluded:
            refused.append((code, "verifier-rejected"))
            continue
        rec = recs.get(code)
        if rec is None:
            refused.append((code, "unknown code"))
            continue
        if code in curated:
            refused.append((code, "already curated"))
            continue
        words = title.split()
        if not (2 <= len(words) <= 9):
            refused.append((code, f"word count {len(words)}: {title[:50]}"))
            continue
        if not re.search(r"[A-Za-z]", title) or '"' in title:
            refused.append((code, f"bad chars: {title[:50]}"))
            continue
        if title.lower() == rec["judul"].strip().lower():
            refused.append((code, "identical to judul"))
            continue
        if code in ok:
            refused.append((code, "duplicate code in input"))
            continue
        ok[code] = title

    # collision gate: same title on different judul
    by_title: dict[str, list[str]] = defaultdict(list)
    for c, t in ok.items():
        by_title[t.lower()].append(c)
    for t, cs in sorted(by_title.items()):
        if len(cs) > 1:
            juduls = {recs[c]["judul"].strip().lower() for c in cs}
            if len(juduls) > 1:
                for c in cs:
                    refused.append((c, f"title collision: '{t}' x{len(cs)}"))
                    ok.pop(c, None)

    lines = [f'  "{c}": "{ok[c]}",' for c in sorted(ok)]
    TARGET.write_text(HEADER + "\n".join(lines) + "\n};\n", encoding="utf-8")
    print(f"written: {len(ok)} titles | refused: {len(refused)}")
    for c, why in refused[:40]:
        print(f"  REFUSED {c}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
