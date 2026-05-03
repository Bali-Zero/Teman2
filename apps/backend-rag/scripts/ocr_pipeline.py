"""
OCR Pipeline — Extract structured data from CRM documents
==========================================================
Per ogni documento in DB (company_documents + documents):
  1. Scarica file da Drive (via google_drive_file_id)
  2. Se PDF → estrai testo con pypdf (tier 1)
  3. Se immagine o PDF scansionato (testo vuoto) → Ollama qwen2.5vl:7b (tier 2)
  4. Prompt specifico per tipo documento → JSON strutturato
  5. Salva in ocr_extracted_data (JSONB) + aggiorna ocr_status

Run:
    cd apps/backend-rag
    source venv/bin/activate
    python3 scripts/ocr_pipeline.py --batch 50 [--dry-run] [--type akta_pendirian] [--table company_documents]
"""

import argparse
import asyncio
import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# --- Config ---
_db_env = os.getenv("DATABASE_URL", "")
DB = (
    _db_env.replace("postgres://", "postgresql://")
    if _db_env
    else "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag?sslmode=disable"
)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = "qwen2.5vl:7b"

# OAuth credentials (same as bulk_populate)
OAUTH_CLIENT_ID = "930328104463-m3g4gq72095rip08269kvt8s7et9ev12.apps.googleusercontent.com"
OAUTH_CLIENT_SECRET = "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"
OAUTH_REFRESH_TOKEN = "1//0gbiun0bBkNVCCgYIARAAGBASNwF-L9IrGvLMkg0QQ7fz0x98C1zyFqsCvzyijl7NjxUXoJ8K_-BAN8t-ZuQyT5uIv2iVJUPSiMA"

_oauth_access_token: str | None = None
_oauth_token_expiry: float = 0.0

# --- OCR Prompts per document type ---
OCR_PROMPTS: dict[str, str] = {
    "akta_pendirian": """Extract from this Indonesian notarial deed (Akta Pendirian). Return ONLY valid JSON, no other text:
{
  "company_name": "",
  "notary_name": "",
  "deed_number": "",
  "deed_date": "YYYY-MM-DD",
  "directors": [{"name": "", "ownership_pct": 0}],
  "commissioners": [{"name": "", "ownership_pct": 0}],
  "authorized_capital": 0,
  "paid_capital": 0,
  "registered_address": "",
  "kbli_codes": [],
  "company_status": "TERTUTUP"
}""",
    "nib": """Extract from this NIB (Nomor Induk Berusaha). Return ONLY valid JSON, no other text:
{
  "nib_number": "",
  "company_name": "",
  "kbli_codes": [{"code": "", "description": ""}],
  "issue_date": "YYYY-MM-DD",
  "pma_status": "PMA"
}""",
    "npwp": """Extract from this NPWP document. Return ONLY valid JSON, no other text:
{
  "npwp_number": "",
  "name": "",
  "kpp_office": "",
  "registration_date": "YYYY-MM-DD"
}""",
    "passport": """Extract from this passport. Return ONLY valid JSON, no other text:
{
  "full_name": "",
  "passport_number": "",
  "nationality": "",
  "date_of_birth": "YYYY-MM-DD",
  "date_of_expiry": "YYYY-MM-DD",
  "sex": "",
  "place_of_birth": ""
}""",
    "sk_decree": """Extract from this SK Kemenkumham decree. Return ONLY valid JSON, no other text:
{
  "sk_number": "",
  "company_name": "",
  "issue_date": "YYYY-MM-DD",
  "capital_info": ""
}""",
    "kitas": """Extract from this KITAS/ITAS permit. Return ONLY valid JSON, no other text:
{
  "permit_number": "",
  "full_name": "",
  "nationality": "",
  "sponsor": "",
  "valid_from": "YYYY-MM-DD",
  "valid_until": "YYYY-MM-DD",
  "occupation": ""
}""",
    "company_profile": """Extract from this company profile document. Return ONLY valid JSON, no other text:
{
  "company_name": "",
  "business_activity": "",
  "address": "",
  "directors": [],
  "commissioners": []
}""",
}

# Fallback prompt for unknown document types
DEFAULT_PROMPT = """Extract all structured data from this document. Return ONLY valid JSON with the key information found (names, numbers, dates, addresses)."""

# Document type normalization
DOC_TYPE_ALIASES: dict[str, str] = {
    "akta": "akta_pendirian",
    "akta_pendirian": "akta_pendirian",
    "akta_perubahan": "akta_pendirian",
    "nib": "nib",
    "npwp": "npwp",
    "npwp_personal": "npwp",
    "passport": "passport",
    "sk_decree": "sk_decree",
    "sk_kemenkumham": "sk_decree",
    "kitas": "kitas",
    "kitap": "kitas",
    "company_profile": "company_profile",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"}


async def get_oauth_token() -> str:
    """Get OAuth access token for Drive API, refreshing if expired."""
    global _oauth_access_token, _oauth_token_expiry

    if _oauth_access_token and time.time() < _oauth_token_expiry - 60:
        return _oauth_access_token

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": OAUTH_CLIENT_ID,
                "client_secret": OAUTH_CLIENT_SECRET,
                "refresh_token": OAUTH_REFRESH_TOKEN,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    _oauth_access_token = data["access_token"]
    _oauth_token_expiry = time.time() + data.get("expires_in", 3600)
    logger.info("OAuth token refreshed")
    return _oauth_access_token


async def download_from_drive(file_id: str, token: str) -> bytes | None:
    """Download a file from Google Drive by file ID. Auto-refreshes token on 401."""
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&supportsAllDrives=true"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            if resp.status_code == 200:
                return resp.content
            if resp.status_code == 401:
                # Token expired — force refresh and retry
                global _oauth_access_token, _oauth_token_expiry
                _oauth_access_token = None
                _oauth_token_expiry = 0.0
                logger.info("    Token expired, refreshing...")
                new_token = await get_oauth_token()
                resp = await client.get(url, headers={"Authorization": f"Bearer {new_token}"})
                if resp.status_code == 200:
                    return resp.content
            logger.warning(f"Drive download failed: HTTP {resp.status_code} for {file_id}")
            return None
    except Exception as e:
        logger.error(f"Drive download error for {file_id}: {e}")
        return None


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF using PyMuPDF (fitz). Returns empty string if scanned/image PDF."""
    try:
        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        return "\n".join(text_parts).strip()
    except Exception as e:
        logger.warning(f"PDF text extraction failed: {e}")
        return ""


def pdf_to_images(pdf_bytes: bytes, max_pages: int = 5) -> list[str]:
    """Convert PDF pages to base64 PNG images for vision OCR.

    Uses adaptive zoom: 2x for small PDFs, 1.5x for medium, 1x for large.
    This prevents Ollama timeouts on large scanned documents.
    """
    try:
        import fitz

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        # Adaptive zoom based on file size to avoid Ollama timeouts
        size_mb = len(pdf_bytes) / (1024 * 1024)
        if size_mb > 5:
            zoom = 1.0  # Large files: lower res to avoid timeout
        elif size_mb > 2:
            zoom = 1.5  # Medium files
        else:
            zoom = 2.0  # Small files: high res

        images = []
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            img_bytes = pix.tobytes("png")
            images.append(base64.b64encode(img_bytes).decode())
        doc.close()
        return images
    except Exception as e:
        logger.error(f"PDF to image conversion failed: {e}")
        return []


def image_to_base64(image_bytes: bytes) -> str:
    """Convert image bytes to base64."""
    return base64.b64encode(image_bytes).decode()


async def ocr_via_ollama(prompt: str, image_base64: str) -> str | None:
    """Send image to Ollama qwen2.5vl:7b for vision OCR."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [image_base64],
            }
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 8192,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("message", {}).get("content", "").strip()
            if content:
                return content
            return None
    except httpx.ConnectError:
        logger.error("Ollama not available — is it running?")
        return None
    except httpx.TimeoutException:
        logger.warning("Ollama timeout (180s)")
        return None
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return None


async def ocr_via_ollama_text(prompt: str) -> str | None:
    """Send text-only prompt to Ollama (no image). Used for text-rich PDFs."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 8192,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data.get("message", {}).get("content", "").strip()
            return content if content else None
    except Exception as e:
        logger.error(f"Ollama text-only error: {e}")
        return None


def parse_json_response(text: str) -> dict | None:
    """Parse JSON from LLM response, handling markdown code blocks."""
    if not text:
        return None

    # Strip markdown code blocks
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                pass

    logger.warning(f"Could not parse JSON from response: {text[:200]}")
    return None


def get_prompt_for_type(doc_type: str) -> str:
    """Get the appropriate OCR prompt for a document type."""
    normalized = DOC_TYPE_ALIASES.get(doc_type.lower(), doc_type.lower())
    return OCR_PROMPTS.get(normalized, DEFAULT_PROMPT)


async def process_document(
    conn: asyncpg.Connection,
    doc: dict,
    table: str,
    dry_run: bool,
) -> bool:
    """Process a single document: download, OCR, save results."""
    doc_id = doc["id"]
    doc_type = doc["document_type"] or "other"
    file_name = doc["file_name"] or "unknown"
    drive_file_id = doc["google_drive_file_id"]

    logger.info(f"  [{doc_id}] {file_name} (type: {doc_type})")

    # 1. Mark as processing
    if not dry_run:
        await conn.execute(
            f"UPDATE {table} SET ocr_status = 'processing', updated_at = NOW() WHERE id = $1",
            doc_id,
        )

    # 2. Download from Drive (always get fresh token)
    token = await get_oauth_token()
    file_bytes = await download_from_drive(drive_file_id, token)
    if not file_bytes:
        if not dry_run:
            await conn.execute(
                f"UPDATE {table} SET ocr_status = 'failed', updated_at = NOW() WHERE id = $1",
                doc_id,
            )
        logger.warning("    ✗ Download failed")
        return False

    logger.info(f"    Downloaded: {len(file_bytes)} bytes")

    # 3. Determine if PDF or image
    ext = Path(file_name).suffix.lower()
    is_pdf = ext == ".pdf" or file_bytes[:4] == b"%PDF"
    is_image = ext in IMAGE_EXTENSIONS

    prompt = get_prompt_for_type(doc_type)
    ocr_result: dict | None = None

    if is_pdf:
        # Tier 1: Try text extraction
        text = extract_text_from_pdf(file_bytes)
        if len(text) > 100:
            # Good text content — render first page as image for vision OCR
            # (vision model can extract structured data better from the visual layout)
            logger.info(
                f"    PDF text extracted: {len(text)} chars — using first page image for structure"
            )
            images = pdf_to_images(file_bytes, max_pages=2)
            if images:
                llm_response = await ocr_via_ollama(prompt, images[0])
                ocr_result = parse_json_response(llm_response)
            else:
                # Fallback: pass text directly via text-only LLM call
                text_prompt = f"{prompt}\n\nDocument text:\n{text[:8000]}"
                llm_response = await ocr_via_ollama_text(text_prompt)
                ocr_result = parse_json_response(llm_response)
        else:
            # Scanned PDF — Tier 2: Vision OCR
            logger.info("    Scanned PDF — using vision OCR")
            images = pdf_to_images(file_bytes, max_pages=3)
            for i, img_b64 in enumerate(images):
                logger.info(f"    Processing page {i + 1}/{len(images)}...")
                response = await ocr_via_ollama(prompt, img_b64)
                result = parse_json_response(response)
                if result:
                    ocr_result = result
                    break  # Use first successful extraction

    elif is_image:
        # Direct image OCR
        logger.info("    Image file — using vision OCR")
        img_b64 = image_to_base64(file_bytes)
        response = await ocr_via_ollama(prompt, img_b64)
        ocr_result = parse_json_response(response)

    else:
        logger.warning(f"    ✗ Unsupported file type: {ext}")
        if not dry_run:
            await conn.execute(
                f"UPDATE {table} SET ocr_status = 'skipped', updated_at = NOW() WHERE id = $1",
                doc_id,
            )
        return False

    # 4. Save results
    if ocr_result:
        logger.info(f"    ✓ OCR extracted: {list(ocr_result.keys())}")
        if dry_run:
            logger.info(f"    [DRY] Would save: {json.dumps(ocr_result, indent=2)[:300]}")
        else:
            ocr_json = json.dumps(ocr_result)
            await conn.execute(
                f"""UPDATE {table}
                    SET ocr_status = 'completed',
                        ocr_extracted_data = $1::jsonb,
                        updated_at = NOW()
                    WHERE id = $2""",
                ocr_json,
                doc_id,
            )

            # For company_documents, also update companies table (non-fatal)
            if table == "company_documents":
                try:
                    await update_company_from_ocr(conn, doc, ocr_result, doc_type, dry_run)
                except Exception as e:
                    logger.warning(f"    ⚠ Company update failed (OCR data saved OK): {e}")

        return True
    else:
        logger.warning("    ✗ OCR failed to extract structured data")
        if not dry_run:
            await conn.execute(
                f"UPDATE {table} SET ocr_status = 'failed', updated_at = NOW() WHERE id = $1",
                doc_id,
            )
        return False


async def update_company_from_ocr(
    conn: asyncpg.Connection,
    doc: dict,
    ocr_data: dict,
    doc_type: str,
    dry_run: bool,
) -> None:
    """Update companies table with OCR-extracted data."""
    company_id = doc.get("company_id")
    if not company_id:
        return

    normalized = DOC_TYPE_ALIASES.get(doc_type.lower(), doc_type.lower())
    updates: list[tuple[str, Any]] = []

    if normalized == "nib":
        nib = ocr_data.get("nib_number", "").strip()
        if nib:
            updates.append(("nib", nib))

    elif normalized == "npwp":
        npwp = ocr_data.get("npwp_number", "").strip()
        if npwp:
            updates.append(("npwp_company", npwp))

    elif normalized == "akta_pendirian":
        deed_no = ocr_data.get("deed_number", "").strip()
        deed_date = ocr_data.get("deed_date", "").strip()
        if deed_no:
            updates.append(("akta_pendirian_no", deed_no))
        if deed_date and deed_date != "YYYY-MM-DD":
            updates.append(("akta_pendirian_date", deed_date))

    elif normalized == "sk_decree":
        sk_no = ocr_data.get("sk_number", "").strip()
        sk_date = ocr_data.get("issue_date", "").strip()
        if sk_no:
            updates.append(("sk_menhumkam_no", sk_no))
        if sk_date and sk_date != "YYYY-MM-DD":
            updates.append(("sk_menhumkam_date", sk_date))

    if not updates:
        return

    for col, val in updates:
        # Only update if currently NULL
        current = await conn.fetchval(f"SELECT {col} FROM companies WHERE id = $1", company_id)
        if current is None:
            logger.info(f"    → companies.{col} = {val}")
            if not dry_run:
                if "date" in col:
                    # asyncpg requires datetime.date, not str
                    try:
                        from datetime import date as dt_date

                        date_val = dt_date.fromisoformat(val)
                        await conn.execute(
                            f"UPDATE companies SET {col} = $1, updated_at = NOW() WHERE id = $2",
                            date_val,
                            company_id,
                        )
                    except (ValueError, TypeError) as e:
                        logger.warning(f"    ⚠ Invalid date '{val}' for {col}: {e}")
                else:
                    await conn.execute(
                        f"UPDATE companies SET {col} = $1, updated_at = NOW() WHERE id = $2",
                        val,
                        company_id,
                    )


async def ensure_ocr_columns(conn: asyncpg.Connection, table: str) -> None:
    """Add ocr_status, ocr_extracted_data columns if missing."""
    existing = await conn.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name = $1",
        table,
    )
    cols = {r["column_name"] for r in existing}

    if "ocr_status" not in cols:
        logger.info(f"Adding ocr_status column to {table}")
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN ocr_status VARCHAR(20) DEFAULT NULL")

    if "ocr_extracted_data" not in cols:
        logger.info(f"Adding ocr_extracted_data column to {table}")
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN ocr_extracted_data JSONB DEFAULT NULL")

    if "ocr_completed_at" not in cols:
        logger.info(f"Adding ocr_completed_at column to {table}")
        await conn.execute(
            f"ALTER TABLE {table} ADD COLUMN ocr_completed_at TIMESTAMPTZ DEFAULT NULL"
        )


async def main(
    dry_run: bool,
    batch_size: int,
    doc_type: str | None,
    table: str,
) -> None:
    logger.info(f"{'DRY RUN — ' if dry_run else ''}OCR Pipeline starting")
    logger.info(f"Table: {table}, Batch: {batch_size}, Type filter: {doc_type or 'all'}")
    logger.info(f"Ollama: {OLLAMA_URL} model: {OLLAMA_MODEL}")

    # Check Ollama availability
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            if OLLAMA_MODEL not in models and f"{OLLAMA_MODEL}:latest" not in models:
                logger.error(f"Model {OLLAMA_MODEL} not found in Ollama. Available: {models}")
                return
            logger.info(f"Ollama OK — model {OLLAMA_MODEL} available")
    except Exception as e:
        logger.error(f"Ollama not available at {OLLAMA_URL}: {e}")
        return

    conn = await asyncpg.connect(DB)

    try:
        # Ensure OCR columns exist
        await ensure_ocr_columns(conn, table)

        # Warm-up OAuth token
        await get_oauth_token()

        # Build query
        conditions = [
            "(ocr_status IS NULL OR ocr_status = 'pending')",
            "google_drive_file_id IS NOT NULL",
        ]

        if table == "company_documents":
            select_cols = "id, company_id, document_type, google_drive_file_id, file_name"
        else:
            select_cols = "id, client_id, document_type, file_id as google_drive_file_id, file_name"

        if doc_type:
            conditions.append(f"document_type = '{doc_type}'")

        where = " AND ".join(conditions)
        query = f"SELECT {select_cols} FROM {table} WHERE {where} ORDER BY id LIMIT $1"

        docs = await conn.fetch(query, batch_size)
        logger.info(f"Found {len(docs)} documents to process")

        if not docs:
            logger.info("No documents to process")
            return

        stats = {"processed": 0, "success": 0, "failed": 0, "skipped": 0}

        for doc in docs:
            try:
                success = await process_document(conn, dict(doc), table, dry_run)
                stats["processed"] += 1
                if success:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1
            except Exception as e:
                logger.error(f"Error processing doc {doc['id']}: {e}", exc_info=True)
                stats["failed"] += 1

            # Progress log every 10
            if stats["processed"] % 10 == 0:
                logger.info(
                    f"--- Progress: {stats['processed']}/{len(docs)} "
                    f"({stats['success']} OK, {stats['failed']} failed) ---"
                )

        logger.info("\n=== OCR PIPELINE SUMMARY ===")
        logger.info(f"  Documents processed : {stats['processed']}")
        logger.info(f"  Successful          : {stats['success']}")
        logger.info(f"  Failed              : {stats['failed']}")
        if dry_run:
            logger.info("  (DRY RUN — no DB changes made)")

    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="OCR Pipeline — extract structured data from CRM documents"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB writes")
    parser.add_argument(
        "--batch", type=int, default=50, help="Number of documents per run (default 50)"
    )
    parser.add_argument(
        "--type", type=str, default=None, help="Filter by document_type (e.g., akta_pendirian, nib)"
    )
    parser.add_argument(
        "--table",
        type=str,
        default="company_documents",
        choices=["company_documents", "documents"],
        help="Which table to process (default: company_documents)",
    )
    args = parser.parse_args()

    asyncio.run(
        main(dry_run=args.dry_run, batch_size=args.batch, doc_type=args.type, table=args.table)
    )
