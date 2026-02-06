#!/usr/bin/env python3
"""
VERIFICATION PASS 6: Complete cross-sector validation

Checks:
1. Every pp28_sources code must exist in KBLI 2020
2. Check for logical inconsistencies (e.g., finance code mapping to education)
3. Verify CODICE_RINUMERATO codes have sensible mappings (same sector)
"""

import json
from collections import defaultdict

# KBLI Category/Section mapping based on 2-digit codes
KBLI_SECTORS = {
    "01": "A - Agriculture",
    "02": "A - Agriculture",
    "03": "A - Agriculture",
    "05": "B - Mining",
    "06": "B - Mining",
    "07": "B - Mining",
    "08": "B - Mining",
    "09": "B - Mining",
    "10": "C - Manufacturing",
    "11": "C - Manufacturing",
    "12": "C - Manufacturing",
    "13": "C - Manufacturing",
    "14": "C - Manufacturing",
    "15": "C - Manufacturing",
    "16": "C - Manufacturing",
    "17": "C - Manufacturing",
    "18": "C - Manufacturing",
    "19": "C - Manufacturing",
    "20": "C - Manufacturing",
    "21": "C - Manufacturing",
    "22": "C - Manufacturing",
    "23": "C - Manufacturing",
    "24": "C - Manufacturing",
    "25": "C - Manufacturing",
    "26": "C - Manufacturing",
    "27": "C - Manufacturing",
    "28": "C - Manufacturing",
    "29": "C - Manufacturing",
    "30": "C - Manufacturing",
    "31": "C - Manufacturing",
    "32": "C - Manufacturing",
    "33": "C - Manufacturing",
    "35": "D - Electricity/Gas",
    "36": "E - Water/Waste",
    "37": "E - Water/Waste",
    "38": "E - Water/Waste",
    "39": "E - Water/Waste",
    "41": "F - Construction",
    "42": "F - Construction",
    "43": "F - Construction",
    "45": "G - Trade",
    "46": "G - Trade",
    "47": "G - Trade",
    "49": "H - Transport",
    "50": "H - Transport",
    "51": "H - Transport",
    "52": "H - Transport",
    "53": "H - Transport",
    "55": "I - Accommodation/Food",
    "56": "I - Accommodation/Food",
    "58": "J - Info/Communication",
    "59": "J - Info/Communication",
    "60": "J - Info/Communication",
    "61": "J - Info/Communication",
    "62": "J - Info/Communication",
    "63": "J - Info/Communication",
    "64": "K - Finance/Insurance",
    "65": "K - Finance/Insurance",
    "66": "K - Finance/Insurance",
    "68": "L - Real Estate",
    "69": "M - Professional Services",
    "70": "M - Professional Services",
    "71": "M - Professional Services",
    "72": "M - Professional Services",
    "73": "M - Professional Services",
    "74": "M - Professional Services",
    "75": "M - Professional Services",
    "77": "N - Administrative Services",
    "78": "N - Administrative Services",
    "79": "N - Administrative Services",
    "80": "N - Administrative Services",
    "81": "N - Administrative Services",
    "82": "N - Administrative Services",
    "84": "O - Public Admin",
    "85": "P - Education",
    "86": "Q - Health/Social",
    "87": "Q - Health/Social",
    "88": "Q - Health/Social",
    "90": "R - Arts/Entertainment",
    "91": "R - Arts/Entertainment",
    "92": "R - Arts/Entertainment",
    "93": "R - Arts/Entertainment",
    "94": "S - Other Services",
    "95": "S - Other Services",
    "96": "S - Other Services",
    "97": "T - Household Activities",
    "98": "T - Household Activities",
    "99": "U - International Orgs",
}


def get_sector(code):
    """Get sector from KBLI code (first 2 digits)"""
    if len(code) >= 2:
        prefix = code[:2]
        return KBLI_SECTORS.get(prefix, f"Unknown ({prefix})")
    return "Unknown"


def get_sector_letter(code):
    """Get just the sector letter (A-U) from code"""
    sector = get_sector(code)
    if sector.startswith("Unknown"):
        return "X"
    return sector.split(" - ")[0]


def main():
    print("=" * 80)
    print("VERIFICATION PASS 6: Complete Cross-Sector Validation")
    print("=" * 80)
    print()

    # Load KBLI 2025
    with open(
        "source_documents/KBLI_2025_FINAL_CLEAN.json", "r", encoding="utf-8"
    ) as f:
        kbli_2025_file = json.load(f)

    # Extract metadata and data array
    metadata = kbli_2025_file.get("metadata", {})
    statistics = kbli_2025_file.get("statistics", {})
    kbli_2025 = kbli_2025_file.get("data", [])

    print(f"KBLI 2025 version: {metadata.get('version', 'unknown')}")
    print(f"KBLI 2025 source: {metadata.get('source', 'unknown')}")
    print()

    # Load KBLI 2020
    with open("source_documents/kbli_2020_official.json", "r", encoding="utf-8") as f:
        kbli_2020 = json.load(f)

    # Build set of all KBLI 2020 codes
    kbli_2020_codes = set()
    for entry in kbli_2020:
        code = entry.get("kode_kbli") or entry.get("code")
        if code:
            kbli_2020_codes.add(str(code))

    print(f"KBLI 2020 codes loaded: {len(kbli_2020_codes)}")
    print(f"KBLI 2025 codes to check: {len(kbli_2025)}")
    print()

    # Validation counters
    total_checked = 0
    codes_with_pp28_sources = 0
    invalid_pp28_sources = []
    cross_sector_anomalies = []
    rinumerato_issues = []

    # Track statistics
    change_type_stats = defaultdict(int)
    pp28_source_found = 0
    pp28_source_missing = 0

    for entry in kbli_2025:
        total_checked += 1
        code_2025 = entry.get("kode_kbli_2025", "")
        title = entry.get("judul", "")
        change_type = entry.get(
            "status_mapping", ""
        )  # Field is status_mapping, not change_type
        pp28_sources = entry.get("pp28_sources", []) or []

        change_type_stats[change_type] += 1

        # Check 1: Verify pp28_sources codes exist in KBLI 2020
        if pp28_sources:
            codes_with_pp28_sources += 1
            for source_code in pp28_sources:
                if source_code not in kbli_2020_codes:
                    invalid_pp28_sources.append(
                        {
                            "code_2025": code_2025,
                            "title": title,
                            "invalid_source": source_code,
                            "change_type": change_type,
                        }
                    )
                    pp28_source_missing += 1
                else:
                    pp28_source_found += 1

                # Check 2 & 3: Cross-sector mapping check
                sector_2025 = get_sector_letter(code_2025)
                sector_source = get_sector_letter(source_code)

                # For CODICE_RINUMERATO, expect same sector
                if change_type == "CODICE_RINUMERATO":
                    if (
                        sector_2025 != sector_source
                        and sector_source != "X"
                        and sector_2025 != "X"
                    ):
                        rinumerato_issues.append(
                            {
                                "code_2025": code_2025,
                                "title": title,
                                "source_code": source_code,
                                "sector_2025": get_sector(code_2025),
                                "sector_source": get_sector(source_code),
                            }
                        )

                # General cross-sector anomaly detection
                # Flag if sectors are very different (not adjacent in typical business flows)
                if (
                    sector_2025 != sector_source
                    and sector_source != "X"
                    and sector_2025 != "X"
                ):
                    # Allow some logical cross-sector mappings (e.g., trade of manufactured goods)
                    allowed_cross = [
                        ("C", "G"),  # Manufacturing <-> Trade
                        ("G", "C"),
                        ("J", "M"),  # Info/Comm <-> Professional Services
                        ("M", "J"),
                        ("K", "M"),  # Finance <-> Professional Services
                        ("M", "K"),
                        ("N", "M"),  # Admin <-> Professional Services
                        ("M", "N"),
                    ]

                    mapping = (sector_2025, sector_source)

                    # Flag truly anomalous mappings (e.g., Finance to Education)
                    suspicious_pairs = [
                        ("K", "P"),  # Finance <-> Education
                        ("P", "K"),
                        ("K", "Q"),  # Finance <-> Health
                        ("Q", "K"),
                        ("A", "K"),  # Agriculture <-> Finance
                        ("K", "A"),
                        ("B", "P"),  # Mining <-> Education
                        ("P", "B"),
                    ]

                    if mapping in suspicious_pairs:
                        cross_sector_anomalies.append(
                            {
                                "code_2025": code_2025,
                                "title": title,
                                "source_code": source_code,
                                "sector_2025": get_sector(code_2025),
                                "sector_source": get_sector(source_code),
                                "change_type": change_type,
                            }
                        )

    # Print results
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print()

    print(f"Total codes checked: {total_checked}")
    print(f"Codes with pp28_sources: {codes_with_pp28_sources}")
    print(f"Total pp28_source references: {pp28_source_found + pp28_source_missing}")
    print(f"  - Found in KBLI 2020: {pp28_source_found}")
    print(f"  - NOT found in KBLI 2020: {pp28_source_missing}")
    print()

    print("Change type distribution:")
    for ct, count in sorted(change_type_stats.items()):
        print(f"  {ct or 'UNCHANGED'}: {count}")
    print()

    print("-" * 80)
    print("CHECK 1: Invalid pp28_sources (codes not in KBLI 2020)")
    print("-" * 80)
    if invalid_pp28_sources:
        print(f"FOUND {len(invalid_pp28_sources)} invalid source codes:")
        for item in invalid_pp28_sources[:20]:  # Show first 20
            print(
                f"  - {item['code_2025']} ({item['change_type']}): invalid source '{item['invalid_source']}'"
            )
            print(f"    Title: {item['title'][:60]}...")
        if len(invalid_pp28_sources) > 20:
            print(f"  ... and {len(invalid_pp28_sources) - 20} more")
    else:
        print("PASS - All pp28_sources codes exist in KBLI 2020")
    print()

    print("-" * 80)
    print("CHECK 2: Cross-sector mapping anomalies (suspicious mappings)")
    print("-" * 80)
    if cross_sector_anomalies:
        print(f"FOUND {len(cross_sector_anomalies)} suspicious cross-sector mappings:")
        for item in cross_sector_anomalies[:20]:
            print(f"  - {item['code_2025']} -> {item['source_code']}")
            print(f"    {item['sector_2025']} <- {item['sector_source']}")
            print(f"    Title: {item['title'][:50]}...")
        if len(cross_sector_anomalies) > 20:
            print(f"  ... and {len(cross_sector_anomalies) - 20} more")
    else:
        print("PASS - No suspicious cross-sector anomalies found")
    print()

    print("-" * 80)
    print("CHECK 3: CODICE_RINUMERATO with different sectors")
    print("-" * 80)
    if rinumerato_issues:
        print(f"FOUND {len(rinumerato_issues)} renumbered codes with sector changes:")
        for item in rinumerato_issues[:20]:
            print(f"  - {item['code_2025']} <- {item['source_code']}")
            print(f"    {item['sector_2025']} <- {item['sector_source']}")
            print(f"    Title: {item['title'][:50]}...")
        if len(rinumerato_issues) > 20:
            print(f"  ... and {len(rinumerato_issues) - 20} more")
    else:
        print("PASS - All CODICE_RINUMERATO codes map within same sector")
    print()

    # Final verdict
    print("=" * 80)
    print("FINAL VERDICT")
    print("=" * 80)

    issues_found = (
        len(invalid_pp28_sources) + len(cross_sector_anomalies) + len(rinumerato_issues)
    )

    if issues_found == 0:
        print("STATUS: PASS")
        print("All 1562 codes validated successfully!")
        print("- All pp28_sources reference valid KBLI 2020 codes")
        print("- No suspicious cross-sector mappings detected")
        print("- All CODICE_RINUMERATO codes maintain sector consistency")
    else:
        print("STATUS: ISSUES FOUND")
        print(f"- Invalid pp28_sources: {len(invalid_pp28_sources)}")
        print(f"- Cross-sector anomalies: {len(cross_sector_anomalies)}")
        print(f"- CODICE_RINUMERATO sector changes: {len(rinumerato_issues)}")

        # Determine if these are critical
        if len(invalid_pp28_sources) > 0:
            print()
            print("CRITICAL: Some pp28_sources reference non-existent KBLI 2020 codes!")

        if len(cross_sector_anomalies) > 0:
            print()
            print("WARNING: Some mappings cross unexpected sector boundaries")
            print("         (May be intentional policy changes - review manually)")

        if len(rinumerato_issues) > 0:
            print()
            print("WARNING: Some CODICE_RINUMERATO entries changed sectors")
            print("         (Unusual but may be intentional - review manually)")


if __name__ == "__main__":
    main()
