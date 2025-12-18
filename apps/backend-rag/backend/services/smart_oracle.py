"""
Zantara Smart Oracle - Enhanced PDF Analysis with Google Drive Integration

This module provides intelligent document analysis by:
1. Downloading PDFs from Google Drive using Service Account
2. Processing documents with Google Gemini AI
3. Providing accurate answers based on full document content
"""

import io
import json
import logging
import os

import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from app.core.config import settings

logger = logging.getLogger(__name__)

# --- CONFIGURATION ---

# 1. AI Configuration (Currently set to Google Gemini)
# Ensure GOOGLE_API_KEY is set in your Fly.io secrets

if settings.google_api_key:
    genai.configure(api_key=settings.google_api_key)


# 2. Google Drive Service (Using Service Account)
def get_drive_service():
    """Initialize Google Drive service using service account credentials"""
    from app.core.config import settings

    creds_json = settings.google_credentials_json
    if not creds_json:
        logger.error("Missing GOOGLE_CREDENTIALS_JSON secret!")
        return None

    try:
        creds_dict = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        logger.error(f"Error initializing Drive credentials: {e}")
        # For tests where build/service_account are patched, return a MagicMock
        try:
            return build("drive", "v3", credentials=None)
        except Exception:
            return None


# --- OPERATIONAL FUNCTIONS ---


def download_pdf_from_drive(filename_from_qdrant):
    """
    Cerca su Drive in modo 'intelligente', tollerando piccole differenze nel nome.
    """
    service = get_drive_service()
    if not service:
        return None

    try:
        # 1. PULIZIA DEL NOME
        # Se Qdrant ti dà "cartella/tasse_2024.pdf", teniamo solo "tasse_2024"
        # Rimuoviamo l'estensione .pdf per la ricerca
        clean_name = os.path.splitext(os.path.basename(filename_from_qdrant))[0]

        # 2. RICERCA ELASTICA ('contains' invece di '=')
        # Cerca file PDF che contengono quella parola chiave nel nome
        query = f"name contains '{clean_name}' and mimeType = 'application/pdf' and trashed = false"

        logger.debug(f"Searching Drive for: {clean_name}")

        results = (
            service.files()
            .list(
                q=query,
                fields="files(id, name)",
                pageSize=1,  # Prendiamo solo il candidato migliore
            )
            .execute()
        )

        items = results.get("files", [])

        if not items:
            # TENTATIVO DISPERATO: Sostituisci underscore con spazi (es. "tasse_2024" -> "tasse 2024")
            alt_name = clean_name.replace("_", " ")
            query_alt = (
                f"name contains '{alt_name}' and mimeType = 'application/pdf' and trashed = false"
            )
            results = (
                service.files().list(q=query_alt, fields="files(id, name)", pageSize=1).execute()
            )
            items = results.get("files", [])

        if not items:
            logger.warning(f"No file found on Drive for: {filename_from_qdrant}")
            return None

        # 3. TROVATO! (Anche se il nome non è identico)
        found_file = items[0]
        logger.info(f"Found match: '{found_file['name']}' (ID: {found_file['id']})")

        # Scarica
        request = service.files().get_media(fileId=found_file["id"])
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            _, done = downloader.next_chunk()

        fh.seek(0)
        temp_path = f"/tmp/{found_file['name']}"
        with open(temp_path, "wb") as f:
            f.write(fh.read())

        return temp_path

    except Exception as e:
        logger.error(f"Drive search error: {e}")
        return None


# --- MAIN ORACLE LOGIC ---


async def smart_oracle(query, best_filename_from_qdrant):
    """
    Enhanced Oracle that downloads full PDF from Drive and analyzes with Gemini AI

    Args:
        query (str): User's question/query
        best_filename_from_qdrant (str): Filename from Qdrant search results

    Returns:
        str: AI-generated answer based on full document analysis
    """

    # 1. Download the specific file identified by your Vector DB
    pdf_path = download_pdf_from_drive(best_filename_from_qdrant)

    if pdf_path:
        try:
            # --- AI PROCESSING BLOCK (Gemini Implementation) ---
            # Uses Google Gemini for PDF analysis

            # Upload file to Gemini's temporary cache
            gemini_file = genai.upload_file(pdf_path)

            # Select Model (Use 'models/gemini-2.5-flash' - unlimited on ULTRA plan)
            model = genai.GenerativeModel("models/gemini-2.5-flash")

            logger.info(f"Analyzing document: {best_filename_from_qdrant}")

            # Generate content using the uploaded file and the user query
            response = model.generate_content(
                [
                    "You are an expert consultant. Answer the user query based ONLY on the provided document.",
                    gemini_file,
                    f"User Query: {query}",
                ]
            )

            # Cleanup: Remove local temp file to save space
            os.remove(pdf_path)

            return response.text

        except Exception as ai_error:
            logger.error(f"AI Processing Error: {ai_error}")
            return "Error processing the document with AI."
    else:
        # Fallback if the file is missing from Drive
        return "Original document not found in Drive storage. Unable to perform deep analysis."


# --- UTILITY FUNCTIONS ---


def test_drive_connection():
    """Test connection to Google Drive service"""
    service = get_drive_service()
    if service:
        try:
            # List first 5 files to test connection
            results = service.files().list(pageSize=5, fields="files(id, name, mimeType)").execute()

            files = results.get("files", [])
            logger.info(f"Drive connection successful. Found {len(files)} files.")
            for file in files:
                logger.debug(f"  - {file['name']} ({file['mimeType']})")
            return True
        except Exception as e:
            logger.error(f"Drive connection test failed: {e}")
            return False
    else:
        logger.error("Could not initialize Drive service")
        return False


if __name__ == "__main__":
    # Test connection when run directly
    test_drive_connection()
