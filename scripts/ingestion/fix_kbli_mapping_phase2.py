#!/usr/bin/env python3
"""
FASE 2: Flag BPS_ONLY codes with licensing_status: "PENDING_REGULATION"

These 174 codes are new in KBLI 2025 and don't have PP28 licensing rules yet.
This script adds a clear flag to indicate their regulatory status.

Author: Zantara AI
Date: 2026-02-04
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
KBLI_2025_PATH = BASE_DIR / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
REPORT_PATH = (
    BASE_DIR
    / "reports"
    / f"kbli_mapping_phase2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print("=" * 70)
    print("FASE 2: Flag BPS_ONLY codes with licensing_status")
    print("=" * 70)

    # Load data
    print("\n[1/4] Loading data...")
    kbli_2025_raw = load_json(KBLI_2025_PATH)
    if isinstance(kbli_2025_raw, dict) and "data" in kbli_2025_raw:
        items = kbli_2025_raw["data"]
        is_wrapped = True
    else:
        items = kbli_2025_raw
        is_wrapped = False
    print(f"      KBLI 2025: {len(items)} codes")

    # Create backup
    print("\n[2/4] Creating backup...")
    backup_path = KBLI_2025_PATH.with_suffix(
        f".backup_phase2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    shutil.copy(KBLI_2025_PATH, backup_path)
    print(f"      Backup: {backup_path.name}")

    # Apply flags
    print("\n[3/4] Flagging BPS_ONLY codes...")

    flagged = []
    already_regulated = []

    for item in items:
        code = item["kode_kbli_2025"]
        status = item.get("status_mapping", "")

        if status == "BPS_ONLY":
            # New code without PP28 regulation
            item["licensing_status"] = "PENDING_REGULATION"
            item["licensing_note"] = (
                "Codice nuovo in KBLI 2025, non presente in PP 28/2025. Normativa in attesa."
            )
            flagged.append(
                {
                    "code": code,
                    "judul": item.get("judul", ""),
                    "kategori": item.get("kategori", ""),
                }
            )
        else:
            # Has PP28 source - regulated
            if "licensing_status" not in item:
                item["licensing_status"] = "REGULATED"
            already_regulated.append(code)

    print(f"      BPS_ONLY flagged: {len(flagged)}")
    print(f"      Already regulated: {len(already_regulated)}")

    # Save
    print("\n[4/4] Saving...")
    if is_wrapped:
        kbli_2025_raw["data"] = items
        save_json(kbli_2025_raw, KBLI_2025_PATH)
    else:
        save_json(items, KBLI_2025_PATH)
    print(f"      Updated: {KBLI_2025_PATH.name}")

    # Report
    report = {
        "timestamp": datetime.now().isoformat(),
        "phase": "FASE 2 - Flag BPS_ONLY codes",
        "summary": {
            "total_codes": len(items),
            "bps_only_flagged": len(flagged),
            "already_regulated": len(already_regulated),
        },
        "flagged_codes": flagged,
    }
    save_json(report, REPORT_PATH)
    print(f"      Report: {REPORT_PATH.name}")

    # Summary by category
    print("\n" + "=" * 70)
    print("BPS_ONLY CODES BY CATEGORY")
    print("=" * 70)

    by_category = {}
    for f in flagged:
        cat = f.get("kategori", "Unknown")[:1]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(f)

    for cat in sorted(by_category.keys()):
        codes = by_category[cat]
        print(f"\n  Kategori {cat}: {len(codes)} codes")
        for c in codes[:3]:
            print(f"    - {c['code']}: {c['judul'][:50]}")
        if len(codes) > 3:
            print(f"    ... e altri {len(codes) - 3}")

    print(
        f"\n✓ FASE 2 completata! {len(flagged)} codici BPS_ONLY flaggati come PENDING_REGULATION"
    )


if __name__ == "__main__":
    main()
