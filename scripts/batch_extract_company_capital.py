#!/usr/bin/env python3
"""
Batch extract company capital/shares from Profil Perseroan PDFs.
Downloads from Drive via SA, sends to Gemini CLI for extraction.
Runs 5 parallel gemini CLI sessions.
"""
import asyncio
import json
import os
import sys
import io
import time
import subprocess
import tempfile
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

DB_URL = "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag"
SA_KEY = "/Users/nuzantara/Desktop/codexyz/nuzantara-google-drive-sa-key-20260312.json"

PROMPT = """Extract from this Indonesian company document (Profil Perseroan / Akta).
Return ONLY valid JSON, no markdown, no explanation:
{
  "total_authorized_capital": <number in IDR>,
  "share_nominal_value": <number in IDR per share>,
  "kbli_codes": "<comma-separated>",
  "shareholders": [
    {"name": "<FULL NAME>", "role": "<direktur/komisaris/pemegang_saham>", "shares_count": <number>, "ownership_percentage": <number 0-100>}
  ]
}
Parse Indonesian numbers: "10.001.000.000" = 10001000000. If not found, use null."""


def download_from_drive(file_id: str, dest: str) -> bool:
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload

        creds = service_account.Credentials.from_service_account_file(
            SA_KEY, scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        service = build("drive", "v3", credentials=creds)
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        with open(dest, "wb") as f:
            f.write(fh.getvalue())
        return len(fh.getvalue()) > 500
    except Exception as e:
        logger.warning(f"Drive download failed {file_id}: {e}")
        return False


def parse_gemini_json(output: str) -> dict | None:
    """Extract JSON from gemini output, handling markdown and text wrapping."""
    if not output:
        return None
    # Try direct parse first
    try:
        return json.loads(output.strip())
    except json.JSONDecodeError:
        pass
    # Try extracting from markdown
    if "```json" in output:
        output = output.split("```json")[1].split("```")[0].strip()
    elif "```" in output:
        output = output.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        pass
    # Try finding JSON object in text
    import re
    match = re.search(r'\{[^{}]*"shareholders"[^{}]*\[.*?\].*?\}', output, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def extract_with_gemini(pdf_path: str, company_name: str) -> dict | None:
    """Call gemini CLI with the PDF file — no sandbox, yolo mode. Retry once on failure."""
    fname = os.path.basename(pdf_path)
    prompt = f"Read the file {fname} in this directory. Company: {company_name}. {PROMPT}"

    for attempt in range(2):
        try:
            result = subprocess.run(
                ["gemini", "-m", "gemini-2.5-flash", "--approval-mode", "yolo", "-p", prompt],
                capture_output=True, text=True, timeout=90,
                env={**os.environ, "NO_COLOR": "1"},
                cwd=os.path.dirname(pdf_path),
            )
            parsed = parse_gemini_json(result.stdout)
            if parsed:
                return parsed
            if attempt == 0:
                prompt = f"Read {fname}. Return ONLY raw JSON, no text. {PROMPT}"
        except subprocess.TimeoutExpired:
            logger.warning(f"Gemini timeout for {company_name} (attempt {attempt+1})")
        except Exception as e:
            logger.warning(f"Gemini error for {company_name}: {e}")
            break
    return None


async def save_to_db(company_id: int, result: dict):
    import asyncpg
    conn = await asyncpg.connect(DB_URL)
    try:
        if result.get("kbli_codes"):
            await conn.execute(
                "UPDATE companies SET kbli_code = $1 WHERE id = $2 AND (kbli_code IS NULL OR kbli_code = '')",
                str(result["kbli_codes"]), company_id,
            )
        nominal = result.get("share_nominal_value")
        for sh in result.get("shareholders", []):
            name = (sh.get("name") or "").strip().upper()
            shares = sh.get("shares_count")
            pct = sh.get("ownership_percentage")
            if not name or (not shares and not pct):
                continue
            link = None
            for part in [p for p in name.split() if len(p) > 2]:
                link = await conn.fetchrow(
                    "SELECT ccl.id, ccl.shares_count, ccl.share_nominal_value, ccl.ownership_percentage "
                    "FROM client_company_links ccl JOIN clients cl ON cl.id = ccl.client_id "
                    "WHERE ccl.company_id = $1 AND UPPER(cl.full_name) LIKE '%' || $2 || '%' LIMIT 1",
                    company_id, part,
                )
                if link:
                    break
            if not link:
                continue
            sets, params, idx = [], [], 1
            if shares and (link["shares_count"] is None or link["shares_count"] == 0):
                sets.append(f"shares_count = ${idx}"); params.append(int(shares)); idx += 1
            if nominal and (link["share_nominal_value"] is None or float(link["share_nominal_value"] or 0) == 0):
                sets.append(f"share_nominal_value = ${idx}"); params.append(float(nominal)); idx += 1
            if pct and (link["ownership_percentage"] is None or float(link["ownership_percentage"] or 0) == 0):
                sets.append(f"ownership_percentage = ${idx}"); params.append(float(pct)); idx += 1
            if sets:
                params.append(link["id"])
                await conn.execute(f"UPDATE client_company_links SET {', '.join(sets)} WHERE id = ${idx}", *params)
    finally:
        await conn.close()


async def process_one(company: dict, semaphore: asyncio.Semaphore, tmpdir: str) -> bool:
    async with semaphore:
        cid = company["company_id"]
        name = company["company_name"]
        pdf_path = os.path.join(tmpdir, f"{cid}.pdf")

        loop = asyncio.get_event_loop()
        ok = await loop.run_in_executor(None, download_from_drive, company["file_id"], pdf_path)
        if not ok:
            return False

        result = await loop.run_in_executor(None, extract_with_gemini, pdf_path, name)
        if not result:
            return False

        await save_to_db(cid, result)
        sh_count = len(result.get("shareholders", []))
        cap = result.get("total_authorized_capital")
        logger.info(f"✓ {name} — {sh_count} shareholders, capital={cap}")

        try:
            os.unlink(pdf_path)
        except OSError:
            pass
        return True


async def main():
    import asyncpg
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
    concurrency = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    conn = await asyncpg.connect(DB_URL)
    rows = await conn.fetch("""
        SELECT DISTINCT c.id as company_id, c.company_name,
               cd.google_drive_file_id as file_id
        FROM companies c
        JOIN client_company_links ccl ON ccl.company_id = c.id
        JOIN company_documents cd ON cd.company_id = c.id
        WHERE (cd.document_type = 'company_profile' OR cd.file_name ILIKE '%%profil%%')
        AND c.id NOT IN (
            SELECT DISTINCT company_id FROM client_company_links
            WHERE shares_count IS NOT NULL AND shares_count > 0
        )
        ORDER BY c.id
    """)
    await conn.close()

    companies = [dict(r) for r in rows][:limit]
    logger.info(f"Processing {len(companies)} companies (concurrency={concurrency})")

    semaphore = asyncio.Semaphore(concurrency)
    start = time.time()

    tmpdir = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".gemini", "tmp", "company_pdfs")
    os.makedirs(tmpdir, exist_ok=True)
    if True:
        results = await asyncio.gather(
            *[process_one(c, semaphore, tmpdir) for c in companies],
            return_exceptions=True,
        )

    success = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if r is not True)

    conn = await asyncpg.connect(DB_URL)
    final = await conn.fetchval("SELECT COUNT(DISTINCT company_id) FROM client_company_links WHERE shares_count > 0")
    await conn.close()

    logger.info(f"\n=== Complete in {time.time() - start:.0f}s ===")
    logger.info(f"Success: {success}, Failed: {failed}")
    logger.info(f"Companies with capital data: {final} / 736")


if __name__ == "__main__":
    asyncio.run(main())
