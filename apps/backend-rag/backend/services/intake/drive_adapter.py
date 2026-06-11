"""Drive intake adapter (FASE 1B, scoped + path-aware since m227).

Forks the blob-enumeration logic of the existing Drive poller
(`backend/services/crm/drive_poll_service.py` + `ServiceAccountDriveService.
list_changes_since`) but does NOT process/route into CRM — it downloads each
changed file to a local intake blob dir and calls enqueue().

Scope (m227): the adapter REQUIRES ``INTAKE_DRIVE_SCOPE_FOLDER_ID`` (the Drive
folder id of the watched root, e.g. Dropbox-Intake/). The Drive changes API is
account-wide — without the scope filter this adapter would ingest the codebase
mirror, the nightly backups and every other Drive write. Files whose ancestor
chain does not reach the scope folder are skipped. The ancestor walk also yields
the path RELATIVE to the scope root ("<Client Name>/passport.jpg"), persisted as
``intake_queue.source_path`` — the folder-name entity signal for FASE-4 routing.

ZERO CRM writes. PII stays local: blobs are written under INTAKE_BLOB_ROOT on
the Pro, never shipped to cloud LLMs here. Cursor: this adapter advances its
OWN ``system_settings`` key ``intake_drive_page_token`` so it does not fight
the production poller (``drive_poll_page_token``).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import asyncpg

from backend.services.intake.enqueue import enqueue

logger = logging.getLogger(__name__)

_SOURCE = "drive"
_CURSOR_KEY = "intake_drive_page_token"

# Drive folder id of the watched root (e.g. Dropbox-Intake/). REQUIRED —
# fail-safe: without it the adapter refuses to ingest anything.
_SCOPE_ENV = "INTAKE_DRIVE_SCOPE_FOLDER_ID"

# Local blob landing dir (PII stays on the Pro). Override via env.
_BLOB_ROOT = Path(
    os.environ.get("INTAKE_BLOB_ROOT", os.path.expanduser("~/.nuzantara/intake-blobs"))
) / "drive"

# Drive native/Google-Doc mime types we skip (no binary blob to hash).
_GOOGLE_NATIVE_PREFIX = "application/vnd.google-apps"

# Max parent-chain hops before declaring a file out of scope (defensive cap).
_MAX_ANCESTOR_DEPTH = 12


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


async def _folder_meta(drive_service, folder_id: str) -> dict[str, Any]:
    """files.get for one ancestor folder (id, name, parents)."""
    import asyncio

    def _blocking_get() -> dict[str, Any]:
        return (
            drive_service.service.files()
            .get(fileId=folder_id, fields="id, name, parents", supportsAllDrives=True)
            .execute()
        )

    return await asyncio.to_thread(_blocking_get)


async def _resolve_relative_dir(
    drive_service,
    parents: list[str] | None,
    scope_id: str,
    cache: dict[str, dict[str, Any]],
) -> str | None:
    """Walk the parent chain up to the scope folder.

    Returns the folder path RELATIVE to the scope root ("" for a direct child,
    "A/B" for nested), or None when the chain never reaches ``scope_id``
    (= out of scope). ``cache`` memoizes folder lookups within one drain tick.
    """
    cur = (parents or [None])[0]
    segments: list[str] = []
    depth = 0
    while cur and depth < _MAX_ANCESTOR_DEPTH:
        if cur == scope_id:
            return "/".join(reversed(segments))
        meta = cache.get(cur)
        if meta is None:
            try:
                meta = await _folder_meta(drive_service, cur)
            except Exception as exc:
                logger.warning("drain_drive: ancestor walk failed at %s (%s)", cur, exc)
                return None
            cache[cur] = meta
        segments.append(meta.get("name") or cur)
        cur = (meta.get("parents") or [None])[0]
        depth += 1
    return None


async def drain_drive(
    pool: asyncpg.Pool,
    *,
    drive_service=None,
    limit: int = 500,
) -> dict[str, int]:
    """Enumerate Drive changes since the intake cursor, enqueue in-scope blobs.

    `drive_service` is a ServiceAccountDriveService instance; if None, this
    adapter attempts to build one and degrades gracefully (WARN + return zeros)
    if Drive is not configured/reachable (Law 4). ``INTAKE_DRIVE_SCOPE_FOLDER_ID``
    must point at the watched root folder, else the drain refuses to run.

    Returns counters: {changes, enqueued_new, already_present, skipped_native,
    skipped_removed, skipped_out_of_scope, errors}.
    """
    counters = {
        "changes": 0,
        "enqueued_new": 0,
        "already_present": 0,
        "skipped_native": 0,
        "skipped_removed": 0,
        "skipped_out_of_scope": 0,
        "errors": 0,
    }

    scope_id = os.environ.get(_SCOPE_ENV, "").strip()
    if not scope_id:
        logger.warning(
            "drain_drive: %s not set — refusing to ingest the whole Drive "
            "(fail-safe), skipping", _SCOPE_ENV,
        )
        return counters

    if drive_service is None:
        try:
            from backend.services.integrations.service_account_drive_service import (
                ServiceAccountDriveService,
            )

            drive_service = ServiceAccountDriveService()
        except Exception as exc:
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
    except Exception as exc:
        logger.warning("drain_drive: Drive enumeration failed, skipping (%s)", exc)
        return counters

    changes = result.get("changes", [])[:limit]
    counters["changes"] = len(changes)

    folder_cache: dict[str, dict[str, Any]] = {}

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
            # (Folders are google-apps.folder → also skipped here.)
            counters["skipped_native"] += 1
            continue

        # Scope filter (m227): only files whose ancestor chain reaches the
        # watched root are ingested; the walk yields the relative folder path.
        rel_dir = await _resolve_relative_dir(
            drive_service, file_meta.get("parents"), scope_id, folder_cache
        )
        if rel_dir is None:
            counters["skipped_out_of_scope"] += 1
            continue

        file_name = file_meta.get("name", file_id)
        source_path = f"{rel_dir}/{file_name}" if rel_dir else file_name
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
                source_path=source_path,
            )
        except Exception:
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
