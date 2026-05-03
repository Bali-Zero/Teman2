"""
Document Proxy Router

Serves Google Drive documents/images through backend proxy to avoid Google branding.
Used for passport and document previews in CRM.
"""

import logging
import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from backend.app.dependencies import get_current_user, get_database_pool
from backend.services.integrations.google_drive_service import GoogleDriveService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documents Proxy"])


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
    drive_service = GoogleDriveService(db_pool)

    # Use SYSTEM token (team-wide OAuth)
    access_token = await drive_service.get_valid_token(GoogleDriveService.SYSTEM_USER_ID)
    if not access_token:
        raise HTTPException(
            status_code=503,
            detail="Google Drive not connected. Please connect via Settings → Integrations.",
        )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # First get file metadata to determine mime type
            meta_response = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                params={"fields": "mimeType,name,size"},
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
        logger.error(f"[PROXY] Unexpected error: {e}")
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
    drive_service = GoogleDriveService(db_pool)
    access_token = await drive_service.get_valid_token(GoogleDriveService.SYSTEM_USER_ID)

    if not access_token:
        raise HTTPException(
            status_code=503,
            detail="Google Drive not connected",
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Get thumbnail URL from file metadata
            response = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                params={"fields": "thumbnailLink,mimeType"},
                headers={"Authorization": f"Bearer {access_token}"},
            )

            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="File not found")

            if response.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to get file metadata")

            data = response.json()
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
        logger.error(f"[THUMBNAIL] Unexpected error: {e}")
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
