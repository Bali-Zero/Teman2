#!/usr/bin/env python3
"""
FASE 1B: Fix ALL invalid pp28_sources

This script:
1. Removes invalid KBLI codes from pp28_sources (codes that don't exist in KBLI 2020)
2. Fixes specific known mappings (e.g., Hotel Bintang 55101-55104 → 55110)
3. Handles MATCH_CON_AGGREGAZIONE codes with mixed valid/invalid sources

Author: Zantara AI
Date: 2026-02-04
"""

import json
import shutil
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
KBLI_2020_PATH = BASE_DIR / "source_documents" / "kbli_2020_official.json"
KBLI_2025_PATH = BASE_DIR / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
GAP_PATH = BASE_DIR / "reports" / "kbli_pp28_vs_bps2025_gap.json"
REPORT_PATH = (
    BASE_DIR
    / "reports"
    / f"kbli_mapping_phase1b_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)

# Known manual mappings for codes that can't be auto-matched
MANUAL_MAPPINGS = {
    # Hotel Bintang - all should map to 55110
    "55101": {"pp28": ["55110"], "note": "Hotel Bintang Lima → Hotel Bintang"},
    "55102": {"pp28": ["55110"], "note": "Hotel Bintang Empat → Hotel Bintang"},
    "55103": {"pp28": ["55110"], "note": "Hotel Bintang Tiga → Hotel Bintang"},
    "55104": {"pp28": ["55110"], "note": "Hotel Bintang Dua → Hotel Bintang"},
    # 55105 already correct from Phase 1
    "55106": {
        "pp28": ["55120", "55130"],
        "note": "Hotel Nonbintang → Hotel Melati + Pondok Wisata",
    },
    # Pertanian - manual mappings based on domain knowledge
    "01271": {
        "pp28": ["01270"],
        "note": "Pertanian Kopi - parte di 01270 Tanaman Bahan Minuman",
    },
    "01273": {
        "pp28": ["01270"],
        "note": "Pertanian Kakao - parte di 01270 Tanaman Bahan Minuman",
    },
}


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def similarity(s1, s2):
    return SequenceMatcher(None, s1.upper(), s2.upper()).ratio()


def find_best_match(title, pp28_codes, kbli_2020_dict, threshold=0.65):
    """Find best matching PP28 code by title similarity."""
    best = None
    best_score = 0

    for code in pp28_codes:
        if code not in kbli_2020_dict:
            continue
        pp28_title = kbli_2020_dict[code]
        score = similarity(title, pp28_title)
        if score > best_score and score >= threshold:
            best_score = score
            best = (code, pp28_title, score)

    return best


def main():
    print("=" * 70)
    print("FASE 1B: Fix ALL invalid pp28_sources")
    print("=" * 70)

    # Load data
    print("\n[1/5] Loading data...")

    kbli_2020 = load_json(KBLI_2020_PATH)
    kbli_2020_codes = set(str(item["code"]) for item in kbli_2020)
    kbli_2020_dict = {str(item["code"]): item["title"] for item in kbli_2020}
    print(f"      KBLI 2020: {len(kbli_2020_codes)} codes")

    gap_data = load_json(GAP_PATH)
    pp28_codes = set(gap_data.get("missing_codes", []))
    # PP28 also includes codes that exist in both PP28 and BPS2025
    all_pp28_codes = pp28_codes | kbli_2020_codes
    print(f"      PP28 codes available: {len(all_pp28_codes)}")

    kbli_2025_raw = load_json(KBLI_2025_PATH)
    if isinstance(kbli_2025_raw, dict) and "data" in kbli_2025_raw:
        items = kbli_2025_raw["data"]
        is_wrapped = True
    else:
        items = kbli_2025_raw
        is_wrapped = False
    print(f"      KBLI 2025: {len(items)} codes")

    # Analyze all codes
    print("\n[2/5] Analyzing pp28_sources...")

    fixes_needed = []
    already_ok = []
    bps_only = []

    for item in items:
        code = item["kode_kbli_2025"]
        status = item.get("status_mapping", "")
        pp28_src = item.get("pp28_sources", [])

        if status == "BPS_ONLY" or not pp28_src:
            bps_only.append(code)
            continue

        # Check validity of each source
        invalid = [s for s in pp28_src if s not in kbli_2020_codes]
        valid = [s for s in pp28_src if s in kbli_2020_codes]

        if invalid:
            fixes_needed.append(
                {
                    "code": code,
                    "judul": item["judul"],
                    "status": status,
                    "pp28_current": pp28_src,
                    "invalid": invalid,
                    "valid": valid,
                }
            )
        else:
            already_ok.append(code)

    print(f"      Already OK: {len(already_ok)}")
    print(f"      BPS_ONLY (skip): {len(bps_only)}")
    print(f"      Needs fix: {len(fixes_needed)}")

    # Create backup
    print("\n[3/5] Creating backup...")
    backup_path = KBLI_2025_PATH.with_suffix(
        f".backup_phase1b_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    shutil.copy(KBLI_2025_PATH, backup_path)
    print(f"      Backup: {backup_path.name}")

    # Apply fixes
    print("\n[4/5] Applying fixes...")

    fixed_manual = []
    fixed_auto_clean = []
    fixed_auto_match = []
    still_problematic = []

    for item in items:
        code = item["kode_kbli_2025"]

        # Find if needs fix
        fix_info = next((f for f in fixes_needed if f["code"] == code), None)
        if not fix_info:
            continue

        old_pp28 = item.get("pp28_sources", [])
        old_status = item.get("status_mapping", "")

        # Strategy 1: Manual mapping
        if code in MANUAL_MAPPINGS:
            mapping = MANUAL_MAPPINGS[code]
            item["pp28_sources"] = mapping["pp28"]
            item["status_mapping"] = "CODICE_RINUMERATO"
            item["kbli_2020_source"] = mapping["pp28"][0]
            item["mapping_note"] = f"Manual fix: {mapping['note']}"
            fixed_manual.append(
                {
                    "code": code,
                    "old": old_pp28,
                    "new": mapping["pp28"],
                    "method": "manual",
                }
            )
            continue

        # Strategy 2: Has valid sources - just remove invalid ones
        if fix_info["valid"]:
            item["pp28_sources"] = fix_info["valid"]
            if len(fix_info["valid"]) == 1:
                item["kbli_2020_source"] = fix_info["valid"][0]
            # Keep status as is (likely MATCH_CON_AGGREGAZIONE)
            item["mapping_note"] = f"Cleaned: removed invalid {fix_info['invalid']}"
            fixed_auto_clean.append(
                {
                    "code": code,
                    "old": old_pp28,
                    "new": fix_info["valid"],
                    "removed": fix_info["invalid"],
                    "method": "auto_clean",
                }
            )
            continue

        # Strategy 3: No valid sources - try to find match
        match = find_best_match(fix_info["judul"], pp28_codes, kbli_2020_dict)
        if match:
            pp28_code, pp28_title, score = match
            item["pp28_sources"] = [pp28_code]
            item["status_mapping"] = "CODICE_RINUMERATO"
            item["kbli_2020_source"] = pp28_code
            item["mapping_note"] = (
                f"Auto-matched to {pp28_code} ({pp28_title[:30]}...) score={score:.0%}"
            )
            fixed_auto_match.append(
                {
                    "code": code,
                    "old": old_pp28,
                    "new": [pp28_code],
                    "match_title": pp28_title,
                    "score": score,
                    "method": "auto_match",
                }
            )
            continue

        # Strategy 4: Can't fix - mark for review
        item["mapping_note"] = (
            f"NEEDS_REVIEW: invalid pp28_sources {fix_info['invalid']}, no match found"
        )
        item["needs_review"] = True
        still_problematic.append(
            {"code": code, "judul": fix_info["judul"], "invalid": fix_info["invalid"]}
        )

    total_fixed = len(fixed_manual) + len(fixed_auto_clean) + len(fixed_auto_match)
    print(f"      Fixed (manual mapping): {len(fixed_manual)}")
    print(f"      Fixed (auto clean): {len(fixed_auto_clean)}")
    print(f"      Fixed (auto match): {len(fixed_auto_match)}")
    print(f"      Still problematic: {len(still_problematic)}")
    print(f"      TOTAL FIXED: {total_fixed}")

    # Save
    print("\n[5/5] Saving...")

    if is_wrapped:
        kbli_2025_raw["data"] = items
        save_json(kbli_2025_raw, KBLI_2025_PATH)
    else:
        save_json(items, KBLI_2025_PATH)
    print(f"      Updated: {KBLI_2025_PATH.name}")

    # Report
    report = {
        "timestamp": datetime.now().isoformat(),
        "phase": "FASE 1B - Fix ALL invalid pp28_sources",
        "summary": {
            "total_analyzed": len(items),
            "already_ok": len(already_ok),
            "bps_only_skipped": len(bps_only),
            "needed_fix": len(fixes_needed),
            "fixed_manual": len(fixed_manual),
            "fixed_auto_clean": len(fixed_auto_clean),
            "fixed_auto_match": len(fixed_auto_match),
            "total_fixed": total_fixed,
            "still_problematic": len(still_problematic),
        },
        "fixes": {
            "manual": fixed_manual,
            "auto_clean": fixed_auto_clean,
            "auto_match": fixed_auto_match,
        },
        "still_problematic": still_problematic,
    }

    save_json(report, REPORT_PATH)
    print(f"      Report: {REPORT_PATH.name}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\n✓ Fixed (manual): {len(fixed_manual)}")
    for f in fixed_manual[:10]:
        print(f"    {f['code']}: {f['old']} → {f['new']}")

    print(f"\n✓ Fixed (auto clean): {len(fixed_auto_clean)}")
    for f in fixed_auto_clean[:5]:
        print(f"    {f['code']}: removed {f['removed']}, kept {f['new']}")

    print(f"\n✓ Fixed (auto match): {len(fixed_auto_match)}")
    for f in fixed_auto_match[:5]:
        print(f"    {f['code']}: → {f['new']} ({f['score']:.0%})")

    if still_problematic:
        print(f"\n⚠ Still problematic: {len(still_problematic)}")
        for p in still_problematic[:10]:
            print(f"    {p['code']}: {p['judul'][:40]}")

    print("\n✓ Done!")


if __name__ == "__main__":
    main()
