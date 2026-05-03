"""
Update Master Google Sheet from OCR data — Step 4
==================================================
Reads OCR data from DB, maps to 19 fields (D-V), writes to Master Sheet.
Only fills empty cells — never overwrites existing data.

Column mapping (D-V):
  D  = Legal Address (registered_address from AKTA or profile)
  E  = NIB
  F  = NPWP
  G  = KBLI codes
  H  = Director 1 name
  I  = Director 1 ownership %
  J  = Commissioner 1 name  ← ONLY from Profil Perseroan, not AKTA
  K  = Commissioner 1 ownership %
  L  = Investor name (shareholder with PT/CV prefix)
  M  = Investor ownership %
  N  = Authorized Capital
  O  = Deed Date (akta date or SK issue_date)
  P  = Email
  Q  = Phone
  R  = SK Number (Kemenkumham)
  S  = Tax Office KPP (from NPWP doc)
  T  = Company Status (TERTUTUP / TERBUKA)
  U  = PMA / PMDN (investment type from NIB)
  V  = Office Type (always "Virtual Office - Jalan Raya Anyar Gg. 3, No. 2")

Run:
    python3 scripts/update_master_sheet.py [--dry-run] [--limit N]
"""

import argparse
import asyncio
import json
import logging
import os
from typing import Any

import asyncpg
from google.oauth2 import service_account
from googleapiclient.discovery import build

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

DB = (
    os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://")
    or "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag?sslmode=disable"
)

SHEET_ID = "1CcsZmYOiajdWtTlgmoHNeCqBXhbLRZrQVQOBRs422oY"
SHEET_NAME = "Company"
DATA_START_ROW = 10
OFFICE_TYPE_VALUE = "Virtual Office - Jalan Raya Anyar Gg. 3, No. 2"

SA_KEY_PATH = os.getenv(
    "GOOGLE_SA_KEY", "/Users/antonellosiano/Downloads/nuzantara-google-drive-sa-key-20260312.json"
)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_sheets_service = None


def get_sheets():
    global _sheets_service
    if _sheets_service is None:
        creds = service_account.Credentials.from_service_account_file(SA_KEY_PATH, scopes=SCOPES)
        _sheets_service = build("sheets", "v4", credentials=creds, cache_discovery=False)
    return _sheets_service


def extract_19_fields(ocr_docs: list[dict]) -> list[str]:
    """
    Returns 19 values for columns D-V.
    Commissioner (cols J-K) is sourced ONLY from Profil Perseroan — not AKTA.
    Column V is always the fixed virtual office string.
    """
    akta: dict = {}
    nib: dict = {}
    npwp: dict = {}
    sk: dict = {}
    profile: dict = {}
    has_profile = False  # True only if we found a Profil Perseroan doc

    for doc in ocr_docs:
        data = doc.get("ocr_extracted_data")
        if not data:
            continue
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                continue
        if not isinstance(data, dict):
            continue

        dtype = (doc.get("document_type") or "").lower()
        fname = (doc.get("file_name") or "").lower()

        if "akta" in dtype or "akta" in fname:
            akta = {**akta, **data}
        elif "nib" in dtype or "nib" in fname:
            nib = {**nib, **data}
        elif "npwp" in dtype or "npwp" in fname:
            npwp = {**npwp, **data}
        elif "sk" in dtype or "sk" in fname:
            sk = {**sk, **data}
        elif "profil" in fname or "profile" in fname or "company_profile" in dtype:
            profile = {**profile, **data}
            has_profile = True

    def s(v: Any) -> str:
        if v is None or v == "" or v == 0 or v == "YYYY-MM-DD":
            return ""
        return str(v).strip()

    def first(*sources: str) -> str:
        for v in sources:
            if v:
                return v
        return ""

    # Directors: prefer profile, fallback to AKTA
    directors = profile.get("directors") or akta.get("directors") or []
    # Commissioners: ONLY from Profil Perseroan
    commissioners = profile.get("commissioners") if has_profile else []
    shareholders = profile.get("shareholders", [])

    dir1_name = dir1_pct = comm1_name = comm1_pct = investor_name = investor_pct = ""

    if directors and isinstance(directors, list) and isinstance(directors[0], dict):
        dir1_name = s(directors[0].get("name", ""))
        p = s(directors[0].get("ownership_pct", ""))
        dir1_pct = f"{p}%" if p and p != "0" else ""

    if commissioners and isinstance(commissioners, list) and isinstance(commissioners[0], dict):
        comm1_name = s(commissioners[0].get("name", ""))
        p = s(commissioners[0].get("ownership_pct", ""))
        comm1_pct = f"{p}%" if p and p != "0" else ""

    for sh in shareholders or []:
        if isinstance(sh, dict):
            name = s(sh.get("name", ""))
            if name.upper().startswith("PT ") or name.upper().startswith("CV "):
                investor_name = name
                p = s(sh.get("ownership_pct", ""))
                investor_pct = f"{p}%" if p and p != "0" else ""
                break

    kbli_raw = nib.get("kbli_codes") or profile.get("kbli_codes") or []
    if isinstance(kbli_raw, list):
        codes = []
        for k in kbli_raw:
            if isinstance(k, dict):
                c = k.get("code") or k.get("kode") or ""
                if c:
                    codes.append(str(c))
            elif k:
                codes.append(str(k))
        kbli_str = ", ".join(codes)
    else:
        kbli_str = s(kbli_raw)
    if kbli_str and not any(c.isdigit() for c in kbli_str):
        kbli_str = ""

    capital = s(
        akta.get("authorized_capital")
        or akta.get("Modal Dasar")
        or profile.get("authorized_capital")
        or ""
    )
    if capital and capital != "0":
        try:
            num = int(
                str(capital).replace(".", "").replace(",", "").replace("Rp", "").replace(" ", "")
            )
            capital = f"Rp {num:,.0f}".replace(",", ".")
        except (ValueError, TypeError):
            pass

    return [
        # D - Legal Address
        first(
            s(akta.get("registered_address") or akta.get("Alamat") or akta.get("address")),
            s(profile.get("registered_address") or profile.get("address") or profile.get("Alamat")),
        ),
        # E - NIB
        s(nib.get("nib_number") or nib.get("Nomor Induk Berusaha") or ""),
        # F - NPWP
        s(npwp.get("npwp_number") or npwp.get("NPWP") or ""),
        # G - KBLI
        kbli_str,
        # H - Director 1 name
        dir1_name,
        # I - Director 1 %
        dir1_pct,
        # J - Commissioner 1 name (only from Profil Perseroan)
        comm1_name,
        # K - Commissioner 1 %
        comm1_pct,
        # L - Investor/shareholder name (PT/CV only)
        investor_name,
        # M - Investor %
        investor_pct,
        # N - Authorized Capital
        capital,
        # O - Deed Date
        first(s(akta.get("deed_date") or akta.get("Tanggal Akta")), s(sk.get("issue_date"))),
        # P - Email
        first(
            s(profile.get("company_email") or profile.get("email") or profile.get("Email")),
            s(akta.get("email")),
        ),
        # Q - Phone
        first(
            s(profile.get("company_phone") or profile.get("phone") or profile.get("Nomor Telepon")),
            s(akta.get("phone")),
        ),
        # R - SK Number (Kemenkumham)
        first(s(sk.get("sk_number")), s(akta.get("sk_number") or akta.get("SK Number"))),
        # S - Tax Office KPP (from NPWP doc)
        s(npwp.get("kpp_office") or ""),
        # T - Company Status (TERTUTUP / TERBUKA)
        first(
            s(akta.get("company_status") or akta.get("Status Perseroan")),
            s(profile.get("company_status")),
        ),
        # U - PMA / PMDN
        first(s(nib.get("pma_status") or nib.get("investment_type")), s(profile.get("pma_status"))),
        # V - Office Type (always fixed)
        OFFICE_TYPE_VALUE,
    ]


_company_name_cache: dict[str, int] | None = None


def _load_company_names() -> dict[str, int]:
    """Load all company names from column A into a cache for fast lookup."""
    global _company_name_cache
    if _company_name_cache is not None:
        return _company_name_cache

    svc = get_sheets()
    result = (
        svc.spreadsheets()
        .values()
        .get(
            spreadsheetId=SHEET_ID,
            range=f"{SHEET_NAME}!A{DATA_START_ROW}:A",
        )
        .execute()
    )
    rows = result.get("values", [])

    _company_name_cache = {}
    for i, row in enumerate(rows):
        if row:
            name = row[0].strip()
            _company_name_cache[name.lower()] = DATA_START_ROW + i
    logger.info(f"Loaded {len(_company_name_cache)} company names from sheet column A")
    return _company_name_cache


def _normalize(s: str) -> str:
    """Remove PT/CV/UD suffix/prefix and lowercase for comparison."""
    s = s.lower().strip()
    for suffix in (" pt", " cv", " ud"):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
    for prefix in ("pt ", "cv ", "ud "):
        if s.startswith(prefix):
            s = s[len(prefix) :].strip()
    return s


def find_sheet_row(company_name: str) -> int | None:
    cache = _load_company_names()
    name = company_name.strip()
    name_lower = name.lower()

    # 1. Exact match (as-is)
    row = cache.get(name_lower)
    if row:
        return row

    # 2. DB "PT Foo Bar" → Sheet "Foo Bar PT"
    for prefix in ("PT ", "CV ", "UD "):
        if name.upper().startswith(prefix):
            without = name[len(prefix) :].strip()
            row = cache.get(f"{without} {prefix.strip()}".lower())
            if row:
                return row

    # 3. Normalize both sides (strip PT/CV prefix+suffix) and compare core name
    core = _normalize(name_lower)
    for sheet_name, sheet_row in cache.items():
        if _normalize(sheet_name) == core:
            return sheet_row

    # 4. Fuzzy: core name substring match
    for sheet_name, sheet_row in cache.items():
        sc = _normalize(sheet_name)
        if core and sc and (core in sc or sc in core):
            return sheet_row

    return None


NUM_FIELDS = 19  # D through V


def read_sheet_row(row: int) -> list[str]:
    try:
        svc = get_sheets()
        result = (
            svc.spreadsheets()
            .values()
            .get(
                spreadsheetId=SHEET_ID,
                range=f"{SHEET_NAME}!D{row}:V{row}",
            )
            .execute()
        )
        rows = result.get("values", [])
        if rows:
            data = rows[0]
            while len(data) < NUM_FIELDS:
                data.append("")
            return data
        return [""] * NUM_FIELDS
    except Exception as e:
        logger.warning(f"    Sheet read error: {e}")
        return [""] * NUM_FIELDS


def write_sheet_row(row: int, values: list[str]) -> bool:
    try:
        svc = get_sheets()
        svc.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f"{SHEET_NAME}!D{row}:V{row}",
            valueInputOption="RAW",
            body={"values": [values]},
        ).execute()
        return True
    except Exception as e:
        logger.warning(f"    Sheet write error: {e}")
        return False


async def main(dry_run: bool, limit: int) -> None:
    logger.info(f"{'DRY RUN — ' if dry_run else ''}Update Master Sheet (Step 4)")
    conn = await asyncpg.connect(DB)

    try:
        companies = await conn.fetch(
            """
            SELECT c.id, c.company_name
            FROM companies c
            JOIN company_documents cd ON cd.company_id = c.id
            WHERE cd.ocr_status = 'completed' AND cd.ocr_extracted_data IS NOT NULL
            GROUP BY c.id, c.company_name
            HAVING count(*) > 0
            ORDER BY c.id LIMIT $1
        """,
            limit,
        )

        logger.info(f"Companies with OCR data: {len(companies)}")
        totals = {"updated": 0, "fields": 0, "not_found": 0, "skipped": 0, "errors": 0}

        # Pre-load sheet names
        _load_company_names()

        for i, co in enumerate(companies):
            cid = co["id"]
            cname = co["company_name"]

            docs = await conn.fetch(
                """
                SELECT document_type, file_name, ocr_extracted_data
                FROM company_documents
                WHERE company_id = $1 AND ocr_status = 'completed' AND ocr_extracted_data IS NOT NULL
            """,
                cid,
            )

            fields = extract_19_fields([dict(d) for d in docs])
            non_empty = sum(1 for f in fields if f.strip())
            if non_empty == 0:
                logger.info(f"  [{cid}] SKIP (no fields): {cname[:50]}")
                totals["skipped"] += 1
                continue

            row = find_sheet_row(cname)
            if not row:
                logger.info(f"  [{cid}] NOT FOUND in sheet: {repr(cname[:50])}")
                totals["not_found"] += 1
                continue

            existing = read_sheet_row(row)
            merged = list(existing)
            written = 0
            for j in range(min(len(existing), len(fields))):
                new_val = fields[j].strip()
                if not existing[j].strip() and new_val:
                    merged[j] = fields[j]
                    written += 1
            # Col V (index 18) = always write the fixed office type if still empty
            if len(merged) < NUM_FIELDS:
                merged.extend([""] * (NUM_FIELDS - len(merged)))
            if not merged[18].strip():
                merged[18] = OFFICE_TYPE_VALUE
                written += 1

            if written == 0:
                totals["skipped"] += 1
                continue

            logger.info(f"  [{cid}] {cname[:40]}: row {row}, +{written} fields")

            if not dry_run:
                if not write_sheet_row(row, merged):
                    totals["errors"] += 1
                    continue

            totals["updated"] += 1
            totals["fields"] += written

            if (i + 1) % 50 == 0:
                logger.info(
                    f"\n--- {i + 1}/{len(companies)} | updated={totals['updated']} fields={totals['fields']} ---\n"
                )

        logger.info("\n=== SHEET UPDATE SUMMARY ===")
        logger.info(f"  Companies   : {len(companies)}")
        logger.info(f"  Rows updated: {totals['updated']}")
        logger.info(f"  Fields      : {totals['fields']}")
        logger.info(f"  Not found   : {totals['not_found']}")
        logger.info(f"  Skipped     : {totals['skipped']}")
        logger.info(f"  Errors      : {totals['errors']}")
        if dry_run:
            logger.info("  (DRY RUN)")

    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=2000)
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, limit=args.limit))
