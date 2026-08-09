"""Fail-closed client for the synthetic portal document sink.

The adapter is disabled unless both QA sink variables are present. When it is
enabled it additionally requires a disposable loopback PostgreSQL database,
an explicit loopback HTTP sink, reserved ``example.com`` identities, and
reserved synthetic PDF names. This keeps the prod-like browser gate on the
real portal service path without touching Drive, OCR, or client data.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

import httpx

from backend.services.portal.upload_validation import MAX_PORTAL_UPLOAD_SIZE

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
_FILE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
_SYNTHETIC_EMAIL_RE = re.compile(r"^[^@\s]+@example\.com$", re.IGNORECASE)
_SYNTHETIC_PDF_RE = re.compile(r"^synthetic-portal-[a-z0-9-]+\.pdf$")


@dataclass(frozen=True)
class QADocumentSinkClient:
    """Minimal async client for an ephemeral, loopback-only document store."""

    base_url: str
    key: str

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> QADocumentSinkClient | None:
        source = os.environ if environment is None else environment
        url_value = source.get("MY_PORTAL_QA_DOCUMENT_SINK_URL", "").strip()
        key = source.get("MY_PORTAL_QA_DOCUMENT_SINK_KEY", "").strip()

        if not url_value and not key:
            return None
        if not url_value or not key:
            raise RuntimeError("Portal QA document sink configuration is incomplete")

        _validate_disposable_database(source.get("DATABASE_URL", ""))
        base_url = _validate_sink_url(url_value)
        if not _KEY_RE.fullmatch(key):
            raise RuntimeError("Portal QA document sink rejected MY_PORTAL_QA_DOCUMENT_SINK_KEY")
        return cls(base_url=base_url, key=key)

    @staticmethod
    def validate_synthetic_upload(
        *,
        email: str,
        file_name: str,
        mime_type: str | None,
    ) -> None:
        if not _SYNTHETIC_EMAIL_RE.fullmatch(email.strip().lower()):
            raise RuntimeError("Portal QA document sink rejected the uploader identity")
        if not _SYNTHETIC_PDF_RE.fullmatch(file_name):
            raise RuntimeError("Portal QA document sink rejected the document name")
        if mime_type != "application/pdf":
            raise RuntimeError("Portal QA document sink rejected the document type")

    async def upload(
        self,
        *,
        content: bytes,
        file_name: str,
    ) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/qa/documents",
                    content=content,
                    headers={
                        "Content-Type": "application/pdf",
                        "X-QA-Sink-Key": self.key,
                        "X-QA-Document-Name": file_name,
                    },
                )
        except httpx.HTTPError as error:
            raise RuntimeError("Portal QA document storage is unavailable") from error

        if response.status_code != 201:
            raise RuntimeError("Portal QA document storage rejected the upload")
        try:
            file_id = response.json()["file_id"]
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("Portal QA document storage returned an invalid response") from error
        if not isinstance(file_id, str) or not _FILE_ID_RE.fullmatch(file_id):
            raise RuntimeError("Portal QA document storage returned an invalid response")
        return {
            "success": True,
            "file_id": file_id,
            "file_url": None,
            "folder_path": "qa-document-sink",
            "error": None,
        }

    async def download(self, file_id: str) -> bytes | None:
        if not _FILE_ID_RE.fullmatch(file_id):
            return None
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/qa/documents/{file_id}",
                    headers={"X-QA-Sink-Key": self.key},
                )
        except httpx.HTTPError as error:
            raise RuntimeError("Portal QA document storage is unavailable") from error

        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise RuntimeError("Portal QA document storage rejected the download")
        if response.headers.get("content-type", "").split(";", 1)[0] != "application/pdf":
            raise RuntimeError("Portal QA document storage returned an invalid document")
        if not response.content or len(response.content) > MAX_PORTAL_UPLOAD_SIZE:
            raise RuntimeError("Portal QA document storage returned an invalid document")
        return response.content


def _validate_disposable_database(value: str) -> None:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise RuntimeError("Portal QA document sink rejected DATABASE_URL") from error
    hostname = (parsed.hostname or "").lower().rstrip(".")
    database_name = unquote(parsed.path.lstrip("/"))
    if (
        parsed.scheme not in {"postgres", "postgresql"}
        or hostname not in _LOOPBACK_HOSTS
        or port is None
        or not database_name.startswith("my_portal_qa")
    ):
        raise RuntimeError("Portal QA document sink rejected DATABASE_URL")


def _validate_sink_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise RuntimeError(
            "Portal QA document sink rejected MY_PORTAL_QA_DOCUMENT_SINK_URL"
        ) from error
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme != "http"
        or hostname not in _LOOPBACK_HOSTS
        or port is None
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("Portal QA document sink rejected MY_PORTAL_QA_DOCUMENT_SINK_URL")
    return f"http://{parsed.netloc}"
