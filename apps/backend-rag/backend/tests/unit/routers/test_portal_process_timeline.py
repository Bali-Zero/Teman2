"""Tests for portal process timeline endpoint."""

import logging
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from backend.app.routers.portal_process_timeline import _build_timeline


@pytest.mark.asyncio
async def test_timeline_returns_steps_for_valid_practice() -> None:
    """Timeline endpoint returns ordered steps for a practice belonging to the client."""
    mock_conn = AsyncMock()

    mock_conn.fetchrow.return_value = {
        "id": 10,
        "client_id": 1,
        "status": "in_progress",
        "start_date": "2026-01-15",
        "completion_date": None,
        "expiry_date": None,
        "notes": None,
        "practice_name": "KITAS B211A",
        "practice_category": "visa",
        "assigned_to": "asya@balizero.com",
    }

    mock_conn.fetch.return_value = [
        {
            "old_status": None,
            "new_status": "inquiry",
            "changed_at": "2026-01-15T10:00:00+00:00",
            "changed_by": "system",
        },
        {
            "old_status": "inquiry",
            "new_status": "quotation_sent",
            "changed_at": "2026-01-15T14:00:00+00:00",
            "changed_by": "asya@balizero.com",
        },
        {
            "old_status": "quotation_sent",
            "new_status": "payment_pending",
            "changed_at": "2026-01-16T09:00:00+00:00",
            "changed_by": "asya@balizero.com",
        },
        {
            "old_status": "payment_pending",
            "new_status": "in_progress",
            "changed_at": "2026-01-17T11:00:00+00:00",
            "changed_by": "system",
        },
    ]

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _build_timeline(mock_pool, practice_id=10, client_id=1)

    assert result is not None
    assert result["practice_id"] == 10
    assert result["practice_name"] == "KITAS B211A"
    assert result["current_status"] == "in_progress"
    assert len(result["steps"]) == 4
    assert result["steps"][0]["status"] == "inquiry"
    assert result["steps"][0]["completed"] is True
    assert result["steps"][-1]["status"] == "in_progress"
    assert result["steps"][-1]["is_current"] is True


@pytest.mark.asyncio
async def test_timeline_returns_none_for_wrong_client() -> None:
    """Timeline endpoint returns None if practice does not belong to the client."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = None

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _build_timeline(mock_pool, practice_id=999, client_id=1)
    assert result is None


@pytest.mark.asyncio
async def test_timeline_fallback_when_no_status_log() -> None:
    """Timeline returns single step when practice_status_log table doesn't exist."""
    mock_conn = AsyncMock()

    mock_conn.fetchrow.return_value = {
        "id": 5,
        "client_id": 1,
        "status": "waiting_documents",
        "start_date": "2026-02-01",
        "completion_date": None,
        "expiry_date": None,
        "notes": None,
        "practice_name": "PT PMA Setup",
        "practice_category": "company",
        "assigned_to": "damar@balizero.com",
    }

    # Simulate table not existing
    mock_conn.fetch.side_effect = asyncpg.UndefinedTableError(
        "relation practice_status_log does not exist"
    )

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _build_timeline(mock_pool, practice_id=5, client_id=1)

    assert result is not None
    assert result["practice_name"] == "PT PMA Setup"
    assert len(result["steps"]) == 1
    assert result["steps"][0]["status"] == "waiting_documents"
    assert result["steps"][0]["is_current"] is True


@pytest.mark.asyncio
async def test_timeline_response_never_carries_staff_identity() -> None:
    """Client-facing timeline must not leak staff actor identity.

    `changed_by` (practice_status_log actor) and `assigned_to` (case
    officer) are staff email addresses — internal identity, never
    client-facing. Even if a row/mock still carries them (e.g. a stale
    caller or a DB column that outlives this query), the response dict
    built for the client must not surface either key, at any nesting
    level (outer dict + every step dict, both the history-rows path and
    the single-step fallback path).
    """
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "id": 20,
        "client_id": 1,
        "status": "in_progress",
        "start_date": "2026-01-15",
        "completion_date": None,
        "expiry_date": None,
        "notes": None,
        "practice_name": "KITAS B211A",
        "practice_category": "visa",
        # Extra keys a looser mock/caller might still attach — must never
        # be read into the response even if present on the row.
        "assigned_to": "staff@example.com",
    }
    mock_conn.fetch.return_value = [
        {
            "old_status": None,
            "new_status": "inquiry",
            "changed_at": "2026-01-15T10:00:00+00:00",
            "changed_by": "staff@example.com",
        },
        {
            "old_status": "inquiry",
            "new_status": "in_progress",
            "changed_at": "2026-01-16T09:00:00+00:00",
            "changed_by": "other-staff@example.com",
        },
    ]

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _build_timeline(mock_pool, practice_id=20, client_id=1)

    assert result is not None
    assert "assigned_to" not in result
    assert len(result["steps"]) == 2
    for step in result["steps"]:
        assert "changed_by" not in step


@pytest.mark.asyncio
async def test_timeline_fallback_response_never_carries_staff_identity() -> None:
    """Same guarantee on the single-step fallback path (no status_log rows)."""
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {
        "id": 21,
        "client_id": 1,
        "status": "waiting_documents",
        "start_date": "2026-02-01",
        "completion_date": None,
        "expiry_date": None,
        "notes": None,
        "practice_name": "PT PMA Setup",
        "practice_category": "company",
        "assigned_to": "staff@example.com",
    }
    mock_conn.fetch.side_effect = asyncpg.UndefinedTableError(
        "relation practice_status_log does not exist"
    )

    mock_pool = MagicMock()
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    result = await _build_timeline(mock_pool, practice_id=21, client_id=1)

    assert result is not None
    assert "assigned_to" not in result
    assert len(result["steps"]) == 1
    assert "changed_by" not in result["steps"][0]


def _practice_row(status: str = "waiting_documents") -> dict:
    return {
        "id": 5,
        "client_id": 1,
        "status": status,
        "start_date": "2026-02-01",
        "completion_date": None,
        "expiry_date": None,
        "notes": None,
        "practice_name": "PT PMA Setup",
        "practice_category": "company",
        "assigned_to": "damar@balizero.com",
    }


def _pool_for(mock_conn) -> MagicMock:
    pool = MagicMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
    return pool


class TestHistoryFailuresAreNotSpelledAsEmptyHistory:
    """A missing table and a broken query must not look the same.

    Until migration 310 the history query was wrapped in a bare
    `except Exception: pass`, so BOTH cases produced a one-step timeline and a
    200 — and an empty history is indistinguishable from a practice that never
    moved. Prod was measured in that state on 2026-08-27: the table did not
    exist at all, so every tracker request took the silent path.
    """

    @pytest.mark.asyncio
    async def test_absent_table_degrades_but_says_so(self, caplog) -> None:
        """The pre-310 database still serves a timeline, and logs a warning."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = _practice_row()
        mock_conn.fetch.side_effect = asyncpg.UndefinedTableError(
            "relation practice_status_log does not exist"
        )

        with caplog.at_level(logging.WARNING, logger="backend.app.routers.portal_process_timeline"):
            result = await _build_timeline(_pool_for(mock_conn), practice_id=5, client_id=1)

        assert result is not None
        assert len(result["steps"]) == 1
        joined = " ".join(r.getMessage() for r in caplog.records)
        assert "practice_status_log is absent" in joined
        assert "310" in joined, "the log line must name the migration that fixes it"

    @pytest.mark.asyncio
    async def test_a_real_db_error_still_degrades_but_is_no_longer_SILENT(self, caplog) -> None:
        """A fault still yields a one-step timeline — it is no longer unlogged.

        The name matters and an earlier one overclaimed: this test was called
        "..._is_logged_not_swallowed" while asserting `len(steps) == 1`, i.e.
        asserting the swallowing. An adversarial review caught the mismatch.

        The DEGRADATION is deliberate and unchanged: a client asking about their
        own practice should not get a 500 because history is unavailable. What
        changed is only that the fault is now on the record at ERROR with a
        traceback, instead of vanishing into `except Exception: pass`. Note the
        scope this leaves: `asyncpg.PostgresError` also covers a query timeout
        and a schema drift (`QueryCanceledError`, `UndefinedColumnError`), and
        each of those likewise renders as a one-step timeline. Logged, not
        surfaced. Turning any of them into a client-visible failure is a
        product decision, not a bug fix, and is not made here.
        """
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = _practice_row()
        mock_conn.fetch.side_effect = asyncpg.InsufficientPrivilegeError(
            "permission denied for table practice_status_log"
        )

        with caplog.at_level(logging.ERROR, logger="backend.app.routers.portal_process_timeline"):
            result = await _build_timeline(_pool_for(mock_conn), practice_id=5, client_id=1)

        # Still serves the current status — a client asking about their own
        # practice should not get a 500 because history is unavailable.
        assert result is not None
        assert len(result["steps"]) == 1
        # …but the fault is on the record, at ERROR, with a traceback.
        assert any(r.levelno >= logging.ERROR for r in caplog.records)
        assert any(r.exc_info for r in caplog.records), "must log the traceback"
        assert "practice_status_log query failed" in " ".join(
            r.getMessage() for r in caplog.records
        )

    @pytest.mark.asyncio
    async def test_a_dropped_connection_degrades_it_does_not_become_a_500(self, caplog) -> None:
        """`asyncpg.InterfaceError` is NOT a `PostgresError` — measured, not assumed.

        Its MRO is `InterfaceError -> InterfaceMessage -> Exception`; it does not
        descend from `PostgresError` at all. So narrowing the original
        `except Exception` to the two Postgres classes silently created a NEW
        failure mode: a connection dropped between `fetchrow()` and `fetch()`
        escaped both handlers and reached the client as a 500, where the bare
        handler this replaced degraded to a 200.

        That is a regression introduced by the narrowing itself, found by a third
        adversarial round, and this test is the guilt proof: remove
        `asyncpg.InterfaceError` from the handler tuple in the router and this
        goes RED with the InterfaceError propagating, while the
        `InsufficientPrivilegeError` test above stays green — the two are
        genuinely different classes, not one assertion wearing two names.
        """
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = _practice_row()
        mock_conn.fetch.side_effect = asyncpg.InterfaceError("connection is closed")

        with caplog.at_level(logging.ERROR, logger="backend.app.routers.portal_process_timeline"):
            result = await _build_timeline(_pool_for(mock_conn), practice_id=5, client_id=1)

        assert result is not None, "a dropped connection must not become a client-facing 500"
        assert len(result["steps"]) == 1
        assert any(r.exc_info for r in caplog.records), "must log the traceback"

    def test_interface_error_is_not_a_postgres_error(self) -> None:
        """Pins the fact the handler depends on, so a future tidy cannot undo it.

        If someone collapses the tuple back to `except asyncpg.PostgresError`
        reasoning that "InterfaceError is surely a PostgresError", this states
        plainly that it is not. The assertion is about the library, not our code,
        which is exactly why it is worth writing down.
        """
        assert not issubclass(asyncpg.InterfaceError, asyncpg.PostgresError)
        assert issubclass(asyncpg.UndefinedTableError, asyncpg.PostgresError)

    @pytest.mark.asyncio
    async def test_a_non_database_error_still_propagates(self) -> None:
        """The narrowed except must not become a new catch-all.

        A bug in this function (a TypeError, an attribute error on a row) is
        not a degraded-history condition and must reach the caller instead of
        being rendered as a practice that never moved.
        """
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = _practice_row()
        mock_conn.fetch.side_effect = TypeError("not a postgres problem")

        with pytest.raises(TypeError):
            await _build_timeline(_pool_for(mock_conn), practice_id=5, client_id=1)


class TestTheTimelineSurvivesAStatusProductionActuallyAllows:
    """`practices.status` is NULLABLE in prod, and the reader assumed a string.

    Measured 2026-08-27 against the code as it stood: BOTH paths raised
    `AttributeError: 'NoneType' object has no attribute 'replace'` — including
    the fallback path, which is the one production takes today. This was a LIVE
    500 on the client tracker for any practice with a NULL status, not a defect
    migration 310 introduced; 310 only makes a second path reach it.

    The cause is subtle enough to be worth naming: the call was
    `STATUS_LABELS.get(status, status.replace(...))`, and Python evaluates a
    `dict.get` DEFAULT eagerly — so it raised before the lookup that would have
    succeeded.

    WHAT THESE TWO TESTS DO NOT CLAIM, stated because both review seats of the
    2026-09-11 council named it: a payload carrying `"status": null` is still
    REJECTED WHOLESALE by the client. `apps/mouth/src/lib/schemas/process.ts`
    types `ProcessStep.status` and `ProcessTimelineData.current_status` as
    members of a closed, non-nullable `z.enum`, so Zod discards the entire
    response and the tracker shows "unable to load" instead of a 500. What is
    fixed here is only the AttributeError; making a NULL status renderable
    needs a value on BOTH sides of the contract (`unknown` in the enum, or
    `SET NOT NULL` with a backfill — 0 rows measured 2026-08-27), which is a
    contract change and is not made in this PR. These tests pin the crash that
    is fixed; they do not assert that the client can render the result.
    """

    @pytest.mark.asyncio
    async def test_a_null_status_does_not_crash_the_fallback_path(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = _practice_row(status=None)
        mock_conn.fetch.side_effect = asyncpg.UndefinedTableError("no table")

        result = await _build_timeline(_pool_for(mock_conn), practice_id=5, client_id=1)

        assert result is not None
        assert result["steps"][0]["status"] is None
        assert result["steps"][0]["label"] == "Unknown"

    @pytest.mark.asyncio
    async def test_a_null_status_does_not_crash_the_history_path(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = _practice_row(status=None)
        mock_conn.fetch.return_value = [
            {"old_status": "on_process", "new_status": None, "changed_at": "2026-01-01"}
        ]

        result = await _build_timeline(_pool_for(mock_conn), practice_id=5, client_id=1)

        assert result is not None
        assert result["steps"][-1]["label"] == "Unknown"


class TestATerminalStatusIsNeverRenderedAsInProgress:
    """The two paths used to disagree about a finished practice.

    The history path marked the last row current whenever it matched the
    practice's status, so a completed practice came back as
    `{"status": "completed", "completed": False, "is_current": True}` and the
    client rendered a spinning loader on finished work — while the fallback
    path, ten lines below, got the same practice right. Caught by an adversarial
    review, and reachable only because 310 makes the history path run at all.
    """

    @pytest.mark.asyncio
    async def test_completed_is_completed_not_current_on_the_history_path(self) -> None:
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = _practice_row(status="completed")
        mock_conn.fetch.return_value = [
            {"old_status": None, "new_status": "on_process", "changed_at": "2026-01-01"},
            {
                "old_status": "on_process",
                "new_status": "completed",
                "changed_at": "2026-01-02",
            },
        ]

        result = await _build_timeline(_pool_for(mock_conn), practice_id=5, client_id=1)

        last = result["steps"][-1]
        assert last["status"] == "completed"
        assert last["is_current"] is False, "a finished practice is not in progress"
        assert last["completed"] is True

    @pytest.mark.asyncio
    async def test_a_non_terminal_last_step_IS_current(self) -> None:
        """Innocence: the fix must not mark everything finished."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = _practice_row(status="on_process")
        mock_conn.fetch.return_value = [
            {"old_status": "inquiry", "new_status": "on_process", "changed_at": "2026-01-02"}
        ]

        result = await _build_timeline(_pool_for(mock_conn), practice_id=5, client_id=1)

        last = result["steps"][-1]
        assert last["is_current"] is True
        assert last["completed"] is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            ("completed", (True, False)),
            ("approved", (True, False)),
            ("cancelled", (True, False)),
            ("on_process", (False, True)),
        ],
    )
    async def test_both_paths_answer_identically_for_the_same_status(
        self, status, expected
    ) -> None:
        """DoD #3 of the spec: one practice, both paths, the same two flags.

        The previous round fixed the disagreement for `completed` and `approved`
        only. `cancelled` kept it: the history path said `completed=True` (a
        filled tick) and the fallback path `completed=False` (a grey circle) for
        the same practice — so applying migration 310 would have changed how
        every cancelled practice renders, with no frontend change and no test
        going red (124 of 893 when measured 2026-08-27; 137 of 1011 on
        2026-09-11 — the count moves, the defect did not).
        A review seat drove both paths and reported the two answers side by side.

        Parametrised over every terminal status AND a non-terminal one, because
        a helper that returned a constant would satisfy a single case. The flags
        now come from `_step_flags`, so this asserts the two branches CALL it
        rather than each carrying its own copy of the rule.
        """
        history_conn = AsyncMock()
        history_conn.fetchrow.return_value = _practice_row(status=status)
        history_conn.fetch.return_value = [
            {"old_status": "inquiry", "new_status": status, "changed_at": "2026-01-02"}
        ]

        fallback_conn = AsyncMock()
        fallback_conn.fetchrow.return_value = _practice_row(status=status)
        fallback_conn.fetch.side_effect = asyncpg.UndefinedTableError("no table")

        from_history = await _build_timeline(
            _pool_for(history_conn), practice_id=5, client_id=1
        )
        from_fallback = await _build_timeline(
            _pool_for(fallback_conn), practice_id=5, client_id=1
        )

        h, f = from_history["steps"][-1], from_fallback["steps"][-1]
        assert (h["completed"], h["is_current"]) == (f["completed"], f["is_current"]), (
            f"the two paths disagree for {status!r}: history says "
            f"completed={h['completed']}/is_current={h['is_current']}, fallback says "
            f"completed={f['completed']}/is_current={f['is_current']}"
        )
        # ...and the pair they agree on is the RIGHT one. Agreement alone is a
        # weak assertion: a helper returning a constant `(True, False)` makes
        # every case above pass, and a round-2 seat reproduced exactly that —
        # dropping `approved` from TERMINAL_STATUSES left the whole file at 19
        # passed while `approved` rendered as still in progress.
        assert (h["completed"], h["is_current"]) == expected, (
            f"history path answers {(h['completed'], h['is_current'])} for {status!r}, "
            f"expected {expected}"
        )
        assert (f["completed"], f["is_current"]) == expected, (
            f"fallback path answers {(f['completed'], f['is_current'])} for {status!r}, "
            f"expected {expected}"
        )

    @pytest.mark.asyncio
    async def test_cancelled_is_closed_but_not_rendered_as_a_success(self) -> None:
        """RULED 2026-09-11 (Zero, Q2 of practice-timeline-semantics-v1).

        A cancelled practice is a step that is CLOSED — nothing is still
        running, so `is_current` is False and the client shows no spinner — and
        `completed` is True. It is not confused with a successful practice
        because the client colours it by STATUS: `stateColors.ts` maps
        `cancelled` to `danger`, not to the success tone. This test pins the
        backend half of that ruling; the colour mapping is the frontend's.
        """
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = _practice_row(status="cancelled")
        mock_conn.fetch.return_value = [
            {"old_status": "inquiry", "new_status": "cancelled", "changed_at": "2026-01-02"}
        ]

        result = await _build_timeline(_pool_for(mock_conn), practice_id=5, client_id=1)

        last = result["steps"][-1]
        assert last["status"] == "cancelled", "the client needs the status to colour it"
        assert last["is_current"] is False, "a cancelled practice is not in flight"
        assert last["completed"] is True, "a cancelled practice is closed"
