"""Google Drive Tools - 5 tools for team file management."""

from typing import Optional


def register(mcp, _call, _call_safe):
    @mcp.tool()
    async def list_drive_files(
        folder_id: Optional[str] = None, limit: int = 30
    ) -> dict:
        """
        List files in Google Drive (team service account).

        Args:
            folder_id: Folder ID to list (root if not specified)
            limit: Max files to return

        Returns:
            List of files with name, type, size, modified_date, download_url.
        """
        params: dict = {"limit": limit}
        if folder_id:
            params["folder_id"] = folder_id
        return await _call("/api/drive/files", params=params)

    @mcp.tool()
    async def search_drive(query: str, limit: int = 10) -> dict:
        """
        Search files in Google Drive.

        Args:
            query: Search query (file name, content keywords)
            limit: Max results

        Returns:
            Matching files ranked by relevance.
        """
        return await _call(
            "/api/drive/search", params={"q": query, "limit": limit}
        )

    @mcp.tool()
    async def create_drive_folder(name: str, parent_id: Optional[str] = None) -> dict:
        """
        Create a new folder in Google Drive.

        Args:
            name: Folder name
            parent_id: Parent folder ID (root if not specified)

        Returns:
            Created folder record with ID and URL.
        """
        payload: dict = {"name": name}
        if parent_id:
            payload["parent_id"] = parent_id
        return await _call(
            "/api/drive/folders", method="POST", json=payload
        )

    @mcp.tool()
    async def get_drive_storage_stats() -> dict:
        """
        Get Google Drive storage statistics.

        Returns:
            Total storage used, files count, folders count, largest files, storage by type.
        """
        return await _call("/api/drive/stats")

    @mcp.tool()
    async def create_client_drive_folder(client_id: str) -> dict:
        """
        Create a structured Drive folder for a CRM client.

        Creates a folder with standard subfolders: Passport, Visa, Company, Tax, Legal, Other.

        Args:
            client_id: UUID of the CRM client

        Returns:
            Created folder structure with IDs and URLs.
        """
        return await _call(
            f"/api/crm/drive-folders/{client_id}", method="POST"
        )
