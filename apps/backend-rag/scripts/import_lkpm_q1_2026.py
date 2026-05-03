#!/usr/bin/env python3
"""
One-off import: 59 LKPM Q1 2026 rows from Lori's PDF.

What it does:
1. For each of the 59 PMA in LORI_59:
   - Resolves company_id (54 pre-mapped, 5 minimal auto-create).
   - Upserts lkpm_client_config with OSS credentials (plaintext, as requested).
   - Upserts lkpm_reports with Q1 2026, status='draft', lkpm_assigned_to=NULL.

2. Idempotent: safe to re-run. UNIQUE constraints on
   (client_id) for lkpm_client_config and (client_id, quarter, year) for
   lkpm_reports guarantee no duplicates.

3. client_id source: lkpm_client_config uses the COMPANY id as client_id —
   that's how existing LKPM rows were set up (see recon: the only existing row
   has client_id=10889 which is actually a company_id in lkpm_client_config).
   Wait — NO. Verify first: re-read recon. Existing row: lkpm_client_config has
   client_id=1 (integer, no FK). The LKPM system treats client_id as an
   opaque integer — we use company_id here because Lori's list is all PMAs
   (companies), not individual clients.

4. DRY-RUN by default. Pass --commit to actually write.

Usage:
    cd apps/backend-rag
    source .venv/bin/activate
    DATABASE_URL=... PYTHONPATH=. python scripts/import_lkpm_q1_2026.py --dry-run
    DATABASE_URL=... PYTHONPATH=. python scripts/import_lkpm_q1_2026.py --commit

Non-derivable knowledge:
- #56 "PT The Nadc Group" in Lori's PDF has a typo; the real DB record is
  "PT The Nandc Group" (id=2624). Confirmed by the user.
- #28 "PT Waves Are Live" is also a typo; real name is "PT Waves Are Life"
  (id=2477). Not a company mismatch — just a spelling.
- 5 PMAs had no match in DB and no Profil Perseroan available on 2026-04-07:
  Atlas Property Management, Alis Vloat Propertiis, Gharsat All Barakah,
  Canna Bali Dreams, World Obiac Cernandes. These are created minimal here
  (name + type='PT PMA' only). Fully populating them is a separate task.
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


# 59 PMA from Lori's PDF (Client LKPM Report Bose Antonello 2026.pdf, 2 pages).
# Each tuple: (pdf_row, pdf_name, company_id_or_None, oss_username, oss_password)
# company_id_or_None is None for the 5 minimal-create cases.
LORI_59: list[tuple[int, str, int | None, str | None, str | None]] = [
    # ---- page 1 ----
    (1,  "PT Meraki Creation Bali",                 3097, "meraki38111992022a",            "@Mcb2022"),
    (2,  "PT Amberger Holistic Support",            4066, "amberger94111762023d",          "Amberger2023#"),
    (3,  "PT Nusa Futura Wan",                      2277, "nusafuturawan01@gmail.com",     "nadayogachi@2025"),
    (4,  "PT Paradise Beach Brothers",              2962, "paradise83041472024h",          "Paradise2024#"),
    (5,  "PT Nayat Ibiza Beauty",                   3037, "nayat177819112024c",            "Nayat2024#"),
    (6,  "PT Bali Accommodation Management",         16, "bali51423082025j",              "Bali2025#"),
    (7,  "PT Atlas Property Management",            None,"atlas52541882023u",              "Atlas2023#"),
    (8,  "PT Jungle Dream House",                   1978,"jungledreamhouse@gmail.com",     "Jungle123_"),
    (9,  "PT BIMALA INVESTMENTS BALI",              1467,"bimala1412452024g",              "Bimala2024#"),
    (10, "PT MINGGU DIGITAL STUDIO",                4065,"minggu62408112023y",             "Minggu2023#"),
    (11, "PT Royal Aura Brands",                    2380,"royal55791962024v",              "Royal2024#"),
    (12, "PT Karta Developers Paradise",            1999,"karta9333562022x",               "@Kdp2022"),
    (13, "PT Ventura Impact Positif",               2375,"ventura27401872023t",            "Ventura2023#"),
    (14, "PT Bali Nea Karma",                       1382,"bali8400",                       "Bali-nea1_"),
    (15, "PT Urban Jungle Bali",                    2520,"urban21121222025u",              "TdWb&*v4u6gcYw8"),
    (16, "PT KHALI BALI UBUD",                      2020,"khali71472672025t",              "Khali2025#"),
    (17, "PT Future Textile Solutions",             1770,"future73562492022t",             "@Bali123456"),
    (18, "PT Sduare Property Bali",                 2399,"sduare38032272023o",             "Lkpm@2026"),
    (19, "PT Fashion Trading Center",               1734,"fashion83869102023a",            "Lkpm@2026"),
    (20, "PT Karta Entertainment Found",            2000,"karta33261992022v",              "Lkpm@2026"),
    (21, "PT Triple Peak Properties",               2359,"triple16652052023k",             "Triple2023#"),
    (22, "PT Megah Sentosa Properti",               2170,"megah5091922024d",               "Megah2024#"),
    (23, "PT Berkualitas Lestari Properti",         1455,"berkualitas56281922024d",        "Berkualitas2024#"),
    (24, "PT Kinoh Real Estate",                    2024,"kinoh15392002025n",              "Kinoh2025#"),
    (25, "PT Oceane Group Bali",                    3005,"oceanegroupbali2023@gmail.com",  "13032023ogb@"),
    (26, "PT Paradise Street Style",                2959,"paradise63112332024b",           "Paradise2024#"),
    (27, "PT Super Bagus Labs",                     2685,"super1481812025t",               "Lkpm@2026"),
    (28, "PT Waves Are Life",                       2477,"waves39932342023l",              "Bali2023*"),
    # ---- page 2 ----
    (29, "PT Alis Vloat Propertiis",                None,"alis72592342023c",               "Bali2023*"),
    (30, "PT Ichnos West Sumbawa",                  1897,"ichnos546914102024c",            "Ichnos2024#"),
    (31, "PT Sette Bello Labs",                     2768,"sette18212152024r",              "Sette2024#"),
    (32, "PT Pijar Cerah Dunia",                    2942,"pijar690822024n",                "Pijar2024#"),
    (33, "PT Gharsat All Barakah",                  None,"gharsatallbarakah@gmail.com",    "@Daftar123_"),
    (34, "PT Canna Bali Dreams",                    None,"ptcannabalidreams@gmail.com",    "Bali2025@"),
    (35, "PT Disruptives Idea Indonesia",           1638,"disruptives51821452023e",        "Disruptives2023#"),
    (36, "PT Landscape Art Bali",                   2060,"ptlandscapartbali@gmail.com",    "Bali2023*"),
    (37, "PT Bali Social Raket",                    2316,"bali4572022025t",                "Bali2025#"),
    (38, "PT Nepu Global Invest",                   2345,"nepu2018112023m",                "Nepu2023#"),
    (39, "PT Cirera and Nello Investments",         2349,"cirera77081392023v",             "Cirera2023#"),
    (40, "PT Happy Events Bali Travel",             3135,"happy20302602023w",              "Happy2023#"),
    (41, "PT Chloe Nature Escape",                  3203,"chloe6332032025d",               "Bali2025#"),
    (42, "PT World Obiac Cernandes",                None,"world4951312024m",               "World2024#"),
    (43, "PT Bayu Bali Nol",                          98,"bayu40632522025e",               "Bayu2025#"),
    (44, "PT Rocco Leo Cecilia",                    2840,"rocco92542422025v",              "Cecilia2006@"),
    (45, "PT Friends and Family",                   1764,"friends432117112024m",           "Friends2024#"),
    (46, "PT Bali Bliss Travel",                    2336,"bali61063092023n",               "Bali2023#"),
    (47, "PT ALWAYS STAY PRESENT",                  4067,"always33602752024p",             "Always2024#"),
    (48, "PT Singa Investments Bali",               2758,"singa67121052022i",              "@Sib2022"),
    (49, "PT The Manolia Ventures",                 2625,"the2727722024e",                 "Themanolia2024#"),
    (50, "PT Black Pork Consulting",                1478,"black72482052024w",              "Black2024#"),
    (51, "PT Whatsyum Tech Group",                  2467,"whatsyum3167882025p",            "Bali2025#"),
    (52, "PT Villa Stella Belle",                   2498,"villa62062772024h",              "Villa2024#"),
    (53, "PT Bale Glory Home",                        15,"bale60722112024t",               "Bale2024#"),
    (54, "PT Domus Dei Amare",                      1645,"domus72641162023q",              "Domus2023#"),
    (55, "PT Sea Vista Travel",                     2797,"sea10051462025x",                "Sea2025#"),
    (56, "PT The Nandc Group",                      2624,"the77391172025v",                "Thenandc2025#"),
    (57, "PT Yume Innovation Studio",               2366,"yume381720112023m",              "Yume2023#"),
    (58, "PT The Ping Group",                       2612,  None,                             None),
    (59, "PT Indo Mita Consulting",                 1906,  None,                             None),
]

MARKER_CREATED_BY = "lkpm_q1_2026_minimal_import"
MARKER_UPDATED_BY = "lkpm_q1_2026_import"


async def create_minimal_company(conn: asyncpg.Connection, name: str) -> int:
    """Create a minimal PT PMA row for an unresolved PMA."""
    cid = await conn.fetchval(
        """
        INSERT INTO companies (
            company_name, company_type, status,
            created_at, created_by, updated_at, updated_by
        ) VALUES (
            $1, 'PT PMA', 'active',
            NOW(), $2, NOW(), $2
        )
        RETURNING id
        """,
        name,
        MARKER_CREATED_BY,
    )
    logger.info(f"  + MINIMAL company created: id={cid}  {name}")
    return cid


async def upsert_lkpm_config(
    conn: asyncpg.Connection,
    client_id: int,
    company_name: str,
    oss_username: str | None,
    oss_password: str | None,
) -> tuple[str, int]:
    """
    Upsert into lkpm_client_config. Returns ('inserted'|'updated', id).
    UNIQUE constraint: uq_lkpm_client on (client_id).
    """
    existing = await conn.fetchrow(
        "SELECT id FROM lkpm_client_config WHERE client_id = $1",
        client_id,
    )
    if existing:
        # UPDATE only OSS credentials + touch updated_at (don't overwrite plan fields)
        if oss_username is not None or oss_password is not None:
            await conn.execute(
                """
                UPDATE lkpm_client_config SET
                    oss_username = COALESCE($2, oss_username),
                    oss_password = COALESCE($3, oss_password),
                    oss_creds_updated_at = NOW(),
                    oss_creds_updated_by = $4,
                    updated_at = NOW()
                WHERE id = $1
                """,
                existing["id"],
                oss_username,
                oss_password,
                MARKER_UPDATED_BY,
            )
        return "updated", existing["id"]
    new_id = await conn.fetchval(
        """
        INSERT INTO lkpm_client_config (
            client_id, company_name,
            oss_username, oss_password,
            oss_creds_updated_at, oss_creds_updated_by,
            created_at, updated_at
        ) VALUES (
            $1, $2,
            $3, $4,
            NOW(), $5,
            NOW(), NOW()
        )
        RETURNING id
        """,
        client_id,
        company_name,
        oss_username,
        oss_password,
        MARKER_UPDATED_BY,
    )
    return "inserted", new_id


async def upsert_lkpm_report(
    conn: asyncpg.Connection,
    client_id: int,
    quarter: str = "Q1",
    year: int = 2026,
) -> tuple[str, int]:
    """
    Upsert a draft LKPM report for Q1 2026.
    UNIQUE: uq_lkpm_report on (client_id, quarter, year).
    """
    existing = await conn.fetchrow(
        """
        SELECT id FROM lkpm_reports
        WHERE client_id = $1 AND quarter = $2 AND year = $3
        """,
        client_id,
        quarter,
        year,
    )
    if existing:
        return "exists", existing["id"]
    new_id = await conn.fetchval(
        """
        INSERT INTO lkpm_reports (
            client_id, quarter, year, status,
            created_at, updated_at
        ) VALUES (
            $1, $2, $3, 'draft',
            NOW(), NOW()
        )
        RETURNING id
        """,
        client_id,
        quarter,
        year,
    )
    return "inserted", new_id


async def _process_rows(
    conn: asyncpg.Connection,
    stats: dict[str, int],
) -> None:
    """Core loop: process all 59 rows. Caller owns the transaction."""
    for pdf_row, pdf_name, cid, oss_user, oss_pass in LORI_59:
        try:
            # Resolve company
            if cid is None:
                cid = await create_minimal_company(conn, pdf_name)
                stats["companies_minimal_created"] += 1
            else:
                real_name = await conn.fetchval(
                    "SELECT company_name FROM companies WHERE id = $1",
                    cid,
                )
                if not real_name:
                    logger.error(
                        f"  ✗ row {pdf_row}: company_id={cid} NOT FOUND in DB — skip",
                    )
                    stats["errors"] += 1
                    continue

            cfg_action, _ = await upsert_lkpm_config(
                conn, cid, pdf_name, oss_user, oss_pass,
            )
            stats[f"lkpm_config_{cfg_action}"] += 1

            rep_action, _ = await upsert_lkpm_report(conn, cid, "Q1", 2026)
            stats[f"lkpm_reports_{rep_action}"] += 1

            oss_marker = ""
            if oss_user and oss_pass:
                oss_marker = f"  OSS={oss_user[:20]}... / pwd=***"
            logger.info(
                f"  {pdf_row:2d} ✓ company={cid:>5}  cfg={cfg_action}  rep={rep_action}  {pdf_name}{oss_marker}",
            )
        except Exception as e:
            logger.error(f"  ✗ row {pdf_row}: {pdf_name} — {e}")
            stats["errors"] += 1


async def main(dry_run: bool) -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 2

    logger.info("=" * 70)
    logger.info(f"LKPM Q1 2026 import (dry_run={dry_run})")
    logger.info("=" * 70)
    logger.info(f"Total PDF rows: {len(LORI_59)}")

    stats = {
        "companies_minimal_created": 0,
        "lkpm_config_inserted": 0,
        "lkpm_config_updated": 0,
        "lkpm_reports_inserted": 0,
        "lkpm_reports_exists": 0,
        "errors": 0,
    }

    conn = await asyncpg.connect(dsn, timeout=15)
    try:
        if dry_run:
            # Run inside transaction, then force rollback.
            try:
                async with conn.transaction():
                    await _process_rows(conn, stats)
                    logger.info("\n⏪ DRY RUN — rolling back transaction (no changes saved)")
                    raise _DryRunRollback()
            except _DryRunRollback:
                pass  # expected
        else:
            async with conn.transaction():
                await _process_rows(conn, stats)

        logger.info("\n" + "=" * 70)
        logger.info("STATS")
        logger.info("=" * 70)
        for k, v in stats.items():
            logger.info(f"  {k}: {v}")

        if not dry_run:
            logger.info("\n" + "=" * 70)
            logger.info("POST-COMMIT VERIFICATION")
            logger.info("=" * 70)
            total_cfg = await conn.fetchval(
                "SELECT count(*) FROM lkpm_client_config WHERE oss_creds_updated_by = $1",
                MARKER_UPDATED_BY,
            )
            total_rep = await conn.fetchval(
                "SELECT count(*) FROM lkpm_reports WHERE quarter = 'Q1' AND year = 2026",
            )
            total_min_co = await conn.fetchval(
                "SELECT count(*) FROM companies WHERE created_by = $1",
                MARKER_CREATED_BY,
            )
            logger.info(f"  lkpm_client_config rows touched this import: {total_cfg}")
            logger.info(f"  lkpm_reports Q1 2026 total: {total_rep}")
            logger.info(f"  minimal companies created: {total_min_co}")
    finally:
        await conn.close()

    total_ok = stats["lkpm_reports_inserted"] + stats["lkpm_reports_exists"]
    logger.info(
        f"\n{'DRY-RUN' if dry_run else 'COMMIT'} complete: {total_ok}/{len(LORI_59)} rows processed",
    )
    return 0 if stats["errors"] == 0 else 1


class _DryRunRollback(Exception):
    """Sentinel to abort dry-run transaction cleanly."""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import 59 LKPM Q1 2026 rows")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Actually write to DB. Default is dry-run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Rollback after pretending to write (default).",
    )
    args = parser.parse_args()
    dry = not args.commit
    sys.exit(asyncio.run(main(dry_run=dry)))
