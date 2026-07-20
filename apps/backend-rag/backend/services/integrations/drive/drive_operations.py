import logging
import time
from typing import Any

import httpx

# Import del decoratore di audit e metriche (estratto precedentemente)
from backend.services.integrations.drive.drive_audit import drive_operation

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


def _normalize_drive_file(f: dict[str, Any]) -> dict[str, Any]:
    """Drive API v3 returns no `type` field and `size` as a string (absent for
    folders and Google-native docs); the team_drive router contract requires
    `type` ('file'|'folder') and an int `size` on every item."""
    f["type"] = "folder" if f.get("mimeType") == _FOLDER_MIME_TYPE else "file"
    f["size"] = int(f.get("size") or 0)
    return f


class DriveOperationsManager:
    """
    Gestisce le operazioni CRUD (Create, Read, Update, Delete) su Google Drive.
    Utilizza httpx in modo nativamente asincrono, evitando l'import bloccante
    di googleapiclient.discovery (basato su httplib2 sincrono).
    """

    def __init__(
        self, auth_manager: Any, http_client: httpx.AsyncClient, audit: Any | None = None
    ) -> None:
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
            "https://www.googleapis.com/drive/v3/files",
            headers=headers,
            params=params,
        )

        # Propaga l'errore HTTP (che verrà catturato dal decoratore @drive_operation per i log)
        response.raise_for_status()

        data = response.json()
        data["files"] = [_normalize_drive_file(f) for f in data.get("files", [])]
        return data

    @drive_operation("search_files")
    async def search_files(
        self,
        user_email: str,
        query: str,
        file_type: str | None = None,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """Search files by name/content across the user's Drive."""
        token = await self.auth_manager.get_access_token(user_email)
        if not token:
            raise PermissionError(f"Impossibile ottenere un token di accesso per {user_email}")

        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        mime_map = {
            "folder": "application/vnd.google-apps.folder",
            "document": "application/vnd.google-apps.document",
            "spreadsheet": "application/vnd.google-apps.spreadsheet",
            "pdf": "application/pdf",
        }

        query_parts = ["trashed=false", f"name contains '{query}'"]
        if file_type and file_type in mime_map:
            query_parts.append(f"mimeType='{mime_map[file_type]}'")

        params = {
            "q": " and ".join(query_parts),
            "pageSize": min(page_size, 50),
            "fields": "files(id, name, mimeType, size, modifiedTime, webViewLink, parents)",
        }

        response = await self.http_client.get(
            "https://www.googleapis.com/drive/v3/files",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        return [_normalize_drive_file(f) for f in response.json().get("files", [])]

    @drive_operation("get_storage_stats")
    async def get_storage_stats(
        self, user_email: str, max_pages: int = 20, max_seconds: float = 10.0
    ) -> dict[str, Any]:
        """Aggregate storage statistics for the team Drive.

        `storage_used_bytes`/`storage_limit_bytes` come from a single, exact
        `about.get` call — independent of the walk below. `files_count`/
        `folders_count`/`storage_by_type`/`largest_files` come from a
        paginated `files.list` walk (pageSize 1000, capped at `max_pages`
        pages OR `max_seconds` wall-clock time, whichever hits first).
        If the drive has more pages than the cap allows, `truncated=True` and
        `scanned_pages` say so explicitly — a partial count is never returned
        silently as if it were the total.
        """
        token = await self._token(user_email)
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        about_response = await self.http_client.get(
            "https://www.googleapis.com/drive/v3/about",
            headers=headers,
            params={"fields": "storageQuota,user"},
        )
        about_response.raise_for_status()
        about_data = about_response.json()
        quota = about_data.get("storageQuota", {})
        quota_measured_as = about_data.get("user", {}).get("emailAddress")

        files_count = 0
        folders_count = 0
        storage_by_type: dict[str, int] = {}
        all_files: list[dict[str, Any]] = []
        page_token: str | None = None
        scanned_pages = 0
        truncated = False
        walk_deadline = time.monotonic() + max_seconds

        while True:
            params: dict[str, Any] = {
                "q": "trashed=false",
                "pageSize": 1000,
                "fields": "nextPageToken, files(id, name, mimeType, size)",
            }
            if page_token:
                params["pageToken"] = page_token

            response = await self.http_client.get(
                "https://www.googleapis.com/drive/v3/files",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            scanned_pages += 1

            for raw in data.get("files", []):
                f = _normalize_drive_file(raw)
                if f["type"] == "folder":
                    folders_count += 1
                else:
                    files_count += 1
                    storage_by_type[f["mimeType"]] = (
                        storage_by_type.get(f["mimeType"], 0) + f["size"]
                    )
                    all_files.append(f)

            page_token = data.get("nextPageToken")
            if not page_token:
                break
            if scanned_pages >= max_pages or time.monotonic() >= walk_deadline:
                truncated = True
                break

        all_files.sort(key=lambda f: f["size"], reverse=True)
        largest_files = [
            {"id": f["id"], "name": f["name"], "size": f["size"]} for f in all_files[:10]
        ]

        limit = quota.get("limit")
        return {
            "storage_used_bytes": int(quota.get("usage") or 0),
            "storage_limit_bytes": int(limit) if limit else None,
            "quota_measured_as": quota_measured_as,
            "files_count": files_count,
            "folders_count": folders_count,
            "storage_by_type": storage_by_type,
            "largest_files": largest_files,
            "scanned_pages": scanned_pages,
            "truncated": truncated,
        }

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
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            headers=headers,
            params=params,
        )
        response.raise_for_status()

        return _normalize_drive_file(response.json())

    async def _token(self, user_email: str) -> str:
        token = await self.auth_manager.get_access_token(user_email)
        if not token:
            raise PermissionError(f"Impossibile ottenere un token di accesso per {user_email}")
        return token

    @drive_operation("delete_file")
    async def delete_file(
        self, user_email: str, file_id: str, permanent: bool = False
    ) -> dict[str, Any]:
        """Trash (default) or permanently delete a file via Drive API v3.

        ``permanent=False`` → ``PATCH {trashed:true}`` (recoverable from the bin).
        ``permanent=True``  → ``DELETE`` (irreversible). Mirrors the httpx pattern of
        the read methods above. Returns a small status dict the router surfaces.
        """
        token = await self._token(user_email)
        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}"

        if permanent:
            response = await self.http_client.delete(url, headers=headers)
            response.raise_for_status()  # 204 No Content on success
            return {"id": file_id, "deleted": True, "permanent": True}

        response = await self.http_client.patch(
            url,
            headers={**headers, "Content-Type": "application/json"},
            params={"fields": "id, trashed"},
            json={"trashed": True},
        )
        response.raise_for_status()
        return {"id": file_id, "trashed": True, "permanent": False}

    @drive_operation("move_file")
    async def move_file(
        self,
        user_email: str,
        file_id: str,
        new_parent_id: str,
        old_parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Move a file by re-parenting it (Drive API v3 addParents/removeParents).

        When ``old_parent_id`` is omitted the current parent is looked up first so the
        file is not left multi-homed (Drive allows multiple parents; we keep exactly one).
        """
        token = await self._token(user_email)
        headers = {"Authorization": f"Bearer {token}"}

        remove_parent = old_parent_id
        if remove_parent is None:
            meta = await self.http_client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                headers=headers,
                params={"fields": "parents"},
            )
            meta.raise_for_status()
            parents = meta.json().get("parents") or []
            remove_parent = parents[0] if parents else None

        params: dict[str, Any] = {
            "addParents": new_parent_id,
            "fields": "id, name, parents, mimeType, modifiedTime, webViewLink",
        }
        if remove_parent:
            params["removeParents"] = remove_parent

        response = await self.http_client.patch(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            headers={**headers, "Content-Type": "application/json"},
            params=params,
            json={},
        )
        response.raise_for_status()
        return response.json()

    @drive_operation("copy_file")
    async def copy_file(
        self,
        user_email: str,
        file_id: str,
        new_name: str | None = None,
        parent_folder_id: str | None = None,
    ) -> dict[str, Any]:
        """Copy a file (Drive API v3 files.copy). Optionally rename + place in a folder."""
        token = await self._token(user_email)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        body: dict[str, Any] = {}
        if new_name:
            body["name"] = new_name
        if parent_folder_id:
            body["parents"] = [parent_folder_id]

        response = await self.http_client.post(
            f"https://www.googleapis.com/drive/v3/files/{file_id}/copy",
            headers=headers,
            params={"fields": "id, name, parents, mimeType, modifiedTime, webViewLink"},
            json=body,
        )
        response.raise_for_status()
        return response.json()
