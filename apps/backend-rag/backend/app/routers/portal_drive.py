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
    """Return a client-safe placeholder without exposing Drive navigation."""
    async with pool.acquire() as conn:
        await conn.fetchval(
            "SELECT drive_folder_id FROM clients WHERE id = $1 AND deleted_at IS NULL",
            client_id,
        )

    return {
        "files": [],
        "folders": [],
        "total_files": 0,
        "message": "Drive navigation is not exposed in the client portal",
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
    """Block Drive subfolder navigation from the client portal."""
    raise HTTPException(status_code=404, detail="Drive navigation is not exposed in the client portal")
