"""
Document Proxy Router

Serves Google Drive documents/images through backend proxy to avoid Google branding.
Used for passport and document previews in CRM.
"""

import asyncio
import logging
import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from google.auth.transport import requests as google_auth_requests

from backend.app.dependencies import get_current_user, get_database_pool
from backend.services.integrations.service_account_drive_service import (
    ServiceAccountDriveService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documents Proxy"])

# A Google Drive file ID is an opaque base64url-ish token. Anchoring the shape
# is the first half of the fix: `file_id` is interpolated straight into
# `https://www.googleapis.com/drive/v3/files/{file_id}`, so a value carrying
# `/`, `?` or `..` does not address a FILE — it rewrites the API path and can
# reach other Drive endpoints entirely (CodeQL py/partial-ssrf).
_DRIVE_FILE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,256}$")

# Fields the metadata call must return. `parents` is load-bearing: it is what
# ties a file to the client folder that authorises reading it.
_METADATA_FIELDS = "mimeType,name,size,parents"


def _assert_file_id_shape(file_id: str) -> None:
    """Reject anything that is not a bare Drive file ID, before any network call."""
    if not _DRIVE_FILE_ID_RE.match(file_id or ""):
        raise HTTPException(status_code=400, detail="Malformed Drive file id")


# The authorisation predicate. A file is served only if the CRM can place it:
# either its ID is one we registered as a document, or it sits directly in a
# folder we registered for a client/company.
#
# Registry FIRST, folder second — and that order is a measurement, not a style
# choice. Client documents do NOT live directly in the client folder: the Drive
# layout is `<client folder>/01_Immigration/Actual Visa/…`
# (`service_account_drive_service.py:286-288`), so a document's immediate
# `parents` is a SUBFOLDER, which is not registered anywhere. A guard that asked
# only "is a parent a known client folder?" would 403 nearly every real document
# in the CRM viewer. Measured 2026-07-31 on the live DB: 18,749 of 18,762
# `documents` rows carry `file_id`, 56,975 of 56,987 `company_documents` rows
# carry `google_drive_file_id` — the registry is the surface that actually
# answers, and `strpos` covers the 10 rows whose ID survives only inside a URL.
# (`strpos`, not `LIKE '%'||$1||'%'`: a Drive ID legitimately contains `_`, which
# LIKE would read as a single-character wildcard and quietly widen the match.)
_AUTHORISED_FILE_SQL = """
    SELECT 1
    WHERE EXISTS (SELECT 1 FROM documents WHERE file_id = $1)
       OR EXISTS (SELECT 1 FROM company_documents WHERE google_drive_file_id = $1)
       OR EXISTS (SELECT 1 FROM invoices WHERE drive_file_id = $1)
       OR EXISTS (SELECT 1 FROM lkpm_receipts WHERE file_drive_id = $1)
       OR EXISTS (
            SELECT 1 FROM documents
             WHERE strpos(coalesce(google_drive_file_url, ''), $1) > 0
                OR strpos(coalesce(file_url, ''), $1) > 0
          )
       OR EXISTS (
            SELECT 1 FROM company_documents
             WHERE strpos(coalesce(google_drive_file_url, ''), $1) > 0
          )
       OR (cardinality($2::text[]) > 0 AND (
              EXISTS (
                SELECT 1 FROM clients
                 WHERE google_drive_folder_id = ANY($2::text[])
                    OR drive_folder_id = ANY($2::text[])
              )
           OR EXISTS (
                SELECT 1 FROM companies
                 WHERE google_drive_folder_id = ANY($2::text[])
              )
          ))
"""


async def _assert_file_is_ours(file_id: str, parents: list[str], db_pool: Any) -> None:
    """The file must be one this CRM registered, or sit in a folder it registered.

    WHY THIS EXISTS (CodeQL alerts #791/#792, triaged 2026-07-31 and confirmed by
    an independent cross-family review). Before this check, `GET /proxy/{file_id}`
    took an arbitrary Drive ID from the URL, fetched it with the SERVICE ACCOUNT's
    token, and returned the bytes. The only guard was `Depends(get_current_user)`,
    i.e. "any authenticated user", and the injected `db_pool` was never queried —
    there was not a single SELECT in this module. So any holder of a valid JWT
    could read ANY file the service account can see, and that account carries the
    full `drive` scope.

    WHAT THIS DOES AND DOES NOT CLOSE — stated plainly, because a guard trusted
    beyond its reach is worse than no guard. It bounds the blast radius from
    "every file in the Workspace the service account can reach" down to "files
    Bali Zero already holds in its CRM". Two gaps remain open ON PURPOSE:

    1. It is not a per-user gate: a team member can still read a client they are
       not assigned to. That half is blocked on data, not on code — of 12,037 rows
       in `clients`, only 2,061 carry `assigned_to` (17%, measured 2026-07-31).
       Gating on the assignee tonight would revoke document access for the other
       83% and break the CRM for every non-admin. It needs an `assigned_to`
       backfill first: an owner decision about who holds those clients.

    2. The registry is self-authorising for a caller who can WRITE. `POST
       /api/crm/clients/{id}/documents` stores `data.file_id` from the request
       body verbatim (`crm_enhanced_documents.py:123-165`), so someone with write
       access to any one client can register an arbitrary Drive ID and then read
       it here. That is a far smaller population than "any authenticated user",
       and it leaves a `documents` row behind, but it is not nothing. Closing it
       means validating provenance at WRITE time — tracked, not silently assumed.
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(_AUTHORISED_FILE_SQL, file_id, parents)

    if row is None:
        logger.warning(
            "[PROXY] denied: file %s is not registered in the CRM and is not in a "
            "known client folder",
            file_id,
        )
        raise HTTPException(status_code=403, detail="File is not in a known client folder")


async def _get_drive_access_token() -> str:
    """Return a fresh Bearer token from the Service Account credentials.

    Replaces the legacy `GoogleDriveService.get_valid_token(SYSTEM_USER_ID)`
    path: that path was permanently disabled (logs `OAuth SYSTEM disabled —
    Drive operations use ServiceAccountDriveService`) and returned None,
    so every thumbnail / proxy call 503'd with 'Google Drive not connected'.
    Service Account + Domain-wide Delegation is the canonical drive auth
    for the backend — same pattern as crm_enhanced.py:46-48.
    """
    drive_service = ServiceAccountDriveService()
    # google-auth's `credentials.refresh()` is sync — offload to a thread
    # so we don't block the event loop on the TLS handshake to oauth2.googleapis.com.
    if not drive_service.credentials.token:
        await asyncio.to_thread(
            drive_service.credentials.refresh, google_auth_requests.Request()
        )
    token = drive_service.credentials.token
    if not token:
        raise HTTPException(
            status_code=503,
            detail="Google Drive Service Account token refresh failed",
        )
    return token


@router.get("/proxy/{file_id}")
async def proxy_drive_file(
    file_id: str,
    current_user: dict = Depends(get_current_user),
    db_pool=Depends(get_database_pool),
) -> Response:
    """
    Proxy Google Drive file through backend.
    Returns binary image/document data without Google branding.

    Args:
        file_id: Google Drive file ID (extracted from drive URL)

    Returns:
        Binary file content with appropriate mime type
    """
    _assert_file_id_shape(file_id)
    access_token = await _get_drive_access_token()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # First get file metadata to determine mime type
            meta_response = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                params={"fields": _METADATA_FIELDS},
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if meta_response.status_code == 404:
                raise HTTPException(status_code=404, detail="File not found in Google Drive")

            if meta_response.status_code != 200:
                logger.error(f"[PROXY] Metadata fetch failed: {meta_response.status_code}")
                raise HTTPException(status_code=500, detail="Failed to fetch file metadata")

            metadata = meta_response.json()
            mime_type = metadata.get("mimeType", "application/octet-stream")
            file_name = metadata.get("name", "document")

            # Authorise BEFORE the download leg: the metadata call is the cheap
            # probe, the download is the disclosure.
            await _assert_file_is_ours(file_id, metadata.get("parents") or [], db_pool)

            # Download file content
            download_response = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                params={"alt": "media"},
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if download_response.status_code != 200:
                logger.error(f"[PROXY] Download failed: {download_response.status_code}")
                raise HTTPException(status_code=500, detail="Failed to download file")

            return Response(
                content=download_response.content,
                media_type=mime_type,
                headers={
                    "Cache-Control": "private, max-age=3600",
                    "Content-Disposition": f'inline; filename="{file_name}"',
                },
            )

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Google Drive request timed out")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[PROXY] Unexpected error: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/thumbnail/{file_id}")
async def get_drive_thumbnail(
    file_id: str,
    width: int = Query(400, ge=100, le=1600, description="Thumbnail width in pixels"),
    current_user: dict = Depends(get_current_user),
    db_pool=Depends(get_database_pool),
) -> Any:
    """
    Get thumbnail of Google Drive file.
    Smaller, faster-loading preview image for document cards.

    Args:
        file_id: Google Drive file ID
        width: Desired thumbnail width (100-1600px)

    Returns:
        JPEG thumbnail image
    """
    _assert_file_id_shape(file_id)
    access_token = await _get_drive_access_token()

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Get thumbnail URL from file metadata. `parents` is requested here
            # for the same reason as in the proxy leg — a thumbnail of a file we
            # may not read is still a disclosure.
            response = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                params={"fields": "thumbnailLink,mimeType,parents"},
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="File not found")

            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to get file metadata")

            data = response.json()
            await _assert_file_is_ours(file_id, data.get("parents") or [], db_pool)
            thumbnail_url = data.get("thumbnailLink")

            if not thumbnail_url:
                # No thumbnail available - return placeholder or proxy full image
                # For images, we can use the full file as fallback
                mime_type = data.get("mimeType", "")
                if mime_type.startswith("image/"):
                    # Redirect to full proxy endpoint
                    return await proxy_drive_file(file_id, current_user, db_pool)

                raise HTTPException(
                    status_code=404,
                    detail="No thumbnail available for this file type",
                )

            # Modify thumbnail URL for custom size
            # Google thumbnail URLs contain =s{size} parameter
            thumbnail_url = re.sub(r"=s\d+", f"=s{width}", thumbnail_url)

            # Fetch thumbnail
            thumb_response = await client.get(thumbnail_url, timeout=10.0)

            if thumb_response.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to fetch thumbnail")

            return Response(
                content=thumb_response.content,
                media_type="image/jpeg",
                headers={
                    "Cache-Control": "private, max-age=3600",
                },
            )

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Thumbnail request timed out")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[THUMBNAIL] Unexpected error: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


def extract_file_id_from_url(url: str) -> str | None:
    """
    Extract Google Drive file ID from various URL formats.

    Supported formats:
    - https://drive.google.com/file/d/{FILE_ID}/view
    - https://drive.google.com/open?id={FILE_ID}
    - https://drive.google.com/uc?id={FILE_ID}

    Args:
        url: Google Drive URL

    Returns:
        File ID or None if not found
    """
    if not url:
        return None

    # Format: /file/d/{FILE_ID}/
    match = re.search(r"/file/d/([^/]+)", url)
    if match:
        return match.group(1)

    # Format: ?id={FILE_ID}
    match = re.search(r"[?&]id=([^&]+)", url)
    if match:
        return match.group(1)

    return None
