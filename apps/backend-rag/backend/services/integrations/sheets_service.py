"""
Google Sheets Service — Read/write operations via Service Account (DWD).

Uses the same credential chain as TeamDriveService:
1. Domain-Wide Delegation → impersonates zero@balizero.com
2. Direct Service Account fallback

The SA must have the target spreadsheet shared with it (Editor role),
or DWD must be configured with the Sheets scope.
"""

import base64
import json
import logging
import os
import tempfile
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

CREDENTIALS_ENV_VAR = "GOOGLE_SERVICE_ACCOUNT_JSON"


class SheetsService:
    """Thin wrapper around Google Sheets API v4."""

    def __init__(self) -> None:
        self._service: Any | None = None
        self._connected_as: str | None = None

    # ------------------------------------------------------------------
    # Credential helpers (same logic as TeamDriveService)
    # ------------------------------------------------------------------

    def _get_credentials_path(self) -> str | None:
        env_creds = os.environ.get(CREDENTIALS_ENV_VAR) or os.environ.get("GOOGLE_SERVICE_ACCOUNT")
        if not env_creds:
            return None

        creds_json: str | None = None

        # Try raw JSON
        try:
            parsed = json.loads(env_creds)
            if parsed.get("type") == "service_account":
                creds_json = env_creds
        except json.JSONDecodeError as e:
            logger.debug(f"SA creds not raw JSON, trying base64: {e}")

        # Try base64
        if not creds_json:
            try:
                decoded = base64.b64decode(env_creds).decode("utf-8")
                parsed = json.loads(decoded)
                if parsed.get("type") == "service_account":
                    creds_json = decoded
            except Exception as e:
                logger.debug(f"SA creds base64 decode failed: {e}")

        if creds_json:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_file:
                temp_file.write(creds_json)
                return temp_file.name

        return None

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service

        creds_path = self._get_credentials_path()
        if not creds_path:
            raise FileNotFoundError(
                "Google credentials not found. Set GOOGLE_SERVICE_ACCOUNT_JSON.",
            )

        # Use Direct SA (DWD doesn't have Sheets scope in Workspace config).
        # The target spreadsheets must be shared with the SA email as Editor.
        credentials = service_account.Credentials.from_service_account_file(
            creds_path, scopes=SCOPES,
        )
        svc = build("sheets", "v4", credentials=credentials)
        self._connected_as = "service-account"
        logger.info("[SHEETS] ✅ Direct SA mode (spreadsheets must be shared with SA)")

        self._service = svc
        return self._service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def read_range(self, spreadsheet_id: str, range_: str) -> list[list[str]]:
        """Read a range from a spreadsheet. Returns list of rows."""
        svc = self._get_service()
        result = (
            svc.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_).execute()
        )
        return result.get("values", [])

    async def write_range(
        self,
        spreadsheet_id: str,
        range_: str,
        values: list[list[str]],
        value_input_option: str = "USER_ENTERED",
    ) -> dict:
        """Write values to a range. Returns API response."""
        svc = self._get_service()
        body = {"values": values}
        result = (
            svc.spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_,
                valueInputOption=value_input_option,
                body=body,
            )
            .execute()
        )
        logger.info(f"[SHEETS] ✅ Updated {result.get('updatedCells', 0)} cells in {range_}")
        return result

    async def append_row(
        self,
        spreadsheet_id: str,
        range_: str,
        values: list[list[str]],
        value_input_option: str = "USER_ENTERED",
    ) -> dict:
        """Append rows after the last row with data."""
        svc = self._get_service()
        body = {"values": values}
        result = (
            svc.spreadsheets()
            .values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=range_,
                valueInputOption=value_input_option,
                body=body,
            )
            .execute()
        )
        logger.info(f"[SHEETS] ✅ Appended {len(values)} row(s) to {range_}")
        return result

    async def find_row_by_value(
        self,
        spreadsheet_id: str,
        range_: str,
        search_column: int,
        search_value: str,
    ) -> int | None:
        """
        Find the row number (1-based) where column matches value.

        Args:
            spreadsheet_id: Sheet ID
            range_: Range to search (e.g. 'Company!A:A')
            search_column: 0-based column index within the range
            search_value: Value to match (case-insensitive)

        Returns:
            1-based row number or None
        """
        rows = await self.read_range(spreadsheet_id, range_)
        for i, row in enumerate(rows):
            if len(row) > search_column:
                if row[search_column].strip().lower() == search_value.strip().lower():
                    return i + 1  # 1-based
        return None
