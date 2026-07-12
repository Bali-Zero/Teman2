"""
Admin endpoint per verificare stato Google Drive e triggerare drive poll.
"""

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from backend.app.dependencies import get_current_user
from backend.app.utils.crm_utils import is_crm_admin

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


def _require_backfill_admin(user: dict[str, Any]) -> None:
    """Gate the Drive backfill trigger to admins. Raises 403 otherwise.

    Backfill writes new rows into the shared `documents` table for every
    client Drive folder scanned; it is a bulk mutation, not a read-only
    status check, so it must not be reachable by any authenticated caller.
    """
    if not is_crm_admin(user):
        raise HTTPException(status_code=403, detail="admin required")


def _env_flag(name: str, *, default: bool = False) -> bool:
    """Parse common env truthy values."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _drive_poll_api_timeout_seconds() -> float:
    """Return server-side timeout for the cron-triggered Drive poll."""
    raw_value = os.getenv("DRIVE_POLL_API_TIMEOUT_SECONDS", "100")
    try:
        timeout = float(raw_value)
    except ValueError:
        logger.warning(
            "Invalid DRIVE_POLL_API_TIMEOUT_SECONDS=%r; falling back to 100",
            raw_value,
        )
        return 100.0
    return max(5.0, min(timeout, 115.0))


def _drive_poll_api_mode() -> str:
    """Return Drive poll API mode.

    worker: HTTP only reports worker state; the Fly drive process owns polling.
    direct: legacy behavior; the request runs the poll synchronously.
    """
    raw_value = os.getenv("DRIVE_POLL_API_MODE", "worker").strip().lower()
    if raw_value in {"direct", "legacy"}:
        return "direct"
    return "worker"


def _drive_poll_worker_stale_seconds() -> int:
    raw_value = os.getenv("DRIVE_POLL_WORKER_STALE_SECONDS", "900")
    try:
        value = int(raw_value)
    except ValueError:
        logger.warning(
            "Invalid DRIVE_POLL_WORKER_STALE_SECONDS=%r; falling back to 900",
            raw_value,
        )
        return 900
    return max(60, min(value, 86_400))


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _get_request_pool(request: Request) -> Any | None:
    app = getattr(request, "app", None)
    state = getattr(app, "state", None)
    pool = getattr(state, "db_pool", None)
    if pool is not None and hasattr(pool, "acquire"):
        return pool
    return None


async def _read_drive_poll_worker_status(pool: Any | None) -> dict[str, Any]:
    """Read Drive worker heartbeat keys from system_settings."""
    stale_after_seconds = _drive_poll_worker_stale_seconds()
    if pool is None:
        return {
            "mode": "worker",
            "available": False,
            "status": "unknown",
            "healthy": False,
            "stale": False,
            "stale_after_seconds": stale_after_seconds,
            "message": "db_pool unavailable",
        }

    keys = [
        "drive_poll_worker_heartbeat_at",
        "drive_poll_worker_last_status",
        "drive_poll_worker_last_started_at",
        "drive_poll_worker_last_finished_at",
        "drive_poll_worker_last_result",
        "drive_poll_worker_last_error",
    ]
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT key, value, updated_at
                FROM system_settings
                WHERE key = ANY($1::text[])
                """,
                keys,
            )
    except Exception as e:
        logger.warning("Drive poll worker status read failed: %s", e)
        return {
            "mode": "worker",
            "available": False,
            "status": "unknown",
            "healthy": False,
            "stale": False,
            "stale_after_seconds": stale_after_seconds,
            "message": "Drive poll worker status unavailable",
        }

    values = {row["key"]: row["value"] for row in rows}
    heartbeat_at = _parse_iso_datetime(values.get("drive_poll_worker_heartbeat_at"))
    age_seconds: float | None = None
    stale = False
    if heartbeat_at is not None:
        age_seconds = max(0.0, (datetime.now(UTC) - heartbeat_at).total_seconds())
        stale = age_seconds > stale_after_seconds

    last_result: dict[str, Any] | None = None
    raw_result = values.get("drive_poll_worker_last_result")
    if raw_result:
        try:
            decoded = json.loads(raw_result)
            if isinstance(decoded, dict):
                last_result = decoded
        except Exception:
            last_result = {"raw": raw_result[:500], "parse_error": True}

    status = values.get("drive_poll_worker_last_status") or "never_seen"
    unhealthy_statuses = {"error", "timeout"}
    healthy = heartbeat_at is not None and not stale and status not in unhealthy_statuses
    return {
        "mode": "worker",
        "available": True,
        "status": status,
        "healthy": healthy,
        "stale": stale,
        "heartbeat_at": heartbeat_at.isoformat() if heartbeat_at else None,
        "heartbeat_age_seconds": age_seconds,
        "stale_after_seconds": stale_after_seconds,
        "last_started_at": values.get("drive_poll_worker_last_started_at"),
        "last_finished_at": values.get("drive_poll_worker_last_finished_at"),
        "last_error_present": bool(values.get("drive_poll_worker_last_error")),
        "last_error_message": (
            "Last Drive poll worker run failed; see server logs"
            if values.get("drive_poll_worker_last_error")
            else None
        ),
        "last_result": last_result,
    }


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
    oauth_info: dict[str, Any] = {
        "disabled": True,
        "note": "OAuth SYSTEM disabled 2026-05-10 — Drive uses Service Account",
    }
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


@router.get("/poll/status")
async def drive_poll_status(request: Request) -> dict[str, Any]:
    """Read Drive poll owner status without doing Drive or OCR work."""
    mode = _drive_poll_api_mode()
    if mode == "direct":
        return {
            "status": "direct",
            "mode": "direct",
            "worker_owned": False,
            "message": "Drive poll API is in legacy direct mode",
        }
    worker_status = await _read_drive_poll_worker_status(_get_request_pool(request))
    top_status = "ok"
    if (
        not worker_status.get("healthy")
        or worker_status.get("stale")
        or worker_status.get("status") == "error"
    ):
        top_status = "stale"
    return {
        "status": top_status,
        "mode": "worker",
        "worker_owned": True,
        "result": worker_status,
    }


@router.post("/poll")
async def trigger_drive_poll(request: Request) -> dict[str, Any]:
    """Trigger Google Drive changes poll (for cron jobs / OpenClaw automation)."""
    mode = _drive_poll_api_mode()
    if mode != "direct":
        worker_status = await _read_drive_poll_worker_status(_get_request_pool(request))
        top_status = "ok"
        if (
            not worker_status.get("healthy")
            or worker_status.get("stale")
            or worker_status.get("status") == "error"
        ):
            top_status = "stale"
        logger.info(
            "Drive poll POST handled in worker mode: status=%s stale=%s",
            worker_status.get("status"),
            worker_status.get("stale"),
        )
        return {
            "status": top_status,
            "processed": 0,
            "inline_ocr": False,
            "mode": "worker",
            "worker_owned": True,
            "result": worker_status,
        }

    inline_ocr = _env_flag("DRIVE_POLL_INLINE_OCR", default=False)
    timeout_seconds = _drive_poll_api_timeout_seconds()
    try:
        from backend.services.crm.drive_poll_service import poll_drive_changes

        result = await asyncio.wait_for(
            poll_drive_changes(inline_ocr=inline_ocr),
            timeout=timeout_seconds,
        )
        processed = result.get("processed", 0)
        logger.info(
            "Drive poll triggered via API: %s new files processed (inline_ocr=%s)",
            processed,
            inline_ocr,
        )
        return {
            "status": "ok",
            "processed": processed,
            "inline_ocr": inline_ocr,
            "result": result,
        }
    except TimeoutError as e:
        logger.error(
            "Drive poll timed out after %.1fs (inline_ocr=%s)",
            timeout_seconds,
            inline_ocr,
            exc_info=True,
        )
        raise HTTPException(
            status_code=504,
            detail={
                "status": "timeout",
                "message": f"Drive poll exceeded {timeout_seconds:.1f}s",
                "inline_ocr": inline_ocr,
            },
        ) from e
    except Exception as e:
        logger.error("Drive poll failed: %s", e, exc_info=True)
        return {"status": "error", "message": "Drive poll failed"}


@router.post("/backfill")
async def backfill_drive_documents(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """One-time backfill: scan all client Drive folders and register schema-compliant files.

    Runs in background. Only adds files NOT already in the documents table.
    Skips generic files (surat kuasa, WhatsApp images, agus.pdf, etc.).
    """
    _require_backfill_admin(current_user)

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
                        logger.warning("Backfill client #%s: %s", cid, e)

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
