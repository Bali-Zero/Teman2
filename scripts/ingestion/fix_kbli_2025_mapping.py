#!/usr/bin/env python3
"""
Fix KBLI 2025 pp28_sources mapping for renumbered codes.

This script:
1. Identifies KBLI 2025 codes with pp28_sources that don't exist in KBLI 2020
2. Finds the correct KBLI 2020 code by title similarity
3. Updates the mapping with correct pp28_sources and status

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
REPORT_PATH = (
    BASE_DIR
    / "reports"
    / f"kbli_mapping_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)

# Thresholds
HIGH_CONFIDENCE_THRESHOLD = 0.80
MEDIUM_CONFIDENCE_THRESHOLD = 0.60
AUTO_FIX_THRESHOLD = 0.80  # Only auto-fix above this threshold


def load_json(path: Path) -> list | dict:
    """Load JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: list | dict, path: Path):
    """Save JSON file with proper formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def calculate_similarity(str1: str, str2: str) -> float:
    """Calculate string similarity ratio."""
    return SequenceMatcher(None, str1.upper(), str2.upper()).ratio()


def find_best_match(
    title_2025: str, kbli_2020_dict: dict
) -> tuple[str, str, float] | None:
    """Find best matching KBLI 2020 code by title similarity."""
    best_match = None
    best_score = 0

    for code_2020, title_2020 in kbli_2020_dict.items():
        score = calculate_similarity(title_2025, title_2020)
        if score > best_score and score >= MEDIUM_CONFIDENCE_THRESHOLD:
            best_score = score
            best_match = (code_2020, title_2020, score)

    return best_match


def main():
    print("=" * 60)
    print("KBLI 2025 Mapping Fix Script")
    print("=" * 60)

    # Load data
    print("\n[1/5] Loading KBLI data...")
    kbli_2020 = load_json(KBLI_2020_PATH)
    kbli_2025 = load_json(KBLI_2025_PATH)

    # Build KBLI 2020 lookup
    kbli_2020_codes = {
        str(item.get("code", "")): item.get("title", "") for item in kbli_2020
    }
    print(f"      KBLI 2020: {len(kbli_2020_codes)} codes")

    # Handle KBLI 2025 structure
    items_2025 = kbli_2025 if isinstance(kbli_2025, list) else kbli_2025.get("data", [])
    print(f"      KBLI 2025: {len(items_2025)} codes")

    # Find problematic codes
    print("\n[2/5] Analyzing mapping problems...")

    problems = []
    for item in items_2025:
        code_2025 = item.get("kode_kbli_2025", "")
        pp28_sources = item.get("pp28_sources", [])
        status = item.get("status_mapping", "")
        judul_2025 = item.get("judul", "")

        # Only process MATCH_LANGSUNG with non-existent pp28_sources
        if status == "MATCH_LANGSUNG":
            # Check if pp28_sources contains the same code and it doesn't exist in 2020
            has_self_reference = code_2025 in pp28_sources
            self_exists_in_2020 = code_2025 in kbli_2020_codes

            if has_self_reference and not self_exists_in_2020:
                # Find best match in KBLI 2020
                match = find_best_match(judul_2025, kbli_2020_codes)

                problems.append(
                    {
                        "code_2025": code_2025,
                        "judul_2025": judul_2025,
                        "pp28_sources_old": pp28_sources,
                        "status_old": status,
                        "match_2020": match,
                    }
                )

    print(f"      Found {len(problems)} codes with mapping issues")

    # Categorize by confidence
    high_confidence = [
        p
        for p in problems
        if p["match_2020"] and p["match_2020"][2] >= HIGH_CONFIDENCE_THRESHOLD
    ]
    medium_confidence = [
        p
        for p in problems
        if p["match_2020"]
        and MEDIUM_CONFIDENCE_THRESHOLD
        <= p["match_2020"][2]
        < HIGH_CONFIDENCE_THRESHOLD
    ]
    no_match = [p for p in problems if not p["match_2020"]]

    print(
        f"\n      High confidence (≥{HIGH_CONFIDENCE_THRESHOLD:.0%}): {len(high_confidence)} codes"
    )
    print(
        f"      Medium confidence ({MEDIUM_CONFIDENCE_THRESHOLD:.0%}-{HIGH_CONFIDENCE_THRESHOLD:.0%}): {len(medium_confidence)} codes"
    )
    print(f"      No match found: {len(no_match)} codes (possibly truly new)")

    # Create backup
    print("\n[3/5] Creating backup...")
    backup_path = KBLI_2025_PATH.with_suffix(
        f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    shutil.copy(KBLI_2025_PATH, backup_path)
    print(f"      Backup saved to: {backup_path.name}")

    # Apply fixes
    print(f"\n[4/5] Applying fixes (auto-fix threshold: {AUTO_FIX_THRESHOLD:.0%})...")

    fixes_applied = []
    fixes_suggested = []

    for item in items_2025:
        code_2025 = item.get("kode_kbli_2025", "")

        # Find if this code has a problem
        problem = next((p for p in problems if p["code_2025"] == code_2025), None)

        if problem and problem["match_2020"]:
            match_code, match_title, match_score = problem["match_2020"]

            fix_record = {
                "kbli_2025": code_2025,
                "judul": problem["judul_2025"],
                "old_pp28_sources": problem["pp28_sources_old"],
                "old_status": problem["status_old"],
                "new_pp28_sources": [match_code],
                "new_status": "CODICE_RINUMERATO",
                "kbli_2020_source": match_code,
                "kbli_2020_title": match_title,
                "match_score": match_score,
            }

            if match_score >= AUTO_FIX_THRESHOLD:
                # Apply fix automatically
                item["pp28_sources"] = [match_code]
                item["status_mapping"] = "CODICE_RINUMERATO"
                item["kbli_2020_source"] = match_code
                item["mapping_note"] = (
                    f"KBLI 2020 code {match_code} rinumerato a {code_2025} in KBLI 2025 (match: {match_score:.0%})"
                )

                fix_record["action"] = "AUTO_FIXED"
                fixes_applied.append(fix_record)
            else:
                # Suggest fix but don't apply
                fix_record["action"] = "NEEDS_REVIEW"
                fixes_suggested.append(fix_record)

    print(f"      Auto-fixed: {len(fixes_applied)} codes")
    print(f"      Needs review: {len(fixes_suggested)} codes")

    # Save updated KBLI 2025
    print("\n[5/5] Saving updated data...")
    save_json(kbli_2025 if isinstance(kbli_2025, dict) else items_2025, KBLI_2025_PATH)
    print(f"      Updated: {KBLI_2025_PATH.name}")

    # Generate report
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_problems": len(problems),
            "auto_fixed": len(fixes_applied),
            "needs_review": len(fixes_suggested),
            "no_match_found": len(no_match),
            "thresholds": {
                "auto_fix": AUTO_FIX_THRESHOLD,
                "high_confidence": HIGH_CONFIDENCE_THRESHOLD,
                "medium_confidence": MEDIUM_CONFIDENCE_THRESHOLD,
            },
        },
        "fixes_applied": fixes_applied,
        "fixes_suggested": fixes_suggested,
        "no_match": [
            {
                "kbli_2025": p["code_2025"],
                "judul": p["judul_2025"],
                "note": "Possibly a truly new KBLI 2025 code",
            }
            for p in no_match
        ],
    }

    save_json(report, REPORT_PATH)
    print(f"      Report: {REPORT_PATH.name}")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\nTotal codes with mapping issues: {len(problems)}")
    print(f"✓ Auto-fixed (≥{AUTO_FIX_THRESHOLD:.0%} match): {len(fixes_applied)}")
    print(f"⚠ Needs manual review: {len(fixes_suggested)}")
    print(f"? No match found (new codes?): {len(no_match)}")

    if fixes_applied:
        print("\n--- Sample of auto-fixed codes ---")
        for fix in fixes_applied[:5]:
            print(f"  {fix['kbli_2025']}: {fix['judul'][:40]}")
            print(
                f"    {fix['old_pp28_sources']} → {fix['new_pp28_sources']} ({fix['match_score']:.0%})"
            )

    if fixes_suggested:
        print("\n--- Codes needing review ---")
        for fix in fixes_suggested[:5]:
            print(f"  {fix['kbli_2025']}: {fix['judul'][:40]}")
            print(
                f"    Suggested: {fix['kbli_2020_source']} ({fix['match_score']:.0%})"
            )

    print(f"\n✓ Done! Check report at: {REPORT_PATH}")


if __name__ == "__main__":
    main()
