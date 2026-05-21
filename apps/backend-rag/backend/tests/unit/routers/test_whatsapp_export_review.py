"""Unit tests for the safe WhatsApp export staging review API."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.routers.whatsapp_export_review import (
    BatchReviewItem,
    _message_from_row,
    _safe_basename,
    _sanitize_text,
    _update_contact_review,
    router,
)

FORBIDDEN_MARKERS = [
    "raw_baileys_event",
    "jid",
    "lid",
    "media_url",
    "media_stored_path",
    "ocr_result",
    "raw_pdf_text",
    "/Users/",
    "drive.google.com",
    "A12345678",
    "rekening",
    "account number",
]


class FakeAcquire:
    def __init__(self, conn: FakeConn) -> None:
        self.conn = conn

    async def __aenter__(self) -> FakeConn:
        return self.conn

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class FakePool:
    def __init__(self, conn: FakeConn) -> None:
        self.conn = conn

    def acquire(self) -> FakeAcquire:
        return FakeAcquire(self.conn)


class FakeConn:
    def __init__(
        self,
        *,
        rows_by_table: dict[str, list[dict[str, Any]]] | None = None,
        existing_tables: set[str] | None = None,
    ) -> None:
        self.rows_by_table = rows_by_table or {}
        self.existing_tables = existing_tables or set(self.rows_by_table)
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchval(self, query: str, *args: Any) -> bool:
        if "information_schema.tables" in query:
            return str(args[0]) in self.existing_tables
        return False

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        if "information_schema.columns" in query:
            table = str(args[0])
            columns = set()
            for row in self.rows_by_table.get(table, []):
                columns.update(row)
            return [{"column_name": column} for column in sorted(columns)]

        for table, rows in self.rows_by_table.items():
            if f"FROM {table}" in query:
                if args and args[0] == "%yopo%":
                    return [row for row in rows if "yopo" in json.dumps(row, default=str).lower()]
                return rows
        return []

    async def execute(self, query: str, *args: Any) -> str:
        self.executed.append((query, args))
        return "UPDATE 1"


@pytest.fixture
def admin_user() -> dict[str, str]:
    return {"id": "user-admin", "email": "zero@balizero.com", "role": "admin"}


def make_client(user: dict[str, str], conn: FakeConn) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_database_pool] = lambda: FakePool(conn)
    return TestClient(app)


def assert_no_forbidden_markers(payload: Any) -> None:
    serialized = json.dumps(payload, sort_keys=True, default=str)
    for marker in FORBIDDEN_MARKERS:
        assert marker not in serialized


def test_sanitizer_helpers_remove_paths_drive_urls_passports_and_bank_markers() -> None:
    assert _safe_basename("/Users/nuzantara/private/passport.pdf") == "passport.pdf"
    assert _safe_basename("https://drive.google.com/file/d/raw/view") is None

    text = _sanitize_text(
        "Passport A12345678 in /Users/nuzantara/Desktop/private.pdf "
        "rekening BCA 1234567890 token=super-secret-token "
        "https://drive.google.com/file/d/raw/view"
    )

    assert "/Users/" not in text
    assert "drive.google.com" not in text
    assert "A12345678" not in text
    assert "rekening BCA 1234567890" not in text
    assert "super-secret-token" not in text


def test_response_models_forbid_extra_fields() -> None:
    with pytest.raises(ValueError):
        BatchReviewItem(
            id=1,
            label="batch",
            source_basename=None,
            review_status=None,
            total_contacts=None,
            total_documents=None,
            total_messages=None,
            imported_at=None,
            created_at=None,
            metadata={},
            raw_baileys_event={"secret": True},
        )


def test_messages_endpoint_returns_excerpt_and_excludes_sensitive_fields(
    admin_user: dict[str, str],
) -> None:
    conn = FakeConn(
        rows_by_table={
            "whatsapp_export_messages_staging": [
                {
                    "id": 1,
                    "batch_id": 10,
                    "contact_id": 20,
                    "direction": "inbound",
                    "phone": "+6281234567890",
                    "body": (
                        "YOPO passport A12345678 rekening Mandiri 1234567890 "
                        "from /Users/nuzantara/raw.pdf"
                    ),
                    "source_relpath": "/Users/nuzantara/Desktop/raw/export/chat.txt",
                    "message_at": datetime(2026, 5, 21, tzinfo=timezone.utc),
                    "review_status": "pending",
                    "metadata": {
                        "confidence": "high",
                        "raw_baileys_event": {"jid": "62812@s.whatsapp.net"},
                        "media_stored_path": "/Users/nuzantara/private.jpg",
                    },
                    "raw_baileys_event": {"jid": "62812@s.whatsapp.net"},
                    "jid": "62812@s.whatsapp.net",
                    "lid": "secret-lid",
                    "media_url": "https://signed.example/media",
                    "media_stored_path": "/Users/nuzantara/private.jpg",
                    "ocr_result": "passport A12345678",
                    "raw_pdf_text": "account number 123",
                }
            ]
        }
    )
    client = make_client(admin_user, conn)

    response = client.get("/api/whatsapp-export/messages")

    assert response.status_code == 200
    payload = response.json()
    item = payload["items"][0]
    assert item["masked_phone"].startswith("+62")
    assert item["masked_phone"].endswith("890")
    assert "body" not in item
    assert "body_excerpt" in item
    assert item["source_basename"] == "chat.txt"
    assert item["metadata"] == {"confidence": "high"}
    assert_no_forbidden_markers(payload)


def test_contacts_and_documents_endpoints_exclude_raw_paths_and_sensitive_fields(
    admin_user: dict[str, str],
) -> None:
    conn = FakeConn(
        rows_by_table={
            "whatsapp_export_contacts_staging": [
                {
                    "id": 2,
                    "batch_id": 10,
                    "display_name": "Yopo Client",
                    "phone": "+6287777771234",
                    "source_file": "C:\\Users\\raw\\contacts.csv",
                    "review_status": "pending",
                    "match_status": "suggested",
                    "match_confidence": 0.91,
                    "suggested_client_id": 42,
                    "metadata": {
                        "match_confidence": 0.91,
                        "jid": "62877@s.whatsapp.net",
                        "account_number": "123456",
                    },
                    "jid": "62877@s.whatsapp.net",
                }
            ],
            "whatsapp_export_documents_staging": [
                {
                    "id": 3,
                    "batch_id": 10,
                    "contact_id": 2,
                    "title": "Yopo Passport A12345678",
                    "document_type": "passport",
                    "source_relpath": "exports/yopo/passport.pdf",
                    "review_status": "pending",
                    "link_status": "suggested",
                    "suggested_document_id": "safe-doc-id",
                    "metadata": {
                        "document_type": "passport",
                        "ocr_result": "passport A12345678",
                        "media_url": "https://drive.google.com/file/d/raw/view",
                    },
                    "raw_pdf_text": "account number 123",
                }
            ],
        }
    )
    client = make_client(admin_user, conn)

    contacts = client.get("/api/whatsapp-export/contacts").json()
    documents = client.get("/api/whatsapp-export/documents").json()

    assert contacts["items"][0]["source_basename"] == "contacts.csv"
    assert documents["items"][0]["source_basename"] == "passport.pdf"
    assert_no_forbidden_markers(contacts)
    assert_no_forbidden_markers(documents)


def test_yopo_case_returns_human_recap_without_raw_passport_bank_or_local_path(
    admin_user: dict[str, str],
) -> None:
    conn = FakeConn(
        rows_by_table={
            "whatsapp_export_contacts_staging": [
                {
                    "id": 11,
                    "display_name": "YOPO contact",
                    "phone": "+6281111119999",
                    "review_status": "pending",
                    "source_file": "/Users/nuzantara/yopo/contacts.csv",
                }
            ],
            "whatsapp_export_documents_staging": [
                {
                    "id": 12,
                    "title": "YOPO passport A12345678",
                    "document_type": "passport",
                    "source_file": "yopo-passport.pdf",
                    "raw_pdf_text": "rekening BCA 1234567890",
                }
            ],
            "whatsapp_export_messages_staging": [
                {
                    "id": 13,
                    "body": "YOPO sent passport A12345678 and bank account number 1234567890",
                    "phone": "+6281111119999",
                    "source_file": "/Users/nuzantara/yopo/chat.txt",
                }
            ],
        }
    )
    client = make_client(admin_user, conn)

    response = client.get("/api/whatsapp-export/yopo-case")

    assert response.status_code == 200
    payload = response.json()
    assert payload["recap"] == {
        "contact_count": 1,
        "document_count": 1,
        "message_count": 1,
        "review_status": "pending",
    }
    assert_no_forbidden_markers(payload)


@pytest.mark.asyncio
async def test_approval_sql_updates_staging_only() -> None:
    conn = MagicMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    conn.fetchval = AsyncMock(return_value=False)

    await _update_contact_review(
        conn,
        contact_id=44,
        review_status="approved",
        approved_client_id=99,
        current_user={"email": "zero@balizero.com"},
        note="approve",
    )

    update_query, *update_args = conn.execute.await_args_list[0].args
    assert "UPDATE whatsapp_export_contacts_staging" in update_query
    assert "whatsapp_contacts" not in update_query
    assert "whatsapp_message_context" not in update_query
    assert update_args[:3] == [44, "approved", 99]


def test_approve_endpoint_updates_staging_and_inserts_review_action(
    admin_user: dict[str, str],
) -> None:
    conn = FakeConn(
        existing_tables={
            "whatsapp_export_contacts_staging",
            "whatsapp_export_review_actions",
        }
    )
    client = make_client(admin_user, conn)

    response = client.post(
        "/api/whatsapp-export/contacts/44/approve-match",
        json={"approved_client_id": 99, "note": "matched"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": 44,
        "status": "approved",
        "action": "approve-match",
    }
    executed_sql = "\n".join(query for query, _args in conn.executed)
    assert "UPDATE whatsapp_export_contacts_staging" in executed_sql
    assert "INSERT INTO whatsapp_export_review_actions" in executed_sql
    assert "whatsapp_message_context" not in executed_sql


def test_empty_or_missing_tables_return_empty_lists(admin_user: dict[str, str]) -> None:
    client = make_client(admin_user, FakeConn())

    response = client.get("/api/whatsapp-export/batches")

    assert response.status_code == 200
    assert response.json() == {"items": [], "limit": 50, "offset": 0}


def test_message_helper_uses_excerpt_not_body() -> None:
    item = _message_from_row(
        {
            "id": 1,
            "body": "hello " + ("x" * 400),
            "phone": "+6281234567890",
            "source_file": "chat.txt",
        }
    )

    payload = item.model_dump()
    assert "body" not in payload
    assert len(payload["body_excerpt"]) <= 240
