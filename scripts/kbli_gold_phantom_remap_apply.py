#!/usr/bin/env python3
"""Apply HIGH-confidence phantom-code remaps to apps/mouth/data/kbli-gold-all.json's
`youllAlsoNeed` field.

Reads scripts/_kbli_gold_remap_table.json (built by hand from the multi-source research:
existing KBLI_2017_TO_2025_MAPPING.json crosswalk + agy/Gemini web-search research +
chat_kbli semantic cross-check), of the shape:

{
  "47719": {"successor": "47901", "confidence": "high", "mapping_type": "DIRECT",
            "source": "..."},
  "68200": {"successor": null, "confidence": "unmapped", ...},
  ...
}

Only entries with confidence == "high" AND a non-null successor are applied. Everything
else is left untouched in the dataset and reported.

Replacement rule: within each `youllAlsoNeed` bullet line "- **CODE**[ — desc]", if CODE is
a phantom with a high-confidence successor, the CODE token is replaced in place with the
successor code. If the successor would collide with a code already present in the SAME
entry's youllAlsoNeed (either an original valid code or another remapped one), the
duplicate bullet line is dropped (never emit two bullets pointing at the same code).

Idempotent / dry-run by default; --write commits changes to disk.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLD_PATH = ROOT / "apps/mouth/data/kbli-gold-all.json"
TABLE_PATH = ROOT / "scripts/_kbli_gold_remap_table.json"

BULLET_CODE_RE = re.compile(r"^(-\s+\*{0,2})(\d{5})(\*{0,2}.*)$")


def apply_remap(text: str, remap: dict[str, object]) -> tuple[str, int, int]:
    """Returns (new_text, n_replaced, n_dropped_duplicate).

    `remap` values are either a single successor code (str) or a list of codes
    (SPLIT-expand: one phantom bullet becomes N bullets, one per successor).
    """
    lines = text.split("\n")
    seen_codes: set[str] = set()
    # First pass: collect all codes already in the text (valid, non-bulleted refs too)
    for line in lines:
        for m in re.finditer(r"\b(\d{5})\b", line):
            seen_codes.add(m.group(1))

    out_lines = []
    n_replaced = 0
    n_dropped = 0
    for line in lines:
        stripped = line.strip()
        bm = BULLET_CODE_RE.match(stripped)
        if bm:
            prefix, code, suffix = bm.groups()
            if code in remap:
                successors = remap[code]
                if isinstance(successors, str):
                    successors = [successors]
                new_bullets = []
                for successor in successors:
                    if successor in seen_codes and successor != code:
                        n_dropped += 1
                        continue
                    new_bullets.append(line.replace(code, successor, 1))
                    seen_codes.add(successor)
                seen_codes.discard(code)
                if new_bullets:
                    out_lines.extend(new_bullets)
                    n_replaced += 1
                continue
        out_lines.append(line)
    return "\n".join(out_lines), n_replaced, n_dropped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="commit changes to kbli-gold-all.json")
    args = ap.parse_args()

    table = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
    remap = {
        code: v["successor"]
        for code, v in table.items()
        if v.get("apply") and v.get("successor")
    }
    print(f"High-confidence remaps to apply: {len(remap)} / {len(table)} total phantom codes")

    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    total_replaced = 0
    total_dropped = 0
    entries_touched = 0

    for entry_code, entry in gold.items():
        text = entry.get("youllAlsoNeed") or ""
        if not text.strip():
            continue
        new_text, n_rep, n_drop = apply_remap(text, remap)
        if n_rep or n_drop:
            entries_touched += 1
            total_replaced += n_rep
            total_dropped += n_drop
            entry["youllAlsoNeed"] = new_text

    print(f"Entries touched: {entries_touched}")
    print(f"Bullet lines remapped: {total_replaced}")
    print(f"Bullet lines dropped (would-be duplicate): {total_dropped}")

    if args.write:
        GOLD_PATH.write_text(
            json.dumps(gold, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"WROTE {GOLD_PATH}")
    else:
        print("DRY RUN — pass --write to commit")


if __name__ == "__main__":
    main()
