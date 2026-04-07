"""
Unit tests for hr_late_reply router.

Coverage focus:
- GET form: valid token, wrong token, already replied
- POST submit: state transitions for the three input states
  (AWAITING_REPLY -> RESOLVED, REMINDER_SENT -> RESOLVED_LATE,
  ESCALATED -> ESCALATED preserved)
- POST submit: invalid token rejected
- POST submit: replay protection (already replied)

The router takes the DB pool via FastAPI dependency injection
(``Depends(get_database_pool)``), so we override that dependency on the
test app to inject a fake asyncpg-style pool.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_database_pool
from backend.app.routers import hr_late_reply
from backend.services.analytics.attendance_monitor import (
    STATE_AWAITING_REPLY,
    STATE_ESCALATED,
    STATE_REMINDER_SENT,
    STATE_RESOLVED,
    STATE_RESOLVED_LATE,
)


# ---------------------------------------------------------------------------
# Fake asyncpg connection / pool
# ---------------------------------------------------------------------------


class _FakeConn:
    """
    Stand-in for an asyncpg connection that records the last UPDATE call so
    tests can assert which state was written.
    """

    def __init__(self, fetchrow_returns: dict | None) -> None:
        self.fetchrow_returns = fetchrow_returns
        self.executed: list[tuple] = []

    async def fetchrow(self, *args, **kwargs):
        return self.fetchrow_returns

    async def execute(self, query: str, *args) -> None:
        self.executed.append((query, args))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc) -> None:
        return None


def _make_pool(fetchrow_returns: dict | None) -> MagicMock:
    """
    Build a MagicMock pool whose ``acquire()`` returns a context-manager-aware
    fake connection. Mirrors the pattern used in
    test_unit_team_timesheet_svc.py.
    """
    conn = _FakeConn(fetchrow_returns)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=conn)
    pool._conn = conn  # convenience reference for assertions
    return pool


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> FastAPI:
    """Bare FastAPI app with the hr_late_reply router mounted."""
    application = FastAPI()
    application.include_router(hr_late_reply.router)
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _override_pool(app: FastAPI, pool) -> None:
    """Wire ``pool`` into the app's get_database_pool dependency."""
    app.dependency_overrides[get_database_pool] = lambda: pool


# ---------------------------------------------------------------------------
# GET form
# ---------------------------------------------------------------------------


class TestGetLateReplyForm:
    def test_get_form_with_valid_token(self, app: FastAPI, client: TestClient) -> None:
        incident_id = uuid4()
        token = "valid_token_with_enough_length_xyz"
        pool = _make_pool(
            {
                "id": incident_id,
                "reply_token": token,
                "reply_received_at": None,
                "late_date": date(2026, 4, 7),
                "state": STATE_AWAITING_REPLY,
            },
        )
        _override_pool(app, pool)

        response = client.get(
            f"/api/hr/late-reply/{incident_id}?token={token}",
        )

        assert response.status_code == 200
        assert "Kirim alasan keterlambatan" in response.text
        assert token in response.text  # rendered into the hidden form field

    def test_get_form_with_wrong_token_returns_404(
        self, app: FastAPI, client: TestClient,
    ) -> None:
        incident_id = uuid4()
        pool = _make_pool(
            {
                "id": incident_id,
                "reply_token": "the_real_token_xyzxyzxyzxyzxyz",
                "reply_received_at": None,
                "late_date": date(2026, 4, 7),
                "state": STATE_AWAITING_REPLY,
            },
        )
        _override_pool(app, pool)

        response = client.get(
            f"/api/hr/late-reply/{incident_id}?token=completely_wrong_value_xx",
        )

        assert response.status_code == 404
        assert "Tautan tidak valid" in response.text

    def test_get_form_when_already_replied(
        self, app: FastAPI, client: TestClient,
    ) -> None:
        incident_id = uuid4()
        token = "valid_token_with_enough_length_xyz"
        pool = _make_pool(
            {
                "id": incident_id,
                "reply_token": token,
                "reply_received_at": datetime.now(tz=timezone.utc),
                "late_date": date(2026, 4, 7),
                "state": STATE_RESOLVED,
            },
        )
        _override_pool(app, pool)

        response = client.get(
            f"/api/hr/late-reply/{incident_id}?token={token}",
        )

        assert response.status_code == 200
        assert "Sudah dijawab" in response.text


# ---------------------------------------------------------------------------
# POST submit — the important state-machine cases
# ---------------------------------------------------------------------------


class TestPostLateReply:
    def _post(
        self,
        client: TestClient,
        incident_id,
        token: str,
        reason: str = "Macet parah di Bypass",
    ):
        return client.post(
            f"/api/hr/late-reply/{incident_id}",
            data={"token": token, "reason": reason},
        )

    def test_awaiting_reply_transitions_to_resolved(
        self, app: FastAPI, client: TestClient,
    ) -> None:
        incident_id = uuid4()
        token = "valid_token_with_enough_length_aaa"
        pool = _make_pool(
            {
                "reply_token": token,
                "reply_received_at": None,
                "state": STATE_AWAITING_REPLY,
            },
        )
        _override_pool(app, pool)

        response = self._post(client, incident_id, token)

        assert response.status_code == 200
        assert "Terima kasih" in response.text
        assert len(pool._conn.executed) == 1
        _query, args = pool._conn.executed[0]
        # args[1] is the next state (second positional after reason).
        assert args[1] == STATE_RESOLVED

    def test_reminder_sent_transitions_to_resolved_late(
        self, app: FastAPI, client: TestClient,
    ) -> None:
        incident_id = uuid4()
        token = "valid_token_with_enough_length_bbb"
        pool = _make_pool(
            {
                "reply_token": token,
                "reply_received_at": None,
                "state": STATE_REMINDER_SENT,
            },
        )
        _override_pool(app, pool)

        response = self._post(client, incident_id, token)

        assert response.status_code == 200
        _query, args = pool._conn.executed[0]
        assert args[1] == STATE_RESOLVED_LATE

    def test_escalated_state_is_preserved_on_late_reply(
        self, app: FastAPI, client: TestClient,
    ) -> None:
        """
        Reply arriving AFTER the ultimatum must NOT downgrade the state.
        We still record reply_received_at + reply_content for traceability,
        but state stays ESCALATED so the conduct history is intact.
        """
        incident_id = uuid4()
        token = "valid_token_with_enough_length_ccc"
        pool = _make_pool(
            {
                "reply_token": token,
                "reply_received_at": None,
                "state": STATE_ESCALATED,
            },
        )
        _override_pool(app, pool)

        response = self._post(
            client,
            incident_id,
            token,
            reason="Sorry, I had a family emergency on that day.",
        )

        assert response.status_code == 200
        assert "Terima kasih" in response.text
        _query, args = pool._conn.executed[0]
        # The state we wrote back must STILL be ESCALATED — not downgraded.
        assert args[1] == STATE_ESCALATED
        # And the reply content must still have made it through.
        assert args[0] == "Sorry, I had a family emergency on that day."

    def test_invalid_token_returns_404(
        self, app: FastAPI, client: TestClient,
    ) -> None:
        incident_id = uuid4()
        pool = _make_pool(
            {
                "reply_token": "the_real_token_xyzxyzxyzxyzxyz",
                "reply_received_at": None,
                "state": STATE_AWAITING_REPLY,
            },
        )
        _override_pool(app, pool)

        response = self._post(
            client, incident_id, "wrong_token_value_zzzzzzzzz",
        )

        assert response.status_code == 404
        # And no UPDATE should have been issued.
        assert pool._conn.executed == []

    def test_replay_after_first_reply_is_idempotent(
        self, app: FastAPI, client: TestClient,
    ) -> None:
        incident_id = uuid4()
        token = "valid_token_with_enough_length_ddd"
        pool = _make_pool(
            {
                "reply_token": token,
                "reply_received_at": datetime.now(tz=timezone.utc),
                "state": STATE_RESOLVED,
            },
        )
        _override_pool(app, pool)

        response = self._post(client, incident_id, token)

        assert response.status_code == 200
        assert "Sudah dijawab" in response.text
        # No UPDATE should have been issued the second time.
        assert pool._conn.executed == []
