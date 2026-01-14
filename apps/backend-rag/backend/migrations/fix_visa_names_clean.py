#!/usr/bin/env python3
"""
Fix visa names to use clean format:
- Title: "B4 - Government Assignment" (NOT "B4 - Visa on Arrival (Government Assignment)")
- Category field contains the visa type badge (VOA, Visit Visa, KITAS, etc.)

Run: fly ssh console -a nuzantara-rag -C "python /app/backend/migrations/fix_visa_names_clean.py"
"""

import asyncio
import os

import asyncpg

# Clean name format: CODE - Purpose (no visa type repeated)
CLEAN_NAMES = {
    # A Series - Visa Free
    "A1": "A1 - Tourism",
    "A4": "A4 - Government Assignment",
    "A36": "A36 - Ship and Aircraft Crew",
    "A37": "A37 - Ship Crew (Indonesian Waters)",

    # B Series - VOA
    "B1": "B1 - Tourism",
    "B4": "B4 - Government Assignment",

    # F Series - VOA (Short)
    "F1": "F1 - Tourism (Riau Islands)",
    "F4": "F4 - Government Assignment (Riau Islands)",

    # C Series - Visit Visa
    "C1": "C1 - Tourism",
    "C2": "C2 - Business",
    "C3": "C3 - Medical Treatment",
    "C4": "C4 - Government Assignment",
    "C5": "C5 - Media and Press",
    "C5A": "C5A - Content Creator",
    "C6": "C6 - Social Activities",
    "C7": "C7 - Arts and Culture",
    "C7A": "C7A - Music Performance",
    "C7B": "C7B - Music Performance Crew",
    "C7C": "C7C - Talent and Arts",
    "C8": "C8 - Sports Activities",
    "C8A": "C8A - Athletes",
    "C8B": "C8B - Sports Officials",
    "C9": "C9 - Short Study",
    "C9A": "C9A - Religious Training",
    "C9B": "C9B - Indonesian Language Training",
    "C10": "C10 - Business Speaker",
    "C10A": "C10A - Religious Speaker",
    "C11": "C11 - Product Promotion",
    "C11A": "C11A - Product Promotion (Variant)",
    "C12": "C12 - Pre-Investment",
    "C13": "C13 - Crew Joining Transport",
    "C14": "C14 - Film Production",
    "C15": "C15 - Emergency Response",
    "C16": "C16 - Industry Instructor",
    "C17": "C17 - Audit and Quality Control",
    "C18": "C18 - Work Trial",
    "C19": "C19 - After-Sales Service",
    "C20": "C20 - Installation and Repair",
    "C21": "C21 - Training Instructor",
    "C22": "C22 - Internship",
    "C22A": "C22A - Academic Internship",
    "C22B": "C22B - Skills Development",
}


async def fix_names():
    """Update visa names to clean format."""
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])

    try:
        print("Fixing visa names to clean format...\n")
        print("Format: 'CODE - Purpose' (visa type in category badge)\n")

        updated = 0
        for code, clean_name in CLEAN_NAMES.items():
            result = await conn.execute(
                "UPDATE visa_types SET name = $2, last_updated = NOW() WHERE code = $1",
                code,
                clean_name,
            )
            if "UPDATE 1" in result:
                print(f"  ✓ {clean_name}")
                updated += 1

        print(f"\n✅ Fixed {updated} visa names")

        # Show results
        print("\n📋 Updated Visa Names:")
        print("-" * 60)
        rows = await conn.fetch(
            """
            SELECT code, name, category
            FROM visa_types
            WHERE code LIKE 'A%' OR code LIKE 'B%' OR code LIKE 'F%' OR code LIKE 'C%'
            ORDER BY
                CASE
                    WHEN code LIKE 'A%' THEN 1
                    WHEN code LIKE 'B%' THEN 2
                    WHEN code LIKE 'F%' THEN 3
                    WHEN code LIKE 'C%' THEN 4
                END,
                code
            """
        )

        current_series = ""
        for row in rows:
            series = row['code'][0]
            if series != current_series:
                current_series = series
                series_name = {
                    'A': 'Visa Free',
                    'B': 'VOA',
                    'F': 'VOA (Short)',
                    'C': 'Visit Visa'
                }.get(series, 'Other')
                print(f"\n  === Series {series} - {series_name} ===")

            print(f"  {row['name']:40} [{row['category']}]")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(fix_names())
