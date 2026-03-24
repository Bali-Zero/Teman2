"""
Nationality Normalizer — One-time migration script
Normalizes 227 distinct nationality values down to canonical English demonyms.

Usage:
    cd apps/backend-rag && source .venv/bin/activate
    PYTHONPATH=. python scripts/normalize_nationalities.py --dry-run
    PYTHONPATH=. python scripts/normalize_nationalities.py --apply
"""

import argparse
import asyncio
import logging

import asyncpg

logger = logging.getLogger(__name__)

# Canonical map: every known variant → English demonym
# Source: production DB audit (227 distinct values, 11280 clients)
NATIONALITY_MAP: dict[str, str] = {
    # ── Indonesian ──
    "Indonesian": "Indonesian",
    "INDONESIA": "Indonesian",
    "Indonesia": "Indonesian",
    "WNI": "Indonesian",
    # ── Italian ──
    "Italian": "Italian",
    "ITALIANA": "Italian",
    "ITALIAN": "Italian",
    "ITALIA": "Italian",
    "ITALY": "Italian",
    "Italy": "Italian",
    "ITA": "Italian",
    "IT": "Italian",
    "REPUBBLICA ITALIANA": "Italian",
    # ── Spanish ──
    "Spanish": "Spanish",
    "SPAIN": "Spanish",
    "Spain": "Spanish",
    "SPANYOL": "Spanish",
    "ESP": "Spanish",
    "ESPAÑOLA": "Spanish",
    # ── American ──
    "American": "American",
    "USA": "American",
    "US": "American",
    "United States": "American",
    "UNITED STATES": "American",
    "UNITED STATES OF AMERICA": "American",
    "United States of America": "American",
    "NEGARA: United States": "American",
    "NEGARA: United States TTL:-": "American",
    # ── Australian ──
    "Australian": "Australian",
    "AUSTRALIAN": "Australian",
    "AUSTRALIA": "Australian",
    "Australia": "Australian",
    "NEGARA: Australia": "Australian",
    # ── German ──
    "German": "German",
    "GERMANY": "German",
    "Germany": "German",
    "DEUTSCH": "German",
    "JERMAN": "German",
    "NEGERA: Germany": "German",
    # ── British ──
    "British": "British",
    "BRITISH CITIZEN": "British",
    "British Citizen": "British",
    "United Kingdom": "British",
    "UNITED KINGDOM": "British",
    "GBR": "British",
    "Inggris": "British",
    # ── French ──
    "French": "French",
    "FRANCE": "French",
    "France": "French",
    "Française": "French",
    "FRANCAISE": "French",
    "FRA": "French",
    "PRANCIS": "French",
    "PERANCIS": "French",
    "FRANCIS": "French",
    "NEGARA: France": "French",
    "NEGARA FRANCE": "French",
    # ── Russian ──
    "Russian": "Russian",
    "RUSSIA": "Russian",
    "Russian Federation": "Russian",
    "RUSSIAN FEDERATION": "Russian",
    "RUS": "Russian",
    "Rusia": "Russian",
    "RUSIA": "Russian",
    "NEGARA: Russian Federation": "Russian",
    "NEGARA: RUSSIA": "Russian",
    "NEGARA: Russian Federation KITAS: - TTL: -": "Russian",
    "Российская Федерация": "Russian",
    "РОССИЙСКАЯ ФЕДЕРАЦИЯ / RUSSIAN FEDERATION": "Russian",
    "Federation": "Russian",  # orphaned from "Russian Federation"
    # ── Dutch ──
    "Dutch": "Dutch",
    "Netherlands": "Dutch",
    "NETHERLANDS": "Dutch",
    "BELANDA": "Dutch",
    "NLD": "Dutch",
    "NL": "Dutch",
    "Nederlandse": "Dutch",
    "NEGARA: BELANDA": "Dutch",
    # ── Swiss ──
    "Swiss": "Swiss",
    "SWITZERLAND": "Swiss",
    "SWISS": "Swiss",
    "CHE": "Swiss",
    # ── Singaporean ──
    "Singaporean": "Singaporean",
    "Singapore": "Singaporean",
    "SINGAPORE": "Singaporean",
    "SINGAPORE CITIZEN": "Singaporean",
    "SINGAPURA": "Singaporean",
    # ── Emirati ──
    "Emirati": "Emirati",
    # ── Danish ──
    "Danish": "Danish",
    "DNK": "Danish",
    # ── Brazilian ──
    "Brazilian": "Brazilian",
    "Brasil": "Brazilian",
    "BRASIL": "Brazilian",
    "BRA": "Brazilian",
    "BRAZIL": "Brazilian",
    # ── Indian ──
    "Indian": "Indian",
    "INDIAN": "Indian",
    "India": "Indian",
    "INDIA": "Indian",
    "IND": "Indian",
    # ── Hungarian ──
    "Hungarian": "Hungarian",
    "Hungary": "Hungarian",
    "HUNGARY": "Hungarian",
    "HUN": "Hungarian",
    "MAGYAR": "Hungarian",
    "MAGYAR/HUNGARIAN": "Hungarian",
    # ── Ukrainian ──
    "Ukrainian": "Ukrainian",
    "UKRAINIAN": "Ukrainian",
    "Ukraine": "Ukrainian",
    "UKRAINE": "Ukrainian",
    "UKRAINA": "Ukrainian",
    "UKR": "Ukrainian",
    "УКРАЇНА": "Ukrainian",
    "Україна": "Ukrainian",
    "NEGARA: UKRAINE": "Ukrainian",
    # ── Swedish ──
    "Swedish": "Swedish",
    "Sweden": "Swedish",
    # ── Belgian ──
    "Belgian": "Belgian",
    "BELGIUM": "Belgian",
    "BELGIA": "Belgian",
    # ── Thai ──
    "Thai": "Thai",
    "THAI": "Thai",
    "THA": "Thai",
    "THAILAND": "Thai",
    # ── Austrian ──
    "Austrian": "Austrian",
    "AUSTRIA": "Austrian",
    "AUT": "Austrian",
    # ── South African ──
    "South African": "South African",
    "SOUTH AFRICAN": "South African",
    "South Africa": "South African",
    # ── Chinese ──
    "Chinese": "Chinese",
    "CHINESE": "Chinese",
    "CHINA": "Chinese",
    "CHN": "Chinese",
    "REPUBLIC OF CHINA": "Chinese",
    # ── New Zealander ──
    "New Zealander": "New Zealander",
    "New Zealand": "New Zealander",
    "NEW ZEALAND": "New Zealander",
    # ── Portuguese ──
    "Portuguese": "Portuguese",
    "PORTUGUESA": "Portuguese",
    # ── Malaysian ──
    "Malaysian": "Malaysian",
    "MALAYSIA": "Malaysian",
    # ── Mexican ──
    "Mexican": "Mexican",
    # ── Norwegian ──
    "Norwegian": "Norwegian",
    # ── Polish ──
    "Polish": "Polish",
    "POLANDIA": "Polish",
    # ── Filipino ──
    "Filipino": "Filipino",
    # ── Argentinian ──
    "Argentinian": "Argentinian",
    "Argentina": "Argentinian",
    "ARGENTINA": "Argentinian",
    # ── Czech ──
    "Czech": "Czech",
    "CZECH REPUBLIC": "Czech",
    "REPUBLIK CEKO": "Czech",
    # ── Moroccan ──
    "Moroccan": "Moroccan",
    "Morocco": "Moroccan",
    # ── Colombian ──
    "Colombian": "Colombian",
    # ── Greek ──
    "Greek": "Greek",
    "HELLENIC": "Greek",
    # ── Finnish ──
    "Finnish": "Finnish",
    "FIN": "Finnish",
    # ── Israeli ──
    "Israeli": "Israeli",
    # ── Korean ──
    "Korean": "Korean",
    "KOR": "Korean",
    "REPUBLIC OF KOREA": "Korean",
    # ── Japanese ──
    "Japanese": "Japanese",
    "Japan": "Japanese",
    "JAPAN": "Japanese",
    "JPN": "Japanese",
    "JEPANG": "Japanese",
    # ── Vietnamese ──
    "Vietnamese": "Vietnamese",
    # ── Saudi ──
    "Saudi": "Saudi",
    "SAUDI ARABIA": "Saudi",
    # ── Canadian ──
    "Canadian": "Canadian",
    "CANADIAN": "Canadian",
    "Canada": "Canadian",
    "CANADA": "Canadian",
    "CANADIAN/CANADIENNE": "Canadian",
    "NEGARA CANADA": "Canadian",
    # ── Irish ──
    "Irish": "Irish",
    "IRISH": "Irish",
    "IRL": "Irish",
    "IRELAND": "Irish",
    # ── Romanian ──
    "Romanian": "Romanian",
    "ROMÂNĂ": "Romanian",
    "NEGARA: ROMANIA": "Romanian",
    # ── Algerian ──
    "Algerian": "Algerian",
    "ALGERIENNE": "Algerian",
    # ── Belarusian ──
    "Belarusian": "Belarusian",
    "Belarus": "Belarusian",
    "BELARUS": "Belarusian",
    # ── Egyptian ──
    "Egyptian": "Egyptian",
    "Egypt": "Egyptian",
    # ── Lebanese ──
    "Lebanese": "Lebanese",
    "Lebanon": "Lebanese",
    # ── Ghanaian ──
    "GHANA": "Ghanaian",
    # ── Venezuelan ──
    "VEN": "Venezuelan",
    "VENEZUELA": "Venezuelan",
    # ── Taiwanese ──
    "TAIWAN": "Taiwanese",
    # ── Salvadoran ──
    "EL SALVADOR": "Salvadoran",
    # ── Nicaraguan ──
    "NICARAGUA": "Nicaraguan",
    # ── Turkish ──
    "TUR": "Turkish",
    # ── Lithuanian ──
    "Lithuanian": "Lithuanian",
    # ── Estonian ──
    "Estonian": "Estonian",
    # ── Nepalese ──
    "NEPALESE": "Nepalese",
    # ── Syrian ──
    "SYRIA": "Syrian",
    "SYRIAN ARAB REPUBLIC": "Syrian",
    # ── Ethiopian ──
    "ETHIOPIAN": "Ethiopian",
    # ── Armenian ──
    "Armenia": "Armenian",
    "ARMENIA": "Armenian",
    # ── Maltese ──
    "Maltese": "Maltese",
    # ── Cypriot ──
    "Cypriot": "Cypriot",
    # ── Tajik ──
    "Tajikistan": "Tajik",
    # ── Turkmen ──
    "TURKMENISTAN": "Turkmen",
    # ── Azerbaijani ──
    "AZERBAIJAN": "Azerbaijani",
    # ── Kazakh ──
    "Kazakhstan": "Kazakh",
    # ── Kyrgyz ──
    "Kyrgyz Republic": "Kyrgyz",
    "KGZ": "Kyrgyz",
    # ── Hong Kong ──
    "HONG KONG": "Hong Konger",
    # ── Serbian ──
    "SRB": "Serbian",
    # ── Garbage → NULL ──
    "NEGARA: -": None,
    "NEGARA: TTL:-": None,
    "NEGERI ASING": None,
    "NEGARAI": None,
    "NEGERA": None,
    "KUTA": None,
    "BALIKPAPAN": None,
    "other": None,
}

DB_URL = "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag"


async def run(dry_run: bool = True) -> None:
    conn = await asyncpg.connect(DB_URL)
    try:
        # Fetch all distinct nationality values
        rows = await conn.fetch(
            "SELECT DISTINCT nationality FROM clients WHERE nationality IS NOT NULL AND nationality != ''"
        )

        updates: list[tuple[str | None, str]] = []  # (new_value, old_value)
        unmapped: list[str] = []

        for row in rows:
            old = row["nationality"]
            if old in NATIONALITY_MAP:
                new = NATIONALITY_MAP[old]
                if new != old:
                    updates.append((new, old))
            else:
                unmapped.append(old)

        print(f"\n{'=' * 60}")
        print(f"Nationality Normalization {'(DRY RUN)' if dry_run else '(APPLYING)'}")
        print(f"{'=' * 60}")
        print(f"Total distinct values:  {len(rows)}")
        print(f"Will update:            {len(updates)}")
        print(f"Already canonical:      {len(rows) - len(updates) - len(unmapped)}")
        print(f"Unmapped (skipped):     {len(unmapped)}")

        if unmapped:
            print("\nUnmapped values (add to NATIONALITY_MAP):")
            for v in sorted(unmapped):
                cnt = await conn.fetchval(
                    "SELECT COUNT(*) FROM clients WHERE nationality = $1", v
                )
                print(f"  '{v}' ({cnt} clients)")

        if updates:
            print("\nUpdates to apply:")
            for new, old in sorted(updates, key=lambda x: x[1]):
                cnt = await conn.fetchval(
                    "SELECT COUNT(*) FROM clients WHERE nationality = $1", old
                )
                target = new if new else "NULL"
                print(f"  '{old}' → '{target}' ({cnt} clients)")

        if not dry_run and updates:
            print(f"\nApplying {len(updates)} updates...")
            async with conn.transaction():
                total_affected = 0
                for new, old in updates:
                    if new is None:
                        result = await conn.execute(
                            "UPDATE clients SET nationality = NULL WHERE nationality = $1",
                            old,
                        )
                    else:
                        result = await conn.execute(
                            "UPDATE clients SET nationality = $1 WHERE nationality = $2",
                            new,
                            old,
                        )
                    affected = int(result.split()[-1])
                    total_affected += affected
                print(f"Done. {total_affected} rows updated.")

            # Verify
            remaining = await conn.fetchval(
                "SELECT COUNT(DISTINCT nationality) FROM clients WHERE nationality IS NOT NULL"
            )
            print(f"Distinct nationalities after: {remaining}")
        elif not dry_run:
            print("\nNo updates needed.")
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Normalize client nationalities")
    parser.add_argument(
        "--apply", action="store_true", help="Apply changes (default is dry-run)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would change without applying",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(dry_run=not args.apply))
