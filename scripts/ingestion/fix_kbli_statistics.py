#!/usr/bin/env python3
"""
Update statistics section in KBLI 2025 metadata to reflect actual data.

Author: Zantara AI
Date: 2026-02-04
"""

import json
from datetime import datetime
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).parent.parent.parent
KBLI_2025_PATH = BASE_DIR / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print("=" * 70)
    print("UPDATE: Statistiche metadata KBLI 2025")
    print("=" * 70)

    # Load data
    print("\n[1/3] Caricamento dati...")
    kbli_raw = load_json(KBLI_2025_PATH)

    if not isinstance(kbli_raw, dict) or "data" not in kbli_raw:
        print("ERROR: File non ha struttura attesa (metadata + data)")
        return

    items = kbli_raw["data"]
    print(f"      Totale codici: {len(items)}")

    # Calculate actual statistics
    print("\n[2/3] Calcolo statistiche reali...")

    # Status mapping counts
    status_counts = Counter(item.get("status_mapping", "") for item in items)

    # Licensing status counts
    licensing_counts = Counter(item.get("licensing_status", "") for item in items)

    # PMA status counts
    pma_counts = Counter(item.get("pma_status", "") for item in items)

    # PMA prioritas count
    pma_prioritas = sum(1 for item in items if item.get("pma_prioritas") == True)

    # With per_skala
    with_per_skala = sum(
        1 for item in items if item.get("per_skala") and len(item["per_skala"]) > 0
    )

    # With sektor
    with_sektor = sum(1 for item in items if item.get("sektor_id"))

    # PMA verification counts
    pma_verification_counts = Counter(
        item.get("pma_verification", "null") for item in items
    )

    # Build new statistics
    new_stats = {
        "total_codes": len(items),
        "by_status": dict(status_counts),
        "by_licensing": dict(licensing_counts),
        "pma": {
            "TERBUKA": pma_counts.get("TERBUKA", 0),
            "TERBATAS": pma_counts.get("TERBATAS", 0),
            "TERTUTUP": pma_counts.get("TERTUTUP", 0),
            "PRIORITAS": pma_prioritas,
        },
        "pma_verification": {
            k: v for k, v in pma_verification_counts.items() if k != "null"
        },
        "with_per_skala": with_per_skala,
        "with_sektor": with_sektor,
        "last_updated": datetime.now().isoformat(),
    }

    # Print comparison
    print("\n      === Confronto Statistiche ===")
    old_stats = kbli_raw.get("statistics", {})

    print("\n      by_status (VECCHIO → NUOVO):")
    old_by_status = old_stats.get("by_status", {})
    for status, count in sorted(new_stats["by_status"].items()):
        old_count = old_by_status.get(status, "N/A")
        marker = "✓" if old_count == count else "⚠"
        print(f"        {marker} {status}: {old_count} → {count}")

    print("\n      by_licensing (NUOVO):")
    for status, count in sorted(new_stats["by_licensing"].items()):
        print(f"        {status}: {count}")

    print("\n      pma_verification (NUOVO):")
    for status, count in sorted(new_stats["pma_verification"].items()):
        print(f"        {status}: {count}")

    # Update
    print("\n[3/3] Aggiornamento statistiche...")
    kbli_raw["statistics"] = new_stats
    kbli_raw["metadata"]["statistics_updated"] = datetime.now().isoformat()

    save_json(kbli_raw, KBLI_2025_PATH)
    print(f"      ✓ Aggiornato: {KBLI_2025_PATH.name}")

    print("\n" + "=" * 70)
    print("✓ Statistiche aggiornate!")
    print("=" * 70)


if __name__ == "__main__":
    main()
