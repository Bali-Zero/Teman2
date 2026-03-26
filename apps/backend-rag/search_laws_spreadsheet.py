
import asyncio
import logging
import os
import sys

# Aggiungi il percorso del progetto al PYTHONPATH
sys.path.append(os.getcwd())

from backend.services.integrations.service_account_drive_service import ServiceAccountDriveService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    try:
        drive_service = ServiceAccountDriveService()

        # Query per cercare fogli di calcolo con parole chiave specifiche
        keywords = ["Laws", "Peraturan", "UU", "PP", "Permen", "Legislation"]

        all_found_files = []

        for kw in keywords:
            query = f"name contains '{kw}' and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
            logger.info(f"Searching for: {query}")

            request = drive_service.service.files().list(
                q=query,
                fields="files(id, name, webViewLink, mimeType)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )

            result = await asyncio.to_thread(request.execute)
            files = result.get("files", [])
            all_found_files.extend(files)

        # Rimuovi duplicati (file che potrebbero corrispondere a più parole chiave)
        unique_files = {f["id"]: f for f in all_found_files}.values()

        if not unique_files:
            print("No files found with the specified keywords.")
            return

        print(f"\nFound {len(unique_files)} unique spreadsheet(s):")
        for f in unique_files:
            print(f"Name: {f['name']}")
            print(f"ID: {f['id']}")
            print(f"URL: {f['webViewLink']}")
            print("-" * 20)

    except Exception as e:
        logger.error(f"Error during search: {e}")

if __name__ == "__main__":
    asyncio.run(main())
