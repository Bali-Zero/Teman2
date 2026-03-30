"""
CRM Google Drive Folder Management

Handles automatic creation of standardized folder structures for clients.
"""

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile

from backend.app.core.config import settings
from backend.app.dependencies import get_current_user, get_database_pool
from backend.services.integrations.google_drive_service import GoogleDriveService

router = APIRouter()
logger = logging.getLogger(__name__)


# Standard folder structure for all clients
STANDARD_SUBFOLDERS = [
    "00_Profile",
    "01_Immigration",
    "02_Company",
    "02_Company/AKTA",
    "02_Company/NIB",
    "02_Company/NPWP",
    "02_Company/Profile Perseroan",
    "03_Tax",
    "03_Tax/SPT company",
    "03_Tax/SPT personal",
    "03_Tax/LKPM reports",
    "03_Tax/NPWP personal",
    "04_Family",
    "99_Misc",
]


@router.post("/clients/{client_id}/create-drive-folder")
async def create_client_drive_folder(
    client_id: int,
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Create standardized Google Drive folder structure for a client.

    This endpoint:
    1. Retrieves client information from database
    2. Creates a root folder: "[ID]_[Name]"
    3. Creates 6 standardized subfolders
    4. Updates client record with google_drive_folder_id
    5. Returns all folder IDs for reference

    Args:
        client_id: Client database ID
        pool: Database connection pool
        current_user: Authenticated user

    Returns:
        {
            "success": true,
            "root_folder_id": "1ABC...XYZ",
            "root_folder_url": "https://drive.google.com/...",
            "folders": {
                "00_Profile": {"id": "...", "url": "..."},
                "01_Immigration": {"id": "...", "url": "..."},
                ...
            }
        }

    Raises:
        HTTPException: If client not found or folder creation fails
    """
    logger.info(f"[CRM] Creating Drive folder structure for client {client_id}")

    # 1. Get client information
    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            """
            SELECT id, full_name, client_type, google_drive_folder_id
            FROM clients
            WHERE id = $1
            """,
            client_id,
        )

    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    # Check if folder already exists
    if client["google_drive_folder_id"]:
        logger.warning(
            f"[CRM] Client {client_id} already has Drive folder: {client['google_drive_folder_id']}",
        )
        raise HTTPException(
            status_code=400,
            detail=f"Client already has a Google Drive folder: {client['google_drive_folder_id']}",
        )

    # 2. Initialize Google Drive service
    drive_service = GoogleDriveService(pool)

    # Check if system is connected to Google Drive
    is_connected = await drive_service.is_connected(GoogleDriveService.SYSTEM_USER_ID)
    if not is_connected:
        raise HTTPException(
            status_code=503,
            detail="Google Drive not connected. Please connect the system account first.",
        )

    # 3. Determine parent folder based on client type
    parent_folder_id = None

    if client["client_type"] == "individual":
        parent_folder_id = settings.gdrive_individuals_folder_id
    elif client["client_type"] == "company":
        parent_folder_id = settings.gdrive_companies_folder_id
    else:
        # Fallback to root folder
        parent_folder_id = settings.google_drive_root_folder_id

    if not parent_folder_id:
        raise HTTPException(
            status_code=500,
            detail=f"Parent folder not configured for client type: {client['client_type']}",
        )

    # 4. Create root folder: "[ID]_[Name]"
    root_folder_name = f"{client['id']}_{client['full_name']}"

    try:
        root_folder = await drive_service.create_folder(
            user_id=GoogleDriveService.SYSTEM_USER_ID,
            name=root_folder_name,
            parent_id=parent_folder_id,
        )
    except Exception as e:
        logger.error(f"[CRM] Failed to create root folder for client {client_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create root folder: {str(e)}",
        ) from e

    logger.info(f"[CRM] Created root folder: {root_folder['id']} for client {client_id}")

    # 5. Create standardized subfolders (supports nested paths like "02_Company/AKTA")
    subfolders = {}
    folder_id_cache = {"": root_folder["id"]}

    for subfolder_path in STANDARD_SUBFOLDERS:
        try:
            parts = subfolder_path.split("/")
            if len(parts) == 1:
                parent_id = root_folder["id"]
                name = parts[0]
            else:
                parent_path = parts[0]
                name = parts[1]
                parent_id = folder_id_cache.get(parent_path, root_folder["id"])

            subfolder = await drive_service.create_folder(
                user_id=GoogleDriveService.SYSTEM_USER_ID,
                name=name,
                parent_id=parent_id,
            )
            subfolders[subfolder_path] = {
                "id": subfolder["id"],
                "url": subfolder.get("webViewLink", ""),
            }
            if len(parts) == 1:
                folder_id_cache[name] = subfolder["id"]
            logger.info(f"[CRM] Created subfolder: {subfolder_path} ({subfolder['id']})")
        except Exception as e:
            logger.error(f"[CRM] Failed to create subfolder {subfolder_path}: {e}")
            # Continue creating other folders even if one fails

    # 6. Update client record with root folder ID
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE clients
            SET google_drive_folder_id = $1, updated_at = NOW()
            WHERE id = $2
            """,
            root_folder["id"],
            client_id,
        )

    logger.info(
        f"[CRM] Successfully created folder structure for client {client_id}. "
        f"Root folder: {root_folder['id']}",
    )

    return {
        "success": True,
        "client_id": client_id,
        "root_folder_id": root_folder["id"],
        "root_folder_url": root_folder.get("webViewLink", ""),
        "root_folder_name": root_folder_name,
        "folders": subfolders,
        "created_count": len(subfolders),
    }


@router.get("/clients/{client_id}/drive-folder")
async def get_client_drive_folder(
    client_id: int,
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get Google Drive folder information for a client.

    Returns the root folder ID and checks if it exists in Google Drive.

    Args:
        client_id: Client database ID

    Returns:
        {
            "client_id": 123,
            "folder_id": "1ABC...XYZ",
            "folder_url": "https://drive.google.com/...",
            "exists": true
        }
    """
    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            """
            SELECT id, full_name, google_drive_folder_id
            FROM clients
            WHERE id = $1
            """,
            client_id,
        )

    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    if not client["google_drive_folder_id"]:
        return {
            "client_id": client_id,
            "folder_id": None,
            "exists": False,
            "message": "No Google Drive folder created yet",
        }

    # Verify folder exists in Google Drive
    drive_service = GoogleDriveService(pool)
    folder_exists = False
    folder_url = None

    try:
        folder_info = await drive_service.get_file(
            user_id=GoogleDriveService.SYSTEM_USER_ID,
            file_id=client["google_drive_folder_id"],
        )
        folder_exists = True
        folder_url = folder_info.get("webViewLink", "")
    except Exception as e:
        logger.warning(
            f"[CRM] Could not verify folder {client['google_drive_folder_id']} "
            f"for client {client_id}: {e}",
        )

    return {
        "client_id": client_id,
        "folder_id": client["google_drive_folder_id"],
        "folder_url": folder_url,
        "exists": folder_exists,
    }


@router.delete("/clients/{client_id}/drive-folder")
async def unlink_client_drive_folder(
    client_id: int,
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Unlink Google Drive folder from client (does NOT delete the folder).

    This only removes the folder ID from the database. The actual folder
    remains in Google Drive and can be manually deleted if needed.

    Args:
        client_id: Client database ID

    Returns:
        {"success": true, "message": "..."}
    """
    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            "SELECT id, google_drive_folder_id FROM clients WHERE id = $1",
            client_id,
        )

    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    if not client["google_drive_folder_id"]:
        raise HTTPException(
            status_code=400,
            detail="Client does not have a linked Google Drive folder",
        )

    # Remove folder ID from database
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE clients SET google_drive_folder_id = NULL, updated_at = NOW() WHERE id = $1",
            client_id,
        )

    logger.info(
        f"[CRM] Unlinked Drive folder {client['google_drive_folder_id']} from client {client_id}",
    )

    return {
        "success": True,
        "message": f"Unlinked folder {client['google_drive_folder_id']} from client {client_id}",
        "note": "The folder still exists in Google Drive and was not deleted",
    }


@router.get("/clients/{client_id}/drive-folder/structure")
async def get_client_drive_folder_structure(
    client_id: int,
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get complete folder structure with file counts and statistics.

    Returns:
        {
            "root_folder_id": "1ABC...XYZ",
            "folders": [
                {
                    "name": "00_Profile",
                    "id": "...",
                    "file_count": 12,
                    "total_size_bytes": 5242880,
                    "last_modified": "2026-01-20T10:30:00Z"
                },
                ...
            ],
            "total_files": 47,
            "total_size_bytes": 131072000
        }
    """
    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            """
            SELECT id, google_drive_folder_id
            FROM clients
            WHERE id = $1
            """,
            client_id,
        )

    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    if not client["google_drive_folder_id"]:
        raise HTTPException(
            status_code=404,
            detail="Client does not have a Google Drive folder",
        )

    drive_service = GoogleDriveService(pool)

    try:
        return await drive_service.get_folder_structure(
            user_id=GoogleDriveService.SYSTEM_USER_ID,
            root_folder_id=client["google_drive_folder_id"],
        )
    except Exception as e:
        logger.error(f"[CRM] Failed to get folder structure for client {client_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get folder structure: {str(e)}",
        ) from e


@router.get("/clients/{client_id}/drive-folder/{folder_name}/files")
async def list_folder_files(
    client_id: int,
    folder_name: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None),
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    List files in a specific subfolder.

    Args:
        client_id: Client database ID
        folder_name: Subfolder name (e.g., "01_Immigration")
        limit: Max files to return (default: 50, max: 200)
        offset: Pagination offset
        search: Optional search query

    Returns:
        {
            "folder_name": "01_Immigration",
            "folder_id": "1GHI...XYZ",
            "files": [...],
            "total": 23,
            "limit": 50,
            "offset": 0
        }
    """
    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            """
            SELECT id, google_drive_folder_id
            FROM clients
            WHERE id = $1
            """,
            client_id,
        )

    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    if not client["google_drive_folder_id"]:
        raise HTTPException(
            status_code=404,
            detail="Client does not have a Google Drive folder",
        )

    drive_service = GoogleDriveService(pool)

    # First, get folder structure to find the subfolder ID
    try:
        structure = await drive_service.get_folder_structure(
            user_id=GoogleDriveService.SYSTEM_USER_ID,
            root_folder_id=client["google_drive_folder_id"],
        )
    except Exception as e:
        logger.error(f"[CRM] Failed to get folder structure: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get folder structure: {str(e)}",
        ) from e

    # Find the subfolder
    subfolder = next((f for f in structure["folders"] if f["name"] == folder_name), None)
    if not subfolder:
        raise HTTPException(
            status_code=404,
            detail=f"Subfolder '{folder_name}' not found",
        )

    # List files in the subfolder
    try:
        files_data = await drive_service.list_folder_files(
            user_id=GoogleDriveService.SYSTEM_USER_ID,
            folder_id=subfolder["id"],
            limit=limit,
            offset=offset,
            search=search,
        )

        return {
            "folder_name": folder_name,
            "folder_id": subfolder["id"],
            **files_data,
        }
    except Exception as e:
        logger.error(f"[CRM] Failed to list files in folder {folder_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list files: {str(e)}",
        ) from e


@router.post("/clients/{client_id}/drive-folder/{folder_name}/upload")
async def upload_file_to_folder(
    client_id: int,
    folder_name: str,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Upload a file directly to a subfolder.

    Args:
        client_id: Client database ID
        folder_name: Subfolder name (e.g., "01_Immigration")
        file: File to upload

    Returns:
        {
            "success": true,
            "file_id": "1JKL...XYZ",
            "file_name": "passport.pdf",
            "size_bytes": 2359296,
            "download_url": "/api/documents/proxy/1JKL...XYZ"
        }
    """
    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            """
            SELECT id, google_drive_folder_id
            FROM clients
            WHERE id = $1
            """,
            client_id,
        )

    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    if not client["google_drive_folder_id"]:
        raise HTTPException(
            status_code=404,
            detail="Client does not have a Google Drive folder",
        )

    drive_service = GoogleDriveService(pool)

    # Get folder structure to find subfolder ID
    try:
        structure = await drive_service.get_folder_structure(
            user_id=GoogleDriveService.SYSTEM_USER_ID,
            root_folder_id=client["google_drive_folder_id"],
        )
    except Exception as e:
        logger.error(f"[CRM] Failed to get folder structure: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get folder structure: {str(e)}",
        ) from e

    # Find the subfolder
    subfolder = next((f for f in structure["folders"] if f["name"] == folder_name), None)
    if not subfolder:
        raise HTTPException(
            status_code=404,
            detail=f"Subfolder '{folder_name}' not found",
        )

    # Read file content
    file_content = await file.read()
    file_name = file.filename or "uploaded_file"

    # Upload to Drive
    try:
        upload_result = await drive_service.upload_file_to_folder(
            user_id=GoogleDriveService.SYSTEM_USER_ID,
            folder_id=subfolder["id"],
            file_content=file_content,
            file_name=file_name,
            mime_type=file.content_type,
        )

        logger.info(
            f"[CRM] Uploaded file '{file_name}' to folder {folder_name} for client {client_id}",
        )

        # Dispatch OCR in background
        from backend.app.routers.crm_enhanced import _dispatch_ocr_by_folder

        background_tasks.add_task(
            _dispatch_ocr_by_folder,
            pool,
            client_id,
            upload_result["id"],
            folder_name,
            file_name,
        )

        return {
            "success": True,
            "folder_name": folder_name,
            "folder_id": subfolder["id"],
            "ocr_triggered": True,
            **upload_result,
        }
    except Exception as e:
        logger.error(f"[CRM] Failed to upload file: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file: {str(e)}",
        ) from e


@router.get("/clients/{client_id}/drive-folder/stats")
async def get_client_drive_folder_stats(
    client_id: int,
    pool=Depends(get_database_pool),
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Get aggregated statistics for client's Drive folder.

    Returns:
        {
            "total_files": 47,
            "total_size_bytes": 131072000,
            "total_size_mb": 125.0,
            "last_synced": "2026-01-20T12:30:00Z",
            "by_category": {
                "00_Profile": {"files": 2, "size_mb": 5.2},
                "01_Immigration": {"files": 23, "size_mb": 45.0},
                ...
            }
        }
    """
    async with pool.acquire() as conn:
        client = await conn.fetchrow(
            """
            SELECT id, google_drive_folder_id
            FROM clients
            WHERE id = $1
            """,
            client_id,
        )

    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    if not client["google_drive_folder_id"]:
        raise HTTPException(
            status_code=404,
            detail="Client does not have a Google Drive folder",
        )

    drive_service = GoogleDriveService(pool)

    try:
        return await drive_service.get_folder_stats(
            user_id=GoogleDriveService.SYSTEM_USER_ID,
            root_folder_id=client["google_drive_folder_id"],
        )
    except Exception as e:
        logger.error(f"[CRM] Failed to get folder stats for client {client_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get folder stats: {str(e)}",
        ) from e
