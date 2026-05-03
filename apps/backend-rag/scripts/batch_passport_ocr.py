"""
Batch Passport OCR — Individual_CRM
====================================
For each client with a passport in 00_Profile but no passport_number in DB:
1. Find passport file in 00_Profile
2. OCR with Gemini 2.5 Flash Lite
3. Update clients table (passport_number, nationality, DOB, expiry, gender, birthplace)

Only updates empty fields — never overwrites.

Run:
    python3 scripts/batch_passport_ocr.py [--dry-run] [--limit N] [--test N]
"""

import argparse
import asyncio
import base64
import json
import logging
import os
import re
import time

import asyncpg
import httpx

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

DB = (
    os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://")
    or "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag?sslmode=disable"
)

OAUTH_CLIENT_ID = "930328104463-m3g4gq72095rip08269kvt8s7et9ev12.apps.googleusercontent.com"
OAUTH_CLIENT_SECRET = "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"
OAUTH_REFRESH_TOKEN = "1//0gbiun0bBkNVCCgYIARAAGBASNwF-L9IrGvLMkg0QQ7fz0x98C1zyFqsCvzyijl7NjxUXoJ8K_-BAN8t-ZuQyT5uIv2iVJUPSiMA"

OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

PASSPORT_PROMPT = (
    "Extract from this passport. Return ONLY valid JSON:\n"
    '{"full_name": "", "passport_number": "", "nationality": "", '
    '"date_of_birth": "YYYY-MM-DD", "date_of_expiry": "YYYY-MM-DD", '
    '"sex": "", "place_of_birth": ""}'
)

_oauth_token: str = ""
_oauth_expiry: float = 0


async def get_oauth_token(client: httpx.AsyncClient) -> str:
    global _oauth_token, _oauth_expiry
    if _oauth_token and time.time() < _oauth_expiry - 60:
        return _oauth_token
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
    _oauth_token = data["access_token"]
    _oauth_expiry = time.time() + data.get("expires_in", 3600)
    return _oauth_token


async def find_passport_file(client: httpx.AsyncClient, client_drive_id: str) -> dict | None:
    """Find passport file in 00_Profile subfolder.

    Priority:
    1. Files named with 'passport' or 'paspor' (most reliable)
    2. Any image/PDF in 00_Profile (fallback — will OCR and discard if not a passport)
    """
    headers = {"Authorization": f"Bearer {await get_oauth_token(client)}"}

    # Find 00_Profile
    r = await client.get(
        "https://www.googleapis.com/drive/v3/files",
        headers=headers,
        params={
            "q": f"'{client_drive_id}' in parents and name = '00_Profile' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "fields": "files(id)",
            "pageSize": "1",
        },
    )
    profiles = r.json().get("files", [])
    if not profiles:
        return None

    # List all files in 00_Profile
    r2 = await client.get(
        "https://www.googleapis.com/drive/v3/files",
        headers=headers,
        params={
            "q": f"'{profiles[0]['id']}' in parents and trashed = false",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "fields": "files(id,name,mimeType)",
            "pageSize": "50",
        },
    )
    files = r2.json().get("files", [])

    # Priority 1: explicitly named passport files
    for f in files:
        name_lower = f["name"].lower()
        if "passport" in name_lower or "paspor" in name_lower:
            return f

    # Priority 2: any image or PDF (likely ID document)
    supported_mime = {"image/jpeg", "image/png", "image/jpg", "image/webp", "application/pdf"}
    for f in files:
        if f.get("mimeType") in supported_mime:
            return f

    return None


async def download_file(client: httpx.AsyncClient, file_id: str) -> bytes | None:
    headers = {"Authorization": f"Bearer {await get_oauth_token(client)}"}
    try:
        r = await client.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&supportsAllDrives=true",
            headers=headers,
            timeout=30,
        )
        if r.status_code == 200:
            return r.content
        logger.warning(f"    Download failed: {r.status_code}")
        return None
    except Exception as e:
        logger.warning(f"    Download error: {e}")
        return None


async def ocr_passport(client: httpx.AsyncClient, image_data: bytes, mime_type: str) -> dict | None:
    """OCR passport image with OpenAI GPT-4o-mini. Returns extracted dict or None."""
    img_b64 = base64.b64encode(image_data).decode()
    data_url = f"data:{mime_type};base64,{img_b64}"

    try:
        r = await client.post(
            OPENAI_URL,
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": PASSPORT_PROMPT},
                            {"type": "image_url", "image_url": {"url": data_url, "detail": "low"}},
                        ],
                    }
                ],
                "max_tokens": 300,
                "temperature": 0.1,
            },
            timeout=30,
        )

        if r.status_code == 429:
            logger.warning("    Rate limited — waiting 30s")
            await asyncio.sleep(30)
            r = await client.post(
                OPENAI_URL,
                headers={"Authorization": f"Bearer {OPENAI_KEY}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": PASSPORT_PROMPT},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": data_url, "detail": "low"},
                                },
                            ],
                        }
                    ],
                    "max_tokens": 300,
                    "temperature": 0.1,
                },
                timeout=30,
            )

        if r.status_code != 200:
            logger.warning(f"    OpenAI error: {r.status_code} {r.text[:100]}")
            return None

        resp = r.json()
        text = resp["choices"][0]["message"]["content"].strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        return json.loads(text)

    except json.JSONDecodeError:
        logger.warning("    JSON parse failed")
        return None
    except httpx.TimeoutException:
        logger.warning("    Timeout")
        return None
    except Exception as e:
        logger.warning(f"    OCR error: {e}")
        return None


def normalize_date(date_str: str) -> str | None:
    """Normalize various date formats to YYYY-MM-DD."""
    if not date_str or date_str == "YYYY-MM-DD":
        return None
    # DD-MM-YYYY or DD/MM/YYYY
    m = re.match(r"(\d{2})[/-](\d{2})[/-](\d{4})", date_str)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    # Already YYYY-MM-DD
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", date_str)
    if m:
        return date_str
    return None


async def update_client(conn: asyncpg.Connection, client_id: int, data: dict, dry_run: bool) -> int:
    """Update client fields from OCR data. Only fills empty fields. Returns count of fields updated."""
    updated = 0

    fields_map = [
        ("passport_number", data.get("passport_number"), False),
        ("nationality", data.get("nationality"), False),
        ("gender", data.get("sex", "")[:1].upper() if data.get("sex") else None, False),
        ("birthplace", data.get("place_of_birth"), False),
        ("date_of_birth", normalize_date(data.get("date_of_birth", "")), True),
        ("passport_expiry", normalize_date(data.get("date_of_expiry", "")), True),
    ]

    for col, val, is_date in fields_map:
        if not val or val == "YYYY-MM-DD":
            continue
        # Check if field is already populated
        current = await conn.fetchval(f"SELECT {col} FROM clients WHERE id = $1", client_id)
        if current is not None and str(current).strip():
            continue
        # Update
        if not dry_run:
            if is_date:
                from datetime import date as dt_date

                try:
                    d = dt_date.fromisoformat(val)
                    await conn.execute(
                        f"UPDATE clients SET {col} = $1, updated_at = NOW() WHERE id = $2",
                        d,
                        client_id,
                    )
                    updated += 1
                except ValueError:
                    pass
            else:
                await conn.execute(
                    f"UPDATE clients SET {col} = $1, updated_at = NOW() WHERE id = $2",
                    str(val).strip(),
                    client_id,
                )
                updated += 1
        else:
            updated += 1

    return updated


async def update_client_with_retry(client_id: int, data: dict, dry_run: bool) -> int:
    """Update client using fresh per-call connection with retry on tunnel drops."""
    max_attempts = 8
    for attempt in range(max_attempts):
        conn = None
        try:
            conn = await asyncpg.connect(DB, command_timeout=60)
            result = await update_client(conn, client_id, data, dry_run)
            return result
        except (asyncpg.exceptions.ConnectionDoesNotExistError, OSError, ConnectionRefusedError) as e:
            wait = min(5 * (attempt + 1), 30)
            logger.warning(f"    ⚠️ Connection error attempt {attempt+1}/{max_attempts}: {e}")
            if attempt < max_attempts - 1:
                await asyncio.sleep(wait)
        except Exception as e:
            logger.warning(f"    ⚠️ DB error for client {client_id}: {e}")
            return 0
        finally:
            if conn and not conn.is_closed():
                await conn.close()
    return 0


async def fetch_clients_with_retry(limit: int) -> list:
    """Fetch candidate clients using a fresh short-lived connection with retry."""
    max_attempts = 8
    for attempt in range(max_attempts):
        conn = None
        try:
            conn = await asyncpg.connect(DB, command_timeout=60)
            rows = await conn.fetch(
                """
                SELECT id, full_name, google_drive_folder_id
                FROM clients
                WHERE deleted_at IS NULL
                  AND google_drive_folder_id IS NOT NULL
                  AND google_drive_folder_id != ''
                  AND (passport_number IS NULL OR passport_number = '')
                  AND LENGTH(full_name) > 3
                ORDER BY id
                LIMIT $1
                """,
                limit,
            )
            return list(rows)
        except (asyncpg.exceptions.ConnectionDoesNotExistError, OSError, ConnectionRefusedError) as e:
            wait = min(5 * (attempt + 1), 30)
            logger.warning(f"Connection error attempt {attempt+1}/{max_attempts}: {e}, retrying in {wait}s")
            if attempt < max_attempts - 1:
                await asyncio.sleep(wait)
        finally:
            if conn and not conn.is_closed():
                await conn.close()
    raise RuntimeError("Failed to fetch clients after all retries")


async def main(dry_run: bool, limit: int, test: int) -> None:
    logger.info(f"{'DRY RUN — ' if dry_run else ''}Batch Passport OCR")

    # Fetch client list with fresh short-lived connection
    clients = await fetch_clients_with_retry(limit)
    logger.info(f"Clients without passport: {len(clients)}")

    if test > 0:
        clients = clients[:test]
        logger.info(f"TEST MODE: processing only {test}")

    totals = {
        "processed": 0,
        "ocr_ok": 0,
        "fields": 0,
        "no_passport_file": 0,
        "ocr_failed": 0,
        "errors": 0,
    }

    async with httpx.AsyncClient(timeout=60) as http:
        await get_oauth_token(http)

        for i, cl in enumerate(clients):
            cid = cl["id"]
            name = cl["full_name"]
            drive_id = cl["google_drive_folder_id"]

            try:
                # Find passport file
                passport_file = await find_passport_file(http, drive_id)
                if not passport_file:
                    totals["no_passport_file"] += 1
                    continue

                # Download
                file_data = await download_file(http, passport_file["id"])
                if not file_data:
                    totals["errors"] += 1
                    continue

                # Determine mime type
                mime = passport_file.get("mimeType", "image/jpeg")
                if mime == "application/pdf":
                    # Convert PDF first page to image
                    import fitz

                    doc = fitz.open(stream=file_data, filetype="pdf")
                    pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
                    file_data = pix.tobytes("png")
                    mime = "image/png"
                    doc.close()

                # OCR
                extracted = await ocr_passport(http, file_data, mime)
                if not extracted or not extracted.get("passport_number"):
                    # Retry once
                    await asyncio.sleep(2)
                    extracted = await ocr_passport(http, file_data, mime)
                if not extracted or not extracted.get("passport_number"):
                    totals["ocr_failed"] += 1
                    logger.info(f"  [{i + 1}] {name[:35]:35s} ✗ OCR failed")
                    continue

                # Update DB — fresh connection per client, with retry
                fields = await update_client_with_retry(cid, extracted, dry_run)
                totals["ocr_ok"] += 1
                totals["fields"] += fields
                totals["processed"] += 1

                logger.info(
                    f"  [{i + 1}] {name[:35]:35s} ✓ {extracted['passport_number']} +{fields} fields"
                )

            except Exception as e:
                totals["errors"] += 1
                logger.warning(f"  [{i + 1}] {name[:35]:35s} ERROR: {e}")

            if (i + 1) % 30 == 0:
                logger.info(
                    f"\n--- {i + 1}/{len(clients)} | ok={totals['ocr_ok']} fields={totals['fields']} ---\n"
                )

    logger.info(f"\n{'=' * 50}")
    logger.info(f"Batch Passport OCR {'(DRY RUN)' if dry_run else 'COMPLETE'}")
    logger.info(f"  Processed  : {totals['processed']}")
    logger.info(f"  OCR success: {totals['ocr_ok']}")
    logger.info(f"  Fields     : {totals['fields']}")
    logger.info(f"  No passport: {totals['no_passport_file']}")
    logger.info(f"  OCR failed : {totals['ocr_failed']}")
    logger.info(f"  Errors     : {totals['errors']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--test", type=int, default=0, help="Test on N clients only")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run, limit=args.limit, test=args.test))
