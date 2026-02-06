#!/usr/bin/env python3
"""
FASE 1: Fix pp28_sources mapping for KBLI 2025

This script correctly maps KBLI 2025 codes to their PP28 sources (KBLI 2020 codes).

Logic:
1. Load PP28 codes from gap analysis (these are KBLI 2020 codes used in PP28)
2. Load KBLI 2020 official data (to get titles for matching)
3. Load KBLI 2025 data
4. For codes with wrong pp28_sources:
   - Find matching KBLI 2020 code in PP28 by title similarity
   - Update pp28_sources to correct KBLI 2020 code
   - Mark as CODICE_RINUMERATO

Author: Zantara AI
Date: 2026-02-04
"""

import json
import shutil
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
KBLI_2020_PATH = BASE_DIR / "source_documents" / "kbli_2020_official.json"
KBLI_2025_PATH = BASE_DIR / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
GAP_PATH = BASE_DIR / "reports" / "kbli_pp28_vs_bps2025_gap.json"
REPORT_PATH = (
    BASE_DIR
    / "reports"
    / f"kbli_mapping_phase1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)

# Thresholds
HIGH_CONFIDENCE = 0.85
MEDIUM_CONFIDENCE = 0.70
AUTO_FIX_THRESHOLD = 0.75  # More conservative


def load_json(path: Path) -> dict | list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def similarity(s1: str, s2: str) -> float:
    """Calculate string similarity."""
    return SequenceMatcher(None, s1.upper().strip(), s2.upper().strip()).ratio()


def normalize_title(title: str) -> str:
    """Normalize title for better matching."""
    # Remove common prefixes/suffixes that differ between versions
    title = title.upper().strip()
    for prefix in ["AKTIVITAS ", "INDUSTRI ", "JASA ", "PERDAGANGAN "]:
        if title.startswith(prefix):
            title = title[len(prefix) :]
    return title


def find_best_pp28_match(
    code_2025: str, title_2025: str, pp28_codes: set, kbli_2020_dict: dict
) -> tuple | None:
    """
    Find the best matching PP28 code for a KBLI 2025 code.

    Returns: (pp28_code, pp28_title, score) or None
    """
    best_match = None
    best_score = 0

    # Normalize the 2025 title
    norm_2025 = normalize_title(title_2025)

    # Only search within PP28 codes (KBLI 2020 codes that are in PP28)
    for pp28_code in pp28_codes:
        if pp28_code not in kbli_2020_dict:
            continue

        pp28_title = kbli_2020_dict[pp28_code]
        norm_pp28 = normalize_title(pp28_title)

        # Calculate similarity on both original and normalized titles
        score1 = similarity(title_2025, pp28_title)
        score2 = similarity(norm_2025, norm_pp28)
        score = max(score1, score2)

        # Bonus if first 2-3 digits match (same sector)
        if code_2025[:2] == pp28_code[:2]:
            score += 0.05
        if code_2025[:3] == pp28_code[:3]:
            score += 0.05

        if score > best_score:
            best_score = min(score, 1.0)  # Cap at 1.0
            best_match = (pp28_code, pp28_title, best_score)

    return best_match if best_match and best_match[2] >= MEDIUM_CONFIDENCE else None


def main():
    print("=" * 70)
    print("FASE 1: Fix pp28_sources mapping")
    print("=" * 70)

    # Step 1: Load data
    print("\n[1/6] Loading data...")

    kbli_2020 = load_json(KBLI_2020_PATH)
    kbli_2020_dict = {str(item["code"]): item["title"] for item in kbli_2020}
    print(f"      KBLI 2020: {len(kbli_2020_dict)} codes")

    gap_data = load_json(GAP_PATH)
    pp28_codes = set(gap_data.get("missing_codes", []))
    print(f"      PP28 codes (KBLI 2020 in PP28 but not in BPS2025): {len(pp28_codes)}")

    kbli_2025_raw = load_json(KBLI_2025_PATH)
    if isinstance(kbli_2025_raw, dict) and "data" in kbli_2025_raw:
        kbli_2025_data = kbli_2025_raw["data"]
        is_wrapped = True
    else:
        kbli_2025_data = kbli_2025_raw
        is_wrapped = False
    print(f"      KBLI 2025: {len(kbli_2025_data)} codes")

    # Step 2: Identify codes needing fix
    print("\n[2/6] Identifying codes with wrong pp28_sources...")

    needs_fix = []
    already_correct = []
    bps_only = []
    aggregated = []

    for item in kbli_2025_data:
        code = item.get("kode_kbli_2025", "")
        status = item.get("status_mapping", "")
        pp28_src = item.get("pp28_sources", [])

        if status == "BPS_ONLY":
            bps_only.append(code)
            continue

        if "AGGREGAZIONE" in status:
            aggregated.append(code)
            continue

        # Check if pp28_sources points to itself
        if pp28_src == [code]:
            # Check if this code exists in PP28 (as KBLI 2020)
            if code in pp28_codes or code in kbli_2020_dict:
                # Code exists in PP28 with same number - it's correct
                already_correct.append(code)
            else:
                # Code doesn't exist in PP28 - needs remapping
                needs_fix.append(item)
        else:
            # pp28_sources points to different code(s) - assume correct
            already_correct.append(code)

    print(f"      Already correct: {len(already_correct)}")
    print(f"      Aggregated (skip): {len(aggregated)}")
    print(f"      BPS_ONLY (skip): {len(bps_only)}")
    print(f"      Needs fix: {len(needs_fix)}")

    # Step 3: Find matches
    print("\n[3/6] Finding PP28 matches for codes needing fix...")

    fixes = []
    no_match = []

    for item in needs_fix:
        code = item["kode_kbli_2025"]
        title = item["judul"]

        match = find_best_pp28_match(code, title, pp28_codes, kbli_2020_dict)

        if match:
            pp28_code, pp28_title, score = match
            fixes.append(
                {
                    "code_2025": code,
                    "title_2025": title,
                    "pp28_code": pp28_code,
                    "pp28_title": pp28_title,
                    "score": score,
                    "auto_fix": score >= AUTO_FIX_THRESHOLD,
                }
            )
        else:
            no_match.append({"code_2025": code, "title_2025": title})

    auto_fixes = [f for f in fixes if f["auto_fix"]]
    manual_review = [f for f in fixes if not f["auto_fix"]]

    print(f"      Auto-fix (≥{AUTO_FIX_THRESHOLD:.0%}): {len(auto_fixes)}")
    print(
        f"      Manual review ({MEDIUM_CONFIDENCE:.0%}-{AUTO_FIX_THRESHOLD:.0%}): {len(manual_review)}"
    )
    print(f"      No match found: {len(no_match)}")

    # Step 4: Create backup
    print("\n[4/6] Creating backup...")
    backup_path = KBLI_2025_PATH.with_suffix(
        f".backup_phase1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    shutil.copy(KBLI_2025_PATH, backup_path)
    print(f"      Backup: {backup_path.name}")

    # Step 5: Apply auto-fixes
    print("\n[5/6] Applying auto-fixes...")

    applied = []
    for item in kbli_2025_data:
        code = item.get("kode_kbli_2025", "")

        # Find if this code should be auto-fixed
        fix = next((f for f in auto_fixes if f["code_2025"] == code), None)

        if fix:
            old_pp28 = item.get("pp28_sources", [])
            old_status = item.get("status_mapping", "")

            # Apply fix
            item["pp28_sources"] = [fix["pp28_code"]]
            item["status_mapping"] = "CODICE_RINUMERATO"
            item["kbli_2020_source"] = fix["pp28_code"]
            item["mapping_note"] = (
                f"PP28 usa codice KBLI 2020 {fix['pp28_code']} ({fix['pp28_title'][:30]}...). Match: {fix['score']:.0%}"
            )

            applied.append(
                {
                    "code_2025": code,
                    "old_pp28_sources": old_pp28,
                    "new_pp28_sources": [fix["pp28_code"]],
                    "old_status": old_status,
                    "new_status": "CODICE_RINUMERATO",
                    "pp28_title": fix["pp28_title"],
                    "score": fix["score"],
                }
            )

    print(f"      Applied: {len(applied)} fixes")

    # Step 6: Save
    print("\n[6/6] Saving...")

    if is_wrapped:
        kbli_2025_raw["data"] = kbli_2025_data
        save_json(kbli_2025_raw, KBLI_2025_PATH)
    else:
        save_json(kbli_2025_data, KBLI_2025_PATH)
    print(f"      Updated: {KBLI_2025_PATH.name}")

    # Generate report
    report = {
        "timestamp": datetime.now().isoformat(),
        "phase": "FASE 1 - Fix pp28_sources mapping",
        "thresholds": {
            "auto_fix": AUTO_FIX_THRESHOLD,
            "medium_confidence": MEDIUM_CONFIDENCE,
            "high_confidence": HIGH_CONFIDENCE,
        },
        "summary": {
            "total_kbli_2025": len(kbli_2025_data),
            "already_correct": len(already_correct),
            "bps_only_skipped": len(bps_only),
            "aggregated_skipped": len(aggregated),
            "needed_fix": len(needs_fix),
            "auto_fixed": len(applied),
            "needs_manual_review": len(manual_review),
            "no_match_found": len(no_match),
        },
        "fixes_applied": applied,
        "needs_manual_review": manual_review,
        "no_match": no_match,
    }

    save_json(report, REPORT_PATH)
    print(f"      Report: {REPORT_PATH.name}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nTotal codes analyzed: {len(kbli_2025_data)}")
    print(f"✓ Auto-fixed: {len(applied)}")
    print(f"⚠ Needs manual review: {len(manual_review)}")
    print(f"? No match found: {len(no_match)}")

    if applied:
        print("\n--- Sample fixes applied ---")
        for fix in applied[:10]:
            print(
                f"  {fix['code_2025']}: {fix['old_pp28_sources']} → {fix['new_pp28_sources']} ({fix['score']:.0%})"
            )

    if manual_review:
        print("\n--- Codes needing manual review ---")
        for fix in manual_review[:10]:
            print(
                f"  {fix['code_2025']}: suggested {fix['pp28_code']} ({fix['score']:.0%})"
            )

    print(f"\n✓ Done! Report saved to: {REPORT_PATH}")

    return len(applied), len(manual_review), len(no_match)


if __name__ == "__main__":
    main()
