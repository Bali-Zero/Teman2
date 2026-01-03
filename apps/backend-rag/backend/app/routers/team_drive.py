"""
Team Drive API Router

Provides Google Drive file access for authenticated team members.
Uses Service Account authentication - no individual OAuth needed.

Team members with Zoho email can access shared Drive files through Zantara.
Files are filtered based on user's department:
- Setup Team: Legal, Immigration, Visa folders
- Tax Department: Tax, Finance folders
- Marketing: Marketing, Content folders
- Board: All folders
"""

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.dependencies import get_current_user, get_database_pool
from services.integrations.team_drive_service import TeamDriveService, get_team_drive_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drive", tags=["Team Drive"])

# Shared folders visible to everyone
SHARED_FOLDERS = ["_Shared", "Shared", "Common", "Templates"]


class FileItem(BaseModel):
    """File or folder item."""
    id: str
    name: str
    type: str  # 'file' or 'folder'
    mimeType: str
    size: int = 0
    modifiedTime: str | None = None
    webViewLink: str | None = None
    thumbnailLink: str | None = None


class FileListResponse(BaseModel):
    """Response for file listing."""
    files: list[FileItem]
    next_page_token: str | None = None


class BreadcrumbItem(BaseModel):
    """Breadcrumb path item."""
    id: str
    name: str


class CreateFolderRequest(BaseModel):
    """Request to create a folder."""
    name: str
    parent_id: str


class CreateDocRequest(BaseModel):
    """Request to create a Google Doc/Sheet/Slides."""
    name: str
    parent_id: str
    doc_type: str = "document"  # document, spreadsheet, presentation


class RenameRequest(BaseModel):
    """Request to rename a file/folder."""
    new_name: str


class MoveRequest(BaseModel):
    """Request to move a file/folder."""
    new_parent_id: str
    old_parent_id: str | None = None


class CopyRequest(BaseModel):
    """Request to copy a file."""
    new_name: str | None = None
    parent_id: str | None = None


class OperationResponse(BaseModel):
    """Response for file operations."""
    success: bool
    file: FileItem | None = None
    message: str | None = None


# Dependency to get drive service
def get_drive() -> TeamDriveService:
    service = get_team_drive_service()
    if not service.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Google Drive integration not configured"
        )
    return service


async def get_user_allowed_folders(user_email: str, pool) -> tuple[list[str], bool]:
    """
    Get list of folder names the user is allowed to access.
    Returns (folder_names, can_see_all)
    """
    try:
        async with pool.acquire() as conn:
            # Get user's department and personal folders
            user_row = await conn.fetchrow(
                """
                SELECT tm.department, tm.drive_folders, tm.full_name, d.drive_folders as dept_folders, d.can_see_all
                FROM team_members tm
                LEFT JOIN departments d ON tm.department = d.code
                WHERE tm.email = $1 AND tm.active = true
                """,
                user_email
            )

            if not user_row:
                # User not found, return only shared folders
                return SHARED_FOLDERS.copy(), False

            # Board members see everything
            if user_row['can_see_all']:
                return [], True

            allowed = set(SHARED_FOLDERS)

            # Add department folders
            if user_row['dept_folders']:
                dept_folders = user_row['dept_folders'] if isinstance(user_row['dept_folders'], list) else json.loads(user_row['dept_folders'])
                allowed.update(dept_folders)

            # Add personal folders (user's name)
            if user_row['full_name']:
                # Add variations of user's name
                name = user_row['full_name']
                allowed.add(name)
                allowed.add(name.split()[0])  # First name only

            # Add custom folders assigned to this user
            if user_row['drive_folders']:
                personal = user_row['drive_folders'] if isinstance(user_row['drive_folders'], list) else json.loads(user_row['drive_folders'])
                allowed.update(personal)

            return list(allowed), False

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error getting user folders: {e}")
        # On error, return only shared folders
        return SHARED_FOLDERS.copy(), False


def folder_matches_allowed(folder_name: str, allowed_folders: list[str]) -> bool:
    """Check if a folder name matches any of the allowed folder patterns."""
    folder_lower = folder_name.lower()
    for allowed in allowed_folders:
        if allowed.lower() in folder_lower or folder_lower in allowed.lower():
            return True
    return False


@router.get("/status")
async def drive_status(
    current_user: Annotated[dict, Depends(get_current_user)],
    drive: Annotated[TeamDriveService, Depends(get_drive)],
):
    """
    Check if Drive integration is configured and accessible.
    """
    try:
        # Quick test - list 1 file
        result = await drive.list_files(page_size=1)
        return {
            "status": "connected",
            "service_account": "nuzantara-bot@nuzantara.iam.gserviceaccount.com",
            "files_accessible": len(result.get("files", [])) > 0
        }
    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Status check failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@router.get("/files", response_model=FileListResponse)
async def list_files(
    current_user: Annotated[dict, Depends(get_current_user)],
    drive: Annotated[TeamDriveService, Depends(get_drive)],
    pool: Annotated[any, Depends(get_database_pool)],
    folder_id: str | None = Query(None, description="Folder ID to list contents of"),
    page_size: int = Query(50, ge=1, le=100),
    page_token: str | None = Query(None, description="Pagination token"),
    q: str | None = Query(None, description="Search query"),
):
    """
    List files in a folder or search across all shared files.
    Files are filtered based on user's department permissions.

    - If `folder_id` is provided, lists contents of that folder
    - If `q` is provided, searches for files matching the query
    - Otherwise, lists root-level folders filtered by department
    """
    try:
        user_email = current_user.get("email", "")

        # Get user's allowed folders
        allowed_folders, can_see_all = await get_user_allowed_folders(user_email, pool)

        result = await drive.list_files(
            folder_id=folder_id,
            page_size=page_size,
            page_token=page_token,
            query=q,
        )

        files = result["files"]

        # Filter at root level only (when no folder_id specified)
        if not folder_id and not can_see_all:
            filtered_files = []
            for f in files:
                # Allow all non-folder files
                if f["type"] != "folder" or folder_matches_allowed(f["name"], allowed_folders):
                    filtered_files.append(f)
            files = filtered_files
            logger.info(f"[TEAM_DRIVE] Filtered {len(result['files'])} -> {len(files)} files for {user_email}")

        return FileListResponse(
            files=[FileItem(**f) for f in files],
            next_page_token=result.get("next_page_token"),
        )

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error listing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/{file_id}")
async def get_file(
    file_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    drive: Annotated[TeamDriveService, Depends(get_drive)],
):
    """
    Get metadata for a specific file.
    """
    try:
        file = await drive.get_file_metadata(file_id)
        return FileItem(**file)

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error getting file {file_id}: {e}")
        raise HTTPException(status_code=404, detail="File not found")


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    drive: Annotated[TeamDriveService, Depends(get_drive)],
):
    """
    Download a file's content.

    For Google Docs/Sheets/Slides, exports to PDF/XLSX.
    For regular files, downloads the content directly.
    """
    try:
        content, filename, mime_type = await drive.download_file(file_id)

        # Log download for audit
        user_email = current_user.get("email", "unknown")
        logger.info(f"[TEAM_DRIVE] {user_email} downloaded: {filename}")

        return Response(
            content=content,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(content)),
            }
        )

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error downloading file {file_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/folders/{folder_id}/path", response_model=list[BreadcrumbItem])
async def get_folder_path(
    folder_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    drive: Annotated[TeamDriveService, Depends(get_drive)],
):
    """
    Get the breadcrumb path to a folder.
    """
    try:
        path = await drive.get_folder_path(folder_id)
        return [BreadcrumbItem(**item) for item in path]

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error getting folder path: {e}")
        return []


@router.get("/search")
async def search_files(
    q: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    drive: Annotated[TeamDriveService, Depends(get_drive)],
    file_type: str | None = Query(None, description="Filter by type: folder, document, spreadsheet, pdf"),
    page_size: int = Query(20, ge=1, le=50),
):
    """
    Search for files by name.
    """
    try:
        files = await drive.search_files(
            query=q,
            file_type=file_type,
            page_size=page_size,
        )

        return {
            "query": q,
            "results": [FileItem(**f) for f in files],
            "count": len(files),
        }

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error searching: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# CRUD Operations
# =========================================================================

async def check_write_permission(
    user_email: str,
    folder_id: str,
    pool,
    drive: TeamDriveService,
) -> bool:
    """
    Check if user has write permission to a folder.
    Write permission = can see the folder (or any of its parents).
    """
    allowed_folders, can_see_all = await get_user_allowed_folders(user_email, pool)

    # Board members can write everywhere
    if can_see_all:
        return True

    # Get folder's path and check if any matches allowed folders
    try:
        folder_path = await drive.get_folder_path(folder_id)
        for item in folder_path:
            if folder_matches_allowed(item["name"], allowed_folders):
                return True
    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error checking write permission: {e}")

    return False


@router.post("/files/upload", response_model=OperationResponse)
async def upload_file(
    current_user: Annotated[dict, Depends(get_current_user)],
    drive: Annotated[TeamDriveService, Depends(get_drive)],
    pool: Annotated[any, Depends(get_database_pool)],
    file: UploadFile = File(...),
    parent_id: str = Form(...),
):
    """
    Upload a file to Google Drive.
    """
    user_email = current_user.get("email", "")

    # Check write permission
    if not await check_write_permission(user_email, parent_id, pool, drive):
        raise HTTPException(
            status_code=403,
            detail="Non hai i permessi per caricare file in questa cartella"
        )

    try:
        content = await file.read()
        result = await drive.upload_file(
            file_content=content,
            filename=file.filename or "untitled",
            mime_type=file.content_type or "application/octet-stream",
            parent_folder_id=parent_id,
        )

        logger.info(f"[TEAM_DRIVE] {user_email} uploaded: {file.filename}")

        return OperationResponse(
            success=True,
            file=FileItem(**result),
            message=f"File '{file.filename}' caricato con successo"
        )

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/folders", response_model=OperationResponse)
async def create_folder(
    request: CreateFolderRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    drive: Annotated[TeamDriveService, Depends(get_drive)],
    pool: Annotated[any, Depends(get_database_pool)],
):
    """
    Create a new folder.
    """
    user_email = current_user.get("email", "")

    # Check write permission
    if not await check_write_permission(user_email, request.parent_id, pool, drive):
        raise HTTPException(
            status_code=403,
            detail="Non hai i permessi per creare cartelle qui"
        )

    try:
        result = await drive.create_folder(
            name=request.name,
            parent_folder_id=request.parent_id,
        )

        logger.info(f"[TEAM_DRIVE] {user_email} created folder: {request.name}")

        return OperationResponse(
            success=True,
            file=FileItem(**result),
            message=f"Cartella '{request.name}' creata"
        )

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error creating folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/create", response_model=OperationResponse)
async def create_doc(
    request: CreateDocRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    drive: Annotated[TeamDriveService, Depends(get_drive)],
    pool: Annotated[any, Depends(get_database_pool)],
):
    """
    Create a new Google Doc, Sheet, or Slides.
    """
    user_email = current_user.get("email", "")

    # Check write permission
    if not await check_write_permission(user_email, request.parent_id, pool, drive):
        raise HTTPException(
            status_code=403,
            detail="Non hai i permessi per creare documenti qui"
        )

    try:
        result = await drive.create_google_doc(
            name=request.name,
            parent_folder_id=request.parent_id,
            doc_type=request.doc_type,
        )

        doc_type_names = {
            "document": "Documento",
            "spreadsheet": "Foglio di calcolo",
            "presentation": "Presentazione",
        }

        logger.info(f"[TEAM_DRIVE] {user_email} created {request.doc_type}: {request.name}")

        return OperationResponse(
            success=True,
            file=FileItem(**result),
            message=f"{doc_type_names.get(request.doc_type, 'Documento')} '{request.name}' creato"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error creating doc: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/files/{file_id}/rename", response_model=OperationResponse)
async def rename_file(
    file_id: str,
    request: RenameRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    drive: Annotated[TeamDriveService, Depends(get_drive)],
):
    """
    Rename a file or folder.
    """
    user_email = current_user.get("email", "")

    try:
        result = await drive.rename_file(
            file_id=file_id,
            new_name=request.new_name,
        )

        logger.info(f"[TEAM_DRIVE] {user_email} renamed {file_id} to: {request.new_name}")

        return OperationResponse(
            success=True,
            file=FileItem(**result),
            message=f"Rinominato in '{request.new_name}'"
        )

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error renaming file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    drive: Annotated[TeamDriveService, Depends(get_drive)],
    permanent: bool = Query(False, description="Permanently delete instead of trashing"),
):
    """
    Delete a file or folder (move to trash by default).
    """
    user_email = current_user.get("email", "")

    try:
        await drive.delete_file(
            file_id=file_id,
            permanent=permanent,
        )

        action = "eliminato definitivamente" if permanent else "spostato nel cestino"
        logger.info(f"[TEAM_DRIVE] {user_email} deleted {file_id} (permanent={permanent})")

        return {
            "success": True,
            "message": f"File {action}"
        }

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error deleting file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/files/{file_id}/move", response_model=OperationResponse)
async def move_file(
    file_id: str,
    request: MoveRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    drive: Annotated[TeamDriveService, Depends(get_drive)],
    pool: Annotated[any, Depends(get_database_pool)],
):
    """
    Move a file to a different folder.
    """
    user_email = current_user.get("email", "")

    # Check write permission on destination
    if not await check_write_permission(user_email, request.new_parent_id, pool, drive):
        raise HTTPException(
            status_code=403,
            detail="Non hai i permessi per spostare file in questa cartella"
        )

    try:
        result = await drive.move_file(
            file_id=file_id,
            new_parent_id=request.new_parent_id,
            old_parent_id=request.old_parent_id,
        )

        logger.info(f"[TEAM_DRIVE] {user_email} moved {file_id} to {request.new_parent_id}")

        return OperationResponse(
            success=True,
            file=FileItem(**result),
            message="File spostato"
        )

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error moving file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/{file_id}/copy", response_model=OperationResponse)
async def copy_file(
    file_id: str,
    request: CopyRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    drive: Annotated[TeamDriveService, Depends(get_drive)],
    pool: Annotated[any, Depends(get_database_pool)],
):
    """
    Copy a file.
    """
    user_email = current_user.get("email", "")

    # Check write permission on destination if specified
    if request.parent_id:
        if not await check_write_permission(user_email, request.parent_id, pool, drive):
            raise HTTPException(
                status_code=403,
                detail="Non hai i permessi per copiare file in questa cartella"
            )

    try:
        result = await drive.copy_file(
            file_id=file_id,
            new_name=request.new_name,
            parent_folder_id=request.parent_id,
        )

        logger.info(f"[TEAM_DRIVE] {user_email} copied {file_id}")

        return OperationResponse(
            success=True,
            file=FileItem(**result),
            message="File copiato"
        )

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error copying file: {e}")
        raise HTTPException(status_code=500, detail=str(e))
