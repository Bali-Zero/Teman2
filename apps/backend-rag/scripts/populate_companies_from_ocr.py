"""
Populate Companies from OCR — Step 2+3
=======================================
For each company with completed OCR:
  Step 2: Update companies table fields from ocr_extracted_data
  Step 3: Match directors/commissioners → clients, create client_company_links

Run:
    python3 scripts/populate_companies_from_ocr.py [--dry-run] [--limit N]
"""

import argparse
import asyncio
import json
import logging
import os
import re
from datetime import date as dt_date
from typing import Any

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB = (
    os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://")
    or "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag?sslmode=disable"
)


async def merge_custom_fields(
    conn: asyncpg.Connection, company_id: int, new_fields: dict, dry_run: bool
) -> bool:
    current = await conn.fetchval("SELECT custom_fields FROM companies WHERE id = $1", company_id)
    existing = {}
    if current:
        if isinstance(current, str):
            try:
                parsed = json.loads(current)
                existing = parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                existing = {}
        elif isinstance(current, dict):
            existing = current

    added = {}
    for k, v in new_fields.items():
        if k not in existing or not existing[k]:
            added[k] = v

    if not added:
        return False

    merged = {**existing, **added}
    if not dry_run:
        await conn.execute(
            "UPDATE companies SET custom_fields = $1::jsonb, updated_at = NOW() WHERE id = $2",
            json.dumps(merged),
            company_id,
        )
    for k, v in added.items():
        logger.info(f"    → custom_fields.{k} = {str(v)[:60]}")
    return True


async def update_company_fields(conn: asyncpg.Connection, company_id: int, dry_run: bool) -> dict:
    stats = {"fields_updated": 0, "directors_linked": 0}

    docs = await conn.fetch(
        """
        SELECT id, document_type, file_name, ocr_extracted_data
        FROM company_documents
        WHERE company_id = $1 AND ocr_status = 'completed' AND ocr_extracted_data IS NOT NULL
    """,
        company_id,
    )

    if not docs:
        return stats

    akta: dict = {}
    nib: dict = {}
    npwp: dict = {}
    sk: dict = {}
    profile: dict = {}

    for doc in docs:
        ocr = doc["ocr_extracted_data"]
        if isinstance(ocr, str):
            try:
                ocr = json.loads(ocr)
            except json.JSONDecodeError:
                continue
        if not isinstance(ocr, dict):
            continue

        dtype = (doc["document_type"] or "").lower()
        fname = (doc["file_name"] or "").lower()

        if "akta" in dtype or "akta" in fname:
            akta = {**akta, **ocr}
        elif "nib" in dtype or "nib" in fname:
            nib = {**nib, **ocr}
        elif "npwp" in dtype or "npwp" in fname:
            npwp = {**npwp, **ocr}
        elif "sk" in dtype or "sk" in fname:
            sk = {**sk, **ocr}
        elif "profil" in fname or "profile" in fname:
            profile = {**profile, **ocr}
        else:
            profile = {**profile, **ocr}

    async def set_if_null(col: str, val: Any, is_date: bool = False) -> bool:
        if not val or val == "YYYY-MM-DD" or val == "":
            return False
        val = str(val).strip()
        if not val:
            return False
        current = await conn.fetchval(f"SELECT {col} FROM companies WHERE id = $1", company_id)
        if current is not None and str(current).strip():
            return False
        try:
            if is_date:
                try:
                    d = dt_date.fromisoformat(val)
                    if not dry_run:
                        await conn.execute(
                            f"UPDATE companies SET {col} = $1, updated_at = NOW() WHERE id = $2",
                            d,
                            company_id,
                        )
                    logger.info(f"    → {col} = {val}")
                    return True
                except ValueError:
                    return False
            else:
                if not dry_run:
                    await conn.execute(
                        f"UPDATE companies SET {col} = $1, updated_at = NOW() WHERE id = $2",
                        val,
                        company_id,
                    )
                logger.info(f"    → {col} = {val}")
                return True
        except asyncpg.exceptions.UniqueViolationError:
            logger.warning(f"    ⚠ {col} = {val} already exists on another company")
            return False

    # AKTA
    if akta:
        if await set_if_null("akta_pendirian_no", akta.get("deed_number")):
            stats["fields_updated"] += 1
        if await set_if_null("akta_pendirian_date", akta.get("deed_date"), is_date=True):
            stats["fields_updated"] += 1
        if await set_if_null(
            "registered_address",
            akta.get("registered_address") or akta.get("Alamat") or akta.get("address"),
        ):
            stats["fields_updated"] += 1
        extra = {}
        cap = akta.get("authorized_capital") or akta.get("Modal Dasar")
        if cap and str(cap) != "0":
            extra["authorized_capital"] = str(cap)
        paid = akta.get("paid_capital") or akta.get("Modal Disetor")
        if paid and str(paid) != "0":
            extra["paid_up_capital"] = str(paid)
        status = akta.get("company_status") or akta.get("Status Perseroan")
        if status:
            extra["company_status"] = str(status)
        if extra:
            if await merge_custom_fields(conn, company_id, extra, dry_run):
                stats["fields_updated"] += len(extra)

    # NIB
    if nib:
        nib_num = nib.get("nib_number") or nib.get("Nomor Induk Berusaha")
        if nib_num:
            if await set_if_null("nib", str(nib_num)):
                stats["fields_updated"] += 1
        kbli = nib.get("kbli_codes") or nib.get("Kode/ Nama KBLI")
        if kbli:
            if isinstance(kbli, list):
                codes = []
                for k in kbli:
                    if isinstance(k, dict):
                        c = k.get("code") or k.get("kode") or ""
                        if c:
                            codes.append(str(c))
                    elif k:
                        codes.append(str(k))
                kbli_str = ", ".join(codes) if codes else ""
            else:
                kbli_str = str(kbli)
            if kbli_str:
                if await set_if_null("kbli_code", kbli_str):
                    stats["fields_updated"] += 1
        pma = nib.get("pma_status")
        if pma:
            if await merge_custom_fields(conn, company_id, {"investment_type": pma}, dry_run):
                stats["fields_updated"] += 1

    # NPWP
    if npwp:
        npwp_num = npwp.get("npwp_number") or npwp.get("NPWP")
        if npwp_num:
            if await set_if_null("npwp_company", str(npwp_num)):
                stats["fields_updated"] += 1
        kpp = npwp.get("kpp_office")
        if kpp:
            if await merge_custom_fields(conn, company_id, {"tax_office": kpp}, dry_run):
                stats["fields_updated"] += 1

    # SK
    if sk:
        sk_num = sk.get("sk_number")
        if sk_num:
            if await set_if_null("sk_menhumkam_no", sk_num):
                stats["fields_updated"] += 1
        sk_date = sk.get("issue_date")
        if sk_date:
            if await set_if_null("sk_menhumkam_date", sk_date, is_date=True):
                stats["fields_updated"] += 1

    # Profile
    if profile:
        email = (
            profile.get("email")
            or profile.get("Official Email")
            or profile.get("Email")
            or profile.get("company_email")
        )
        if email and "@" in str(email):
            if await set_if_null("company_email", str(email)):
                stats["fields_updated"] += 1
        phone = (
            profile.get("phone")
            or profile.get("Nomor Telepon")
            or profile.get("phone_number")
            or profile.get("company_phone")
        )
        if phone:
            if await set_if_null("company_phone", str(phone)):
                stats["fields_updated"] += 1
        addr = profile.get("address") or profile.get("Alamat") or profile.get("registered_address")
        if addr:
            if await set_if_null("registered_address", str(addr)):
                stats["fields_updated"] += 1

    # Step 3: Link directors/commissioners/shareholders
    directors = profile.get("directors", []) or akta.get("directors", [])
    commissioners = profile.get("commissioners", []) or akta.get("commissioners", [])
    shareholders = profile.get("shareholders", [])

    for person in directors:
        if isinstance(person, dict):
            name = person.get("name", "").strip()
            pct = person.get("ownership_pct", 0)
            if name and len(name) > 2:
                linked = await link_person_to_company(
                    conn, company_id, name, "director", pct, dry_run
                )
                if linked:
                    stats["directors_linked"] += 1

    for person in commissioners:
        if isinstance(person, dict):
            name = person.get("name", "").strip()
            pct = person.get("ownership_pct", 0)
            if name and len(name) > 2:
                linked = await link_person_to_company(
                    conn, company_id, name, "commissioner", pct, dry_run
                )
                if linked:
                    stats["directors_linked"] += 1

    for person in shareholders:
        if isinstance(person, dict):
            name = person.get("name", "").strip()
            pct = person.get("ownership_pct", 0)
            if name and len(name) > 2:
                linked = await link_person_to_company(
                    conn, company_id, name, "shareholder", pct, dry_run
                )
                if linked:
                    stats["directors_linked"] += 1

    return stats


async def link_person_to_company(conn, company_id, person_name, role, ownership_pct, dry_run):
    name = re.sub(r"\s+", " ", person_name).strip()

    client_id = await conn.fetchval(
        "SELECT id FROM clients WHERE LOWER(TRIM(full_name)) = LOWER(TRIM($1)) AND deleted_at IS NULL LIMIT 1",
        name,
    )

    if not client_id:
        parts = name.split()
        if len(parts) >= 2:
            client_id = await conn.fetchval(
                "SELECT id FROM clients WHERE LOWER(full_name) LIKE $1 AND LOWER(full_name) LIKE $2 AND deleted_at IS NULL LIMIT 1",
                f"%{parts[0].lower()}%",
                f"%{parts[-1].lower()}%",
            )

    if not client_id and len(name.split()) >= 2:
        last = name.split()[-1].lower()
        if len(last) >= 4:
            client_id = await conn.fetchval(
                "SELECT id FROM clients WHERE LOWER(full_name) LIKE $1 AND deleted_at IS NULL LIMIT 1",
                f"%{last}%",
            )

    if not client_id:
        return False

    existing = await conn.fetchval(
        "SELECT id FROM client_company_links WHERE client_id = $1 AND company_id = $2",
        client_id,
        company_id,
    )

    if existing:
        if not dry_run:
            await conn.execute(
                "UPDATE client_company_links SET role = $1, ownership_percentage = $2, updated_at = NOW() WHERE id = $3",
                role,
                ownership_pct if ownership_pct else None,
                existing,
            )
        logger.info(f"    ↻ Updated: client {client_id} → company {company_id} ({role})")
        return True
    else:
        if not dry_run:
            await conn.execute(
                """INSERT INTO client_company_links (client_id, company_id, role, ownership_percentage, status, created_at)
                   VALUES ($1, $2, $3, $4, 'active', NOW()) ON CONFLICT DO NOTHING""",
                client_id,
                company_id,
                role,
                ownership_pct if ownership_pct else None,
            )
        logger.info(f"    + Linked: client {client_id} → company {company_id} ({role})")
        return True


async def main(dry_run: bool, limit: int, start_id: int = 0) -> None:
    logger.info(f"{'DRY RUN — ' if dry_run else ''}Populate Companies from OCR (Step 2+3)")
    pool = await asyncpg.create_pool(DB, min_size=1, max_size=5, command_timeout=60)

    try:
        async with pool.acquire() as conn:
            companies = await conn.fetch(
                """
                SELECT c.id, c.company_name,
                       count(*) FILTER (WHERE LOWER(cd.file_name) LIKE '%.pdf'
                           AND (LOWER(cd.file_name) LIKE '%akta%' OR LOWER(cd.file_name) LIKE '%sk%'
                                OR LOWER(cd.file_name) LIKE '%nib%' OR LOWER(cd.file_name) LIKE '%npwp%'
                                OR LOWER(cd.file_name) LIKE '%profil%perseroan%' OR LOWER(cd.file_name) LIKE '%passport%')) as relevant,
                       count(*) FILTER (WHERE cd.ocr_status = 'completed') as done
                FROM companies c
                JOIN company_documents cd ON cd.company_id = c.id
                GROUP BY c.id, c.company_name
                HAVING count(*) FILTER (WHERE LOWER(cd.file_name) LIKE '%.pdf'
                           AND (LOWER(cd.file_name) LIKE '%akta%' OR LOWER(cd.file_name) LIKE '%sk%'
                                OR LOWER(cd.file_name) LIKE '%nib%' OR LOWER(cd.file_name) LIKE '%npwp%'
                                OR LOWER(cd.file_name) LIKE '%profil%perseroan%' OR LOWER(cd.file_name) LIKE '%passport%')) > 0
                ORDER BY c.id
                LIMIT $1
            """,
                limit,
            )
        # Filter by start_id if provided (resume support)
        if start_id > 0:
            companies = [c for c in companies if c["id"] >= start_id]
            logger.info(f"Resuming from company_id >= {start_id}")

        logger.info(f"Found {len(companies)} fully OCR'd companies")

        totals = {"fields": 0, "directors": 0, "companies": 0}

        for co in companies:
            cid = co["id"]
            cname = co["company_name"]
            logger.info(f"\n📂 [{cid}] {cname} ({co['done']} docs)")

            # Acquire a fresh connection per company to avoid long-lived connection timeouts
            async with pool.acquire() as fresh_conn:
                try:
                    stats = await update_company_fields(fresh_conn, cid, dry_run)
                    totals["fields"] += stats["fields_updated"]
                    totals["directors"] += stats["directors_linked"]
                    if stats["fields_updated"] > 0 or stats["directors_linked"] > 0:
                        totals["companies"] += 1
                except Exception as e:
                    logger.warning(f"  ⚠️ Skipped [{cid}] {cname}: {e}")

        logger.info("\n=== SUMMARY ===")
        logger.info(f"  Companies processed : {len(companies)}")
        logger.info(f"  Companies updated   : {totals['companies']}")
        logger.info(f"  Fields populated    : {totals['fields']}")
        logger.info(f"  Directors linked    : {totals['directors']}")
        if dry_run:
            logger.info("  (DRY RUN)")

    finally:
        await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--start-id", type=int, default=0, help="Resume from company_id >= N")
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run, limit=args.limit, start_id=args.start_id))
