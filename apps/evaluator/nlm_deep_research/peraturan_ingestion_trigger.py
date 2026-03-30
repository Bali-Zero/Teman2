"""
Peraturan Ingestion Trigger

For every Indonesian regulation in the Google Sheet 'list peraturan':
  1. Read rows with Status=PENDING (or empty)
  2. Download PDF from official URL (if available)
  3. POST to /api/legal/upload on Fly.io backend (RAG + KG pipeline)
  4. Save PDF to Google Drive PERATURAN folder via SA
  5. Add as source to NotebookLM NB-6
  6. Update Sheet row with Status=INGESTED, Drive_File_ID, timestamp

Sheet: 1Je7eAK3ya_P5yY9L_JtnwRzkTDrucnzgZ4PvvWlb2us
PERATURAN folder: 1jcLQ6slWAeQupE8jQjp4EFjAfwlNfteM
NB-6 notebook: 85207af3-352f-4554-8d2a-18f42cc541ba

Auth:
  - Google: GOOGLE_SERVICE_ACCOUNT_JSON env var (SA credentials)
  - Backend: X-API-Key header (SCRAPER_API_KEY env var, default internal-scraper-key)

Run:
  python -m apps.evaluator.nlm_deep_research.peraturan_ingestion_trigger [--dry-run] [--row N]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────

SHEET_ID = "1Je7eAK3ya_P5yY9L_JtnwRzkTDrucnzgZ4PvvWlb2us"
PERATURAN_FOLDER_ID = "1jcLQ6slWAeQupE8jQjp4EFjAfwlNfteM"
NB6_NOTEBOOK_ID = "85207af3-352f-4554-8d2a-18f42cc541ba"

BACKEND_URL = os.getenv("BACKEND_URL", "https://nuzantara-rag.fly.dev")
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY", "internal-scraper-key")

# Column indices (0-based), matches Sheet1 structure
COL_NOME = 0          # A — Nome / full title
COL_TIPO = 1          # B — Tipo (UU, PP, Perpres, Permenaker, etc.)
COL_CATEGORIA = 2     # C — Categoria
COL_ANNO = 3          # D — Anno
COL_SINTESI_IT = 4    # E — Breve sintesi IT
COL_CATEGORIA_EN = 5  # F — Categoria EN
COL_SINTESI_EN = 6    # G — Breve sintesi EN
COL_STATUS = 7        # H — Status (PENDING / INGESTED / ERROR / SKIPPED)
COL_URL = 8           # I — URL PDF ufficiale
COL_DRIVE_FILE_ID = 9 # J — Drive File ID (after ingestion)
COL_TIMESTAMP = 10    # K — Ingestion timestamp

SHEET_RANGE_READ = "Sheet1!A2:K1000"  # Skip header row
SHEET_RANGE_WRITE = "Sheet1"

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# HTTP client timeout for large PDF downloads
DOWNLOAD_TIMEOUT = 120  # seconds
UPLOAD_TIMEOUT = 300    # seconds for legal ingestion (OCR + KG can be slow)

# Indonesian government PDF sources — official portals for regex/URL construction
JDIH_BASE_URLS = [
    "https://jdih.kemenkeu.go.id",
    "https://jdih.kemnaker.go.id",
    "https://jdih.bkpm.go.id",
    "https://jdih.menpan.go.id",
    "https://peraturan.go.id",
    "https://jdih.setkab.go.id",
]

# ─── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class RegulationRow:
    """Represents one row from the peraturan sheet."""

    row_index: int  # 1-based (for Sheets API)
    nome: str
    tipo: str
    categoria: str
    anno: str
    sintesi_it: str
    categoria_en: str
    sintesi_en: str
    status: str
    url: str
    drive_file_id: str
    timestamp: str

    @property
    def is_pending(self) -> bool:
        s = self.status.strip().upper()
        return s in ("", "PENDING", "DA INGESTIONARE")

    @property
    def display_name(self) -> str:
        if self.nome:
            return self.nome[:80]
        return f"{self.tipo} {self.anno}"

    @property
    def safe_filename(self) -> str:
        """Sanitized filename for temp/Drive storage."""
        name = self.nome or f"{self.tipo}_{self.anno}"
        safe = "".join(c if c.isalnum() or c in " -_." else "_" for c in name)
        return safe[:100].strip() + ".pdf"


@dataclass
class IngestionResult:
    """Result of a single row ingestion."""

    row: RegulationRow
    success: bool
    drive_file_id: str = ""
    qdrant_chunks: int = 0
    nlm_added: bool = False
    error: str = ""
    skipped: bool = False
    skip_reason: str = ""


# ─── Google credentials ───────────────────────────────────────────────────────


def _get_google_credentials() -> service_account.Credentials:
    """Load SA credentials from GOOGLE_SERVICE_ACCOUNT_JSON env var."""
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not raw:
        # Try file path fallback
        path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if path and Path(path).exists():
            return service_account.Credentials.from_service_account_file(
                path, scopes=GOOGLE_SCOPES
            )
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON env var missing. "
            "Set it to the SA JSON credentials string."
        )

    # Handle base64-encoded JSON
    if not raw.strip().startswith("{"):
        import base64
        raw = base64.b64decode(raw).decode()

    info = json.loads(raw)
    return service_account.Credentials.from_service_account_info(
        info, scopes=GOOGLE_SCOPES
    )


# ─── Sheet operations ─────────────────────────────────────────────────────────


def _read_sheet_rows(sheets_svc) -> list[RegulationRow]:
    """Read all regulation rows from Sheet1."""
    result = (
        sheets_svc.spreadsheets()
        .values()
        .get(spreadsheetId=SHEET_ID, range=SHEET_RANGE_READ)
        .execute()
    )
    rows = result.get("values", [])
    parsed: list[RegulationRow] = []

    def _cell(r: list, idx: int) -> str:
        return r[idx].strip() if idx < len(r) else ""

    for i, row_data in enumerate(rows):
        parsed.append(
            RegulationRow(
                row_index=i + 2,  # +2: 1-based + skip header
                nome=_cell(row_data, COL_NOME),
                tipo=_cell(row_data, COL_TIPO),
                categoria=_cell(row_data, COL_CATEGORIA),
                anno=_cell(row_data, COL_ANNO),
                sintesi_it=_cell(row_data, COL_SINTESI_IT),
                categoria_en=_cell(row_data, COL_CATEGORIA_EN),
                sintesi_en=_cell(row_data, COL_SINTESI_EN),
                status=_cell(row_data, COL_STATUS),
                url=_cell(row_data, COL_URL),
                drive_file_id=_cell(row_data, COL_DRIVE_FILE_ID),
                timestamp=_cell(row_data, COL_TIMESTAMP),
            )
        )

    return parsed


def _update_sheet_row(
    sheets_svc,
    row: RegulationRow,
    status: str,
    drive_file_id: str = "",
    error: str = "",
) -> None:
    """Update status columns for a single row."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    status_value = status
    if error and status == "ERROR":
        status_value = f"ERROR: {error[:80]}"

    # Range: columns H, J, K (Status, Drive_File_ID, Timestamp)
    range_h = f"Sheet1!H{row.row_index}"
    range_j = f"Sheet1!J{row.row_index}"
    range_k = f"Sheet1!K{row.row_index}"

    body = {
        "valueInputOption": "RAW",
        "data": [
            {"range": range_h, "values": [[status_value]]},
            {"range": range_j, "values": [[drive_file_id]]},
            {"range": range_k, "values": [[ts]]},
        ],
    }
    sheets_svc.spreadsheets().values().batchUpdate(
        spreadsheetId=SHEET_ID, body=body
    ).execute()
    logger.info(f"  Sheet row {row.row_index} updated → {status_value}")


def _ensure_sheet_headers(sheets_svc) -> None:
    """Ensure columns H, I, J, K have headers (add if missing)."""
    result = (
        sheets_svc.spreadsheets()
        .values()
        .get(spreadsheetId=SHEET_ID, range="Sheet1!A1:K1")
        .execute()
    )
    headers = result.get("values", [[]])[0] if result.get("values") else []

    new_headers = list(headers)
    while len(new_headers) < 11:
        new_headers.append("")

    changed = False
    if new_headers[COL_STATUS] != "Status":
        new_headers[COL_STATUS] = "Status"
        changed = True
    if new_headers[COL_URL] != "URL PDF":
        new_headers[COL_URL] = "URL PDF"
        changed = True
    if new_headers[COL_DRIVE_FILE_ID] != "Drive_File_ID":
        new_headers[COL_DRIVE_FILE_ID] = "Drive_File_ID"
        changed = True
    if new_headers[COL_TIMESTAMP] != "Ingestion_Timestamp":
        new_headers[COL_TIMESTAMP] = "Ingestion_Timestamp"
        changed = True

    if changed:
        sheets_svc.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range="Sheet1!A1:K1",
            valueInputOption="RAW",
            body={"values": [new_headers]},
        ).execute()
        logger.info("Sheet headers updated (added Status/URL/Drive_File_ID/Timestamp)")


# ─── PDF download ─────────────────────────────────────────────────────────────


def _is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def _download_pdf(url: str, dest_path: Path) -> bool:
    """Download a PDF from a URL to dest_path. Returns True on success."""
    if not _is_valid_url(url):
        return False

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; Nuzantara-LegalBot/1.0; "
            "+https://balizero.com/legal-bot)"
        ),
        "Accept": "application/pdf,*/*",
    }

    try:
        with httpx.Client(follow_redirects=True, timeout=DOWNLOAD_TIMEOUT) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            content = response.content

            # Validate it's actually a PDF
            if not content.startswith(b"%PDF") and "pdf" not in content_type.lower():
                logger.warning(f"  URL returned non-PDF content-type: {content_type}")
                # Still save it and let the backend handle it
                if len(content) < 1000:
                    return False

            dest_path.write_bytes(content)
            logger.info(f"  Downloaded {len(content):,} bytes → {dest_path.name}")
            return True

    except httpx.HTTPStatusError as e:
        logger.warning(f"  HTTP {e.response.status_code} downloading {url}")
        return False
    except Exception as e:
        logger.warning(f"  Download failed: {e}")
        return False


# ─── Backend ingestion ────────────────────────────────────────────────────────


def _ingest_to_backend(pdf_path: Path, row: RegulationRow) -> dict:
    """
    POST the PDF to /api/legal/upload on Fly.io.
    Returns the JSON response dict (success + chunk count).
    """
    title = row.nome or f"{row.tipo} {row.anno}"

    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        params: dict = {}
        if title:
            params["title"] = title
        # Always tier A for national regulations, B for local
        tipo_upper = row.tipo.upper()
        if tipo_upper in ("UU", "PP", "PERPRES", "PERPU"):
            params["tier"] = "A"
        elif tipo_upper in ("PERMENAKER", "PERMEN", "PERMEN KEUANGAN", "PMK", "KMK"):
            params["tier"] = "B"
        else:
            params["tier"] = "B"

        with httpx.Client(timeout=UPLOAD_TIMEOUT) as client:
            response = client.post(
                f"{BACKEND_URL}/api/legal/upload",
                files=files,
                params=params,
                headers={"X-API-Key": SCRAPER_API_KEY},
            )
            response.raise_for_status()
            return response.json()


# ─── Drive upload ─────────────────────────────────────────────────────────────


def _upload_to_drive(drive_svc, pdf_path: Path, row: RegulationRow) -> str:
    """
    Upload PDF to PERATURAN folder in Google Drive via SA.
    Returns the Drive file ID.
    """
    title = row.nome or f"{row.tipo} {row.anno}"
    # Build a descriptive filename: TIPO_ANNO_SanitizedName.pdf
    safe_name = "".join(
        c if c.isalnum() or c in " -_" else "_" for c in title
    )[:80]
    drive_filename = f"{row.tipo}_{row.anno}_{safe_name}.pdf".replace(" ", "_")

    file_metadata = {
        "name": drive_filename,
        "parents": [PERATURAN_FOLDER_ID],
        "description": (
            f"{title}\n"
            f"Tipo: {row.tipo}\n"
            f"Anno: {row.anno}\n"
            f"Categoria: {row.categoria}\n"
            f"Ingested: {datetime.now(timezone.utc).isoformat()}"
        ),
    }
    media = MediaFileUpload(str(pdf_path), mimetype="application/pdf", resumable=True)

    file_obj = (
        drive_svc.files()
        .create(body=file_metadata, media_body=media, fields="id, name, webViewLink")
        .execute()
    )
    drive_id = file_obj.get("id", "")
    logger.info(f"  Drive upload OK → {drive_filename} (id={drive_id})")
    return drive_id


# ─── NLM source addition ──────────────────────────────────────────────────────


def _add_to_nlm_nb6(row: RegulationRow, drive_file_id: str) -> bool:
    """
    Add the regulation as a source to NLM NB-6.
    Uses the NLM bridge if available, falls back silently.
    """
    try:
        from apps.evaluator.nlm_deep_research.nlm_bridge import NLMBridge  # type: ignore

        bridge = NLMBridge()
        # Use the Drive file URL as source if we have a file ID
        if drive_file_id:
            source_url = f"https://drive.google.com/file/d/{drive_file_id}/view"
        elif row.url:
            source_url = row.url
        else:
            logger.info("  NLM: no URL available, skipping")
            return False

        result = bridge.add_source_to_notebook(
            notebook_id=NB6_NOTEBOOK_ID,
            source_url=source_url,
            title=row.nome or f"{row.tipo} {row.anno}",
        )
        success = bool(result and result.get("success"))
        if success:
            logger.info(f"  NLM NB-6 source added: {row.nome[:50]}")
        else:
            logger.info(f"  NLM NB-6 add returned: {result}")
        return success

    except ImportError:
        logger.debug("  NLM bridge not available, skipping NLM step")
        return False
    except Exception as e:
        logger.warning(f"  NLM add failed (non-blocking): {e}")
        return False


# ─── Main ingestion loop ──────────────────────────────────────────────────────


def run(dry_run: bool = False, row_filter: Optional[int] = None) -> None:
    """
    Main entry point.

    Args:
        dry_run: If True, read sheet and log what would happen without writing.
        row_filter: If set, only process this specific row_index.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    logger.info("=" * 60)
    logger.info("Peraturan Ingestion Trigger starting")
    logger.info(f"  backend: {BACKEND_URL}")
    logger.info(f"  sheet:   {SHEET_ID}")
    logger.info(f"  drive:   {PERATURAN_FOLDER_ID}")
    logger.info(f"  dry_run: {dry_run}")
    logger.info("=" * 60)

    # 1. Build Google services
    try:
        creds = _get_google_credentials()
    except RuntimeError as e:
        logger.error(f"Google credentials error: {e}")
        sys.exit(1)

    sheets_svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
    drive_svc = build("drive", "v3", credentials=creds, cache_discovery=False)

    # 2. Ensure sheet columns exist
    if not dry_run:
        try:
            _ensure_sheet_headers(sheets_svc)
        except Exception as e:
            logger.warning(f"Could not update sheet headers: {e}")

    # 3. Read rows
    try:
        all_rows = _read_sheet_rows(sheets_svc)
    except HttpError as e:
        logger.error(f"Sheet read error: {e}")
        sys.exit(1)

    logger.info(f"Sheet has {len(all_rows)} regulation rows")

    # 4. Filter to pending
    if row_filter is not None:
        pending = [r for r in all_rows if r.row_index == row_filter]
        logger.info(f"Row filter active: processing row {row_filter} only")
    else:
        pending = [r for r in all_rows if r.is_pending]

    if not pending:
        logger.info("No pending rows to ingest. All done.")
        return

    logger.info(f"Found {len(pending)} pending row(s)")

    # 5. Process each row
    results: list[IngestionResult] = []

    for row in pending:
        logger.info(f"\n[Row {row.row_index}] {row.display_name}")
        result = IngestionResult(row=row, success=False)

        if dry_run:
            logger.info(f"  DRY RUN: would process — url={row.url or '(none)'}")
            result.skipped = True
            result.skip_reason = "dry_run"
            results.append(result)
            continue

        # 5a. Download PDF
        if not row.url:
            logger.info("  No URL in sheet — skipping (mark as SKIPPED_NO_URL)")
            _update_sheet_row(sheets_svc, row, "SKIPPED_NO_URL")
            result.skipped = True
            result.skip_reason = "no_url"
            results.append(result)
            continue

        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = Path(tmp_dir) / row.safe_filename
            downloaded = _download_pdf(row.url, pdf_path)

            if not downloaded:
                logger.warning(f"  Could not download PDF from {row.url}")
                _update_sheet_row(sheets_svc, row, "ERROR", error="download_failed")
                result.error = "download_failed"
                results.append(result)
                continue

            # 5b. Ingest to backend (Qdrant + KG)
            try:
                ingest_resp = _ingest_to_backend(pdf_path, row)
                chunks = ingest_resp.get("chunks_created", 0)
                result.qdrant_chunks = chunks
                logger.info(
                    f"  Backend ingestion OK → {chunks} chunks "
                    f"({ingest_resp.get('book_title', '')})"
                )
            except httpx.HTTPStatusError as e:
                err = f"backend_{e.response.status_code}"
                logger.error(f"  Backend ingest failed: {e.response.status_code} — {e.response.text[:200]}")
                _update_sheet_row(sheets_svc, row, "ERROR", error=err)
                result.error = err
                results.append(result)
                continue
            except Exception as e:
                logger.error(f"  Backend ingest exception: {e}")
                _update_sheet_row(sheets_svc, row, "ERROR", error=str(e)[:80])
                result.error = str(e)[:80]
                results.append(result)
                continue

            # 5c. Upload to Drive PERATURAN folder
            try:
                drive_id = _upload_to_drive(drive_svc, pdf_path, row)
                result.drive_file_id = drive_id
            except Exception as e:
                logger.warning(f"  Drive upload failed (non-blocking): {e}")
                drive_id = ""

            # 5d. Add to NLM NB-6 (non-blocking)
            result.nlm_added = _add_to_nlm_nb6(row, drive_id)

            # 5e. Update sheet row
            _update_sheet_row(
                sheets_svc, row, "INGESTED", drive_file_id=drive_id
            )
            result.success = True
            results.append(result)

        # Brief pause between rows to avoid rate limits
        time.sleep(2)

    # 6. Summary
    logger.info("\n" + "=" * 60)
    logger.info("INGESTION SUMMARY")
    logger.info("=" * 60)
    ingested = [r for r in results if r.success]
    skipped = [r for r in results if r.skipped]
    errors = [r for r in results if not r.success and not r.skipped]

    logger.info(f"  Ingested:  {len(ingested)}")
    logger.info(f"  Skipped:   {len(skipped)}")
    logger.info(f"  Errors:    {len(errors)}")

    for r in ingested:
        logger.info(
            f"  ✅ {r.row.display_name} "
            f"({r.qdrant_chunks} chunks, drive={r.drive_file_id[:20] if r.drive_file_id else 'N/A'})"
        )
    for r in errors:
        logger.info(f"  ❌ {r.row.display_name} — {r.error}")
    for r in skipped:
        logger.info(f"  ⏭  {r.row.display_name} — {r.skip_reason}")

    logger.info("=" * 60)

    if errors:
        sys.exit(1)  # Non-zero exit so cron can alert on failure


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest pending Indonesian regulations into Qdrant + Drive + NLM"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read sheet and log what would happen, without writing anything",
    )
    parser.add_argument(
        "--row",
        type=int,
        default=None,
        metavar="N",
        help="Process only this specific row index (1-based, Sheet row number)",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, row_filter=args.row)


if __name__ == "__main__":
    main()
