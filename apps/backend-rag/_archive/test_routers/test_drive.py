"""Test Drive connectivity - public endpoint."""

import os

from fastapi import APIRouter

router = APIRouter()


@router.get("/test/drive-status")
async def test_drive_status():
    """Test Google Drive Service Account connectivity."""
    from backend.services.integrations.service_account_drive_service import (
        ServiceAccountDriveService,
    )

    has_creds = bool(os.environ.get("GOOGLE_CREDENTIALS_JSON"))
    prefer_sa = os.environ.get("GOOGLE_DRIVE_PREFER_SERVICE_ACCOUNT", "").lower() == "true"

    try:
        drive = ServiceAccountDriveService()
        # Try to get Individuals folder structure
        result = await drive.get_folder_structure(
            root_folder_id="1mNi2FkhZqP9inJH2Y1taXLCgS95UkYk4"  # Individual_CRM
        )
        return {
            "service_account_configured": has_creds,
            "prefer_service_account": prefer_sa,
            "drive_accessible": True,
            "individuals_folder_name": result.get("root_folder_name", "unknown"),
            "subfolders_count": len(result.get("folders", [])),
            "status": "✅ Google Drive Service Account working!",
        }
    except Exception as e:
        return {
            "service_account_configured": has_creds,
            "prefer_service_account": prefer_sa,
            "drive_accessible": False,
            "error": str(e),
            "status": "❌ Drive connection failed",
        }
