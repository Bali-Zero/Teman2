import logging
from typing import Any

import httpx

# Import del decoratore di audit e metriche
from backend.services.integrations.drive.drive_audit import drive_operation

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DrivePermissionsManager:
    """
    Gestisce le operazioni di ACL (Access Control List) e permessi su Google Drive.
    Utilizza httpx per chiamate asincrone non bloccanti all'API v3 di Google Drive,
    evitando l'uso della SDK sincrona ufficiale.
    """

    def __init__(self, auth_manager: Any, http_client: httpx.AsyncClient, audit: Any | None = None) -> None:
        self.auth_manager = auth_manager
        self.http_client = http_client
        self.audit = audit

    def _get_headers(self, token: str) -> dict[str, str]:
        """Utility per costruire gli header autorizzativi REST standard."""
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    @drive_operation("list_permissions")
    async def list_permissions(self, user_email: str, file_id: str) -> list[dict[str, Any]]:
        """
        Recupera la lista dei permessi per un file o cartella.
        Mappa automaticamente i campi Google Drive nel modello PermissionItem.
        """
        token = await self.auth_manager.get_access_token(user_email)
        if not token:
            raise PermissionError(f"Impossibile ottenere il token di accesso per {user_email}")

        params = {"fields": "permissions(id, emailAddress, displayName, role, type)"}

        response = await self.http_client.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions",
            headers=self._get_headers(token),
            params=params,
        )
        response.raise_for_status()  # Propaga l'HTTPStatusError al decoratore per l'audit

        data = response.json()
        permissions = []

        # Normalizzazione in linea con il modello Pydantic `PermissionItem`
        for perm in data.get("permissions", []):
            permissions.append(
                {
                    "id": perm.get("id"),
                    "email": perm.get("emailAddress", ""),
                    "name": perm.get("displayName", ""),
                    "role": perm.get("role"),
                    "type": perm.get("type"),
                },
            )

        return permissions

    @drive_operation("add_permission")
    async def add_permission(self, user_email: str, file_id: str, request: Any) -> dict[str, Any]:
        """
        Aggiunge un permesso (condivisione) a un file o cartella e invia opzionalmente un'email.
        """
        token = await self.auth_manager.get_access_token(user_email)
        if not token:
            raise PermissionError("Autenticazione fallita durante l'aggiunta dei permessi.")

        # Estrazione sicura che supporta sia dizionari che modelli Pydantic (es. AddPermissionRequest)
        email = getattr(request, "email", None) or (
            request.get("email") if isinstance(request, dict) else None
        )
        role = getattr(request, "role", None) or (
            request.get("role") if isinstance(request, dict) else None
        )

        send_notification = getattr(request, "send_notification", True)
        if isinstance(request, dict) and "send_notification" in request:
            send_notification = request["send_notification"]

        body = {"type": "user", "role": role, "emailAddress": email}
        params = {
            "sendNotificationEmail": "true" if send_notification else "false",
            "fields": "id, emailAddress, displayName, role, type",
        }

        response = await self.http_client.post(
            f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions",
            headers=self._get_headers(token),
            params=params,
            json=body,
        )
        response.raise_for_status()

        perm = response.json()
        return {
            "id": perm.get("id"),
            "email": perm.get("emailAddress", ""),
            "name": perm.get("displayName", ""),
            "role": perm.get("role"),
            "type": perm.get("type"),
        }

    @drive_operation("update_permission")
    async def update_permission(
        self, user_email: str, file_id: str, permission_id: str, request: Any,
    ) -> dict[str, Any]:
        """
        Aggiorna il ruolo di un permesso esistente (es. da 'reader' a 'writer').
        """
        token = await self.auth_manager.get_access_token(user_email)
        if not token:
            raise PermissionError("Autenticazione fallita durante l'aggiornamento dei permessi.")

        role = getattr(request, "role", None) or (
            request.get("role") if isinstance(request, dict) else None
        )

        body = {"role": role}
        params = {"fields": "id, emailAddress, displayName, role, type"}

        response = await self.http_client.patch(
            f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions/{permission_id}",
            headers=self._get_headers(token),
            params=params,
            json=body,
        )
        response.raise_for_status()

        perm = response.json()
        return {
            "id": perm.get("id"),
            "email": perm.get("emailAddress", ""),
            "name": perm.get("displayName", ""),
            "role": perm.get("role"),
            "type": perm.get("type"),
        }

    @drive_operation("remove_permission")
    async def remove_permission(
        self, user_email: str, file_id: str, permission_id: str,
    ) -> dict[str, bool]:
        """
        Rimuove / revoca un permesso di accesso a un file o cartella.
        """
        token = await self.auth_manager.get_access_token(user_email)
        if not token:
            raise PermissionError("Autenticazione fallita durante la revoca dei permessi.")

        response = await self.http_client.delete(
            f"https://www.googleapis.com/drive/v3/files/{file_id}/permissions/{permission_id}",
            headers=self._get_headers(token),
        )
        response.raise_for_status()

        return {"success": True}
