"""Tests for the read-only wa-mirror CRM timeline API."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.routers.wa_mirror_messages import router

EXPECTED_MESSAGE_KEYS = {
    "id",
    "client_id",
    "practice_id",
    "direction",
    "team_member_phone",
    "counterpart_phone",
    "body",
    "body_truncated",
    "message_date",
    "media_type",
    "media_mime",
    "has_media",
    "has_ocr",
    "source",
}


@pytest.fixture
def admin_user() -> dict[str, str]:
    return {
        "id": "user-admin",
        "email": "zero@balizero.com",
        "role": "admin",
    }


@pytest.fixture
def member_user() -> dict[str, str]:
    return {
        "id": "user-member",
        "email": "member@balizero.com",
        "role": "member",
    }


@pytest.fixture
def mock_db_pool() -> MagicMock:
    pool = MagicMock()
    conn = AsyncMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    pool._mock_conn = conn
    return pool


@pytest.fixture
def mock_db_conn(mock_db_pool: MagicMock) -> AsyncMock:
    return mock_db_pool._mock_conn


def make_client(user: dict[str, str], db_pool: MagicMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_database_pool] = lambda: db_pool
    return TestClient(app)


def message_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": 501,
        "client_id": 42,
        "practice_id": 88,
        "direction": "inbound",
        "team_member_phone": "+628213107363",
        "counterpart_phone": "+6281234567890",
        "body": "Client asked for renewal timing",
        "message_text": "legacy duplicate text",
        "message_date": datetime(2026, 5, 17, 10, 30, tzinfo=timezone.utc),
        "media_type": "text",
        "media_mime": None,
        "ocr_result": None,
        "source": "wa_mirror",
    }
    row.update(overrides)
    return row


def test_filters_by_client_and_practice(
    admin_user: dict[str, str],
    mock_db_pool: MagicMock,
    mock_db_conn: AsyncMock,
) -> None:
    """The endpoint must pass both CRM filters into the DB query."""
    mock_db_conn.fetchval.return_value = True
    mock_db_conn.fetch.return_value = [message_row()]
    client = make_client(admin_user, mock_db_pool)

    response = client.get("/api/wa/messages?client_id=42&practice_id=88&limit=25")

    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 25
    assert data["items"][0]["client_id"] == 42
    assert data["items"][0]["practice_id"] == 88
    query, *params = mock_db_conn.fetch.await_args.args
    assert "client_id = $" in query
    assert "practice_id = $" in query
    assert 42 in params
    assert 88 in params


def test_returns_prospect_rows_for_admin(
    admin_user: dict[str, str],
    mock_db_pool: MagicMock,
    mock_db_conn: AsyncMock,
) -> None:
    """Unmatched one-to-one rows are queryable as prospects without inventing a client."""
    mock_db_conn.fetch.return_value = [
        message_row(
            id=777,
            client_id=None,
            practice_id=None,
            counterpart_phone="+6289876543210",
            body="Can Bali Zero help me open a PT PMA?",
        )
    ]
    client = make_client(admin_user, mock_db_pool)

    response = client.get("/api/wa/messages?prospect_only=true")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["id"] == 777
    assert item["client_id"] is None
    assert item["practice_id"] is None
    assert item["counterpart_phone"] == "+6289876543210"


def test_scrubs_synthetic_raw_baileys_envelope(
    admin_user: dict[str, str],
    mock_db_pool: MagicMock,
    mock_db_conn: AsyncMock,
) -> None:
    """Only the response-model allowlist may leave the backend."""
    mock_db_conn.fetchval.return_value = True
    mock_db_conn.fetch.return_value = [
        message_row(
            media_type="image",
            media_mime="image/jpeg",
            ocr_result={"text": "passport number should stay internal"},
            raw_baileys_event={
                "message": {
                    "extendedTextMessage": {
                        "contextInfo": {
                            "quotedMessage": {"conversation": "quoted secret"},
                            "participant": "628111@g.us",
                        }
                    }
                },
                "groupMetadata": {"subject": "Not allowed"},
                "mediaUrl": "https://signed.example/token",
            },
            media_url="https://signed.example/token",
            media_stored_path="/Users/nuzantara/wa-mirror-media/private.jpg",
        )
    ]
    client = make_client(admin_user, mock_db_pool)

    response = client.get("/api/wa/messages?practice_id=88")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert set(item) == EXPECTED_MESSAGE_KEYS
    assert item["has_media"] is True
    assert item["has_ocr"] is True
    serialized = json.dumps(response.json(), sort_keys=True)
    assert "raw_baileys_event" not in serialized
    assert "quotedMessage" not in serialized
    assert "groupMetadata" not in serialized
    assert "media_url" not in serialized
    assert "media_stored_path" not in serialized
    assert "signed.example" not in serialized
    assert "passport number should stay internal" not in serialized


def test_rejects_unfiltered_timeline(
    admin_user: dict[str, str],
    mock_db_pool: MagicMock,
) -> None:
    client = make_client(admin_user, mock_db_pool)

    response = client.get("/api/wa/messages")

    assert response.status_code == 400


def test_rejects_prospect_queue_for_non_admin(
    member_user: dict[str, str],
    mock_db_pool: MagicMock,
) -> None:
    client = make_client(member_user, mock_db_pool)

    response = client.get("/api/wa/messages?prospect_only=true")

    assert response.status_code == 403


def test_wa_mirror_router_registered_in_manifest_and_runtime() -> None:
    from backend.app.setup.router_manifest import ROUTER_MANIFEST
    from backend.app.setup.router_registration import include_light_routers, include_routers

    entries = [entry for entry in ROUTER_MANIFEST if entry.name == "wa_mirror_messages"]
    assert len(entries) == 1
    assert entries[0].process_groups == frozenset({"api"})

    full = FastAPI()
    include_routers(full)
    assert any(route.path == "/api/wa/messages" for route in full.routes)

    light = FastAPI()
    include_light_routers(light)
    assert any(route.path == "/api/wa/messages" for route in light.routes)
