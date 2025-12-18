#!/usr/bin/env python3
"""
VISA CODE VALIDATOR
==================

Validates that visa documents in Qdrant contain only valid, current visa codes.
Reports any documents that reference codes not in the official registry.

Valid Indonesian Visa Codes (as of 2025):
- E23X: Investor visas
- E28X: Work visas
- E30X: Social/Cultural visas
- E31X: Family visas
- E32X: Second Home visas
- E33X: Retirement visas
- B211: Visit visas (social/business)
- D212: Education visas

Usage:
    python scripts/validate_visa_codes.py
"""

import asyncio
import os
import re
from collections import defaultdict
from datetime import datetime

import httpx
from dotenv import load_dotenv

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "https://nuzantara-qdrant.fly.dev")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")

REPORT_DIR = "scripts/audit_reports"
os.makedirs(REPORT_DIR, exist_ok=True)

# Valid current visa code patterns
VALID_PATTERNS = [
    # E-series (KITAS/KITAP)
    r"E23[A-Z]?",  # Investor
    r"E28[A-Z]?",  # Work
    r"E30[A-Z]?",  # Social/Cultural
    r"E31[A-Z]?",  # Family
    r"E32[A-Z]?",  # Second Home
    r"E33[A-Z]?",  # Retirement
    # Visit visas
    r"B211[A-Z]?",  # Visit visa (valid format is B211, NOT B211A as standalone)
    # But B211A as part of description is OK
    r"D212",  # Education
    # VOA
    r"VOA",  # Visa on Arrival
    # eVOA
    r"eVOA",  # Electronic VOA
]

# Known invalid/obsolete patterns
INVALID_PATTERNS = [
    r"C3\d{2}",  # Old C-series (C312, C313, C314, C315, C316, C317)
    r"(?<![EB])211[AB](?![0-9])",  # Standalone 211A or 211B (not part of B211 or E211)
]


async def scroll_collection(client, headers, collection, limit=100, offset=None):
    """Scroll through collection"""
    payload = {"limit": limit, "with_payload": True, "with_vector": False}
    if offset:
        payload["offset"] = offset

    resp = await client.post(
        f"{QDRANT_URL}/collections/{collection}/points/scroll",
        headers=headers,
        json=payload,
        timeout=60,
    )

    if resp.status_code == 200:
        data = resp.json().get("result", {})
        return data.get("points", []), data.get("next_page_offset")
    return [], None


def extract_visa_codes(text: str) -> list[str]:
    """Extract all potential visa codes from text"""
    # Match patterns like E31A, C317, B211, etc.
    pattern = r"\b([A-Z]\d{2,3}[A-Z]?)\b"
    matches = re.findall(pattern, text.upper())
    return list(set(matches))


def validate_code(code: str) -> tuple[bool, str]:
    """Check if a code is valid"""
    # Check against valid patterns
    for pattern in VALID_PATTERNS:
        if re.fullmatch(pattern, code, re.IGNORECASE):
            return True, "valid"

    # Check against known invalid patterns
    for pattern in INVALID_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            return False, "obsolete/fake"

    # Unknown - might be valid, might not
    return None, "unknown"


async def validate_collection(client, headers, collection):
    """Validate all documents in a collection"""
    print(f"\nValidating {collection}...")

    stats = {
        "total": 0,
        "with_codes": 0,
        "valid_codes": defaultdict(int),
        "invalid_codes": defaultdict(list),
        "unknown_codes": defaultdict(int),
    }

    offset = None
    while True:
        points, next_offset = await scroll_collection(
            client, headers, collection, limit=100, offset=offset
        )

        if not points:
            break

        for point in points:
            stats["total"] += 1
            point_id = str(point["id"])
            payload = point.get("payload", {})
            text = payload.get("text", "")
            metadata = str(payload.get("metadata", {}))

            all_text = f"{text} {metadata}"
            codes = extract_visa_codes(all_text)

            if codes:
                stats["with_codes"] += 1

                for code in codes:
                    is_valid, status = validate_code(code)
                    if is_valid is True:
                        stats["valid_codes"][code] += 1
                    elif is_valid is False:
                        stats["invalid_codes"][code].append(point_id)
                    else:
                        stats["unknown_codes"][code] += 1

        offset = next_offset
        if not offset:
            break

        if stats["total"] % 500 == 0:
            print(f"  Processed {stats['total']} documents...")

    print(f"  Done: {stats['total']} docs, {stats['with_codes']} with codes")
    return stats


async def main():
    print("=" * 60)
    print("VISA CODE VALIDATOR")
    print("=" * 60)
    print(f"Started: {datetime.now().isoformat()}")

    headers = {"api-key": QDRANT_API_KEY, "Content-Type": "application/json"}

    collections = ["visa_oracle", "legal_unified", "bali_zero_pricing"]

    all_stats = {}

    async with httpx.AsyncClient() as client:
        for collection in collections:
            try:
                stats = await validate_collection(client, headers, collection)
                all_stats[collection] = stats
            except Exception as e:
                print(f"  Error: {e}")
                all_stats[collection] = {"error": str(e)}

    # Generate report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"{REPORT_DIR}/visa_validation_{timestamp}.md"

    with open(report_path, "w") as f:
        f.write("# Visa Code Validation Report\n\n")
        f.write(f"**Generated:** {datetime.now().isoformat()}\n\n")

        # Summary
        f.write("## Summary\n\n")
        f.write("| Collection | Documents | With Codes | Invalid Found |\n")
        f.write("|------------|-----------|------------|---------------|\n")

        for coll, stats in all_stats.items():
            if "error" in stats:
                f.write(f"| {coll} | Error | - | - |\n")
            else:
                invalid_count = sum(len(ids) for ids in stats["invalid_codes"].values())
                f.write(
                    f"| {coll} | {stats['total']} | {stats['with_codes']} | {invalid_count} |\n"
                )

        # Valid codes found
        f.write("\n## Valid Codes Distribution\n\n")
        all_valid = defaultdict(int)
        for stats in all_stats.values():
            if "valid_codes" in stats:
                for code, count in stats["valid_codes"].items():
                    all_valid[code] += count

        if all_valid:
            f.write("| Code | Occurrences |\n")
            f.write("|------|-------------|\n")
            for code, count in sorted(all_valid.items(), key=lambda x: -x[1])[:20]:
                f.write(f"| {code} | {count} |\n")

        # Invalid codes found
        f.write("\n## Invalid/Obsolete Codes Found\n\n")
        has_invalid = False
        for coll, stats in all_stats.items():
            if "invalid_codes" in stats and stats["invalid_codes"]:
                has_invalid = True
                f.write(f"### {coll}\n\n")
                for code, ids in stats["invalid_codes"].items():
                    f.write(f"**{code}** - {len(ids)} documents\n")
                    f.write(f"```\n{ids[:10]}\n```\n\n")

        if not has_invalid:
            f.write("No invalid codes found.\n")

        f.write("\n---\n*Generated by validate_visa_codes.py*\n")

    print(f"\nReport saved: {report_path}")

    # Console summary
    print("\n" + "=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)

    total_invalid = 0
    for stats in all_stats.values():
        if "invalid_codes" in stats:
            total_invalid += sum(len(ids) for ids in stats["invalid_codes"].values())

    if total_invalid == 0:
        print("All visa codes are valid!")
    else:
        print(f"Found {total_invalid} documents with invalid codes")
        print("See report for details")


if __name__ == "__main__":
    asyncio.run(main())
