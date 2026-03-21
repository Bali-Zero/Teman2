"""Test Drive folder creation - public endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/test/drive-create-folder")
async def test_drive_create_folder():
    """Force create a test folder in Drive."""
    import uuid

    from backend.services.integrations.service_account_drive_service import (
        ServiceAccountDriveService,
    )

    try:
        drive = ServiceAccountDriveService()

        # Create test folder
        test_name = f"TEST_{uuid.uuid4().hex[:8]}"
        result = await drive.create_client_folder(
            client_id=99999, client_name=test_name, client_type="individual"
        )

        return {
            "success": True,
            "folder_created": result.get("root_folder_id") is not None,
            "folder_id": result.get("root_folder_id"),
            "folder_url": result.get("root_folder_url"),
            "subfolders": list(result.get("subfolders", {}).keys()),
        }
    except Exception as e:
        import traceback

        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}
