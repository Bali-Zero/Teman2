"""
Document Retrieval Service
Responsibility: PDF download and document handling from Google Drive
"""

import io
import logging
import os
from typing import Optional

from googleapiclient.http import MediaIoBaseDownload

from services.oracle_google_services import google_services

logger = logging.getLogger(__name__)


class DocumentRetrievalService:
    """
    Service for document retrieval from Google Drive.

    Responsibility: Download PDFs from Google Drive using fuzzy search.
    """

    def download_pdf_from_drive(self, filename: str) -> Optional[str]:
        """
        Download PDF from Google Drive using fuzzy search.

        Args:
            filename: PDF filename to search for

        Returns:
            Temporary file path if found, None otherwise
        """
        if not google_services.drive_service:
            logger.warning("⚠️ Google Drive service not available")
            return None

        try:
            clean_name = os.path.splitext(os.path.basename(filename))[0]
            logger.info(f"🔍 Searching for document: {clean_name}")

            search_queries = [
                f"name contains '{clean_name}' and mimeType = 'application/pdf' and trashed = false",
                f"name contains '{clean_name.replace('_', ' ')}' and mimeType = 'application/pdf' and trashed = false",
                f"name contains '{clean_name.replace('-', ' ')}' and mimeType = 'application/pdf' and trashed = false",
                f"name contains '{clean_name.replace('_', '')}' and mimeType = 'application/pdf' and trashed = false",
            ]

            for query in search_queries:
                results = (
                    google_services.drive_service.files()
                    .list(q=query, fields="files(id, name, size, createdTime)", pageSize=1)
                    .execute()
                )

                files = results.get("files", [])
                if files:
                    found_file = files[0]
                    logger.info(f"✅ Found match: '{found_file['name']}' (ID: {found_file['id']})")

                    request = google_services.drive_service.files().get_media(
                        fileId=found_file["id"]
                    )
                    file_stream = io.BytesIO()
                    downloader = MediaIoBaseDownload(file_stream, request)

                    done = False
                    while done is False:
                        status, done = downloader.next_chunk()

                    file_stream.seek(0)
                    temp_path = f"/tmp/{found_file['name']}"

                    with open(temp_path, "wb") as temp_file:
                        temp_file.write(file_stream.read())

                    return temp_path

            return None

        except Exception as e:
            logger.error(f"❌ Error downloading from Drive: {e}")
            return None
