import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "apps", "backend-rag"))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from backend.services.integrations.service_account_drive_service import (
    ServiceAccountDriveService,
)


async def main():
    logger.info("🧪 Starting Drive Service Verification...")

    try:
        service = ServiceAccountDriveService()
        logger.info("✅ Service Initialized")

        # Test 1: List Root (verifies supportsAllDrives=True on get/list)
        logger.info(f"📂 Listing root folder: {service.root_folder_id}")
        structure = await service.get_folder_structure(service.root_folder_id)
        logger.info(
            f"✅ List Success. Found {len(structure['folders'])} folders and {structure['total_files']} files."
        )

        # Test 2: Create Test Folder (verifies supportsAllDrives=True on create)
        folder_name = "SENTINEL_VERIFICATION_FOLDER"
        logger.info(f"📁 Creating test folder: {folder_name}")
        folder = await service.create_folder(folder_name)
        folder_id = folder["id"]
        logger.info(f"✅ Create Success. ID: {folder_id}")

        # Test 3: Upload File (verifies supportsAllDrives=True on create media)
        logger.info("📄 Uploading test file...")
        await service.upload_file_to_folder(
            folder_id=folder_id,
            file_content=b"Verification timestamp",
            file_name="sentinel_check.txt",
            mime_type="text/plain",
        )
        logger.info("✅ Upload Success")

        print("\n✨ ALL TESTS PASSED: Service is compliant with Shared Drive logic.")

    except Exception as e:
        logger.error(f"❌ Test Failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # We must activate the venv and set pythonpath before running this,
    # but the script assumes the environment is ready.
    asyncio.run(main())
