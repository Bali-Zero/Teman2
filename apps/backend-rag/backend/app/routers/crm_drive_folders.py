"""
CRM Google Drive Folder Management

Handles automatic creation of standardized folder structures for clients.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.core.auth import get_current_user
from backend.app.core.config import settings
from backend.app.core.database import get_database_pool
from backend.services.integrations.google_drive_service import GoogleDriveService

router = APIRouter()
logger = logging.getLogger(__name__)


# Standard folder structure for all clients
STANDARD_SUBFOLDERS = [
    "00_Profile",
    "01_Immigration",
    "02_Company",
    "03_Tax",
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
            f"[CRM] Client {client_id} already has Drive folder: {client['google_drive_folder_id']}"
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
        )

    logger.info(f"[CRM] Created root folder: {root_folder['id']} for client {client_id}")

    # 5. Create standardized subfolders
    subfolders = {}

    for subfolder_name in STANDARD_SUBFOLDERS:
        try:
            subfolder = await drive_service.create_folder(
                user_id=GoogleDriveService.SYSTEM_USER_ID,
                name=subfolder_name,
                parent_id=root_folder["id"],
            )
            subfolders[subfolder_name] = {
                "id": subfolder["id"],
                "url": subfolder.get("webViewLink", ""),
            }
            logger.info(f"[CRM] Created subfolder: {subfolder_name} ({subfolder['id']})")
        except Exception as e:
            logger.error(f"[CRM] Failed to create subfolder {subfolder_name}: {e}")
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
        f"Root folder: {root_folder['id']}"
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
            f"for client {client_id}: {e}"
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
        f"[CRM] Unlinked Drive folder {client['google_drive_folder_id']} from client {client_id}"
    )

    return {
        "success": True,
        "message": f"Unlinked folder {client['google_drive_folder_id']} from client {client_id}",
        "note": "The folder still exists in Google Drive and was not deleted",
    }
