"""
Unit tests for POST /api/whatsapp/send guard (whatsapp_conversations router).

Coverage:
- Team allowlist (WHATSAPP_TEAM_ALLOWLIST) lets staff numbers bypass the CRM
  check without a clients-table record.
- Unknown numbers still get 403 (anti-spam guard unchanged).
- Phone normalization: '+62 878-6187-0777' == '6287861870777' == '+6287861870777'.
- Empty allowlist == CRM/team-directory validation for everyone.
- Team members (team_members.whatsapp) pass the DB gate even with an empty
  allowlist and no clients-table record (CURE), while a number in neither
  clients nor team_members is still rejected (INNOCENCE).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_current_user, get_optional_database_pool
from backend.app.routers import whatsapp_conversations
from backend.app.routers.whatsapp_conversations import (
    _is_team_number,
    _normalize_phone,
    _outbound_rate,
    router,
)

TEAM_PHONE = "+6287861870777"
UNKNOWN_PHONE = "+6281111111111"

# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """Module-global rate limiter state must not leak across tests."""
    _outbound_rate.clear()
    yield
    _outbound_rate.clear()


@pytest.fixture
def app(mock_db_pool, mock_current_user) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_current_user] = lambda: mock_current_user
    test_app.dependency_overrides[get_optional_database_pool] = lambda: mock_db_pool
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _set_allowlist(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """Set the allowlist on the settings object the router actually reads."""
    monkeypatch.setattr(
        whatsapp_conversations.settings, "whatsapp_team_allowlist", value, raising=False
    )


# ============================================================
# (a) Allowlisted number passes the guard
# ============================================================


def test_allowlisted_number_bypasses_crm_guard(client, mock_db_conn, monkeypatch):
    """A team number sends successfully even when the CRM has no matching client."""
    _set_allowlist(monkeypatch, "6287861870777")
    mock_db_conn.fetchval = AsyncMock(return_value=False)  # NOT in CRM

    with patch.object(
        whatsapp_conversations.whatsapp_service,
        "send_message",
        new=AsyncMock(return_value={"messages": [{"id": "wamid.test"}]}),
    ) as mock_send:
        response = client.post(
            "/api/whatsapp/send", json={"phone": TEAM_PHONE, "message": "ciao team"}
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    mock_send.assert_awaited_once_with(phone="6287861870777", text="ciao team")
    # CRM lookup must be skipped entirely — no CRM pollution, no CRM read needed
    mock_db_conn.fetchval.assert_not_awaited()


# ============================================================
# (b) Unknown number still 403
# ============================================================


def test_unknown_number_still_403(client, mock_db_conn, monkeypatch):
    """A number neither in the allowlist nor in the CRM is still rejected."""
    _set_allowlist(monkeypatch, "6287861870777")
    mock_db_conn.fetchval = AsyncMock(return_value=False)

    with patch.object(
        whatsapp_conversations.whatsapp_service, "send_message", new=AsyncMock()
    ) as mock_send:
        response = client.post(
            "/api/whatsapp/send", json={"phone": UNKNOWN_PHONE, "message": "spam?"}
        )

    assert response.status_code == 403
    assert "not found in CRM" in response.json()["detail"]
    mock_send.assert_not_awaited()


# ============================================================
# (c) Normalization variants match
# ============================================================


@pytest.mark.parametrize(
    "allowlist_entry",
    ["+62 878-6187-0777", "6287861870777", "+6287861870777", " +62 878 6187 0777 "],
)
@pytest.mark.parametrize(
    "request_phone",
    ["+62 878-6187-0777", "6287861870777", "+6287861870777"],
)
def test_normalization_variants_match(
    client, mock_db_conn, monkeypatch, allowlist_entry, request_phone
):
    """Every formatting variant of the same number matches the allowlist."""
    _set_allowlist(monkeypatch, allowlist_entry)
    mock_db_conn.fetchval = AsyncMock(return_value=False)

    with patch.object(
        whatsapp_conversations.whatsapp_service,
        "send_message",
        new=AsyncMock(return_value={"messages": [{"id": "wamid.test"}]}),
    ):
        response = client.post("/api/whatsapp/send", json={"phone": request_phone, "message": "hi"})

    assert response.status_code == 200
    mock_db_conn.fetchval.assert_not_awaited()


def test_normalize_phone_strips_non_digits():
    assert _normalize_phone("+62 878-6187-0777") == "6287861870777"
    assert _normalize_phone("6287861870777") == "6287861870777"
    assert _normalize_phone("") == ""


def test_is_team_number_rejects_partial_match(monkeypatch):
    """Comparison is on FULL normalized strings — no substring/suffix matching."""
    _set_allowlist(monkeypatch, "6287861870777")
    assert _is_team_number("6287861870777") is True
    assert _is_team_number("87861870777") is False  # missing country code
    assert _is_team_number("16287861870777") is False  # extra leading digit
    assert _is_team_number("") is False


# ============================================================
# (d) Empty allowlist = behavior identical to today
# ============================================================


def test_empty_allowlist_known_client_sends(client, mock_db_conn, monkeypatch):
    """Empty allowlist: a CRM-known client still passes via the CRM check."""
    _set_allowlist(monkeypatch, "")
    mock_db_conn.fetchval = AsyncMock(return_value=True)  # IS in CRM

    with patch.object(
        whatsapp_conversations.whatsapp_service,
        "send_message",
        new=AsyncMock(return_value={"messages": [{"id": "wamid.test"}]}),
    ):
        response = client.post(
            "/api/whatsapp/send", json={"phone": UNKNOWN_PHONE, "message": "hello"}
        )

    assert response.status_code == 200
    mock_db_conn.fetchval.assert_awaited_once()


def test_empty_allowlist_team_number_still_403(client, mock_db_conn, monkeypatch):
    """Empty allowlist: even the staff number is rejected (identical to today)."""
    _set_allowlist(monkeypatch, "")
    mock_db_conn.fetchval = AsyncMock(return_value=False)

    with patch.object(
        whatsapp_conversations.whatsapp_service, "send_message", new=AsyncMock()
    ) as mock_send:
        response = client.post("/api/whatsapp/send", json={"phone": TEAM_PHONE, "message": "hello"})

    assert response.status_code == 403
    assert "not found in CRM" in response.json()["detail"]
    mock_send.assert_not_awaited()


# ============================================================
# (e) DB recipient gate: team members pass, unknown numbers don't
# ============================================================
#
# The /send DB gate accepts a recipient that is EITHER a non-deleted client
# (clients.phone) OR an active team member (team_members.whatsapp), in a single
# UNION-ALL EXISTS query. These tests pin both halves of that contract:
#   - CURE: a team-member number absent from clients still sends (no 403).
#   - INNOCENCE: a number in neither table is still rejected (403).
# The DB is mocked, so the boolean returned by fetchval stands in for "the
# UNION query found a matching row". We additionally assert the SQL actually
# consults team_members, so the gate cannot silently regress to clients-only.


def _send_query_sql(mock_db_conn) -> str:
    """Return the SQL string passed to the single fetchval recipient-gate call."""
    mock_db_conn.fetchval.assert_awaited_once()
    args, _ = mock_db_conn.fetchval.await_args
    return args[0]


def test_team_member_in_db_bypasses_clients_only_gate(client, mock_db_conn, monkeypatch):
    """CURE: a team-member number (in team_members.whatsapp, not in clients) sends.

    Allowlist is empty, so the env short-circuit cannot help — the send must
    succeed purely on the DB gate matching team_members. This is Surya's case:
    +6282298000137 lives in team_members.whatsapp but not in clients.
    """
    _set_allowlist(monkeypatch, "")
    # fetchval True == the UNION query found a row (here: the team_members half).
    mock_db_conn.fetchval = AsyncMock(return_value=True)
    surya_phone = "+6282298000137"

    with patch.object(
        whatsapp_conversations.whatsapp_service,
        "send_message",
        new=AsyncMock(return_value={"messages": [{"id": "wamid.test"}]}),
    ) as mock_send:
        response = client.post(
            "/api/whatsapp/send", json={"phone": surya_phone, "message": "ciao Surya"}
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
    mock_send.assert_awaited_once()
    # Prove the gate actually consults team_members (not a blanket allow and not
    # a clients-only check): the SQL must reference both source tables.
    sql = _send_query_sql(mock_db_conn)
    assert "team_members" in sql
    assert "whatsapp" in sql
    assert "clients" in sql


def test_unknown_number_not_in_clients_or_team_still_403(client, mock_db_conn, monkeypatch):
    """INNOCENCE: a number in NEITHER clients NOR team_members is still rejected.

    The team-member fix must not turn the gate into a blanket allow.
    """
    _set_allowlist(monkeypatch, "")
    mock_db_conn.fetchval = AsyncMock(return_value=False)  # in no table

    with patch.object(
        whatsapp_conversations.whatsapp_service, "send_message", new=AsyncMock()
    ) as mock_send:
        response = client.post(
            "/api/whatsapp/send", json={"phone": UNKNOWN_PHONE, "message": "spam?"}
        )

    assert response.status_code == 403
    assert "not found in CRM" in response.json()["detail"]
    mock_send.assert_not_awaited()
    mock_db_conn.fetchval.assert_awaited_once()
