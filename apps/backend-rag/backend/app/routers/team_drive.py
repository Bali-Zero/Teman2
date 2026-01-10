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

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.dependencies import get_current_user, get_database_pool
from app.utils.crm_utils import is_super_admin
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


# Dependency to get drive service (with OAuth support)
async def get_drive(
    pool: Annotated[any, Depends(get_database_pool)],
) -> TeamDriveService:
    """
    Get TeamDriveService with OAuth support.

    Uses db_pool to lookup OAuth SYSTEM token for 30TB quota.
    Falls back to Service Account if OAuth not configured.
    """
    service = get_team_drive_service(db_pool=pool)
    if not service.is_configured():
        raise HTTPException(status_code=503, detail="Google Drive integration not configured")
    return service


async def get_user_allowed_folders(
    user_email: str,
    pool,
    context_folder: str | None = None,
) -> tuple[list[str], bool]:
    """
    Get list of folder names the user is allowed to access.
    Uses folder_access_rules table for granular permissions.

    Args:
        user_email: User's email address
        pool: Database connection pool
        context_folder: Parent folder name (None = root level)

    Returns (folder_names, can_see_all)
    - folder_names: List of allowed folder patterns
    - can_see_all: Always False now (granular permissions for everyone)
    """
    try:
        async with pool.acquire() as conn:
            # Get user's department and role
            user_row = await conn.fetchrow(
                """
                SELECT tm.department, tm.full_name, d.name as role_name, d.can_see_all
                FROM team_members tm
                LEFT JOIN departments d ON tm.department = d.code
                WHERE tm.email = $1 AND tm.active = true
                """,
                user_email,
            )

            if not user_row:
                # User not found, return only default shared folders
                return SHARED_FOLDERS.copy(), False

            department = user_row["department"]
            full_name = user_row["full_name"] or ""
            can_see_all = user_row["can_see_all"] or False

            # Determine user's role from can_see_all flag
            # Board members have can_see_all=True in their department
            role = "board" if can_see_all else "team"

            # Query folder_access_rules with priority order
            # Priority: user_email > department_code > role > default (*)
            # context_folder = NULL in DB means "applies everywhere" (wildcard context)
            rules = await conn.fetch(
                """
                SELECT allowed_folders, priority
                FROM folder_access_rules
                WHERE active = true
                  AND (
                    context_folder IS NULL  -- NULL = applies everywhere
                    OR context_folder = $3  -- specific context match
                  )
                  AND (
                    user_email = $1
                    OR department_code = $2
                    OR role = $4
                    OR role = '*'
                  )
                ORDER BY priority DESC
                """,
                user_email,
                department,
                context_folder,
                role,
            )

            # Aggregate all allowed folders
            allowed = set()
            has_wildcard = False
            for rule in rules:
                folders = rule["allowed_folders"]
                if folders:
                    # Check for wildcard - user sees EVERYTHING
                    if "*" in folders:
                        has_wildcard = True
                        logger.info(f"[TEAM_DRIVE] Wildcard access for {user_email}")
                        break
                    allowed.update(folders)

            # If wildcard found, return can_see_all=True
            if has_wildcard:
                return ["*"], True

            # Always add user's personal folder (first name)
            if full_name:
                first_name = full_name.split()[0]
                allowed.add(first_name)
                allowed.add(full_name)

            # Fallback to shared folders if no rules matched
            if not allowed:
                allowed.update(SHARED_FOLDERS)

            logger.info(
                f"[TEAM_DRIVE] Permissions for {user_email} in context={context_folder}: {list(allowed)}"
            )

            return list(allowed), False

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error getting user folders: {e}")
        # On error, return only shared folders
        return SHARED_FOLDERS.copy(), False


def folder_matches_allowed(folder_name: str, allowed_folders: list[str]) -> bool:
    """Check if a folder name matches any of the allowed folder patterns."""
    # Wildcard means full access
    if "*" in allowed_folders:
        return True
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

    Shows OAuth status if connected (30TB quota).
    """
    try:
        # Quick test - list 1 file
        result = await drive.list_files(page_size=1)

        # Get connection info
        conn_info = drive.get_connection_info()

        return {
            "status": "connected",
            "mode": conn_info["mode"],  # "oauth" or "service_account"
            "connected_as": conn_info["connected_as"],
            "is_oauth": conn_info["is_oauth"],
            "files_accessible": len(result.get("files", [])) > 0,
            "quota_info": "30TB (antonellosiano@gmail.com)"
            if conn_info["is_oauth"]
            else "Workspace quota (zero@balizero.com)",
        }
    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Status check failed: {e}")
        return {"status": "error", "error": str(e)}


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
    Files are filtered based on user's folder_access_rules permissions.

    - If `folder_id` is provided, lists contents of that folder
    - If `q` is provided, searches for files matching the query
    - Otherwise, lists root-level folders filtered by permissions
    """
    try:
        user_email = current_user.get("email", "")

        # Determine context folder name for permission lookup
        context_folder = None
        if folder_id:
            # Get the folder's name to use as context
            try:
                folder_path = await drive.get_folder_path(folder_id)
                if folder_path:
                    # Use the current folder's name as context
                    context_folder = folder_path[-1]["name"] if folder_path else None
            except Exception as e:
                logger.warning(f"[TEAM_DRIVE] Could not get folder path: {e}")

        # Get user's allowed folders for this context
        allowed_folders, _ = await get_user_allowed_folders(user_email, pool, context_folder)

        result = await drive.list_files(
            folder_id=folder_id,
            page_size=page_size,
            page_token=page_token,
            query=q,
        )

        files = result["files"]

        # Apply folder filtering (at ALL levels, not just root)
        filtered_files = []
        for f in files:
            # Allow all non-folder files
            if f["type"] != "folder" or folder_matches_allowed(f["name"], allowed_folders):
                filtered_files.append(f)

        if len(filtered_files) != len(files):
            logger.info(
                f"[TEAM_DRIVE] Filtered {len(files)} -> {len(filtered_files)} for {user_email} "
                f"(context={context_folder})"
            )

        files = filtered_files

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
            },
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
    file_type: str | None = Query(
        None, description="Filter by type: folder, document, spreadsheet, pdf"
    ),
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
            status_code=403, detail="Non hai i permessi per caricare file in questa cartella"
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
            message=f"File '{file.filename}' caricato con successo",
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
        raise HTTPException(status_code=403, detail="Non hai i permessi per creare cartelle qui")

    try:
        result = await drive.create_folder(
            name=request.name,
            parent_folder_id=request.parent_id,
        )

        logger.info(f"[TEAM_DRIVE] {user_email} created folder: {request.name}")

        return OperationResponse(
            success=True, file=FileItem(**result), message=f"Cartella '{request.name}' creata"
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
        raise HTTPException(status_code=403, detail="Non hai i permessi per creare documenti qui")

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
            message=f"{doc_type_names.get(request.doc_type, 'Documento')} '{request.name}' creato",
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
            success=True, file=FileItem(**result), message=f"Rinominato in '{request.new_name}'"
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

        return {"success": True, "message": f"File {action}"}

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
            status_code=403, detail="Non hai i permessi per spostare file in questa cartella"
        )

    try:
        result = await drive.move_file(
            file_id=file_id,
            new_parent_id=request.new_parent_id,
            old_parent_id=request.old_parent_id,
        )

        logger.info(f"[TEAM_DRIVE] {user_email} moved {file_id} to {request.new_parent_id}")

        return OperationResponse(success=True, file=FileItem(**result), message="File spostato")

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
                status_code=403, detail="Non hai i permessi per copiare file in questa cartella"
            )

    try:
        result = await drive.copy_file(
            file_id=file_id,
            new_name=request.new_name,
            parent_folder_id=request.parent_id,
        )

        logger.info(f"[TEAM_DRIVE] {user_email} copied {file_id}")

        return OperationResponse(success=True, file=FileItem(**result), message="File copiato")

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error copying file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Permission Management (Board only)
# =========================================================================


class PermissionItem(BaseModel):
    """Permission entry."""

    id: str
    email: str
    name: str
    role: str  # owner, writer, commenter, reader
    type: str  # user, group, domain, anyone


class AddPermissionRequest(BaseModel):
    """Request to add permission."""

    email: str
    role: str = "reader"  # reader, commenter, writer
    send_notification: bool = True


class UpdatePermissionRequest(BaseModel):
    """Request to update permission."""

    role: str  # reader, commenter, writer


async def check_is_board(user_email: str, pool) -> bool:
    """Check if user is a board member (can_see_all)."""
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT d.can_see_all
                FROM team_members tm
                JOIN departments d ON tm.department = d.code
                WHERE tm.email = $1 AND tm.active = true
                """,
                user_email,
            )
            return row and row["can_see_all"]
    except Exception:
        return False


@router.get("/files/{file_id}/permissions", response_model=list[PermissionItem])
async def list_permissions(
    file_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    drive: Annotated[TeamDriveService, Depends(get_drive)],
):
    """
    List permissions for a file/folder.
    All authenticated users can view who has access.
    Zero is hidden from other users (invisible admin).
    """
    user_email = current_user.get("email", "")

    try:
        permissions = await drive.list_permissions(file_id)

        # Filter out hidden admins unless the requester is one of them
        if not is_super_admin(current_user):
            from app.utils.crm_utils import SUPER_ADMIN_EMAILS

            permissions = [p for p in permissions if p.get("email") not in SUPER_ADMIN_EMAILS]

        return [PermissionItem(**p) for p in permissions]

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error listing permissions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/{file_id}/permissions", response_model=PermissionItem)
async def add_permission(
    file_id: str,
    request: AddPermissionRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    drive: Annotated[TeamDriveService, Depends(get_drive)],
):
    """
    Add permission for a user. All authenticated users can manage permissions.
    """
    user_email = current_user.get("email", "")

    try:
        permission = await drive.add_permission(
            file_id=file_id,
            email=request.email,
            role=request.role,
            send_notification=request.send_notification,
        )

        logger.info(
            f"[TEAM_DRIVE] {user_email} added {request.role} for {request.email} on {file_id}"
        )

        return PermissionItem(**permission)

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error adding permission: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/files/{file_id}/permissions/{permission_id}", response_model=PermissionItem)
async def update_permission(
    file_id: str,
    permission_id: str,
    request: UpdatePermissionRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    drive: Annotated[TeamDriveService, Depends(get_drive)],
):
    """
    Update permission role. All authenticated users can manage permissions.
    """
    user_email = current_user.get("email", "")

    try:
        permission = await drive.update_permission(
            file_id=file_id,
            permission_id=permission_id,
            role=request.role,
        )

        logger.info(
            f"[TEAM_DRIVE] {user_email} updated permission {permission_id} to {request.role}"
        )

        return PermissionItem(**permission)

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error updating permission: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/files/{file_id}/permissions/{permission_id}")
async def remove_permission(
    file_id: str,
    permission_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    drive: Annotated[TeamDriveService, Depends(get_drive)],
):
    """
    Remove permission. All authenticated users can manage permissions.
    """
    user_email = current_user.get("email", "")

    try:
        await drive.remove_permission(
            file_id=file_id,
            permission_id=permission_id,
        )

        logger.info(f"[TEAM_DRIVE] {user_email} removed permission {permission_id} from {file_id}")

        return {"success": True, "message": "Permesso rimosso"}

    except Exception as e:
        logger.error(f"[TEAM_DRIVE] Error removing permission: {e}")
        raise HTTPException(status_code=500, detail=str(e))
