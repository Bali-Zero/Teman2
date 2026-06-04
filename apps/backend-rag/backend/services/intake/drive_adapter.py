"""Drive intake adapter (FASE 1B).

Forks the blob-enumeration logic of the existing Drive poller
(`backend/services/crm/drive_poll_service.py` + `ServiceAccountDriveService.
list_changes_since`) but does NOT process/route into CRM — it downloads each
changed file to a local intake blob dir and calls enqueue().

ZERO CRM writes. PII stays local: blobs are written under INTAKE_BLOB_ROOT on
the Pro, never shipped to cloud LLMs here. Cursor reuses the existing
`system_settings` key `drive_poll_page_token` (read-only fork — this adapter
advances its OWN cursor key `intake_drive_page_token` so it does not fight the
production poller).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import asyncpg

from backend.services.intake.enqueue import enqueue

logger = logging.getLogger(__name__)

_SOURCE = "drive"
_CURSOR_KEY = "intake_drive_page_token"

# Local blob landing dir (PII stays on the Pro). Override via env.
_BLOB_ROOT = Path(
    os.environ.get("INTAKE_BLOB_ROOT", os.path.expanduser("~/.nuzantara/intake-blobs"))
) / "drive"

# Drive native/Google-Doc mime types we skip (no binary blob to hash).
_GOOGLE_NATIVE_PREFIX = "application/vnd.google-apps"


def _local_blob_path(file_id: str, file_name: str) -> Path:
    safe_name = file_name.replace("/", "_") if file_name else file_id
    return _BLOB_ROOT / file_id[:2] / f"{file_id}__{safe_name}"


async def _download_file(drive_service, file_id: str, dest: Path) -> int:
    """Download Drive file bytes to dest via get_media. Returns byte size."""
    import asyncio
    import io

    from googleapiclient.http import MediaIoBaseDownload

    def _blocking_download() -> bytes:
        request = drive_service.service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _status, done = downloader.next_chunk()
        return buf.getvalue()

    data = await asyncio.to_thread(_blocking_download)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return len(data)


async def drain_drive(
    pool: asyncpg.Pool,
    *,
    drive_service=None,
    limit: int = 500,
) -> dict[str, int]:
    """Enumerate Drive changes since the intake cursor, enqueue new blobs.

    `drive_service` is a ServiceAccountDriveService instance; if None, this
    adapter attempts to build one and degrades gracefully (WARN + return zeros)
    if Drive is not configured/reachable (Law 4).

    Returns counters: {changes, enqueued_new, already_present, skipped_native,
    skipped_removed, errors}.
    """
    counters = {
        "changes": 0,
        "enqueued_new": 0,
        "already_present": 0,
        "skipped_native": 0,
        "skipped_removed": 0,
        "errors": 0,
    }

    if drive_service is None:
        try:
            from backend.services.integrations.service_account_drive_service import (
                ServiceAccountDriveService,
            )

            drive_service = ServiceAccountDriveService()
        except Exception as exc:  # noqa: BLE001 — graceful degradation (Law 4)
            logger.warning("drain_drive: Drive service unavailable, skipping (%s)", exc)
            return counters

    # Read / seed our own intake cursor (separate from the prod poller token).
    async with pool.acquire() as conn:
        token_row = await conn.fetchval(
            "SELECT value FROM system_settings WHERE key = $1", _CURSOR_KEY
        )
    page_token: str | None = None
    if isinstance(token_row, str) and token_row not in ("", "{}"):
        import json as _json

        try:
            parsed = _json.loads(token_row)
            page_token = parsed.get("token") if isinstance(parsed, dict) else None
        except (ValueError, TypeError):
            page_token = None

    try:
        if not page_token:
            page_token = await drive_service.get_start_page_token()
        result = await drive_service.list_changes_since(page_token)
    except Exception as exc:  # noqa: BLE001 — graceful degradation (Law 4)
        logger.warning("drain_drive: Drive enumeration failed, skipping (%s)", exc)
        return counters

    changes = result.get("changes", [])[:limit]
    counters["changes"] = len(changes)

    for change in changes:
        if change.get("removed"):
            counters["skipped_removed"] += 1
            continue
        file_meta = change.get("file") or {}
        file_id = change.get("fileId") or file_meta.get("id")
        if not file_id or file_meta.get("trashed"):
            counters["skipped_removed"] += 1
            continue
        mime_type = file_meta.get("mimeType", "")
        if mime_type.startswith(_GOOGLE_NATIVE_PREFIX):
            # Google-native docs have no downloadable binary blob to hash.
            counters["skipped_native"] += 1
            continue

        file_name = file_meta.get("name", file_id)
        dest = _local_blob_path(file_id, file_name)
        try:
            byte_size = await _download_file(drive_service, file_id, dest)
            res = await enqueue(
                pool,
                source=_SOURCE,
                source_ref=f"drive:{file_id}",
                blob_path=dest,
                mime_type=mime_type or None,
                byte_size=byte_size,
            )
        except Exception:  # noqa: BLE001 — adapter must not crash the drain loop
            logger.exception("drain_drive enqueue failed for file_id=%s", file_id)
            counters["errors"] += 1
            continue
        if res.was_new:
            counters["enqueued_new"] += 1
        else:
            counters["already_present"] += 1

    # Advance our cursor (idempotent upsert).
    new_token = result.get("new_page_token")
    if new_token:
        import json

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO system_settings (key, value, updated_at)
                VALUES ($1, $2, now())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
                """,
                _CURSOR_KEY,
                json.dumps({"token": new_token}),
            )

    logger.info("drain_drive done: %s", counters)
    return counters
