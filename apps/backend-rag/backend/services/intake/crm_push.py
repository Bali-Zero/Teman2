"""Pro→Fly CRM delivery for committed intake documents.

When a reviewer APPROVES an intake proposal with the writer armed, the local
(Pro Postgres) commit is the source of truth for the approve outcome. This
module is the best-effort DELIVERY leg that runs AFTER that commit: it pushes
the original blob to the existing Fly base64 upload endpoint
(``POST /api/crm/clients/{client_id}/documents/upload`` —
``crm_enhanced_documents.upload_document_base64``), which resolves/creates the
client's Google Drive folder, uploads the file, INSERTs the canonical
``documents`` row on the Fly Postgres (the CRM kita reads) and dispatches OCR.

PII note: the blob transits Pro→Fly→Google Drive. That is the CRM's sanctioned
storage path — identical to a manual upload from the kita frontend — so this
does not widen the PII surface beyond what every manual document upload
already does (Law 2: the intake REVIEW data itself stays on the Pro; only the
approved document travels, authenticated with the reviewer's own JWT).

Failure policy: :func:`push_committed_document` NEVER raises for delivery
failures — it always returns a :class:`CrmPushResult`. The caller treats the
local commit as final and surfaces the push status in the approve response +
audit trail.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://nuzantara-rag.fly.dev"
DEFAULT_MAX_MB = 9.0  # raw bytes; base64 inflates ~33% against the endpoint's ~10MB class limit
_REQUEST_TIMEOUT_SECONDS = 60.0

# Google Drive webViewLink → file id (best-effort: the Fly endpoint's response
# carries only document_id + file_url, not the bare Drive file id).
_DRIVE_FILE_ID_RE = re.compile(r"/d/([A-Za-z0-9_-]{10,})")


def push_enabled() -> bool:
    """Kill-switch — ``INTAKE_CRM_PUSH_ENABLED`` (default ON)."""
    return os.environ.get("INTAKE_CRM_PUSH_ENABLED", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _push_base_url() -> str:
    return os.environ.get("INTAKE_CRM_PUSH_BASE_URL", "").strip() or DEFAULT_BASE_URL


def _max_push_bytes() -> int:
    """Raw-blob size guard in bytes (env ``INTAKE_CRM_PUSH_MAX_MB``, default 9 MB)."""
    raw = os.environ.get("INTAKE_CRM_PUSH_MAX_MB", "").strip()
    try:
        mb = float(raw) if raw else DEFAULT_MAX_MB
    except ValueError:
        mb = DEFAULT_MAX_MB
    return int(mb * 1024 * 1024)


# --------------------------------------------------------------------------- #
# Persistent HTTP client (Golden Rule 10) — lazy module singleton.
# --------------------------------------------------------------------------- #
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(_REQUEST_TIMEOUT_SECONDS))
    return _client


async def close_client() -> None:
    """Close the module HTTP client (called from the app lifespan shutdown)."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


@dataclass
class CrmPushResult:
    """Outcome of one Pro→Fly document delivery attempt."""

    ok: bool
    status: str  # pushed | too_large | denied_rbac | rejected | server_error |
    #              unreachable | no_token | missing_blob | error
    fly_doc_id: int | None = None
    file_id: str | None = None
    file_url: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_drive_file_id(file_url: str | None) -> str | None:
    if not file_url:
        return None
    m = _DRIVE_FILE_ID_RE.search(file_url)
    return m.group(1) if m else None


async def push_committed_document(
    *,
    bearer_token: str | None,
    client_id: int,
    file_name: str,
    document_type: str,
    blob_path: str,
    practice_id: int | None = None,
    document_category: str | None = None,
    mime_type: str | None = None,
    expiry_date: str | None = None,
    notes: str | None = None,
    family_member_id: int | None = None,
    base_url: str | None = None,
) -> CrmPushResult:
    """Deliver one committed intake blob to the Fly CRM upload endpoint.

    Matches ``DocumentUploadBase64`` (crm_enhanced_documents.py) exactly:
    ``file`` (base64), ``file_name``, ``document_type`` + the optional
    ``mime_type`` / ``notes`` / ``document_category`` / ``expiry_date`` /
    ``family_member_id`` / ``practice_id``. Fields the endpoint does not
    accept (e.g. extracted_fields) are deliberately NOT sent.

    Auth: the reviewer's own ``Authorization: Bearer <jwt>`` — the Fly endpoint
    enforces ``get_current_user`` + ``verify_client_access(write=True)``.

    Retry: ONE retry on transient failures (connect/read errors, 5xx).
    401/403 → ``denied_rbac`` (no retry). Other 4xx → ``rejected``.
    NEVER raises for delivery failures — always returns a CrmPushResult.
    """
    if not bearer_token:
        return CrmPushResult(ok=False, status="no_token", detail="no bearer token on request")

    path = Path(blob_path)
    try:
        raw = await asyncio.to_thread(path.read_bytes)
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError) as exc:
        return CrmPushResult(
            ok=False, status="missing_blob", detail=f"{type(exc).__name__}: {exc}"
        )

    max_bytes = _max_push_bytes()
    if len(raw) > max_bytes:
        return CrmPushResult(
            ok=False,
            status="too_large",
            detail=f"blob {len(raw)} bytes exceeds limit {max_bytes} bytes",
        )

    payload: dict[str, Any] = {
        "file": base64.b64encode(raw).decode("ascii"),
        "file_name": file_name,
        "document_type": document_type,
    }
    optional_fields: dict[str, Any] = {
        "mime_type": mime_type,
        "notes": notes,
        "document_category": document_category,
        "expiry_date": expiry_date,
        "family_member_id": family_member_id,
        "practice_id": practice_id,
    }
    payload.update({key: value for key, value in optional_fields.items() if value is not None})

    url = f"{(base_url or _push_base_url()).rstrip('/')}/api/crm/clients/{client_id}/documents/upload"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    client = _get_client()

    try:
        last_detail: str | None = None
        for attempt in (0, 1):
            try:
                resp = await client.post(url, json=payload, headers=headers)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_detail = f"{type(exc).__name__}: {exc}"
                if attempt == 0:
                    logger.warning(
                        "intake.crm_push.transient client=%s err=%s — retrying once",
                        client_id,
                        last_detail,
                    )
                    continue
                return CrmPushResult(ok=False, status="unreachable", detail=last_detail)

            if resp.status_code in (401, 403):
                return CrmPushResult(
                    ok=False,
                    status="denied_rbac",
                    detail=f"HTTP {resp.status_code}: {resp.text[:200]}",
                )
            if resp.status_code >= 500:
                last_detail = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if attempt == 0:
                    logger.warning(
                        "intake.crm_push.5xx client=%s detail=%s — retrying once",
                        client_id,
                        last_detail,
                    )
                    continue
                return CrmPushResult(ok=False, status="server_error", detail=last_detail)
            if resp.status_code >= 400:
                return CrmPushResult(
                    ok=False,
                    status="rejected",
                    detail=f"HTTP {resp.status_code}: {resp.text[:200]}",
                )

            # 2xx — response shape: {"success", "document_id", "file_url", ...}
            try:
                data = resp.json()
            except ValueError:
                data = {}
            if not isinstance(data, dict):
                data = {}
            fly_doc_id = data.get("document_id")
            file_url = data.get("file_url")
            logger.info(
                "intake.crm_push.pushed client=%s fly_doc=%s file_url=%s",
                client_id,
                fly_doc_id,
                bool(file_url),
            )
            return CrmPushResult(
                ok=True,
                status="pushed",
                fly_doc_id=int(fly_doc_id) if fly_doc_id is not None else None,
                file_id=_parse_drive_file_id(file_url),
                file_url=file_url,
            )
        # Unreachable: the loop always returns. Defensive fallthrough.
        return CrmPushResult(ok=False, status="error", detail=last_detail or "exhausted retries")
    except Exception as exc:  # delivery must never break the approve
        logger.exception("intake.crm_push.unexpected client=%s", client_id)
        return CrmPushResult(ok=False, status="error", detail=f"{type(exc).__name__}: {exc}")
