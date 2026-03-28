"""
Endpoint per refresh manuale del token Google Drive.
"""

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/admin/drive", tags=["admin"])


@router.post("/refresh")
async def drive_refresh(request: Request) -> dict[str, Any]:
    """Force refresh del token Google Drive SYSTEM."""
    pool = getattr(request.app.state, "db_pool", None)
    if not pool:
        return {"status": "error", "message": "Database pool not available"}

    try:
        from backend.services.integrations.google_drive_service import GoogleDriveService

        drive = GoogleDriveService(pool)

        # Get current refresh token
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT refresh_token FROM google_drive_tokens WHERE user_id = 'SYSTEM'"
            )
            if not row or not row["refresh_token"]:
                return {
                    "status": "error",
                    "message": "No refresh token found. Manual re-authorization required.",
                    "auth_url": "/admin/google-drive/auth",
                }

            refresh_token = row["refresh_token"]

        # Try refresh
        new_token = await drive._refresh_token("SYSTEM", refresh_token)

        if new_token:
            return {
                "status": "success",
                "message": "Token refreshed successfully",
                "token_preview": new_token[:30] + "...",
            }
        return {
            "status": "error",
            "message": "Refresh failed. Token may be revoked.",
            "auth_url": "/admin/google-drive/auth",
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Refresh error: {str(e)}",
            "auth_url": "/admin/google-drive/auth",
        }
