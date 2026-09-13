"""Real-Postgres integration tests for the notification-alert write path.

Covers two coupled fixes in ``backend.app.modules.notifications.service``
(``NotificationService``):

1. ``_update_alert_status`` — the UPDATE used to read
   ``status = $1`` alongside ``CASE WHEN $1::text = 'sent'``. Postgres deduces
   a single type per parameter from ALL of its uses in one statement; here
   ``status`` is ``character varying`` while the cast said ``text``, so
   PREPARE always failed with ``asyncpg.exceptions.AmbiguousParameterError``.
   This is a PREPARE-time defect: a mocked connection (``AsyncMock``/a fake
   that just records the SQL string) executes the broken SQL exactly as
   happily as the fixed SQL, because nothing ever asks a real Postgres to
   PREPARE it. Only a real Postgres exhibits the failure, so this file talks
   to one — see ``backend/tests/db/conftest.py``'s ``db_tx`` fixture (a real
   ``asyncpg.Connection`` wrapped in a transaction rolled back at teardown).
   ``test_bare_dollar1_reused_as_text_and_varchar_still_raises_in_postgres``
   below re-executes the ORIGINAL buggy SQL text (not the code under test)
   directly against Postgres so this file carries its own independent proof
   that the defect is real and that the fix's phrasing avoids it, without
   requiring anyone to hand-edit ``service.py`` to observe the regression.

2. ``supersede_duplicate_pending_alerts`` — collapses repeated ``pending``
   alerts for the same ``(client_id, alert_type)`` down to the newest,
   because the queue is drained on every poll and #1 above meant no alert
   had ever actually left ``pending``, so a live client backlog of ~3120
   duplicate rows had accumulated. These tests exercise the real SQL,
   including the ``(created_at, id)`` tuple tie-break and the schema's own
   ``uq_notification_alert_daily`` unique index (only one pending alert per
   client+type+day) that makes a genuine timestamp tie unreachable in
   production — the tie test says explicitly why it drops that index inside
   its own rolled-back transaction to isolate the tuple comparison.

``notification_alerts`` is defined by the legacy module-level migration
``backend.migrations.migration_071_notification_alerts`` (not one of the
``migrations_v2/*.sql`` files applied to the ``nuzantara_test`` template), so
it does not exist there permanently. ``notif_conn`` below creates it with the
migration's own ``UPGRADE_SQL`` (``CREATE TABLE IF NOT EXISTS`` — idempotent)
inside ``db_tx``'s transaction; DDL is transactional in Postgres, so it
disappears with everything else at rollback and never touches the shared
test database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import Mock

import asyncpg
import pytest
import pytest_asyncio

from backend.app.modules.notifications.models import AlertStatus, AlertType, ClientAlert
from backend.app.modules.notifications.service import NotificationService
from backend.migrations.migration_071_notification_alerts import UPGRADE_SQL

pytestmark = pytest.mark.integration


class _SingleConnectionPool:
    """Presents one real ``asyncpg.Connection`` as a ``db_pool``.

    ``NotificationService`` calls ``self.db_pool.acquire()``; every acquire
    here returns the SAME connection that ``db_tx`` set up (and will roll
    back), so a client row inserted by test setup is visible to the service
    without anything being committed for real — it is all one Postgres
    session and one transaction.
    """

    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    def acquire(self) -> Any:
        conn = self._conn

        class _Ctx:
            async def __aenter__(self_inner):
                return conn

            async def __aexit__(self_inner, *exc):
                return False

        return _Ctx()


@pytest_asyncio.fixture
async def notif_conn(db_tx: asyncpg.Connection) -> asyncpg.Connection:
    """``db_tx`` with ``notification_alerts`` guaranteed to exist (see module docstring)."""
    await db_tx.execute(UPGRADE_SQL)
    return db_tx


@pytest.fixture
def service(notif_conn: asyncpg.Connection) -> NotificationService:
    return NotificationService(db_pool=_SingleConnectionPool(notif_conn), email_provider=Mock())


_counter = 0


async def _make_client(conn: asyncpg.Connection, *, tag: str) -> int:
    global _counter
    _counter += 1
    row = await conn.fetchrow(
        "INSERT INTO clients (full_name, email) VALUES ($1, $2) RETURNING id",
        f"Test Client {tag}",
        f"test-{tag}-{_counter}@example.com",
    )
    return row["id"]


async def _insert_alert(
    conn: asyncpg.Connection,
    *,
    client_id: int,
    created_at: datetime,
    alert_type: AlertType = AlertType.BIRTHDAY,
    status: AlertStatus = AlertStatus.PENDING,
) -> int:
    row = await conn.fetchrow(
        """
        INSERT INTO notification_alerts
            (client_id, alert_type, status, message, email_subject, email_body, created_at)
        VALUES ($1, $2, $3, 'm', 's', '<p>b</p>', $4)
        RETURNING id
        """,
        client_id,
        alert_type.value,
        status.value,
        created_at,
    )
    return row["id"]


# ============================================================================
# 1. `_update_alert_status` against a real Postgres PREPARE
# ============================================================================


class TestUpdateAlertStatusAgainstRealPostgres:
    @pytest.mark.asyncio
    async def test_sent_status_persists_and_stamps_sent_at(
        self, service: NotificationService, notif_conn: asyncpg.Connection
    ) -> None:
        client_id = await _make_client(notif_conn, tag="sent")
        created = datetime(2026, 1, 1, tzinfo=timezone.utc)
        alert_id = await _insert_alert(notif_conn, client_id=client_id, created_at=created)
        alert = ClientAlert(
            id=alert_id,
            client_id=client_id,
            alert_type=AlertType.BIRTHDAY,
            status=AlertStatus.PENDING,
            message="m",
            email_subject="s",
            email_body="<p>b</p>",
            created_at=created,
        )

        await service._update_alert_status(alert, AlertStatus.SENT)

        row = await notif_conn.fetchrow(
            "SELECT status, sent_at FROM notification_alerts WHERE id = $1", alert_id
        )
        assert row["status"] == "sent"
        assert row["sent_at"] is not None

    @pytest.mark.asyncio
    async def test_failed_status_persists_without_sent_at(
        self, service: NotificationService, notif_conn: asyncpg.Connection
    ) -> None:
        client_id = await _make_client(notif_conn, tag="failed")
        created = datetime(2026, 1, 2, tzinfo=timezone.utc)
        alert_id = await _insert_alert(notif_conn, client_id=client_id, created_at=created)
        alert = ClientAlert(
            id=alert_id,
            client_id=client_id,
            alert_type=AlertType.BIRTHDAY,
            status=AlertStatus.PENDING,
            message="m",
            email_subject="s",
            email_body="<p>b</p>",
            created_at=created,
        )

        await service._update_alert_status(alert, AlertStatus.FAILED, "smtp down")

        row = await notif_conn.fetchrow(
            "SELECT status, sent_at, error_message FROM notification_alerts WHERE id = $1",
            alert_id,
        )
        assert row["status"] == "failed"
        assert row["sent_at"] is None
        assert row["error_message"] == "smtp down"

    @pytest.mark.asyncio
    async def test_bare_dollar1_reused_as_text_and_varchar_still_raises_in_postgres(
        self, notif_conn: asyncpg.Connection
    ) -> None:
        """Independent proof the defect is real, without editing ``service.py``.

        This executes the ORIGINAL buggy statement text verbatim (the form
        ``_update_alert_status`` carried before the fix: ``status = $1``
        reused inside ``CASE WHEN $1::text = 'sent'``) directly against the
        same real ``notification_alerts`` table this file creates. It must
        raise ``AmbiguousParameterError`` every time PostgreSQL is asked to
        PREPARE it — that is the whole defect, and it is independent of
        whatever ``service.py`` currently contains. Verified interactively
        against this same local Postgres before this file was written; verbatim:
        ``AmbiguousParameterError: inconsistent types deduced for parameter $1``
        / ``DETAIL: text versus character varying``.
        """
        client_id = await _make_client(notif_conn, tag="ambiguous")
        alert_id = await _insert_alert(
            notif_conn, client_id=client_id, created_at=datetime(2026, 1, 3, tzinfo=timezone.utc)
        )

        with pytest.raises(asyncpg.exceptions.AmbiguousParameterError) as exc_info:
            await notif_conn.execute(
                """
                UPDATE notification_alerts
                SET status = $1,
                    sent_at = CASE WHEN $1::text = 'sent' THEN NOW() ELSE sent_at END,
                    error_message = $2
                WHERE id = $3
                """,
                "sent",
                None,
                alert_id,
            )

        assert "inconsistent types deduced for parameter $1" in str(exc_info.value)


# ============================================================================
# 2. `supersede_duplicate_pending_alerts` — guilt + innocence + idempotence + tie
# ============================================================================


class TestSupersedeDuplicatePendingAlerts:
    @pytest.mark.asyncio
    async def test_three_pending_same_client_and_type_collapse_to_the_newest(
        self, service: NotificationService, notif_conn: asyncpg.Connection
    ) -> None:
        client_id = await _make_client(notif_conn, tag="guilt")
        id_old = await _insert_alert(
            notif_conn, client_id=client_id, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        id_mid = await _insert_alert(
            notif_conn, client_id=client_id, created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)
        )
        id_new = await _insert_alert(
            notif_conn, client_id=client_id, created_at=datetime(2026, 1, 3, tzinfo=timezone.utc)
        )

        superseded = await service.supersede_duplicate_pending_alerts()

        assert superseded == 2
        rows = {
            r["id"]: r
            for r in await notif_conn.fetch(
                "SELECT id, status, error_message FROM notification_alerts WHERE id = ANY($1)",
                [id_old, id_mid, id_new],
            )
        }
        assert rows[id_new]["status"] == "pending"
        assert rows[id_mid]["status"] == "suppressed"
        assert rows[id_old]["status"] == "suppressed"
        assert (
            rows[id_old]["error_message"] == "superseded by a newer pending alert of the same type"
        )
        assert (
            rows[id_mid]["error_message"] == "superseded by a newer pending alert of the same type"
        )

    @pytest.mark.asyncio
    async def test_different_alert_types_both_stay_pending(
        self, service: NotificationService, notif_conn: asyncpg.Connection
    ) -> None:
        """INNOCENCE: a dedup that collapses across TYPES would silence real warnings."""
        client_id = await _make_client(notif_conn, tag="innocent-type")
        id_a = await _insert_alert(
            notif_conn,
            client_id=client_id,
            alert_type=AlertType.BIRTHDAY,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        id_b = await _insert_alert(
            notif_conn,
            client_id=client_id,
            alert_type=AlertType.PASSPORT_WARNING,
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )

        superseded = await service.supersede_duplicate_pending_alerts()

        assert superseded == 0
        rows = await notif_conn.fetch(
            "SELECT status FROM notification_alerts WHERE id = ANY($1)", [id_a, id_b]
        )
        assert {r["status"] for r in rows} == {"pending"}

    @pytest.mark.asyncio
    async def test_different_clients_same_type_both_stay_pending(
        self, service: NotificationService, notif_conn: asyncpg.Connection
    ) -> None:
        """INNOCENCE: dedup must be scoped per client, never cross-client."""
        client_a = await _make_client(notif_conn, tag="innocent-client-a")
        client_b = await _make_client(notif_conn, tag="innocent-client-b")
        id_a = await _insert_alert(
            notif_conn, client_id=client_a, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        id_b = await _insert_alert(
            notif_conn, client_id=client_b, created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)
        )

        superseded = await service.supersede_duplicate_pending_alerts()

        assert superseded == 0
        rows = await notif_conn.fetch(
            "SELECT status FROM notification_alerts WHERE id = ANY($1)", [id_a, id_b]
        )
        assert {r["status"] for r in rows} == {"pending"}

    @pytest.mark.asyncio
    async def test_running_it_twice_the_second_run_changes_nothing(
        self, service: NotificationService, notif_conn: asyncpg.Connection
    ) -> None:
        client_id = await _make_client(notif_conn, tag="idempotent")
        await _insert_alert(
            notif_conn, client_id=client_id, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        await _insert_alert(
            notif_conn, client_id=client_id, created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)
        )

        first = await service.supersede_duplicate_pending_alerts()
        second = await service.supersede_duplicate_pending_alerts()

        assert first == 1
        assert second == 0

    @pytest.mark.asyncio
    async def test_a_tie_on_created_at_still_leaves_exactly_one_survivor(
        self, service: NotificationService, notif_conn: asyncpg.Connection
    ) -> None:
        """Exercises the `(created_at, id)` tuple comparison, not just `created_at`.

        `uq_notification_alert_daily` (one pending alert per client+alert_type
        per calendar day) makes a genuine timestamp TIE for the same
        (client_id, alert_type) unreachable in production — two rows on the
        same day already violate that index regardless of their exact time.
        Dropping the index here, inside this test's own transaction (rolled
        back at teardown by `db_tx`, so nothing outside this test ever sees
        it gone), isolates what the tuple comparison buys on its own: with a
        `created_at` tie, `id` breaks it, and the greater id survives. A test
        that only used distinct timestamps would never touch this code path.
        """
        await notif_conn.execute("DROP INDEX IF EXISTS uq_notification_alert_daily")
        client_id = await _make_client(notif_conn, tag="tie")
        tied_at = datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc)
        id_first = await _insert_alert(notif_conn, client_id=client_id, created_at=tied_at)
        id_second = await _insert_alert(notif_conn, client_id=client_id, created_at=tied_at)
        assert id_second > id_first, "BIGSERIAL must assign the second insert the higher id"

        superseded = await service.supersede_duplicate_pending_alerts()

        assert superseded == 1
        rows = {
            r["id"]: r["status"]
            for r in await notif_conn.fetch(
                "SELECT id, status FROM notification_alerts WHERE id = ANY($1)",
                [id_first, id_second],
            )
        }
        assert rows[id_second] == "pending", "higher id wins the (created_at, id) tie"
        assert rows[id_first] == "suppressed"
