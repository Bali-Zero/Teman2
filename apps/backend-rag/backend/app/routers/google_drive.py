"""
Google Drive API Router

Handles OAuth flow and file operations for Google Drive integration.
"""

import logging
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.dependencies import get_current_user, get_database_pool
from services.integrations.google_drive_service import GoogleDriveService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/google-drive", tags=["Google Drive"])


# =========================================================================
# RESPONSE MODELS
# =========================================================================


class ConnectionStatus(BaseModel):
    """Google Drive connection status."""

    connected: bool
    configured: bool
    root_folder_id: str | None = None


class FileItem(BaseModel):
    """File/folder item from Google Drive."""

    id: str
    name: str
    mime_type: str
    size: int | None = None
    modified_time: str | None = None
    icon_link: str | None = None
    web_view_link: str | None = None
    thumbnail_link: str | None = None
    is_folder: bool = False


class FileListResponse(BaseModel):
    """Response for file listing."""

    files: list[FileItem]
    next_page_token: str | None = None
    breadcrumb: list[dict[str, str]] = []


# =========================================================================
# OAUTH ENDPOINTS
# =========================================================================


@router.get("/status")
async def get_connection_status(
    current_user: dict = Depends(get_current_user),
    db_pool=Depends(get_database_pool),
) -> ConnectionStatus:
    """
    Check if user has connected Google Drive.
    """
    service = GoogleDriveService(db_pool)

    return ConnectionStatus(
        connected=await service.is_connected(current_user["id"]),
        configured=service.is_configured(),
        root_folder_id=service.root_folder_id,
    )


@router.get("/auth/url")
async def get_auth_url(
    request: Request,
    current_user: dict = Depends(get_current_user),
    db_pool=Depends(get_database_pool),
) -> dict[str, str]:
    """
    Get OAuth authorization URL for connecting Google Drive.

    Returns URL to redirect user to for Google consent.
    """
    service = GoogleDriveService(db_pool)

    if not service.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Google Drive OAuth not configured. Contact administrator.",
        )

    # Create state token with user ID for CSRF protection
    state = f"{current_user['id']}:{secrets.token_urlsafe(32)}"

    # Store state in session/cache for verification (simplified: using query param)
    auth_url = service.get_authorization_url(state)

    return {"auth_url": auth_url}


@router.get("/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    error: str | None = Query(None),
    db_pool=Depends(get_database_pool),
) -> RedirectResponse:
    """
    OAuth callback endpoint.

    Google redirects here after user grants consent.
    """
    # Frontend base URL for redirects
    frontend_url = "https://zantara.balizero.com"

    # Handle OAuth errors
    if error:
        logger.error(f"[GDRIVE] OAuth error: {error}")
        return RedirectResponse(
            url=f"{frontend_url}/settings/integrations?error={error}",
            status_code=302,
        )

    # Extract user_id from state
    try:
        user_id, _ = state.split(":", 1)
    except ValueError:
        logger.error("[GDRIVE] Invalid state parameter")
        return RedirectResponse(
            url=f"{frontend_url}/settings/integrations?error=invalid_state",
            status_code=302,
        )

    service = GoogleDriveService(db_pool)

    try:
        await service.exchange_code(code, user_id)
        logger.info(f"[GDRIVE] Successfully connected for user {user_id}")
        return RedirectResponse(
            url=f"{frontend_url}/settings/integrations?success=google_drive_connected",
            status_code=302,
        )
    except Exception as e:
        logger.error(f"[GDRIVE] Token exchange failed: {e}")
        return RedirectResponse(
            url=f"{frontend_url}/settings/integrations?error=token_exchange_failed",
            status_code=302,
        )


@router.post("/disconnect")
async def disconnect(
    current_user: dict = Depends(get_current_user),
    db_pool=Depends(get_database_pool),
) -> dict[str, bool]:
    """
    Disconnect Google Drive for current user.
    """
    service = GoogleDriveService(db_pool)
    success = await service.disconnect(current_user["id"])
    return {"success": success}


# =========================================================================
# FILE OPERATIONS
# =========================================================================


@router.get("/files")
async def list_files(
    folder_id: str | None = Query(None, description="Folder ID (default: root)"),
    page_token: str | None = Query(None, description="Pagination token"),
    page_size: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db_pool=Depends(get_database_pool),
) -> FileListResponse:
    """
    List files in a folder.

    Files are filtered based on user's Google Drive permissions.
    """
    service = GoogleDriveService(db_pool)

    if not await service.is_connected(current_user["id"]):
        raise HTTPException(
            status_code=401,
            detail="Google Drive not connected. Please connect first.",
        )

    try:
        result = await service.list_files(
            user_id=current_user["id"],
            folder_id=folder_id,
            page_token=page_token,
            page_size=page_size,
        )

        # Convert to response model
        files = [
            FileItem(
                id=f["id"],
                name=f["name"],
                mime_type=f["mimeType"],
                size=f.get("size"),
                modified_time=f.get("modifiedTime"),
                icon_link=f.get("iconLink"),
                web_view_link=f.get("webViewLink"),
                thumbnail_link=f.get("thumbnailLink"),
                is_folder=f["mimeType"] == "application/vnd.google-apps.folder",
            )
            for f in result["files"]
        ]

        # Get breadcrumb path
        breadcrumb = []
        if folder_id:
            breadcrumb = await service.get_folder_path(current_user["id"], folder_id)

        return FileListResponse(
            files=files,
            next_page_token=result.get("next_page_token"),
            breadcrumb=breadcrumb,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/files/{file_id}")
async def get_file(
    file_id: str,
    current_user: dict = Depends(get_current_user),
    db_pool=Depends(get_database_pool),
) -> FileItem:
    """
    Get file metadata.
    """
    service = GoogleDriveService(db_pool)

    if not await service.is_connected(current_user["id"]):
        raise HTTPException(status_code=401, detail="Google Drive not connected")

    try:
        f = await service.get_file(current_user["id"], file_id)

        return FileItem(
            id=f["id"],
            name=f["name"],
            mime_type=f["mimeType"],
            size=f.get("size"),
            modified_time=f.get("modifiedTime"),
            icon_link=f.get("iconLink"),
            web_view_link=f.get("webViewLink"),
            thumbnail_link=f.get("thumbnailLink"),
            is_folder=f["mimeType"] == "application/vnd.google-apps.folder",
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/search")
async def search_files(
    q: str = Query(..., min_length=2, description="Search query"),
    page_size: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    db_pool=Depends(get_database_pool),
) -> list[FileItem]:
    """
    Search files by name.
    """
    service = GoogleDriveService(db_pool)

    if not await service.is_connected(current_user["id"]):
        raise HTTPException(status_code=401, detail="Google Drive not connected")

    files = await service.search_files(
        user_id=current_user["id"],
        query=q,
        page_size=page_size,
    )

    return [
        FileItem(
            id=f["id"],
            name=f["name"],
            mime_type=f["mimeType"],
            size=f.get("size"),
            modified_time=f.get("modifiedTime"),
            icon_link=f.get("iconLink"),
            web_view_link=f.get("webViewLink"),
            is_folder=f["mimeType"] == "application/vnd.google-apps.folder",
        )
        for f in files
    ]


@router.get("/my-folder")
async def get_my_folder(
    current_user: dict = Depends(get_current_user),
    db_pool=Depends(get_database_pool),
) -> dict[str, Any] | None:
    """
    Get current user's personal folder.

    Returns the folder matching user's name in the team structure.
    """
    service = GoogleDriveService(db_pool)

    if not await service.is_connected(current_user["id"]):
        raise HTTPException(status_code=401, detail="Google Drive not connected")

    folder = await service.get_user_folder(
        user_id=current_user["id"],
        user_email=current_user["email"],
    )

    if not folder:
        return {"found": False, "message": "Personal folder not found"}

    return {
        "found": True,
        "folder_id": folder["id"],
        "folder_name": folder["name"],
    }
