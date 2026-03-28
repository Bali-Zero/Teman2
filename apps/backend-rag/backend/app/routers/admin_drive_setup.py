"""
Setup Service Account for Drive uploads (fallback when OAuth fails)
"""

import os
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/admin/drive", tags=["admin"])


@router.post("/use-service-account")
async def use_service_account(request: Request) -> dict[str, Any]:
    """
    Switch document upload to use Service Account instead of OAuth.
    This is a fallback when OAuth token is expired/revoked.
    """
    pool = getattr(request.app.state, "db_pool", None)
    if not pool:
        return {"status": "error", "message": "Database pool not available"}

    try:
        # Check if Service Account is configured
        sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not sa_path:
            return {
                "status": "error",
                "message": "Service Account not configured",
                "env_var": "GOOGLE_APPLICATION_CREDENTIALS",
            }

        # Check if file exists
        if not os.path.exists(sa_path):
            return {"status": "error", "message": f"Service Account file not found: {sa_path}"}

        # Test Service Account
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = service_account.Credentials.from_service_account_file(
            sa_path, scopes=["https://www.googleapis.com/auth/drive"],
        )

        service = build("drive", "v3", credentials=credentials)

        # Test API call
        about = service.about().get(fields="user").execute()
        user = about.get("user", {})

        return {
            "status": "success",
            "message": "Service Account is working",
            "service_account_email": user.get("emailAddress"),
            "display_name": user.get("displayName"),
            "note": "Update portal_service.py to use TeamDriveService for uploads",
        }

    except Exception as e:
        return {"status": "error", "message": f"Service Account test failed: {str(e)}"}


@router.get("/service-account-status")
async def service_account_status() -> dict[str, Any]:
    """Check if Service Account is configured."""
    sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    return {
        "configured": bool(sa_path),
        "path": sa_path,
        "file_exists": os.path.exists(sa_path) if sa_path else False,
    }


@router.get("/test-list-files")
async def test_list_files(request: Request) -> dict[str, Any]:
    """
    Test Drive file listing via Service Account (public endpoint for diagnostics).
    Lists first 5 files to verify SA connectivity.
    """
    try:
        from backend.services.integrations.team_drive_service import TeamDriveService

        drive = TeamDriveService()
        result = await drive.list_files(page_size=5)
        files = result.get("files", [])
        return {
            "status": "success",
            "mode": "service_account",
            "file_count": len(files),
            "files": [
                {"name": f.get("name"), "type": f.get("mimeType"), "id": f.get("id")} for f in files
            ],
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
