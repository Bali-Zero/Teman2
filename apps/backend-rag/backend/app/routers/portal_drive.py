"""
Portal Drive Proxy Router.

Provides scoped access to a client's Google Drive folder.
Clients can only see files in their own drive_folder_id.
"""

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from backend.app.dependencies import get_database_pool
from backend.app.routers.portal import get_current_client
from backend.app.utils.logging_utils import get_logger
from backend.services.integrations.service_account_drive_service import ServiceAccountDriveService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/portal/drive", tags=["portal-drive"])


def _get_drive_service() -> ServiceAccountDriveService:
    return ServiceAccountDriveService()


async def _list_client_drive_files(
    pool: asyncpg.Pool,
    drive_service: ServiceAccountDriveService,
    client_id: int,
) -> dict[str, Any] | None:
    """List files from the client's Google Drive folder. Returns None if no folder linked."""
    async with pool.acquire() as conn:
        folder_id = await conn.fetchval(
            "SELECT drive_folder_id FROM clients WHERE id = $1 AND deleted_at IS NULL",
            client_id,
        )

    if not folder_id:
        return None

    return await drive_service.get_folder_structure(folder_id)


@router.get("/files")
async def list_drive_files(
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    drive_service: ServiceAccountDriveService = Depends(_get_drive_service),
) -> dict[str, Any]:
    """List files in the client's Google Drive folder."""
    try:
        result = await _list_client_drive_files(db_pool, drive_service, client["client_id"])
        if result is None:
            return {
                "success": True,
                "data": {"files": [], "folders": [], "total_files": 0, "message": "No Drive folder linked"},
            }
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Failed to list Drive files for client {client['client_id']}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load documents from Drive")


@router.get("/files/{folder_id}/list")
async def list_subfolder_files(
    folder_id: str,
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    drive_service: ServiceAccountDriveService = Depends(_get_drive_service),
) -> dict[str, Any]:
    """List files in a subfolder of the client's Drive folder."""
    async with db_pool.acquire() as conn:
        root_folder_id = await conn.fetchval(
            "SELECT drive_folder_id FROM clients WHERE id = $1 AND deleted_at IS NULL",
            client["client_id"],
        )

    if not root_folder_id:
        raise HTTPException(status_code=404, detail="No Drive folder linked")

    root_structure = await drive_service.get_folder_structure(root_folder_id)
    allowed_ids = {root_folder_id} | {f["id"] for f in root_structure.get("folders", [])}

    if folder_id not in allowed_ids:
        raise HTTPException(status_code=403, detail="Access denied to this folder")

    result = await drive_service.get_folder_structure(folder_id)
    return {"success": True, "data": result}
