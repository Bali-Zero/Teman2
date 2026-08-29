"""Database contracts of NotificationService.

These pin three defects measured in production on 2026-08-29 (Sentry org
``bali-zero-7p``, project ``nuzantara-backend``, 362 events each over 14 days —
matching the hourly ``_send_pending_alerts`` job, 24 x 14 = 336):

1. ``UndefinedTableError: relation "users" does not exist`` — ``_get_team_leader_email``
   queried a table that does not exist in this database. The staff directory is
   ``team_members`` (63 ``FROM team_members`` call sites against 27 ``FROM users``,
   of which 24 are fake SQL inside debugger tests).
2. ``AmbiguousParameterError: inconsistent types deduced for parameter $1`` —
   ``_update_alert_status`` used ``$1`` both as the value of a ``VARCHAR(20)``
   column and as the left side of a comparison against a text literal, so
   Postgres could not infer a single type for it.
3. The consequence of (1) that actually hurt a client: the team leader is only a
   **BCC**. Because the lookup ran unguarded inside ``process_alert``, a database
   error while fetching an optional BCC aborted the whole send, so the alert
   e-mail never reached the client at all — and the ``except`` handler then hit
   defect (2) while trying to record the failure, leaving the row ``pending``
   forever.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from backend.app.modules.notifications.models import (
    AlertStatus,
    AlertType,
    ClientAlert,
)
from backend.app.modules.notifications.service import NotificationService


class _RecordingConnection:
    """Captures every SQL string the service sends, and can be told to fail."""

    def __init__(self, *, fetchrow_error: Exception | None = None):
        self.statements: list[str] = []
        self.args: list[tuple] = []
        self._fetchrow_error = fetchrow_error

    async def fetchrow(self, sql, *args):
        self.statements.append(sql)
        self.args.append(args)
        if self._fetchrow_error is not None:
            raise self._fetchrow_error
        return {"email": "leader@balizero.com"}

    async def execute(self, sql, *args):
        self.statements.append(sql)
        self.args.append(args)
        return "UPDATE 1"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _pool(conn: _RecordingConnection) -> Mock:
    pool = Mock()
    pool.acquire = Mock(return_value=conn)
    return pool


def _service(conn: _RecordingConnection, *, send_ok: bool = True) -> NotificationService:
    provider = Mock()
    provider.send_email = AsyncMock(return_value=send_ok)
    return NotificationService(db_pool=_pool(conn), email_provider=provider)


def _alert(alert_type: AlertType) -> ClientAlert:
    return ClientAlert(
        id=1,
        client_id=42,
        alert_type=alert_type,
        status=AlertStatus.PENDING,
        message="m",
        email_subject="s",
        email_body="<p>b</p>",
        created_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
    )


class TestTeamLeaderLookupTargetsARealTable:
    @pytest.mark.asyncio
    async def test_queries_team_members_and_never_the_absent_users_table(self):
        conn = _RecordingConnection()
        service = _service(conn)

        await service._get_team_leader_email(42)

        sql = " ".join(conn.statements).lower()
        assert "team_members" in sql, "the staff directory is team_members"
        assert "from users" not in sql, (
            'relation "users" does not exist in this database — production raised '
            "UndefinedTableError 362 times in 14 days on this query"
        )


class TestAlertStatusUpdateIsUnambiguous:
    @pytest.mark.asyncio
    async def test_status_parameter_is_not_reused_across_two_inferred_types(self):
        conn = _RecordingConnection()
        service = _service(conn)

        await service._update_alert_status(_alert(AlertType.BIRTHDAY), AlertStatus.SENT)

        update = next(s for s in conn.statements if "update notification_alerts" in s.lower())
        normalised = " ".join(update.split())
        # $1 feeds a VARCHAR(20) column AND a comparison against a text literal.
        # Without an explicit cast Postgres deduces two different types for one
        # placeholder and asyncpg raises AmbiguousParameterError.
        assert "$1 = 'sent'" not in normalised, (
            "bare $1 compared to a text literal while also assigned to status "
            "VARCHAR(20) — this is the AmbiguousParameterError seen in production"
        )


class TestAnOptionalBccNeverBlocksTheAlert:
    @pytest.mark.asyncio
    async def test_client_is_still_emailed_when_the_team_leader_lookup_fails(self):
        """A BCC is a nicety; a passport-expiry warning is not."""
        conn = _RecordingConnection(fetchrow_error=RuntimeError("relation does not exist"))
        service = _service(conn)

        result = await service.process_alert(
            _alert(AlertType.PASSPORT_CRITICAL), "client@example.com"
        )

        service.email_provider.send_email.assert_awaited_once()
        assert result.success is True
        sent = service.email_provider.send_email.await_args.kwargs
        assert sent["to_email"] == "client@example.com"
        assert not sent.get("bcc"), "the BCC is dropped, the alert still goes out"


class TestOneBadAlertNeverEndsTheRun:
    """The queue is oldest-first with no LIMIT (``service.py`` ``get_pending_alerts``).

    Before 2026-08-29 ``process_alerts_batch`` had no per-item guard, so the first
    alert that raised took the whole run down with it — every alert behind it was
    never attempted, and produced no Sentry event either, because the code that
    would have raised for them never ran.
    """

    @pytest.mark.asyncio
    async def test_the_alerts_behind_a_failing_one_are_still_attempted(self):
        conn = _RecordingConnection()
        service = _service(conn)

        async def email_for(client_id):
            if client_id == 1:
                raise RuntimeError("lookup exploded")
            return f"c{client_id}@example.com"

        alerts = [_alert(AlertType.BIRTHDAY) for _ in range(3)]
        for i, alert in enumerate(alerts, start=1):
            alert.id = i
            alert.client_id = i

        results = await service.process_alerts_batch(alerts, email_for)

        assert len(results) == 3, "every alert gets a result, none is silently skipped"
        assert results[0].success is False
        assert [r.success for r in results[1:]] == [True, True]
        assert service.email_provider.send_email.await_count == 2


class TestRecordingAFailureNeverMasksIt:
    @pytest.mark.asyncio
    async def test_a_broken_status_update_does_not_replace_the_real_error(self):
        """The status UPDATE runs inside the ``except`` that handles the real error.

        When it raised too (the AmbiguousParameterError), it escaped ``process_alert``
        and became the only thing Sentry ever saw — hiding the cause underneath.
        """
        conn = _RecordingConnection()
        service = _service(conn)
        service.email_provider.send_email = AsyncMock(side_effect=RuntimeError("smtp down"))

        async def execute_that_fails(sql, *args):
            raise RuntimeError("ambiguous parameter")

        conn.execute = execute_that_fails

        result = await service.process_alert(_alert(AlertType.BIRTHDAY), "c@example.com")

        assert result.success is False
        assert "smtp down" in result.error_message, (
            "the surfaced error must be the real cause, not the bookkeeping failure"
        )
