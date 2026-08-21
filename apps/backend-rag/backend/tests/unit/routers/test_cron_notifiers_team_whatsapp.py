"""
Unit tests for POST /api/cron/notifiers/team-whatsapp (cron_notifiers router)
and its backing service backend/services/crm/team_whatsapp_sender.py.

Guilt + innocence coverage (cicatrix-superscar.md #3 doctrine — every guard
needs both a colpevolezza and an innocenza test):

1. Guilt  — wrong/missing X-API-Key -> 401, send never attempted.
2. Guilt  — unknown email (no team_members row) -> 404, send never attempted.
3. Guilt  — email resolves but active is False -> 404 (same as unknown —
   TeamMemberNotFound intentionally covers both), send never attempted.
4. Guilt  — email resolves + active, but whatsapp is NULL/empty -> 422, send
   never attempted.
5. Innocence — email resolves + active + has a WhatsApp number -> 200, the
   outbound send fires exactly once with a digit-only phone.
6. Case-insensitive email lookup — the SQL param passed to team_members is
   the lowercased email, regardless of request casing.

Plus narrow unit tests directly against the pure `normalize_phone` helper.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import cron_notifiers
from backend.services.crm import team_whatsapp_sender
from backend.services.crm.team_whatsapp_sender import normalize_phone

VALID_API_KEY = "test-key-123"

ACTIVE_ROW = {
    "email": "budi@balizero.com",
    "active": True,
    "whatsapp": "+6281234567890",
}

# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The router reads a module-level constant baked from os.getenv at
    import time, not a FastAPI dependency — pin it directly."""
    monkeypatch.setattr(cron_notifiers, "_API_KEY", VALID_API_KEY)


@pytest.fixture
def app(mock_db_pool) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(cron_notifiers.router)
    # _get_db_pool reads request.app.state.db_pool directly (no Depends override).
    test_app.state.db_pool = mock_db_pool
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _post(client: TestClient, body: dict, headers: dict | None = None):
    if headers is None:
        headers = {"X-API-Key": VALID_API_KEY}
    return client.post("/api/cron/notifiers/team-whatsapp", json=body, headers=headers)


# ============================================================
# 1. Guilt — wrong / missing API key
# ============================================================


@pytest.mark.parametrize(
    "headers",
    [
        {},  # missing entirely
        {"X-API-Key": "wrong-key"},  # wrong value
    ],
    ids=["missing_header", "wrong_header"],
)
def test_bad_api_key_rejected_before_any_send(client, mock_db_conn, headers):
    with patch.object(
        team_whatsapp_sender.whatsapp_service, "send_message", new=AsyncMock()
    ) as mock_send:
        response = _post(
            client,
            {"team_email": "budi@balizero.com", "text": "hello"},
            headers=headers,
        )

    assert response.status_code == 401
    mock_send.assert_not_awaited()
    # The auth guard fires before any DB lookup is attempted.
    mock_db_conn.fetchrow.assert_not_awaited()


# ============================================================
# 2. Guilt — unknown email
# ============================================================


def test_unknown_email_404(client, mock_db_conn):
    mock_db_conn.fetchrow = AsyncMock(return_value=None)

    with patch.object(
        team_whatsapp_sender.whatsapp_service, "send_message", new=AsyncMock()
    ) as mock_send:
        response = _post(client, {"team_email": "ghost@balizero.com", "text": "hello"})

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
    mock_send.assert_not_awaited()


# ============================================================
# 3. Guilt — resolves but inactive
# ============================================================


def test_inactive_member_404(client, mock_db_conn):
    mock_db_conn.fetchrow = AsyncMock(
        return_value={"email": "budi@balizero.com", "active": False, "whatsapp": "+6281234567890"}
    )

    with patch.object(
        team_whatsapp_sender.whatsapp_service, "send_message", new=AsyncMock()
    ) as mock_send:
        response = _post(client, {"team_email": "budi@balizero.com", "text": "hello"})

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
    mock_send.assert_not_awaited()


# ============================================================
# 4. Guilt — active but no WhatsApp number
# ============================================================


@pytest.mark.parametrize("whatsapp_value", [None, ""], ids=["null", "empty_string"])
def test_active_but_no_whatsapp_422(client, mock_db_conn, whatsapp_value):
    mock_db_conn.fetchrow = AsyncMock(
        return_value={"email": "budi@balizero.com", "active": True, "whatsapp": whatsapp_value}
    )

    with patch.object(
        team_whatsapp_sender.whatsapp_service, "send_message", new=AsyncMock()
    ) as mock_send:
        response = _post(client, {"team_email": "budi@balizero.com", "text": "hello"})

    assert response.status_code == 422
    assert "no WhatsApp number" in response.json()["detail"]
    mock_send.assert_not_awaited()


# ============================================================
# 5. Innocence — happy path
# ============================================================


def test_active_member_with_whatsapp_sends_200(client, mock_db_conn):
    mock_db_conn.fetchrow = AsyncMock(return_value=dict(ACTIVE_ROW))

    with patch.object(
        team_whatsapp_sender.whatsapp_service,
        "send_message",
        new=AsyncMock(return_value={"messages": [{"id": "wamid.test"}]}),
    ) as mock_send:
        response = _post(client, {"team_email": "budi@balizero.com", "text": "hello team"})

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "team_whatsapp"
    assert body["sent"] is True
    mock_send.assert_awaited_once_with(phone="6281234567890", text="hello team")


# ============================================================
# 6. Case-insensitive email lookup
# ============================================================


def test_case_insensitive_email_lookup(client, mock_db_conn):
    mock_db_conn.fetchrow = AsyncMock(return_value=dict(ACTIVE_ROW))

    with patch.object(
        team_whatsapp_sender.whatsapp_service,
        "send_message",
        new=AsyncMock(return_value={"messages": [{"id": "wamid.test"}]}),
    ) as mock_send:
        response = _post(client, {"team_email": "Budi@BaliZero.COM", "text": "hi"})

    assert response.status_code == 200
    mock_send.assert_awaited_once()
    # Assert the $1 SQL param was lowercased, not the raw request casing.
    mock_db_conn.fetchrow.assert_awaited_once()
    args, _ = mock_db_conn.fetchrow.await_args
    assert args[1] == "budi@balizero.com"


# ============================================================
# normalize_phone — pure function, no DB, no FastAPI
# ============================================================


def test_normalize_phone_strips_plus_and_digits_only():
    assert normalize_phone("+6281234567890") == "6281234567890"


def test_normalize_phone_strips_dashes():
    assert normalize_phone("081-234-567") == "081234567"


def test_normalize_phone_strips_spaces_and_parens():
    assert normalize_phone("+62 (821) 345-6789") == "628213456789"
