"""
OCR Pipeline v2 — Gemini CLI con accesso Drive diretto
=======================================================
Usa `gemini -p` (headless) per estrarre dati strutturati dai documenti.
Gemini ha accesso nativo a Google Drive tramite OAuth dell'utente.

Processa per company (non per singolo doc): Gemini apre tutta la cartella
00_AKTA e estrae tutti i documenti in un colpo.

Run:
    cd apps/backend-rag
    python3 scripts/ocr_pipeline_gemini.py --batch 20 [--dry-run] [--folder 00_AKTA]
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import time

import asyncpg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# --- Config ---
_db_env = os.getenv("DATABASE_URL", "")
DB = (
    _db_env.replace("postgres://", "postgresql://")
    if _db_env
    else "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag?sslmode=disable"
)

COMPANY_CRM_NAME = "Company_CRM"

# Prompt template per Gemini
AKTA_PROMPT = """Nella mia Google Drive, vai in:
My Drive > Company_CRM > {company_folder} > {subfolder}

Per ogni file PDF o immagine in quella cartella, estrai i dati strutturati. Restituisci UN UNICO JSON array:

[
  {{
    "file_name": "nome esatto del file",
    "document_type": "akta_pendirian|akta_perubahan|sk_decree|other",
    "company_name": "",
    "notary_name": "",
    "deed_number": "",
    "deed_date": "YYYY-MM-DD",
    "directors": [{{"name": "", "ownership_pct": 0}}],
    "commissioners": [{{"name": "", "ownership_pct": 0}}],
    "authorized_capital": 0,
    "paid_capital": 0,
    "registered_address": "",
    "kbli_codes": [],
    "sk_number": "",
    "company_status": "TERTUTUP|TERBUKA"
  }}
]

Regole:
- Compila solo i campi che trovi nel documento
- Date in formato YYYY-MM-DD
- Capitali in Rupiah (numero intero, no separatori)
- Se un file non è un atto notarile, metti document_type: "other" e compila quello che trovi
- Se la cartella è vuota o non esiste, rispondi con []
- Rispondi SOLO con il JSON array, nessun altro testo
"""

NIB_PROMPT = """Nella mia Google Drive, vai in:
My Drive > Company_CRM > {company_folder} > 01_NIB

Per ogni file PDF o immagine, estrai i dati. Restituisci UN UNICO JSON array:

[
  {{
    "file_name": "nome esatto del file",
    "nib_number": "",
    "company_name": "",
    "kbli_codes": [{{"code": "", "description": ""}}],
    "issue_date": "YYYY-MM-DD",
    "pma_status": "PMA|PMDN"
  }}
]

Compila solo i campi trovati. Rispondi SOLO con il JSON, nessun altro testo.
Se la cartella è vuota o non esiste, rispondi con []
"""

NPWP_PROMPT = """Nella mia Google Drive, vai in:
My Drive > Company_CRM > {company_folder} > 02_NPWP

Per ogni file PDF o immagine, estrai i dati. Restituisci UN UNICO JSON array:

[
  {{
    "file_name": "nome esatto del file",
    "npwp_number": "",
    "name": "",
    "kpp_office": "",
    "registration_date": "YYYY-MM-DD"
  }}
]

Compila solo i campi trovati. Rispondi SOLO con il JSON, nessun altro testo.
Se la cartella è vuota o non esiste, rispondi con []
"""

FOLDER_PROMPTS = {
    "00_AKTA": AKTA_PROMPT,
    "01_NIB": NIB_PROMPT,
    "02_NPWP": NPWP_PROMPT,
}


def call_gemini(prompt: str, timeout: int = 120) -> str | None:
    """Call Gemini CLI in headless mode. Returns raw output."""
    try:
        result = subprocess.run(
            ["gemini", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            logger.warning(f"Gemini CLI error (rc={result.returncode}): {result.stderr[:200]}")
            return None
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.warning(f"Gemini CLI timeout ({timeout}s)")
        return None
    except FileNotFoundError:
        logger.error("gemini CLI not found — install with: brew install gemini-cli")
        return None
    except Exception as e:
        logger.error(f"Gemini CLI error: {e}")
        return None


def parse_json_from_output(text: str) -> list[dict] | None:
    """Parse JSON array from Gemini output, handling markdown blocks."""
    if not text:
        return None

    # Strip markdown code blocks
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines)

    # Find JSON array
    start = cleaned.find("[")
    end = cleaned.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            data = json.loads(cleaned[start:end])
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    logger.warning(f"Could not parse JSON from Gemini output: {text[:300]}")
    return None


async def update_company_docs(
    conn: asyncpg.Connection,
    company_id: int,
    docs: list[dict],
    folder_type: str,
    dry_run: bool,
) -> int:
    """Match Gemini results to company_documents and update OCR data."""
    updated = 0

    for doc in docs:
        file_name = doc.get("file_name", "")
        if not file_name:
            continue

        # Find matching doc in DB
        row = await conn.fetchrow(
            "SELECT id, document_type FROM company_documents WHERE company_id = $1 AND file_name = $2",
            company_id,
            file_name,
        )

        if not row:
            # Try fuzzy match (file names sometimes differ slightly)
            row = await conn.fetchrow(
                "SELECT id, document_type FROM company_documents WHERE company_id = $1 AND file_name ILIKE $2",
                company_id,
                f"%{file_name[:30]}%",
            )

        if not row:
            logger.info(f"      ? No DB match for: {file_name}")
            continue

        doc_id = row["id"]
        ocr_json = json.dumps(doc)

        if dry_run:
            logger.info(f"      [DRY] Would save OCR for [{doc_id}] {file_name}")
        else:
            await conn.execute(
                """UPDATE company_documents
                   SET ocr_status = 'completed',
                       ocr_extracted_data = $1::jsonb,
                       updated_at = NOW()
                   WHERE id = $2""",
                ocr_json,
                doc_id,
            )

        updated += 1

        # Update companies table for key fields
        if not dry_run and folder_type == "00_AKTA":
            await update_company_fields(conn, company_id, doc)
        elif not dry_run and folder_type == "01_NIB":
            nib = doc.get("nib_number", "").strip()
            if nib:
                current = await conn.fetchval("SELECT nib FROM companies WHERE id = $1", company_id)
                if not current:
                    await conn.execute(
                        "UPDATE companies SET nib = $1, updated_at = NOW() WHERE id = $2",
                        nib,
                        company_id,
                    )
                    logger.info(f"      → companies.nib = {nib}")
        elif not dry_run and folder_type == "02_NPWP":
            npwp = doc.get("npwp_number", "").strip()
            if npwp:
                current = await conn.fetchval(
                    "SELECT npwp_company FROM companies WHERE id = $1", company_id
                )
                if not current:
                    await conn.execute(
                        "UPDATE companies SET npwp_company = $1, updated_at = NOW() WHERE id = $2",
                        npwp,
                        company_id,
                    )
                    logger.info(f"      → companies.npwp_company = {npwp}")

    return updated


async def update_company_fields(conn: asyncpg.Connection, company_id: int, doc: dict) -> None:
    """Update companies table from AKTA OCR data."""
    doc_type = doc.get("document_type", "")

    if doc_type in ("akta_pendirian", "akta_perubahan"):
        deed_no = doc.get("deed_number", "").strip()
        deed_date = doc.get("deed_date", "").strip()
        if deed_no:
            current = await conn.fetchval(
                "SELECT akta_pendirian_no FROM companies WHERE id = $1", company_id
            )
            if not current:
                await conn.execute(
                    "UPDATE companies SET akta_pendirian_no = $1, updated_at = NOW() WHERE id = $2",
                    deed_no,
                    company_id,
                )
                logger.info(f"      → companies.akta_pendirian_no = {deed_no}")
        if deed_date and deed_date != "YYYY-MM-DD":
            current = await conn.fetchval(
                "SELECT akta_pendirian_date FROM companies WHERE id = $1", company_id
            )
            if not current:
                try:
                    from datetime import date as dt_date

                    d = dt_date.fromisoformat(deed_date)
                    await conn.execute(
                        "UPDATE companies SET akta_pendirian_date = $1, updated_at = NOW() WHERE id = $2",
                        d,
                        company_id,
                    )
                    logger.info(f"      → companies.akta_pendirian_date = {deed_date}")
                except ValueError:
                    pass

        # Update capital if available
        auth_cap = doc.get("authorized_capital", 0)
        paid_cap = doc.get("paid_capital", 0)
        if auth_cap and isinstance(auth_cap, (int, float)) and auth_cap > 0:
            await conn.execute(
                "UPDATE companies SET custom_fields = custom_fields || $1::jsonb, updated_at = NOW() WHERE id = $2",
                json.dumps({"authorized_capital": auth_cap, "paid_capital": paid_cap}),
                company_id,
            )

    elif doc_type == "sk_decree":
        sk_no = doc.get("sk_number", "").strip()
        sk_date = doc.get("deed_date", "").strip()
        if sk_no:
            current = await conn.fetchval(
                "SELECT sk_menhumkam_no FROM companies WHERE id = $1", company_id
            )
            if not current:
                await conn.execute(
                    "UPDATE companies SET sk_menhumkam_no = $1, updated_at = NOW() WHERE id = $2",
                    sk_no,
                    company_id,
                )
                logger.info(f"      → companies.sk_menhumkam_no = {sk_no}")
        if sk_date and sk_date != "YYYY-MM-DD":
            current = await conn.fetchval(
                "SELECT sk_menhumkam_date FROM companies WHERE id = $1", company_id
            )
            if not current:
                try:
                    from datetime import date as dt_date

                    d = dt_date.fromisoformat(sk_date)
                    await conn.execute(
                        "UPDATE companies SET sk_menhumkam_date = $1, updated_at = NOW() WHERE id = $2",
                        d,
                        company_id,
                    )
                except ValueError:
                    pass


async def ensure_ocr_columns(conn: asyncpg.Connection) -> None:
    """Add ocr columns to company_documents if missing."""
    existing = await conn.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'company_documents'",
    )
    cols = {r["column_name"] for r in existing}

    if "ocr_status" not in cols:
        await conn.execute(
            "ALTER TABLE company_documents ADD COLUMN ocr_status VARCHAR(20) DEFAULT NULL"
        )
    if "ocr_extracted_data" not in cols:
        await conn.execute(
            "ALTER TABLE company_documents ADD COLUMN ocr_extracted_data JSONB DEFAULT NULL"
        )


async def main(dry_run: bool, batch_size: int, folder: str) -> None:
    logger.info(f"{'DRY RUN — ' if dry_run else ''}OCR Pipeline v2 (Gemini CLI)")
    logger.info(f"Folder: {folder}, Batch: {batch_size}")

    # Check gemini CLI
    check = subprocess.run(["gemini", "--version"], capture_output=True, text=True, timeout=5)
    if check.returncode != 0:
        logger.error("gemini CLI not available")
        return
    logger.info(f"Gemini CLI: v{check.stdout.strip()}")

    conn = await asyncpg.connect(DB)

    try:
        await ensure_ocr_columns(conn)

        prompt_template = FOLDER_PROMPTS.get(folder)
        if not prompt_template:
            logger.error(f"No prompt template for folder: {folder}")
            return

        # Get companies that have docs needing OCR in the target folder
        # We process by company, not by individual doc
        companies = await conn.fetch(
            """SELECT DISTINCT c.id, c.company_name, c.google_drive_folder_id
               FROM companies c
               JOIN company_documents cd ON cd.company_id = c.id
               WHERE (cd.ocr_status IS NULL OR cd.ocr_status = 'pending')
                 AND cd.google_drive_file_id IS NOT NULL
               ORDER BY c.id
               LIMIT $1""",
            batch_size,
        )

        logger.info(f"Found {len(companies)} companies to process")

        if not companies:
            logger.info("No companies to process")
            return

        stats = {"processed": 0, "docs_updated": 0, "failed": 0, "empty": 0}

        for company in companies:
            cid = company["id"]
            cname = company["company_name"]
            logger.info(f"\n  [{cid}] {cname}")

            # Build prompt
            prompt = prompt_template.format(company_folder=cname, subfolder=folder)

            # Call Gemini
            logger.info(f"    Calling Gemini for {folder}...")
            raw_output = call_gemini(prompt, timeout=180)

            if not raw_output:
                logger.warning("    ✗ Gemini returned no output")
                stats["failed"] += 1
                continue

            # Parse JSON
            docs = parse_json_from_output(raw_output)

            if not docs:
                if "[]" in raw_output:
                    logger.info("    ○ Empty folder")
                    stats["empty"] += 1
                else:
                    logger.warning(f"    ✗ Could not parse output: {raw_output[:200]}")
                    stats["failed"] += 1
                continue

            logger.info(f"    ✓ Gemini extracted {len(docs)} documents")

            # Update DB
            updated = await update_company_docs(conn, cid, docs, folder, dry_run)
            stats["docs_updated"] += updated
            stats["processed"] += 1

            logger.info(f"    ✓ {updated}/{len(docs)} docs matched in DB")

            # Rate limit (be nice to Gemini)
            time.sleep(2)

            # Progress log
            if stats["processed"] % 10 == 0:
                logger.info(
                    f"\n--- Progress: {stats['processed']}/{len(companies)} "
                    f"({stats['docs_updated']} docs, {stats['failed']} failed) ---\n"
                )

        logger.info("\n=== GEMINI OCR SUMMARY ===")
        logger.info(f"  Companies processed : {stats['processed']}")
        logger.info(f"  Documents updated   : {stats['docs_updated']}")
        logger.info(f"  Empty folders       : {stats['empty']}")
        logger.info(f"  Failed              : {stats['failed']}")
        if dry_run:
            logger.info("  (DRY RUN — no DB changes)")

    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OCR Pipeline v2 — Gemini CLI with Drive access")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--batch", type=int, default=20, help="Companies per run (default 20)")
    parser.add_argument(
        "--folder",
        type=str,
        default="00_AKTA",
        choices=["00_AKTA", "01_NIB", "02_NPWP"],
        help="Which subfolder to OCR (default: 00_AKTA)",
    )
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run, batch_size=args.batch, folder=args.folder))
