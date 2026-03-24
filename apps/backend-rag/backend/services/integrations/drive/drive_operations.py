import logging
from typing import Any

import httpx

# Import del decoratore di audit e metriche (estratto precedentemente)
from backend.services.integrations.drive.drive_audit import drive_operation

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DriveOperationsManager:
    """
    Gestisce le operazioni CRUD (Create, Read, Update, Delete) su Google Drive.
    Utilizza httpx in modo nativamente asincrono, evitando l'import bloccante
    di googleapiclient.discovery (basato su httplib2 sincrono).
    """

    def __init__(self, auth_manager: Any, http_client: httpx.AsyncClient, audit: Any | None = None):
        self.auth_manager = auth_manager
        self.http_client = http_client
        self.audit = audit  # Permette al decoratore @drive_operation di usare l'istanza corretta

    @drive_operation("list_files")
    async def list_files(
        self,
        user_email: str,
        folder_id: str | None = None,
        q: str | None = None,
        page_size: int = 50,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """
        Recupera la lista dei file in modo asincrono tramite l'API v3 di Google Drive.
        """
        # 1. Recupero del token (gestisce in automatico il DB OAuth o il fallback Service Account)
        token = await self.auth_manager.get_access_token(user_email)
        if not token:
            raise PermissionError(f"Impossibile ottenere un token di accesso per {user_email}")

        # 2. Configurazione Headers per l'API REST
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        # 3. Costruzione sicura della query (Google Drive Search string)
        query_parts = ["trashed=false"]
        if folder_id:
            query_parts.append(f"'{folder_id}' in parents")
        if q:
            query_parts.append(q)

        params = {
            "q": " and ".join(query_parts),
            "pageSize": page_size,
            "fields": "nextPageToken, files(id, name, mimeType, size, modifiedTime, webViewLink, thumbnailLink)",
        }
        if page_token:
            params["pageToken"] = page_token

        # 4. Chiamata HTTPX puramente asincrona
        response = await self.http_client.get(
            "https://www.googleapis.com/drive/v3/files", headers=headers, params=params
        )

        # Propaga l'errore HTTP (che verrà catturato dal decoratore @drive_operation per i log)
        response.raise_for_status()

        return response.json()

    @drive_operation("get_file_metadata")
    async def get_file_metadata(self, user_email: str, file_id: str) -> dict[str, Any]:
        """
        Recupera i metadati di un singolo file usando httpx.
        """
        token = await self.auth_manager.get_access_token(user_email)
        if not token:
            raise PermissionError("Autenticazione fallita durante il recupero dei metadati.")

        headers = {"Authorization": f"Bearer {token}"}
        params = {"fields": "id, name, mimeType, size, modifiedTime, webViewLink, thumbnailLink"}

        response = await self.http_client.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}", headers=headers, params=params
        )
        response.raise_for_status()

        return response.json()
