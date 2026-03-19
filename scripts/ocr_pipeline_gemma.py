"""
OCR Pipeline — Gemini 2.5 Flash Lite (Tier 2)
==============================================
Batch OCR: download PDF from Drive → convert to image → Gemini API → save JSON to DB.
Ordered by company_id so each company is completed together.

Run:
    python3 scripts/ocr_pipeline_gemma.py --batch 5000 [--dry-run] [--type akta_pendirian] [--pdf-only]
"""

import argparse
import asyncio
import base64
import io
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import asyncpg
import fitz  # PyMuPDF
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_db_env = os.getenv("DATABASE_URL", "")
DB = (
    _db_env.replace("postgres://", "postgresql://")
    if _db_env
    else "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:5433/nuzantara_rag?sslmode=disable"
)

GEMMA_API_KEY = os.getenv("GEMMA_API_KEY", "")
GEMMA_MODEL = "gemini-2.5-flash-lite"
GEMMA_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMMA_MODEL}:generateContent"

RPM_LIMIT = 2000
RPM_WINDOW: list[float] = []

OAUTH_CLIENT_ID = "930328104463-m3g4gq72095rip08269kvt8s7et9ev12.apps.googleusercontent.com"
OAUTH_CLIENT_SECRET = "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"
OAUTH_REFRESH_TOKEN = "1//0gbiun0bBkNVCCgYIARAAGBASNwF-L9IrGvLMkg0QQ7fz0x98C1zyFqsCvzyijl7NjxUXoJ8K_-BAN8t-ZuQyT5uIv2iVJUPSiMA"

_oauth_access_token: str | None = None
_oauth_token_expiry: float = 0.0

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"}

PROMPTS: dict[str, str] = {
    "akta_pendirian": "Extract from this Indonesian notarial deed (Akta Pendirian/Perubahan). Return ONLY valid JSON, no other text:\n"
        '{"company_name": "", "notary_name": "", "deed_number": "", "deed_date": "YYYY-MM-DD", '
        '"directors": [{"name": "", "ownership_pct": 0}], "commissioners": [{"name": "", "ownership_pct": 0}], '
        '"authorized_capital": 0, "paid_capital": 0, "registered_address": "", "kbli_codes": [], "company_status": "TERTUTUP"}',

    "nib": "Extract from this NIB (Nomor Induk Berusaha). Return ONLY valid JSON:\n"
        '{"nib_number": "", "company_name": "", "kbli_codes": [{"code": "", "description": ""}], "issue_date": "YYYY-MM-DD", "pma_status": "PMA"}',

    "npwp": "Extract from this NPWP document. Return ONLY valid JSON:\n"
        '{"npwp_number": "", "name": "", "kpp_office": "", "registration_date": "YYYY-MM-DD"}',

    "passport": "Extract from this passport. Return ONLY valid JSON:\n"
        '{"full_name": "", "passport_number": "", "nationality": "", "date_of_birth": "YYYY-MM-DD", '
        '"date_of_expiry": "YYYY-MM-DD", "sex": "", "place_of_birth": ""}',

    "sk_decree": "Extract from this SK Kemenkumham decree. Return ONLY valid JSON:\n"
        '{"sk_number": "", "company_name": "", "issue_date": "YYYY-MM-DD", "capital_info": ""}',

    "kitas": "Extract from this KITAS/ITAS permit. Return ONLY valid JSON:\n"
        '{"permit_number": "", "full_name": "", "nationality": "", "sponsor": "", '
        '"valid_from": "YYYY-MM-DD", "valid_until": "YYYY-MM-DD", "occupation": ""}',

    "company_profile": "Extract from this Indonesian Company Profile (Profil Perseroan/Detail Perseroan). "
        "IMPORTANT: The table 'PENGURUS DAN PEMEGANG SAHAM' at the end lists ALL directors, commissioners and shareholders "
        "with their name, role (DIREKTUR/KOMISARIS), passport number, nationality, and share count. Extract ALL of them. "
        "Return ONLY valid JSON:\n"
        '{"company_name": "", "company_type": "PMA", "company_status": "TERTUTUP", '
        '"registered_address": "", "city": "", "company_phone": "", "company_email": "", '
        '"notary_name": "", "deed_number": "", "deed_date": "YYYY-MM-DD", '
        '"sk_number": "", "sk_date": "YYYY-MM-DD", '
        '"authorized_capital": 0, "paid_capital": 0, '
        '"kbli_codes": [{"code": "47735", "description": "Perdagangan Eceran"}], '
        '"directors": [{"name": "FULL NAME", "role": "DIREKTUR", "passport": "", "nationality": "", "shares": 0, "share_value": 0, "ownership_pct": 0}], '
        '"commissioners": [{"name": "FULL NAME", "role": "KOMISARIS", "passport": "", "nationality": "", "shares": 0, "share_value": 0, "ownership_pct": 0}]}',
}

DEFAULT_PROMPT = "Extract all structured data from this document. Return ONLY valid JSON with key information (names, numbers, dates, addresses)."

DOC_TYPE_ALIASES: dict[str, str] = {
    "akta": "akta_pendirian", "akta_pendirian": "akta_pendirian", "akta_perubahan": "akta_pendirian",
    "nib": "nib", "npwp": "npwp", "npwp_personal": "npwp",
    "passport": "passport", "sk_decree": "sk_decree", "sk_kemenkumham": "sk_decree",
    "kitas": "kitas", "kitap": "kitas", "company_profile": "company_profile",
}


async def get_oauth_token() -> str:
    global _oauth_access_token, _oauth_token_expiry
    if _oauth_access_token and time.time() < _oauth_token_expiry - 60:
        return _oauth_access_token
    async with httpx.AsyncClient() as client:
        resp = await client.post("https://oauth2.googleapis.com/token", data={
            "client_id": OAUTH_CLIENT_ID, "client_secret": OAUTH_CLIENT_SECRET,
            "refresh_token": OAUTH_REFRESH_TOKEN, "grant_type": "refresh_token",
        })
        resp.raise_for_status()
        data = resp.json()
    _oauth_access_token = data["access_token"]
    _oauth_token_expiry = time.time() + data.get("expires_in", 3600)
    logger.info("OAuth token refreshed")
    return _oauth_access_token


async def download_from_drive(file_id: str) -> bytes | None:
    token = await get_oauth_token()
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&supportsAllDrives=true"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            if resp.status_code == 200:
                return resp.content
            if resp.status_code == 401:
                global _oauth_access_token, _oauth_token_expiry
                _oauth_access_token = None
                _oauth_token_expiry = 0.0
                token = await get_oauth_token()
                resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
                if resp.status_code == 200:
                    return resp.content
            logger.warning(f"Drive download failed: HTTP {resp.status_code} for {file_id}")
            return None
    except Exception as e:
        logger.error(f"Drive download error: {e}")
        return None


def file_to_base64_images(file_bytes: bytes, file_name: str) -> list[tuple[str, str]]:
    """Convert file to list of (base64, mime_type) tuples. PDFs return all pages."""
    ext = Path(file_name).suffix.lower()
    is_pdf = ext == ".pdf" or file_bytes[:4] == b"%PDF"
    is_image = ext in IMAGE_EXTENSIONS

    if is_pdf:
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            size_mb = len(file_bytes) / (1024 * 1024)
            zoom = 1.0 if size_mb > 5 else (1.5 if size_mb > 2 else 2.0)
            pages = []
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
                img_bytes = pix.tobytes("png")
                pages.append((base64.b64encode(img_bytes).decode(), "image/png"))
            doc.close()
            if pages:
                logger.info(f"    PDF → {len(pages)} page(s)")
            return pages
        except Exception as e:
            logger.warning(f"PDF conversion failed: {e}")
            return []
    elif is_image:
        mime = "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext.lstrip('.')}"
        return [(base64.b64encode(file_bytes).decode(), mime)]
    return []


async def rate_limit():
    now = time.time()
    while RPM_WINDOW and RPM_WINDOW[0] < now - 60:
        RPM_WINDOW.pop(0)
    if len(RPM_WINDOW) >= RPM_LIMIT:
        wait = 60 - (now - RPM_WINDOW[0]) + 0.5
        if wait > 0:
            logger.info(f"    Rate limit: waiting {wait:.1f}s")
            await asyncio.sleep(wait)
    RPM_WINDOW.append(time.time())


async def call_gemma(prompt: str, images: list[tuple[str, str]]) -> str | None:
    """Call Gemini with prompt + one or more images [(b64, mime), ...]."""
    await rate_limit()
    parts: list[dict] = [{"text": prompt}]
    for img_b64, mime_type in images:
        parts.append({"inline_data": {"mime_type": mime_type, "data": img_b64}})
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096},
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{GEMMA_URL}?key={GEMMA_API_KEY}", json=payload)
            if resp.status_code == 429:
                logger.warning("    Rate limited (429) — waiting 60s")
                await asyncio.sleep(60)
                resp = await client.post(f"{GEMMA_URL}?key={GEMMA_API_KEY}", json=payload)
            if resp.status_code != 200:
                logger.warning(f"    Gemma API error: {resp.status_code} {resp.text[:200]}")
                return None
            data = resp.json()
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return text.strip() if text else None
    except httpx.TimeoutException:
        logger.warning("    Gemma timeout (60s)")
        return None
    except Exception as e:
        logger.error(f"    Gemma error: {e}")
        return None


def parse_json_response(text: str) -> dict | None:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                pass
    logger.warning(f"    JSON parse failed: {text[:200]}")
    return None


async def process_document(conn: asyncpg.Connection, doc: dict, table: str, dry_run: bool) -> bool:
    doc_id = doc["id"]
    doc_type = doc["document_type"] or "other"
    file_name = doc["file_name"] or "unknown"
    drive_file_id = doc["google_drive_file_id"]

    logger.info(f"  [{doc_id}] {file_name} ({doc_type})")

    if not dry_run:
        await conn.execute(f"UPDATE {table} SET ocr_status = 'processing', updated_at = NOW() WHERE id = $1", doc_id)

    file_bytes = await download_from_drive(drive_file_id)
    if not file_bytes:
        if not dry_run:
            await conn.execute(f"UPDATE {table} SET ocr_status = 'failed', updated_at = NOW() WHERE id = $1", doc_id)
        return False

    images = file_to_base64_images(file_bytes, file_name)
    if not images:
        logger.warning(f"    ✗ Unsupported file type")
        if not dry_run:
            await conn.execute(f"UPDATE {table} SET ocr_status = 'skipped', updated_at = NOW() WHERE id = $1", doc_id)
        return False

    # Determine prompt — prefer filename-based classification
    normalized = DOC_TYPE_ALIASES.get(doc_type.lower(), doc_type.lower())
    fname_lower = file_name.lower()
    if "profil" in fname_lower and "perseroan" in fname_lower:
        normalized = "company_profile"
    elif "akta" in fname_lower:
        normalized = "akta_pendirian"
    elif "nib" in fname_lower or "oss" in fname_lower:
        normalized = "nib"
    elif "npwp" in fname_lower:
        normalized = "npwp"
    elif "passport" in fname_lower or "paspor" in fname_lower:
        normalized = "passport"
    elif ("sk " in fname_lower or "sk_" in fname_lower) and ("ahu" in fname_lower or "kemen" in fname_lower or "pendirian" in fname_lower or "perubahan" in fname_lower):
        normalized = "sk_decree"
    elif "kitas" in fname_lower or "itas" in fname_lower:
        normalized = "kitas"
    prompt = PROMPTS.get(normalized, DEFAULT_PROMPT)

    t0 = time.time()
    raw = await call_gemma(prompt, images)
    elapsed = time.time() - t0

    ocr_result = parse_json_response(raw)

    if isinstance(ocr_result, list):
        if len(ocr_result) == 1 and isinstance(ocr_result[0], dict):
            ocr_result = ocr_result[0]
        else:
            ocr_result = {"items": ocr_result}

    if ocr_result and isinstance(ocr_result, dict):
        keys_preview = list(ocr_result.keys())[:5]
        logger.info(f"    ✓ {elapsed:.1f}s — {keys_preview}")
        if not dry_run:
            await conn.execute(
                f"UPDATE {table} SET ocr_status = 'completed', ocr_extracted_data = $1::jsonb, updated_at = NOW() WHERE id = $2",
                json.dumps(ocr_result), doc_id)
        return True
    else:
        logger.warning(f"    ✗ {elapsed:.1f}s — no structured data")
        if not dry_run:
            await conn.execute(f"UPDATE {table} SET ocr_status = 'failed', updated_at = NOW() WHERE id = $1", doc_id)
        return False


async def ensure_ocr_columns(conn: asyncpg.Connection, table: str) -> None:
    existing = await conn.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name = $1", table)
    cols = {r["column_name"] for r in existing}
    if "ocr_status" not in cols:
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN ocr_status VARCHAR(20) DEFAULT NULL")
    if "ocr_extracted_data" not in cols:
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN ocr_extracted_data JSONB DEFAULT NULL")


async def main(dry_run: bool, batch_size: int, doc_type: str | None, table: str, pdf_only: bool = False, company_min: int = 0, company_max: int = 999999) -> None:
    logger.info(f"{'DRY RUN — ' if dry_run else ''}OCR Pipeline (Gemini 2.5 Flash Lite)")
    logger.info(f"Table: {table}, Batch: {batch_size}, Type: {doc_type or 'all'}, PDF only: {pdf_only}, Company range: {company_min}-{company_max}")

    conn = await asyncpg.connect(DB)

    try:
        await ensure_ocr_columns(conn, table)

        conditions = ["(ocr_status IS NULL OR ocr_status = 'pending')", "google_drive_file_id IS NOT NULL"]
        if table == "company_documents":
            conditions.extend([f"company_id >= {company_min}", f"company_id <= {company_max}"])
        if table == "company_documents":
            select = "id, company_id, document_type, google_drive_file_id, file_name"
        else:
            select = "id, client_id, document_type, file_id as google_drive_file_id, file_name"
        if doc_type:
            conditions.append(f"document_type = '{doc_type}'")
        if pdf_only:
            conditions.append("LOWER(file_name) LIKE '%.pdf'")

        if pdf_only and not dry_run:
            skipped = await conn.execute(
                f"""UPDATE {table} SET ocr_status = 'skipped'
                    WHERE (ocr_status IS NULL OR ocr_status = 'pending')
                    AND google_drive_file_id IS NOT NULL
                    AND LOWER(file_name) NOT LIKE '%.pdf'
                    {f"AND document_type = '{doc_type}'" if doc_type else ''}""")
            logger.info(f"Bulk-skipped non-PDF files: {skipped}")

        order = "company_id, id" if table == "company_documents" else "client_id, id"
        query = f"SELECT {select} FROM {table} WHERE {' AND '.join(conditions)} ORDER BY {order} LIMIT $1"
        docs = await conn.fetch(query, batch_size)
        logger.info(f"Found {len(docs)} documents to process")

        if not docs:
            return

        stats = {"ok": 0, "fail": 0, "companies_done": 0}
        t_start = time.time()
        current_company = None

        for i, doc in enumerate(docs):
            doc_dict = dict(doc)
            entity_id = doc_dict.get("company_id") or doc_dict.get("client_id")

            if entity_id != current_company:
                if current_company is not None:
                    stats["companies_done"] += 1
                current_company = entity_id
                if table == "company_documents":
                    cname = await conn.fetchval("SELECT company_name FROM companies WHERE id = $1", entity_id)
                else:
                    cname = await conn.fetchval("SELECT full_name FROM clients WHERE id = $1", entity_id)
                logger.info(f"\n📂 Company #{entity_id}: {cname or 'unknown'}")

            try:
                success = await process_document(conn, doc_dict, table, dry_run)
                if success:
                    stats["ok"] += 1
                else:
                    stats["fail"] += 1
            except Exception as e:
                logger.error(f"    ERROR doc {doc['id']}: {e}")
                stats["fail"] += 1

            if (i + 1) % 50 == 0:
                elapsed = time.time() - t_start
                rate = (i + 1) / elapsed * 60
                logger.info(f"\n--- {i+1}/{len(docs)} | {stats['ok']} ok, {stats['fail']} fail | {stats['companies_done']} companies | {rate:.0f} docs/min ---\n")

        elapsed = time.time() - t_start
        logger.info(f"\n=== OCR SUMMARY ===")
        logger.info(f"  Processed  : {stats['ok'] + stats['fail']}")
        logger.info(f"  Successful : {stats['ok']}")
        logger.info(f"  Failed     : {stats['fail']}")
        logger.info(f"  Companies  : {stats['companies_done']}")
        logger.info(f"  Time       : {elapsed/60:.1f} min ({elapsed/(stats['ok']+stats['fail']+0.001):.1f}s/doc)")
        if dry_run:
            logger.info("  (DRY RUN)")

    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OCR Pipeline — Gemini 2.5 Flash Lite")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch", type=int, default=5000)
    parser.add_argument("--type", type=str, default=None)
    parser.add_argument("--table", type=str, default="company_documents", choices=["company_documents", "documents"])
    parser.add_argument("--pdf-only", action="store_true")
    parser.add_argument("--company-min", type=int, default=0, help="Min company_id")
    parser.add_argument("--company-max", type=int, default=999999, help="Max company_id")
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run, batch_size=args.batch, doc_type=args.type, table=args.table,
                     pdf_only=args.pdf_only, company_min=args.company_min, company_max=args.company_max))
