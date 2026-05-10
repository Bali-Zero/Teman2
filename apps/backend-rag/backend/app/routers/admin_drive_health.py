"""
Admin endpoint per verificare stato Google Drive e triggerare drive poll.
"""

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request

logger = logging.getLogger(__name__)

# Documents that belong in the frontend (schema-compliant)
# Everything else stays in Drive only
SCHEMA_KEYWORDS: dict[str, list[str]] = {
    "personal": [
        "passport",
        "paspor",
        "pport",
        "photo",
        "foto",
        "selfie",
        "foto_wajah",
        "address",
        "alamat",
        "ktp",
        "id card",
        "domicile",
    ],
    "immigration": [
        "kitas",
        "kitap",
        "itas",
        "visa",
        "voa",
        "b211",
        "e-visa",
        "evisa",
        "imk",
        "itk",
        "imta",
        "rptka",
        "work permit",
        "stay permit",
        "telex",
        "vitas",
        "merp",
        "sktt",
    ],
    "pma": [
        "akta",
        "pendirian",
        "perubahan",
        "deed",
        "nib",
        "oss",
        "berusaha",
        "npwp",
        "sk ",
        "sk_",
        "sk-",
        "kemenkumham",
        "menkumham",
        "profile perseroan",
        "profil perusahaan",
        "company profile",
    ],
    "tax": ["spt", "lkpm", "pajak", "pph", "ppn", "bpjs", "bukti potong"],
    "family": [
        "family",
        "spouse",
        "wife",
        "husband",
        "child",
        "son",
        "daughter",
        "moglie",
        "marito",
        "figlio",
        "figlia",
        "marriage",
        "nikah",
        "birth",
        "kelahiran",
        "kartu keluarga",
    ],
}


def _is_schema_compliant(filename: str) -> tuple[str | None, str | None]:
    """Return (category, keyword) if file belongs in frontend, else (None, None)."""
    fn = filename.lower().replace("_", " ").replace("-", " ")
    is_family = any(kw in fn for kw in SCHEMA_KEYWORDS["family"])
    for cat, keywords in SCHEMA_KEYWORDS.items():
        if cat == "family":
            continue
        for kw in keywords:
            if kw in fn:
                return ("family" if is_family else cat), kw
    return None, None


def _infer_type(filename: str) -> str:
    """Quick document type from filename."""
    fn = filename.lower()
    if "passport" in fn or "paspor" in fn:
        return "passport"
    if "kitas" in fn or "kitap" in fn:
        return "kitas"
    if any(k in fn for k in ["visa", "voa", "b211", "evisa", "e-visa"]):
        return "visa"
    if "imk" in fn:
        return "imk"
    if "itk" in fn:
        return "itk"
    if "akta" in fn:
        return "akta"
    if "nib" in fn or "berusaha" in fn or "oss" in fn:
        return "nib"
    if "npwp" in fn:
        return "npwp"
    if "spt" in fn:
        return "spt"
    if "lkpm" in fn:
        return "lkpm"
    if any(k in fn for k in ["sk ", "sk_", "kemenkumham"]):
        return "sk"
    if "profile perseroan" in fn or "company profile" in fn:
        return "profile_perseroan"
    if any(k in fn for k in ["photo", "foto", "selfie"]):
        return "photo"
    if any(k in fn for k in ["address", "alamat", "ktp"]):
        return "alamat"
    return "other"


router = APIRouter(prefix="/api/admin/drive", tags=["admin"])


@router.get("/health")
async def drive_health(request: Request) -> dict[str, Any]:
    """Verifica stato Drive integration (public endpoint).

    Post-2026-05-10: primary auth is Service Account (domain-wide delegation
    impersonating zero@balizero.com), not the legacy SYSTEM OAuth token.
    Health is determined by SA reachability; OAuth SYSTEM info is reported
    informationally for debugging legacy callers but does NOT influence the
    overall status.
    """
    pool = getattr(request.app.state, "db_pool", None)

    # Primary check: Service Account reachability
    sa_working = False
    sa_error: str | None = None
    try:
        from backend.services.integrations.service_account_drive_service import (
            ServiceAccountDriveService,
        )

        sa_drive = ServiceAccountDriveService()
        # get_start_page_token is the cheapest authenticated call (no list)
        await sa_drive.get_start_page_token()
        sa_working = True
    except Exception as e:
        sa_error = str(e)[:200]

    # Informational: legacy OAuth SYSTEM token state (no longer load-bearing)
    oauth_info: dict[str, Any] = {"disabled": True, "note": "OAuth SYSTEM disabled 2026-05-10 — Drive uses Service Account"}
    if pool is not None:
        try:
            async with pool.acquire() as conn:
                table_exists = await conn.fetchval(
                    """SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'google_drive_tokens'
                    )""",
                )
                if table_exists:
                    token = await conn.fetchrow(
                        """SELECT user_id, expires_at, refresh_token IS NOT NULL as has_refresh, updated_at
                           FROM google_drive_tokens WHERE user_id = 'SYSTEM'""",
                    )
                    if token:
                        oauth_info["legacy_token_present"] = True
                        oauth_info["legacy_expires_at"] = token["expires_at"].isoformat()
        except Exception:
            # Legacy info is best-effort only
            pass

    return {
        "status": "healthy" if sa_working else "error",
        "auth_mode": "service_account",
        "service_account": {
            "working": sa_working,
            "error": sa_error,
            "delegated_user": "zero@balizero.com",
        },
        "oauth_legacy": oauth_info,
        # Backward-compat top-level field for any external monitor still keying on this
        "api_working": sa_working,
    }


@router.post("/poll")
async def trigger_drive_poll(request: Request) -> dict[str, Any]:
    """Trigger Google Drive changes poll (for cron jobs / OpenClaw automation)."""
    try:
        from backend.services.crm.drive_poll_service import poll_drive_changes

        result = await poll_drive_changes()
        processed = result.get("processed", 0)
        logger.info(f"Drive poll triggered via API: {processed} new files processed")
        return {
            "status": "ok",
            "processed": processed,
            "result": result,
        }
    except Exception as e:
        logger.error(f"Drive poll failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}


@router.post("/backfill")
async def backfill_drive_documents(
    request: Request, background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """One-time backfill: scan all client Drive folders and register schema-compliant files.

    Runs in background. Only adds files NOT already in the documents table.
    Skips generic files (surat kuasa, WhatsApp images, agus.pdf, etc.).
    """
    import asyncpg

    from backend.services.integrations.service_account_drive_service import (
        ServiceAccountDriveService,
    )

    async def _run_backfill() -> None:
        import os

        pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=3)
        drive = ServiceAccountDriveService()

        try:
            async with pool.acquire() as conn:
                clients = await conn.fetch(
                    "SELECT id, google_drive_folder_id FROM clients "
                    "WHERE google_drive_folder_id IS NOT NULL",
                )
                existing = await conn.fetch(
                    "SELECT file_id FROM documents WHERE file_id IS NOT NULL",
                )
                existing_fids = {r["file_id"] for r in existing}

            logger.info(
                f"Backfill: scanning {len(clients)} clients, {len(existing_fids)} existing docs",
            )

            added = 0
            skipped = 0
            errors = 0

            for i, cl in enumerate(clients):
                cid = cl["id"]
                folder_id = cl["google_drive_folder_id"]
                try:
                    # List all files recursively (top-level + subfolders + nested)
                    files = []
                    q = f"'{folder_id}' in parents and trashed = false"
                    top = (
                        drive.service.files()
                        .list(
                            q=q,
                            fields="files(id, name, mimeType)",
                            pageSize=100,
                            supportsAllDrives=True,
                            includeItemsFromAllDrives=True,
                        )
                        .execute()
                        .get("files", [])
                    )

                    for item in top:
                        if item["mimeType"] == "application/vnd.google-apps.folder":
                            sub_q = f"'{item['id']}' in parents and trashed = false"
                            subs = (
                                drive.service.files()
                                .list(
                                    q=sub_q,
                                    fields="files(id, name, mimeType)",
                                    pageSize=100,
                                    supportsAllDrives=True,
                                    includeItemsFromAllDrives=True,
                                )
                                .execute()
                                .get("files", [])
                            )
                            for sf in subs:
                                if sf["mimeType"] == "application/vnd.google-apps.folder":
                                    nested_q = f"'{sf['id']}' in parents and trashed = false"
                                    nested = (
                                        drive.service.files()
                                        .list(
                                            q=nested_q,
                                            fields="files(id, name)",
                                            pageSize=50,
                                            supportsAllDrives=True,
                                            includeItemsFromAllDrives=True,
                                        )
                                        .execute()
                                        .get("files", [])
                                    )
                                    for nf in nested:
                                        files.append((nf["id"], nf["name"], sf["name"]))
                                else:
                                    files.append((sf["id"], sf["name"], item["name"]))

                    for file_id, file_name, _folder_name in files:
                        if file_id in existing_fids:
                            continue

                        category, _ = _is_schema_compliant(file_name)
                        if not category:
                            skipped += 1
                            continue

                        doc_type = _infer_type(file_name)
                        url = f"https://drive.google.com/file/d/{file_id}/view?usp=drivesdk"

                        async with pool.acquire() as conn:
                            await conn.execute(
                                "INSERT INTO documents "
                                "(client_id, document_type, document_category, file_name, file_id, "
                                "google_drive_file_url, status, storage_type, ocr_status) "
                                "VALUES ($1,$2,$3,$4,$5,$6,'active','google_drive','pending') "
                                "ON CONFLICT DO NOTHING",
                                cid,
                                doc_type,
                                category,
                                file_name,
                                file_id,
                                url,
                            )
                        existing_fids.add(file_id)
                        added += 1

                except Exception as e:
                    errors += 1
                    if errors <= 5:
                        logger.warning(f"Backfill client #{cid}: {e}")

                if (i + 1) % 200 == 0:
                    logger.info(
                        f"Backfill progress: {i + 1}/{len(clients)}, +{added}, skip {skipped}",
                    )

            logger.info(
                f"Backfill DONE: {len(clients)} clients, +{added} docs, {skipped} skipped, {errors} errors",
            )
        finally:
            await pool.close()

    background_tasks.add_task(_run_backfill)
    return {"status": "started", "message": "Backfill running in background. Check logs."}
