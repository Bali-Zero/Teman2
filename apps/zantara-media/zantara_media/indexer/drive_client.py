"""
Google Drive v3 async client for GARUDA change-feed indexing.

All blocking Drive API calls are wrapped in asyncio.get_event_loop().run_in_executor()
so they never block the event loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GARUDA folder constants
# ---------------------------------------------------------------------------

GARUDA_ROOT_ID = "1xjkBpgic3tZl3_K1u7vy-qJpw7XzpIYN"

GARUDA_SUBFOLDER_IDS: frozenset[str] = frozenset(
    {
        "1xjkBpgic3tZl3_K1u7vy-qJpw7XzpIYN",  # root GARUDA
        "1c9QnRb22XdcrFH8ukxgJeWW41soZhzVq",  # photos
        "1QZ6hnEqUAxIwhz6yhWeXh6m3QsgFnJ6G",  # videos
        "1CX2K-MtRQVMqDwlbcT9gLTGf4mGmGVh3",  # audio
        "1n3VjN-YZGGH-6-yByxIi0rLGxi4iTDu1",  # intelligence
        "1b7ERuRssLPAxKYHtAhv2Kx-G81ot0Ulb",  # drafts
        "18E-rHjO94JFqao1xMCoA2mmy4oK9Waw7",  # research
        "1dX87C514aOZO82NTxl8meHiiO3dhIJNl",  # published
    }
)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DriveFile:
    id: str
    name: str
    mime_type: str
    parents: list[str]
    size: int
    modified_time: datetime
    version: int
    trashed: bool


@dataclass
class Change:
    change_type: str  # typically "file"
    file_id: str
    file: DriveFile | None
    removed: bool
    is_tombstone: bool  # True if removed or file.trashed
    next_page_token: str | None = field(default=None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_drive_file(data: dict) -> DriveFile:
    """Parse a raw Drive API file resource into a DriveFile dataclass."""
    raw_time = data.get("modifiedTime", "1970-01-01T00:00:00Z")
    try:
        modified_time = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
    except ValueError:
        modified_time = datetime.utcfromtimestamp(0)

    return DriveFile(
        id=data.get("id", ""),
        name=data.get("name", ""),
        mime_type=data.get("mimeType", ""),
        parents=data.get("parents", []),
        size=int(data.get("size", 0)),
        modified_time=modified_time,
        version=int(data.get("version", 0)),
        trashed=bool(data.get("trashed", False)),
    )


def _parse_change(change_data: dict) -> Change:
    """Parse a raw Drive API change resource into a Change dataclass."""
    removed = bool(change_data.get("removed", False))

    raw_file = change_data.get("file")
    drive_file: DriveFile | None = None
    file_trashed = False
    if raw_file:
        drive_file = _parse_drive_file(raw_file)
        file_trashed = drive_file.trashed

    is_tombstone = removed or file_trashed

    return Change(
        change_type=change_data.get("type", "file"),
        file_id=change_data.get("fileId", ""),
        file=drive_file,
        removed=removed,
        is_tombstone=is_tombstone,
        next_page_token=None,  # filled by the generator after paging
    )


# ---------------------------------------------------------------------------
# OAuth / service construction
# ---------------------------------------------------------------------------


async def get_drive_service():  # type: ignore[return]
    """
    Build and return a Google Drive v3 service object.

    Token resolution order:
    1. ``GOOGLE_DRIVE_CREDENTIALS_FILE`` env var → path to OAuth2 JSON file.
    2. ``google_drive_tokens`` Postgres table (asyncpg, DATABASE_URL).

    The blocking ``build()`` call is wrapped in run_in_executor.
    """
    loop = asyncio.get_event_loop()

    creds_file = os.environ.get("GOOGLE_DRIVE_CREDENTIALS_FILE")
    if creds_file:
        creds = await loop.run_in_executor(None, _load_creds_from_file, creds_file)
    else:
        creds = await _load_creds_from_db()

    service = await loop.run_in_executor(None, _build_drive_service, creds)
    return service


def _load_creds_from_file(path: str):
    """Load OAuth2 credentials from a JSON file (blocking)."""
    from google.oauth2.credentials import Credentials  # type: ignore[import]

    with open(path) as fh:
        data = json.load(fh)

    # Support both raw token JSON and "installed" / "web" client-secret format.
    if "token" in data:
        return Credentials(
            token=data["token"],
            refresh_token=data.get("refresh_token"),
            token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=data.get("client_id"),
            client_secret=data.get("client_secret"),
            scopes=data.get("scopes"),
        )
    raise ValueError(f"Unrecognised credential format in {path!r}")


async def _load_creds_from_db():
    """
    Load OAuth2 credentials from the ``google_drive_tokens`` Postgres table.

    Schema (matches backend-rag/services/integrations/drive/drive_auth.py):
      user_id, access_token, refresh_token, expires_at, created_at, updated_at

    client_id/client_secret/token_uri come from env vars (same as backend-rag).
    Defaults to user_id='SYSTEM' (system-wide Drive access).
    """
    import asyncpg  # type: ignore[import]
    from google.oauth2.credentials import Credentials  # type: ignore[import]

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "Neither GOOGLE_DRIVE_CREDENTIALS_FILE nor DATABASE_URL is set; "
            "cannot load Drive OAuth tokens."
        )

    user_id = os.environ.get("GARUDA_DRIVE_USER_ID", "SYSTEM")
    conn = await asyncpg.connect(database_url)
    try:
        row = await conn.fetchrow(
            "SELECT access_token, refresh_token, expires_at FROM google_drive_tokens "
            "WHERE user_id = $1",
            user_id,
        )
    finally:
        await conn.close()

    if not row:
        raise RuntimeError(
            f"No rows found in google_drive_tokens for user_id={user_id!r}."
        )

    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(
            "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET env vars required for OAuth refresh."
        )

    return Credentials(
        token=row["access_token"],
        refresh_token=row["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=[
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )


def _build_drive_service(creds):
    """Build the Drive API service (blocking wrapper)."""
    from googleapiclient.discovery import build  # type: ignore[import]

    return build("drive", "v3", credentials=creds, cache_discovery=False)


# ---------------------------------------------------------------------------
# DriveClient
# ---------------------------------------------------------------------------


class DriveClient:
    """Async wrapper around the Google Drive v3 changes API."""

    def __init__(self, service=None) -> None:
        """
        Parameters
        ----------
        service:
            Pre-built Drive API service (useful for testing / injection).
            If None, ``get_drive_service()`` is called on first use.
        """
        self._service = service

    async def _get_service(self):
        if self._service is None:
            self._service = await get_drive_service()
        return self._service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_start_page_token(self) -> str:
        """Return the current start page token for the Drive changes feed."""
        service = await self._get_service()
        loop = asyncio.get_event_loop()

        def _call() -> dict:
            return service.changes().getStartPageToken().execute()

        result: dict = await loop.run_in_executor(None, _call)
        token: str = result["startPageToken"]
        logger.debug("Fetched start page token: %s", token)
        return token

    async def list_changes(
        self,
        page_token: str,
        page_size: int = 100,
    ) -> AsyncIterator[Change]:
        """
        Async generator that pages through Drive changes starting at *page_token*.

        Yields one :class:`Change` per changed file.  Each yielded ``Change``
        has ``next_page_token`` set to the token that should be persisted after
        the item is processed (i.e. the token returned with that page).
        """
        service = await self._get_service()
        loop = asyncio.get_event_loop()
        current_token: str = page_token

        while True:
            token_snapshot = current_token  # capture for closure

            def _fetch(tok: str = token_snapshot) -> dict:
                return (
                    service.changes()
                    .list(
                        pageToken=tok,
                        pageSize=page_size,
                        fields=(
                            "nextPageToken,newStartPageToken,"
                            "changes(type,fileId,removed,file("
                            "id,name,mimeType,parents,size,"
                            "modifiedTime,version,trashed))"
                        ),
                    )
                    .execute()
                )

            page: dict = await loop.run_in_executor(None, _fetch)

            next_page_token: str | None = page.get("nextPageToken")
            new_start_token: str | None = page.get("newStartPageToken")
            effective_next = next_page_token or new_start_token

            for change_data in page.get("changes", []):
                change = _parse_change(change_data)
                change.next_page_token = effective_next
                yield change

            if next_page_token:
                current_token = next_page_token
            else:
                # No more pages.
                break

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    async def download_file(self, file_id: str) -> bytes:
        """Download file content as bytes (runs blocking Drive call in executor)."""
        import io

        from googleapiclient.http import MediaIoBaseDownload  # type: ignore[import]

        service = await self._get_service()
        loop = asyncio.get_event_loop()

        def _download() -> bytes:
            request = service.files().get_media(fileId=file_id)
            buf = io.BytesIO()
            downloader = MediaIoBaseDownload(buf, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return buf.getvalue()

        return await loop.run_in_executor(None, _download)

    async def file_exists(self, file_id: str) -> bool:
        """Check if a file exists on Drive (returns False for 404 or trashed)."""
        from googleapiclient.errors import HttpError  # type: ignore[import]

        loop = asyncio.get_event_loop()
        service = await self._get_service()

        def _check() -> bool:
            try:
                result = service.files().get(
                    fileId=file_id,
                    fields="id,trashed",
                ).execute()
                return not result.get("trashed", False)
            except HttpError as e:
                if e.resp.status == 404:
                    return False
                raise

        return await loop.run_in_executor(None, _check)

    @staticmethod
    def is_under_garuda(file_parents: list[str]) -> bool:
        """
        Return True if *any* parent ID in ``file_parents`` belongs to the
        GARUDA folder tree (checked against the known set of subfolder IDs).

        This is an O(k) local check — no extra API calls required.
        """
        return any(pid in GARUDA_SUBFOLDER_IDS for pid in file_parents)
