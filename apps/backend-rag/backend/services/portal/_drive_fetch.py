"""One Drive read path for every portal download proxy.

WHY THIS EXISTS — the portal's vault download, invoice-PDF download and LKPM
receipt download each opened `GoogleDriveService(...).get_valid_token(SYSTEM)`
and refused when it came back empty. It always comes back empty:
`GoogleDriveService._refresh_token` returns None for `SYSTEM` **by design**
since 2026-05-10 ("OAuth SYSTEM disabled — Drive operations use
ServiceAccountDriveService"), and the stored SYSTEM token expired
2026-06-15. So all three proxies raised, and the routers turned that into a
generic HTTP 500 — measured live 2026-09-11 on a client's own document:
`GET /api/portal/documents/<id>/download` → 500
`{"detail":"Failed to download document"}`, with the vault's DOWNLOAD button
failing silently (portal audit finding F-01).

Uploads had already moved to the Service Account, which is also the identity
that owns the files it wrote — so the reads have to use the same credential,
not merely a working one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DriveFile:
    content: bytes
    file_name: str
    mime_type: str


def _is_not_found(exc: Exception) -> bool:
    """True when Drive answered 404/410 — the file is gone, not broken."""
    status = getattr(getattr(exc, "resp", None), "status", None)
    if status is None:
        status = getattr(exc, "status_code", None)
    return status in (404, 410)


async def fetch_drive_file(
    file_id: str,
    *,
    fallback_file_name: str,
    fallback_mime_type: str,
    what: str,
) -> DriveFile | None:
    """Read a Drive file through the Service Account.

    Returns None when Drive reports the file as missing (the caller turns
    that into a 404, not a 500). Raises RuntimeError on any other failure so
    a real outage is not misreported as "your document does not exist".
    """
    from backend.services.integrations.service_account_drive_service import (
        ServiceAccountDriveService,
    )

    sa_drive = ServiceAccountDriveService()

    try:
        metadata = await sa_drive.get_file_metadata(file_id)
    except Exception as e:
        if _is_not_found(e):
            return None
        logger.error("Portal %s metadata fetch failed: %s", what, e)
        raise RuntimeError(f"Failed to fetch {what} metadata") from e

    try:
        content = await sa_drive.download_file_content(file_id)
    except Exception as e:
        if _is_not_found(e):
            return None
        logger.error("Portal %s download failed: %s", what, e)
        raise RuntimeError(f"Failed to download {what}") from e

    return DriveFile(
        content=content,
        file_name=metadata.get("name") or fallback_file_name,
        mime_type=metadata.get("mimeType") or fallback_mime_type,
    )
