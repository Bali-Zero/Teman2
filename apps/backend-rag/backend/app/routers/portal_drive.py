"""
Portal Drive Proxy Router.

Provides scoped access to a client's Google Drive folder.
Clients can only see a safe projection of their own google_drive_folder_id.
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


def _client_safe_drive_projection(result: dict[str, Any] | None) -> dict[str, Any] | None:
    """Allowlist the Drive metadata that may cross the client API boundary."""
    if result is None:
        return None

    raw_folders = result.get("folders", [])
    folders = raw_folders if isinstance(raw_folders, list) else []
    safe_folders = [
        {"name": folder["name"]}
        for folder in folders
        if isinstance(folder, dict) and isinstance(folder.get("name"), str)
    ]

    projection: dict[str, Any] = {
        # File access is served through the authenticated document proxy.
        # Raw Drive file metadata must never cross this boundary.
        "files": [],
        "folders": safe_folders,
        "total_files": result.get("total_files", 0),
    }
    for key in ("root_name", "total_size_bytes", "message"):
        if key in result:
            projection[key] = result[key]

    return projection


async def _list_client_drive_files(
    pool: asyncpg.Pool,
    drive_service: ServiceAccountDriveService,
    client_id: int,
) -> dict[str, Any] | None:
    """Load the configured Drive structure for final client-safe projection."""
    async with pool.acquire() as conn:
        folder_id = await conn.fetchval(
            "SELECT google_drive_folder_id FROM clients WHERE id = $1 AND deleted_at IS NULL",
            client_id,
        )

    if not folder_id:
        return {
            "files": [],
            "folders": [],
            "total_files": 0,
            "message": "No client Drive folder is configured",
        }

    structure = await drive_service.get_folder_structure(folder_id)
    folders = [
        {"id": folder["id"], "name": folder["name"]}
        for folder in structure.get("folders", [])
        if folder.get("id") and folder.get("name")
    ]

    return {
        "root_id": structure.get("root_id", folder_id),
        "root_name": structure.get("root_name"),
        "files": [],
        "folders": folders,
        "total_files": structure.get("total_files", 0),
        "total_size_bytes": structure.get("total_size_bytes", 0),
    }


@router.get("/files")
async def list_drive_files(
    client: dict = Depends(get_current_client),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    drive_service: ServiceAccountDriveService = Depends(_get_drive_service),
) -> dict[str, Any]:
    """List files in the client's Google Drive folder."""
    try:
        result = await _list_client_drive_files(db_pool, drive_service, client["client_id"])
        return {"success": True, "data": _client_safe_drive_projection(result)}
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
    """Block Drive subfolder navigation from the client portal."""
    raise HTTPException(
        status_code=404, detail="Drive navigation is not exposed in the client portal"
    )
