"""
LegalFullIngestionWorker — async background worker for legal document ingestion.

Pipeline: Qdrant+KG -> Drive (SA) -> NLM bridge -> Google Sheets
Pattern: PostgreSQL SKIP LOCKED with visibility_at timeout (10 min).
"""

import asyncio
import io
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg
import httpx

from backend.core.legal_config import (
    DRIVE_LEGAL_ROOT,
    LEGAL_CATALOG_SHEET_ID,
    resolve_nb_notebook_id,
)

logger = logging.getLogger(__name__)

WORKER_INTERVAL = 10  # seconds between queue polls
VISIBILITY_TIMEOUT = "10 minutes"
NLM_BRIDGE_URL = os.getenv("NLM_BRIDGE_URL", "")
NLM_BRIDGE_KEY = os.getenv("NLM_BRIDGE_KEY", "")


async def run_worker(db_pool: asyncpg.Pool, app_state: Any) -> None:  # noqa: ANN401
    """Main worker loop. Runs forever in lifespan background task."""
    logger.info("✅ LegalFullIngestionWorker started")
    while True:
        try:
            await _process_one_job(db_pool, app_state)
        except asyncio.CancelledError:
            logger.info("🛑 LegalFullIngestionWorker cancelled — shutting down")
            return
        except Exception as e:
            logger.error(f"⚠️ Worker loop error (non-fatal): {e}", exc_info=True)
        await asyncio.sleep(WORKER_INTERVAL)


async def _claim_job(conn: asyncpg.Connection) -> asyncpg.Record | None:
    """Claim one pending job with SKIP LOCKED + visibility timeout."""
    return await conn.fetchrow(
        """
        UPDATE legal_ingest_jobs
        SET visibility_at = NOW() + $1::interval,
            updated_at    = NOW()
        WHERE id = (
            SELECT id FROM legal_ingest_jobs
            WHERE status NOT IN ('complete', 'failed')
              AND visibility_at <= NOW()
            ORDER BY created_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING *
        """,
        VISIBILITY_TIMEOUT,
    )


async def _update_job(conn: asyncpg.Connection, job_id: str, **fields: Any) -> None:
    """Update job fields + updated_at."""
    set_clauses = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(fields))
    values = list(fields.values())
    await conn.execute(
        f"UPDATE legal_ingest_jobs SET {set_clauses}, updated_at = NOW() WHERE id = $1",
        job_id,
        *values,
    )


async def _download_pdf(url: str, tipo: str, nomor: str, anno: str) -> Path:
    """Download PDF from URL to a temp file. Returns path."""
    dest = Path(tempfile.mkdtemp()) / f"{tipo}_{nomor}_{anno}.pdf"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(str(url), follow_redirects=True)
        resp.raise_for_status()
    dest.write_bytes(resp.content)
    logger.info(f"📥 Downloaded PDF: {dest} ({len(resp.content)} bytes)")
    return dest


def _build_drive_service() -> Any:
    """Build Google Drive API service using service account credentials."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("GOOGLE_SERVICE_ACCOUNT")
        if not creds_json:
            return None

        try:
            creds_dict = json.loads(creds_json)
        except json.JSONDecodeError:
            import base64
            creds_dict = json.loads(base64.b64decode(creds_json).decode())

        scopes = ["https://www.googleapis.com/auth/drive"]
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=scopes
        )
        return build("drive", "v3", credentials=credentials)
    except Exception as e:
        logger.warning(f"⚠️ Could not build Drive service: {e}")
        return None


def _drive_upload_file(
    drive_service: Any,
    file_path: Path,
    folder_id: str,
    file_name: str,
) -> dict[str, str]:
    """Upload file to Drive folder. Returns {file_id, web_view_link}."""
    from googleapiclient.http import MediaIoBaseUpload

    file_content = file_path.read_bytes()
    file_metadata = {"name": file_name, "parents": [folder_id]}
    media = MediaIoBaseUpload(
        io.BytesIO(file_content),
        mimetype="application/pdf",
        resumable=True,
    )
    uploaded = (
        drive_service.files()
        .create(body=file_metadata, media_body=media, fields="id,webViewLink")
        .execute()
    )
    return {
        "file_id": uploaded.get("id", ""),
        "web_view_link": uploaded.get(
            "webViewLink",
            f"https://drive.google.com/file/d/{uploaded.get('id', '')}/view",
        ),
    }


def _drive_get_or_create_folder(
    drive_service: Any,
    folder_name: str,
    parent_id: str,
) -> str:
    """Get or create a folder inside parent_id. Returns folder ID."""
    # Search for existing
    q = (
        f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents and trashed = false"
    )
    result = drive_service.files().list(q=q, fields="files(id)").execute()
    files = result.get("files", [])
    if files:
        return files[0]["id"]
    # Create
    folder_metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = drive_service.files().create(body=folder_metadata, fields="id").execute()
    return folder["id"]


def _drive_find_file(
    drive_service: Any,
    file_name: str,
    folder_id: str,
) -> dict[str, str] | None:
    """Find a file by exact name in a folder. Returns {file_id, web_view_link} or None."""
    q = f"name = '{file_name}' and '{folder_id}' in parents and trashed = false"
    result = drive_service.files().list(q=q, fields="files(id,webViewLink)").execute()
    files = result.get("files", [])
    if not files:
        return None
    f = files[0]
    return {
        "file_id": f.get("id", ""),
        "web_view_link": f.get("webViewLink", ""),
    }


async def _process_one_job(db_pool: asyncpg.Pool, app_state: Any) -> None:  # noqa: ANN401
    """Claim and process one job, updating status after each step."""
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            job = await _claim_job(conn)
    if not job:
        return  # Queue empty

    job_id = str(job["id"])
    tipo = job["tipo"]
    nomor = job["nomor"]
    anno = job["anno"]
    source_url = job["source_url"]
    nb_target = job["nb_target"]
    titolo = job["titolo"]
    current_status = job["status"]

    logger.info(
        f"▶️  Processing legal job {job_id} ({tipo} {nomor}/{anno}) status={current_status}"
    )

    pdf_path: Path | None = None

    try:
        # ── Step 1: Qdrant + KG ──────────────────────────────────────────────
        if current_status == "pending":
            if not source_url:
                raise ValueError("source_url is required for ingestion")

            pdf_path = await _download_pdf(source_url, tipo, nomor, anno)

            from backend.services.ingestion.legal_ingestion_service import LegalIngestionService

            service = LegalIngestionService()
            result = await service.ingest_legal_document(
                file_path=str(pdf_path),
                title=titolo,
            )
            chunks = result.get("chunks_created", 0)
            if not titolo:
                titolo = result.get("book_title", f"{tipo} {nomor}/{anno}")

            async with db_pool.acquire() as conn:
                await _update_job(
                    conn,
                    job_id,
                    status="qdrant_done",
                    qdrant_chunks=chunks,
                    titolo=titolo,
                )
            current_status = "qdrant_done"
            logger.info(f"✅ Step 1 done: {chunks} chunks ingested")

        # ── Step 2: Drive Upload ──────────────────────────────────────────────
        if current_status == "qdrant_done":
            if pdf_path is None:
                pdf_path = await _download_pdf(source_url, tipo, nomor, anno)

            canonical_name = f"{tipo}_{nomor}_{anno}.pdf"
            drive_file_id = ""
            drive_url = ""

            drive_service = await asyncio.to_thread(_build_drive_service)
            if drive_service is None:
                logger.warning("⚠️  Drive service unavailable — skipping Drive step")
                drive_file_id = "skipped"
                drive_url = ""
            else:
                root_folder_id = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "root")

                # Build folder path: PERATURAN/tipo/anno
                peraturan_id = await asyncio.to_thread(
                    _drive_get_or_create_folder, drive_service, DRIVE_LEGAL_ROOT, root_folder_id
                )
                tipo_id = await asyncio.to_thread(
                    _drive_get_or_create_folder, drive_service, tipo, peraturan_id
                )
                anno_id = await asyncio.to_thread(
                    _drive_get_or_create_folder, drive_service, anno, tipo_id
                )

                # Check idempotency
                existing = await asyncio.to_thread(
                    _drive_find_file, drive_service, canonical_name, anno_id
                )
                if existing:
                    drive_file_id = existing["file_id"]
                    drive_url = existing["web_view_link"]
                    logger.info(f"ℹ️  Drive: file already exists ({drive_file_id}), skipping")
                else:
                    upload_result = await asyncio.to_thread(
                        _drive_upload_file, drive_service, pdf_path, anno_id, canonical_name
                    )
                    drive_file_id = upload_result["file_id"]
                    drive_url = upload_result["web_view_link"]
                    logger.info(f"✅ Step 2 done: Drive file_id={drive_file_id}")

            async with db_pool.acquire() as conn:
                await _update_job(
                    conn,
                    job_id,
                    status="drive_done",
                    drive_file_id=drive_file_id,
                    drive_url=drive_url,
                )
            current_status = "drive_done"

        # ── Step 3: NLM Bridge ────────────────────────────────────────────────
        if current_status == "drive_done":
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT drive_file_id FROM legal_ingest_jobs WHERE id = $1", job_id
                )
            drive_file_id = row["drive_file_id"]

            nb_id = resolve_nb_notebook_id(nb_target)
            if not nb_id:
                raise ValueError(f"Unknown nb_target: {nb_target}")

            nlm_source_id = "skipped"
            if NLM_BRIDGE_URL and drive_file_id and drive_file_id != "skipped":
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{NLM_BRIDGE_URL}/nlm/source-add",
                        headers={"X-Bridge-Key": NLM_BRIDGE_KEY},
                        json={
                            "notebook_id": nb_id,
                            "source_type": "drive",
                            "document_id": drive_file_id,
                        },
                    )
                    resp.raise_for_status()
                    nlm_data = resp.json()
                    nlm_source_id = nlm_data.get("source_id", "")
                    logger.info(f"✅ Step 3 done: NLM source_id={nlm_source_id}")
            else:
                logger.warning("⚠️  NLM_BRIDGE_URL not set or Drive skipped — skipping NLM step")

            async with db_pool.acquire() as conn:
                await _update_job(conn, job_id, status="nlm_done", nlm_source_id=nlm_source_id)
            current_status = "nlm_done"

        # ── Step 4: Google Sheets ─────────────────────────────────────────────
        if current_status == "nlm_done":
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT titolo, drive_url, qdrant_chunks FROM legal_ingest_jobs WHERE id = $1",
                    job_id,
                )
            titolo_final = row["titolo"] or f"{tipo} {nomor}/{anno}"
            drive_url_final = row["drive_url"] or ""
            chunks_final = row["qdrant_chunks"] or 0

            sheets_row: str | None = None
            if LEGAL_CATALOG_SHEET_ID:
                sheets_service = getattr(app_state, "sheets_service", None)
                if sheets_service:
                    row_data = [
                        tipo,
                        nomor,
                        anno,
                        titolo_final,
                        drive_url_final,
                        nb_target,
                        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        chunks_final,
                    ]
                    result = await sheets_service.append_row(
                        spreadsheet_id=LEGAL_CATALOG_SHEET_ID,
                        range_name="Sheet1!A:H",
                        values=[row_data],
                    )
                    sheets_row = str(result.get("updated_range", ""))
                    logger.info(f"✅ Step 4 done: Sheets row={sheets_row}")
                else:
                    logger.warning("⚠️  sheets_service not in app_state — skipping Sheets step")
                    sheets_row = "skipped"
            else:
                logger.warning("⚠️  LEGAL_CATALOG_SHEET_ID not set — skipping Sheets step")
                sheets_row = "skipped"

            async with db_pool.acquire() as conn:
                await _update_job(conn, job_id, status="complete", sheets_row=sheets_row)
            logger.info(f"🎉 Job {job_id} complete!")

    except Exception as e:
        error_msg = f"{current_status}: {e}"
        logger.error(f"❌ Job {job_id} failed at {current_status}: {e}", exc_info=True)
        async with db_pool.acquire() as conn:
            await _update_job(conn, job_id, status="failed", error=error_msg)
    finally:
        if pdf_path and pdf_path.exists():
            try:
                pdf_path.unlink()
            except Exception:
                pass
