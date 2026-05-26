"""Read-only Drive metadata validation for CRM Guardian.

This service validates Drive IDs that the CRM already stores. It does not
list broad corpora and it never mutates Drive or production CRM rows.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Protocol

from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

DRIVE_ID_PATTERNS = (
    re.compile(r"/d/([A-Za-z0-9_-]{10,})"),
    re.compile(r"/folders/([A-Za-z0-9_-]{10,})"),
    re.compile(r"[?&]id=([A-Za-z0-9_-]{10,})"),
)


class DriveMetadataFetcher(Protocol):
    async def get_file_metadata_detailed(self, file_id: str) -> dict[str, Any]:
        """Fetch detailed metadata for one Drive file/folder."""


@dataclass(frozen=True, slots=True)
class CRMDriveLink:
    source_table: str
    link_kind: str
    entity_type: str
    entity_id: str
    parent_entity_id: str | None
    entity_label: str | None
    document_type: str | None
    file_name: str | None
    drive_id: str
    raw_url: str | None
    crm_status: str | None
    crm_updated_at: str | None


@dataclass(frozen=True, slots=True)
class DriveMetadataSnapshot:
    drive_id: str
    validation_status: str
    name: str | None
    mime_type: str | None
    owner_email: str | None
    owner_domain: str
    parent_ids: tuple[str, ...]
    shared_drive_id: str | None
    trashed: bool
    web_view_link: str | None
    shortcut_target_id: str | None
    shortcut_target_mime_type: str | None
    can_copy: bool | None
    can_download: bool | None
    can_edit: bool | None
    can_move_item_into_team_drive: bool | None
    can_move_item_out_of_drive: bool | None
    can_move_item_within_drive: bool | None
    error_status: str | None = None
    error_message: str | None = None


CRM_DRIVE_LINKS_SQL = """
SELECT
    'clients' AS source_table,
    'client_folder' AS link_kind,
    'client' AS entity_type,
    id::text AS entity_id,
    NULL::text AS parent_entity_id,
    full_name::text AS entity_label,
    NULL::text AS document_type,
    NULL::text AS file_name,
    google_drive_folder_id::text AS raw_drive_id,
    NULL::text AS raw_url,
    status::text AS crm_status,
    updated_at::text AS crm_updated_at
FROM clients
WHERE google_drive_folder_id IS NOT NULL AND google_drive_folder_id <> ''

UNION ALL

SELECT
    'client_drive_subfolders', 'client_subfolder', 'client',
    client_id::text, id::text, subfolder_name::text, NULL::text, subfolder_name::text,
    subfolder_id::text, NULL::text, NULL::text, created_at::text
FROM client_drive_subfolders
WHERE subfolder_id IS NOT NULL AND subfolder_id <> ''

UNION ALL

SELECT
    'companies', 'company_folder', 'company',
    id::text, NULL::text, company_name::text, NULL::text, NULL::text,
    google_drive_folder_id::text, NULL::text, status::text, updated_at::text
FROM companies
WHERE google_drive_folder_id IS NOT NULL AND google_drive_folder_id <> ''

UNION ALL

SELECT
    'companies', 'tax_dept_folder', 'company',
    id::text, NULL::text, company_name::text, NULL::text, NULL::text,
    tax_dept_folder_id::text, NULL::text, status::text, updated_at::text
FROM companies
WHERE tax_dept_folder_id IS NOT NULL AND tax_dept_folder_id <> ''

UNION ALL

SELECT
    'documents', 'client_document', 'client',
    client_id::text, id::text, file_name::text, document_type::text, file_name::text,
    file_id::text, COALESCE(google_drive_file_url, file_url)::text, status::text, updated_at::text
FROM documents
WHERE (file_id IS NOT NULL AND file_id <> '')
   OR (google_drive_file_url IS NOT NULL AND google_drive_file_url <> '')
   OR (file_url IS NOT NULL AND file_url <> '')

UNION ALL

SELECT
    'company_documents', 'company_document', 'company',
    company_id::text, id::text, COALESCE(document_title, file_name)::text,
    document_type::text, file_name::text,
    google_drive_file_id::text, google_drive_file_url::text, status::text, updated_at::text
FROM company_documents
WHERE (google_drive_file_id IS NOT NULL AND google_drive_file_id <> '')
   OR (google_drive_file_url IS NOT NULL AND google_drive_file_url <> '')

UNION ALL

SELECT
    'invoices', 'invoice', 'client',
    client_id::text, id::text, invoice_number::text, 'invoice', invoice_number::text,
    drive_file_id::text, drive_web_link::text, NULL::text, updated_at::text
FROM invoices
WHERE (drive_file_id IS NOT NULL AND drive_file_id <> '')
   OR (drive_web_link IS NOT NULL AND drive_web_link <> '')

UNION ALL

SELECT
    'crm_guardian_summary_queue', 'guardian_summary_folder', 'client',
    client_id::text, id::text, drive_folder_name::text, NULL::text, drive_folder_name::text,
    drive_folder_id::text, NULL::text, status::text,
    COALESCE(completed_at, started_at, enqueued_at)::text
FROM crm_guardian_summary_queue
WHERE drive_folder_id IS NOT NULL AND drive_folder_id <> ''

UNION ALL

SELECT
    'crm_guardian_file_content_cache', 'guardian_content_cache_file', 'drive_file',
    file_id::text, id::text, content_hash::text, extractor::text, NULL::text,
    file_id::text, NULL::text,
    CASE WHEN deleted_at IS NULL THEN 'active' ELSE 'deleted' END,
    COALESCE(last_seen_at, extracted_at)::text
FROM crm_guardian_file_content_cache
WHERE file_id IS NOT NULL AND file_id <> ''
"""


def extract_drive_id(raw_drive_id: str | None, raw_url: str | None = None) -> str | None:
    candidate = (raw_drive_id or "").strip()
    if candidate and not candidate.startswith("http"):
        return candidate
    haystack = " ".join(part for part in [candidate, raw_url or ""] if part)
    for pattern in DRIVE_ID_PATTERNS:
        match = pattern.search(haystack)
        if match:
            return match.group(1)
    return None


def owner_email(metadata: dict[str, Any]) -> str | None:
    owners = metadata.get("owners")
    if not isinstance(owners, list) or not owners:
        return None
    first = owners[0]
    if not isinstance(first, dict):
        return None
    email = first.get("emailAddress")
    return str(email) if email else None


def owner_domain(email: str | None) -> str:
    if not email or "@" not in email:
        return "unknown"
    return email.split("@", 1)[1].lower()


def _bool_cap(metadata: dict[str, Any], key: str) -> bool | None:
    capabilities = metadata.get("capabilities")
    if not isinstance(capabilities, dict):
        return None
    value = capabilities.get(key)
    return value if isinstance(value, bool) else None


def metadata_to_snapshot(drive_id: str, metadata: dict[str, Any]) -> DriveMetadataSnapshot:
    owners_email = owner_email(metadata)
    shortcut = metadata.get("shortcutDetails")
    if not isinstance(shortcut, dict):
        shortcut = {}
    parents = metadata.get("parents")
    parent_ids = tuple(str(parent) for parent in parents if parent) if isinstance(parents, list) else ()
    return DriveMetadataSnapshot(
        drive_id=drive_id,
        validation_status="ok",
        name=str(metadata["name"]) if metadata.get("name") else None,
        mime_type=str(metadata["mimeType"]) if metadata.get("mimeType") else None,
        owner_email=owners_email,
        owner_domain=owner_domain(owners_email),
        parent_ids=parent_ids,
        shared_drive_id=str(metadata["driveId"]) if metadata.get("driveId") else None,
        trashed=metadata.get("trashed") is True,
        web_view_link=str(metadata["webViewLink"]) if metadata.get("webViewLink") else None,
        shortcut_target_id=str(shortcut["targetId"]) if shortcut.get("targetId") else None,
        shortcut_target_mime_type=(
            str(shortcut["targetMimeType"]) if shortcut.get("targetMimeType") else None
        ),
        can_copy=_bool_cap(metadata, "canCopy"),
        can_download=_bool_cap(metadata, "canDownload"),
        can_edit=_bool_cap(metadata, "canEdit"),
        can_move_item_into_team_drive=_bool_cap(metadata, "canMoveItemIntoTeamDrive"),
        can_move_item_out_of_drive=_bool_cap(metadata, "canMoveItemOutOfDrive"),
        can_move_item_within_drive=_bool_cap(metadata, "canMoveItemWithinDrive"),
    )


def error_to_snapshot(drive_id: str, exc: Exception) -> DriveMetadataSnapshot:
    status = "error"
    message = str(exc)
    if isinstance(exc, HttpError):
        status = f"error_{exc.resp.status}"
        message = exc.reason or message
    return DriveMetadataSnapshot(
        drive_id=drive_id,
        validation_status=status,
        name=None,
        mime_type=None,
        owner_email=None,
        owner_domain="unknown",
        parent_ids=(),
        shared_drive_id=None,
        trashed=False,
        web_view_link=None,
        shortcut_target_id=None,
        shortcut_target_mime_type=None,
        can_copy=None,
        can_download=None,
        can_edit=None,
        can_move_item_into_team_drive=None,
        can_move_item_out_of_drive=None,
        can_move_item_within_drive=None,
        error_status=status,
        error_message=message,
    )


async def fetch_crm_drive_links(conn: Any) -> list[CRMDriveLink]:
    rows = await conn.fetch(CRM_DRIVE_LINKS_SQL)
    links: list[CRMDriveLink] = []
    for row in rows:
        raw_drive_id = row.get("raw_drive_id") if hasattr(row, "get") else row["raw_drive_id"]
        raw_url = row.get("raw_url") if hasattr(row, "get") else row["raw_url"]
        drive_id = extract_drive_id(raw_drive_id, raw_url)
        if not drive_id:
            continue
        links.append(
            CRMDriveLink(
                source_table=str(row["source_table"]),
                link_kind=str(row["link_kind"]),
                entity_type=str(row["entity_type"]),
                entity_id=str(row["entity_id"]),
                parent_entity_id=str(row["parent_entity_id"]) if row["parent_entity_id"] else None,
                entity_label=str(row["entity_label"]) if row["entity_label"] else None,
                document_type=str(row["document_type"]) if row["document_type"] else None,
                file_name=str(row["file_name"]) if row["file_name"] else None,
                drive_id=drive_id,
                raw_url=str(raw_url) if raw_url else None,
                crm_status=str(row["crm_status"]) if row["crm_status"] else None,
                crm_updated_at=str(row["crm_updated_at"]) if row["crm_updated_at"] else None,
            )
        )
    return links


def unique_drive_ids(links: list[CRMDriveLink]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for link in links:
        if link.drive_id in seen:
            continue
        seen.add(link.drive_id)
        unique.append(link.drive_id)
    return unique


def summarize_snapshots(snapshots: list[DriveMetadataSnapshot]) -> dict[str, Any]:
    statuses = Counter(snapshot.validation_status for snapshot in snapshots)
    owners = Counter(snapshot.owner_domain for snapshot in snapshots if snapshot.validation_status == "ok")
    mime_types = Counter(
        snapshot.mime_type or "unknown" for snapshot in snapshots if snapshot.validation_status == "ok"
    )
    return {
        "total": len(snapshots),
        "ok": statuses["ok"],
        "errors": len(snapshots) - statuses["ok"],
        "status_counts": dict(statuses),
        "owner_domain_counts": dict(owners),
        "mime_type_counts": dict(mime_types),
    }


class CRMGuardianDriveMetadataSnapshotService:
    """Validate known CRM Drive IDs through direct metadata lookups."""

    def __init__(self, drive_service: DriveMetadataFetcher, *, concurrency: int = 8) -> None:
        self.drive_service = drive_service
        self.concurrency = max(1, concurrency)

    async def validate_drive_id(self, drive_id: str) -> DriveMetadataSnapshot:
        try:
            metadata = await self.drive_service.get_file_metadata_detailed(drive_id)
            return metadata_to_snapshot(drive_id, metadata)
        except Exception as exc:
            logger.debug("Drive metadata validation failed for %s: %s", drive_id, exc)
            return error_to_snapshot(drive_id, exc)

    async def validate_drive_ids(self, drive_ids: list[str]) -> list[DriveMetadataSnapshot]:
        semaphore = asyncio.Semaphore(self.concurrency)

        async def guarded(drive_id: str) -> DriveMetadataSnapshot:
            async with semaphore:
                return await self.validate_drive_id(drive_id)

        return await asyncio.gather(*(guarded(drive_id) for drive_id in drive_ids))

    async def validate_db_links(
        self,
        conn: Any,
        *,
        limit: int | None = None,
    ) -> tuple[list[CRMDriveLink], list[DriveMetadataSnapshot]]:
        links = await fetch_crm_drive_links(conn)
        drive_ids = unique_drive_ids(links)
        if limit is not None:
            drive_ids = drive_ids[: max(0, limit)]
        snapshots = await self.validate_drive_ids(drive_ids)
        return links, snapshots
