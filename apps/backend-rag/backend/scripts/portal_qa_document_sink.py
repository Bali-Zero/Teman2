"""Ephemeral loopback-only PDF store for the client-portal QA gate.

Documents are validated, kept only in process memory, and exposed only through
an authenticated synthetic contract. The service has no persistence or
external integrations and its receipt reports counts only.
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
import secrets
from collections.abc import Mapping
from dataclasses import dataclass

from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from pydantic import BaseModel

from backend.app.utils.logging_utils import get_logger
from backend.services.portal.upload_validation import (
    MAX_PORTAL_UPLOAD_SIZE,
    PORTAL_UPLOAD_CHUNK_SIZE,
    validate_upload_type,
)

logger = get_logger(__name__)

_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
_FILE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
_INVOICE_FILE_ID_RE = re.compile(r"^synthetic_invoice_pdf_[a-z0-9_-]{10,200}$")
_SYNTHETIC_PDF_RE = re.compile(r"^synthetic-portal-[a-z0-9-]+\.pdf$")
_SYNTHETIC_INVOICE_PDF = base64.b64decode(
    "JVBERi0xLjMKJeLjz9MKMSAwIG9iago8PAovUHJvZHVjZXIgKHB5cGRmKQo+PgplbmRvYmoK"
    "MiAwIG9iago8PAovVHlwZSAvUGFnZXMKL0NvdW50IDEKL0tpZHMgWyA0IDAgUiBdCj4+CmVu"
    "ZG9iagozIDAgb2JqCjw8Ci9UeXBlIC9DYXRhbG9nCi9QYWdlcyAyIDAgUgo+PgplbmRvYmoK"
    "NCAwIG9iago8PAovVHlwZSAvUGFnZQovUmVzb3VyY2VzIDw8Cj4+Ci9NZWRpYUJveCBbIDAu"
    "MCAwLjAgNzIgNzIgXQovUGFyZW50IDIgMCBSCj4+CmVuZG9iagp4cmVmCjAgNQowMDAwMDAw"
    "MDAwIDY1NTM1IGYgCjAwMDAwMDAwMTUgMDAwMDAgbiAKMDAwMDAwMDA1NCAwMDAwMCBuIA"
    "owMDAwMDAwMTEzIDAwMDAwIG4gCjAwMDAwMDAxNjIgMDAwMDAgbiAKdHJhaWxlcgo8PAov"
    "U2l6ZSA1Ci9Sb290IDMgMCBSCi9JbmZvIDEgMCBSCj4+CnN0YXJ0eHJlZgoyNTQKJSVFT0YK"
)


@dataclass(frozen=True)
class QADocumentSinkSettings:
    """Validated secret for the disposable in-memory document sink."""

    key: str
    invoice_file_id: str

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> QADocumentSinkSettings:
        source = os.environ if environment is None else environment
        key = source.get("MY_PORTAL_QA_DOCUMENT_SINK_KEY", "").strip()
        invoice_file_id = source.get("MY_PORTAL_SYNTHETIC_INVOICE_FILE_ID", "").strip()
        if not key:
            raise RuntimeError("Portal QA document sink missing MY_PORTAL_QA_DOCUMENT_SINK_KEY")
        if not _KEY_RE.fullmatch(key):
            raise RuntimeError("Portal QA document sink rejected MY_PORTAL_QA_DOCUMENT_SINK_KEY")
        if not _INVOICE_FILE_ID_RE.fullmatch(invoice_file_id):
            raise RuntimeError(
                "Portal QA document sink rejected MY_PORTAL_SYNTHETIC_INVOICE_FILE_ID"
            )
        return cls(key=key, invoice_file_id=invoice_file_id)


class DocumentReceipt(BaseModel):
    documents: int
    uploads: int
    downloads: int
    rejected_uploads: int


class _ArmedUploadFailure(RuntimeError):
    """One-shot synthetic storage failure used only by the QA sink."""


class _DocumentStore:
    def __init__(self, *, invoice_file_id: str) -> None:
        self._lock = asyncio.Lock()
        self._documents: dict[str, bytes] = {
            invoice_file_id: _SYNTHETIC_INVOICE_PDF,
        }
        self._uploads = 0
        self._downloads = 0
        self._rejected_uploads = 0
        self._fail_next_upload = False

    async def arm_next_upload_failure(self) -> bool:
        async with self._lock:
            if self._fail_next_upload:
                return False
            self._fail_next_upload = True
            return True

    async def put(self, content: bytes) -> str:
        file_id = secrets.token_urlsafe(32)
        async with self._lock:
            if self._fail_next_upload:
                self._fail_next_upload = False
                self._rejected_uploads += 1
                raise _ArmedUploadFailure
            self._documents[file_id] = content
            self._uploads += 1
        return file_id

    async def get(self, file_id: str) -> bytes | None:
        async with self._lock:
            content = self._documents.get(file_id)
            if content is not None:
                self._downloads += 1
            return content

    async def receipt(self) -> DocumentReceipt:
        async with self._lock:
            return DocumentReceipt(
                documents=len(self._documents),
                uploads=self._uploads,
                downloads=self._downloads,
                rejected_uploads=self._rejected_uploads,
            )


def _require_key(provided: str | None, expected: str) -> None:
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


async def _read_pdf_bounded(request: Request) -> bytes:
    content = bytearray()
    async for chunk in request.stream():
        if not chunk:
            continue
        content.extend(chunk)
        if len(content) > MAX_PORTAL_UPLOAD_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Synthetic document exceeds the QA limit",
            )
        if len(chunk) > PORTAL_UPLOAD_CHUNK_SIZE:
            await asyncio.sleep(0)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Synthetic document is empty",
        )
    return bytes(content)


def create_app(settings: QADocumentSinkSettings | None = None) -> FastAPI:
    """Build the fail-closed in-memory sink for uvicorn ``--factory``."""

    config = settings or QADocumentSinkSettings.from_environment()
    store = _DocumentStore(invoice_file_id=config.invoice_file_id)
    app = FastAPI(title="Portal QA document sink", docs_url=None, redoc_url=None)

    @app.get("/health", status_code=status.HTTP_204_NO_CONTENT)
    async def health() -> None:
        return None

    @app.post("/qa/documents", status_code=status.HTTP_201_CREATED)
    async def upload_document(
        request: Request,
        x_qa_sink_key: str | None = Header(default=None, alias="X-QA-Sink-Key"),
        x_qa_document_name: str | None = Header(
            default=None,
            alias="X-QA-Document-Name",
        ),
    ) -> dict[str, str]:
        _require_key(x_qa_sink_key, config.key)
        if not x_qa_document_name or not _SYNTHETIC_PDF_RE.fullmatch(x_qa_document_name):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Synthetic document contract rejected",
            )
        declared_mime = request.headers.get("content-type", "").split(";", 1)[0]
        content = await _read_pdf_bounded(request)
        try:
            validate_upload_type(
                file_ext=".pdf",
                declared_mime_type=declared_mime,
                content=content,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Synthetic document content rejected",
            ) from error
        try:
            file_id = await store.put(content)
        except _ArmedUploadFailure as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Synthetic document storage failure",
            ) from error
        return {"file_id": file_id}

    @app.post("/qa/fail-next-upload", status_code=status.HTTP_204_NO_CONTENT)
    async def fail_next_upload(
        x_qa_sink_key: str | None = Header(default=None, alias="X-QA-Sink-Key"),
    ) -> None:
        _require_key(x_qa_sink_key, config.key)
        if not await store.arm_next_upload_failure():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Synthetic upload failure is already armed",
            )

    @app.get("/qa/documents/{file_id}")
    async def download_document(
        file_id: str,
        x_qa_sink_key: str | None = Header(default=None, alias="X-QA-Sink-Key"),
    ) -> Response:
        _require_key(x_qa_sink_key, config.key)
        if not _FILE_ID_RE.fullmatch(file_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        content = await store.get(file_id)
        if content is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Cache-Control": "private, no-store"},
        )

    @app.get("/qa/receipt", response_model=DocumentReceipt)
    async def receipt(
        x_qa_sink_key: str | None = Header(default=None, alias="X-QA-Sink-Key"),
    ) -> DocumentReceipt:
        _require_key(x_qa_sink_key, config.key)
        return await store.receipt()

    logger.info("Portal QA document sink initialized with an ephemeral store")
    return app
