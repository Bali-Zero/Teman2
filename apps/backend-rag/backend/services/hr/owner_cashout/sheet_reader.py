"""Google Sheets reader for WEEKLY CASHOUT using Service Account.

Uses OWNER_CASHOUT_SA_JSON env var (raw JSON) OR OWNER_CASHOUT_SA_FILE (path).
Scope: spreadsheets.readonly — this service is read-only by design.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
ENV_JSON = "OWNER_CASHOUT_SA_JSON"
ENV_FILE = "OWNER_CASHOUT_SA_FILE"


class SheetReader:
    """Thin read-only wrapper around Google Sheets API v4."""

    def __init__(self) -> None:
        self._service: Any | None = None

    def _resolve_credentials_path(self) -> str:
        file_path = os.environ.get(ENV_FILE)
        if file_path and os.path.isfile(file_path):
            return file_path

        raw = os.environ.get(ENV_JSON)
        if not raw:
            raise RuntimeError(
                f"Missing service account credentials. Set {ENV_FILE} or {ENV_JSON}."
            )

        # Validate JSON
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"{ENV_JSON} is not valid JSON: {e}") from e

        if parsed.get("type") != "service_account":
            raise RuntimeError(f"{ENV_JSON} is not a service account key")

        # Write to temp file for google lib
        tf = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="owner_cashout_sa_"
        )
        tf.write(raw)
        tf.close()
        return tf.name

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service

        creds_path = self._resolve_credentials_path()
        creds = service_account.Credentials.from_service_account_file(
            creds_path, scopes=SCOPES
        )
        self._service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        logger.info("[CASHOUT] Sheets service initialized (SA)")
        return self._service

    def list_tabs(self, spreadsheet_id: str) -> list[str]:
        """Return the titles of all tabs in the spreadsheet."""
        svc = self._get_service()
        meta = (
            svc.spreadsheets()
            .get(spreadsheetId=spreadsheet_id, fields="sheets.properties.title")
            .execute()
        )
        return [s["properties"]["title"] for s in meta.get("sheets", [])]

    def read_range(self, spreadsheet_id: str, range_: str) -> list[list[str]]:
        """Read a range and return raw rows.

        Note: Google returns rows of variable length (trailing empties trimmed).
        Callers must pad rows before indexing.
        """
        svc = self._get_service()
        result = (
            svc.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=range_)
            .execute()
        )
        return result.get("values", [])
