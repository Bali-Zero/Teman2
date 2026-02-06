#!/usr/bin/env python3
"""
FASE 4: Distinguish BPS_ONLY codes by OSS applicability

Updates licensing_status for BPS_ONLY codes:
- NOT_APPLICABLE_OSS: Government, non-profit, prohibited activities (75 codes)
- PENDING_REGULATION: Actual business activities awaiting PP28 rules (101 codes)

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
    / f"kbli_mapping_phase4_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)

# Codes that are NOT applicable to OSS (government, non-profit, prohibited)
NOT_APPLICABLE_OSS_CODES = {
    # === GOVERNMENT ADMINISTRATION (84xxx) - 33 codes ===
    "84111",
    "84112",
    "84113",
    "84114",
    "84115",
    "84119",
    "84121",
    "84122",
    "84123",
    "84124",
    "84125",
    "84126",
    "84129",
    "84130",
    "84141",
    "84142",
    "84143",
    "84144",
    "84145",
    "84146",
    "84147",
    "84148",
    "84149",
    "84210",
    "84221",
    "84222",
    "84223",
    "84224",
    "84231",
    "84232",
    "84233",
    "84234",
    "84300",  # Mandatory social security
    # === GOVERNMENT FACILITIES (91xxx) - 8 codes ===
    "91111",  # Government libraries
    "91121",  # Government archives
    "91211",  # Government museums
    "91221",  # Government heritage sites
    "91421",  # Wildlife reserves
    "91422",  # National parks
    "91423",  # Protected forests
    "91426",  # Marine parks
    # === NON-COMMERCIAL ORGANIZATIONS (94xxx) - 7 codes ===
    "94110",  # Business associations
    "94121",  # Social science organizations
    "94122",  # Natural science organizations
    "94200",  # Labor unions
    "94910",  # Religious organizations
    "94920",  # Political parties
    "94990",  # Other membership organizations
    # === HOUSEHOLDS (97-98) - 3 codes ===
    "97000",  # Households as employers
    "98100",  # Household goods production
    "98200",  # Household services production
    # === INTERNATIONAL ORGANIZATIONS (99) - 1 code ===
    "99000",  # International bodies
    # === PROHIBITED (92) - 1 code ===
    "92000",  # Gambling
    # === GOVERNMENT SOCIAL WELFARE (87-88 pemerintah/LKS) - 13 codes ===
    "87101",  # Gov residential healthcare
    "87102",  # LKS residential healthcare
    "87201",  # Gov mental health care
    "87202",  # LKS mental health care
    "87301",  # Gov elderly/disabled care
    "87302",  # LKS elderly/disabled care
    "87991",  # LKS children welfare
    "87992",  # Children in conflict with law
    "87993",  # Homeless care
    "88101",  # Gov social without accommodation
    "88102",  # LKS social without accommodation
    "88901",  # Gov other social activities
    "88902",  # LKS other social activities
    # === CHARITY/FUND COLLECTION (88) - 3 codes ===
    "88903",  # Islamic charity (zakat/waqf)
    "88904",  # Non-Islamic charity
    "88905",  # Other charity
    # === GOVERNMENT EDUCATION (85 pemerintah) - 6 codes ===
    "85101",  # Gov kindergarten
    "85201",  # Gov primary school
    "85311",  # Gov middle school
    "85315",  # Gov high school
    "85550",  # Gov other education
    "85560",  # Gov job training
}

# Reason mapping for notes
NOT_APPLICABLE_REASONS = {
    "84": "Attività governativa - non richiede licenza commerciale OSS",
    "91_gov": "Struttura governativa - non attività commerciale",
    "91_nature": "Area protetta/conservazione - gestione governativa",
    "94": "Organizzazione non-profit/associazione - non attività commerciale",
    "97": "Attività domestica - non attività commerciale",
    "98": "Produzione domestica per uso proprio - non attività commerciale",
    "99": "Organizzazione internazionale - non soggetta a licenza OSS Indonesia",
    "92": "Attività proibita (gioco d'azzardo) - non licenziabile",
    "87_gov": "Servizio sociale governativo/LKS - non attività commerciale",
    "88_gov": "Servizio sociale governativo/LKS - non attività commerciale",
    "88_charity": "Raccolta fondi beneficenza - non attività commerciale",
    "85_gov": "Istruzione pubblica governativa - non attività commerciale",
}


def get_reason(code):
    """Get the appropriate reason for NOT_APPLICABLE_OSS status."""
    if code.startswith("84"):
        return NOT_APPLICABLE_REASONS["84"]
    elif code in ["91111", "91121", "91211", "91221"]:
        return NOT_APPLICABLE_REASONS["91_gov"]
    elif code in ["91421", "91422", "91423", "91426"]:
        return NOT_APPLICABLE_REASONS["91_nature"]
    elif code.startswith("94"):
        return NOT_APPLICABLE_REASONS["94"]
    elif code.startswith("97"):
        return NOT_APPLICABLE_REASONS["97"]
    elif code.startswith("98"):
        return NOT_APPLICABLE_REASONS["98"]
    elif code == "99000":
        return NOT_APPLICABLE_REASONS["99"]
    elif code == "92000":
        return NOT_APPLICABLE_REASONS["92"]
    elif code in [
        "87101",
        "87102",
        "87201",
        "87202",
        "87301",
        "87302",
        "87991",
        "87992",
        "87993",
    ]:
        return NOT_APPLICABLE_REASONS["87_gov"]
    elif code in ["88101", "88102", "88901", "88902"]:
        return NOT_APPLICABLE_REASONS["88_gov"]
    elif code in ["88903", "88904", "88905"]:
        return NOT_APPLICABLE_REASONS["88_charity"]
    elif code in ["85101", "85201", "85311", "85315", "85550", "85560"]:
        return NOT_APPLICABLE_REASONS["85_gov"]
    return "Non applicabile a licenza OSS"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print("=" * 70)
    print("FASE 4: Distinguish BPS_ONLY codes by OSS applicability")
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
        f".backup_phase4_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    shutil.copy(KBLI_2025_PATH, backup_path)
    print(f"      Backup: {backup_path.name}")

    # Update licensing_status
    print("\n[3/4] Updating licensing_status for BPS_ONLY codes...")

    not_applicable = []
    pending_regulation = []
    other_codes = []

    for item in items:
        code = item["kode_kbli_2025"]
        status = item.get("status_mapping", "")

        if status == "BPS_ONLY":
            if code in NOT_APPLICABLE_OSS_CODES:
                item["licensing_status"] = "NOT_APPLICABLE_OSS"
                item["licensing_note"] = get_reason(code)
                not_applicable.append(
                    {
                        "code": code,
                        "judul": item.get("judul", ""),
                        "reason": get_reason(code),
                    }
                )
            else:
                item["licensing_status"] = "PENDING_REGULATION"
                item["licensing_note"] = (
                    "Codice business nuovo in KBLI 2025, in attesa di normativa PP28."
                )
                pending_regulation.append(
                    {"code": code, "judul": item.get("judul", "")}
                )
        else:
            other_codes.append(code)

    print(f"      NOT_APPLICABLE_OSS: {len(not_applicable)}")
    print(f"      PENDING_REGULATION: {len(pending_regulation)}")
    print(f"      REGULATED (unchanged): {len(other_codes)}")

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
        "phase": "FASE 4 - Distinguish BPS_ONLY by OSS applicability",
        "summary": {
            "total_bps_only": len(not_applicable) + len(pending_regulation),
            "not_applicable_oss": len(not_applicable),
            "pending_regulation": len(pending_regulation),
            "regulated": len(other_codes),
        },
        "not_applicable_oss": not_applicable,
        "pending_regulation": pending_regulation,
    }
    save_json(report, REPORT_PATH)
    print(f"      Report: {REPORT_PATH.name}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"\n✓ NOT_APPLICABLE_OSS: {len(not_applicable)} codici")
    print("  (Governo, non-profit, proibito, welfare sociale)")

    by_category = {}
    for n in not_applicable:
        cat = n["code"][:2]
        if cat not in by_category:
            by_category[cat] = 0
        by_category[cat] += 1

    for cat in sorted(by_category.keys()):
        print(f"    Cat {cat}: {by_category[cat]} codici")

    print(f"\n✓ PENDING_REGULATION: {len(pending_regulation)} codici")
    print("  (Business reali in attesa di normativa)")

    by_category = {}
    for p in pending_regulation:
        cat = p["code"][:2]
        if cat not in by_category:
            by_category[cat] = 0
        by_category[cat] += 1

    for cat in sorted(by_category.keys()):
        print(f"    Cat {cat}: {by_category[cat]} codici")

    print("\n✓ FASE 4 completata!")


if __name__ == "__main__":
    main()
