#!/usr/bin/env python3
"""Inventory phantom (KBLI-2020-vintage) codes referenced inside
apps/mouth/data/kbli-gold-all.json's `youllAlsoNeed` field.

A "phantom" code is a 5-digit reference inside `youllAlsoNeed` that does not
exist in the canonical KBLI-2025 catalogue (data/source_documents/
KBLI_2025_FINAL_CLEAN.json, 1,559 codes, v10.0-L2-oss-risk).

Zero-LLM, deterministic. Prints fresh counts + a per-code / per-entry
breakdown so downstream remap work has ground truth, not memory.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLD_PATH = ROOT / "apps/mouth/data/kbli-gold-all.json"
DATASET_PATH = ROOT / "data/source_documents/KBLI_2025_FINAL_CLEAN.json"

CODE_RE = re.compile(r"\b(\d{5})\b")


def main() -> None:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    valid_codes = {r["kode_kbli_2025"] for r in dataset["data"]}
    print(f"Canonical 2025 catalogue: {len(valid_codes)} codes")

    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    print(f"Gold entries: {len(gold)}")

    phantom_refs: dict[str, list[str]] = defaultdict(list)  # phantom_code -> [entry codes]
    entries_with_phantom: set[str] = set()
    entries_missing_field = 0
    total_refs = 0
    valid_refs = 0

    for entry_code, entry in gold.items():
        text = entry.get("youllAlsoNeed") or ""
        if not text.strip():
            entries_missing_field += 1
            continue
        refs = CODE_RE.findall(text)
        for ref in refs:
            total_refs += 1
            if ref in valid_codes:
                valid_refs += 1
                continue
            phantom_refs[ref].append(entry_code)
            entries_with_phantom.add(entry_code)

    n_phantom_codes = len(phantom_refs)
    n_phantom_refs = sum(len(v) for v in phantom_refs.values())

    print(f"Entries missing/empty youllAlsoNeed: {entries_missing_field}")
    print(f"Total 5-digit refs found: {total_refs} (valid={valid_refs}, phantom={n_phantom_refs})")
    print(f"Unique phantom codes: {n_phantom_codes}")
    print(f"Gold entries containing >=1 phantom ref: {len(entries_with_phantom)}")
    print()
    print("=== Phantom code -> citing entries (count) ===")
    for code, citers in sorted(phantom_refs.items(), key=lambda kv: -len(kv[1])):
        print(f"{code}\t{len(citers)}\t{','.join(sorted(set(citers)))}")

    out = {
        "canonical_count": len(valid_codes),
        "gold_entry_count": len(gold),
        "phantom_code_count": n_phantom_codes,
        "phantom_ref_count": n_phantom_refs,
        "entries_with_phantom_count": len(entries_with_phantom),
        "phantom_refs": {code: sorted(set(citers)) for code, citers in phantom_refs.items()},
    }
    out_path = ROOT / "scripts/_kbli_gold_phantom_inventory.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
