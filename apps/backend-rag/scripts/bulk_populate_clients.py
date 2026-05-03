"""
Bulk Population Script — Client Drive → DB
==========================================
Per ogni client con google_drive_folder_id:
  1. Legge Alamat.txt → clients.address
  2. Trova foto (jpg/png/jpeg nella root) → clients.avatar_url (Drive webViewLink)
  3. Trova 02_Company/ → crea companies + client_company_links + company_documents
  4. Trova 01_Immigration/ → personal docs (passport, KITAS, visa) → documents table
  5. Trova 03_Tax/ → personal docs (NPWP, SPT, LKPM) → documents table
  6. Trova 04_Family/ → family docs → documents table
  7. Trova 99_Misc/ → misc docs → documents table
  8. File sciolti nella root (PDF, images) → documents table

Run:
    cd apps/backend-rag
    source venv/bin/activate
    PYTHONPATH=. python3 scripts/bulk_populate_clients.py [--dry-run] [--limit N] [--client-id N]
"""

import argparse
import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import asyncpg
import httpx
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_db_env = os.getenv("DATABASE_URL", "")
DB = (
    _db_env.replace("postgres://", "postgresql://")
    if _db_env
    else "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag?sslmode=disable"
)

# Category map for document names → DB category
DOC_CATEGORY_MAP = {
    # Personal
    "passport": "passport",
    "kitas": "kitas",
    "ktp": "ktp",
    "npwp": "npwp",
    "photo": "photo",
    "foto": "photo",
    # Company
    "akta": "akta_pendirian",
    "sk_kemenkumham": "sk_decree",
    "sk kemenkumham": "sk_decree",
    "sk_kemenhumham": "sk_decree",
    "nib": "nib",
    "siup": "siup",
    "company_profile": "company_profile",
    "profile perseroan": "company_profile",
    "npwp perusahaan": "npwp",
    "npwp_perusahaan": "npwp",
    "spt": "spt",
    "neraca": "financial",
    "laporan keuangan": "financial",
}

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DOC_EXTENSIONS = {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".xlsx", ".xls"}
COMPANY_FOLDER_NAMES = {"02_company", "company", "02 company"}
FOLDER_MIME = "application/vnd.google-apps.folder"

# Personal document mapping: keyword → (document_type, document_category)
PERSONAL_DOC_MAP = {
    # Immigration
    "passport": ("passport", "immigration"),
    "kitas": ("kitas", "immigration"),
    "kitap": ("kitap", "immigration"),
    "visa": ("visa", "immigration"),
    "e-visa": ("evisa", "immigration"),
    "evisa": ("evisa", "immigration"),
    "imta": ("work_permit", "immigration"),
    "itas": ("kitas", "immigration"),
    "telex": ("telex_visa", "immigration"),
    "approval": ("approval_letter", "immigration"),
    "stay_permit": ("stay_permit", "immigration"),
    "exit_permit": ("exit_permit", "immigration"),
    # Tax
    "npwp": ("npwp_personal", "tax"),
    "lkpm": ("lkpm", "tax"),
    "spt": ("spt_personal", "tax"),
    # Personal
    "selfie": ("photo", "personal"),
    "photo": ("photo", "personal"),
    "foto": ("photo", "personal"),
    "ktp": ("ktp", "personal"),
    "cv": ("cv", "personal"),
    "resume": ("cv", "personal"),
    # Financial
    "bank": ("bank_statement", "financial"),
    "statement": ("bank_statement", "financial"),
    "rekening": ("bank_statement", "financial"),
    # Other
    "invitation": ("invitation_letter", "other"),
    "domicile": ("domicile_letter", "other"),
    "domisili": ("domicile_letter", "other"),
    "surat": ("letter", "other"),
    "contract": ("contract", "other"),
    "kontrak": ("contract", "other"),
}

# Folder name → default category override
FOLDER_CATEGORY_MAP = {
    "01_immigration": "immigration",
    "01immigration": "immigration",
    "immigration": "immigration",
    "03_tax": "tax",
    "03tax": "tax",
    "tax": "tax",
    "04_family": "family",
    "04family": "family",
    "family": "family",
    "00_profile": "personal",
    "00profile": "personal",
    "profile": "personal",
    "99_misc": "other",
    "99misc": "other",
    "misc": "other",
}


async def get_drive_access_token(conn: asyncpg.Connection) -> str:
    """Get a valid Drive access token, refreshing if needed."""
    from datetime import datetime, timedelta, timezone

    row = await conn.fetchrow(
        "SELECT access_token, refresh_token, expires_at FROM google_drive_tokens WHERE user_id = $1",
        "SYSTEM",
    )
    if not row:
        raise ValueError("No SYSTEM Drive token in DB")

    # Return existing token if still valid (>5 min remaining)
    if row["expires_at"] and row["expires_at"] > datetime.now(timezone.utc) + timedelta(minutes=5):
        return row["access_token"]

    # Refresh
    client_id = "930328104463-d39fpretk5t0lucunkovu7o0g6id5eu2.apps.googleusercontent.com"
    client_secret = "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"

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": row["refresh_token"],
                "grant_type": "refresh_token",
            },
        )

    if resp.status_code != 200:
        raise ValueError(f"Token refresh HTTP {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    token = data["access_token"]
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))

    await conn.execute(
        "UPDATE google_drive_tokens SET access_token=$1, expires_at=$2, updated_at=NOW() WHERE user_id=$3",
        token,
        expires_at,
        "SYSTEM",
    )
    return token


SA_PATH = os.path.expanduser("~/Desktop/nuzantara-9ae2756d7fcc.json")

# OAuth credentials from rclone gdrive remote (antonellosiano@gmail.com)
# These can access folders owned by all team members
OAUTH_CLIENT_ID = "930328104463-m3g4gq72095rip08269kvt8s7et9ev12.apps.googleusercontent.com"
OAUTH_CLIENT_SECRET = "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"
OAUTH_REFRESH_TOKEN = "1//0gbiun0bBkNVCCgYIARAAGBASNwF-L9IrGvLMkg0QQ7fz0x98C1zyFqsCvzyijl7NjxUXoJ8K_-BAN8t-ZuQyT5uIv2iVJUPSiMA"

_oauth_access_token: str | None = None
_oauth_token_expiry: float = 0.0


def _get_oauth_access_token() -> str:
    """Get OAuth access token, refreshing if expired."""
    import json as _json
    import time
    import urllib.parse
    import urllib.request

    global _oauth_access_token, _oauth_token_expiry

    if _oauth_access_token and time.time() < _oauth_token_expiry - 60:
        return _oauth_access_token

    data = urllib.parse.urlencode(
        {
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "refresh_token": OAUTH_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        }
    ).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        result = _json.loads(resp.read())

    _oauth_access_token = result["access_token"]
    _oauth_token_expiry = time.time() + result.get("expires_in", 3600)
    logger.info("  OAuth token refreshed")
    return _oauth_access_token


def build_drive_service(_access_token: str | None = None) -> Any:
    """Build Drive service — OAuth primary (can access all team folders), SA fallback."""
    try:
        token = _get_oauth_access_token()
        creds = Credentials(
            token=token,
            refresh_token=OAUTH_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=OAUTH_CLIENT_ID,
            client_secret=OAUTH_CLIENT_SECRET,
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception as e:
        logger.warning(f"  OAuth failed ({e}), falling back to SA")
        if os.path.exists(SA_PATH):
            import json as _json

            creds = service_account.Credentials.from_service_account_info(
                _json.load(open(SA_PATH)),
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
            return build("drive", "v3", credentials=creds, cache_discovery=False)
        raise RuntimeError("No valid credentials available")


def list_folder(service: Any, folder_id: str) -> list[dict]:
    """List all files in a folder (non-recursive)."""
    try:
        results = (
            service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="files(id, name, mimeType, webViewLink, webContentLink)",
                orderBy="name",
                pageSize=100,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        return results.get("files", [])
    except HttpError as e:
        logger.warning(f"  Drive list error for {folder_id}: {e}")
        return []


def read_text_file(service: Any, file_id: str) -> str | None:
    """Download and read a small text file from Drive."""
    try:
        content = service.files().get_media(fileId=file_id).execute()
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="replace").strip()
        return str(content).strip()
    except Exception as e:
        logger.warning(f"  Could not read file {file_id}: {e}")
        return None


def guess_category(name: str) -> str:
    """Guess company document category from filename."""
    name_lower = name.lower().replace("-", "_").replace(" ", "_")
    for key, cat in DOC_CATEGORY_MAP.items():
        key_norm = key.lower().replace("-", "_").replace(" ", "_")
        if key_norm in name_lower:
            return cat
    return "other"


def guess_personal_category(filename: str, parent_folder: str = "") -> tuple[str, str]:
    """Guess personal document (type, category) from filename and parent folder.

    Returns (document_type, document_category).
    """
    name_lower = filename.lower().replace("-", "_").replace(" ", "_")
    folder_lower = parent_folder.lower().replace("-", "_").replace(" ", "_")

    # 1. Try folder name as category context (e.g. "KITAS" subfolder inside 01_Immigration)
    for key, (doc_type, doc_cat) in PERSONAL_DOC_MAP.items():
        key_norm = key.lower().replace("-", "_").replace(" ", "_")
        if key_norm in folder_lower:
            # Subfolder name matches — use it as type, refine from filename if possible
            # But check filename too for more specific match
            for fkey, (ftype, fcat) in PERSONAL_DOC_MAP.items():
                fkey_norm = fkey.lower().replace("-", "_").replace(" ", "_")
                if fkey_norm in name_lower and fkey_norm != key_norm:
                    return ftype, fcat
            return doc_type, doc_cat

    # 2. Try filename matching
    for key, (doc_type, doc_cat) in PERSONAL_DOC_MAP.items():
        key_norm = key.lower().replace("-", "_").replace(" ", "_")
        if key_norm in name_lower:
            return doc_type, doc_cat

    # 3. Infer from parent section folder
    parent_cat = FOLDER_CATEGORY_MAP.get(folder_lower, "")
    if parent_cat:
        return "other", parent_cat

    return "other", "other"


def is_photo(file: dict) -> bool:
    name = file["name"].lower()
    mime = file.get("mimeType", "")
    ext = Path(name).suffix
    return ext in PHOTO_EXTENSIONS or mime.startswith("image/")


def is_company_folder(file: dict) -> bool:
    return file["mimeType"] == "application/vnd.google-apps.folder" and (
        file["name"].lower().strip() in COMPANY_FOLDER_NAMES
        or file["name"].strip().startswith("02_")
        or file["name"].strip().startswith("02 ")
    )


def extract_pt_name(folder_name: str, client_name: str) -> str | None:
    """Try to extract PT name from folder listing or use client name."""
    # Try to find company folder named like "PT ..."
    words = folder_name.upper()
    if words.startswith("PT ") or " PT " in words:
        return folder_name
    return None


async def process_client(
    conn: asyncpg.Connection,
    service: Any,
    client: asyncpg.Record,
    dry_run: bool,
) -> dict:
    cid = client["id"]
    name = client["full_name"]
    folder_id = client["google_drive_folder_id"]
    result = {
        "id": cid,
        "name": name,
        "address": False,
        "photo": False,
        "company": False,
        "docs": 0,
        "personal_docs": 0,
    }

    logger.info(f"[{cid}] {name} — folder {folder_id}")

    files = list_folder(service, folder_id)
    if not files:
        logger.info("  ⚠️  Empty or inaccessible folder")
        return result

    folders_count = sum(1 for f in files if f["mimeType"] == FOLDER_MIME)
    files_count = len(files) - folders_count
    logger.info(f"  📂 {folders_count} folders, {files_count} files in root")

    address_updated = False
    photo_updated = False

    # Find standard subfolders
    profile_folder = next(
        (f for f in files if f["name"].strip() in ("00_Profile", "00Profile")), None
    )
    company_folder = next((f for f in files if is_company_folder(f)), None)

    # 1. Scan root for alamat/photo (legacy structure)
    for f in files:
        fname = f["name"]
        fname_lower = fname.lower()
        if fname_lower in ("alamat.txt", "alamat.md", "address.txt") and not address_updated:
            if not client["address"]:
                text = read_text_file(service, f["id"])
                if text:
                    logger.info(f"  → address (root txt): {text[:80]}")
                    if not dry_run:
                        await conn.execute(
                            "UPDATE clients SET address = $1 WHERE id = $2", text, cid
                        )
                    address_updated = True
                    result["address"] = True
        elif is_photo(f) and not photo_updated and not client["avatar_url"]:
            url = f.get("webViewLink") or f.get("webContentLink", "")
            logger.info(f"  → avatar (root): {fname}")
            if not dry_run:
                await conn.execute("UPDATE clients SET avatar_url = $1 WHERE id = $2", url, cid)
            photo_updated = True
            result["photo"] = True

    # 2. Scan 00_Profile/ for alamat + photo
    if profile_folder:
        profile_files = list_folder(service, profile_folder["id"])
        for f in profile_files:
            fname = f["name"]
            fname_lower = fname.lower()

            # Alamat file (txt or image)
            if fname_lower.startswith("alamat") and not address_updated:
                if not client["address"]:
                    if fname_lower.endswith(".txt"):
                        text = read_text_file(service, f["id"])
                        if text:
                            logger.info(f"  → address (txt): {text[:80]}")
                            if not dry_run:
                                await conn.execute(
                                    "UPDATE clients SET address = $1 WHERE id = $2", text, cid
                                )
                            address_updated = True
                            result["address"] = True
                    else:
                        # Image — store Drive URL as reference
                        url = f.get("webViewLink", "")
                        logger.info(f"  → address (img link): {fname}")
                        if not dry_run:
                            await conn.execute(
                                "UPDATE clients SET address = $1 WHERE id = $2", url, cid
                            )
                        address_updated = True
                        result["address"] = True

            # Photo selfie / passport photo
            elif is_photo(f) and not photo_updated and not client["avatar_url"]:
                name_l = fname.lower()
                if any(kw in name_l for kw in ("selfie", "profile", "photo", "foto", "avatar")):
                    url = f.get("webViewLink") or f.get("webContentLink", "")
                    logger.info(f"  → avatar: {fname}")
                    if not dry_run:
                        await conn.execute(
                            "UPDATE clients SET avatar_url = $1 WHERE id = $2", url, cid
                        )
                    photo_updated = True
                    result["photo"] = True

    # 3. 02_Company/ → company + docs
    if company_folder:
        result["company"] = await process_company(
            conn, service, client, company_folder, dry_run, result
        )

    # 4. Personal docs from standard subfolders
    personal_folders = {
        "01_Immigration": ("01_Immigration", "01Immigration"),
        "03_Tax": ("03_Tax", "03Tax"),
        "04_Family": ("04_Family", "04Family"),
        "99_Misc": ("99_Misc", "99Misc"),
    }
    for section, name_variants in personal_folders.items():
        folder = next(
            (
                f
                for f in files
                if f["mimeType"] == FOLDER_MIME and f["name"].strip() in name_variants
            ),
            None,
        )
        if folder:
            folder_files = list_folder(service, folder["id"])
            if folder_files:
                added = await ingest_personal_docs(
                    conn,
                    service,
                    cid,
                    folder["id"],
                    section,
                    folder_files,
                    dry_run,
                )
                result["personal_docs"] += added

    # 5. Personal docs from 00_Profile/ (non-photo, non-alamat files)
    if profile_folder:
        profile_files = list_folder(service, profile_folder["id"])
        for f in profile_files:
            if f["mimeType"] == FOLDER_MIME:
                sub = list_folder(service, f["id"])
                added = await ingest_personal_docs(
                    conn,
                    service,
                    cid,
                    f["id"],
                    f["name"],
                    sub,
                    dry_run,
                )
                result["personal_docs"] += added
                continue
            fname_lower = f["name"].lower()
            ext = Path(f["name"]).suffix.lower()
            # Skip already-handled alamat/photo and non-doc files
            if fname_lower.startswith("alamat") or ext not in DOC_EXTENSIONS:
                continue
            if is_photo(f):
                continue  # photos handled above
            # Ingest as personal doc
            existing = await conn.fetchval(
                "SELECT id FROM documents WHERE client_id = $1 AND file_name = $2",
                cid,
                f["name"],
            )
            if not existing:
                doc_type, doc_cat = guess_personal_category(f["name"], "00_Profile")
                file_id = f.get("id", "")
                url = f.get("webViewLink") or f.get("webContentLink", "")
                logger.info(f"      + doc (profile): {f['name']} [{doc_type}/{doc_cat}]")
                if not dry_run:
                    await conn.execute(
                        """INSERT INTO documents (
                            client_id, document_type, document_category,
                            file_name, file_id, google_drive_file_url,
                            storage_type, uploaded_by, status, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, 'google_drive', 'bulk_population', 'active', NOW())
                        ON CONFLICT DO NOTHING""",
                        cid,
                        doc_type,
                        doc_cat,
                        f["name"],
                        file_id,
                        url,
                    )
                result["personal_docs"] += 1

    # 6. Loose root files (not folders, not alamat, not already-handled photos)
    for f in files:
        if f["mimeType"] == FOLDER_MIME:
            continue
        fname = f["name"]
        fname_lower = fname.lower()
        ext = Path(fname).suffix.lower()
        if ext not in DOC_EXTENSIONS:
            continue
        if fname_lower in ("alamat.txt", "alamat.md", "address.txt"):
            continue
        # Check if already ingested
        existing = await conn.fetchval(
            "SELECT id FROM documents WHERE client_id = $1 AND file_name = $2",
            cid,
            fname,
        )
        if existing:
            continue
        doc_type, doc_cat = guess_personal_category(fname, "")
        file_id = f.get("id", "")
        url = f.get("webViewLink") or f.get("webContentLink", "")
        logger.info(f"      + doc (root): {fname} [{doc_type}/{doc_cat}]")
        if not dry_run:
            await conn.execute(
                """INSERT INTO documents (
                    client_id, document_type, document_category,
                    file_name, file_id, google_drive_file_url,
                    storage_type, uploaded_by, status, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, 'google_drive', 'bulk_population', 'active', NOW())
                ON CONFLICT DO NOTHING""",
                cid,
                doc_type,
                doc_cat,
                fname,
                file_id,
                url,
            )
        result["personal_docs"] += 1

    return result


async def ingest_personal_docs(
    conn: asyncpg.Connection,
    service: Any,
    client_id: int,
    folder_id: str,
    section_folder: str,
    files: list[dict],
    dry_run: bool,
    depth: int = 0,
) -> int:
    """Ingest personal documents into the `documents` table.

    Recursively scans subfolders. Uses parent folder name for category inference.
    """
    if depth > 3:
        return 0

    added = 0

    for f in files:
        if f["mimeType"] == FOLDER_MIME:
            sub_files = list_folder(service, f["id"])
            added += await ingest_personal_docs(
                conn,
                service,
                client_id,
                f["id"],
                f["name"],  # pass subfolder name as context
                sub_files,
                dry_run,
                depth + 1,
            )
            continue

        name = f["name"]
        ext = Path(name).suffix.lower()
        if ext not in DOC_EXTENSIONS:
            continue

        # Skip alamat text files (handled separately)
        if name.lower() in ("alamat.txt", "alamat.md", "address.txt"):
            continue

        # Dedup check
        existing = await conn.fetchval(
            "SELECT id FROM documents WHERE client_id = $1 AND file_name = $2",
            client_id,
            name,
        )
        if existing:
            continue

        doc_type, doc_category = guess_personal_category(name, section_folder)
        file_id = f.get("id", "")
        url = f.get("webViewLink") or f.get("webContentLink", "")

        logger.info(f"      + doc: {name} [{doc_type}/{doc_category}]")
        if not dry_run:
            await conn.execute(
                """INSERT INTO documents (
                    client_id, document_type, document_category,
                    file_name, file_id, google_drive_file_url,
                    storage_type, uploaded_by, status, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, 'google_drive', 'bulk_population', 'active', NOW())
                ON CONFLICT DO NOTHING""",
                client_id,
                doc_type,
                doc_category,
                name,
                file_id,
                url,
            )
        added += 1

    return added


async def process_company(
    conn: asyncpg.Connection,
    service: Any,
    client: asyncpg.Record,
    company_folder: dict,
    dry_run: bool,
    result: dict,
) -> bool:
    cid = client["id"]
    cname = client["full_name"]

    company_files = list_folder(service, company_folder["id"])
    if not company_files:
        return False

    # 1. Try to find PT name from DB (already linked company)
    pt_name = await conn.fetchval(
        """SELECT co.company_name FROM companies co
           JOIN client_company_links l ON l.company_id = co.id
           WHERE l.client_id = $1
           ORDER BY l.is_primary DESC NULLS LAST, l.id ASC LIMIT 1""",
        cid,
    )

    # 2. Try subfolders named like "PT ..."
    if not pt_name:
        for f in company_files:
            if "folder" not in f["mimeType"]:
                continue
            name_up = f["name"].upper().strip()
            if name_up.startswith("PT ") or name_up.startswith("CV "):
                pt_name = f["name"].strip()
                break

    # 3. Try file names (e.g. AKTA PT Nils.pdf)
    if not pt_name:
        for f in company_files:
            name_up = f["name"].upper()
            if name_up.startswith("PT ") or " PT " in name_up:
                pt_name = Path(f["name"]).stem
                break

    # 4. Fallback: client name + Company
    if not pt_name:
        pt_name = f"{cname} — Company"

    logger.info(f"  → company: {pt_name}")

    # Find or create company
    company_id = await conn.fetchval(
        "SELECT id FROM companies WHERE LOWER(TRIM(company_name)) = LOWER(TRIM($1))", pt_name
    )
    if not company_id:
        first_word = pt_name.split()[1] if len(pt_name.split()) > 1 else pt_name
        company_id = await conn.fetchval(
            "SELECT id FROM companies WHERE company_name ILIKE $1 LIMIT 1",
            f"%{first_word}%",
        )

    if not company_id:
        logger.info(
            f"    ⚠️  no matching company found for '{pt_name}' — skipping (not creating placeholder)"
        )
        return False
    else:
        logger.info(f"    found existing company id={company_id}")

    # client_company_links
    if company_id and company_id != -1:
        existing_link = await conn.fetchval(
            "SELECT id FROM client_company_links WHERE client_id = $1 AND company_id = $2",
            cid,
            company_id,
        )
        if not existing_link:
            logger.info(f"    linking client {cid} → company {company_id} (role=shareholder)")
            if not dry_run:
                await conn.execute(
                    """INSERT INTO client_company_links (client_id, company_id, role, is_primary, created_at)
                       VALUES ($1, $2, 'shareholder', false, NOW())
                       ON CONFLICT DO NOTHING""",
                    cid,
                    company_id,
                )

    # company_documents — recurse into subfolders
    docs_added = 0
    docs_added += await ingest_company_docs(
        conn, service, company_id, company_folder["id"], company_files, dry_run
    )
    result["docs"] += docs_added
    return True


async def ingest_company_docs(
    conn: asyncpg.Connection,
    service: Any,
    company_id: int | None,
    folder_id: str,
    files: list[dict],
    dry_run: bool,
    depth: int = 0,
) -> int:
    if depth > 3 or not company_id or company_id == -1:
        return 0

    added = 0

    for f in files:
        if f["mimeType"] == FOLDER_MIME:
            # Recurse into sub-folder (AKTA, NIB, etc.)
            sub_files = list_folder(service, f["id"])
            added += await ingest_company_docs(
                conn, service, company_id, f["id"], sub_files, dry_run, depth + 1
            )
            continue

        # Skip non-documents
        name = f["name"]
        ext = Path(name).suffix.lower()
        if ext not in DOC_EXTENSIONS:
            continue

        url = f.get("webViewLink") or f.get("webContentLink", "")
        category = guess_category(name)

        # Check if already in company_documents
        existing = await conn.fetchval(
            "SELECT id FROM company_documents WHERE company_id = $1 AND file_name = $2",
            company_id,
            name,
        )
        if existing:
            continue

        file_id = f.get("id", "")
        logger.info(f"      + company_doc: {name} [{category}]")
        if not dry_run:
            await conn.execute(
                """INSERT INTO company_documents (
                    company_id, document_type, file_name,
                    google_drive_file_id, google_drive_file_url,
                    storage_type, uploaded_by, created_at
                ) VALUES ($1, $2, $3, $4, $5, 'google_drive', 'bulk_population', NOW())
                ON CONFLICT DO NOTHING""",
                company_id,
                category,
                name,
                file_id,
                url,
            )
        added += 1

    return added


async def main(dry_run: bool, limit: int, client_id: int | None, min_id: int = 0) -> None:
    logger.info(f"{'DRY RUN — ' if dry_run else ''}Starting bulk population")

    conn = await asyncpg.connect(DB)

    if os.path.exists(SA_PATH):
        logger.info("Using Service Account for Drive access")
        service = build_drive_service()
    else:
        logger.info("Getting Drive OAuth access token...")
        access_token = await get_drive_access_token(conn)
        logger.info("Drive token OK")
        service = build_drive_service(access_token)

    try:
        if client_id:
            clients = await conn.fetch(
                "SELECT id, full_name, google_drive_folder_id, address, avatar_url FROM clients WHERE id = $1",
                client_id,
            )
        else:
            clients = await conn.fetch(
                """SELECT id, full_name, google_drive_folder_id, address, avatar_url
                   FROM clients
                   WHERE google_drive_folder_id IS NOT NULL AND deleted_at IS NULL
                   AND id >= $2
                   ORDER BY id
                   LIMIT $1""",
                limit,
                min_id,
            )

        logger.info(f"Processing {len(clients)} clients")

        stats = {"address": 0, "photo": 0, "company": 0, "docs": 0, "personal_docs": 0, "errors": 0}

        for client in clients:
            try:
                r = await process_client(conn, service, client, dry_run)
                if r["address"]:
                    stats["address"] += 1
                if r["photo"]:
                    stats["photo"] += 1
                if r["company"]:
                    stats["company"] += 1
                stats["docs"] += r["docs"]
                stats["personal_docs"] += r["personal_docs"]
            except Exception as e:
                logger.error(f"  ERROR client {client['id']}: {e}", exc_info=True)
                stats["errors"] += 1

        logger.info("\n=== SUMMARY ===")
        logger.info(f"  Addresses updated  : {stats['address']}")
        logger.info(f"  Photos updated     : {stats['photo']}")
        logger.info(f"  Companies linked   : {stats['company']}")
        logger.info(f"  Company docs added : {stats['docs']}")
        logger.info(f"  Personal docs added: {stats['personal_docs']}")
        logger.info(f"  Errors             : {stats['errors']}")
        if dry_run:
            logger.info("  (DRY RUN — no DB changes made)")

    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no DB writes")
    parser.add_argument("--limit", type=int, default=50, help="Max clients to process (default 50)")
    parser.add_argument("--client-id", type=int, default=None, help="Process single client by ID")
    parser.add_argument(
        "--min-id", type=int, default=0, help="Start from this client ID (inclusive)"
    )
    args = parser.parse_args()

    asyncio.run(
        main(dry_run=args.dry_run, limit=args.limit, client_id=args.client_id, min_id=args.min_id)
    )
