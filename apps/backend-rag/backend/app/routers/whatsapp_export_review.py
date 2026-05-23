"""Safe staging review API for WhatsApp export imports.

The router intentionally exposes only a small allowlisted projection of staging
rows. It never returns raw WhatsApp envelopes, local file paths, signed media
URLs, OCR/PDF text, JIDs/LIDs, or full message bodies.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from datetime import datetime
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from backend.app.dependencies import get_current_user, get_database_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whatsapp-export", tags=["whatsapp-export"])

DEFAULT_LIMIT = 50
MAX_LIMIT = 100
MAX_EXCERPT_CHARS = 240

STAGING_TABLES: dict[str, str] = {
    "batches": "whatsapp_export_batches",
    "contacts": "whatsapp_export_contacts_staging",
    "documents": "whatsapp_export_documents_staging",
    "messages": "whatsapp_export_messages_staging",
}
REVIEW_ACTIONS_TABLE = "whatsapp_export_review_actions"
REVIEW_STATUSES = {"pending", "approved", "rejected", "ignored"}
BATCH_STATUSES = {"parsed", "reviewing", "completed", "failed", "archived"}

LOCAL_PATH_RE = re.compile(
    r"(?i)(?:/Users/|/private/|/var/folders/|/tmp/|/Volumes/|"
    r"[A-Z]:\\|\\\\[A-Za-z0-9_.-]+\\)"
)
DRIVE_URL_RE = re.compile(r"(?i)(?:https?://)?(?:drive|docs)\.google\.com/\S+")
URL_RE = re.compile(r"(?i)https?://\S+")
PASSPORT_RE = re.compile(
    r"(?i)\b(?:passport|paspor)\b[\s:#-]*[A-Z0-9]{5,12}\b|"
    r"\b[A-Z][0-9]{7,8}\b"
)
BANK_RE = re.compile(
    r"(?i)\b(?:rekening|bank|account|acct|swift|iban|bca|mandiri|bni|bri)\b"
    r"[\s:#-]*[0-9A-Z .-]{4,30}"
)
SECRET_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|bearer)\b"
    r"[\s:=#-]*[A-Za-z0-9._~+/=-]{6,}"
)
LONG_ID_RE = re.compile(r"\b[A-Za-z0-9_-]{24,}\b")
PHONE_DIGITS_RE = re.compile(r"\d")

SAFE_METADATA_KEYS = {
    "batch_label",
    "confidence",
    "detected_language",
    "document_type",
    "imported_at",
    "match_confidence",
    "parser",
    "review_note",
    "source",
    "status",
}
SENSITIVE_KEYS = {
    "raw_baileys_event",
    "jid",
    "lid",
    "media_url",
    "media_stored_path",
    "ocr_result",
    "raw_pdf_text",
    "body",
    "message_text",
    "passport_number",
    "bank_account",
    "account_number",
    "source_relpath",
    "source_file",
}

RESOURCE_COLUMNS: dict[str, set[str]] = {
    "batches": {
        "id",
        "source_root",
        "source_label",
        "source_hash",
        "chat_title",
        "canonical_chat_path",
        "status",
        "created_at",
        "created_by",
        "metadata",
    },
    "contacts": {
        "id",
        "batch_id",
        "display_name",
        "phone_raw",
        "phone_canonical",
        "waid",
        "source_relpath",
        "source_file",
        "review_status",
        "match_confidence",
        "match_reasons",
        "matched_client_id",
        "matched_whatsapp_contact_id",
        "approved_client_id",
        "duplicate_group_key",
        "is_team_candidate",
        "rejected_reason",
        "metadata",
        "created_at",
        "updated_at",
    },
    "documents": {
        "id",
        "batch_id",
        "file_name",
        "file_ext",
        "file_size_bytes",
        "sha256",
        "document_category",
        "inferred_service_type",
        "inferred_person_name",
        "inferred_company_name",
        "inferred_sponsor_company",
        "inferred_document_date",
        "match_confidence",
        "match_reasons",
        "matched_client_id",
        "matched_practice_id",
        "contains_sensitive_data",
        "source_relpath",
        "review_status",
        "metadata",
        "created_at",
    },
    "messages": {
        "id",
        "batch_id",
        "source_relpath",
        "message_index",
        "message_date",
        "sender_display_name",
        "body",
        "body_excerpt",
        "has_attachments",
        "attachment_relpaths",
        "review_status",
        "created_at",
        "metadata",
    },
}


class SafeModel(BaseModel):
    """Base response/request model with a strict public contract."""

    model_config = ConfigDict(extra="forbid")


class ReviewActionResponse(SafeModel):
    id: int
    status: str
    action: str


class ApproveContactMatchRequest(SafeModel):
    approved_client_id: int = Field(gt=0)
    note: str | None = Field(default=None, max_length=500)


class ApproveDocumentLinkRequest(SafeModel):
    approved_client_id: int | None = Field(default=None, gt=0)
    approved_practice_id: int | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=500)


class RejectRequest(SafeModel):
    reason: str | None = Field(default=None, max_length=500)


class BatchReviewItem(SafeModel):
    id: int
    label: str | None
    source_label: str | None = None
    source_basename: str | None
    review_status: str | None
    total_contacts: int | None
    total_documents: int | None
    total_messages: int | None
    counts: dict[str, int] | None = None
    confidence: float | None = None
    reasons: list[str] = Field(default_factory=list)
    imported_at: datetime | None
    created_at: datetime | None
    metadata: dict[str, Any]


class BatchReviewResponse(SafeModel):
    items: list[BatchReviewItem]
    limit: int
    offset: int


class ContactReviewItem(SafeModel):
    id: int
    batch_id: int | None
    source_label: str | None = None
    display_name: str | None
    masked_phone: str | None
    source_basename: str | None
    review_status: str | None
    match_status: str | None
    match_confidence: float | None
    confidence: float | None = None
    reasons: list[str] = Field(default_factory=list)
    suggested_client_id: int | None
    suggested_client: str | None = None
    approved_client_id: int | None
    created_at: datetime | None
    metadata: dict[str, Any]


class ContactReviewResponse(SafeModel):
    items: list[ContactReviewItem]
    limit: int
    offset: int


class DocumentReviewItem(SafeModel):
    id: int
    batch_id: int | None
    contact_id: int | None
    source_label: str | None = None
    title: str | None
    document_type: str | None
    source_basename: str | None
    review_status: str | None
    link_status: str | None
    suggested_document_id: str | None
    approved_document_id: str | None
    suggested_client_id: int | None = None
    suggested_practice_id: int | None = None
    suggested_client: str | None = None
    suggested_practice: str | None = None
    confidence: float | None = None
    reasons: list[str] = Field(default_factory=list)
    created_at: datetime | None
    metadata: dict[str, Any]


class DocumentReviewResponse(SafeModel):
    items: list[DocumentReviewItem]
    limit: int
    offset: int


class MessageReviewItem(SafeModel):
    id: int
    batch_id: int | None
    contact_id: int | None
    direction: str | None
    source_label: str | None = None
    display_name: str | None = None
    masked_phone: str | None
    body_excerpt: str
    source_basename: str | None
    review_status: str | None
    message_at: datetime | None
    created_at: datetime | None
    metadata: dict[str, Any]


class MessageReviewResponse(SafeModel):
    items: list[MessageReviewItem]
    limit: int
    offset: int


class YopoCaseRecap(SafeModel):
    contacts: list[ContactReviewItem]
    documents: list[DocumentReviewItem]
    messages: list[MessageReviewItem]
    recap: dict[str, Any]


def _row_get(row: Mapping[str, Any], key: str, default: Any = None) -> Any:
    if hasattr(row, "get"):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return default


def _safe_basename(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if DRIVE_URL_RE.search(text) or URL_RE.search(text):
        return None
    normalized = text.replace("\\", "/")
    basename = PurePosixPath(normalized).name or PureWindowsPath(text).name
    if not basename or LOCAL_PATH_RE.search(basename):
        return None
    return basename[:160]


def _source_basename(row: Mapping[str, Any]) -> str | None:
    for key in ("source_relpath", "source_file", "canonical_chat_path", "source_root"):
        basename = _safe_basename(_row_get(row, key))
        if basename:
            return basename
    return None


def _mask_phone(value: Any) -> str | None:
    digits = "".join(PHONE_DIGITS_RE.findall(str(value or "")))
    if not digits:
        return None
    if len(digits) <= 4:
        return "*" * len(digits)
    country = digits[:2] if digits.startswith("62") else digits[:1]
    return f"+{country}{'*' * max(len(digits) - len(country) - 3, 3)}{digits[-3:]}"


def _sanitize_text(value: Any, max_chars: int = MAX_EXCERPT_CHARS) -> str:
    text = str(value or "")
    text = DRIVE_URL_RE.sub("[redacted-url]", text)
    text = URL_RE.sub("[redacted-url]", text)
    text = LOCAL_PATH_RE.sub("[redacted-path]", text)
    text = SECRET_RE.sub("[redacted-secret]", text)
    text = PASSPORT_RE.sub("[redacted-passport]", text)
    text = BANK_RE.sub("[redacted-bank]", text)
    text = LONG_ID_RE.sub("[redacted-id]", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _reject_local_path_patterns(value: Any) -> str | None:
    text = _sanitize_text(value, max_chars=500)
    if not text or LOCAL_PATH_RE.search(text) or DRIVE_URL_RE.search(text):
        return None
    return text


def _safe_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    if not isinstance(value, Mapping):
        return {}
    safe: dict[str, Any] = {}
    for key, raw_value in value.items():
        key_text = str(key)
        if key_text in SENSITIVE_KEYS or key_text not in SAFE_METADATA_KEYS:
            continue
        if isinstance(raw_value, (str, int, float, bool)) or raw_value is None:
            safe[key_text] = (
                _reject_local_path_patterns(raw_value) if isinstance(raw_value, str) else raw_value
            )
    return {key: value for key, value in safe.items() if value is not None}


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_str(value: Any) -> str | None:
    text = _reject_local_path_patterns(value)
    return text if text else None


def _first_value(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = _row_get(row, key)
        if value is not None:
            return value
    return None


def _safe_reasons(value: Any) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = [value]
    if not isinstance(value, list):
        return []
    reasons: list[str] = []
    for item in value:
        text = _coerce_str(item)
        if text:
            reasons.append(text)
    return reasons[:6]


async def _table_exists(conn: asyncpg.Connection, table_name: str) -> bool:
    exists = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1
              FROM information_schema.tables
             WHERE table_schema = 'public'
               AND table_name = $1
        )
        """,
        table_name,
    )
    return bool(exists)


async def _available_columns(conn: asyncpg.Connection, table_name: str) -> set[str]:
    rows = await conn.fetch(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = $1
        """,
        table_name,
    )
    return {str(_row_get(row, "column_name")) for row in rows}


async def _fetch_resource_rows(
    conn: asyncpg.Connection,
    resource: Literal["batches", "contacts", "documents", "messages"],
    *,
    limit: int,
    offset: int,
    batch_id: int | None = None,
    status: str | None = None,
    yopo_only: bool = False,
) -> list[Mapping[str, Any]]:
    table_name = STAGING_TABLES[resource]
    if not await _table_exists(conn, table_name):
        return []

    available = await _available_columns(conn, table_name)
    selected = sorted(RESOURCE_COLUMNS[resource] & available)
    if not selected:
        return []

    where_clauses: list[str] = []
    params: list[Any] = []
    status_filter = _coerce_str(status)
    if resource == "batches" and status_filter in BATCH_STATUSES and "status" in available:
        params.append(status_filter)
        where_clauses.append(f"status = ${len(params)}")
    elif (
        resource != "batches" and status_filter in REVIEW_STATUSES and "review_status" in available
    ):
        params.append(status_filter)
        where_clauses.append(f"review_status = ${len(params)}")

    if resource != "batches" and batch_id is not None and "batch_id" in available:
        params.append(batch_id)
        where_clauses.append(f"batch_id = ${len(params)}")

    if yopo_only:
        text_columns = [
            column
            for column in (
                "display_name",
                "file_name",
                "sender_display_name",
                "body",
                "body_excerpt",
                "source_file",
                "source_relpath",
                "source_label",
                "chat_title",
                "canonical_chat_path",
            )
            if column in available
        ]
        if text_columns:
            params.append("%yopo%")
            where_clauses.append(
                "("
                + " OR ".join(
                    f"LOWER({column}::text) LIKE ${len(params)}" for column in text_columns
                )
                + ")"
            )

    order_column = next(
        (
            column
            for column in (
                "message_date",
                "created_at",
                "imported_at",
                "message_at",
                "id",
            )
            if column in available
        ),
        selected[0],
    )
    params.extend([limit, offset])
    limit_placeholder = f"${len(params) - 1}"
    offset_placeholder = f"${len(params)}"
    selected_expressions = list(selected)
    if resource == "batches":
        if await _table_exists(conn, STAGING_TABLES["contacts"]):
            selected_expressions.extend(
                [
                    "(SELECT COUNT(*)::int FROM whatsapp_export_contacts_staging c WHERE c.batch_id = whatsapp_export_batches.id) AS total_contacts",
                    "(SELECT COUNT(*)::int FROM whatsapp_export_contacts_staging c WHERE c.batch_id = whatsapp_export_batches.id AND c.review_status = 'pending') AS contact_pending",
                    "(SELECT COUNT(*)::int FROM whatsapp_export_contacts_staging c WHERE c.batch_id = whatsapp_export_batches.id AND c.review_status = 'approved') AS contact_approved",
                    "(SELECT COUNT(*)::int FROM whatsapp_export_contacts_staging c WHERE c.batch_id = whatsapp_export_batches.id AND c.review_status = 'rejected') AS contact_rejected",
                ]
            )
        if await _table_exists(conn, STAGING_TABLES["documents"]):
            selected_expressions.extend(
                [
                    "(SELECT COUNT(*)::int FROM whatsapp_export_documents_staging d WHERE d.batch_id = whatsapp_export_batches.id) AS total_documents",
                    "(SELECT COUNT(*)::int FROM whatsapp_export_documents_staging d WHERE d.batch_id = whatsapp_export_batches.id AND d.review_status = 'pending') AS document_pending",
                    "(SELECT COUNT(*)::int FROM whatsapp_export_documents_staging d WHERE d.batch_id = whatsapp_export_batches.id AND d.review_status = 'approved') AS document_approved",
                    "(SELECT COUNT(*)::int FROM whatsapp_export_documents_staging d WHERE d.batch_id = whatsapp_export_batches.id AND d.review_status = 'rejected') AS document_rejected",
                ]
            )
        if await _table_exists(conn, STAGING_TABLES["messages"]):
            selected_expressions.extend(
                [
                    "(SELECT COUNT(*)::int FROM whatsapp_export_messages_staging m WHERE m.batch_id = whatsapp_export_batches.id) AS total_messages",
                    "(SELECT COUNT(*)::int FROM whatsapp_export_messages_staging m WHERE m.batch_id = whatsapp_export_batches.id AND m.review_status = 'pending') AS message_pending",
                    "(SELECT COUNT(*)::int FROM whatsapp_export_messages_staging m WHERE m.batch_id = whatsapp_export_batches.id AND m.review_status = 'approved') AS message_approved",
                    "(SELECT COUNT(*)::int FROM whatsapp_export_messages_staging m WHERE m.batch_id = whatsapp_export_batches.id AND m.review_status = 'rejected') AS message_rejected",
                ]
            )
    columns_sql = ", ".join(selected_expressions)
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    rows = await conn.fetch(
        f"""
        SELECT {columns_sql}
          FROM {table_name}
          {where_sql}
         ORDER BY {order_column} DESC
         LIMIT {limit_placeholder} OFFSET {offset_placeholder}
        """,
        *params,
    )
    return list(rows)


def _batch_from_row(row: Mapping[str, Any]) -> BatchReviewItem:
    source_label = _coerce_str(_first_value(row, "source_label", "label", "chat_title"))
    contact_pending = _coerce_int(_row_get(row, "contact_pending")) or 0
    document_pending = _coerce_int(_row_get(row, "document_pending")) or 0
    message_pending = _coerce_int(_row_get(row, "message_pending")) or 0
    contact_approved = _coerce_int(_row_get(row, "contact_approved")) or 0
    document_approved = _coerce_int(_row_get(row, "document_approved")) or 0
    message_approved = _coerce_int(_row_get(row, "message_approved")) or 0
    contact_rejected = _coerce_int(_row_get(row, "contact_rejected")) or 0
    document_rejected = _coerce_int(_row_get(row, "document_rejected")) or 0
    message_rejected = _coerce_int(_row_get(row, "message_rejected")) or 0
    counts = {
        "contacts": _coerce_int(_row_get(row, "total_contacts")) or 0,
        "documents": _coerce_int(_row_get(row, "total_documents")) or 0,
        "messages": _coerce_int(_row_get(row, "total_messages")) or 0,
        "pending": contact_pending + document_pending + message_pending,
        "approved": contact_approved + document_approved + message_approved,
        "rejected": contact_rejected + document_rejected + message_rejected,
    }
    return BatchReviewItem(
        id=int(_row_get(row, "id")),
        label=source_label,
        source_label=source_label,
        source_basename=_source_basename(row),
        review_status=_coerce_str(_first_value(row, "review_status", "status")),
        total_contacts=counts["contacts"],
        total_documents=counts["documents"],
        total_messages=counts["messages"],
        counts=counts,
        imported_at=_row_get(row, "imported_at"),
        created_at=_row_get(row, "created_at"),
        metadata=_safe_metadata(_row_get(row, "metadata")),
    )


def _contact_from_row(row: Mapping[str, Any]) -> ContactReviewItem:
    confidence = _coerce_float(_row_get(row, "match_confidence"))
    suggested_client_id = _coerce_int(_first_value(row, "suggested_client_id", "matched_client_id"))
    approved_client_id = _coerce_int(_row_get(row, "approved_client_id"))
    return ContactReviewItem(
        id=int(_row_get(row, "id")),
        batch_id=_coerce_int(_row_get(row, "batch_id")),
        source_label=None,
        display_name=_coerce_str(_row_get(row, "display_name")),
        masked_phone=_mask_phone(
            _first_value(row, "phone", "phone_canonical", "phone_raw", "waid")
        ),
        source_basename=_source_basename(row),
        review_status=_coerce_str(_row_get(row, "review_status")),
        match_status=_coerce_str(_row_get(row, "match_status"))
        or ("matched" if suggested_client_id or approved_client_id else None),
        match_confidence=confidence,
        confidence=confidence,
        reasons=_safe_reasons(_row_get(row, "match_reasons")),
        suggested_client_id=suggested_client_id,
        suggested_client=str(suggested_client_id) if suggested_client_id is not None else None,
        approved_client_id=approved_client_id,
        created_at=_row_get(row, "created_at"),
        metadata=_safe_metadata(_row_get(row, "metadata")),
    )


def _document_from_row(row: Mapping[str, Any]) -> DocumentReviewItem:
    confidence = _coerce_float(_row_get(row, "match_confidence"))
    matched_client_id = _coerce_int(_row_get(row, "matched_client_id"))
    matched_practice_id = _coerce_int(_row_get(row, "matched_practice_id"))
    return DocumentReviewItem(
        id=int(_row_get(row, "id")),
        batch_id=_coerce_int(_row_get(row, "batch_id")),
        contact_id=_coerce_int(_row_get(row, "contact_id")),
        source_label=None,
        title=_coerce_str(_first_value(row, "title", "file_name")),
        document_type=_coerce_str(_first_value(row, "document_type", "document_category")),
        source_basename=_source_basename(row),
        review_status=_coerce_str(_row_get(row, "review_status")),
        link_status=_coerce_str(_row_get(row, "link_status"))
        or ("matched" if matched_client_id or matched_practice_id else None),
        suggested_document_id=_coerce_str(_row_get(row, "suggested_document_id")),
        approved_document_id=_coerce_str(_row_get(row, "approved_document_id")),
        suggested_client_id=matched_client_id,
        suggested_practice_id=matched_practice_id,
        suggested_client=str(matched_client_id) if matched_client_id is not None else None,
        suggested_practice=str(matched_practice_id) if matched_practice_id is not None else None,
        confidence=confidence,
        reasons=_safe_reasons(_row_get(row, "match_reasons")),
        created_at=_row_get(row, "created_at"),
        metadata=_safe_metadata(_row_get(row, "metadata")),
    )


def _message_from_row(row: Mapping[str, Any]) -> MessageReviewItem:
    body = (
        _row_get(row, "body_excerpt")
        or _row_get(row, "body")
        or _row_get(row, "message_text")
        or ""
    )
    return MessageReviewItem(
        id=int(_row_get(row, "id")),
        batch_id=_coerce_int(_row_get(row, "batch_id")),
        contact_id=_coerce_int(_row_get(row, "contact_id")),
        direction=_coerce_str(_row_get(row, "direction")),
        source_label=None,
        display_name=_coerce_str(_row_get(row, "sender_display_name")),
        masked_phone=_mask_phone(_row_get(row, "phone")),
        body_excerpt=_sanitize_text(body),
        source_basename=_source_basename(row),
        review_status=_coerce_str(_row_get(row, "review_status")),
        message_at=_first_value(row, "message_at", "message_date"),
        created_at=_row_get(row, "created_at"),
        metadata=_safe_metadata(_row_get(row, "metadata")),
    )


def _actor_email(current_user: Mapping[str, Any]) -> str | None:
    email = current_user.get("email") if hasattr(current_user, "get") else None
    return str(email) if email else None


async def _insert_review_action_if_table_exists(
    conn: asyncpg.Connection,
    *,
    entity_type: str,
    entity_id: int,
    action: str,
    actor_email: str | None,
    previous_status: str | None,
    new_status: str | None,
    note: str | None,
) -> None:
    if not await _table_exists(conn, REVIEW_ACTIONS_TABLE):
        return
    try:
        await conn.execute(
            """
            INSERT INTO whatsapp_export_review_actions
                (entity_type, entity_id, action, actor_email, previous_status, new_status, payload, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, NOW())
            """,
            entity_type,
            entity_id,
            action,
            actor_email,
            previous_status,
            new_status,
            json.dumps({"note": _sanitize_text(note, max_chars=500)} if note else {}),
        )
    except asyncpg.PostgresError:
        logger.warning("Could not insert WhatsApp export review action", exc_info=True)


async def _update_contact_review(
    conn: asyncpg.Connection,
    *,
    contact_id: int,
    review_status: str,
    approved_client_id: int | None,
    current_user: Mapping[str, Any],
    note: str | None,
) -> None:
    await conn.execute(
        """
        UPDATE whatsapp_export_contacts_staging
           SET review_status = $2,
               approved_client_id = $3,
               rejected_reason = CASE WHEN $2 = 'rejected' THEN $4 ELSE NULL END,
               updated_at = NOW()
         WHERE id = $1
        """,
        contact_id,
        review_status,
        approved_client_id,
        _sanitize_text(note, max_chars=500) if note else None,
    )
    await _insert_review_action_if_table_exists(
        conn,
        entity_type="contact",
        entity_id=contact_id,
        action=review_status,
        actor_email=_actor_email(current_user),
        previous_status=None,
        new_status=review_status,
        note=note,
    )


async def _update_document_review(
    conn: asyncpg.Connection,
    *,
    document_id: int,
    review_status: str,
    approved_client_id: int | None,
    approved_practice_id: int | None,
    current_user: Mapping[str, Any],
    note: str | None,
) -> None:
    await conn.execute(
        """
        UPDATE whatsapp_export_documents_staging
           SET review_status = $2,
               matched_client_id = COALESCE($3, matched_client_id),
               matched_practice_id = COALESCE($4, matched_practice_id)
         WHERE id = $1
        """,
        document_id,
        review_status,
        approved_client_id,
        approved_practice_id,
    )
    await _insert_review_action_if_table_exists(
        conn,
        entity_type="document",
        entity_id=document_id,
        action=review_status,
        actor_email=_actor_email(current_user),
        previous_status=None,
        new_status=review_status,
        note=note,
    )


async def _update_batch_status(
    conn: asyncpg.Connection,
    *,
    batch_id: int,
    status: str,
    current_user: Mapping[str, Any],
    note: str | None,
) -> None:
    await conn.execute(
        """
        UPDATE whatsapp_export_batches
           SET status = $2
         WHERE id = $1
        """,
        batch_id,
        status,
    )
    await _insert_review_action_if_table_exists(
        conn,
        entity_type="batch",
        entity_id=batch_id,
        action=status,
        actor_email=_actor_email(current_user),
        previous_status=None,
        new_status=None,
        note=note,
    )


async def _update_message_review(
    conn: asyncpg.Connection,
    *,
    message_id: int,
    review_status: str,
    current_user: Mapping[str, Any],
    note: str | None,
) -> None:
    await conn.execute(
        """
        UPDATE whatsapp_export_messages_staging
           SET review_status = $2
         WHERE id = $1
        """,
        message_id,
        review_status,
    )
    await _insert_review_action_if_table_exists(
        conn,
        entity_type="message",
        entity_id=message_id,
        action=review_status,
        actor_email=_actor_email(current_user),
        previous_status=None,
        new_status=review_status,
        note=note,
    )


@router.get("/batches", response_model=BatchReviewResponse)
async def list_batches(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None, max_length=32),
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> BatchReviewResponse:
    del current_user
    async with db_pool.acquire() as conn:
        rows = await _fetch_resource_rows(
            conn,
            "batches",
            limit=limit,
            offset=offset,
            status=status,
        )
    return BatchReviewResponse(
        items=[_batch_from_row(row) for row in rows],
        limit=limit,
        offset=offset,
    )


@router.get("/contacts", response_model=ContactReviewResponse)
async def list_contacts(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    batch_id: int | None = Query(None, ge=1),
    status: str | None = Query(None, max_length=32),
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ContactReviewResponse:
    del current_user
    async with db_pool.acquire() as conn:
        rows = await _fetch_resource_rows(
            conn,
            "contacts",
            limit=limit,
            offset=offset,
            batch_id=batch_id,
            status=status,
        )
    return ContactReviewResponse(
        items=[_contact_from_row(row) for row in rows],
        limit=limit,
        offset=offset,
    )


@router.get("/documents", response_model=DocumentReviewResponse)
async def list_documents(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    batch_id: int | None = Query(None, ge=1),
    status: str | None = Query(None, max_length=32),
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> DocumentReviewResponse:
    del current_user
    async with db_pool.acquire() as conn:
        rows = await _fetch_resource_rows(
            conn,
            "documents",
            limit=limit,
            offset=offset,
            batch_id=batch_id,
            status=status,
        )
    return DocumentReviewResponse(
        items=[_document_from_row(row) for row in rows],
        limit=limit,
        offset=offset,
    )


@router.get("/messages", response_model=MessageReviewResponse)
async def list_messages(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    batch_id: int | None = Query(None, ge=1),
    status: str | None = Query(None, max_length=32),
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> MessageReviewResponse:
    del current_user
    async with db_pool.acquire() as conn:
        rows = await _fetch_resource_rows(
            conn,
            "messages",
            limit=limit,
            offset=offset,
            batch_id=batch_id,
            status=status,
        )
    return MessageReviewResponse(
        items=[_message_from_row(row) for row in rows],
        limit=limit,
        offset=offset,
    )


@router.get("/yopo-case", response_model=YopoCaseRecap)
async def get_yopo_case(
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> YopoCaseRecap:
    del current_user
    async with db_pool.acquire() as conn:
        contact_rows = await _fetch_resource_rows(
            conn, "contacts", limit=MAX_LIMIT, offset=0, yopo_only=True
        )
        document_rows = await _fetch_resource_rows(
            conn, "documents", limit=MAX_LIMIT, offset=0, yopo_only=True
        )
        message_rows = await _fetch_resource_rows(
            conn, "messages", limit=MAX_LIMIT, offset=0, yopo_only=True
        )
    contacts = [_contact_from_row(row) for row in contact_rows]
    documents = [_document_from_row(row) for row in document_rows]
    messages = [_message_from_row(row) for row in message_rows]
    return YopoCaseRecap(
        contacts=contacts,
        documents=documents,
        messages=messages,
        recap={
            "contact_count": len(contacts),
            "document_count": len(documents),
            "message_count": len(messages),
            "review_status": "pending" if contacts or documents or messages else "not_found",
        },
    )


@router.post(
    "/contacts/{contact_id}/approve-match",
    response_model=ReviewActionResponse,
)
async def approve_contact_match(
    contact_id: int,
    payload: ApproveContactMatchRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ReviewActionResponse:
    async with db_pool.acquire() as conn:
        if not await _table_exists(conn, STAGING_TABLES["contacts"]):
            raise HTTPException(status_code=404, detail="Contact staging table not found")
        await _update_contact_review(
            conn,
            contact_id=contact_id,
            review_status="approved",
            approved_client_id=payload.approved_client_id,
            current_user=current_user,
            note=payload.note,
        )
    return ReviewActionResponse(id=contact_id, status="approved", action="approve-match")


@router.post("/contacts/{contact_id}/reject", response_model=ReviewActionResponse)
async def reject_contact(
    contact_id: int,
    payload: RejectRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ReviewActionResponse:
    async with db_pool.acquire() as conn:
        if not await _table_exists(conn, STAGING_TABLES["contacts"]):
            raise HTTPException(status_code=404, detail="Contact staging table not found")
        await _update_contact_review(
            conn,
            contact_id=contact_id,
            review_status="rejected",
            approved_client_id=None,
            current_user=current_user,
            note=payload.reason,
        )
    return ReviewActionResponse(id=contact_id, status="rejected", action="reject")


@router.post(
    "/documents/{document_id}/approve-link",
    response_model=ReviewActionResponse,
)
async def approve_document_link(
    document_id: int,
    payload: ApproveDocumentLinkRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ReviewActionResponse:
    async with db_pool.acquire() as conn:
        if not await _table_exists(conn, STAGING_TABLES["documents"]):
            raise HTTPException(status_code=404, detail="Document staging table not found")
        await _update_document_review(
            conn,
            document_id=document_id,
            review_status="approved",
            approved_client_id=payload.approved_client_id,
            approved_practice_id=payload.approved_practice_id,
            current_user=current_user,
            note=payload.note,
        )
    return ReviewActionResponse(id=document_id, status="approved", action="approve-link")


@router.post("/documents/{document_id}/reject", response_model=ReviewActionResponse)
async def reject_document(
    document_id: int,
    payload: RejectRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ReviewActionResponse:
    async with db_pool.acquire() as conn:
        if not await _table_exists(conn, STAGING_TABLES["documents"]):
            raise HTTPException(status_code=404, detail="Document staging table not found")
        await _update_document_review(
            conn,
            document_id=document_id,
            review_status="rejected",
            approved_client_id=None,
            approved_practice_id=None,
            current_user=current_user,
            note=payload.reason,
        )
    return ReviewActionResponse(id=document_id, status="rejected", action="reject")


@router.post("/{resource}/{entity_id}/approve", response_model=ReviewActionResponse)
async def approve_review_item(
    resource: Literal["batches", "contacts", "documents", "messages"],
    entity_id: int,
    payload: RejectRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ReviewActionResponse:
    async with db_pool.acquire() as conn:
        if not await _table_exists(conn, STAGING_TABLES[resource]):
            raise HTTPException(status_code=404, detail="WhatsApp export staging table not found")
        if resource == "batches":
            await _update_batch_status(
                conn,
                batch_id=entity_id,
                status="completed",
                current_user=current_user,
                note=payload.reason,
            )
            return ReviewActionResponse(id=entity_id, status="completed", action="approve")
        if resource == "contacts":
            raise HTTPException(
                status_code=400,
                detail="Use /contacts/{id}/approve-match with approved_client_id",
            )
        if resource == "documents":
            raise HTTPException(
                status_code=400,
                detail="Use /documents/{id}/approve-link for document approvals",
            )
        await _update_message_review(
            conn,
            message_id=entity_id,
            review_status="approved",
            current_user=current_user,
            note=payload.reason,
        )
        return ReviewActionResponse(id=entity_id, status="approved", action="approve")


@router.post("/{resource}/{entity_id}/reject", response_model=ReviewActionResponse)
async def reject_review_item(
    resource: Literal["batches", "contacts", "documents", "messages"],
    entity_id: int,
    payload: RejectRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ReviewActionResponse:
    async with db_pool.acquire() as conn:
        if not await _table_exists(conn, STAGING_TABLES[resource]):
            raise HTTPException(status_code=404, detail="WhatsApp export staging table not found")
        if resource == "batches":
            await _update_batch_status(
                conn,
                batch_id=entity_id,
                status="archived",
                current_user=current_user,
                note=payload.reason,
            )
            return ReviewActionResponse(id=entity_id, status="archived", action="reject")
        if resource == "contacts":
            await _update_contact_review(
                conn,
                contact_id=entity_id,
                review_status="rejected",
                approved_client_id=None,
                current_user=current_user,
                note=payload.reason,
            )
            return ReviewActionResponse(id=entity_id, status="rejected", action="reject")
        if resource == "documents":
            await _update_document_review(
                conn,
                document_id=entity_id,
                review_status="rejected",
                approved_client_id=None,
                approved_practice_id=None,
                current_user=current_user,
                note=payload.reason,
            )
            return ReviewActionResponse(id=entity_id, status="rejected", action="reject")
        await _update_message_review(
            conn,
            message_id=entity_id,
            review_status="rejected",
            current_user=current_user,
            note=payload.reason,
        )
        return ReviewActionResponse(id=entity_id, status="rejected", action="reject")
